"""
MMarra Data Hub - Elasticsearch Search Engine
Busca fuzzy em produtos, clientes e fornecedores.
Toda comunicacao via HTTP REST com httpx (zero dependencia extra).
"""

import os
import re

import httpx

ELASTIC_URL = os.getenv("ELASTIC_URL", "http://localhost:9200")

from src.elastic.mappings import PRODUCTS_INDEX, PARTNERS_INDEX


class ElasticSearchEngine:
    """Motor de busca com Elasticsearch."""

    # ============================================================
    # BUSCA DE PRODUTOS
    # ============================================================

    async def search_products(self, text: str = None, codigo: str = None,
                               marca: str = None, aplicacao: str = None,
                               limit: int = 10) -> list:
        """
        Busca produtos no Elasticsearch.

        Args:
            text: busca geral na descricao/complemento/aplicacao
            codigo: codigo de fabricante, referencia, numero original
            marca: filtro por marca
            aplicacao: filtro por veiculo/aplicacao
            limit: maximo de resultados

        Returns:
            Lista de dicts com produtos rankeados por relevancia
        """
        must = []
        filter_clauses = [{"term": {"ativo": True}}]

        # Busca por codigo (exact + fuzzy nos campos de codigo)
        if codigo:
            clean_code = re.sub(r'[\s\-/\.]', '', codigo).upper()

            code_should = [
                # Match exato (boost alto)
                {"term": {"referencia.raw": {"value": codigo.upper(), "boost": 10}}},
                {"term": {"num_fabricante.raw": {"value": codigo.upper(), "boost": 10}}},
                {"term": {"num_original.raw": {"value": codigo.upper(), "boost": 10}}},
                {"term": {"ref_fornecedor.raw": {"value": codigo.upper(), "boost": 10}}},
                # Match limpo (sem espacos/tracos)
                {"match": {"all_codes": {"query": clean_code, "boost": 8}}},
                # Fuzzy (pega typos)
                {"fuzzy": {"all_codes": {"value": clean_code, "fuzziness": "AUTO", "boost": 5}}},
                # Match parcial
                {"wildcard": {"all_codes": {"value": f"*{clean_code}*", "boost": 3}}},
            ]
            must.append({"bool": {"should": code_should, "minimum_should_match": 1}})

        # Busca por texto (descricao, aplicacao, complemento)
        if text:
            must.append({
                "multi_match": {
                    "query": text,
                    "fields": [
                        "descricao^3",
                        "full_text^2",
                        "aplicacao^2",
                        "complemento",
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                }
            })

        # Filtro por marca (exact + fuzzy)
        if marca:
            filter_clauses.append({
                "bool": {
                    "should": [
                        {"match": {"marca": {"query": marca, "fuzziness": "AUTO"}}},
                        {"term": {"marca.raw": marca.upper()}},
                    ]
                }
            })

        # Filtro por aplicacao
        if aplicacao:
            must.append({
                "match": {
                    "aplicacao": {
                        "query": aplicacao,
                        "fuzziness": "AUTO",
                    }
                }
            })

        # Montar query
        query = {
            "size": limit,
            "query": {
                "bool": {
                    "must": must if must else [{"match_all": {}}],
                    "filter": filter_clauses,
                }
            },
            "_source": ["codprod", "descricao", "marca", "aplicacao", "referencia",
                         "num_fabricante", "num_original", "ref_fornecedor",
                         "num_fabricante2", "complemento", "unidade"],
            "highlight": {
                "fields": {
                    "descricao": {},
                    "aplicacao": {},
                    "all_codes": {},
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{ELASTIC_URL}/{PRODUCTS_INDEX}/_search",
                    json=query,
                    headers={"Content-Type": "application/json"}
                )

                if r.status_code != 200:
                    print(f"[ELASTIC] Erro busca produtos: {r.status_code} {r.text[:200]}")
                    return []

                result = r.json()
                hits = result.get("hits", {}).get("hits", [])

                products = []
                for hit in hits:
                    src = hit.get("_source", {})
                    src["_score"] = round(hit.get("_score", 0), 2)
                    src["_highlights"] = hit.get("highlight", {})
                    products.append(src)

                return products
        except Exception as e:
            print(f"[ELASTIC] Erro conexao busca produtos: {e}")
            return []

    # ============================================================
    # BUSCA DE PARCEIROS (Clientes/Fornecedores)
    # ============================================================

    async def search_partners(self, text: str = None, cnpj: str = None,
                               tipo: str = None, cidade: str = None,
                               vendedor: str = None, limit: int = 10) -> list:
        """
        Busca clientes/fornecedores no Elasticsearch.

        Args:
            text: busca geral (nome, fantasia, cidade)
            cnpj: busca por CNPJ/CPF
            tipo: "C" = clientes, "F" = fornecedores, None = todos
            cidade: filtro por cidade
            vendedor: filtro por vendedor responsavel
            limit: maximo de resultados
        """
        must = []
        filter_clauses = [{"term": {"ativo": True}}]

        if cnpj:
            clean_cnpj = re.sub(r'[^\d]', '', cnpj)
            must.append({"wildcard": {"cnpj_cpf": f"*{clean_cnpj}*"}})

        if text:
            must.append({
                "multi_match": {
                    "query": text,
                    "fields": ["nome^3", "fantasia^3", "full_text^2", "cidade"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                }
            })

        if tipo and tipo.upper() in ("C", "F"):
            filter_clauses.append({
                "bool": {
                    "should": [
                        {"term": {"tipo": tipo.upper()}},
                        {"term": {"tipo": "A"}},  # "Ambos" sempre aparece
                    ]
                }
            })

        if cidade:
            must.append({"match": {"cidade": {"query": cidade, "fuzziness": "AUTO"}}})

        if vendedor:
            must.append({"match": {"vendedor": {"query": vendedor, "fuzziness": "AUTO"}}})

        query = {
            "size": limit,
            "query": {
                "bool": {
                    "must": must if must else [{"match_all": {}}],
                    "filter": filter_clauses,
                }
            },
            "_source": ["codparc", "nome", "fantasia", "cnpj_cpf", "tipo",
                         "cidade", "uf", "telefone", "email", "vendedor"],
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{ELASTIC_URL}/{PARTNERS_INDEX}/_search",
                    json=query,
                    headers={"Content-Type": "application/json"}
                )

                if r.status_code != 200:
                    print(f"[ELASTIC] Erro busca parceiros: {r.status_code}")
                    return []

                result = r.json()
                hits = result.get("hits", {}).get("hits", [])

                return [{"_score": round(h.get("_score", 0), 2), **h.get("_source", {})} for h in hits]
        except Exception as e:
            print(f"[ELASTIC] Erro conexao busca parceiros: {e}")
            return []

    # ============================================================
    # HEALTH CHECK
    # ============================================================

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(f"{ELASTIC_URL}/_cluster/health")
                health = r.json()

                r2 = await client.get(f"{ELASTIC_URL}/_cat/indices?format=json")
                indices = r2.json()

                return {
                    "status": health.get("status"),
                    "indices": {
                        idx.get("index"): {
                            "docs": idx.get("docs.count"),
                            "size": idx.get("store.size"),
                        } for idx in indices if idx.get("index", "").startswith("idx_")
                    }
                }
        except Exception as e:
            return {"status": "offline", "error": str(e)}
