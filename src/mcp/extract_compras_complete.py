"""
Script para completar mapeamento de compras.
Investiga: TGFLIB, tabelas de cotação (TGFCOT/TGFCOI), tabelas de solicitação (TGFSOL/TGFSOI)

Versão standalone - não depende do MCP Server
"""

import os
import json
import time
import asyncio
import warnings
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Suprimir warnings de SSL
warnings.filterwarnings('ignore')

# Tenta importar httpx
try:
    import httpx
except ImportError:
    print("Instalando httpx...")
    os.system("pip install httpx")
    import httpx

# Carrega .env da raiz do projeto
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

# Configuração do Sankhya (OAuth 2.0)
SANKHYA_BASE_URL = "https://api.sankhya.com.br"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_X_TOKEN", "")


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
        """Autentica na API do Sankhya via OAuth 2.0."""
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
        """Executa uma query SQL no Sankhya via DbExplorerSP."""
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


# Cliente global
sankhya = SankhyaClient()


async def verificar_tabela_existe(tabela: str) -> bool:
    """Verifica se uma tabela existe no banco."""
    sql = f"SELECT COUNT(*) as existe FROM USER_TABLES WHERE TABLE_NAME = '{tabela.upper()}'"
    result = await sankhya.execute_query(sql)

    if "error" in result:
        print(f"Erro verificando {tabela}: {result['error']}")
        return False

    rows = result.get("responseBody", {}).get("rows", [])
    if rows:
        return int(rows[0][0]) > 0
    return False


async def descrever_tabela(tabela: str) -> dict:
    """Obtém estrutura completa de uma tabela."""
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
        WHERE c.TABLE_NAME = '{tabela.upper()}'
        ORDER BY c.COLUMN_ID
    """
    return await sankhya.execute_query(sql)


async def buscar_chaves(tabela: str) -> dict:
    """Obtém PKs e FKs de uma tabela."""
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
        WHERE uc.TABLE_NAME = '{tabela.upper()}'
            AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY tipo_chave, campo
    """
    return await sankhya.execute_query(sql)


async def contar_registros(tabela: str) -> int:
    """Conta registros de uma tabela."""
    sql = f"SELECT COUNT(*) as total FROM {tabela.upper()}"
    result = await sankhya.execute_query(sql)

    if "error" in result:
        return -1

    rows = result.get("responseBody", {}).get("rows", [])
    if rows:
        return int(rows[0][0])
    return 0


async def sample_dados(tabela: str, limite: int = 10, where: str = None) -> dict:
    """Obtém amostra de dados."""
    if where:
        sql = f"SELECT * FROM {tabela.upper()} WHERE {where} AND ROWNUM <= {limite}"
    else:
        sql = f"SELECT * FROM {tabela.upper()} WHERE ROWNUM <= {limite}"
    return await sankhya.execute_query(sql)


async def valores_dominio(tabela: str, campo: str, limite: int = 50) -> dict:
    """Lista valores distintos de um campo."""
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
    return await sankhya.execute_query(sql)


async def investigar_tgflib():
    """Investigacao completa da TGFLIB."""
    print("\n" + "="*60)
    print("INVESTIGANDO TGFLIB (Liberacoes/Aprovacoes)")
    print("="*60)

    # 1. Verificar se existe
    existe = await verificar_tabela_existe("TGFLIB")
    if not existe:
        print("[X] TGFLIB nao existe no banco!")
        return {"existe": False}

    print("[OK] TGFLIB existe")

    # 2. Contar registros
    total = await contar_registros("TGFLIB")
    print(f"Total de registros: {total:,}")

    # 3. Estrutura
    print("\nEstrutura da tabela:")
    estrutura = await descrever_tabela("TGFLIB")
    if estrutura.get("responseBody", {}).get("rows"):
        for row in estrutura["responseBody"]["rows"][:20]:
            print(f"  {row[0]:20} {row[1]:15} {row[5] if row[5] else ''}")

    # 4. Chaves
    print("\nChaves (PK/FK):")
    chaves = await buscar_chaves("TGFLIB")
    if chaves.get("responseBody", {}).get("rows"):
        for row in chaves["responseBody"]["rows"]:
            print(f"  {row[0]:3} {row[1]:20} -> {row[3] or ''}.{row[4] or ''}")

    # 5. Valores de dominio importantes
    print("\nDistribuicao por EVENTO (tipo de liberacao):")
    eventos = await valores_dominio("TGFLIB", "EVENTO")
    if eventos.get("responseBody", {}).get("rows"):
        for row in eventos["responseBody"]["rows"][:10]:
            print(f"  {row[0]:30} {row[1]:>10,}")

    print("\nDistribuicao por TABELA:")
    tabelas = await valores_dominio("TGFLIB", "TABELA")
    if tabelas.get("responseBody", {}).get("rows"):
        for row in tabelas["responseBody"]["rows"][:10]:
            print(f"  {row[0]:30} {row[1]:>10,}")

    print("\nStatus de liberacao (pendentes vs liberados):")
    pendentes_sql = """
        SELECT
            CASE WHEN DHLIB IS NULL THEN 'Pendente' ELSE 'Liberado' END as status,
            COUNT(*) as quantidade
        FROM TGFLIB
        GROUP BY CASE WHEN DHLIB IS NULL THEN 'Pendente' ELSE 'Liberado' END
    """
    pendentes = await sankhya.execute_query(pendentes_sql)
    if pendentes.get("responseBody", {}).get("rows"):
        for row in pendentes["responseBody"]["rows"]:
            print(f"  {row[0]:30} {row[1]:>10,}")

    # 6. Sample de dados
    print("\nAmostra de dados (5 registros):")
    sample = await sample_dados("TGFLIB", 5)

    # 7. Verificar conexao com TGFCAB
    print("\nVerificando conexao com TGFCAB via NUNOTA:")
    conexao_sql = """
        SELECT * FROM (
            SELECT
                l.NUNOTA,
                l.EVENTO,
                l.TABELA,
                l.DHLIB,
                c.NUMNOTA,
                c.CODTIPOPER,
                c.TIPMOV
            FROM TGFLIB l
            JOIN TGFCAB c ON l.NUNOTA = c.NUNOTA
            WHERE l.TABELA = 'TGFCAB'
            ORDER BY l.NUNOTA DESC
        ) WHERE ROWNUM <= 10
    """
    conexao = await sankhya.execute_query(conexao_sql)
    if conexao.get("responseBody", {}).get("rows"):
        print("  NUNOTA     EVENTO                    NUMNOTA  TOP   TIPMOV")
        for row in conexao["responseBody"]["rows"]:
            print(f"  {row[0]:<10} {row[1]:<25} {row[4]:<8} {row[5]:<5} {row[6]}")

    return {
        "existe": True,
        "total_registros": total,
        "estrutura": estrutura,
        "chaves": chaves,
        "eventos": eventos,
        "tabelas": tabelas,
        "pendentes": pendentes,
        "sample": sample,
        "conexao_tgfcab": conexao
    }


async def investigar_cotacao():
    """Verifica se existem tabelas de cotacao."""
    print("\n" + "="*60)
    print("INVESTIGANDO TABELAS DE COTACAO")
    print("="*60)

    tabelas_cotacao = ["TGFCOT", "TGFCOI", "TGFCOC", "AD_COTACAO", "AD_COTACAOITEM"]
    resultado = {}

    for tabela in tabelas_cotacao:
        existe = await verificar_tabela_existe(tabela)
        resultado[tabela] = existe
        status = "[OK] Existe" if existe else "[X] Nao existe"
        print(f"{tabela}: {status}")

        if existe:
            total = await contar_registros(tabela)
            print(f"  Total de registros: {total:,}")

            estrutura = await descrever_tabela(tabela)
            resultado[f"{tabela}_estrutura"] = estrutura

            chaves = await buscar_chaves(tabela)
            resultado[f"{tabela}_chaves"] = chaves

            sample = await sample_dados(tabela, 5)
            resultado[f"{tabela}_sample"] = sample

    # Verificar se ha tabelas com "COT" no nome
    print("\nBuscando outras tabelas com 'COT' no nome:")
    sql_cot = "SELECT TABLE_NAME FROM USER_TABLES WHERE TABLE_NAME LIKE '%COT%' ORDER BY TABLE_NAME"
    outras_cot = await sankhya.execute_query(sql_cot)
    resultado["outras_tabelas_cot"] = outras_cot
    if outras_cot.get("responseBody", {}).get("rows"):
        for row in outras_cot["responseBody"]["rows"]:
            print(f"  {row[0]}")
    else:
        print("  Nenhuma tabela encontrada")

    return resultado


async def investigar_solicitacao():
    """Verifica se existem tabelas de solicitacao de compra."""
    print("\n" + "="*60)
    print("INVESTIGANDO TABELAS DE SOLICITACAO DE COMPRA")
    print("="*60)

    tabelas_sol = ["TGFSOL", "TGFSOI", "AD_SOLICITACAO", "AD_SOLICITACAOITEM", "TGFSCM", "TGFSCI"]
    resultado = {}

    for tabela in tabelas_sol:
        existe = await verificar_tabela_existe(tabela)
        resultado[tabela] = existe
        status = "[OK] Existe" if existe else "[X] Nao existe"
        print(f"{tabela}: {status}")

        if existe:
            total = await contar_registros(tabela)
            print(f"  Total de registros: {total:,}")

            estrutura = await descrever_tabela(tabela)
            resultado[f"{tabela}_estrutura"] = estrutura

            chaves = await buscar_chaves(tabela)
            resultado[f"{tabela}_chaves"] = chaves

            sample = await sample_dados(tabela, 5)
            resultado[f"{tabela}_sample"] = sample

    # Verificar se ha tabelas com "SOL" no nome
    print("\nBuscando outras tabelas com 'SOL' no nome:")
    sql_sol = "SELECT TABLE_NAME FROM USER_TABLES WHERE TABLE_NAME LIKE '%SOL%' ORDER BY TABLE_NAME"
    outras_sol = await sankhya.execute_query(sql_sol)
    resultado["outras_tabelas_sol"] = outras_sol
    if outras_sol.get("responseBody", {}).get("rows"):
        for row in outras_sol["responseBody"]["rows"]:
            print(f"  {row[0]}")
    else:
        print("  Nenhuma tabela encontrada")

    # Verificar TGFCAB com TIPMOV='J' (Solicitacao)
    print("\nVerificando TGFCAB com TIPMOV='J' (Solicitacao de Compra):")
    sol_cab_sql = """
        SELECT
            TIPMOV,
            COUNT(*) as quantidade,
            SUM(VLRNOTA) as valor_total
        FROM TGFCAB
        WHERE TIPMOV = 'J'
        GROUP BY TIPMOV
    """
    sol_cab = await sankhya.execute_query(sol_cab_sql)
    resultado["tgfcab_tipmov_j"] = sol_cab

    if sol_cab.get("responseBody", {}).get("rows"):
        row = sol_cab["responseBody"]["rows"][0]
        print(f"[OK] Existe TIPMOV='J' em TGFCAB: {row[1]:,} registros, R$ {float(row[2] or 0):,.2f}")

        # Sample de solicitacoes
        sample_sol = await sample_dados("TGFCAB", 5, "TIPMOV = 'J'")
        resultado["tgfcab_tipmov_j_sample"] = sample_sol

        # TOPs usadas para solicitacao
        tops_sol_sql = """
            SELECT * FROM (
                SELECT
                    c.CODTIPOPER,
                    t.DESCROPER,
                    COUNT(*) as quantidade
                FROM TGFCAB c
                JOIN TGFTOP t ON c.CODTIPOPER = t.CODTIPOPER AND t.DHALTER = (
                    SELECT MAX(DHALTER) FROM TGFTOP WHERE CODTIPOPER = c.CODTIPOPER
                )
                WHERE c.TIPMOV = 'J'
                GROUP BY c.CODTIPOPER, t.DESCROPER
                ORDER BY quantidade DESC
            ) WHERE ROWNUM <= 10
        """
        tops_sol = await sankhya.execute_query(tops_sol_sql)
        resultado["tops_solicitacao"] = tops_sol
        if tops_sol.get("responseBody", {}).get("rows"):
            print("\n  TOPs usadas para solicitacao:")
            for row in tops_sol["responseBody"]["rows"]:
                print(f"    TOP {row[0]}: {row[1]} ({row[2]:,} registros)")
    else:
        print("[X] Nao existe TIPMOV='J' em TGFCAB")

    # Verificar tambem TIPMOV='O' (Pedido de Compra)
    print("\nVerificando TGFCAB com TIPMOV='O' (Pedido de Compra):")
    ped_cab_sql = """
        SELECT
            TIPMOV,
            COUNT(*) as quantidade,
            SUM(VLRNOTA) as valor_total
        FROM TGFCAB
        WHERE TIPMOV = 'O'
        GROUP BY TIPMOV
    """
    ped_cab = await sankhya.execute_query(ped_cab_sql)
    resultado["tgfcab_tipmov_o"] = ped_cab

    if ped_cab.get("responseBody", {}).get("rows"):
        row = ped_cab["responseBody"]["rows"][0]
        print(f"[OK] Existe TIPMOV='O' em TGFCAB: {row[1]:,} registros, R$ {float(row[2] or 0):,.2f}")

        # TOPs usadas para pedido de compra
        tops_ped_sql = """
            SELECT * FROM (
                SELECT
                    c.CODTIPOPER,
                    t.DESCROPER,
                    COUNT(*) as quantidade
                FROM TGFCAB c
                JOIN TGFTOP t ON c.CODTIPOPER = t.CODTIPOPER AND t.DHALTER = (
                    SELECT MAX(DHALTER) FROM TGFTOP WHERE CODTIPOPER = c.CODTIPOPER
                )
                WHERE c.TIPMOV = 'O'
                GROUP BY c.CODTIPOPER, t.DESCROPER
                ORDER BY quantidade DESC
            ) WHERE ROWNUM <= 10
        """
        tops_ped = await sankhya.execute_query(tops_ped_sql)
        resultado["tops_pedido_compra"] = tops_ped
        if tops_ped.get("responseBody", {}).get("rows"):
            print("\n  TOPs usadas para pedido de compra:")
            for row in tops_ped["responseBody"]["rows"]:
                print(f"    TOP {row[0]}: {row[1]} ({row[2]:,} registros)")
    else:
        print("[X] Nao existe TIPMOV='O' em TGFCAB")

    return resultado


async def main():
    """Executa todas as investigacoes."""
    print("Iniciando investigacao completa para mapeamento de compras")
    print("="*60)

    resultados = {}

    # 1. TGFLIB
    resultados["tgflib"] = await investigar_tgflib()

    # 2. Cotacao
    resultados["cotacao"] = await investigar_cotacao()

    # 3. Solicitacao
    resultados["solicitacao"] = await investigar_solicitacao()

    # Salvar resultados
    output_path = Path(__file__).parent / "compras_complete_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "="*60)
    print(f"[OK] Dados salvos em: {output_path}")
    print("="*60)

    return resultados


if __name__ == "__main__":
    asyncio.run(main())
