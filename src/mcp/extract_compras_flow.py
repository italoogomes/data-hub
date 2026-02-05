"""
Script para extrair dados do fluxo de compras completo.
Identifica tabelas, status e relacionamentos.
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

    with httpx.Client(timeout=120.0, verify=False) as client:
        response = client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "detail": response.text}
        data = response.json()
        if data.get("status") == "0":
            return {"error": "Erro na API", "detail": data.get("statusMessage", data)}
        return data


def main():
    print("=== MAPEAMENTO COMPLETO DO FLUXO DE COMPRAS ===\n")

    resultado = {}

    # 1. Status das notas de compra (STATUSNOTA, STATUSNFE)
    print("1. Analisando status das notas de compra...")
    sql_status_compra = """
        SELECT STATUSNOTA, COUNT(*) AS QTD
        FROM TGFCAB
        WHERE TIPMOV IN ('C', 'O', 'J')
        GROUP BY STATUSNOTA
        ORDER BY QTD DESC
    """
    resultado["status_nota_compra"] = execute_query(sql_status_compra)

    # 2. Campos de controle em TGFCAB para compras
    print("2. Buscando campos de status em TGFCAB...")
    sql_campos_status = """
        SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = 'TGFCAB'
          AND (COLUMN_NAME LIKE '%STATUS%'
               OR COLUMN_NAME LIKE '%PEND%'
               OR COLUMN_NAME LIKE '%APROV%'
               OR COLUMN_NAME LIKE '%CONFIRM%'
               OR COLUMN_NAME LIKE '%LIBER%')
        ORDER BY COLUMN_NAME
    """
    resultado["campos_status_tgfcab"] = execute_query(sql_campos_status)

    # 3. Estrutura TGFEST (Estoque)
    print("3. Buscando estrutura TGFEST...")
    sql_estrutura_est = """
        SELECT
            c.COLUMN_NAME as CAMPO,
            c.DATA_TYPE as TIPO,
            c.DATA_LENGTH as TAMANHO,
            c.NULLABLE as PERMITE_NULO
        FROM USER_TAB_COLUMNS c
        WHERE c.TABLE_NAME = 'TGFEST'
        ORDER BY c.COLUMN_ID
    """
    resultado["estrutura_tgfest"] = execute_query(sql_estrutura_est)

    # 4. Chaves TGFEST
    print("4. Buscando chaves TGFEST...")
    sql_chaves_est = """
        SELECT
            CASE uc.CONSTRAINT_TYPE WHEN 'P' THEN 'PK' WHEN 'R' THEN 'FK' END as TIPO_CHAVE,
            ucc.COLUMN_NAME as CAMPO,
            r_uc.TABLE_NAME as TABELA_REF,
            r_ucc.COLUMN_NAME as CAMPO_REF
        FROM USER_CONSTRAINTS uc
        JOIN USER_CONS_COLUMNS ucc ON uc.CONSTRAINT_NAME = ucc.CONSTRAINT_NAME
        LEFT JOIN USER_CONSTRAINTS r_uc ON uc.R_CONSTRAINT_NAME = r_uc.CONSTRAINT_NAME
        LEFT JOIN USER_CONS_COLUMNS r_ucc ON r_uc.CONSTRAINT_NAME = r_ucc.CONSTRAINT_NAME
        WHERE uc.TABLE_NAME = 'TGFEST' AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY TIPO_CHAVE, CAMPO
    """
    resultado["chaves_tgfest"] = execute_query(sql_chaves_est)

    # 5. Sample TGFEST
    print("5. Buscando amostra TGFEST...")
    sql_sample_est = """
        SELECT * FROM (
            SELECT CODPROD, CODEMP, CODLOCAL, ESTOQUE, RESERVADO, QTDPENDENTE
            FROM TGFEST
            WHERE ESTOQUE > 0
            ORDER BY ESTOQUE DESC
        ) WHERE ROWNUM <= 20
    """
    resultado["sample_tgfest"] = execute_query(sql_sample_est)

    # 6. Estrutura TGFFIN (Financeiro)
    print("6. Buscando estrutura TGFFIN...")
    sql_estrutura_fin = """
        SELECT
            c.COLUMN_NAME as CAMPO,
            c.DATA_TYPE as TIPO,
            c.DATA_LENGTH as TAMANHO,
            c.NULLABLE as PERMITE_NULO
        FROM USER_TAB_COLUMNS c
        WHERE c.TABLE_NAME = 'TGFFIN'
        ORDER BY c.COLUMN_ID
    """
    resultado["estrutura_tgffin"] = execute_query(sql_estrutura_fin)

    # 7. Chaves TGFFIN
    print("7. Buscando chaves TGFFIN...")
    sql_chaves_fin = """
        SELECT
            CASE uc.CONSTRAINT_TYPE WHEN 'P' THEN 'PK' WHEN 'R' THEN 'FK' END as TIPO_CHAVE,
            ucc.COLUMN_NAME as CAMPO,
            r_uc.TABLE_NAME as TABELA_REF,
            r_ucc.COLUMN_NAME as CAMPO_REF
        FROM USER_CONSTRAINTS uc
        JOIN USER_CONS_COLUMNS ucc ON uc.CONSTRAINT_NAME = ucc.CONSTRAINT_NAME
        LEFT JOIN USER_CONSTRAINTS r_uc ON uc.R_CONSTRAINT_NAME = r_uc.CONSTRAINT_NAME
        LEFT JOIN USER_CONS_COLUMNS r_ucc ON r_uc.CONSTRAINT_NAME = r_ucc.CONSTRAINT_NAME
        WHERE uc.TABLE_NAME = 'TGFFIN' AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY TIPO_CHAVE, CAMPO
    """
    resultado["chaves_tgffin"] = execute_query(sql_chaves_fin)

    # 8. Sample TGFFIN (titulos a pagar de compras)
    print("8. Buscando amostra TGFFIN (pagar)...")
    sql_sample_fin = """
        SELECT * FROM (
            SELECT NUFIN, NUNOTA, CODPARC, DTVENC, VLRDESDOB, RECDESP, PROVISAO
            FROM TGFFIN
            WHERE RECDESP = -1
            ORDER BY NUFIN DESC
        ) WHERE ROWNUM <= 20
    """
    resultado["sample_tgffin_pagar"] = execute_query(sql_sample_fin)

    # 9. Vinculo nota -> financeiro
    print("9. Analisando vinculo nota-financeiro...")
    sql_vinculo_fin = """
        SELECT * FROM (
            SELECT C.NUNOTA, C.CODTIPOPER, C.VLRNOTA,
                   COUNT(F.NUFIN) AS QTD_TITULOS,
                   SUM(F.VLRDESDOB) AS VLR_TITULOS
            FROM TGFCAB C
            LEFT JOIN TGFFIN F ON C.NUNOTA = F.NUNOTA
            WHERE C.TIPMOV = 'C' AND C.CODTIPOPER = 1209
            GROUP BY C.NUNOTA, C.CODTIPOPER, C.VLRNOTA
            ORDER BY C.NUNOTA DESC
        ) WHERE ROWNUM <= 20
    """
    resultado["vinculo_nota_financeiro"] = execute_query(sql_vinculo_fin)

    # 10. Tabela de aprovacoes (se existir)
    print("10. Buscando tabelas de aprovacao...")
    sql_tabelas_aprov = """
        SELECT TABLE_NAME
        FROM USER_TABLES
        WHERE TABLE_NAME LIKE '%APROV%'
           OR TABLE_NAME LIKE '%LIBER%'
           OR TABLE_NAME LIKE '%ALCAD%'
        ORDER BY TABLE_NAME
    """
    resultado["tabelas_aprovacao"] = execute_query(sql_tabelas_aprov)

    # 11. Estrutura TGFLIB (Liberacoes) se existir
    print("11. Buscando estrutura TGFLIB...")
    sql_estrutura_lib = """
        SELECT
            c.COLUMN_NAME as CAMPO,
            c.DATA_TYPE as TIPO,
            c.DATA_LENGTH as TAMANHO
        FROM USER_TAB_COLUMNS c
        WHERE c.TABLE_NAME = 'TGFLIB'
        ORDER BY c.COLUMN_ID
    """
    resultado["estrutura_tgflib"] = execute_query(sql_estrutura_lib)

    # 12. Vinculo solicitacao -> pedido -> nota
    print("12. Analisando fluxo solicitacao->pedido->nota...")
    sql_fluxo = """
        SELECT * FROM (
            SELECT
                SOL.NUNOTA AS NUNOTA_SOLIC,
                SOL.CODTIPOPER AS TOP_SOLIC,
                SOL.VLRNOTA AS VLR_SOLIC,
                PED.NUNOTA AS NUNOTA_PED,
                PED.CODTIPOPER AS TOP_PED,
                NOTA.NUNOTA AS NUNOTA_COMPRA,
                NOTA.CODTIPOPER AS TOP_COMPRA,
                NOTA.VLRNOTA AS VLR_COMPRA
            FROM TGFCAB SOL
            LEFT JOIN TGFCAB PED ON SOL.NUNOTA = PED.NUNOTAORIG
            LEFT JOIN TGFCAB NOTA ON PED.NUNOTA = NOTA.NUNOTAORIG
            WHERE SOL.CODTIPOPER = 1804
            ORDER BY SOL.NUNOTA DESC
        ) WHERE ROWNUM <= 20
    """
    resultado["fluxo_solic_ped_nota"] = execute_query(sql_fluxo)

    # 13. Campos NUNOTAORIG em TGFCAB
    print("13. Analisando uso de NUNOTAORIG...")
    sql_nunotaorig = """
        SELECT CODTIPOPER, TIPMOV, COUNT(*) AS QTD,
               COUNT(NUNOTAORIG) AS COM_ORIGEM
        FROM TGFCAB
        WHERE TIPMOV IN ('C', 'O', 'J')
        GROUP BY CODTIPOPER, TIPMOV
        ORDER BY QTD DESC
    """
    resultado["uso_nunotaorig"] = execute_query(sql_nunotaorig)

    # 14. Contagem por status para pedidos compra (TOP 1301)
    print("14. Status dos pedidos de compra...")
    sql_status_ped = """
        SELECT STATUSNOTA, PENDESSION, COUNT(*) AS QTD
        FROM TGFCAB
        WHERE CODTIPOPER = 1301
        GROUP BY STATUSNOTA, PENDESSION
        ORDER BY QTD DESC
    """
    resultado["status_pedidos_compra"] = execute_query(sql_status_ped)

    # 15. Campos de pendencia em TGFCAB
    print("15. Analisando campos de pendencia...")
    sql_pendencia = """
        SELECT COLUMN_NAME, DATA_TYPE
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = 'TGFCAB'
          AND COLUMN_NAME LIKE 'PEND%'
        ORDER BY COLUMN_NAME
    """
    resultado["campos_pendencia"] = execute_query(sql_pendencia)

    # 16. Valores de PENDESSION
    print("16. Valores de PENDESSION...")
    sql_pendession = """
        SELECT PENDESSION, COUNT(*) AS QTD
        FROM TGFCAB
        WHERE TIPMOV IN ('C', 'O', 'J')
        GROUP BY PENDESSION
        ORDER BY QTD DESC
    """
    resultado["valores_pendession"] = execute_query(sql_pendession)

    # 17. Estrutura TGFVAR (Variáveis/Itens adicionais)
    print("17. Buscando movimentacao estoque por compra...")
    sql_mov_est = """
        SELECT * FROM (
            SELECT I.NUNOTA, I.CODPROD, I.QTDNEG,
                   C.CODTIPOPER, T.ATUALEST
            FROM TGFITE I
            JOIN TGFCAB C ON I.NUNOTA = C.NUNOTA
            JOIN TGFTOP T ON C.CODTIPOPER = T.CODTIPOPER AND C.DHTIPOPER = T.DHALTER
            WHERE C.TIPMOV = 'C' AND T.ATUALEST = 'E'
            ORDER BY I.NUNOTA DESC
        ) WHERE ROWNUM <= 20
    """
    resultado["mov_estoque_compra"] = execute_query(sql_mov_est)

    # 18. Contagem TGFEST
    print("18. Contagem registros TGFEST...")
    sql_count_est = "SELECT COUNT(*) AS TOTAL FROM TGFEST"
    resultado["contagem_tgfest"] = execute_query(sql_count_est)

    # 19. Contagem TGFFIN
    print("19. Contagem registros TGFFIN...")
    sql_count_fin = "SELECT COUNT(*) AS TOTAL FROM TGFFIN"
    resultado["contagem_tgffin"] = execute_query(sql_count_fin)

    # 20. TGFFIN por tipo (receber/pagar)
    print("20. TGFFIN por tipo...")
    sql_fin_tipo = """
        SELECT RECDESP,
               CASE RECDESP WHEN 1 THEN 'RECEBER' WHEN -1 THEN 'PAGAR' ELSE 'OUTROS' END AS TIPO,
               COUNT(*) AS QTD,
               SUM(VLRDESDOB) AS VLR_TOTAL
        FROM TGFFIN
        GROUP BY RECDESP
        ORDER BY QTD DESC
    """
    resultado["tgffin_por_tipo"] = execute_query(sql_fin_tipo)

    # Salvar
    output_file = Path(__file__).parent / "compras_flow_data.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"\nDados salvos em: {output_file}")

    # Mostrar resumo
    print("\n=== RESUMO ===")

    if "contagem_tgfest" in resultado and "responseBody" in resultado["contagem_tgfest"]:
        rows = resultado["contagem_tgfest"]["responseBody"].get("rows", [])
        if rows:
            print(f"TGFEST (Estoque): {rows[0][0]} registros")

    if "contagem_tgffin" in resultado and "responseBody" in resultado["contagem_tgffin"]:
        rows = resultado["contagem_tgffin"]["responseBody"].get("rows", [])
        if rows:
            print(f"TGFFIN (Financeiro): {rows[0][0]} registros")

    if "tgffin_por_tipo" in resultado and "responseBody" in resultado["tgffin_por_tipo"]:
        rows = resultado["tgffin_por_tipo"]["responseBody"].get("rows", [])
        print(f"\nTGFFIN por tipo:")
        for row in rows:
            print(f"  {row[1]}: {row[2]} titulos, R$ {row[3]:,.2f}")


if __name__ == "__main__":
    main()
