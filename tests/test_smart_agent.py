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
        from src.llm.smart_agent import extract_entities
        r = extract_entities("pendencia da marca mann", known_marcas={"MANN", "DONALDSON"})
        assert r["marca"] == "MANN"

    def test_fornecedor(self):
        from src.llm.smart_agent import extract_entities
        r = extract_entities("pedidos do fornecedor filtros mann", known_marcas=set())
        assert r["fornecedor"] == "FILTROS MANN"

    def test_empresa(self):
        from src.llm.smart_agent import extract_entities
        r = extract_entities("pendencia da empresa mmarra", known_empresas={"MMARRA", "CENTERPECAS"})
        assert r["empresa"] == "MMARRA"

    def test_noise_word_not_captured(self):
        from src.llm.smart_agent import extract_entities
        r = extract_entities("maior data de entrega da donaldson", known_marcas={"DONALDSON"})
        # "ENTREGA" nao deve ser capturado como marca
        assert r["marca"] != "ENTREGA"
        assert r["marca"] == "DONALDSON"

    def test_sem_entidade(self):
        from src.llm.smart_agent import extract_entities
        r = extract_entities("ola bom dia")
        assert r["marca"] is None
        assert r["fornecedor"] is None


# ============================================================
# TestScoreIntent
# ============================================================

class TestScoreIntent:
    def test_pendencia(self):
        from src.llm.smart_agent import score_intent
        scores = score_intent(["pendencia", "compras", "mann"])
        assert scores.get("pendencia_compras", 0) > 0

    def test_saudacao(self):
        from src.llm.smart_agent import score_intent
        scores = score_intent(["ola", "bom", "dia"])
        assert scores.get("saudacao", 0) > 0

    def test_estoque(self):
        from src.llm.smart_agent import score_intent
        scores = score_intent(["estoque", "produto", "133346"])
        assert scores.get("estoque", 0) > 0

    def test_vendas(self):
        from src.llm.smart_agent import score_intent
        scores = score_intent(["vendas", "hoje"])
        assert scores.get("vendas", 0) > 0

    def test_ajuda(self):
        from src.llm.smart_agent import score_intent
        scores = score_intent(["ajuda"])
        assert scores.get("ajuda", 0) > 0


# ============================================================
# TestSafeSql
# ============================================================

class TestSafeSql:
    def test_normal(self):
        from src.llm.smart_agent import _safe_sql
        assert _safe_sql("MANN") == "MANN"

    def test_aspas(self):
        from src.llm.smart_agent import _safe_sql
        assert _safe_sql("O'REILLY") == "O''REILLY"

    def test_injection(self):
        from src.llm.smart_agent import _safe_sql
        result = _safe_sql("'; DROP TABLE TGFCAB; --")
        assert "DROP" not in result or ";" not in result
        assert "--" not in result

    def test_vazio(self):
        from src.llm.smart_agent import _safe_sql
        assert _safe_sql("") == ""
        assert _safe_sql(None) == ""

    def test_semicolon_removed(self):
        from src.llm.smart_agent import _safe_sql
        result = _safe_sql("MANN; DELETE FROM")
        assert ";" not in result


# ============================================================
# TestColumnNormalize
# ============================================================

class TestColumnNormalize:
    def test_previsao(self):
        from src.llm.smart_agent import COLUMN_NORMALIZE
        assert COLUMN_NORMALIZE["PREVISAO"] == "PREVISAO_ENTREGA"
        assert COLUMN_NORMALIZE["PREVISAO_ENTREGA"] == "PREVISAO_ENTREGA"

    def test_fabricante(self):
        from src.llm.smart_agent import COLUMN_NORMALIZE
        assert COLUMN_NORMALIZE["FABRICANTE"] == "NUM_FABRICANTE"
        assert COLUMN_NORMALIZE["NUMERO_FABRICANTE"] == "NUM_FABRICANTE"
        assert COLUMN_NORMALIZE["CODIGO_FABRICANTE"] == "NUM_FABRICANTE"

    def test_original(self):
        from src.llm.smart_agent import COLUMN_NORMALIZE
        assert COLUMN_NORMALIZE["ORIGINAL"] == "NUM_ORIGINAL"

    def test_referencia(self):
        from src.llm.smart_agent import COLUMN_NORMALIZE
        assert COLUMN_NORMALIZE["REFERENCIA"] == "REFERENCIA"


# ============================================================
# TestGroqKeyPool
# ============================================================

class TestGroqKeyPool:
    def test_criacao_vazia(self):
        from src.llm.smart_agent import GroqKeyPool
        pool = GroqKeyPool([], "test")
        assert pool.available is False
        assert pool.get_key() is None

    def test_round_robin(self):
        from src.llm.smart_agent import GroqKeyPool
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
        from src.llm.smart_agent import GroqKeyPool
        pool = GroqKeyPool(["key1", "key2"], "test")
        pool.mark_rate_limited("key1", cooldown_s=60)
        # key1 em cooldown, deve pegar key2
        k = pool.get_key()
        assert k == "key2"

    def test_stats(self):
        from src.llm.smart_agent import GroqKeyPool
        pool = GroqKeyPool(["key1", "key2"], "test")
        pool.get_key()
        pool.get_key()
        s = pool.stats()
        assert s["pool"] == "test"
        assert s["keys"] == 2

    def test_mark_error(self):
        from src.llm.smart_agent import GroqKeyPool
        pool = GroqKeyPool(["key1"], "test")
        pool.mark_error("key1")
        s = pool.stats()
        assert s["errors"].get("...key1") == 1 or len(s["errors"]) > 0
