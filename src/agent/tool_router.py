"""
MMarra Data Hub - Tool Router.

Roteador de 3 camadas que decide qual ferramenta usar:
  Layer 1 (Haiku):      Claude Haiku - classificação inteligente (~200ms)
  Layer 2 (FC):         Groq Function Calling - backup se Haiku falhar (~300ms)
  Layer 3 (Fallback):   Scoring keywords + heurística (último recurso)

Queries triviais (saudação, ajuda, excel) são resolvidas por scoring
ANTES do Haiku para economizar tokens e latência.

Feature flag: USE_HAIKU_CLASSIFIER=true/false no .env
Quando false, volta pro fluxo antigo (scoring → FC → fallback).
"""

import json
import time
import re
from typing import Optional

from src.agent.tools import TOOLS, ToolCall, INTENT_TO_TOOL, tool_params_to_filters
from src.agent.scoring import score_intent, INTENT_THRESHOLDS
from src.agent.entities import extract_entities
from src.agent.context import ConversationContext
from src.core.groq_client import (
    pool_classify, groq_request, GROQ_MODEL_CLASSIFY
)
from src.core.utils import normalize


# Config
FC_CONFIDENCE_THRESHOLD = 0.65   # Score mínimo do Layer 1 para skip FC
FC_LOW_THRESHOLD = 0.35          # Abaixo disso, vai direto pro FC
FC_TIMEOUT = 12                  # Timeout do Function Calling (segundos)

# System prompt para Function Calling
FC_SYSTEM_PROMPT = """Você é o roteador do sistema ERP da MMarra Distribuidora Automotiva (autopeças pesadas).
Analise a pergunta do usuário e chame a ferramenta mais adequada com os parâmetros corretos.

REGRAS:
- SEMPRE chame uma ferramenta. Nunca responda em texto.
- Extraia APENAS entidades presentes na pergunta atual. NÃO invente ou herde dados de contexto anterior.
- Marcas são MAIÚSCULAS: MANN, SABO, DONALDSON, WEGA, FLEETGUARD, EATON, ZF, NAKATA, MAHLE.
- Empresas: RIBEIR(ão Preto), UBERL(ândia), ARACAT(uba), ITUMBI(ara).
- Períodos: "hoje", "ontem", "semana", "mês passado" → mapear para enum.
- "mil" = x1000 (ex: "50 mil" = 50000, "100 mil" = 100000).

ATALHOS DE FILTRO (use sempre que possível):
- "atrasados" → apenas_atrasados=true
- "acima de X mil" → valor_minimo=X000
- "abaixo de X mil" → valor_maximo=X000
- "mais de N dias" → dias_minimo=N
- Combine múltiplos atalhos! Ex: "atrasados acima de 50 mil" → apenas_atrasados=true, valor_minimo=50000

FERRAMENTAS:
- "tudo sobre" um produto → produto_360
- ENCONTRAR um produto → buscar_produto
- PENDÊNCIAS de compra → consultar_pendencias
- VENDA/FATURAMENTO → consultar_vendas
- RASTREAR pedido de venda → rastrear_pedido
- SIMILARES/EQUIVALENTES → buscar_similares
- BOLETO/DUPLICATA/CONTAS A PAGAR/RECEBER/FLUXO → consultar_financeiro (tipo: pagar/receber/fluxo)
- INADIMPLÊNCIA/DEVEDOR/QUEM DEVE → consultar_inadimplencia
- COMISSÃO/MARGEM/ALÍQUOTA/RANKING VENDEDOR → consultar_comissao (view: ranking/detalhe)"""


# ============================================================
# COMPLEX QUERY DETECTION
# ============================================================

_COMPLEX_PATTERNS = [
    # Filtros numéricos
    r'(?:acima|abaixo|mais|menos|maior|menor)\s+(?:de|que)\s+\d',
    r'\d+\s*(?:mil|k|reais|R\$)',
    r'(?:valor|vlr|preco|custo)\s+(?:acima|abaixo|maior|menor)',
    r'(?:entre)\s+\d.*(?:e|a)\s+\d',
    # Filtros temporais complexos
    r'(?:mais|menos)\s+(?:de|que)\s+\d+\s*dias',
    r'(?:aberto|pendente)\s+(?:ha|a)\s+mais',
    # Múltiplos critérios
    r'(?:atrasad[oa]s?|no prazo|sem previsao).*(?:acima|abaixo|maior|menor|valor|\d+\s*mil)',
    r'(?:acima|abaixo|maior|menor|valor|\d+\s*mil).*(?:atrasad[oa]s?|no prazo|sem previsao)',
    # Campos específicos
    r'(?:sem|com)\s+(?:previsao|confirmacao|data)\s+de',
    r'(?:dias?\s+aberto|dias?\s+pendente|dias?\s+atraso)',
]

_COMPLEX_COMPILED = [re.compile(p, re.IGNORECASE) for p in _COMPLEX_PATTERNS]


def _is_complex_query(q_norm: str, tokens: list) -> bool:
    """Detecta se a query precisa de interpretação semântica (LLM)."""
    for pattern in _COMPLEX_COMPILED:
        if pattern.search(q_norm):
            return True

    complexity_words = {
        "maior", "menor", "mais", "menos", "acima", "abaixo",
        "entre", "superior", "inferior", "sem", "com",
        "atrasado", "atrasados", "prazo", "atraso",
        "caro", "barato", "urgente", "critico",
        "valor", "quantidade", "data", "dias",
    }
    found = sum(1 for t in tokens if t in complexity_words)
    return found >= 2


    # Keywords que indicam query "sem filtro" (genérica)
_RESET_WORDS = {"todos", "todas", "geral", "tudo", "total", "ranking"}

# Keywords do domínio: se a query repete o domínio do ctx.intent → query nova
# Cross-domain: keywords de outro domínio (sem continuidade) → domain switch → nova query
_DOMAIN_KEYWORDS = {
    "comissao": {"comissao", "comissoes", "comissão", "comissões", "ranking"},
    "pendencia_compras": {"pendencia", "pendencias", "pendência", "pendências", "pedido", "pedidos"},
    "vendas": {"vendas", "faturamento", "venda"},
    "estoque": {"estoque"},
    "financeiro": {"financeiro", "financeira", "boleto", "boletos", "contas", "titulos", "pagar", "receber"},
    "inadimplencia": {"inadimplencia", "inadimplente", "devedor", "devendo"},
}

# Cache: todas as domain keywords de todos os domínios
_ALL_DOMAIN_KWS = set()
for _kws in _DOMAIN_KEYWORDS.values():
    _ALL_DOMAIN_KWS.update(_kws)


def _is_new_query(question: str, q_norm: str, tokens: list, params: dict,
                  ctx: ConversationContext) -> bool:
    """
    Detecta se a pergunta é uma NOVA consulta independente ou um follow-up.

    Nova query = tem intent próprio claro + não referencia dados anteriores.
    Follow-up = usa pronomes/referências + não tem entidades novas.

    Ordem dos checks:
    1. Continuity detection (gates checks subsequentes)
    2. Complex query (só sem continuidade)
    3. Entity diff (só sem continuidade)
    4. Same-domain re-statement (SEMPRE, mesmo com continuidade)
    5. Cross-domain keywords (só sem continuidade)
    6. Reset words (SEMPRE)
    7. Intent words + query longa (só sem continuidade)
    """
    if not ctx or not ctx.intent:
        return True

    # ---- STEP 1: Detectar sinais de continuidade ----
    # Quando presentes, a query é provavelmente follow-up — NÃO usar entity-diff nem complex
    _continuity = {"e", "agora", "tambem", "entao", "ainda", "alem",
                   "desses", "destes", "daqueles", "esses", "dele", "dela",
                   "ele", "ela", "eles", "elas"}
    has_continuity = any(w in tokens for w in _continuity)
    if not has_continuity:
        has_continuity = bool(re.search(r'^e\s+(da|do|de|das|dos)\s+', q_norm))

    # ---- STEP 2: Complex query (só sem continuidade) ----
    # "desses qual o mais caro?" tem continuidade → skip (é filtro, não query nova)
    if not has_continuity and _is_complex_query(q_norm, tokens):
        return True

    # ---- STEP 3: Entity diff (só sem continuidade) ----
    if not has_continuity:
        new_marca = params.get("marca")
        new_empresa = params.get("empresa")
        new_vendedor = params.get("vendedor")
        if new_marca and new_marca != ctx.params.get("marca"):
            return True
        if new_empresa and new_empresa != ctx.params.get("empresa"):
            return True
        if new_vendedor and new_vendedor != ctx.params.get("vendedor"):
            return True

    # ---- STEP 4: Same-domain re-statement (SEMPRE, mesmo com continuidade) ----
    # "comissão do mês" com ctx=comissao → re-statement → query nova
    # "e a comissão?" com ctx=comissao → re-statement → query nova
    domain_kws = _DOMAIN_KEYWORDS.get(ctx.intent, set())
    if domain_kws and any(kw in q_norm for kw in domain_kws):
        return True

    # ---- STEP 5: Cross-domain keywords (só sem continuidade) ----
    # "pedidos atrasados" com ctx=comissao → "pedidos" é de pendencia_compras → domain switch
    # MAS "qual marca ele mais vendeu?" com ctx=comissao → "ele" = continuidade → skip
    if not has_continuity:
        other_kws = _ALL_DOMAIN_KWS - (domain_kws or set())
        if any(kw in q_norm for kw in other_kws):
            return True

    # ---- STEP 6: Reset words (SEMPRE) ----
    if any(w in tokens for w in _RESET_WORDS):
        return True

    # ---- STEP 7: Intent words + query longa (só sem continuidade) ----
    if not has_continuity:
        intent_words = {
            "pendencia", "pendencias", "pedido", "pedidos", "compra", "compras",
            "venda", "vendas", "faturamento", "estoque", "produto", "produtos",
            "cliente", "fornecedor", "rastrear", "rastreio",
            "financeiro", "financeira", "boleto", "boletos", "pagar", "receber",
            "inadimplencia", "inadimplente", "devendo", "devedor",
            "comissao", "comissoes", "aliquota", "margem",
        }
        has_intent_word = any(t in intent_words for t in tokens)
        if has_intent_word and len(tokens) > 5:
            return True

    return False


# ============================================================
# MAIN ROUTER
# ============================================================

async def route(question: str, user_context: dict = None,
                ctx: ConversationContext = None,
                known_marcas: set = None, known_empresas: set = None,
                known_compradores: set = None,
                log: dict = None, history: list = None) -> ToolCall:
    """
    Roteador principal de 3 camadas.
    """
    t0 = time.time()
    q_norm = normalize(question)
    tokens = q_norm.split()
    
    if log is None:
        log = {}

    # Extrair entidades da pergunta ATUAL (antes de qualquer merge com contexto)
    params = extract_entities(
        question,
        known_marcas or set(),
        known_empresas or set(),
        known_compradores or set()
    )

    # ================================================================
    # PRE-CHECK: Follow-up ou nova query?
    # ================================================================
    is_new = _is_new_query(question, q_norm, tokens, params, ctx)

    if ctx and ctx.intent and not is_new:
        from src.agent.context import detect_followup, detect_filter_request

        # Excel follow-up
        if any(w in q_norm for w in ("excel", "planilha", "csv", "exportar", "baixar")):
            return ToolCall("gerar_excel", {}, source="context", confidence=0.99)
        
        # Filter follow-up (ex: "só os atrasados", "filtra por MANN")
        filters = detect_filter_request(q_norm, tokens)
        if filters:
            return ToolCall(
                INTENT_TO_TOOL.get(ctx.intent, ctx.intent),
                {"_followup_filters": filters},
                source="context_filter",
                confidence=0.95
            )
        
        # Pronoun follow-up (ex: "e de uberlândia?", "e ontem?")
        if detect_followup(q_norm.split(), q_norm):
            return ToolCall(
                INTENT_TO_TOOL.get(ctx.intent, ctx.intent),
                {"_followup": True},
                source="context_followup",
                confidence=0.90
            )

    # ================================================================
    # TRIVIAIS: Scoring rápido para intents óbvios (<1ms)
    # Resolve saudacao/ajuda/excel SEM gastar tokens no Haiku.
    # ================================================================
    scores = score_intent(tokens)
    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]

    if best_intent == "saudacao" and best_score >= 0.7:
        _log_route(log, "scoring", "saudacao", best_score, t0)
        return ToolCall("saudacao", {}, source="scoring", confidence=best_score)

    if best_intent == "ajuda" and best_score >= 0.7:
        _log_route(log, "scoring", "ajuda", best_score, t0)
        return ToolCall("ajuda", {}, source="scoring", confidence=best_score)

    if any(w in q_norm for w in ("excel", "planilha", "csv", "exportar")):
        _log_route(log, "scoring", "gerar_excel", 0.99, t0)
        return ToolCall("gerar_excel", {}, source="scoring", confidence=0.99)

    # ================================================================
    # LAYER 1: Claude Haiku — classificação inteligente (~200ms)
    # Substitui scoring + FC como classificador principal.
    # Feature flag: USE_HAIKU_CLASSIFIER no .env
    # ================================================================
    from src.agent.haiku_classifier import haiku_classify, USE_HAIKU_CLASSIFIER

    if USE_HAIKU_CLASSIFIER:
        haiku_result = await haiku_classify(
            question=question,
            known_marcas=known_marcas,
            known_empresas=known_empresas,
            known_compradores=known_compradores,
            ctx=ctx if not is_new else None,
            history=history,
        )

        if haiku_result and haiku_result.confidence >= 0.5:
            # Merge Haiku params com entities extraídas via regex
            # Regex é mais confiável pra marcas/empresas (match exato contra lista)
            haiku_result.params = _merge_fc_with_entities(
                haiku_result.name, haiku_result.params, params
            )
            _log_route(log, "haiku", haiku_result.name, haiku_result.confidence, t0)
            print(f"[ROUTER] Layer 1 (Haiku): {haiku_result.name}({haiku_result.params}) "
                  f"conf={haiku_result.confidence:.0%} | {int((time.time()-t0)*1000)}ms")
            return haiku_result

        if haiku_result:
            print(f"[ROUTER] Haiku conf baixa ({haiku_result.confidence:.0%}), tentando FC...")
        else:
            print(f"[ROUTER] Haiku falhou, tentando FC...")

    # ================================================================
    # LAYER 2: Groq Function Calling (backup se Haiku falhar)
    # ================================================================
    if pool_classify.available:
        fc_ctx = ctx if not is_new else None
        fc_result = await _function_calling(question, fc_ctx, params, history)
        if fc_result:
            _log_route(log, "function_calling", fc_result.name, fc_result.confidence, t0)
            print(f"[ROUTER] Layer 2 (FC): {fc_result.name}({fc_result.params}) | "
                  f"{int((time.time()-t0)*1000)}ms")
            return fc_result
        print(f"[ROUTER] Layer 2 (FC): falhou, caindo pro fallback")

    # ================================================================
    # LAYER 3: Scoring + Fallback heurístico (último recurso)
    # Se Haiku + FC falharam, scoring garante que o sistema funciona.
    # ================================================================
    if best_score >= FC_CONFIDENCE_THRESHOLD:
        tool_name = INTENT_TO_TOOL.get(best_intent, best_intent)
        tool_params = _entities_to_tool_params(tool_name, params, question)
        _log_route(log, "scoring_fallback", tool_name, best_score, t0)
        print(f"[ROUTER] Layer 3 (scoring): {tool_name} score={best_score:.2f} | "
              f"{int((time.time()-t0)*1000)}ms")
        return ToolCall(tool_name, tool_params, source="scoring_fallback", confidence=best_score)

    tool_call = _fallback_route(best_intent, best_score, params, q_norm, tokens)
    _log_route(log, "fallback", tool_call.name, tool_call.confidence, t0)
    print(f"[ROUTER] Layer 3 (fallback): {tool_call.name} | {int((time.time()-t0)*1000)}ms")
    return tool_call


# ============================================================
# LAYER 2: Function Calling
# ============================================================

async def _function_calling(question: str, ctx: ConversationContext = None,
                            params: dict = None, history: list = None) -> Optional[ToolCall]:
    """Usa Groq Function Calling para rotear a query."""
    
    messages = [
        {"role": "system", "content": FC_SYSTEM_PROMPT},
    ]
    
    # Só adicionar contexto se explicitamente passado (não em new queries)
    if ctx and ctx.intent:
        context_hint = (
            f"[Contexto: última consulta foi '{ctx.intent}'"
            f"{' sobre marca ' + ctx.params.get('marca', '') if ctx.params.get('marca') else ''}"
            f"{' empresa ' + ctx.params.get('empresa', '') if ctx.params.get('empresa') else ''}"
            f"]"
        )
        messages.append({"role": "system", "content": context_hint})
    
    # Incluir histórico da sessão (ajuda o LLM a resolver referências)
    if history:
        for msg in history[:-1]:  # Excluir a última (é a pergunta atual)
            messages.append(msg)
    
    messages.append({"role": "user", "content": question})
    
    try:
        result = await groq_request(
            pool=pool_classify,
            messages=messages,
            temperature=0.0,
            max_tokens=300,
            timeout=FC_TIMEOUT,
            model=GROQ_MODEL_CLASSIFY,
            tools=TOOLS,
            tool_choice="required"
        )
        
        if not result:
            return None
        
        tool_calls = result.get("tool_calls")
        if not tool_calls or len(tool_calls) == 0:
            content = result.get("content", "")
            if content:
                return _parse_text_fallback(content, params)
            return None
        
        tc = tool_calls[0]
        fn = tc.get("function", {})
        name = fn.get("name", "")
        
        args_raw = fn.get("arguments", "{}")
        try:
            args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
        except json.JSONDecodeError:
            args = {}
        
        if params:
            args = _merge_fc_with_entities(name, args, params)
        
        return ToolCall(name, args, source="function_calling", confidence=0.85)
    
    except Exception as e:
        print(f"[ROUTER] FC error: {e}")
        return None


def _parse_text_fallback(content: str, params: dict = None) -> Optional[ToolCall]:
    """Se o modelo respondeu em texto ao invés de tool_call, tenta extrair intent."""
    try:
        data = json.loads(content)
        if "intent" in data:
            intent = data["intent"]
            tool_name = INTENT_TO_TOOL.get(intent, intent)
            return ToolCall(tool_name, params or {}, source="fc_text_fallback", confidence=0.70)
    except (json.JSONDecodeError, KeyError):
        pass
    return None


# ============================================================
# LAYER 3: Fallback heurístico
# ============================================================

def _fallback_route(best_intent: str, best_score: float, params: dict,
                    q_norm: str, tokens: list) -> ToolCall:
    """Roteamento de fallback baseado em entidades + scoring."""
    
    has_entity = any(params.get(k) for k in ("marca", "fornecedor", "comprador"))
    
    if has_entity and best_score >= 0.25:
        tool_name = INTENT_TO_TOOL.get(best_intent, "consultar_pendencias")
        tool_params = _entities_to_tool_params(tool_name, params, q_norm)
        return ToolCall(tool_name, tool_params, source="fallback_entity", confidence=0.50)
    
    if has_entity:
        tool_params = _entities_to_tool_params("consultar_pendencias", params, q_norm)
        return ToolCall("consultar_pendencias", tool_params, source="fallback_entity", confidence=0.40)
    
    from src.llm.knowledge_base import score_knowledge
    kb_score = score_knowledge(q_norm)
    if kb_score >= 0.3:
        return ToolCall("consultar_conhecimento", {"pergunta": q_norm}, source="fallback_kb", confidence=0.45)
    
    return ToolCall("saudacao", {}, source="fallback_default", confidence=0.20)


# ============================================================
# HELPERS
# ============================================================

def _entities_to_tool_params(tool_name: str, params: dict, question: str = "") -> dict:
    """Converte entidades extraídas para parâmetros da tool específica."""
    
    if tool_name == "consultar_pendencias":
        tp = {}
        if params.get("marca"): tp["marca"] = params["marca"]
        if params.get("fornecedor"): tp["fornecedor"] = params["fornecedor"]
        if params.get("empresa"): tp["empresa"] = params["empresa"]
        if params.get("comprador"): tp["comprador"] = params["comprador"]
        return tp
    
    elif tool_name == "consultar_vendas":
        tp = {}
        if params.get("marca"): tp["marca"] = params["marca"]
        if params.get("empresa"): tp["empresa"] = params["empresa"]
        if params.get("periodo"): tp["periodo"] = params["periodo"]
        return tp
    
    elif tool_name == "consultar_estoque":
        tp = {}
        if params.get("codprod"): tp["codprod"] = params["codprod"]
        if params.get("produto_nome"): tp["produto_nome"] = params["produto_nome"]
        if params.get("marca"): tp["marca"] = params["marca"]
        if params.get("empresa"): tp["empresa"] = params["empresa"]
        return tp
    
    elif tool_name == "buscar_produto":
        tp = {}
        if params.get("produto_nome"): tp["texto_busca"] = params["produto_nome"]
        if params.get("marca"): tp["marca"] = params["marca"]
        if params.get("aplicacao"): tp["aplicacao"] = params["aplicacao"]
        return tp
    
    elif tool_name == "buscar_parceiro":
        tp = {"texto_busca": question, "tipo": "cliente"}
        return tp
    
    elif tool_name == "rastrear_pedido":
        tp = {}
        if params.get("nunota"): tp["nunota"] = params["nunota"]
        return tp
    
    elif tool_name == "produto_360":
        tp = {}
        if params.get("codprod"): tp["codprod"] = params["codprod"]
        if params.get("codigo_fabricante"): tp["codigo_fabricante"] = params["codigo_fabricante"]
        return tp
    
    elif tool_name == "buscar_similares":
        tp = {}
        if params.get("codprod"): tp["codprod"] = params["codprod"]
        if params.get("codigo_fabricante"): tp["codigo_fabricante"] = params["codigo_fabricante"]
        return tp
    
    elif tool_name == "consultar_financeiro":
        tp = {}
        if params.get("empresa"): tp["empresa"] = params["empresa"]
        if params.get("parceiro"): tp["parceiro"] = params["parceiro"]
        if params.get("periodo"): tp["periodo"] = params["periodo"]
        return tp

    elif tool_name == "consultar_inadimplencia":
        tp = {}
        if params.get("empresa"): tp["empresa"] = params["empresa"]
        if params.get("parceiro"): tp["parceiro"] = params["parceiro"]
        return tp

    elif tool_name == "consultar_comissao":
        tp = {}
        if params.get("empresa"): tp["empresa"] = params["empresa"]
        if params.get("vendedor"): tp["vendedor"] = params["vendedor"]
        if params.get("marca"): tp["marca"] = params["marca"]
        if params.get("periodo"): tp["periodo"] = params["periodo"]
        return tp

    elif tool_name == "consultar_conhecimento":
        return {"pergunta": question}

    return {}


def _merge_fc_with_entities(tool_name: str, fc_args: dict, regex_params: dict) -> dict:
    """
    Merge Function Calling args com entidades extraídas via regex.
    Regex é mais confiável pra marcas/empresas (match exato contra lista conhecida).
    FC é mais confiável pra parâmetros semânticos (período, filtros, ordenação).
    """
    merged = dict(fc_args)
    
    entity_fields = {
        "consultar_pendencias": ["marca", "fornecedor", "empresa", "comprador"],
        "consultar_vendas": ["marca", "empresa"],
        "consultar_estoque": ["marca", "empresa", "codprod"],
        "buscar_produto": ["marca"],
        "produto_360": ["codprod", "codigo_fabricante"],
        "buscar_similares": ["codprod", "codigo_fabricante"],
        "rastrear_pedido": ["nunota"],
        "consultar_financeiro": ["empresa", "parceiro"],
        "consultar_inadimplencia": ["empresa", "parceiro"],
        "consultar_comissao": ["empresa", "marca"],
    }
    
    fields = entity_fields.get(tool_name, [])
    for field in fields:
        regex_val = regex_params.get(field)
        if regex_val and not merged.get(field):
            merged[field] = regex_val
    
    return merged


def _log_route(log: dict, layer: str, tool_name: str, confidence: float, t0: float):
    """Registra informações de roteamento no log."""
    if log is not None:
        log["router"] = {
            "layer": layer,
            "tool": tool_name,
            "confidence": round(confidence, 3),
            "latency_ms": round((time.time() - t0) * 1000),
        }