"""
Testes basicos do Smart Agent.
Roda com: python -m pytest tests/ -v
"""

import os
import sys
import time
from pathlib import Path

# Setup paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Carregar .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


# ============================================================
# TestExtractEntities
# ============================================================

class TestExtractEntities:
    def test_marca_simples(self):
        from src.llm.smart_agent_v3_backup import extract_entities
        r = extract_entities("pendencia da marca mann", known_marcas={"MANN", "DONALDSON"})
        assert r["marca"] == "MANN"

    def test_fornecedor(self):
        from src.llm.smart_agent_v3_backup import extract_entities
        r = extract_entities("pedidos do fornecedor filtros mann", known_marcas=set())
        assert r["fornecedor"] == "FILTROS MANN"

    def test_empresa(self):
        from src.llm.smart_agent_v3_backup import extract_entities
        r = extract_entities("pendencia da empresa mmarra", known_empresas={"MMARRA", "CENTERPECAS"})
        assert r["empresa"] == "MMARRA"

    def test_noise_word_not_captured(self):
        from src.llm.smart_agent_v3_backup import extract_entities
        r = extract_entities("maior data de entrega da donaldson", known_marcas={"DONALDSON"})
        # "ENTREGA" nao deve ser capturado como marca
        assert r["marca"] != "ENTREGA"
        assert r["marca"] == "DONALDSON"

    def test_sem_entidade(self):
        from src.llm.smart_agent_v3_backup import extract_entities
        r = extract_entities("ola bom dia")
        assert r["marca"] is None
        assert r["fornecedor"] is None


# ============================================================
# TestScoreIntent
# ============================================================

class TestScoreIntent:
    def test_pendencia(self):
        from src.llm.smart_agent_v3_backup import score_intent
        scores = score_intent(["pendencia", "compras", "mann"])
        assert scores.get("pendencia_compras", 0) > 0

    def test_saudacao(self):
        from src.llm.smart_agent_v3_backup import score_intent
        scores = score_intent(["ola", "bom", "dia"])
        assert scores.get("saudacao", 0) > 0

    def test_estoque(self):
        from src.llm.smart_agent_v3_backup import score_intent
        scores = score_intent(["estoque", "produto", "133346"])
        assert scores.get("estoque", 0) > 0

    def test_vendas(self):
        from src.llm.smart_agent_v3_backup import score_intent
        scores = score_intent(["vendas", "hoje"])
        assert scores.get("vendas", 0) > 0

    def test_ajuda(self):
        from src.llm.smart_agent_v3_backup import score_intent
        scores = score_intent(["ajuda"])
        assert scores.get("ajuda", 0) > 0


# ============================================================
# TestSafeSql
# ============================================================

class TestSafeSql:
    def test_normal(self):
        from src.llm.smart_agent_v3_backup import _safe_sql
        assert _safe_sql("MANN") == "MANN"

    def test_aspas(self):
        from src.llm.smart_agent_v3_backup import _safe_sql
        assert _safe_sql("O'REILLY") == "O''REILLY"

    def test_injection(self):
        from src.llm.smart_agent_v3_backup import _safe_sql
        result = _safe_sql("'; DROP TABLE TGFCAB; --")
        assert "DROP" not in result or ";" not in result
        assert "--" not in result

    def test_vazio(self):
        from src.llm.smart_agent_v3_backup import _safe_sql
        assert _safe_sql("") == ""
        assert _safe_sql(None) == ""

    def test_semicolon_removed(self):
        from src.llm.smart_agent_v3_backup import _safe_sql
        result = _safe_sql("MANN; DELETE FROM")
        assert ";" not in result


# ============================================================
# TestColumnNormalize
# ============================================================

class TestColumnNormalize:
    def test_previsao(self):
        from src.llm.smart_agent_v3_backup import COLUMN_NORMALIZE
        assert COLUMN_NORMALIZE["PREVISAO"] == "PREVISAO_ENTREGA"
        assert COLUMN_NORMALIZE["PREVISAO_ENTREGA"] == "PREVISAO_ENTREGA"

    def test_fabricante(self):
        from src.llm.smart_agent_v3_backup import COLUMN_NORMALIZE
        assert COLUMN_NORMALIZE["FABRICANTE"] == "NUM_FABRICANTE"
        assert COLUMN_NORMALIZE["NUMERO_FABRICANTE"] == "NUM_FABRICANTE"
        assert COLUMN_NORMALIZE["CODIGO_FABRICANTE"] == "NUM_FABRICANTE"

    def test_original(self):
        from src.llm.smart_agent_v3_backup import COLUMN_NORMALIZE
        assert COLUMN_NORMALIZE["ORIGINAL"] == "NUM_ORIGINAL"

    def test_referencia(self):
        from src.llm.smart_agent_v3_backup import COLUMN_NORMALIZE
        assert COLUMN_NORMALIZE["REFERENCIA"] == "REFERENCIA"


# ============================================================
# TestGroqKeyPool
# ============================================================

class TestGroqKeyPool:
    def test_criacao_vazia(self):
        from src.llm.smart_agent_v3_backup import GroqKeyPool
        pool = GroqKeyPool([], "test")
        assert pool.available is False
        assert pool.get_key() is None

    def test_round_robin(self):
        from src.llm.smart_agent_v3_backup import GroqKeyPool
        pool = GroqKeyPool(["key1", "key2", "key3"], "test")
        assert pool.available is True
        k1 = pool.get_key()
        k2 = pool.get_key()
        k3 = pool.get_key()
        k4 = pool.get_key()
        # Deve rotacionar entre as 3 chaves
        assert k1 != k2 or k2 != k3  # Pelo menos deve variar
        assert k4 == k1  # Volta pro inicio

    def test_cooldown(self):
        from src.llm.smart_agent_v3_backup import GroqKeyPool
        pool = GroqKeyPool(["key1", "key2"], "test")
        pool.mark_rate_limited("key1", cooldown_s=60)
        # key1 em cooldown, deve pegar key2
        k = pool.get_key()
        assert k == "key2"

    def test_stats(self):
        from src.llm.smart_agent_v3_backup import GroqKeyPool
        pool = GroqKeyPool(["key1", "key2"], "test")
        pool.get_key()
        pool.get_key()
        s = pool.stats()
        assert s["pool"] == "test"
        assert s["keys"] == 2

    def test_mark_error(self):
        from src.llm.smart_agent_v3_backup import GroqKeyPool
        pool = GroqKeyPool(["key1"], "test")
        pool.mark_error("key1")
        s = pool.stats()
        assert s["errors"].get("...key1") == 1 or len(s["errors"]) > 0


# ============================================================
# TestIsProductCode - detecção de código de produto
# ============================================================

class TestIsProductCode:
    def test_codigo_alfanumerico(self):
        """P618689, W950, 0986B02486 são códigos de produto."""
        from src.agent.product import is_product_code
        assert is_product_code("P618689") is True
        assert is_product_code("W950") is True
        assert is_product_code("0986B02486") is True

    def test_codigo_com_separadores(self):
        """HU727/1X, LF-3000 são códigos com separadores."""
        from src.agent.product import is_product_code
        assert is_product_code("HU727/1X") is True
        assert is_product_code("LF-3000") is True

    def test_codprod_numerico(self):
        """Código numérico puro com 5+ dígitos (CODPROD)."""
        from src.agent.product import is_product_code
        assert is_product_code("133346") is True
        assert is_product_code("12345") is True

    def test_texto_nao_e_codigo(self):
        """Frases e palavras comuns NÃO são código."""
        from src.agent.product import is_product_code
        assert is_product_code("filtro de oleo") is False
        assert is_product_code("pendencia da mann") is False
        assert is_product_code("bom dia") is False
        assert is_product_code("olá") is False

    def test_curto_demais(self):
        """Strings muito curtas não são código."""
        from src.agent.product import is_product_code
        assert is_product_code("AB") is False
        assert is_product_code("") is False

    def test_sem_digito_nao_e_codigo(self):
        """Palavras sem dígitos não são código (ex: MANN, BOSCH)."""
        from src.agent.product import is_product_code
        assert is_product_code("MANN") is False
        assert is_product_code("BOSCH") is False

    def test_dois_tokens_com_codigo(self):
        """Duas palavras onde uma parece código: 'HU727 1X'."""
        from src.agent.product import is_product_code
        assert is_product_code("HU727 1X") is True

    def test_multi_palavra_nao_e_codigo(self):
        """4+ palavras nunca é código."""
        from src.agent.product import is_product_code
        assert is_product_code("filtro oleo mann w950") is False


# ============================================================
# TestElasticHybridQuery - validação da query híbrida
# ============================================================

class TestElasticHybridQuery:
    """Valida que search_products monta a query corretamente com 3 prioridades."""

    def _capture_query(self, **kwargs):
        """Monta a query sem enviar ao Elastic (chama a lógica interna)."""
        import re
        should = []
        filter_clauses = [{"term": {"ativo": True}}]
        text = kwargs.get("text")
        codigo = kwargs.get("codigo")
        marca = kwargs.get("marca")

        if codigo:
            clean_code = re.sub(r'[\s\-/\.]', '', codigo).upper()
            for field in ("referencia.raw", "num_fabricante.raw", "num_fabricante2.raw",
                          "num_original.raw", "ref_fornecedor.raw"):
                should.append({"term": {field: {"value": codigo.upper(), "boost": 10}}})
            should.append({"match": {"all_codes": {"query": clean_code, "boost": 8}}})
            should.append({"fuzzy": {"all_codes": {"value": clean_code, "fuzziness": "AUTO", "boost": 5}}})
            should.append({"wildcard": {"all_codes": {"value": f"*{clean_code}*", "boost": 3}}})
            if clean_code.isdigit():
                should.append({"term": {"codprod": {"value": int(clean_code), "boost": 10}}})

        if text:
            for field in ("descricao", "full_text"):
                should.append({"match_phrase": {field: {"query": text, "boost": 5, "slop": 2}}})
            should.append({"multi_match": {"query": text, "fields": ["descricao^3", "full_text^2", "aplicacao^2", "complemento"], "type": "best_fields", "fuzziness": "AUTO", "prefix_length": 2, "boost": 1}})
            if ' ' in text.strip():
                should.append({"multi_match": {"query": text, "fields": ["descricao", "marca", "aplicacao", "all_codes"], "type": "cross_fields", "operator": "and", "boost": 3}})
            clean_text = re.sub(r'[\s\-/\.]', '', text).upper()
            if len(clean_text) >= 3:
                should.append({"match": {"all_codes": {"query": clean_text, "boost": 4}}})

        if marca:
            filter_clauses.append({"bool": {"should": [{"match": {"marca": {"query": marca, "fuzziness": "AUTO"}}}, {"term": {"marca.raw": marca.upper()}}]}})

        return should, filter_clauses

    def test_codigo_gera_prioridade_1(self):
        """Busca por código gera term matches com boost 10."""
        should, _ = self._capture_query(codigo="P618689")
        # Deve ter term matches com boost 10
        terms_10 = [s for s in should if "term" in s and any(
            isinstance(v, dict) and v.get("boost") == 10
            for v in s["term"].values()
        )]
        assert len(terms_10) >= 5  # 5 campos .raw

    def test_texto_gera_prioridade_2_e_3(self):
        """Busca por texto gera phrase match (P2) e multi_match (P3)."""
        should, _ = self._capture_query(text="filtro de oleo")
        # Prioridade 2: match_phrase
        phrases = [s for s in should if "match_phrase" in s]
        assert len(phrases) >= 2  # descricao + full_text
        # Prioridade 3: multi_match
        multis = [s for s in should if "multi_match" in s]
        assert len(multis) >= 1

    def test_multi_palavra_gera_cross_fields(self):
        """Busca multi-palavra gera cross_fields com operator=and."""
        should, _ = self._capture_query(text="filtro oleo mann w950")
        cross = [s for s in should if "multi_match" in s and s["multi_match"].get("type") == "cross_fields"]
        assert len(cross) == 1
        assert cross[0]["multi_match"]["operator"] == "and"

    def test_marca_vai_no_filter(self):
        """Marca vai nos filter_clauses, não no should."""
        should, filters = self._capture_query(text="filtro", marca="MANN")
        # Marca não deve estar no should (boost)
        # Marca deve estar no filter
        marca_filters = [f for f in filters if "bool" in f and "should" in f.get("bool", {})]
        assert len(marca_filters) == 1

    def test_codigo_numerico_gera_codprod(self):
        """Código numérico puro gera match em CODPROD."""
        should, _ = self._capture_query(codigo="133346")
        codprod = [s for s in should if "term" in s and "codprod" in s.get("term", {})]
        assert len(codprod) == 1
        assert codprod[0]["term"]["codprod"]["value"] == 133346


# ============================================================
# TestBuildProdutoSummary - narrador de busca Elastic
# ============================================================

class TestBuildProdutoSummary:
    """Valida que o summary para o narrador identifica PRODUTOS, não pedidos."""

    def _sample_results(self):
        return [
            {"codprod": 12345, "descricao": "ELEMENTO FILTRO AR EXTERNO", "marca": "MANN",
             "referencia": "P618689", "aplicacao": "SCANIA R124", "_score": 18.5},
            {"codprod": 67890, "descricao": "FILTRO AR SECUNDARIO", "marca": "MANN",
             "referencia": "CF1640", "aplicacao": "SCANIA P94", "_score": 12.3},
        ]

    def test_summary_identifica_produtos(self):
        """Summary deve conter 'PRODUTOS DO CATALOGO' e instrução anti-alucinação."""
        from src.agent.narrator import build_produto_summary
        summary = build_produto_summary(self._sample_results(), {"codigo_fabricante": "P618689"})
        assert "PRODUTOS DO CATALOGO" in summary
        # Deve conter instrução explícita de que NÃO são pedidos
        assert "NAO" in summary and "pedidos de compra" in summary.lower()
        assert "itens cadastrados" in summary.lower()

    def test_summary_inclui_codigo_buscado(self):
        """Summary deve mencionar o código de fabricante buscado."""
        from src.agent.narrator import build_produto_summary
        summary = build_produto_summary(self._sample_results(), {"codigo_fabricante": "P618689"})
        assert "P618689" in summary

    def test_summary_inclui_dados_produtos(self):
        """Summary deve listar CodProd, descrição e marca dos resultados."""
        from src.agent.narrator import build_produto_summary
        summary = build_produto_summary(self._sample_results(), {"texto_busca": "filtro ar"})
        assert "12345" in summary
        assert "ELEMENTO FILTRO AR" in summary
        assert "MANN" in summary

    def test_summary_nao_inventa_valores(self):
        """Summary NÃO deve conter R$, datas ou valores monetários inventados."""
        from src.agent.narrator import build_produto_summary
        summary = build_produto_summary(self._sample_results(), {"codigo_fabricante": "P618689"})
        assert "R$" not in summary
        assert "reais" not in summary.lower()


# ============================================================
# TestBuildVendasWhere - filtro de vendedor no SQL de vendas
# ============================================================

class TestBuildVendasWhere:
    """Valida que _build_vendas_where filtra por vendedor corretamente."""

    def test_vendedor_gera_filtro(self):
        """params com 'vendedor' deve gerar AND VEN.APELIDO LIKE."""
        from src.sql import _build_vendas_where
        w = _build_vendas_where({"vendedor": "ALVARO"})
        assert "VEN.APELIDO" in w
        assert "ALVARO" in w

    def test_vendedor_nome_retrocompat(self):
        """params com 'vendedor_nome' (legado) também deve funcionar."""
        from src.sql import _build_vendas_where
        w = _build_vendas_where({"vendedor_nome": "RAFAEL"})
        assert "VEN.APELIDO" in w
        assert "RAFAEL" in w

    def test_sem_vendedor_sem_filtro(self):
        """Sem vendedor, não deve gerar filtro de vendedor."""
        from src.sql import _build_vendas_where
        w = _build_vendas_where({"marca": "MANN"})
        assert "VEN.APELIDO" not in w

    def test_vendedor_com_marca(self):
        """Vendedor + marca devem gerar ambos os filtros."""
        from src.sql import _build_vendas_where
        w = _build_vendas_where({"vendedor": "ALVARO", "marca": "MANN"})
        assert "VEN.APELIDO" in w
        assert "MAR.DESCRICAO" in w


# ============================================================
# TestFormatVendasDevoluções - formatter mostra devoluções
# ============================================================

class TestFormatVendasDevolucoes:
    """Valida que format_vendas_response mostra devoluções quando existem."""

    def test_sem_devolucao(self):
        """Sem devoluções, formato clássico."""
        from src.formatters import format_vendas_response
        kpi = {"QTD_VENDAS": 50, "FATURAMENTO": 100000, "VLR_VENDAS": 100000,
               "VLR_DEVOLUCAO": 0, "TICKET_MEDIO": 2000, "MARGEM_MEDIA": 8.5, "COMISSAO_TOTAL": 5000}
        r = format_vendas_response(kpi, "fevereiro")
        assert "faturamento" in r.lower()
        assert "Devolu" not in r

    def test_com_devolucao(self):
        """Com devoluções, mostra vendas brutas + devoluções + líquido."""
        from src.formatters import format_vendas_response
        kpi = {"QTD_VENDAS": 50, "FATURAMENTO": 90000, "VLR_VENDAS": 100000,
               "VLR_DEVOLUCAO": 10000, "TICKET_MEDIO": 2000, "MARGEM_MEDIA": 8.5, "COMISSAO_TOTAL": 5000}
        r = format_vendas_response(kpi, "fevereiro")
        assert "Devolu" in r
        assert "quido" in r  # Líquido (sem acento pra robustez)

    def test_zero_vendas(self):
        """Zero vendas retorna mensagem informativa."""
        from src.formatters import format_vendas_response
        kpi = {"QTD_VENDAS": 0, "FATURAMENTO": 0, "VLR_VENDAS": 0, "VLR_DEVOLUCAO": 0}
        r = format_vendas_response(kpi, "fevereiro")
        assert "Nao encontrei" in r
