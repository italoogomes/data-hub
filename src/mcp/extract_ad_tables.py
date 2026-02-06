"""
Script para investigar tabelas AD_* customizadas da MMarra.
Tabelas AD_ sao customizacoes feitas pela empresa no Sankhya.
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
                raise Exception(f"Falha na autenticacao: {response.status_code}")
            result = response.json()
            self._access_token = result["access_token"]
            self._token_expires_at = time.time() + result.get("expires_in", 300)
            return self._access_token

    async def execute_query(self, sql: str) -> dict:
        if not sql.strip().upper().startswith("SELECT"):
            return {"error": "Apenas SELECT permitido"}

        try:
            token = await self._authenticate()
        except Exception as e:
            return {"error": str(e)}

        url = f"{self.base_url}/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload = {
            "serviceName": "DbExplorerSP.executeQuery",
            "requestBody": {"sql": sql}
        }

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 401:
                self._access_token = None
                return await self.execute_query(sql)
            if response.status_code != 200:
                return {"error": f"HTTP {response.status_code}"}
            data = response.json()
            if data.get("status") == "0":
                return {"error": data.get("statusMessage", "Erro API")}
            return data


sankhya = SankhyaClient()


async def listar_tabelas_ad():
    """Lista todas as tabelas AD_* do banco."""
    print("\n" + "="*70)
    print("LISTANDO TODAS AS TABELAS AD_* (CUSTOMIZACOES MMARRA)")
    print("="*70)

    sql = """
        SELECT TABLE_NAME
        FROM USER_TABLES
        WHERE TABLE_NAME LIKE 'AD_%'
        ORDER BY TABLE_NAME
    """
    result = await sankhya.execute_query(sql)

    tabelas = []
    if result.get("responseBody", {}).get("rows"):
        for row in result["responseBody"]["rows"]:
            tabelas.append(row[0])

    print(f"\nTotal de tabelas AD_*: {len(tabelas)}")
    print("\nTabelas encontradas:")
    for i, t in enumerate(tabelas, 1):
        print(f"  {i:3}. {t}")

    return tabelas


async def contar_registros(tabela: str) -> int:
    """Conta registros de uma tabela."""
    sql = f"SELECT COUNT(*) FROM {tabela}"
    result = await sankhya.execute_query(sql)
    if "error" in result:
        return -1
    rows = result.get("responseBody", {}).get("rows", [])
    return int(rows[0][0]) if rows else 0


async def descrever_tabela(tabela: str) -> dict:
    """Obtem estrutura de uma tabela."""
    sql = f"""
        SELECT
            c.COLUMN_NAME as campo,
            c.DATA_TYPE as tipo,
            c.DATA_LENGTH as tamanho,
            c.NULLABLE as permite_nulo,
            NVL(cc.COMMENTS, '') as comentario
        FROM USER_TAB_COLUMNS c
        LEFT JOIN USER_COL_COMMENTS cc
            ON c.TABLE_NAME = cc.TABLE_NAME
            AND c.COLUMN_NAME = cc.COLUMN_NAME
        WHERE c.TABLE_NAME = '{tabela}'
        ORDER BY c.COLUMN_ID
    """
    return await sankhya.execute_query(sql)


async def buscar_chaves(tabela: str) -> dict:
    """Obtem PKs e FKs."""
    sql = f"""
        SELECT
            CASE uc.CONSTRAINT_TYPE
                WHEN 'P' THEN 'PK'
                WHEN 'R' THEN 'FK'
            END as tipo,
            ucc.COLUMN_NAME as campo,
            r_uc.TABLE_NAME as tabela_ref,
            r_ucc.COLUMN_NAME as campo_ref
        FROM USER_CONSTRAINTS uc
        JOIN USER_CONS_COLUMNS ucc ON uc.CONSTRAINT_NAME = ucc.CONSTRAINT_NAME
        LEFT JOIN USER_CONSTRAINTS r_uc ON uc.R_CONSTRAINT_NAME = r_uc.CONSTRAINT_NAME
        LEFT JOIN USER_CONS_COLUMNS r_ucc ON r_uc.CONSTRAINT_NAME = r_ucc.CONSTRAINT_NAME
        WHERE uc.TABLE_NAME = '{tabela}'
          AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY tipo, campo
    """
    return await sankhya.execute_query(sql)


async def sample_dados(tabela: str, limite: int = 5) -> dict:
    """Amostra de dados."""
    sql = f"SELECT * FROM {tabela} WHERE ROWNUM <= {limite}"
    return await sankhya.execute_query(sql)


async def investigar_tabela(tabela: str, detalhe: bool = True):
    """Investiga uma tabela especifica."""
    print(f"\n{'='*70}")
    print(f"INVESTIGANDO: {tabela}")
    print("="*70)

    # Contar
    total = await contar_registros(tabela)
    if total == -1:
        print(f"[ERRO] Nao foi possivel acessar {tabela}")
        return None

    print(f"Total de registros: {total:,}")

    if total == 0:
        print("[VAZIA] Tabela sem registros")
        if not detalhe:
            return {"tabela": tabela, "total": 0, "status": "vazia"}

    # Estrutura
    estrutura = await descrever_tabela(tabela)
    campos = []
    if estrutura.get("responseBody", {}).get("rows"):
        print(f"\nEstrutura ({len(estrutura['responseBody']['rows'])} campos):")
        for row in estrutura["responseBody"]["rows"][:30]:
            campo = row[0]
            tipo = row[1]
            tamanho = row[2]
            nulo = row[3]
            comentario = row[4] if row[4] else ""
            campos.append({"campo": campo, "tipo": tipo, "tamanho": tamanho})
            if detalhe:
                print(f"  {campo:30} {tipo:15} {tamanho:>6} {nulo:2} {comentario[:40]}")

    # Chaves
    chaves = await buscar_chaves(tabela)
    pks = []
    fks = []
    if chaves.get("responseBody", {}).get("rows"):
        print("\nChaves:")
        for row in chaves["responseBody"]["rows"]:
            tipo = row[0]
            campo = row[1]
            tab_ref = row[2] or ""
            campo_ref = row[3] or ""
            if tipo == "PK":
                pks.append(campo)
                print(f"  PK: {campo}")
            else:
                fks.append({"campo": campo, "ref": f"{tab_ref}.{campo_ref}"})
                print(f"  FK: {campo} -> {tab_ref}.{campo_ref}")

    # Sample
    sample = None
    if total > 0 and detalhe:
        print("\nAmostra de dados:")
        sample = await sample_dados(tabela, 3)
        if sample.get("responseBody", {}).get("rows"):
            # Mostrar nomes das colunas
            cols = [f["name"] for f in sample["responseBody"]["fieldsMetadata"]]
            print(f"  Colunas: {', '.join(cols[:10])}...")
            for i, row in enumerate(sample["responseBody"]["rows"][:3], 1):
                valores = [str(v)[:20] if v else "NULL" for v in row[:5]]
                print(f"  Reg {i}: {' | '.join(valores)}...")

    return {
        "tabela": tabela,
        "total": total,
        "campos": campos,
        "pks": pks,
        "fks": fks,
        "estrutura": estrutura,
        "chaves": chaves,
        "sample": sample
    }


async def classificar_tabelas_ad(tabelas: list):
    """Classifica tabelas por quantidade de registros."""
    print("\n" + "="*70)
    print("CLASSIFICANDO TABELAS AD_* POR QUANTIDADE DE REGISTROS")
    print("="*70)

    contagens = []
    for i, tabela in enumerate(tabelas):
        total = await contar_registros(tabela)
        contagens.append((tabela, total))
        if (i + 1) % 20 == 0:
            print(f"  Processando... {i+1}/{len(tabelas)}")

    # Ordenar por quantidade
    contagens.sort(key=lambda x: x[1], reverse=True)

    # Separar por categoria
    com_dados = [(t, c) for t, c in contagens if c > 0]
    vazias = [(t, c) for t, c in contagens if c == 0]
    erro = [(t, c) for t, c in contagens if c == -1]

    print(f"\n--- TABELAS COM DADOS ({len(com_dados)}) ---")
    for tabela, total in com_dados[:50]:
        print(f"  {tabela:50} {total:>12,}")

    print(f"\n--- TABELAS VAZIAS ({len(vazias)}) ---")
    for tabela, total in vazias[:30]:
        print(f"  {tabela}")

    if erro:
        print(f"\n--- TABELAS COM ERRO ({len(erro)}) ---")
        for tabela, total in erro:
            print(f"  {tabela}")

    return {
        "com_dados": com_dados,
        "vazias": vazias,
        "erro": erro
    }


async def main():
    """Executa investigacao completa das tabelas AD_*."""
    print("Iniciando investigacao das tabelas AD_* (customizacoes MMarra)")
    print("="*70)

    resultados = {}

    # 1. Listar todas as tabelas AD_*
    tabelas = await listar_tabelas_ad()
    resultados["total_tabelas_ad"] = len(tabelas)
    resultados["lista_tabelas"] = tabelas

    # 2. Classificar por quantidade
    classificacao = await classificar_tabelas_ad(tabelas)
    resultados["classificacao"] = {
        "com_dados": len(classificacao["com_dados"]),
        "vazias": len(classificacao["vazias"]),
        "erro": len(classificacao["erro"]),
        "ranking": classificacao["com_dados"][:30]
    }

    # 3. Investigar tabelas especificas (as que ja apareceram)
    tabelas_prioritarias = [
        "AD_APROVACAO",
        "AD_LIBERACOESVENDA",
        "AD_COTACOESDEITENS",
        "AD_SOLICITACAOCOMPRA",
        "AD_SOLICITACAOADIANTAMENTO"
    ]

    print("\n" + "="*70)
    print("INVESTIGANDO TABELAS PRIORITARIAS")
    print("="*70)

    for tabela in tabelas_prioritarias:
        if tabela in tabelas:
            dados = await investigar_tabela(tabela, detalhe=True)
            resultados[tabela] = dados
        else:
            print(f"\n[NAO EXISTE] {tabela}")
            resultados[tabela] = {"existe": False}

    # 4. Investigar as top 10 com mais registros
    print("\n" + "="*70)
    print("INVESTIGANDO TOP 10 TABELAS AD_* COM MAIS REGISTROS")
    print("="*70)

    for tabela, total in classificacao["com_dados"][:10]:
        if tabela not in tabelas_prioritarias:
            dados = await investigar_tabela(tabela, detalhe=True)
            resultados[tabela] = dados

    # Salvar
    output_path = Path(__file__).parent / "ad_tables_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "="*70)
    print(f"[OK] Dados salvos em: {output_path}")
    print("="*70)

    # Resumo
    print("\n" + "="*70)
    print("RESUMO")
    print("="*70)
    print(f"Total tabelas AD_*: {len(tabelas)}")
    print(f"Com dados: {len(classificacao['com_dados'])}")
    print(f"Vazias: {len(classificacao['vazias'])}")
    print(f"\nTop 10 por volume:")
    for tabela, total in classificacao["com_dados"][:10]:
        print(f"  {tabela:50} {total:>12,}")

    return resultados


if __name__ == "__main__":
    asyncio.run(main())
