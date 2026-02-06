"""
Script para investigar regras de negocio da MMarra.
Extrai dados reais para entender como o sistema funciona na pratica.
"""

import os
import json
import time
import asyncio
import warnings
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

warnings.filterwarnings('ignore')

try:
    import httpx
except ImportError:
    os.system("pip install httpx")
    import httpx

project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env")

SANKHYA_BASE_URL = "https://api.sankhya.com.br"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_X_TOKEN", "")


class SankhyaClient:
    def __init__(self):
        self.base_url = SANKHYA_BASE_URL
        self.client_id = SANKHYA_CLIENT_ID
        self.client_secret = SANKHYA_CLIENT_SECRET
        self.x_token = SANKHYA_X_TOKEN
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    async def _authenticate(self) -> str:
        if self._access_token and time.time() < (self._token_expires_at - 30):
            return self._access_token
        url = f"{self.base_url}/authenticate"
        headers = {"X-Token": self.x_token, "Content-Type": "application/x-www-form-urlencoded"}
        data = {"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"}
        async with httpx.AsyncClient(timeout=30.0, verify=False) as client:
            response = await client.post(url, headers=headers, data=data)
            if response.status_code != 200:
                raise Exception(f"Falha auth: {response.status_code}")
            result = response.json()
            self._access_token = result["access_token"]
            self._token_expires_at = time.time() + result.get("expires_in", 300)
            return self._access_token

    async def query(self, sql: str) -> dict:
        if not sql.strip().upper().startswith("SELECT"):
            return {"error": "Apenas SELECT"}
        try:
            token = await self._authenticate()
        except Exception as e:
            return {"error": str(e)}
        url = f"{self.base_url}/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"serviceName": "DbExplorerSP.executeQuery", "requestBody": {"sql": sql}}
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 401:
                self._access_token = None
                return await self.query(sql)
            if response.status_code != 200:
                return {"error": f"HTTP {response.status_code}"}
            data = response.json()
            if data.get("status") == "0":
                return {"error": data.get("statusMessage", "Erro")}
            return data


sankhya = SankhyaClient()


def get_rows(result):
    """Extrai rows do resultado."""
    return result.get("responseBody", {}).get("rows", [])


async def investigar_aprovacao():
    """Investiga como funciona aprovacao na pratica."""
    print("\n" + "="*70)
    print("INVESTIGANDO: APROVACAO DE COMPRAS")
    print("="*70)

    resultado = {}

    # 1. Verificar notas pendentes (STATUSNOTA = 'P')
    print("\n1. Notas pendentes (STATUSNOTA='P'):")
    sql = """
        SELECT
            TIPMOV,
            COUNT(*) as qtd,
            SUM(VLRNOTA) as valor
        FROM TGFCAB
        WHERE STATUSNOTA = 'P'
        GROUP BY TIPMOV
        ORDER BY qtd DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["notas_pendentes_por_tipmov"] = rows
    for row in rows:
        print(f"  TIPMOV={row[0]}: {row[1]:,} notas, R$ {float(row[2] or 0):,.2f}")

    # 2. Verificar campos PENDENTE e APROVADO
    print("\n2. Campos PENDENTE e APROVADO em TGFCAB:")
    sql = """
        SELECT
            PENDENTE,
            APROVADO,
            COUNT(*) as qtd
        FROM TGFCAB
        WHERE PENDENTE IS NOT NULL OR APROVADO IS NOT NULL
        GROUP BY PENDENTE, APROVADO
        ORDER BY qtd DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["pendente_aprovado"] = rows
    for row in rows:
        print(f"  PENDENTE={row[0]}, APROVADO={row[1]}: {row[2]:,}")

    # 3. Verificar se existe algum registro em tabelas de aprovacao
    print("\n3. Tabelas de aprovacao:")
    tabelas = ["TGFLIB", "AD_APROVACAO", "AD_LIBERACOESVENDA"]
    for tab in tabelas:
        sql = f"SELECT COUNT(*) FROM {tab}"
        r = await sankhya.query(sql)
        rows = get_rows(r)
        total = rows[0][0] if rows else 0
        print(f"  {tab}: {total:,} registros")
        resultado[f"count_{tab}"] = total

    # 4. Verificar transicao de status (notas que mudaram de P para L)
    print("\n4. Notas de compra com STATUSNOTA='L' recentes:")
    sql = """
        SELECT * FROM (
            SELECT
                NUNOTA,
                NUMNOTA,
                CODTIPOPER,
                STATUSNOTA,
                PENDENTE,
                APROVADO,
                DTNEG,
                VLRNOTA
            FROM TGFCAB
            WHERE TIPMOV = 'C'
              AND STATUSNOTA = 'L'
            ORDER BY DTNEG DESC
        ) WHERE ROWNUM <= 10
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["notas_compra_liberadas"] = rows
    print("  NUNOTA    NUMNOTA  TOP   STATUS PEND APROV  VLRNOTA")
    for row in rows:
        print(f"  {row[0]:<9} {row[1]:<8} {row[2]:<5} {row[3]:<6} {row[4] or '-':<4} {row[5] or '-':<5} R$ {float(row[7] or 0):,.2f}")

    # 5. Verificar eventos/alerta de limite
    print("\n5. Verificando TGFALL (alertas/limites):")
    sql = "SELECT COUNT(*) FROM TGFALL"
    r = await sankhya.query(sql)
    rows = get_rows(r)
    total = rows[0][0] if rows else 0
    print(f"  TGFALL: {total:,} registros")
    resultado["count_TGFALL"] = total

    if total > 0:
        sql = """
            SELECT * FROM (
                SELECT EVENTO, TABELA, COUNT(*) as qtd
                FROM TGFALL
                GROUP BY EVENTO, TABELA
                ORDER BY qtd DESC
            ) WHERE ROWNUM <= 10
        """
        r = await sankhya.query(sql)
        rows = get_rows(r)
        resultado["tgfall_eventos"] = rows
        for row in rows:
            print(f"    EVENTO={row[0]}, TABELA={row[1]}: {row[2]:,}")

    return resultado


async def investigar_solicitacao():
    """Investiga solicitacao de compra."""
    print("\n" + "="*70)
    print("INVESTIGANDO: SOLICITACAO DE COMPRA")
    print("="*70)

    resultado = {}

    # 1. Solicitacoes por status
    print("\n1. Solicitacoes (TIPMOV='J') por STATUSNOTA:")
    sql = """
        SELECT
            STATUSNOTA,
            COUNT(*) as qtd,
            SUM(VLRNOTA) as valor
        FROM TGFCAB
        WHERE TIPMOV = 'J'
        GROUP BY STATUSNOTA
        ORDER BY qtd DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["por_status"] = rows
    for row in rows:
        status = row[0] or 'NULL'
        print(f"  STATUSNOTA={status}: {row[1]:,} notas, R$ {float(row[2] or 0):,.2f}")

    # 2. Solicitacoes por periodo
    print("\n2. Solicitacoes por ano:")
    sql = """
        SELECT
            TO_CHAR(DTNEG, 'YYYY') as ano,
            COUNT(*) as qtd,
            SUM(VLRNOTA) as valor
        FROM TGFCAB
        WHERE TIPMOV = 'J'
          AND DTNEG IS NOT NULL
        GROUP BY TO_CHAR(DTNEG, 'YYYY')
        ORDER BY ano DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["por_ano"] = rows
    for row in rows[:5]:
        print(f"  {row[0]}: {row[1]:,} notas, R$ {float(row[2] or 0):,.2f}")

    # 3. Solicitacoes por empresa
    print("\n3. Solicitacoes por empresa:")
    sql = """
        SELECT
            c.CODEMP,
            e.RAZAOSOCIAL,
            COUNT(*) as qtd
        FROM TGFCAB c
        JOIN TSIEMP e ON c.CODEMP = e.CODEMP
        WHERE c.TIPMOV = 'J'
        GROUP BY c.CODEMP, e.RAZAOSOCIAL
        ORDER BY qtd DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["por_empresa"] = rows
    for row in rows[:5]:
        print(f"  Emp {row[0]}: {row[2]:,} ({row[1][:30]})")

    # 4. Vinculo solicitacao -> pedido -> compra
    print("\n4. Verificando vinculo entre solicitacao e pedido:")
    sql = """
        SELECT
            c.TIPMOV,
            c.CODTIPOPER,
            c.NUNOTAORIG,
            COUNT(*) as qtd
        FROM TGFCAB c
        WHERE c.TIPMOV IN ('O', 'C')
          AND c.NUNOTAORIG IS NOT NULL
        GROUP BY c.TIPMOV, c.CODTIPOPER, c.NUNOTAORIG
        ORDER BY qtd DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    if rows:
        print(f"  {len(rows)} combinacoes com NUNOTAORIG preenchido")
    else:
        print("  Nenhum vinculo via NUNOTAORIG encontrado")

    # 5. Exemplo de solicitacao
    print("\n5. Exemplo de solicitacao recente:")
    sql = """
        SELECT * FROM (
            SELECT
                c.NUNOTA,
                c.NUMNOTA,
                c.DTNEG,
                c.STATUSNOTA,
                c.VLRNOTA,
                c.CODPARC,
                p.NOMEPARC
            FROM TGFCAB c
            LEFT JOIN TGFPAR p ON c.CODPARC = p.CODPARC
            WHERE c.TIPMOV = 'J'
            ORDER BY c.DTNEG DESC
        ) WHERE ROWNUM <= 3
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["exemplo_solicitacao"] = rows
    for row in rows:
        print(f"  NUNOTA={row[0]}, NUM={row[1]}, DATA={row[2]}, STATUS={row[3]}, VLR=R${float(row[4] or 0):,.2f}")

    return resultado


async def investigar_cotacao():
    """Investiga cotacao de compra."""
    print("\n" + "="*70)
    print("INVESTIGANDO: COTACAO DE COMPRA")
    print("="*70)

    resultado = {}

    # 1. Cotacoes por situacao
    print("\n1. Cotacoes por SITUACAO:")
    sql = """
        SELECT
            SITUACAO,
            COUNT(*) as qtd
        FROM TGFCOT
        GROUP BY SITUACAO
        ORDER BY qtd DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["por_situacao"] = rows
    for row in rows:
        sit = row[0] or 'NULL'
        print(f"  SITUACAO={sit}: {row[1]:,}")

    # 2. Cotacoes por ano
    print("\n2. Cotacoes por ano:")
    sql = """
        SELECT
            TO_CHAR(DHINIC, 'YYYY') as ano,
            COUNT(*) as qtd
        FROM TGFCOT
        WHERE DHINIC IS NOT NULL
        GROUP BY TO_CHAR(DHINIC, 'YYYY')
        ORDER BY ano DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["por_ano"] = rows
    for row in rows[:5]:
        print(f"  {row[0]}: {row[1]:,} cotacoes")

    # 3. Verificar se NUNOTAORIG esta preenchido
    print("\n3. Cotacoes com NUNOTAORIG (vinculo com solicitacao):")
    sql = """
        SELECT
            CASE WHEN NUNOTAORIG IS NULL THEN 'Sem origem' ELSE 'Com origem' END as status,
            COUNT(*) as qtd
        FROM TGFCOT
        GROUP BY CASE WHEN NUNOTAORIG IS NULL THEN 'Sem origem' ELSE 'Com origem' END
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["vinculo_solicitacao"] = rows
    for row in rows:
        print(f"  {row[0]}: {row[1]:,}")

    # 4. Exemplo de cotacao com detalhes
    print("\n4. Exemplo de cotacao:")
    sql = """
        SELECT * FROM (
            SELECT
                NUMCOTACAO,
                DHINIC,
                DHFINAL,
                SITUACAO,
                NUNOTAORIG,
                VALPROPOSTA,
                OBSERVACAO
            FROM TGFCOT
            WHERE DHINIC IS NOT NULL
            ORDER BY DHINIC DESC
        ) WHERE ROWNUM <= 3
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["exemplo_cotacao"] = rows
    for row in rows:
        print(f"  NUM={row[0]}, INICIO={row[1]}, SIT={row[3]}, VLR={row[5]}")

    # 5. Verificar pesos configurados
    print("\n5. Pesos de avaliacao configurados:")
    sql = """
        SELECT * FROM (
            SELECT
                NUMCOTACAO,
                PESOPRECO,
                PESOCONDPAG,
                PESOPRAZOENTREG,
                PESOQUALPROD,
                PESOCONFIABFORN
            FROM TGFCOT
            WHERE PESOPRECO IS NOT NULL
               OR PESOCONDPAG IS NOT NULL
            ORDER BY NUMCOTACAO DESC
        ) WHERE ROWNUM <= 5
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["pesos"] = rows
    if rows:
        for row in rows:
            print(f"  NUM={row[0]}: Preco={row[1]}, CondPag={row[2]}, Prazo={row[3]}, Qual={row[4]}")
    else:
        print("  Nenhuma cotacao com pesos configurados")

    return resultado


async def investigar_custos():
    """Investiga custos de produto."""
    print("\n" + "="*70)
    print("INVESTIGANDO: CUSTOS DE PRODUTO")
    print("="*70)

    resultado = {}

    # 1. Quantidade de registros por empresa
    print("\n1. Registros de custo por empresa:")
    sql = """
        SELECT
            c.CODEMP,
            e.RAZAOSOCIAL,
            COUNT(*) as qtd
        FROM AD_TGFCUSMMA c
        JOIN TSIEMP e ON c.CODEMP = e.CODEMP
        GROUP BY c.CODEMP, e.RAZAOSOCIAL
        ORDER BY qtd DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["por_empresa"] = rows
    for row in rows:
        print(f"  Emp {row[0]}: {row[2]:,} ({row[1][:30]})")

    # 2. Produtos com custo registrado
    print("\n2. Quantidade de produtos com custo:")
    sql = """
        SELECT COUNT(DISTINCT CODPROD) as qtd_produtos
        FROM AD_TGFCUSMMA
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["produtos_com_custo"] = rows[0][0] if rows else 0
    print(f"  {resultado['produtos_com_custo']:,} produtos distintos")

    # 3. Periodo dos registros
    print("\n3. Periodo dos registros:")
    sql = """
        SELECT
            MIN(DTATUAL) as data_min,
            MAX(DTATUAL) as data_max
        FROM AD_TGFCUSMMA
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["periodo"] = rows
    if rows:
        print(f"  De {rows[0][0]} ate {rows[0][1]}")

    # 4. Exemplo de historico de custo
    print("\n4. Exemplo de historico de custo (produto com mais registros):")
    sql = """
        SELECT * FROM (
            SELECT
                CODPROD,
                COUNT(*) as qtd
            FROM AD_TGFCUSMMA
            GROUP BY CODPROD
            ORDER BY qtd DESC
        ) WHERE ROWNUM = 1
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    if rows:
        codprod = rows[0][0]
        print(f"  Produto {codprod} tem {rows[0][1]:,} registros de custo")

        sql = f"""
            SELECT * FROM (
                SELECT
                    DTATUAL,
                    CUSCOMICM,
                    CUSSEMICM,
                    CUSREP
                FROM AD_TGFCUSMMA
                WHERE CODPROD = {codprod}
                  AND CODEMP = 1
                ORDER BY DTATUAL DESC
            ) WHERE ROWNUM <= 5
        """
        r = await sankhya.query(sql)
        rows2 = get_rows(r)
        resultado["exemplo_historico"] = rows2
        for row in rows2:
            print(f"    {row[0]}: ComICM={row[1]}, SemICM={row[2]}, Rep={row[3]}")

    # 5. Diferenca entre TGFCUS (padrao) e AD_TGFCUSMMA
    print("\n5. Comparacao TGFCUS vs AD_TGFCUSMMA:")
    sql = "SELECT COUNT(*) FROM TGFCUS"
    r = await sankhya.query(sql)
    rows = get_rows(r)
    tgfcus = rows[0][0] if rows else 0
    print(f"  TGFCUS (padrao): {tgfcus:,} registros")
    print(f"  AD_TGFCUSMMA (customizada): 709.230 registros")

    return resultado


async def investigar_codigos_auxiliares():
    """Investiga codigos auxiliares de produto."""
    print("\n" + "="*70)
    print("INVESTIGANDO: CODIGOS AUXILIARES DE PRODUTO")
    print("="*70)

    resultado = {}

    # 1. Quantidade por produto
    print("\n1. Distribuicao de codigos por produto:")
    sql = """
        SELECT
            CASE
                WHEN cnt = 1 THEN '1 codigo'
                WHEN cnt BETWEEN 2 AND 5 THEN '2-5 codigos'
                WHEN cnt BETWEEN 6 AND 10 THEN '6-10 codigos'
                ELSE '10+ codigos'
            END as faixa,
            COUNT(*) as qtd_produtos
        FROM (
            SELECT CODPROD, COUNT(*) as cnt
            FROM AD_TGFPROAUXMMA
            GROUP BY CODPROD
        )
        GROUP BY CASE
            WHEN cnt = 1 THEN '1 codigo'
            WHEN cnt BETWEEN 2 AND 5 THEN '2-5 codigos'
            WHEN cnt BETWEEN 6 AND 10 THEN '6-10 codigos'
            ELSE '10+ codigos'
        END
        ORDER BY qtd_produtos DESC
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["distribuicao"] = rows
    for row in rows:
        print(f"  {row[0]}: {row[1]:,} produtos")

    # 2. Por marca
    print("\n2. Codigos por marca (top 10):")
    sql = """
        SELECT * FROM (
            SELECT
                a.CODIGO,
                m.DESCRICAO,
                COUNT(*) as qtd
            FROM AD_TGFPROAUXMMA a
            LEFT JOIN TGFMAR m ON a.CODIGO = m.CODIGO
            WHERE a.CODIGO IS NOT NULL
            GROUP BY a.CODIGO, m.DESCRICAO
            ORDER BY qtd DESC
        ) WHERE ROWNUM <= 10
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["por_marca"] = rows
    for row in rows:
        marca = row[1] or f"Codigo {row[0]}"
        print(f"  {marca[:30]}: {row[2]:,}")

    # 3. Exemplo de produto com varios codigos
    print("\n3. Exemplo de produto com varios codigos auxiliares:")
    sql = """
        SELECT * FROM (
            SELECT CODPROD, COUNT(*) as qtd
            FROM AD_TGFPROAUXMMA
            GROUP BY CODPROD
            ORDER BY qtd DESC
        ) WHERE ROWNUM = 1
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    if rows:
        codprod = rows[0][0]
        print(f"  Produto {codprod} tem {rows[0][1]:,} codigos auxiliares")

        sql = f"""
            SELECT * FROM (
                SELECT NUMAUX, OBSERVACAO, ORIGEM
                FROM AD_TGFPROAUXMMA
                WHERE CODPROD = {codprod}
            ) WHERE ROWNUM <= 5
        """
        r = await sankhya.query(sql)
        rows2 = get_rows(r)
        resultado["exemplo_produto"] = rows2
        for row in rows2:
            print(f"    {row[0][:30]} | {row[1] or '-'} | {row[2] or '-'}")

    # 4. Uso na pratica - busca por codigo
    print("\n4. Exemplo de busca por codigo auxiliar:")
    sql = """
        SELECT * FROM (
            SELECT
                a.NUMAUX,
                a.CODPROD,
                p.DESCRPROD,
                m.DESCRICAO as MARCA
            FROM AD_TGFPROAUXMMA a
            JOIN TGFPRO p ON a.CODPROD = p.CODPROD
            LEFT JOIN TGFMAR m ON a.CODIGO = m.CODIGO
            WHERE a.NUMAUX IS NOT NULL
        ) WHERE ROWNUM <= 3
    """
    r = await sankhya.query(sql)
    rows = get_rows(r)
    resultado["exemplo_busca"] = rows
    for row in rows:
        print(f"  Cod '{row[0][:20]}' -> Prod {row[1]}: {row[2][:30]}")

    return resultado


async def main():
    """Executa todas as investigacoes."""
    print("Investigando regras de negocio MMarra")
    print("="*70)

    resultados = {}

    resultados["aprovacao"] = await investigar_aprovacao()
    resultados["solicitacao"] = await investigar_solicitacao()
    resultados["cotacao"] = await investigar_cotacao()
    resultados["custos"] = await investigar_custos()
    resultados["codigos_auxiliares"] = await investigar_codigos_auxiliares()

    # Salvar
    output_path = Path(__file__).parent / "regras_negocio_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "="*70)
    print(f"[OK] Dados salvos em: {output_path}")
    print("="*70)

    return resultados


if __name__ == "__main__":
    asyncio.run(main())
