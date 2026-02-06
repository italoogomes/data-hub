"""
MMarra Data Hub - Query Executor Seguro
Executa queries SQL no Sankhya com validacoes de seguranca.

Uso:
    from src.llm.query_executor import SafeQueryExecutor

    executor = SafeQueryExecutor()
    result = await executor.execute("SELECT * FROM TGFPAR WHERE ROWNUM <= 10")
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

import httpx
from dotenv import load_dotenv

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ============================================================
# CONFIGURACAO
# ============================================================

SANKHYA_BASE_URL = "https://api.sankhya.com.br"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_X_TOKEN")

# Limites de seguranca
MAX_ROWS = 500
QUERY_TIMEOUT = 30  # segundos

# ============================================================
# EXCECOES
# ============================================================

class QuerySecurityError(Exception):
    """Erro de seguranca na query."""
    pass

class QueryExecutionError(Exception):
    """Erro na execucao da query."""
    pass

class AuthenticationError(Exception):
    """Erro de autenticacao na API Sankhya."""
    pass

# ============================================================
# SAFE QUERY EXECUTOR
# ============================================================

class SafeQueryExecutor:
    """
    Executor seguro de queries SQL no Sankhya.

    Protecoes:
    - Somente SELECT permitido
    - Bloqueio de comandos perigosos (INSERT, UPDATE, DELETE, DROP, etc)
    - Bloqueio de comentarios SQL (--, /* */)
    - Bloqueio de multiplas statements (;)
    - Limite automatico de linhas (ROWNUM <= 500)
    - Timeout de 30 segundos
    - Whitelist opcional de tabelas
    """

    # Palavras-chave PROIBIDAS (case insensitive)
    FORBIDDEN_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE",
        "GRANT", "REVOKE", "EXEC", "EXECUTE", "MERGE", "CALL", "BEGIN", "END",
        "DECLARE", "COMMIT", "ROLLBACK", "SAVEPOINT", "INTO OUTFILE",
        "INTO DUMPFILE", "LOAD_FILE", "UTL_FILE", "DBMS_", "XP_", "SP_"
    ]

    def __init__(self, whitelist: Optional[list] = None):
        """
        Inicializa o executor.

        Args:
            whitelist: Lista opcional de tabelas permitidas (ex: ["TGFPAR", "TGFCAB"])
                      Se None, permite qualquer tabela (somente SELECT)
        """
        self.whitelist = [t.upper() for t in whitelist] if whitelist else None
        self.access_token = None
        self.token_expires = None

    # ============================================================
    # VALIDACAO
    # ============================================================

    def validate_query(self, query: str) -> tuple[bool, str]:
        """
        Valida se a query e segura para execucao.

        Args:
            query: SQL a ser validado

        Returns:
            tuple: (is_valid, error_message)
        """
        if not query or not query.strip():
            return False, "Query vazia"

        # Normalizar para analise
        normalized = query.upper().strip()

        # 1. Deve comecar com SELECT
        if not normalized.startswith("SELECT"):
            return False, "Apenas queries SELECT sao permitidas"

        # 2. Bloquear multiplas statements (ponto e virgula)
        # Remove strings para evitar falsos positivos
        query_no_strings = re.sub(r"'[^']*'", "", query)
        if ";" in query_no_strings:
            return False, "Multiplas statements nao sao permitidas (;)"

        # 3. Bloquear comentarios SQL
        if "--" in query:
            return False, "Comentarios SQL (--) nao sao permitidos"
        if "/*" in query or "*/" in query:
            return False, "Comentarios SQL (/* */) nao sao permitidos"

        # 4. Bloquear palavras-chave perigosas
        # Remover strings para evitar falsos positivos (ex: WHERE NOME LIKE '%INSERT%')
        query_no_strings = re.sub(r"'[^']*'", "", normalized)
        for keyword in self.FORBIDDEN_KEYWORDS:
            # Usar word boundary para evitar falsos positivos
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, query_no_strings):
                return False, f"Palavra-chave proibida: {keyword}"

        # 5. Verificar whitelist de tabelas (se configurada)
        if self.whitelist:
            # Extrair tabelas da query (simplificado)
            # Busca padrao FROM/JOIN seguido de nome de tabela
            table_pattern = r'\b(?:FROM|JOIN)\s+([A-Z_][A-Z0-9_]*)'
            tables_found = re.findall(table_pattern, normalized)

            for table in tables_found:
                if table not in self.whitelist:
                    return False, f"Tabela nao permitida: {table}. Whitelist: {', '.join(self.whitelist)}"

        return True, "OK"

    # ============================================================
    # LIMITE DE LINHAS
    # ============================================================

    def add_row_limit(self, query: str, max_rows: int = MAX_ROWS) -> str:
        """
        Adiciona limite de linhas a query (Oracle ROWNUM).

        Se a query ja tem ROWNUM, respeita o menor valor.
        Se nao tem, envolve com wrapper.

        Args:
            query: SQL original
            max_rows: Limite maximo de linhas

        Returns:
            SQL com limite aplicado
        """
        normalized = query.upper()

        # Verificar se ja tem ROWNUM
        rownum_match = re.search(r'ROWNUM\s*<=?\s*(\d+)', normalized)

        if rownum_match:
            # Ja tem ROWNUM - verificar se e menor que max_rows
            existing_limit = int(rownum_match.group(1))
            if existing_limit <= max_rows:
                # Limite existente e aceitavel
                return query
            else:
                # Substituir pelo limite maximo
                return re.sub(
                    r'(ROWNUM\s*<=?\s*)\d+',
                    f'\\g<1>{max_rows}',
                    query,
                    flags=re.IGNORECASE
                )

        # Nao tem ROWNUM - adicionar wrapper
        query_clean = query.strip().rstrip(';')
        return f"SELECT * FROM ({query_clean}) WHERE ROWNUM <= {max_rows}"

    # ============================================================
    # AUTENTICACAO
    # ============================================================

    async def _authenticate(self) -> str:
        """
        Autentica na API Sankhya via OAuth2.

        Returns:
            Access token

        Raises:
            AuthenticationError: Se falhar autenticacao
        """
        # Verificar se token ainda e valido
        if self.access_token and self.token_expires:
            if datetime.now() < self.token_expires:
                return self.access_token

        # Validar credenciais
        if not all([SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET, SANKHYA_X_TOKEN]):
            raise AuthenticationError(
                "Credenciais Sankhya nao configuradas no .env "
                "(SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET, SANKHYA_X_TOKEN)"
            )

        url = f"{SANKHYA_BASE_URL}/authenticate"
        headers = {
            "X-Token": SANKHYA_X_TOKEN,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "client_id": SANKHYA_CLIENT_ID,
            "client_secret": SANKHYA_CLIENT_SECRET,
            "grant_type": "client_credentials",
        }

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            try:
                response = await client.post(url, headers=headers, data=data)
                response.raise_for_status()

                result = response.json()
                self.access_token = result.get("access_token")

                # Token expira em ~5 minutos no Sankhya, usar 4 min por seguranca
                from datetime import timedelta
                self.token_expires = datetime.now() + timedelta(minutes=4)

                print("[OK] Token Sankhya obtido (expira em 4 min)")
                return self.access_token

            except httpx.HTTPStatusError as e:
                raise AuthenticationError(f"Erro HTTP na autenticacao: {e.response.status_code}")
            except Exception as e:
                raise AuthenticationError(f"Erro na autenticacao: {str(e)}")

    # ============================================================
    # EXECUCAO
    # ============================================================

    async def execute(self, query: str) -> dict:
        """
        Executa query SQL de forma segura.

        Args:
            query: SQL SELECT a ser executado

        Returns:
            dict com:
                - success: bool
                - data: lista de dicts com resultados (se sucesso)
                - columns: lista de nomes das colunas (se sucesso)
                - row_count: numero de linhas retornadas
                - error: mensagem de erro (se falha)
                - query_executed: query que foi executada (com limites aplicados)

        Raises:
            QuerySecurityError: Se query falhar validacao
            QueryExecutionError: Se erro na execucao
        """
        # 1. Validar query
        is_valid, error_msg = self.validate_query(query)
        if not is_valid:
            raise QuerySecurityError(error_msg)

        # 2. Adicionar limite de linhas
        safe_query = self.add_row_limit(query)

        # 3. Executar com retry automatico em caso de token expirado
        return await self._execute_with_retry(safe_query)

    async def _execute_with_retry(self, safe_query: str, retry_count: int = 0) -> dict:
        """
        Executa query com retry automatico em caso de 401/403 (token expirado).

        Args:
            safe_query: Query ja validada e com limite de linhas
            retry_count: Contador de retentativas (max 1)

        Returns:
            dict com resultado da execucao
        """
        MAX_RETRIES = 1

        # Autenticar (ou usar token existente)
        try:
            token = await self._authenticate()
        except AuthenticationError as e:
            return {
                "success": False,
                "error": str(e),
                "query_executed": safe_query,
            }

        # Executar via DbExplorerSP.executeQuery
        url = f"{SANKHYA_BASE_URL}/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "serviceName": "DbExplorerSP.executeQuery",
            "requestBody": {
                "sql": safe_query
            }
        }

        async with httpx.AsyncClient(timeout=QUERY_TIMEOUT, verify=False) as client:
            try:
                response = await client.post(url, headers=headers, json=payload)

                # Verificar se token expirou (401 ou 403)
                if response.status_code in (401, 403):
                    if retry_count < MAX_RETRIES:
                        print(f"[!] Token expirado (HTTP {response.status_code}), re-autenticando...")
                        # Invalidar token para forcar nova autenticacao
                        self.access_token = None
                        self.token_expires = None
                        # Tentar novamente
                        return await self._execute_with_retry(safe_query, retry_count + 1)
                    else:
                        return {
                            "success": False,
                            "error": f"Token expirado e retry falhou (HTTP {response.status_code})",
                            "query_executed": safe_query,
                        }

                response.raise_for_status()

                result = response.json()

                # Processar resposta Sankhya
                if result.get("status") == "1" or result.get("statusMessage") == "OK":
                    rows = result.get("responseBody", {}).get("rows", [])

                    # Extrair colunas do primeiro registro
                    columns = []
                    if rows:
                        columns = list(rows[0].keys()) if isinstance(rows[0], dict) else []

                    return {
                        "success": True,
                        "data": rows,
                        "columns": columns,
                        "row_count": len(rows),
                        "query_executed": safe_query,
                    }
                else:
                    error = result.get("statusMessage", "Erro desconhecido")
                    return {
                        "success": False,
                        "error": error,
                        "query_executed": safe_query,
                    }

            except httpx.TimeoutException:
                return {
                    "success": False,
                    "error": f"Timeout: query excedeu {QUERY_TIMEOUT} segundos",
                    "query_executed": safe_query,
                }
            except httpx.HTTPStatusError as e:
                # Se for 401/403 e ainda tem retry disponivel
                if e.response.status_code in (401, 403) and retry_count < MAX_RETRIES:
                    print(f"[!] Token expirado (HTTP {e.response.status_code}), re-autenticando...")
                    self.access_token = None
                    self.token_expires = None
                    return await self._execute_with_retry(safe_query, retry_count + 1)
                return {
                    "success": False,
                    "error": f"Erro HTTP: {e.response.status_code}",
                    "query_executed": safe_query,
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Erro na execucao: {str(e)}",
                    "query_executed": safe_query,
                }

    # ============================================================
    # FORMATACAO
    # ============================================================

    def format_results(self, result: dict, max_col_width: int = 50) -> str:
        """
        Formata resultado como tabela Markdown.

        Args:
            result: Resultado do execute()
            max_col_width: Largura maxima de coluna

        Returns:
            String formatada em Markdown
        """
        if not result.get("success"):
            return f"**Erro:** {result.get('error', 'Erro desconhecido')}"

        data = result.get("data", [])
        columns = result.get("columns", [])
        row_count = result.get("row_count", 0)

        if not data or not columns:
            return "_Nenhum resultado encontrado._"

        # Truncar valores longos
        def truncate(val, max_len):
            s = str(val) if val is not None else ""
            return s[:max_len] + "..." if len(s) > max_len else s

        # Construir tabela Markdown
        lines = []

        # Header
        header = "| " + " | ".join(truncate(col, max_col_width) for col in columns) + " |"
        separator = "| " + " | ".join("-" * min(len(str(col)), max_col_width) for col in columns) + " |"
        lines.append(header)
        lines.append(separator)

        # Rows (limitar a 50 para exibicao)
        display_rows = data[:50]
        for row in display_rows:
            if isinstance(row, dict):
                values = [truncate(row.get(col, ""), max_col_width) for col in columns]
            else:
                values = [truncate(v, max_col_width) for v in row]
            lines.append("| " + " | ".join(values) + " |")

        # Footer
        if row_count > 50:
            lines.append(f"\n_Exibindo 50 de {row_count} linhas._")
        else:
            lines.append(f"\n_Total: {row_count} linha(s)._")

        return "\n".join(lines)


# ============================================================
# FUNCOES AUXILIARES
# ============================================================

async def execute_safe_query(query: str, whitelist: Optional[list] = None) -> dict:
    """
    Funcao auxiliar para executar query de forma segura.

    Args:
        query: SQL SELECT
        whitelist: Lista opcional de tabelas permitidas

    Returns:
        Resultado da execucao
    """
    executor = SafeQueryExecutor(whitelist=whitelist)
    return await executor.execute(query)


def validate_query(query: str, whitelist: Optional[list] = None) -> tuple[bool, str]:
    """
    Funcao auxiliar para validar query sem executar.

    Args:
        query: SQL a validar
        whitelist: Lista opcional de tabelas permitidas

    Returns:
        tuple: (is_valid, error_message)
    """
    executor = SafeQueryExecutor(whitelist=whitelist)
    return executor.validate_query(query)


# ============================================================
# TESTES
# ============================================================

async def _run_tests():
    """Testes internos do modulo."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(Panel("[bold]SafeQueryExecutor - Testes[/]", border_style="cyan"))

    executor = SafeQueryExecutor()

    # Testes de validacao
    test_cases = [
        # (query, should_pass, description)
        ("SELECT * FROM TGFPAR", True, "SELECT simples"),
        ("select CODPARC from tgfpar where rownum <= 10", True, "SELECT minusculo"),
        ("DELETE FROM TGFPAR", False, "DELETE bloqueado"),
        ("SELECT * FROM TGFPAR; DROP TABLE TGFPAR", False, "Multiplas statements"),
        ("SELECT * FROM TGFPAR -- comentario", False, "Comentario linha"),
        ("SELECT * FROM TGFPAR /* hack */", False, "Comentario bloco"),
        ("SELECT * FROM TGFPAR WHERE NOME LIKE '%INSERT%'", True, "INSERT em string OK"),
        ("INSERT INTO TGFPAR VALUES (1)", False, "INSERT direto"),
        ("UPDATE TGFPAR SET NOME = 'X'", False, "UPDATE bloqueado"),
        ("DROP TABLE TGFPAR", False, "DROP bloqueado"),
        ("EXEC sp_query", False, "EXEC bloqueado"),
    ]

    console.print("\n[bold]Testes de Validacao:[/]")
    for query, should_pass, desc in test_cases:
        is_valid, error = executor.validate_query(query)
        status = "[green]PASS[/]" if is_valid == should_pass else "[red]FAIL[/]"
        console.print(f"  {status} {desc}: {error if not is_valid else 'OK'}")

    # Testes de limite de linhas
    console.print("\n[bold]Testes de Limite de Linhas:[/]")

    test_limits = [
        ("SELECT * FROM TGFPAR", "Sem ROWNUM -> adiciona wrapper"),
        ("SELECT * FROM TGFPAR WHERE ROWNUM <= 10", "ROWNUM 10 -> mantem"),
        ("SELECT * FROM TGFPAR WHERE ROWNUM <= 1000", "ROWNUM 1000 -> reduz para 500"),
    ]

    for query, desc in test_limits:
        result = executor.add_row_limit(query)
        console.print(f"  [cyan]{desc}[/]")
        console.print(f"    Original: {query}")
        console.print(f"    Resultado: {result}")

    # Teste com whitelist
    console.print("\n[bold]Teste com Whitelist:[/]")
    executor_wl = SafeQueryExecutor(whitelist=["TGFPAR", "TGFCAB"])

    wl_tests = [
        ("SELECT * FROM TGFPAR", True, "Tabela permitida"),
        ("SELECT * FROM TGFPRO", False, "Tabela nao permitida"),
        ("SELECT * FROM TGFPAR JOIN TGFCAB ON 1=1", True, "JOIN com tabelas permitidas"),
    ]

    for query, should_pass, desc in wl_tests:
        is_valid, error = executor_wl.validate_query(query)
        status = "[green]PASS[/]" if is_valid == should_pass else "[red]FAIL[/]"
        console.print(f"  {status} {desc}: {error if not is_valid else 'OK'}")

    console.print("\n[bold green]Testes concluidos![/]")


if __name__ == "__main__":
    asyncio.run(_run_tests())
