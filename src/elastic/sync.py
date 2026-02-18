"""
MMarra Data Hub - Elasticsearch Sync
Sincroniza dados do Sankhya (via API REST) para Elasticsearch.

Estrategia:
- Full sync: Carrega TUDO na primeira vez e semanalmente
- Incremental sync: Carrega apenas alterados (DTALTER > ultima_sync)
- Roda no startup (se indice vazio) e no daily_training (incremental)
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path

import httpx

ELASTIC_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")
ELASTIC_TIMEOUT = int(os.getenv("ELASTIC_TIMEOUT", "30"))
SYNC_BATCH_SIZE = 500  # Max rows por query no Sankhya (ROWNUM <= 500)

SYNC_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "elastic_sync_state.json"


class ElasticSync:
    """Sincroniza Sankhya -> Elasticsearch."""

    def __init__(self, executor):
        self.executor = executor
        self._state = self._load_state()

    # ============================================================
    # STATE MANAGEMENT
    # ============================================================

    def _load_state(self) -> dict:
        if SYNC_STATE_FILE.exists():
            try:
                return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"last_full_sync": None, "last_products_sync": None, "last_partners_sync": None}

    def _save_state(self):
        SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        SYNC_STATE_FILE.write_text(json.dumps(self._state, indent=2, ensure_ascii=False), encoding="utf-8")

    # ============================================================
    # ELASTICSEARCH HELPERS
    # ============================================================

    async def _es_request(self, method: str, path: str, body: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=ELASTIC_TIMEOUT) as client:
            url = f"{ELASTIC_URL}/{path}"
            if method == "GET":
                r = await client.get(url)
            elif method == "PUT":
                r = await client.put(url, json=body, headers={"Content-Type": "application/json"})
            elif method == "POST":
                r = await client.post(url, json=body, headers={"Content-Type": "application/json"})
            elif method == "DELETE":
                r = await client.delete(url)
            elif method == "HEAD":
                r = await client.head(url)
                return {"status": r.status_code}
            else:
                raise ValueError(f"Method {method} nao suportado")

            if r.status_code >= 400:
                return {"error": r.text, "status": r.status_code}
            return r.json() if r.text else {"status": r.status_code}

    async def _bulk_index(self, index: str, docs: list) -> dict:
        if not docs:
            return {"indexed": 0, "errors": 0}

        lines = []
        for doc in docs:
            doc_id = doc.pop("_id", None)
            lines.append(json.dumps({"index": {"_index": index, "_id": str(doc_id)}}))
            lines.append(json.dumps(doc, ensure_ascii=False, default=str))

        body = "\n".join(lines) + "\n"

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{ELASTIC_URL}/_bulk",
                content=body,
                headers={"Content-Type": "application/x-ndjson"}
            )
            result = r.json()
            errors = sum(1 for item in result.get("items", []) if item.get("index", {}).get("error"))
            return {"indexed": len(docs) - errors, "errors": errors}

    async def _create_index_if_not_exists(self, index: str, mapping: dict) -> bool:
        check = await self._es_request("HEAD", index)
        if check.get("status") == 200:
            print(f"[ELASTIC] Indice {index} ja existe")
            return False
        result = await self._es_request("PUT", index, mapping)
        if result.get("acknowledged"):
            print(f"[ELASTIC] Indice {index} criado")
            return True
        else:
            print(f"[ELASTIC] Erro ao criar {index}: {result}")
            return False

    async def _count_docs(self, index: str) -> int:
        result = await self._es_request("GET", f"{index}/_count")
        return result.get("count", 0)

    # ============================================================
    # SYNC PRODUTOS
    # ============================================================

    async def sync_products(self, full: bool = False) -> dict:
        from src.elastic.mappings import PRODUCTS_MAPPING, PRODUCTS_INDEX
        await self._create_index_if_not_exists(PRODUCTS_INDEX, PRODUCTS_MAPPING)

        # Montar WHERE
        where = "PRO.ATIVO = 'S'"
        if not full and self._state.get("last_products_sync"):
            last = self._state["last_products_sync"]
            where += f" AND PRO.DTALTER >= TO_DATE('{last}', 'YYYY-MM-DD HH24:MI:SS')"

        # Contar total
        sql_count = f"SELECT COUNT(*) AS TOTAL FROM TGFPRO PRO WHERE {where}"
        count_result = await self.executor.execute(sql_count)
        total = 0
        if count_result.get("success") and count_result.get("data"):
            row = count_result["data"][0]
            total = int(row.get("TOTAL", 0) or 0) if isinstance(row, dict) else int(row[0] or 0)

        if total == 0:
            print(f"[ELASTIC] Produtos: nenhum novo/alterado")
            return {"indexed": 0, "errors": 0, "total": 0}

        mode = "full" if full else "incremental"
        print(f"[ELASTIC] Produtos: sincronizando {total} ({mode})...")

        # Paginar via ROWNUM ranges (Oracle)
        indexed_total = 0
        errors_total = 0
        last_codprod = 0

        while True:
            sql = f"""SELECT PRO.CODPROD, PRO.DESCRPROD,
                NVL(MAR.DESCRICAO, '') AS MARCA,
                NVL(MAR.CODIGO, 0) AS MARCA_CODIGO,
                NVL(PRO.CARACTERISTICAS, '') AS APLICACAO,
                NVL(PRO.COMPLDESC, '') AS COMPLEMENTO,
                NVL(PRO.REFERENCIA, '') AS REFERENCIA,
                NVL(PRO.AD_NUMFABRICANTE, '') AS NUM_FABRICANTE,
                NVL(PRO.AD_NUMFABRICANTE2, '') AS NUM_FABRICANTE2,
                NVL(PRO.AD_NUMORIGINAL, '') AS NUM_ORIGINAL,
                NVL(PRO.REFFORN, '') AS REF_FORNECEDOR,
                NVL(PRO.NCM, '') AS NCM,
                NVL(PRO.CODVOL, '') AS UNIDADE
            FROM TGFPRO PRO
            LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
            WHERE {where} AND PRO.CODPROD > {last_codprod}
            ORDER BY PRO.CODPROD"""

            result = await self.executor.execute(sql)
            if not result.get("success") or not result.get("data"):
                if not result.get("success"):
                    print(f"[ELASTIC] Erro SQL produtos: {result.get('error', '?')}")
                break

            data = result["data"]
            if not data:
                break

            # Converter lista -> dict se necessario (Sankhya retorna listas)
            PRODUCT_COLS = ["CODPROD", "DESCRPROD", "MARCA", "MARCA_CODIGO",
                            "APLICACAO", "COMPLEMENTO", "REFERENCIA",
                            "NUM_FABRICANTE", "NUM_FABRICANTE2", "NUM_ORIGINAL",
                            "REF_FORNECEDOR", "NCM", "UNIDADE"]
            if data and isinstance(data[0], (list, tuple)):
                cols = result.get("columns") or PRODUCT_COLS
                data = [dict(zip(cols, row)) for row in data]

            docs = []
            for row in data:
                codprod = int(row.get("CODPROD", 0) or 0)
                last_codprod = codprod
                ref = str(row.get("REFERENCIA", "") or "")
                nf = str(row.get("NUM_FABRICANTE", "") or "")
                nf2 = str(row.get("NUM_FABRICANTE2", "") or "")
                no = str(row.get("NUM_ORIGINAL", "") or "")
                rf = str(row.get("REF_FORNECEDOR", "") or "")
                descr = str(row.get("DESCRPROD", "") or "")
                aplic = str(row.get("APLICACAO", "") or "")
                compl = str(row.get("COMPLEMENTO", "") or "")

                docs.append({
                    "_id": codprod,
                    "codprod": codprod,
                    "descricao": descr,
                    "marca": str(row.get("MARCA", "") or ""),
                    "marca_codigo": int(row.get("MARCA_CODIGO", 0) or 0),
                    "aplicacao": aplic,
                    "complemento": compl,
                    "referencia": ref,
                    "num_fabricante": nf,
                    "num_fabricante2": nf2,
                    "num_original": no,
                    "ref_fornecedor": rf,
                    "ncm": str(row.get("NCM", "") or ""),
                    "unidade": str(row.get("UNIDADE", "") or ""),
                    "ativo": True,
                    "updated_at": datetime.now().isoformat(),
                    "all_codes": f"{ref} {nf} {nf2} {no} {rf}".strip(),
                    "full_text": f"{descr} {aplic} {compl}".strip(),
                })

            bulk = await self._bulk_index(PRODUCTS_INDEX, docs)
            indexed_total += bulk.get("indexed", 0)
            errors_total += bulk.get("errors", 0)

            batch_num = (indexed_total // SYNC_BATCH_SIZE) + 1
            print(f"[ELASTIC] Produtos: batch {batch_num} — {indexed_total}/{total} (last_codprod={last_codprod})")

            if len(data) < SYNC_BATCH_SIZE:
                break

        # Atualizar state
        self._state["last_products_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if full:
            self._state["last_full_sync"] = self._state["last_products_sync"]
        self._save_state()

        count = await self._count_docs(PRODUCTS_INDEX)
        print(f"[ELASTIC] Produtos: {indexed_total} indexados, {errors_total} erros. Total no indice: {count}")
        return {"indexed": indexed_total, "errors": errors_total, "total_in_index": count}

    # ============================================================
    # SYNC PARCEIROS
    # ============================================================

    async def sync_partners(self, full: bool = False) -> dict:
        from src.elastic.mappings import PARTNERS_MAPPING, PARTNERS_INDEX
        await self._create_index_if_not_exists(PARTNERS_INDEX, PARTNERS_MAPPING)

        where = "PAR.ATIVO = 'S'"
        if not full and self._state.get("last_partners_sync"):
            last = self._state["last_partners_sync"]
            where += f" AND PAR.DTALTER >= TO_DATE('{last}', 'YYYY-MM-DD HH24:MI:SS')"

        sql_count = f"SELECT COUNT(*) AS TOTAL FROM TGFPAR PAR WHERE {where}"
        count_result = await self.executor.execute(sql_count)
        total = 0
        if count_result.get("success") and count_result.get("data"):
            row = count_result["data"][0]
            total = int(row.get("TOTAL", 0) or 0) if isinstance(row, dict) else int(row[0] or 0)

        if total == 0:
            print(f"[ELASTIC] Parceiros: nenhum novo/alterado")
            return {"indexed": 0, "errors": 0, "total": 0}

        mode = "full" if full else "incremental"
        print(f"[ELASTIC] Parceiros: sincronizando {total} ({mode})...")

        indexed_total = 0
        errors_total = 0
        last_codparc = 0

        while True:
            sql = f"""SELECT
                PAR.CODPARC,
                PAR.NOMEPARC AS NOME,
                NVL(PAR.RAZAOSOCIAL, '') AS FANTASIA,
                NVL(PAR.CGC_CPF, '') AS CNPJ_CPF,
                CASE
                    WHEN PAR.CLIENTE = 'S' AND PAR.FORNECEDOR = 'S' THEN 'A'
                    WHEN PAR.FORNECEDOR = 'S' THEN 'F'
                    ELSE 'C'
                END AS TIPO,
                NVL(CID.NOMECID, '') AS CIDADE,
                NVL(UFS.UF, '') AS UF,
                NVL(BAI.NOMEBAI, '') AS BAIRRO,
                NVL(PAR.TELEFONE, '') AS TELEFONE,
                NVL(PAR.EMAIL, '') AS EMAIL,
                NVL(VEN.APELIDO, '') AS VENDEDOR
            FROM TGFPAR PAR
            LEFT JOIN TSICID CID ON CID.CODCID = PAR.CODCID
            LEFT JOIN TSIUFS UFS ON UFS.CODUF = CID.UF
            LEFT JOIN TSIBAI BAI ON BAI.CODBAI = PAR.CODBAI
            LEFT JOIN TGFVEN VEN ON VEN.CODVEND = PAR.CODVEND
            WHERE {where} AND PAR.CODPARC > {last_codparc}
            ORDER BY PAR.CODPARC"""

            result = await self.executor.execute(sql)
            if not result.get("success") or not result.get("data"):
                if not result.get("success"):
                    print(f"[ELASTIC] Erro SQL parceiros: {result.get('error', '?')}")
                break

            data = result["data"]
            if not data:
                break

            # Converter lista -> dict se necessario (Sankhya retorna listas)
            PARTNER_COLS = ["CODPARC", "NOME", "FANTASIA", "CNPJ_CPF",
                            "TIPO", "CIDADE", "UF", "BAIRRO",
                            "TELEFONE", "EMAIL", "VENDEDOR"]
            if data and isinstance(data[0], (list, tuple)):
                cols = result.get("columns") or PARTNER_COLS
                data = [dict(zip(cols, row)) for row in data]

            docs = []
            for row in data:
                codparc = int(row.get("CODPARC", 0) or 0)
                last_codparc = codparc
                nome = str(row.get("NOME", "") or "")
                fantasia = str(row.get("FANTASIA", "") or "")
                cidade = str(row.get("CIDADE", "") or "")

                docs.append({
                    "_id": codparc,
                    "codparc": codparc,
                    "nome": nome,
                    "fantasia": fantasia,
                    "cnpj_cpf": str(row.get("CNPJ_CPF", "") or ""),
                    "tipo": str(row.get("TIPO", "C") or "C"),
                    "cidade": cidade,
                    "uf": str(row.get("UF", "") or ""),
                    "bairro": str(row.get("BAIRRO", "") or ""),
                    "telefone": str(row.get("TELEFONE", "") or ""),
                    "email": str(row.get("EMAIL", "") or ""),
                    "vendedor": str(row.get("VENDEDOR", "") or ""),
                    "ativo": True,
                    "updated_at": datetime.now().isoformat(),
                    "full_text": f"{nome} {fantasia} {cidade}".strip(),
                })

            bulk = await self._bulk_index(PARTNERS_INDEX, docs)
            indexed_total += bulk.get("indexed", 0)
            errors_total += bulk.get("errors", 0)

            batch_num = (indexed_total // SYNC_BATCH_SIZE) + 1
            print(f"[ELASTIC] Parceiros: batch {batch_num} — {indexed_total}/{total} (last_codparc={last_codparc})")

            if len(data) < SYNC_BATCH_SIZE:
                break

        self._state["last_partners_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_state()

        count = await self._count_docs(PARTNERS_INDEX)
        print(f"[ELASTIC] Parceiros: {indexed_total} indexados, {errors_total} erros. Total: {count}")
        return {"indexed": indexed_total, "errors": errors_total, "total_in_index": count}

    # ============================================================
    # FULL / INCREMENTAL
    # ============================================================

    async def full_sync(self) -> dict:
        print(f"[ELASTIC] === FULL SYNC INICIANDO ===")
        t0 = datetime.now()
        products = await self.sync_products(full=True)
        partners = await self.sync_partners(full=True)
        elapsed = (datetime.now() - t0).total_seconds()
        print(f"[ELASTIC] === FULL SYNC COMPLETO em {elapsed:.0f}s ===")
        return {"products": products, "partners": partners, "elapsed_seconds": elapsed}

    async def incremental_sync(self) -> dict:
        products = await self.sync_products(full=False)
        partners = await self.sync_partners(full=False)
        return {"products": products, "partners": partners}