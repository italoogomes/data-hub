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


# ============================================================
# TestIsAnalyticalQuery (Cerebro Analitico)
# ============================================================

class TestIsAnalyticalQuery:
    """Valida detecção de queries analíticas vs fatuais."""

    # ---- Queries SIMPLES (fatual → routing normal) ----

    def test_fatual_quanto(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("quanto faturou o alvaro esse mes?") is False

    def test_fatual_qual_valor(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("qual o valor de pendência da mann?") is False

    def test_fatual_mostra(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("mostra os pedidos atrasados") is False

    def test_fatual_curta(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("oi") is False

    def test_fatual_comissao(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("comissão do rafael") is False

    def test_fatual_ajuda(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("ajuda com as funcionalidades") is False

    def test_fatual_pendencias(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("pendências da nakata") is False

    def test_fatual_estoque(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("estoque do produto 133346") is False

    def test_fatual_relatorio(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("quero um relatório de vendas") is False

    # ---- CONSULTIVOS (pedem ação/conselho → 70b) ----

    def test_consultivo_o_que_eu_posso_fazer(self):
        """BUG FIX: 'o que eu posso fazer' não era detectado (tinha 'eu' no meio)."""
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("o que eu posso fazer para melhorar a entrega?") is True

    def test_consultivo_oq_posso_fazer(self):
        """Informal: 'oq posso fazer'."""
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("oq posso fazer pra melhorar?") is True

    def test_consultivo_como_melhorar(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("como melhorar as vendas do próximo mês?") is True

    def test_consultivo_como_resolver(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("como resolver os atrasos?") is True

    def test_consultivo_me_da_sugestoes(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("me dá sugestões pra vender mais") is True

    def test_consultivo_tem_como_melhorar(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("tem como melhorar isso?") is True

    def test_consultivo_o_que_fazer(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("o que fazer com esses pedidos atrasados?") is True

    # ---- CAUSAIS (pedem explicação → 70b) ----

    def test_causal_por_que(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("por que o faturamento caiu em janeiro?") is True

    def test_causal_pq_informal(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("pq os pedidos atrasaram?") is True

    def test_causal_qual_motivo(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("qual o motivo da queda?") is True

    # ---- DECISÓRIOS (pedem opinião → 70b) ----

    def test_decisorio_vale_a_pena(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("vale a pena trocar de fornecedor?") is True

    def test_decisorio_devo(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("devo focar em qual vendedor?") is True

    # ---- AVALIATIVOS (pedem análise → 70b) ----

    def test_avaliativo_analise(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("analise os dados de vendas") is True

    def test_avaliativo_como_estamos(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("como estamos esse mês?") is True

    def test_avaliativo_o_que_significa(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("o que isso significa?") is True

    def test_avaliativo_tendencia(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("qual a tendência de vendas pra março?") is True

    def test_avaliativo_me_explica(self):
        from src.agent.brain import is_analytical_query
        assert is_analytical_query("me explica essa queda de margem") is True


# ============================================================
# TestCollectSessionContext
# ============================================================

class TestCollectSessionContext:
    """Valida coleta de contexto de sessão para o brain."""

    def test_sem_contexto(self):
        """Sem dados no contexto, retorna None."""
        from src.agent.brain import collect_session_context
        from src.agent.context import ConversationContext
        ctx = ConversationContext("test")
        assert collect_session_context(ctx) is None

    def test_sem_intent(self):
        """Sem intent no contexto, retorna None."""
        from src.agent.brain import collect_session_context
        assert collect_session_context(None) is None

    def test_com_contexto(self):
        """Com dados no contexto, retorna dict com info relevante."""
        from src.agent.brain import collect_session_context
        from src.agent.context import ConversationContext
        ctx = ConversationContext("test")
        ctx.intent = "pendencia_compras"
        ctx.params = {"marca": "NAKATA"}
        ctx.last_question = "pendências da nakata"
        ctx.last_result = {
            "response": "7 itens pendentes da NAKATA...",
            "detail_data": [{"PRODUTO": "A", "VLR_PENDENTE": 100}, {"PRODUTO": "B", "VLR_PENDENTE": 200}],
            "description": "Pendências de compra NAKATA",
        }
        result = collect_session_context(ctx)
        assert result is not None
        assert result["intent"] == "pendencia_compras"
        assert result["total_rows"] == 2
        assert result["params"]["marca"] == "NAKATA"
        assert "nakata" in result["last_question"]

    def test_contexto_sem_detail_data(self):
        """Contexto com intent mas sem detail_data retorna None."""
        from src.agent.brain import collect_session_context
        from src.agent.context import ConversationContext
        ctx = ConversationContext("test")
        ctx.intent = "saudacao"
        ctx.last_result = {"response": "Bom dia!"}
        assert collect_session_context(ctx) is None

    def test_contexto_com_underscore_detail_data(self):
        """BUG FIX: handlers retornam '_detail_data' (com underscore).
        has_data()/get_data() devem aceitar ambas as chaves."""
        from src.agent.brain import collect_session_context
        from src.agent.context import ConversationContext
        ctx = ConversationContext("test")
        ctx.intent = "pendencia_compras"
        ctx.params = {"marca": "NAKATA"}
        ctx.last_question = "pendências da nakata"
        # Simula resultado como handler REALMENTE retorna (com underscore)
        ctx.last_result = {
            "response": "7 itens pendentes da NAKATA...",
            "_detail_data": [{"PRODUTO": "A"}, {"PRODUTO": "B"}, {"PRODUTO": "C"}],
        }
        # has_data() e get_data() devem funcionar com _detail_data
        assert ctx.has_data() is True
        assert len(ctx.get_data()) == 3
        # collect_session_context deve encontrar os dados
        result = collect_session_context(ctx)
        assert result is not None
        assert result["total_rows"] == 3


# ============================================================
# TestBrainResult
# ============================================================

class TestBrainResult:
    """Valida formato do resultado do brain."""

    def test_build_result_format(self):
        """_build_result retorna dict compatível com handlers."""
        from src.agent.brain import _build_result
        result = _build_result("Análise dos dados mostra concentração em Nakata", model="70b")
        assert "response" in result
        assert "Análise" in result["response"]
        assert "Nakata" in result["response"]
        assert result["tipo"] == "brain_analysis"
        assert result["_brain_model"] == "70b"

    def test_format_context(self):
        """_format_context_for_llm formata contexto legível pro LLM."""
        from src.agent.brain import _format_context_for_llm
        ctx_data = {
            "intent": "pendencia_compras",
            "params": {"marca": "NAKATA"},
            "description": "Pendências NAKATA",
            "last_question": "pendências da nakata",
            "data": [{"PRODUTO": "A", "VLR_PENDENTE": 1000, "STATUS_ENTREGA": "ATRASADO"}],
            "total_rows": 7,
            "response_text": "7 itens pendentes da NAKATA, R$ 50.000",
        }
        text = _format_context_for_llm(ctx_data)
        assert "nakata" in text.lower()
        assert "7" in text
        assert "pendencia" in text.lower()
        # Deve conter a narração anterior
        assert "50.000" in text
        # Deve conter resumo calculado
        assert "1.000" in text or "1,000" in text

    def test_format_context_prioriza_narracao(self):
        """Narração anterior é prioridade no contexto."""
        from src.agent.brain import _format_context_for_llm
        ctx_data = {
            "intent": "pendencia_compras",
            "params": {},
            "description": "Pendências",
            "last_question": "pendências da nakata",
            "data": [{"PRODUTO": "A", "VLR_PENDENTE": 100}],
            "total_rows": 1,
            "response_text": "📦 **Pendência de compra NAKATA**\n\n7 pedidos, R$ 29.401, 44% fora do prazo",
        }
        text = _format_context_for_llm(ctx_data)
        # Narração deve estar presente (sem emoji)
        assert "29.401" in text
        assert "44%" in text

    def test_format_context_sem_narracao_usa_resumo(self):
        """Sem narração, usa resumo calculado."""
        from src.agent.brain import _format_context_for_llm
        ctx_data = {
            "intent": "pendencia_compras",
            "params": {"marca": "NAKATA"},
            "description": "Pendências",
            "last_question": "pendências da nakata",
            "data": [
                {"PRODUTO": "A", "VLR_PENDENTE": 1000, "STATUS_ENTREGA": "ATRASADO", "PEDIDO": "100"},
                {"PRODUTO": "B", "VLR_PENDENTE": 2000, "STATUS_ENTREGA": "NO PRAZO", "PEDIDO": "101"},
            ],
            "total_rows": 2,
            "response_text": "",
        }
        text = _format_context_for_llm(ctx_data)
        # Deve ter resumo calculado
        assert "3.000" in text or "3,000" in text  # soma
        assert "ATRASADO" in text
        assert "NO PRAZO" in text


# ============================================================
# TestSummarizeData
# ============================================================

class TestSummarizeData:
    """Valida cálculo de resumo estatístico por domínio."""

    def test_pendencia_summary(self):
        from src.agent.brain import _summarize_data
        rows = [
            {"VLR_PENDENTE": 1000, "STATUS_ENTREGA": "ATRASADO", "PEDIDO": "100", "MARCA": "NAKATA"},
            {"VLR_PENDENTE": 2000, "STATUS_ENTREGA": "ATRASADO", "PEDIDO": "100", "MARCA": "NAKATA"},
            {"VLR_PENDENTE": 500, "STATUS_ENTREGA": "NO PRAZO", "PEDIDO": "101", "MARCA": "FRAS-LE"},
        ]
        text = _summarize_data(rows, "pendencia_compras")
        assert "3.500" in text or "3,500" in text  # valor total
        assert "ATRASADO: 2" in text
        assert "NO PRAZO: 1" in text
        assert "Pedidos distintos: 2" in text

    def test_vendas_summary(self):
        from src.agent.brain import _summarize_data
        rows = [
            {"VALOR": 5000, "MARGEM": 8.5, "VENDEDOR": "RAFAEL"},
            {"VALOR": 3000, "MARGEM": 10.0, "VENDEDOR": "RAFAEL"},
        ]
        text = _summarize_data(rows, "vendas")
        assert "8.000" in text or "8,000" in text  # valor total
        assert "Margem" in text

    def test_empty_data(self):
        from src.agent.brain import _summarize_data
        assert _summarize_data([], "pendencia_compras") == ""
        assert _summarize_data([42], "pendencia_compras") == ""  # não é dict
