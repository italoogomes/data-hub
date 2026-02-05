"""
Script para extrair dados da tabela TSIEMP (Empresas/Filiais).
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
    print("Extraindo dados da TSIEMP (Empresas)...")

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
        WHERE c.TABLE_NAME = 'TSIEMP'
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
        WHERE uc.TABLE_NAME = 'TSIEMP'
            AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY TIPO_CHAVE, CAMPO
    """
    resultado["chaves"] = execute_query(sql_chaves)

    # 3. Lista de empresas
    print("3. Buscando lista de empresas...")
    sql_empresas = """
        SELECT CODEMP, NOMEFANTASIA, RAZAOSOCIAL, CGC,
               INSCESTADUAL, CODCID, TELEFONE, ATIVO
        FROM TSIEMP
        ORDER BY CODEMP
    """
    resultado["empresas"] = execute_query(sql_empresas)

    # 4. Empresas mais usadas em notas
    print("4. Buscando empresas mais usadas...")
    sql_mais_usadas = """
        SELECT * FROM (
            SELECT E.CODEMP, E.NOMEFANTASIA, E.RAZAOSOCIAL,
                   COUNT(*) AS QTD_NOTAS,
                   SUM(C.VLRNOTA) AS VLR_TOTAL
            FROM TGFCAB C
            JOIN TSIEMP E ON C.CODEMP = E.CODEMP
            GROUP BY E.CODEMP, E.NOMEFANTASIA, E.RAZAOSOCIAL
            ORDER BY QTD_NOTAS DESC
        ) WHERE ROWNUM <= 20
    """
    resultado["empresas_mais_usadas"] = execute_query(sql_mais_usadas)

    # 5. Contagem total
    print("5. Contando registros...")
    sql_count = "SELECT COUNT(*) AS TOTAL FROM TSIEMP"
    resultado["contagem"] = execute_query(sql_count)

    # 6. Sample completo
    print("6. Buscando amostra completa...")
    sql_sample = """
        SELECT * FROM (
            SELECT * FROM TSIEMP ORDER BY CODEMP
        ) WHERE ROWNUM <= 10
    """
    resultado["sample"] = execute_query(sql_sample)

    # Salvar
    output_file = Path(__file__).parent / "tsiemp_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\nDados salvos em: {output_file}")

    # Mostrar resumo
    if "contagem" in resultado and "responseBody" in resultado["contagem"]:
        rows = resultado["contagem"]["responseBody"].get("rows", [])
        if rows:
            print(f"Total de empresas: {rows[0][0]}")

    if "empresas" in resultado and "responseBody" in resultado["empresas"]:
        rows = resultado["empresas"]["responseBody"].get("rows", [])
        print(f"\nEmpresas cadastradas:")
        for row in rows:
            print(f"  {row[0]:3} - {row[1] or row[2]}")


if __name__ == "__main__":
    main()
