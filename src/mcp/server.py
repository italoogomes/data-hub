"""
MCP Server para integração com Sankhya ERP.

Este servidor expõe ferramentas para consultar o banco de dados do Sankhya
através da API oficial (DbExplorerSP).

IMPORTANTE: O banco é Oracle, usar sintaxe Oracle (ROWNUM, não TOP).
"""

import os
import json
import time
import httpx
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Carrega .env da raiz do projeto
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

# Configuração do Sankhya (OAuth 2.0)
SANKHYA_BASE_URL = "https://api.sankhya.com.br"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_X_TOKEN", "")

# Inicializa o MCP Server
mcp = FastMCP("sankhya-mcp")


class SankhyaClient:
    """Cliente para comunicação com a API do Sankhya."""

    def __init__(self):
        self.base_url = SANKHYA_BASE_URL
        self.client_id = SANKHYA_CLIENT_ID
        self.client_secret = SANKHYA_CLIENT_SECRET
        self.x_token = SANKHYA_X_TOKEN
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    async def _authenticate(self) -> str:
        """
        Autentica na API do Sankhya via OAuth 2.0.

        Returns:
            Access token válido
        """
        # Verifica se token ainda é válido (com margem de 30s)
        if self._access_token and time.time() < (self._token_expires_at - 30):
            return self._access_token

        url = f"{self.base_url}/authenticate"

        headers = {
            "X-Token": self.x_token,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }

        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(url, headers=headers, data=data)

            if response.status_code != 200:
                raise Exception(f"Falha na autenticação: {response.status_code} - {response.text}")

            result = response.json()
            self._access_token = result["access_token"]
            self._token_expires_at = time.time() + result.get("expires_in", 300)

            return self._access_token

    async def execute_query(self, sql: str) -> dict:
        """
        Executa uma query SQL no Sankhya via DbExplorerSP.

        Args:
            sql: Query SQL (apenas SELECT)

        Returns:
            Resultado da query em formato dict
        """
        if not sql.strip().upper().startswith("SELECT"):
            return {"error": "Apenas queries SELECT são permitidas"}

        try:
            token = await self._authenticate()
        except Exception as e:
            return {"error": f"Falha na autenticação: {str(e)}"}

        url = f"{self.base_url}/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "serviceName": "DbExplorerSP.executeQuery",
            "requestBody": {
                "sql": sql
            }
        }

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 401:
                # Token expirou, tenta renovar
                self._access_token = None
                return await self.execute_query(sql)

            if response.status_code != 200:
                return {
                    "error": f"HTTP {response.status_code}",
                    "detail": response.text
                }

            data = response.json()

            if data.get("status") == "0":
                return {
                    "error": "Erro na API Sankhya",
                    "detail": data.get("statusMessage", data)
                }

            return data


# Instância global do cliente
sankhya = SankhyaClient()


@mcp.tool()
async def executar_query(sql: str) -> str:
    """
    Executa uma query SQL SELECT no banco do Sankhya (Oracle).

    Args:
        sql: Query SQL (apenas SELECT é permitido). Use sintaxe Oracle (ROWNUM, não TOP).

    Returns:
        Resultado da query em JSON
    """
    result = await sankhya.execute_query(sql)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def listar_tabelas(filtro: Optional[str] = None) -> str:
    """
    Lista tabelas do banco de dados do Sankhya.

    Args:
        filtro: Filtro opcional para nome da tabela (ex: 'TGF' lista tabelas que começam com TGF)

    Returns:
        Lista de tabelas em JSON
    """
    sql = """
        SELECT TABLE_NAME as tabela
        FROM USER_TABLES
        WHERE 1=1
    """

    if filtro:
        sql += f" AND TABLE_NAME LIKE '{filtro.upper()}%'"

    sql += " ORDER BY TABLE_NAME"

    result = await sankhya.execute_query(sql)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def descrever_tabela(tabela: str) -> str:
    """
    Mostra a estrutura de uma tabela (campos, tipos, comentários).

    Args:
        tabela: Nome da tabela (ex: TGFCAB)

    Returns:
        Estrutura da tabela em JSON
    """
    tabela = tabela.upper()

    sql = f"""
        SELECT
            c.COLUMN_NAME as campo,
            c.DATA_TYPE as tipo,
            c.DATA_LENGTH as tamanho,
            c.NULLABLE as permite_nulo,
            c.DATA_DEFAULT as valor_padrao,
            NVL(cc.COMMENTS, '') as comentario
        FROM USER_TAB_COLUMNS c
        LEFT JOIN USER_COL_COMMENTS cc
            ON c.TABLE_NAME = cc.TABLE_NAME
            AND c.COLUMN_NAME = cc.COLUMN_NAME
        WHERE c.TABLE_NAME = '{tabela}'
        ORDER BY c.COLUMN_ID
    """

    result = await sankhya.execute_query(sql)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def buscar_chaves(tabela: str) -> str:
    """
    Mostra as chaves primárias (PK) e estrangeiras (FK) de uma tabela.

    Args:
        tabela: Nome da tabela (ex: TGFCAB)

    Returns:
        Chaves da tabela em JSON
    """
    tabela = tabela.upper()

    sql = f"""
        SELECT
            CASE uc.CONSTRAINT_TYPE
                WHEN 'P' THEN 'PK'
                WHEN 'R' THEN 'FK'
            END as tipo_chave,
            ucc.COLUMN_NAME as campo,
            uc.CONSTRAINT_NAME as nome_constraint,
            r_uc.TABLE_NAME as tabela_referenciada,
            r_ucc.COLUMN_NAME as campo_referenciado
        FROM USER_CONSTRAINTS uc
        JOIN USER_CONS_COLUMNS ucc
            ON uc.CONSTRAINT_NAME = ucc.CONSTRAINT_NAME
        LEFT JOIN USER_CONSTRAINTS r_uc
            ON uc.R_CONSTRAINT_NAME = r_uc.CONSTRAINT_NAME
        LEFT JOIN USER_CONS_COLUMNS r_ucc
            ON r_uc.CONSTRAINT_NAME = r_ucc.CONSTRAINT_NAME
        WHERE uc.TABLE_NAME = '{tabela}'
            AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY tipo_chave, campo
    """

    result = await sankhya.execute_query(sql)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def buscar_valores_dominio(tabela: str, campo: str, limite: int = 50) -> str:
    """
    Lista valores distintos de um campo (útil para entender domínios/enums).

    Args:
        tabela: Nome da tabela (ex: TGFCAB)
        campo: Nome do campo (ex: TIPMOV)
        limite: Quantidade máxima de valores (default: 50)

    Returns:
        Valores distintos em JSON
    """
    tabela = tabela.upper()
    campo = campo.upper()
    limite = min(limite, 100)  # Limita a 100 para não sobrecarregar

    sql = f"""
        SELECT * FROM (
            SELECT
                {campo} as valor,
                COUNT(*) as quantidade
            FROM {tabela}
            WHERE {campo} IS NOT NULL
            GROUP BY {campo}
            ORDER BY quantidade DESC
        ) WHERE ROWNUM <= {limite}
    """

    result = await sankhya.execute_query(sql)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def sample_dados(tabela: str, limite: int = 10, where: Optional[str] = None) -> str:
    """
    Retorna uma amostra de dados de uma tabela.

    Args:
        tabela: Nome da tabela (ex: TGFCAB)
        limite: Quantidade de registros (default: 10, max: 100)
        where: Cláusula WHERE opcional (ex: "TIPMOV = 'V'")

    Returns:
        Amostra de dados em JSON
    """
    tabela = tabela.upper()
    limite = min(limite, 100)  # Limita a 100 para não sobrecarregar

    if where:
        sql = f"SELECT * FROM {tabela} WHERE {where} AND ROWNUM <= {limite}"
    else:
        sql = f"SELECT * FROM {tabela} WHERE ROWNUM <= {limite}"

    result = await sankhya.execute_query(sql)
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
