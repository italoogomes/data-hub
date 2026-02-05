"""
Script para extrair dados da tabela TGFVEN (Vendedores).
"""

import os
import json
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

SANKHYA_BASE_URL = "https://api.sankhya.com.br"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_X_TOKEN", "")

_access_token = None
_token_expires_at = 0


def authenticate():
    global _access_token, _token_expires_at
    if _access_token and time.time() < (_token_expires_at - 30):
        return _access_token

    url = f"{SANKHYA_BASE_URL}/authenticate"
    headers = {"X-Token": SANKHYA_X_TOKEN, "Content-Type": "application/x-www-form-urlencoded"}
    data = {"client_id": SANKHYA_CLIENT_ID, "client_secret": SANKHYA_CLIENT_SECRET, "grant_type": "client_credentials"}

    with httpx.Client(timeout=30.0, verify=False) as client:
        response = client.post(url, headers=headers, data=data)
        if response.status_code != 200:
            raise Exception(f"Falha: {response.status_code}")
        result = response.json()
        _access_token = result["access_token"]
        _token_expires_at = time.time() + result.get("expires_in", 300)
        return _access_token


def execute_query(sql: str) -> dict:
    token = authenticate()
    url = f"{SANKHYA_BASE_URL}/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"serviceName": "DbExplorerSP.executeQuery", "requestBody": {"sql": sql}}

    with httpx.Client(timeout=60.0, verify=False) as client:
        response = client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "detail": response.text}
        data = response.json()
        if data.get("status") == "0":
            return {"error": "Erro na API", "detail": data.get("statusMessage", data)}
        return data


def main():
    print("Extraindo dados da TGFVEN (Vendedores)...")

    resultado = {}

    # 1. Estrutura da tabela
    print("1. Buscando estrutura...")
    sql_estrutura = """
        SELECT
            c.COLUMN_NAME as CAMPO,
            c.DATA_TYPE as TIPO,
            c.DATA_LENGTH as TAMANHO,
            c.NULLABLE as PERMITE_NULO,
            NVL(cc.COMMENTS, ' ') as COMENTARIO
        FROM USER_TAB_COLUMNS c
        LEFT JOIN USER_COL_COMMENTS cc
            ON c.TABLE_NAME = cc.TABLE_NAME
            AND c.COLUMN_NAME = cc.COLUMN_NAME
        WHERE c.TABLE_NAME = 'TGFVEN'
        ORDER BY c.COLUMN_ID
    """
    resultado["estrutura"] = execute_query(sql_estrutura)

    # 2. Chaves PK/FK
    print("2. Buscando chaves...")
    sql_chaves = """
        SELECT
            CASE uc.CONSTRAINT_TYPE
                WHEN 'P' THEN 'PK'
                WHEN 'R' THEN 'FK'
            END as TIPO_CHAVE,
            ucc.COLUMN_NAME as CAMPO,
            uc.CONSTRAINT_NAME as NOME_CONSTRAINT,
            r_uc.TABLE_NAME as TABELA_REF,
            r_ucc.COLUMN_NAME as CAMPO_REF
        FROM USER_CONSTRAINTS uc
        JOIN USER_CONS_COLUMNS ucc
            ON uc.CONSTRAINT_NAME = ucc.CONSTRAINT_NAME
        LEFT JOIN USER_CONSTRAINTS r_uc
            ON uc.R_CONSTRAINT_NAME = r_uc.CONSTRAINT_NAME
        LEFT JOIN USER_CONS_COLUMNS r_ucc
            ON r_uc.CONSTRAINT_NAME = r_ucc.CONSTRAINT_NAME
        WHERE uc.TABLE_NAME = 'TGFVEN'
            AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY TIPO_CHAVE, CAMPO
    """
    resultado["chaves"] = execute_query(sql_chaves)

    # 3. Contagem total
    print("3. Contando registros...")
    sql_count = "SELECT COUNT(*) AS TOTAL FROM TGFVEN"
    resultado["contagem"] = execute_query(sql_count)

    # 4. Lista de vendedores principais
    print("4. Buscando lista de vendedores...")
    sql_vendedores = """
        SELECT * FROM (
            SELECT CODVEND, APELIDO, CODPARC, CODGER, TIPVEND, CODCARGAHOR
            FROM TGFVEN
            ORDER BY CODVEND
        ) WHERE ROWNUM <= 100
    """
    resultado["vendedores"] = execute_query(sql_vendedores)

    # 5. Vendedores mais ativos (por notas)
    print("5. Buscando vendedores mais ativos...")
    sql_mais_ativos = """
        SELECT * FROM (
            SELECT V.CODVEND, V.APELIDO, V.TIPVEND,
                   COUNT(*) AS QTD_NOTAS,
                   SUM(C.VLRNOTA) AS VLR_TOTAL
            FROM TGFCAB C
            JOIN TGFVEN V ON C.CODVEND = V.CODVEND
            WHERE C.TIPMOV = 'V'
            GROUP BY V.CODVEND, V.APELIDO, V.TIPVEND
            ORDER BY QTD_NOTAS DESC
        ) WHERE ROWNUM <= 30
    """
    resultado["vendedores_mais_ativos"] = execute_query(sql_mais_ativos)

    # 6. Tipos de vendedor
    print("6. Buscando tipos de vendedor...")
    sql_tipos = "SELECT TIPVEND AS VALOR, COUNT(*) AS QTD FROM TGFVEN GROUP BY TIPVEND ORDER BY QTD DESC"
    resultado["dominio_tipvend"] = execute_query(sql_tipos)

    # 7. Sample completo
    print("7. Buscando amostra completa...")
    sql_sample = """
        SELECT * FROM (
            SELECT * FROM TGFVEN ORDER BY CODVEND
        ) WHERE ROWNUM <= 20
    """
    resultado["sample"] = execute_query(sql_sample)

    # 8. Vendedores por gerente
    print("8. Buscando vendedores por gerente...")
    sql_gerentes = """
        SELECT CODGER, COUNT(*) AS QTD_VENDEDORES
        FROM TGFVEN
        WHERE CODGER IS NOT NULL
        GROUP BY CODGER
        ORDER BY QTD_VENDEDORES DESC
    """
    resultado["vendedores_por_gerente"] = execute_query(sql_gerentes)

    # Salvar
    output_file = Path(__file__).parent / "tgfven_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\nDados salvos em: {output_file}")

    # Mostrar resumo
    if "contagem" in resultado and "responseBody" in resultado["contagem"]:
        rows = resultado["contagem"]["responseBody"].get("rows", [])
        if rows:
            print(f"Total de vendedores: {rows[0][0]}")

    if "vendedores_mais_ativos" in resultado and "responseBody" in resultado["vendedores_mais_ativos"]:
        rows = resultado["vendedores_mais_ativos"]["responseBody"].get("rows", [])
        if rows:
            print(f"\nTop 10 vendedores mais ativos:")
            for row in rows[:10]:
                print(f"  {row[0]:5} - {str(row[1] or ''):30} | {row[3]:>8} notas | R$ {row[4]:>12,.2f}")


if __name__ == "__main__":
    main()
