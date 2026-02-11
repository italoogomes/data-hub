"""
Script para extrair TODAS as TOPs de empenho da TGFTOP.
Busca por descricao contendo 'EMPENHO' ou AD_RESERVAEMPENHO = 'S'.
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
    with httpx.Client(timeout=30.0, verify=False) as client:
        response = client.post(
            f"{SANKHYA_BASE_URL}/authenticate",
            headers={"X-Token": SANKHYA_X_TOKEN, "Content-Type": "application/x-www-form-urlencoded"},
            data={"client_id": SANKHYA_CLIENT_ID, "client_secret": SANKHYA_CLIENT_SECRET, "grant_type": "client_credentials"},
        )
        if response.status_code != 200:
            raise Exception(f"Auth falhou: {response.status_code}")
        result = response.json()
        _access_token = result["access_token"]
        _token_expires_at = time.time() + result.get("expires_in", 300)
        return _access_token


def execute_query(sql):
    token = authenticate()
    with httpx.Client(timeout=60.0, verify=False) as client:
        response = client.post(
            f"{SANKHYA_BASE_URL}/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"requestBody": {"sql": sql}},
        )
        data = response.json()
        if str(data.get("status")) != "1":
            print(f"ERRO: {data.get('statusMessage', data)}")
            return []
        try:
            rows = data["responseBody"]["rows"]
            return rows if isinstance(rows, list) else []
        except (KeyError, TypeError):
            return []


def main():
    # 1. TOPs com EMPENHO na descricao
    print("=" * 100)
    print("BUSCA 1: TOPs com 'EMPENHO' na descricao")
    print("=" * 100)

    sql1 = """
    SELECT CODTIPOPER, DESCROPER, TIPMOV, ATIVO, ATUALEST, ATUALFIN, NFE, AD_RESERVAEMPENHO
    FROM TGFTOP
    WHERE UPPER(DESCROPER) LIKE '%EMPENHO%'
      AND DHALTER = (SELECT MAX(DHALTER) FROM TGFTOP T2 WHERE T2.CODTIPOPER = TGFTOP.CODTIPOPER)
    ORDER BY CODTIPOPER
    """
    rows1 = execute_query(sql1)
    print(f"\nEncontradas: {len(rows1)} TOPs\n")
    for r in rows1:
        if isinstance(r, list):
            print(f"  TOP {r[0]:>5} | {str(r[1]):<70} | TIPMOV={r[2]} | ATIVO={r[3]} | ATUALEST={r[4]} | ATUALFIN={r[5]} | NFE={r[6]} | EMPENHO={r[7]}")

    # 2. TOPs com AD_RESERVAEMPENHO = 'S' (mesmo sem EMPENHO no nome)
    print("\n" + "=" * 100)
    print("BUSCA 2: TOPs com AD_RESERVAEMPENHO = 'S' (campo ativo)")
    print("=" * 100)

    sql2 = """
    SELECT CODTIPOPER, DESCROPER, TIPMOV, ATIVO, ATUALEST, ATUALFIN, NFE, AD_RESERVAEMPENHO
    FROM TGFTOP
    WHERE AD_RESERVAEMPENHO = 'S'
      AND DHALTER = (SELECT MAX(DHALTER) FROM TGFTOP T2 WHERE T2.CODTIPOPER = TGFTOP.CODTIPOPER)
    ORDER BY CODTIPOPER
    """
    rows2 = execute_query(sql2)
    print(f"\nEncontradas: {len(rows2)} TOPs\n")
    for r in rows2:
        if isinstance(r, list):
            print(f"  TOP {r[0]:>5} | {str(r[1]):<70} | TIPMOV={r[2]} | ATIVO={r[3]} | ATUALEST={r[4]} | ATUALFIN={r[5]} | NFE={r[6]} | EMPENHO={r[7]}")

    # 3. Volume de notas para TODAS as TOPs de empenho encontradas
    all_tops = set()
    for r in rows1:
        if isinstance(r, list):
            all_tops.add(int(r[0]))
    for r in rows2:
        if isinstance(r, list):
            all_tops.add(int(r[0]))

    if all_tops:
        tops_str = ",".join(str(t) for t in sorted(all_tops))
        print("\n" + "=" * 100)
        print(f"VOLUME DE NOTAS - {len(all_tops)} TOPs de empenho")
        print("=" * 100)

        sql3 = f"""
        SELECT C.CODTIPOPER,
               COUNT(*) AS QTD,
               SUM(C.VLRNOTA) AS VLR_TOTAL,
               SUM(CASE WHEN C.PENDENTE = 'S' THEN 1 ELSE 0 END) AS PENDENTES,
               SUM(CASE WHEN C.PENDENTE = 'N' THEN 1 ELSE 0 END) AS CONCLUIDOS
        FROM TGFCAB C
        WHERE C.CODTIPOPER IN ({tops_str})
          AND C.STATUSNOTA <> 'C'
        GROUP BY C.CODTIPOPER
        ORDER BY C.CODTIPOPER
        """
        rows3 = execute_query(sql3)
        print(f"\n{'TOP':>5} | {'QTD':>6} | {'VLR_TOTAL':>15} | {'PENDENTES':>9} | {'CONCLUIDOS':>10}")
        print("-" * 60)
        for r in rows3:
            if isinstance(r, list):
                vlr = float(r[2] or 0)
                print(f"{r[0]:>5} | {r[1]:>6} | R$ {vlr:>12,.2f} | {r[3]:>9} | {r[4]:>10}")

    print("\n" + "=" * 100)
    print("Consulta finalizada.")


if __name__ == "__main__":
    main()
