"""
Testes do Haiku Classifier.
Roda com: python -m pytest tests/test_haiku_classifier.py -v
"""

import os
import sys
from pathlib import Path

# Setup paths
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Carregar .env
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


# ============================================================
# TestParseHaikuResponse
# ============================================================

class TestParseHaikuResponse:
    """Testa o parse da resposta JSON do Haiku."""

    def test_json_valido(self):
        from src.agent.haiku_classifier import _parse_haiku_response
        r = _parse_haiku_response('{"tool": "consultar_vendas", "params": {"periodo": "mes"}, "confidence": 0.95}')
        assert r is not None
        assert r["tool"] == "consultar_vendas"
        assert r["params"]["periodo"] == "mes"
        assert r["confidence"] == 0.95

    def test_json_com_markdown(self):
        from src.agent.haiku_classifier import _parse_haiku_response
        text = '```json\n{"tool": "consultar_vendas", "params": {}, "confidence": 0.9}\n```'
        r = _parse_haiku_response(text)
        assert r is not None
        assert r["tool"] == "consultar_vendas"

    def test_json_com_texto_extra(self):
        from src.agent.haiku_classifier import _parse_haiku_response
        text = 'Aqui está: {"tool": "saudacao", "params": {}, "confidence": 0.99}'
        r = _parse_haiku_response(text)
        assert r is not None
        assert r["tool"] == "saudacao"

    def test_texto_invalido(self):
        from src.agent.haiku_classifier import _parse_haiku_response
        assert _parse_haiku_response("não sei classificar") is None

    def test_json_sem_tool(self):
        from src.agent.haiku_classifier import _parse_haiku_response
        assert _parse_haiku_response('{"intent": "vendas"}') is None

    def test_string_vazia(self):
        from src.agent.haiku_classifier import _parse_haiku_response
        assert _parse_haiku_response("") is None

    def test_brain_analyze(self):
        from src.agent.haiku_classifier import _parse_haiku_response
        r = _parse_haiku_response('{"tool": "brain_analyze", "params": {}, "confidence": 0.90}')
        assert r is not None
        assert r["tool"] == "brain_analyze"

    def test_params_complexos(self):
        from src.agent.haiku_classifier import _parse_haiku_response
        text = '{"tool": "consultar_pendencias", "params": {"marca": "MANN", "apenas_atrasados": true, "valor_minimo": 50000}, "confidence": 0.92}'
        r = _parse_haiku_response(text)
        assert r is not None
        assert r["params"]["marca"] == "MANN"
        assert r["params"]["apenas_atrasados"] is True
        assert r["params"]["valor_minimo"] == 50000


# ============================================================
# TestBuildUserMessage
# ============================================================

class TestBuildUserMessage:
    """Testa a construção da mensagem do usuário."""

    def test_sem_contexto(self):
        from src.agent.haiku_classifier import _build_user_message
        msg = _build_user_message("pendências da nakata")
        assert 'Classifique: "pendências da nakata"' in msg

    def test_com_contexto(self):
        from src.agent.haiku_classifier import _build_user_message
        from src.agent.context import ConversationContext
        ctx = ConversationContext("test_user")
        ctx.intent = "pendencia_compras"
        ctx.params = {"marca": "NAKATA"}
        ctx.last_question = "pendências da nakata"
        msg = _build_user_message("e os atrasados?", ctx=ctx)
        assert "pendencia_compras" in msg
        assert "NAKATA" in msg
        assert "pendências da nakata" in msg


# ============================================================
# TestHaikuConfig
# ============================================================

class TestHaikuConfig:
    """Testa configurações do Haiku."""

    def test_defaults(self):
        from src.agent.haiku_classifier import HAIKU_MODEL, HAIKU_TIMEOUT, HAIKU_MAX_TOKENS
        assert "haiku" in HAIKU_MODEL.lower() or "claude" in HAIKU_MODEL.lower()
        assert HAIKU_TIMEOUT > 0
        assert HAIKU_MAX_TOKENS > 0

    def test_api_url(self):
        from src.agent.haiku_classifier import HAIKU_API_URL
        assert "anthropic.com" in HAIKU_API_URL

    def test_classifier_system_not_empty(self):
        from src.agent.haiku_classifier import CLASSIFIER_SYSTEM
        assert len(CLASSIFIER_SYSTEM) > 500
        assert "consultar_pendencias" in CLASSIFIER_SYSTEM
        assert "brain_analyze" in CLASSIFIER_SYSTEM


# ============================================================
# TestIntentToTool
# ============================================================

class TestIntentToTool:
    """Verifica que brain_analyze está mapeado."""

    def test_brain_analyze_in_mapping(self):
        from src.agent.tools import INTENT_TO_TOOL, TOOL_TO_INTENT
        assert "brain_analyze" in INTENT_TO_TOOL
        assert "brain_analyze" in TOOL_TO_INTENT


# ============================================================
# EXPECTED_CLASSIFICATIONS (documentação para validação manual)
# ============================================================

EXPECTED_CLASSIFICATIONS = [
    # (pergunta, tool esperado)
    ("pendências da nakata", "consultar_pendencias"),
    ("qual a próxima entrega do item P618689?", "consultar_pendencias"),
    ("vendas do mês", "consultar_vendas"),
    ("estoque do produto 133346", "consultar_estoque"),
    ("busca filtro de óleo", "buscar_produto"),
    ("boletos vencidos", "consultar_financeiro"),
    ("clientes inadimplentes", "consultar_inadimplencia"),
    ("comissão do rafael", "consultar_comissao"),
    ("como funciona compra casada?", "consultar_conhecimento"),
    ("rastreia pedido 45678", "rastrear_pedido"),
    ("oi", "saudacao"),
    ("ajuda", "ajuda"),
    ("por que o faturamento caiu?", "brain_analyze"),
    ("como melhorar a entrega?", "brain_analyze"),
    ("quem fornece a marca WEGA?", "consultar_pendencias"),
    ("quanto vendemos hoje?", "consultar_vendas"),
    ("dados do cliente Auto Peças", "buscar_parceiro"),
]
