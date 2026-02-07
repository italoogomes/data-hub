"""
MMarra Data Hub - Agente LLM
Agente inteligente que decide entre responder com documentacao ou consultar o banco.

Uso:
    from src.llm.agent import DataHubAgent

    agent = DataHubAgent()
    result = await agent.ask("Quantas notas de compra temos este mes?")
"""

import os
import sys
import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

# Import components
from src.llm.chat import KnowledgeBase
from src.llm.llm_client import LLMClient, LLM_MODEL, LLM_PROVIDER
from src.llm.query_executor import SafeQueryExecutor, QuerySecurityError

# ============================================================
# PROMPTS SIMPLIFICADOS PARA MODELO 8B
# ============================================================

CLASSIFIER_PROMPT = """Voce eh um classificador. Responda APENAS com uma unica palavra.

BANCO = usuario quer dados, numeros, listas, relatorios do sistema.
Palavras-chave: quantos, quais, lista, relatorio, pendente, total, maiores, top, marca, fornecedor, produto, valor, este mes, este ano, ranking, vendas, compras, notas, pedidos, estoque, financeiro.

DOC = usuario quer explicacao, conceito, processo, significado.
Palavras-chave: como funciona, o que eh, explique, qual o processo, o que significa, para que serve.

Pergunta: {pergunta}

Se tiver QUALQUER duvida, responda BANCO.

Resposta (BANCO ou DOC):"""

SQL_GENERATOR_PROMPT = """Gere APENAS o SELECT Oracle. Sem explicacao, sem markdown.

{relacionamentos}

REGRAS:
1. Para limitar resultados, usar WHERE ROWNUM <= N (NAO usar FETCH FIRST, NAO usar LIMIT)
2. Mes atual: DTNEG >= TRUNC(SYSDATE, 'MM')
3. GROUP BY com todas colunas nao-agregadas
4. Ordenar por valor DESC em agregacoes
5. NUNCA juntar TGFCAB com TGFPRO direto. Passar por TGFITE.
6. NAO colocar ponto-e-virgula no final
7. "previsao de entrega" = DTPREVENT (NUNCA usar DTNEG!). MOSTRAR com NVL(TO_CHAR(DTPREVENT,'DD/MM/YYYY'),'Sem previsao'). NAO filtrar IS NOT NULL.
8. FILTRAR por marca: UPPER(M.DESCRICAO) = UPPER('nome'). NUNCA PR.MARCA. SEMPRE UPPER().
9. COMPARACAO DE TEXTO: SEMPRE usar UPPER() em AMBOS os lados.
10. STATUS EM RELATORIOS: STATUSNOTA <> 'C' para excluir cancelados.
11. PENDENCIA: "pedidos pendentes" = PENDENTE = 'S' (campo do Sankhya que indica itens faltando). NAO usar STATUSNOTA = 'P' para pendencia.
12. TIPMOV COMPRA: "pedidos de compra" = TIPMOV = 'O'. "notas de compra/entradas" = TIPMOV = 'C'. "tudo de compra" = TIPMOV IN ('C','O').
13. REGRA DE NIVEL (CRITICA): Se a pergunta menciona MARCA ou PRODUTO, a query DEVE ser nivel ITEM: FROM TGFITE ITE JOIN TGFCAB CAB ON CAB.NUNOTA=ITE.NUNOTA JOIN TGFPRO PRO JOIN TGFMAR MAR. NUNCA usar EXISTS+VLRNOTA para marca. Valor por marca = ITE.VLRTOT. Pendencia = TGFVAR (QTD_PEDIDA - QTD_ATENDIDA).
14. Se a pergunta NAO menciona marca/produto: query nivel CABECALHO (FROM TGFCAB). VLRNOTA eh confiavel.

REGRA DE PENDENCIA (OBRIGATORIO):
- "pendencia" sem especificar = pendencia de COMPRA: PENDENTE='S' AND TIPMOV='O' AND STATUSNOTA<>'C'. Usar TGFCAB.VLRNOTA. SEM TGFFIN.
- "pendencia financeira/contas a pagar/titulos" = TGFFIN WHERE DHBAIXA IS NULL AND RECDESP=-1. SEM TGFITE.
- "pendencia de venda" = PENDENTE='S' AND TIPMOV='P' AND STATUSNOTA<>'C'. SEM TGFFIN.
- NUNCA juntar TGFFIN com TGFITE na mesma query (multiplica valores).
- NUNCA usar STATUSNOTA='P' para pendencia. O campo correto eh PENDENTE (S/N).

Pergunta: {pergunta}

ATENCAO FINAL (LER ANTES DE GERAR):
- NIVEL (CRITICA): Se menciona MARCA ou PRODUTO → FROM TGFITE ITE JOIN TGFCAB CAB JOIN TGFPRO PRO JOIN TGFMAR MAR LEFT JOIN TGFVAR. Valor = ITE.VLRTOT. NUNCA usar VLRNOTA com filtro de marca.
- NIVEL: Se NAO menciona marca/produto → FROM TGFCAB C. VLRNOTA ok.
- TEXTO: SEMPRE UPPER() em AMBOS os lados. Ex: UPPER(MAR.DESCRICAO) = UPPER('donaldson')
- PREVISAO: NVL(TO_CHAR(DTPREVENT,'DD/MM/YYYY'),'Sem previsao'). NAO filtrar IS NOT NULL.
- PENDENCIA: "pedidos pendentes" = PENDENTE='S'. NUNCA usar STATUSNOTA='P' para pendencia. STATUSNOTA<>'C' so para excluir cancelados.
- TIPMOV: "pedidos de compra" = TIPMOV='O'. "notas de compra" = TIPMOV='C'. "tudo de compra" = IN('C','O').

SELECT"""

DOC_ANSWER_PROMPT = """Responda a pergunta usando APENAS a documentacao fornecida abaixo.

Documentacao:
{context}

Pergunta: {pergunta}

Resposta (direta, clara, em portugues):"""

SQL_FIX_PROMPT = """A query abaixo deu erro no Oracle. Corrija. Responda APENAS com o SELECT corrigido.

Query: {sql}
Erro: {erro}

{relacionamentos}

REGRAS:
1. Aliases simples, sem aspas, sem espacos
2. GROUP BY com todas colunas nao-agregadas
3. ROWNUM <= 100
4. Oracle NAO tem LIMIT
5. NUNCA juntar TGFCAB com TGFPRO direto. Passar por TGFITE.

SELECT"""

FORMATTER_PROMPT = """Voce e um assistente de negocios da MMarra Distribuidora.

O usuario perguntou: {pergunta}

DADOS RETORNADOS DO BANCO DE DADOS (use SOMENTE estes dados, NAO invente nada):

{resultados}

Total de registros: {total_rows}

INSTRUCOES OBRIGATORIAS:
1. Use EXCLUSIVAMENTE os dados acima. NAO invente valores, nomes, datas ou qualquer informacao.
2. Se os dados estiverem vazios ou com valores zerados, mostre exatamente isso.
3. Comece com um resumo: quantidade encontrada e total em valor (se houver coluna de valor).
4. Monte uma tabela Markdown com os dados, usando nomes amigaveis nas colunas:
   - NUNOTA -> Pedido
   - NUMNOTA -> Numero NF
   - DTNEG -> Data
   - DTENTSAI -> Data Entrada/Saida
   - NOMEPARC -> Fornecedor ou Cliente (depende do contexto)
   - CODPARC -> Cod. Parceiro
   - VLRNOTA -> Valor
   - VLRTOT -> Valor Total
   - STATUSNOTA -> Status (A=Atendimento, L=Liberado, P=Pendente)
   - DTPREVENT -> Previsao de Entrega
   - TIPMOV -> Tipo (V=Venda, C=Compra, O=Pedido, J=Solicitacao)
   - DESCRPROD -> Produto
   - CODPROD -> Cod. Produto
   - QTDNEG -> Quantidade
   - VLRUNIT -> Valor Unitario
   - RAZAOSOCIAL -> Razao Social
   - NOMEFANTASIA -> Nome Fantasia
5. Adicione insights uteis ao final (maiores valores, padroes, destaques).
6. NAO mencione SQL, query, SELECT, JOIN, TIPMOV, STATUSNOTA ou termos tecnicos.
7. Formate valores como R$ 1.234,56 e datas como DD/MM/YYYY.
8. Se um valor for 0,00 ou NULL, mostre "R$ 0,00" - NAO invente outro valor.

EXEMPLO DE RESPOSTA IDEAL:
Encontrei 20 pedidos pendentes, totalizando R$ 150.000,00.

| Pedido | Data | Fornecedor | Valor | Status |
|--------|------|------------|-------|--------|
| 123456 | 01/02/2026 | Empresa XYZ | R$ 1.500,00 | Aberto |
(continue com os dados REAIS acima)

Os maiores valores sao de Fornecedor A (R$ X) e Fornecedor B (R$ Y).

Responda APENAS com o relatorio formatado:"""

# ============================================================
# AGENTE
# ============================================================

def strip_thinking(text: str) -> str:
    """Remove tags <think>...</think> do Qwen3 antes de processar."""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


def fix_pendencia_sql(sql: str) -> str:
    """Corrige erros comuns do Qwen3 com STATUSNOTA e TIPMOV.

    O Qwen3 frequentemente gera:
        STATUSNOTA = 'P'  (errado para pendencia)
        TIPMOV IN ('C', 'O')  (errado para pedidos de compra)
    Em vez de:
        PENDENTE = 'S'  (campo correto para pendencia)
        TIPMOV = 'O'  (pedido de compra especificamente)
    """
    original = sql
    upper_sql = sql.upper()

    # Fix 1: STATUSNOTA = 'P' → PENDENTE = 'S' AND STATUSNOTA <> 'C'
    # Somente quando PENDENTE nao aparece ja no SQL
    if "PENDENTE" not in upper_sql:
        sql = re.sub(
            r"(\w+\.)?STATUSNOTA\s*=\s*'P'",
            lambda m: f"{m.group(1) or ''}PENDENTE = 'S' AND {m.group(1) or ''}STATUSNOTA <> 'C'",
            sql, flags=re.IGNORECASE
        )

    # Fix 2: TIPMOV IN ('C', 'O') → TIPMOV = 'O' (quando eh sobre pendencia/pedidos)
    # Recalcular upper_sql apos Fix 1 (agora pode conter PENDENTE)
    upper_sql_now = sql.upper()
    has_pendencia = any(kw in upper_sql_now for kw in ['PENDENTE', 'DTPREVENT', 'TGFVAR', 'QTDATENDIDA'])
    if has_pendencia:
        sql = re.sub(
            r"(\w+\.)?TIPMOV\s+IN\s*\(\s*'C'\s*,\s*'O'\s*\)",
            lambda m: f"{m.group(1) or ''}TIPMOV = 'O'",
            sql, flags=re.IGNORECASE
        )

    if sql != original:
        print(f"[i] SQL corrigido automaticamente (PENDENTE/TIPMOV)")
    return sql


def fix_rownum_syntax(sql: str) -> str:
    """Corrige 'ORDER BY ... WHERE ROWNUM' para subquery correta.

    O Qwen3 frequentemente gera:
        SELECT ... ORDER BY x DESC WHERE ROWNUM <= 10
    Em vez de:
        SELECT * FROM (SELECT ... ORDER BY x DESC) WHERE ROWNUM <= 10
    """
    # Detectar padrao: ORDER BY ... WHERE ROWNUM <= N (sem subquery)
    match = re.search(
        r'(ORDER\s+BY\s+[^\n]+?)\s+(WHERE\s+ROWNUM\s*<=\s*\d+)',
        sql, flags=re.IGNORECASE
    )
    if match and 'SELECT * FROM (' not in sql.upper():
        order_clause = match.group(1)
        rownum_clause = match.group(2)
        # Remover o "WHERE ROWNUM" mal posicionado
        inner_sql = sql[:match.start(2)].strip()
        # Envolver em subquery
        sql = f"SELECT * FROM ({inner_sql}) {rownum_clause}"
        print(f"[i] ROWNUM corrigido automaticamente")
    return sql


class DataHubAgent:
    """
    Agente LLM que decide entre responder com documentacao ou consultar o banco.

    Fluxo:
    1. Recebe pergunta do usuario
    2. Classifica: documentacao ou consulta_banco
    3. Se documentacao: retorna resposta direto
    4. Se consulta_banco: executa query e formata resultado
    """

    # Arquivos obrigatorios para contexto SQL (relativos a PROJECT_ROOT/knowledge)
    SQL_CONTEXT_FILES = [
        "sankhya/relacionamentos.md",
        "sankhya/exemplos_sql.md",
        "sankhya/erros_sql.md",
        "glossario/sinonimos.md",
    ]

    def __init__(self):
        self.kb = KnowledgeBase()
        self.llm = None
        self.query_executor = SafeQueryExecutor()
        self.history = []
        self.initialized = False
        self.relacionamentos = ""
        self.sql_context = ""

    def initialize(self):
        """Inicializa base de conhecimento e LLM."""
        if self.initialized:
            return

        self.kb.load()
        self.llm = LLMClient()

        # Referencia SQL condensada (modelo 8B precisa de contexto curto)
        self.relacionamentos = self._build_sql_reference()
        print(f"[OK] Referencia SQL carregada ({len(self.relacionamentos)} chars)")

        # Carregar contexto SQL obrigatorio dos 4 arquivos
        self.sql_context = self._load_sql_context()
        print(f"[OK] Contexto SQL obrigatorio carregado ({len(self.sql_context)} chars)")

        self.initialized = True
        print(f"[OK] Agente inicializado")
        print(f"[i] {len(self.kb.documents)} documentos carregados")
        print(f"[i] Modelo: {LLM_PROVIDER}/{LLM_MODEL}")

    async def ask(self, question: str) -> dict:
        """
        Processa uma pergunta e retorna resposta.

        IMPORTANTE: Sempre usa modo RAG para evitar erro 413 Payload Too Large.
        Nunca envia a base completa - apenas os 5 documentos mais relevantes.

        Args:
            question: Pergunta do usuario

        Returns:
            dict com:
                - response: Resposta formatada
                - tipo: "documentacao" ou "consulta_banco"
                - query_executed: SQL executada (se houver)
                - query_results: Numero de registros retornados (se houver)
                - error: Mensagem de erro (se houver)
        """
        if not self.initialized:
            self.initialize()

        t0 = time.time()

        # SEMPRE usar RAG - buscar apenas os 5 documentos mais relevantes
        # Isso evita erro 413 Payload Too Large da API Groq
        results = self.kb.search(question, top_k=5)
        if results:
            context_parts = []
            total_chars = 0
            max_total = 15000  # Limite total de contexto
            max_per_doc = 3000  # Limite por documento

            for r in results:
                content = r['content'][:max_per_doc] if len(r['content']) > max_per_doc else r['content']
                doc_text = f"## {r['filename']} ({r['category']})\n{content}"

                # Verificar se ainda cabe no limite total
                if total_chars + len(doc_text) > max_total:
                    break

                context_parts.append(doc_text)
                total_chars += len(doc_text)

            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "Nenhum documento relevante encontrado."

        # ETAPA 1: Classificacao
        classification = await self._classify(question, context)

        if classification.get("error"):
            return {
                "response": f"Erro na classificacao: {classification['error']}",
                "tipo": "erro",
                "query_executed": None,
                "query_results": None,
            }

        tipo = classification.get("tipo", "documentacao")

        # Se e documentacao, retorna direto
        if tipo == "documentacao":
            response = classification.get("resposta", "Nao consegui gerar uma resposta.")
            elapsed = round(time.time() - t0, 1)
            print(f"[i] Tempo total: {elapsed}s")
            return {
                "response": response,
                "tipo": "documentacao",
                "query_executed": None,
                "query_results": None,
                "elapsed": elapsed,
            }

        # ETAPA 2: Execucao de query
        sql = classification.get("sql")
        if not sql:
            return {
                "response": "Erro: LLM indicou consulta ao banco mas nao gerou SQL.",
                "tipo": "erro",
                "query_executed": None,
                "query_results": None,
            }

        # Executar query (com auto-correcao em caso de erro Oracle)
        try:
            result = await self.query_executor.execute(sql)
        except QuerySecurityError as e:
            return {
                "response": f"Query bloqueada por seguranca: {str(e)}",
                "tipo": "erro",
                "query_executed": sql,
                "query_results": None,
            }

        if not result.get("success"):
            error_msg = result.get("error", "Erro desconhecido")

            # Auto-correcao: se erro Oracle, tenta corrigir com LLM
            if "ORA-" in error_msg:
                print(f"[!] Erro Oracle detectado, tentando corrigir SQL...")
                fixed_sql = await self._fix_sql(sql, error_msg)

                if fixed_sql and fixed_sql != sql:
                    print(f"[i] SQL corrigido: {fixed_sql[:100]}...")
                    try:
                        result = await self.query_executor.execute(fixed_sql)
                        if result.get("success"):
                            sql = fixed_sql
                            print(f"[OK] Query corrigida executou com sucesso!")
                        else:
                            return {
                                "response": "Nao consegui gerar a consulta correta. Tente reformular a pergunta com mais detalhes.",
                                "tipo": "erro",
                                "query_executed": fixed_sql,
                                "query_results": None,
                            }
                    except QuerySecurityError:
                        return {
                            "response": "Nao consegui gerar a consulta correta. Tente reformular a pergunta com mais detalhes.",
                            "tipo": "erro",
                            "query_executed": fixed_sql,
                            "query_results": None,
                        }
                else:
                    return {
                        "response": "Nao consegui gerar a consulta correta. Tente reformular a pergunta com mais detalhes.",
                        "tipo": "erro",
                        "query_executed": sql,
                        "query_results": None,
                    }
            else:
                return {
                    "response": f"Erro ao executar query: {error_msg}",
                    "tipo": "erro",
                    "query_executed": result.get("query_executed", sql),
                    "query_results": None,
                }

        # Formatar resultados
        formatted_response = await self._format_results(
            question=question,
            sql=result.get("query_executed", sql),
            data=result.get("data", []),
            columns=result.get("columns", []),
        )

        elapsed = round(time.time() - t0, 1)
        print(f"[i] Tempo total: {elapsed}s")
        return {
            "response": formatted_response,
            "tipo": "consulta_banco",
            "query_executed": result.get("query_executed", sql),
            "query_results": result.get("row_count", 0),
            "elapsed": elapsed,
        }

    async def _classify(self, question: str, context: str, retry_with_smaller: bool = True) -> dict:
        """
        Classifica a pergunta em 3 etapas simples:
        1. BANCO ou DOC? (uma palavra)
        2. Se BANCO: gera SQL
        3. Se DOC: responde da documentacao

        Args:
            question: Pergunta do usuario
            context: Contexto da base de conhecimento
            retry_with_smaller: Se True, tenta com contexto menor em caso de erro

        Returns:
            dict com tipo, resposta e sql
        """
        try:
            # ========================================
            # ETAPA 1: CLASSIFICAR (BANCO ou DOC)
            # ========================================
            print(f"[1/3] Classificando pergunta...")
            classifier_prompt = CLASSIFIER_PROMPT.format(pergunta=question)

            classification = strip_thinking(self.llm.chat(
                [{"role": "user", "content": classifier_prompt}],
                temperature=0,
                timeout=120
            )).upper()

            print(f"[i] Classificacao: {classification}")

            # Se nao for claramente DOC, assume BANCO
            if "DOC" not in classification:
                tipo = "consulta_banco"
            else:
                tipo = "documentacao"

            # ========================================
            # ETAPA 2: SE BANCO, GERAR SQL
            # ========================================
            if tipo == "consulta_banco":
                print(f"[2/3] Gerando SQL...")
                sql_prompt = SQL_GENERATOR_PROMPT.format(
                    pergunta=question,
                    relacionamentos=self.relacionamentos
                )

                sql = strip_thinking(self.llm.chat(
                    [
                        {"role": "system", "content": self.sql_context},
                        {"role": "user", "content": sql_prompt},
                    ],
                    temperature=0,
                    timeout=120
                ))

                # Limpar SQL (remover markdown, espacos extras, ponto-e-virgula)
                sql = sql.replace("```sql", "").replace("```", "").strip()
                sql = sql.rstrip(";").strip()

                # Remover FETCH FIRST (Oracle antigo nao suporta, usar ROWNUM)
                sql = re.sub(r'\bFETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY\b', '', sql, flags=re.IGNORECASE).strip()

                # Corrigir ROWNUM mal posicionado (ORDER BY ... WHERE ROWNUM)
                sql = fix_rownum_syntax(sql)

                # Corrigir STATUSNOTA='P' e TIPMOV IN ('C','O') automaticamente
                sql = fix_pendencia_sql(sql)

                # Garantir que comeca com SELECT (prompt termina com "SELECT")
                if not sql.upper().startswith("SELECT"):
                    sql = "SELECT " + sql

                print(f"[i] SQL gerado: {sql[:100]}...")

                # Salvar no historico
                self.history.append({"role": "user", "content": question})

                return {
                    "tipo": "consulta_banco",
                    "resposta": None,
                    "sql": sql,
                }

            # ========================================
            # ETAPA 3: SE DOC, RESPONDER
            # ========================================
            print(f"[2/3] Respondendo da documentacao...")
            doc_prompt = DOC_ANSWER_PROMPT.format(
                context=context[:10000],  # Limitar contexto
                pergunta=question
            )

            resposta = strip_thinking(self.llm.chat(
                [{"role": "user", "content": doc_prompt}],
                temperature=0.3,
                timeout=120
            ))

            # Salvar no historico
            self.history.append({"role": "user", "content": question})
            self.history.append({"role": "assistant", "content": resposta})

            return {
                "tipo": "documentacao",
                "resposta": resposta,
                "sql": None,
            }

        except Exception as e:
            error_str = str(e)
            print(f"[ERRO] Classificacao falhou: {error_str}")
            return {"error": error_str}

    def _build_sql_reference(self) -> str:
        """Referencia SQL condensada para o modelo 8B."""
        return """TABELAS E COLUNAS:
- TGFCAB (C): NUNOTA, NUMNOTA, DTNEG, VLRNOTA, STATUSNOTA, TIPMOV, CODPARC, CODTIPOPER, CODEMP, CODVEND, DTPREVENT, PENDENTE
- TGFITE (I): NUNOTA, SEQUENCIA, CODPROD, QTDNEG, VLRUNIT, VLRTOT
- TGFPAR (P): CODPARC, NOMEPARC, RAZAOSOCIAL, CGC_CPF
- TGFPRO (PR): CODPROD, DESCRPROD, CODMARCA, REFFORN
- TGFMAR (M): CODIGO, DESCRICAO, AD_CODVEND
- TGFTOP (T): CODTIPOPER, DESCROPER
- TGFVEN (V): CODVEND, APELIDO
- TSIEMP (E): CODEMP, NOMEFANTASIA
- TGFEST (ES): CODPROD, CODEMP, ESTOQUE, RESERVADO
- TGFFIN (F): NUFIN, NUNOTA, CODPARC, VLRDESDOB, DTVENC, RECDESP, CODEMP
- TGFVAR (VAR): NUNOTAORIG, SEQUENCIAORIG, NUNOTA, SEQUENCIA, QTDATENDIDA

JOINS OBRIGATORIOS:
- Parceiro: TGFCAB C JOIN TGFPAR P ON C.CODPARC = P.CODPARC
- Vendedor: TGFCAB C JOIN TGFVEN V ON C.CODVEND = V.CODVEND
- Empresa: TGFCAB C JOIN TSIEMP E ON C.CODEMP = E.CODEMP
- Itens: TGFCAB C JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
- Produto: TGFITE I JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
- Marca: TGFPRO PR JOIN TGFMAR M ON PR.CODMARCA = M.CODIGO
- TOP: TGFCAB C JOIN TGFTOP T ON C.CODTIPOPER = T.CODTIPOPER
- Financeiro: TGFCAB C JOIN TGFFIN F ON C.NUNOTA = F.NUNOTA

REGRA DE NIVEL (CRITICA - LER ANTES DE GERAR):
- Se pergunta menciona MARCA ou PRODUTO: query nivel ITEM. FROM TGFITE ITE JOIN TGFCAB CAB ON CAB.NUNOTA=ITE.NUNOTA JOIN TGFPRO PRO ON PRO.CODPROD=ITE.CODPROD LEFT JOIN TGFMAR MAR ON MAR.CODIGO=PRO.CODMARCA LEFT JOIN TGFVAR.
- Se pergunta geral (sem marca/produto): query nivel CABECALHO. FROM TGFCAB C.
- NUNCA usar VLRNOTA quando filtrando por marca! VLRNOTA = valor do pedido INTEIRO (todas as marcas). Valor por marca = ITE.VLRTOT.
- Pendencia real por marca = TGFVAR (QTD_PEDIDA - QTD_ATENDIDA > 0).

PRODUTO/MARCA: NUNCA C JOIN PR direto! Caminho: ITE JOIN PRO ON CODPROD, PRO JOIN MAR ON CODMARCA = CODIGO.
MARCA: SEMPRE usar UPPER(MAR.DESCRICAO) = UPPER('nome'). NUNCA usar TGFPRO.MARCA.
COMPARACAO DE TEXTO: SEMPRE usar UPPER() ao comparar nomes. Dados cadastrados em MAIUSCULO.
ESTOQUE: I JOIN ES ON I.CODPROD = ES.CODPROD AND C.CODEMP = ES.CODEMP

PREVISAO DE ENTREGA: TGFCAB.DTPREVENT (pode ser NULL). MOSTRAR com NVL(TO_CHAR(DTPREVENT,'DD/MM/YYYY'),'Sem previsao'). NAO filtrar IS NOT NULL.
STATUS EM RELATORIOS: STATUSNOTA <> 'C' para excluir cancelados.
PENDENCIA: "pedidos pendentes" = PENDENTE='S'. NUNCA usar STATUSNOTA='P' para pendencia. PENDENTE eh o campo que indica se falta receber itens.
TIPMOV COMPRA: "pedidos de compra" = TIPMOV='O'. "notas de compra" = TIPMOV='C'. "tudo de compra" = IN('C','O').
PEDIDOS ATRASADOS: DTPREVENT < TRUNC(SYSDATE) AND PENDENTE = 'S'

QTD PENDENTE DE ENTREGA: TGFITE.QTDNEG - SUM(TGFVAR.QTDATENDIDA). LEFT JOIN obrigatorio. Filtrar TGFVAR apenas notas nao canceladas.

NUNCA juntar TGFFIN com TGFITE na mesma query! Multiplica valores (N parcelas x M itens).
- Quer VALOR FINANCEIRO (deve, vencido, pago) -> TGFFIN SEM TGFITE
- Quer DADOS PRODUTO (marca, descricao) -> TGFITE SEM TGFFIN
- Quer VALOR DA NOTA -> TGFCAB.VLRNOTA

TIPMOV: V=Venda, C=NotaCompra(entrada), O=PedidoCompra(ordem), P=PedidoVenda, J=SolicitacaoCompra, D=Devolucao
STATUSNOTA: P=Pendente, L=Liberado, A=Atendimento, C=Cancelado
PENDENTE: S=Sim(falta receber itens), N=Nao(completo). Usar para filtrar pendencia!
RECDESP: 1=Receber, -1=Pagar

REGRA DE PENDENCIA:
- "pendencia" sem especificar = COMPRA: PENDENTE='S', TIPMOV='O', STATUSNOTA<>'C'. Valor=VLRNOTA. SEM TGFFIN!
- "pendencia financeira/contas a pagar" = TGFFIN: DHBAIXA IS NULL, RECDESP=-1. SEM TGFITE!
- "pendencia de venda" = PENDENTE='S', TIPMOV='P', STATUSNOTA<>'C'. SEM TGFFIN!
- NUNCA usar STATUSNOTA='P' para pendencia. PENDENTE eh o campo correto."""

    def _load_sql_context(self) -> str:
        """Carrega os 4 arquivos obrigatorios de contexto SQL."""
        knowledge_dir = PROJECT_ROOT / "knowledge"
        parts = []
        for rel_path in self.SQL_CONTEXT_FILES:
            filepath = knowledge_dir / rel_path
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8")
                    parts.append(content)
                except Exception as e:
                    print(f"[!] Erro ao ler {rel_path}: {e}")
            else:
                print(f"[!] Arquivo nao encontrado: {rel_path}")
        return "\n\n---\n\n".join(parts)

    async def _fix_sql(self, sql: str, error: str) -> Optional[str]:
        """
        Tenta corrigir SQL com erro Oracle usando a LLM.

        Args:
            sql: Query que deu erro
            error: Mensagem de erro Oracle

        Returns:
            SQL corrigido ou None se falhar
        """
        try:
            prompt = SQL_FIX_PROMPT.format(
                sql=sql,
                erro=error,
                relacionamentos=self.relacionamentos
            )
            fixed = strip_thinking(self.llm.chat(
                [
                    {"role": "system", "content": self.sql_context},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                timeout=120
            ))

            # Limpar SQL
            fixed = fixed.replace("```sql", "").replace("```", "").strip()
            fixed = fixed.rstrip(";").strip()

            # Remover FETCH FIRST (Oracle antigo nao suporta, usar ROWNUM)
            fixed = re.sub(r'\bFETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY\b', '', fixed, flags=re.IGNORECASE).strip()

            # Corrigir ROWNUM mal posicionado (ORDER BY ... WHERE ROWNUM)
            fixed = fix_rownum_syntax(fixed)

            # Garantir que comeca com SELECT (prompt termina com "SELECT")
            if not fixed.upper().startswith("SELECT"):
                fixed = "SELECT " + fixed

            return fixed
        except Exception as e:
            print(f"[!] Erro ao corrigir SQL: {e}")
            return None

    async def _format_results(self, question: str, sql: str, data: list, columns: list) -> str:
        """
        Formata os resultados da query como relatorio para usuario de negocios.

        IMPORTANTE: Envia os dados em formato estruturado (tabela Markdown) para que
        a LLM use SOMENTE os dados reais e NAO invente valores.
        """
        if not data:
            return "Nao encontrei resultados para essa consulta. Verifique se os filtros estao corretos ou se existem dados para o periodo solicitado."

        # Limitar a 50 linhas para o LLM (evitar payload muito grande)
        sample_data = data[:50]
        has_more = len(data) > 50

        # Formatar como tabela Markdown bem estruturada
        # Isso facilita a LLM entender que sao dados REAIS
        lines = []

        # Cabecalho da tabela
        if columns:
            header = "| " + " | ".join(str(c) for c in columns) + " |"
            separator = "|" + "|".join(["---" for _ in columns]) + "|"
            lines.append(header)
            lines.append(separator)

        # Linhas de dados
        for row in sample_data:
            if isinstance(row, dict):
                values = []
                for c in columns:
                    val = row.get(c, "")
                    # Converter None para string vazia
                    if val is None:
                        val = ""
                    values.append(str(val))
            else:
                values = [str(v) if v is not None else "" for v in row]
            lines.append("| " + " | ".join(values) + " |")

        resultados_texto = "\n".join(lines)

        # Adicionar nota se houver mais dados
        if has_more:
            resultados_texto += f"\n\n(Mostrando 50 de {len(data)} registros)"

        # Chamar LLM para formatar com temperature=0 para ser mais deterministico
        prompt = FORMATTER_PROMPT.format(
            pergunta=question,
            total_rows=len(data),
            resultados=resultados_texto,
        )

        messages = [
            {
                "role": "system",
                "content": "Voce e um assistente de negocios. Sua UNICA tarefa e formatar os dados fornecidos como um relatorio claro. NUNCA invente dados. Use SOMENTE os dados da tabela fornecida."
            },
            {"role": "user", "content": prompt},
        ]

        try:
            print(f"[3/3] Formatando resultado...")
            # Temperature=0 para respostas mais deterministicas (menos criatividade)
            response = strip_thinking(self.llm.chat(messages, temperature=0, timeout=120))
            # Salvar no historico
            self.history.append({"role": "assistant", "content": response})
            return response
        except Exception as e:
            print(f"[!] Erro ao formatar: {e}")
            # Fallback: retornar tabela markdown simples (dados reais, sem LLM)
            fallback_response = f"Encontrei {len(data)} registro(s).\n\n{resultados_texto}"
            return fallback_response

    def clear_history(self):
        """Limpa o historico de conversas."""
        self.history.clear()


# ============================================================
# FUNCOES AUXILIARES
# ============================================================

async def ask_agent(question: str) -> dict:
    """
    Funcao auxiliar para perguntar ao agente.

    Args:
        question: Pergunta do usuario

    Returns:
        Resultado do agente
    """
    agent = DataHubAgent()
    return await agent.ask(question)


# ============================================================
# TESTES
# ============================================================

async def _run_tests():
    """Testes do agente."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.markdown import Markdown

    console = Console()
    console.print(Panel("[bold]DataHubAgent - Testes[/]", border_style="cyan"))

    agent = DataHubAgent()
    agent.initialize()

    # Teste 1: Pergunta de documentacao
    console.print("\n[bold]Teste 1: Pergunta de documentacao[/]")
    console.print("[dim]Pergunta: Como funciona o fluxo de compras?[/]")

    result = await agent.ask("Como funciona o fluxo de compras?")
    console.print(f"[cyan]Tipo:[/] {result['tipo']}")
    console.print(f"[cyan]Query:[/] {result['query_executed']}")
    if result['response']:
        console.print("[cyan]Resposta:[/]")
        try:
            console.print(Markdown(result['response'][:500] + "..."))
        except:
            console.print(result['response'][:500] + "...")

    # Teste 2: Pergunta que precisa de query (simulado)
    console.print("\n[bold]Teste 2: Pergunta que precisa de query[/]")
    console.print("[dim]Pergunta: Quantas notas temos este mes?[/]")

    result = await agent.ask("Quantas notas temos este mes?")
    console.print(f"[cyan]Tipo:[/] {result['tipo']}")
    console.print(f"[cyan]Query:[/] {result['query_executed']}")
    console.print(f"[cyan]Resultados:[/] {result['query_results']}")
    if result['response']:
        console.print("[cyan]Resposta:[/]")
        try:
            console.print(Markdown(result['response'][:500] + "..."))
        except:
            console.print(result['response'][:500] + "...")

    console.print("\n[bold green]Testes concluidos![/]")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_run_tests())
