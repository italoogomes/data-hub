"""
Script para extrair dados complementares da TGFTOP.
Corrigindo nomes de colunas.
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
    print("Extraindo dados complementares TGFTOP...")

    # Carregar dados existentes
    data_file = Path(__file__).parent / "tgftop_data.json"
    with open(data_file, "r", encoding="utf-8") as f:
        resultado = json.load(f)

    # 1. Lista de TOPs com campos corretos
    print("1. Buscando lista de TOPs...")
    sql_tops = """
        SELECT CODTIPOPER, DESCROPER, TIPMOV, DHALTER,
               ATUALFIN, ATUALEST, NFE, ATIVO,
               TEMICMS, TEMIPI, TEMPIS, TEMCOFINS
        FROM TGFTOP
        ORDER BY CODTIPOPER
    """
    resultado["tops_lista"] = execute_query(sql_tops)

    # 2. TOPs mais usadas (usando CODTIPOPER)
    print("2. Buscando TOPs mais usadas...")
    sql_mais_usadas = """
        SELECT * FROM (
            SELECT T.CODTIPOPER, T.DESCROPER, T.TIPMOV,
                   T.ATUALEST, T.ATUALFIN, T.NFE,
                   COUNT(*) AS QTD_NOTAS,
                   SUM(C.VLRNOTA) AS VLR_TOTAL
            FROM TGFCAB C
            JOIN TGFTOP T ON C.CODTIPOPER = T.CODTIPOPER AND C.DHTIPOPER = T.DHALTER
            GROUP BY T.CODTIPOPER, T.DESCROPER, T.TIPMOV, T.ATUALEST, T.ATUALFIN, T.NFE
            ORDER BY QTD_NOTAS DESC
        ) WHERE ROWNUM <= 50
    """
    resultado["tops_mais_usadas"] = execute_query(sql_mais_usadas)

    # 3. Sample simples
    print("3. Buscando amostra...")
    sql_sample = """
        SELECT * FROM (
            SELECT CODTIPOPER, DESCROPER, TIPMOV, ATUALEST, ATUALFIN, NFE, ATIVO
            FROM TGFTOP
            ORDER BY CODTIPOPER
        ) WHERE ROWNUM <= 30
    """
    resultado["sample"] = execute_query(sql_sample)

    # 4. Dominios adicionais
    print("4. Buscando dominios...")
    sql_atualest = "SELECT ATUALEST AS VALOR, COUNT(*) AS QTD FROM TGFTOP GROUP BY ATUALEST ORDER BY QTD DESC"
    resultado["dominio_atualest"] = execute_query(sql_atualest)

    sql_atualfin = "SELECT ATUALFIN AS VALOR, COUNT(*) AS QTD FROM TGFTOP GROUP BY ATUALFIN ORDER BY QTD DESC"
    resultado["dominio_atualfin"] = execute_query(sql_atualfin)

    sql_nfe = "SELECT NFE AS VALOR, COUNT(*) AS QTD FROM TGFTOP WHERE NFE IS NOT NULL GROUP BY NFE ORDER BY QTD DESC"
    resultado["dominio_nfe"] = execute_query(sql_nfe)

    # Salvar
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\nDados atualizados em: {data_file}")

    # Mostrar resumo das TOPs mais usadas
    if "tops_mais_usadas" in resultado and "responseBody" in resultado["tops_mais_usadas"]:
        rows = resultado["tops_mais_usadas"]["responseBody"].get("rows", [])
        if rows:
            print(f"\nTop 10 TOPs mais usadas:")
            for i, row in enumerate(rows[:10]):
                print(f"  {row[0]:5} - {row[1][:40]:40} | {row[2]} | {row[6]:>8} notas")


if __name__ == "__main__":
    main()
