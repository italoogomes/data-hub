"""
Script para extrair dados da tabela TGFTOP (Tipos de Operacao).
Executa queries via API Sankhya e salva em JSON.
"""

import os
import json
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env da raiz do projeto
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

# Configuracao
SANKHYA_BASE_URL = "https://api.sankhya.com.br"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_X_TOKEN", "")

_access_token = None
_token_expires_at = 0


def authenticate():
    """Autentica na API do Sankhya via OAuth 2.0."""
    global _access_token, _token_expires_at

    if _access_token and time.time() < (_token_expires_at - 30):
        return _access_token

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

    with httpx.Client(timeout=30.0, verify=False) as client:
        response = client.post(url, headers=headers, data=data)

        if response.status_code != 200:
            raise Exception(f"Falha na autenticacao: {response.status_code} - {response.text}")

        result = response.json()
        _access_token = result["access_token"]
        _token_expires_at = time.time() + result.get("expires_in", 300)

        return _access_token


def execute_query(sql: str) -> dict:
    """Executa uma query SQL no Sankhya."""
    token = authenticate()

    url = f"{SANKHYA_BASE_URL}/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json"

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

    with httpx.Client(timeout=60.0, verify=False) as client:
        response = client.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "detail": response.text}

        data = response.json()

        if data.get("status") == "0":
            return {"error": "Erro na API Sankhya", "detail": data.get("statusMessage", data)}

        return data


def main():
    print("Extraindo dados da TGFTOP...")

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
        WHERE c.TABLE_NAME = 'TGFTOP'
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
        WHERE uc.TABLE_NAME = 'TGFTOP'
            AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY TIPO_CHAVE, CAMPO
    """
    resultado["chaves"] = execute_query(sql_chaves)

    # 3. Lista completa de TOPs com campos de comportamento
    print("3. Buscando lista de TOPs...")
    sql_tops = """
        SELECT CODTOP, DESCROPER, TIPMOV, DHALTER,
               ATESSION, ATESSION_ITEM, ABORESSION, ABORESSION_ITEM,
               GOLESSION, GOLESSION_ITEM, GOLNEGOC, GOLNEGOC_ITEM,
               ATUALFIN, ATUALEST, GERANFE, FISCALIMP,
               IMPRIME, IMPNOTA, ENVIAEMAIL
        FROM TGFTOP
        ORDER BY CODTOP
    """
    resultado["tops_completo"] = execute_query(sql_tops)

    # 4. TOPs mais usadas (join com TGFCAB)
    print("4. Buscando TOPs mais usadas...")
    sql_mais_usadas = """
        SELECT * FROM (
            SELECT T.CODTOP, T.DESCROPER, T.TIPMOV,
                   T.ATUALEST, T.ATUALFIN, T.GERANFE,
                   COUNT(*) AS QTD_NOTAS,
                   SUM(C.VLRNOTA) AS VLR_TOTAL
            FROM TGFCAB C
            JOIN TGFTOP T ON C.CODTOP = T.CODTOP
            GROUP BY T.CODTOP, T.DESCROPER, T.TIPMOV, T.ATUALEST, T.ATUALFIN, T.GERANFE
            ORDER BY QTD_NOTAS DESC
        ) WHERE ROWNUM <= 50
    """
    resultado["tops_mais_usadas"] = execute_query(sql_mais_usadas)

    # 5. Valores de dominio - TIPMOV
    print("5. Buscando dominios TIPMOV...")
    sql_tipmov = """
        SELECT TIPMOV AS VALOR, COUNT(*) AS QTD
        FROM TGFTOP
        WHERE TIPMOV IS NOT NULL
        GROUP BY TIPMOV
        ORDER BY QTD DESC
    """
    resultado["dominio_tipmov"] = execute_query(sql_tipmov)

    # 6. Contagem total
    print("6. Contando registros...")
    sql_count = "SELECT COUNT(*) AS TOTAL FROM TGFTOP"
    resultado["contagem"] = execute_query(sql_count)

    # 7. Sample de dados
    print("7. Buscando amostra...")
    sql_sample = """
        SELECT * FROM (
            SELECT CODTOP, DESCROPER, TIPMOV, ATUALEST, ATUALFIN, GERANFE, DHALTER
            FROM TGFTOP
            ORDER BY CODTOP
        ) WHERE ROWNUM <= 20
    """
    resultado["sample"] = execute_query(sql_sample)

    # Salva resultado
    output_file = Path(__file__).parent / "tgftop_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\nDados salvos em: {output_file}")

    # Mostra resumo
    if "contagem" in resultado and "responseBody" in resultado["contagem"]:
        rows = resultado["contagem"]["responseBody"].get("rows", [])
        if rows:
            print(f"Total de TOPs: {rows[0][0]}")

    if "tops_mais_usadas" in resultado and "responseBody" in resultado["tops_mais_usadas"]:
        rows = resultado["tops_mais_usadas"]["responseBody"].get("rows", [])
        print(f"\nTop 5 TOPs mais usadas:")
        for i, row in enumerate(rows[:5]):
            print(f"  {row[0]} - {row[1]} ({row[6]} notas)")


if __name__ == "__main__":
    main()
