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

Tipos de perguntas:
- BANCO: usuario quer dados reais, numeros, listas, relatorios, pendencias, totais, quantidades, valores, ranking
  Exemplos: "quantas notas", "quais pedidos pendentes", "maiores clientes", "vendas do mes"

- DOC: usuario quer explicacao de processos, como funciona algo, o que significa algo
  Exemplos: "como funciona", "o que significa", "explique o fluxo", "o que eh"

Pergunta: {pergunta}

IMPORTANTE: Se tiver qualquer duvida, responda BANCO (eh melhor tentar executar).

Resposta (apenas BANCO ou DOC):"""

SQL_GENERATOR_PROMPT = """Gere APENAS a query SQL Oracle para responder a pergunta. Sem explicacao, sem markdown, apenas o SELECT.

TABELAS DISPONIVEIS:
- TGFCAB: Cabecalho de notas (NUNOTA, TIPMOV, DTNEG, VLRNOTA, STATUSNOTA, CODPARC, CODEMP)
- TGFITE: Itens das notas (NUNOTA, SEQUENCIA, CODPROD, QTDNEG, VLRUNIT, VLRTOT)
- TGFPAR: Parceiros/Clientes/Fornecedores (CODPARC, NOMEPARC, RAZAOSOCIAL, CGCCPF)
- TGFPRO: Produtos (CODPROD, DESCRPROD, MARCA, CODVOL, ESTOQUE)
- TGFTOP: Tipos de Operacao (CODTIPOPER, DESCRTIPOPER, ATUALEST, ATUALFIN)
- TGFVEN: Vendedores/Compradores (CODVEND, APELIDO, TIPVEND)
- TGFEST: Estoque (CODEMP, CODLOCAL, CODPROD, ESTOQUE, RESERVADO)
- TGFFIN: Financeiro (NUFIN, NUNOTA, RECDESP, VLRDESDOB, DTVENC, DHBAIXA)

TIPOS DE MOVIMENTACAO (TIPMOV):
- 'V' = Venda
- 'C' = Compra/Recebimento
- 'O' = Pedido de Compra
- 'P' = Pedido de Venda
- 'J' = Solicitacao de Compra
- 'D' = Devolucao
- 'T' = Transferencia

STATUS (STATUSNOTA):
- 'A' = Aberto
- 'L' = Liberado
- 'P' = Pendente

REGRAS OBRIGATORIAS:
1. SEMPRE usar ROWNUM <= 100 para limitar resultados
2. Para datas usar TRUNC(SYSDATE, 'MM') para mes atual
3. JOINs: sempre usar alias curtos (C, P, I, V)
4. Para nomes: JOIN com TGFPAR P ON C.CODPARC = P.CODPARC para trazer NOMEPARC
5. Ordenar por valor DESC quando tiver agregacao

Pergunta: {pergunta}

SQL:"""

DOC_ANSWER_PROMPT = """Responda a pergunta usando APENAS a documentacao fornecida abaixo.

Documentacao:
{context}

Pergunta: {pergunta}

Resposta (direta, clara, em portugues):"""

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
   - STATUSNOTA -> Status (A=Aberto, L=Liberado, P=Pendente)
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

class DataHubAgent:
    """
    Agente LLM que decide entre responder com documentacao ou consultar o banco.

    Fluxo:
    1. Recebe pergunta do usuario
    2. Classifica: documentacao ou consulta_banco
    3. Se documentacao: retorna resposta direto
    4. Se consulta_banco: executa query e formata resultado
    """

    def __init__(self):
        self.kb = KnowledgeBase()
        self.llm = None
        self.query_executor = SafeQueryExecutor()
        self.history = []
        self.initialized = False

    def initialize(self):
        """Inicializa base de conhecimento e LLM."""
        if self.initialized:
            return

        self.kb.load()
        self.llm = LLMClient()
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
            return {
                "response": response,
                "tipo": "documentacao",
                "query_executed": None,
                "query_results": None,
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

        # Executar query
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

        return {
            "response": formatted_response,
            "tipo": "consulta_banco",
            "query_executed": result.get("query_executed", sql),
            "query_results": result.get("row_count", 0),
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

            classification = self.llm.chat(
                [{"role": "user", "content": classifier_prompt}],
                temperature=0,
                timeout=120
            ).strip().upper()

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
                sql_prompt = SQL_GENERATOR_PROMPT.format(pergunta=question)

                sql = self.llm.chat(
                    [{"role": "user", "content": sql_prompt}],
                    temperature=0,
                    timeout=120
                ).strip()

                # Limpar SQL (remover markdown, espacos extras)
                sql = sql.replace("```sql", "").replace("```", "").strip()

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

            resposta = self.llm.chat(
                [{"role": "user", "content": doc_prompt}],
                temperature=0.3,
                timeout=120
            ).strip()

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
            response = self.llm.chat(messages, temperature=0, timeout=120)
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
