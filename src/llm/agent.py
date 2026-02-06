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
# SYSTEM PROMPT DO AGENTE
# ============================================================

AGENT_SYSTEM_PROMPT = """Voce e o assistente de dados da MMarra Distribuidora Automotiva, uma distribuidora de autopecas para veiculos pesados (caminhoes, onibus) com sede em Ribeirao Preto/SP e 9 filiais pelo Brasil.

## Seu papel
- Responder perguntas sobre o negocio, processos, dados e sistema Sankhya ERP
- Explicar fluxos de compra, venda, estoque, financeiro, WMS
- Ajudar a entender tabelas, campos e relacionamentos do banco de dados
- Consultar o banco de dados em tempo real quando necessario
- Explicar regras de negocio especificas da MMarra

## Contexto tecnico
- ERP: Sankhya (banco Oracle)
- Tabelas principais: TGFCAB (notas), TGFITE (itens), TGFPAR (parceiros), TGFPRO (produtos), TGFTOP (operacoes), TSIEMP (empresas), TGFVEN (vendedores), TGFEST (estoque), TGFFIN (financeiro)
- Tabelas customizadas: Prefixo AD_* (MMarra personalizou bastante)

## Numeros chave
- 10 empresas (Ribeirao Preto e a maior: R$ 343M)
- 394k produtos (Cummins 44k, MWM 15k, ZF 14k SKUs)
- 57k parceiros
- 343k notas
- 1.1M itens
- 20 compradores, 86 vendedores

## Regras importantes da MMarra
- NAO usa workflow de aprovacao padrao (TGFLIB vazia)
- Solicitacao de compra usa TGFCAB com TIPMOV='J' (nao TGFSOL)
- Cotacao usa TGFCOT, apenas preco importa (PESOPRECO=1)
- Custos em tabela customizada AD_TGFCUSMMA (709k registros, 5 anos)
- Codigos auxiliares em AD_TGFPROAUXMMA (1.1M registros, 18 por produto)

## Capacidade de consulta ao banco

Voce pode consultar o banco de dados Sankhya (Oracle) em tempo real.

Quando o usuario pedir dados especificos (relatorios, listagens, totais, pendencias, rankings),
voce DEVE gerar uma query SQL para consultar o banco.

Regras para gerar SQL:
- SOMENTE SELECT (nunca INSERT, UPDATE, DELETE)
- Sempre usar sintaxe Oracle (ROWNUM, SYSDATE, NVL, TO_CHAR, TO_DATE)
- Sempre limitar resultados (ROWNUM <= 100 para listagens)
- Usar as tabelas documentadas na base de conhecimento
- Incluir JOINs necessarios para trazer descricoes (ex: NOMEPARC, DESCRPROD)
- Usar TO_CHAR para formatar datas: TO_CHAR(campo, 'DD/MM/YYYY')
- Usar TO_CHAR para formatar valores: TO_CHAR(campo, 'FM999G999G999D00')
- Para mes atual: TRUNC(SYSDATE, 'MM') ate SYSDATE
- Para ano atual: TRUNC(SYSDATE, 'YYYY') ate SYSDATE

## Tipos de Movimentacao (TIPMOV em TGFCAB)
- 'V' = Venda
- 'C' = Compra/Recebimento
- 'D' = Devolucao
- 'O' = Pedido de Compra
- 'P' = Pedido de Venda
- 'J' = Solicitacao de Compra
- 'T' = Transferencia

## Como responder

SEMPRE responda em formato JSON valido:

Para perguntas que podem ser respondidas com a documentacao:
{"tipo": "documentacao", "resposta": "texto da resposta completa", "sql": null}

Para perguntas que precisam de dados do banco:
{"tipo": "consulta_banco", "resposta": null, "sql": "SELECT ..."}

Exemplos:
- "Como funciona o fluxo de compras?" -> {"tipo": "documentacao", "resposta": "O fluxo de compras...", "sql": null}
- "Quantas notas temos este mes?" -> {"tipo": "consulta_banco", "resposta": null, "sql": "SELECT COUNT(*) AS TOTAL FROM TGFCAB WHERE DTNEG >= TRUNC(SYSDATE, 'MM')"}
- "Quais os 10 maiores clientes?" -> {"tipo": "consulta_banco", "resposta": null, "sql": "SELECT * FROM (SELECT P.CODPARC, P.NOMEPARC, SUM(C.VLRNOTA) AS TOTAL FROM TGFCAB C JOIN TGFPAR P ON C.CODPARC = P.CODPARC WHERE C.TIPMOV = 'V' GROUP BY P.CODPARC, P.NOMEPARC ORDER BY TOTAL DESC) WHERE ROWNUM <= 10"}

## Instrucoes finais
- Responda em portugues brasileiro
- Use os documentos fornecidos como fonte principal
- Se nao souber e nao conseguir consultar, diga que precisa investigar
- Seja direto e pratico
- SEMPRE retorne JSON valido
"""

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
        Classifica a pergunta: documentacao ou consulta_banco.

        Args:
            question: Pergunta do usuario
            context: Contexto da base de conhecimento
            retry_with_smaller: Se True, tenta com contexto menor em caso de erro 413

        Returns:
            dict com tipo, resposta e sql
        """
        messages = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT},
            {"role": "system", "content": f"## Documentacao disponivel\n\n{context}"},
        ]

        # Adicionar historico (ultimas 4 trocas)
        for msg in self.history[-8:]:
            messages.append(msg)

        messages.append({"role": "user", "content": question})

        try:
            response = self.llm.chat(messages, temperature=0.1)

            # Tentar extrair JSON da resposta
            json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    # Salvar no historico
                    self.history.append({"role": "user", "content": question})
                    if result.get("tipo") == "documentacao":
                        self.history.append({"role": "assistant", "content": result.get("resposta", "")})
                    return result
                except json.JSONDecodeError:
                    pass

            # Se nao conseguiu extrair JSON, tenta interpretar como documentacao
            return {
                "tipo": "documentacao",
                "resposta": response,
                "sql": None,
            }

        except Exception as e:
            error_str = str(e)
            # Se erro 413 (payload muito grande), tentar com contexto menor
            if "413" in error_str and retry_with_smaller:
                print("[!] Payload muito grande, tentando com contexto reduzido...")
                # Truncar contexto para ~15k caracteres
                truncated_context = context[:15000] + "\n\n[... contexto truncado ...]"
                return await self._classify(question, truncated_context, retry_with_smaller=False)
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
            # Temperature=0 para respostas mais deterministicas (menos criatividade)
            response = self.llm.chat(messages, temperature=0)
            # Salvar no historico
            self.history.append({"role": "assistant", "content": response})
            return response
        except Exception as e:
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
