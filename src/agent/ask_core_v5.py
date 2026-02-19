"""
MMarra Data Hub - ask_core V5 (Tool Use pattern).

Substitui o _ask_core de ~370 linhas por fluxo limpo:
    route() → ToolCall → dispatch() → handler → result

Para integrar: substituir _ask_core() e _dispatch() no SmartAgent.

ANTES (v4): 370 linhas de if/elif com 3 layers misturados
DEPOIS (v5): ~80 linhas, router externo, dispatch por dict
"""

import time
from typing import Optional

from src.agent.tool_router import route as tool_route
from src.agent.tools import ToolCall, tool_params_to_filters, INTENT_TO_TOOL
from src.agent.entities import extract_entities
from src.agent.context import (
    ConversationContext, build_context_hint,
    detect_filter_request
)
from src.agent.session import session_store
from src.agent.product import detect_product_query, is_product_code
from src.core.utils import normalize, tokenize
from src.agent.scoring import COLUMN_NORMALIZE, detect_view_mode
from src.agent.multistep import detect_multistep, extract_kpis_from_result, StepResult
from src.formatters.comparison import format_comparison


# ============================================================
# NEW _ask_core (substitui a versão de 370 linhas)
# ============================================================

async def ask_core_v5(self, question: str, user_context: dict = None, _log: dict = None) -> Optional[dict]:
    """
    Core do SmartAgent V5 - Tool Use pattern.
    
    Fluxo:
    1. Tool Router decide qual ferramenta usar (scoring → FC → fallback)
    2. Dispatch executa o handler correspondente
    3. Session memory é atualizada
    """
    await self._load_entities()
    t0 = time.time()
    tokens = tokenize(question)
    q_norm = normalize(question)
    user_id = (user_context or {}).get("user", "__default__")
    
    # ========== SESSION MEMORY ==========
    session = session_store.get(user_id)
    ctx = session.ctx  # ConversationContext vive dentro da SessionMemory
    session.add_user_message(question)
    history = session.get_history_for_llm(max_messages=6)

    if _log:
        _log["processing"] = _log.get("processing", {})

    # ========== ALIAS RESOLVER (pré-processamento) ==========
    params_pre = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
    self._last_alias_resolved = None
    self._last_produto_nome = params_pre.get("produto_nome")
    
    if params_pre.get("produto_nome"):
        alias = self.alias_resolver.resolve(params_pre["produto_nome"])
        if alias:
            original_term = params_pre["produto_nome"]
            resolved_to = alias.get("nome_real") or str(alias.get("codprod"))
            if alias.get("codprod"):
                params_pre["codprod"] = alias["codprod"]
                params_pre.pop("produto_nome", None)
            elif alias.get("nome_real"):
                params_pre["produto_nome"] = alias["nome_real"]
            self._last_alias_resolved = {"from": original_term, "to": resolved_to}
            print(f"[ALIAS] Resolvido: '{original_term}' -> {resolved_to}")

    # ========== MULTI-STEP DETECTION ==========
    # Detecta queries compostas (comparações, tendências) ANTES do routing normal
    plan = detect_multistep(question, ctx)
    if plan:
        print(f"[MULTISTEP] Detectado: {plan.merge_strategy} com {len(plan.steps)} steps")
        if _log:
            _log["processing"] = _log.get("processing", {})
            _log["processing"].update(layer="multistep", strategy=plan.merge_strategy)

        ms_result = await _execute_multistep(self, plan, question, user_context, t0, ctx, session)
        if ms_result:
            return ms_result
        # Se multi-step falhou, continuar com fluxo normal
        print("[MULTISTEP] Falhou, continuando com fluxo normal")

    # ========== LAYER 0.5: PRODUTO (roteamento especial) ==========
    # Detecta queries de produto que precisam de tratamento especial
    from src.agent.scoring import score_intent, INTENT_THRESHOLDS
    scores = score_intent(tokens)
    best_intent = max(scores, key=scores.get)
    best_score = scores[best_intent]
    
    _non_product = ("pendencia_compras", "estoque", "vendas", "rastreio_pedido")
    _scoring_wins = best_intent in _non_product and best_score >= INTENT_THRESHOLDS.get(best_intent, 8)

    # ---- LAYER 0.5a: Código de produto puro (P618689, W950, 0986B02486) ----
    # Intercepta ANTES do detect_product_query e roteia direto pro Elastic
    if is_product_code(question) and not _scoring_wins:
        print(f"[SMART] Layer 0.5a (código produto): '{question.strip()}'")
        code_params = dict(params_pre)
        code_params["codigo_fabricante"] = question.strip()
        code_params["texto_busca"] = question.strip()
        if _log: _log["processing"].update(layer="produto_code", intent="busca_produto")
        return await self._handle_busca_produto(question, user_context, t0, code_params, ctx)

    product_type = detect_product_query(q_norm, params_pre)

    if product_type and not _scoring_wins:
        print(f"[SMART] Layer 0.5 (produto): type={product_type} | params={params_pre}")
        if _log: _log["processing"].update(layer="produto", intent=product_type)
        return await self._dispatch_product(product_type, question, user_context, t0, params_pre, ctx)

    # ========== TOOL ROUTER (Layer 1 → 2 → 3) ==========
    log_route = {}
    tool_call = await tool_route(
        question=question,
        user_context=user_context,
        ctx=ctx,
        known_marcas=self._known_marcas,
        known_empresas=self._known_empresas,
        known_compradores=self._known_compradores,
        log=log_route,
        history=history,
    )
    
    print(f"[SMART] Router: {tool_call}")
    if _log:
        _log["processing"].update(
            layer=tool_call.source,
            intent=tool_call.intent,
            tool=tool_call.name,
            confidence=tool_call.confidence,
            score=best_score,
            entities={k: v for k, v in params_pre.items() if v and k != "periodo"},
        )
        if log_route.get("router"):
            _log["processing"]["router"] = log_route["router"]

    # ========== DEDUP: vendedor == marca (duplicata de nome) ==========
    # Cross-check: vendedor pode vir do FC e marca do regex (ou vice-versa)
    tc_params_check = tool_call.params or {}
    combined_vendedor = tc_params_check.get("vendedor") or params_pre.get("vendedor")
    combined_marca = tc_params_check.get("marca") or params_pre.get("marca")
    if combined_vendedor and combined_marca:
        vendedor_val = combined_vendedor.strip().upper()
        marca_val = combined_marca.strip().upper()
        if marca_val == vendedor_val or marca_val in vendedor_val or vendedor_val in marca_val:
            if not any(marca_val in m or m in marca_val for m in (self._known_marcas or set())):
                print(f"[SMART] Dedup: marca '{combined_marca}' == vendedor '{combined_vendedor}', removendo marca")
                tc_params_check.pop("marca", None)
                params_pre.pop("marca", None)

    # ========== DISPATCH ==========
    # Se a query NÃO é follow-up (source != context_*), limpar entidades do contexto
    # pra evitar que marca/empresa/vendedor da consulta anterior contamine esta
    _followup_sources = ("context_followup", "context_filter", "context")
    if tool_call.source not in _followup_sources and ctx and ctx.params:
        print(f"[CTX] Query nova (source={tool_call.source}) - limpando contexto: {ctx.params}")
        ctx.params = {}  # Limpa params do contexto anterior
    
    result = await dispatch_v5(self, tool_call, question, user_context, t0, tokens, params_pre, ctx, _log)

    # ========== UPDATE SESSION ==========
    if result and tool_call.name not in ("saudacao", "ajuda"):
        ctx.update(
            intent=tool_call.intent,
            params=tool_call.params if tool_call.params else params_pre,
            result=result,
            question=question,
            view_mode=tool_call.params.get("view", "pedidos")
        )
        # Registrar resposta na sessão
        session.add_assistant_message(
            content=result.get("response", "")[:200],
            tool_used=tool_call.name,
            params=tool_call.params or params_pre
        )

    return result


# ============================================================
# NEW _dispatch (substitui _dispatch + if/elif chain)
# ============================================================

async def dispatch_v5(self, tool_call: ToolCall, question: str, user_context: dict,
                      t0: float, tokens: list, params: dict,
                      ctx: ConversationContext, _log: dict = None) -> Optional[dict]:
    """
    Dispatch limpo por nome de tool.
    Cada tool mapeia diretamente para um handler.
    """
    name = tool_call.name
    tc_params = tool_call.params or {}

    # ---- Follow-up handlers ----
    if name == "gerar_excel":
        return await self._handle_excel_followup(user_context, ctx)

    if tc_params.get("_followup_filters"):
        filters = tc_params["_followup_filters"]
        result = self._handle_filter_followup(ctx, filters, question, t0)
        if result:
            return result
        # Se filtro falhou, continua com dispatch normal

    if tc_params.get("_followup") and ctx.intent:
        # Follow-up sem filtro: re-executar última consulta com contexto
        merged = ctx.merge_params(params)
        name = INTENT_TO_TOOL.get(ctx.intent, name)
        # Overlay entidades NOVAS da pergunta atual que merge_params pode ter ignorado
        # (merge_params tem whitelist fixa que não inclui vendedor, parceiro, etc.)
        # Novas entidades SEMPRE sobrescrevem as do contexto anterior
        for k, v in params.items():
            if v and not k.startswith("_"):
                merged[k] = v

        # Follow-up: se contexto tinha vendedor e nova query trouxe "marca"
        # que não é marca real, é o usuário trocando o vendedor
        # Ex: "comissão do rogerio" → "agora do rafael" → vendedor=RAFAEL
        # Guard: skip se tem empresa (marca é residual da extração de empresa)
        if ctx.params.get("vendedor") and merged.get("marca") and not merged.get("empresa"):
            marca_val = merged["marca"].strip().upper()
            is_known = self._known_marcas and any(
                marca_val in m or m in marca_val for m in self._known_marcas
            )
            if not is_known:
                print(f"[CTX] Follow-up vendedor swap: marca '{merged['marca']}' → vendedor")
                merged["vendedor"] = merged.pop("marca")

        params = merged

    # ---- Merge params: regex entities + FC params ----
    # FC params têm prioridade para campos semânticos (período, filtros)
    # Regex params têm prioridade para entidades conhecidas (marca, empresa)
    merged_params = dict(params)
    for k, v in tc_params.items():
        if not k.startswith("_") and v:
            # Regex wins para marca/empresa (match contra lista ERP)
            if k in ("marca", "empresa", "comprador", "fornecedor") and params.get(k):
                continue
            merged_params[k] = v

    # ---- Extrair view_mode ----
    view_mode = tc_params.get("view") or detect_view_mode(tokens)

    # ---- Extrair filtros do FC ----
    llm_filters = tool_params_to_filters(tc_params)
    
    # ---- Extra columns ----
    extra_columns = []
    for col in (tc_params.get("extra_columns") or []):
        norm = COLUMN_NORMALIZE.get(col.upper().replace(" ", "_"), col.upper())
        if norm not in extra_columns:
            extra_columns.append(norm)

    # Propagar tipo_compra
    if tc_params.get("tipo_compra") and not merged_params.get("tipo_compra"):
        tc = tc_params["tipo_compra"].lower()
        if tc in ("casada", "empenho", "vinculada"):
            merged_params["tipo_compra"] = "Casada"
        elif tc in ("estoque", "futura", "reposicao"):
            merged_params["tipo_compra"] = "Estoque"

    # ============================================================
    # DISPATCH TABLE
    # ============================================================
    
    if name == "consultar_pendencias":
        return await self._handle_pendencia_compras(
            question, user_context, t0, merged_params, view_mode, ctx,
            llm_filters=llm_filters if llm_filters else None,
            extra_columns=extra_columns if extra_columns else None
        )

    elif name == "consultar_vendas":
        return await self._handle_vendas(question, user_context, t0, merged_params, ctx)

    elif name == "consultar_estoque":
        return await self._handle_estoque(question, user_context, t0, merged_params, ctx)

    elif name == "consultar_financeiro":
        return await self._handle_financeiro(question, user_context, t0, merged_params, ctx)

    elif name == "consultar_inadimplencia":
        return await self._handle_inadimplencia(question, user_context, t0, merged_params, ctx)

    elif name == "consultar_comissao":
        return await self._handle_comissao(question, user_context, t0, merged_params, ctx)

    elif name == "buscar_produto":
        merged_params["texto_busca"] = tc_params.get("texto_busca") or merged_params.get("produto_nome", question)
        return await self._handle_busca_produto(question, user_context, t0, merged_params, ctx)

    elif name == "buscar_parceiro":
        tipo = "C" if tc_params.get("tipo") == "cliente" else "F"
        merged_params["texto_busca"] = tc_params.get("texto_busca", question)
        return await self._handle_busca_parceiro(question, user_context, t0, merged_params, tipo=tipo, ctx=ctx)

    elif name == "rastrear_pedido":
        if tc_params.get("nunota"):
            merged_params["nunota"] = tc_params["nunota"]
        return await self._handle_rastreio_pedido(question, user_context, t0, merged_params, ctx)

    elif name == "produto_360":
        return await self._handle_produto_360(question, user_context, t0, merged_params, ctx)

    elif name == "buscar_similares":
        return await self._handle_similares(question, user_context, t0, merged_params, ctx)

    elif name == "consultar_conhecimento":
        from src.llm.knowledge_base import score_knowledge
        kb_result = await self.kb.answer(question)
        if kb_result:
            kb_result["time_ms"] = int((time.time() - t0) * 1000)
            return kb_result
        return self._handle_fallback(question)

    elif name == "saudacao":
        return self._handle_saudacao(user_context)

    elif name == "ajuda":
        return self._handle_ajuda()

    # Fallback
    return self._handle_fallback(question)


# ============================================================
# HELPER: Dispatch de produto (Layer 0.5 preservado)
# ============================================================

async def _dispatch_product(self, product_type: str, question: str, user_context: dict,
                            t0: float, params: dict, ctx: ConversationContext):
    """Dispatch especial para queries de produto."""
    if product_type == "busca_fabricante":
        return await self._handle_busca_fabricante(question, user_context, t0, params, ctx)
    elif product_type == "similares":
        return await self._handle_similares(question, user_context, t0, params, ctx)
    elif product_type == "produto_360":
        return await self._handle_produto_360(question, user_context, t0, params, ctx)
    elif product_type == "busca_aplicacao":
        return await self._handle_busca_aplicacao(question, user_context, t0, params, ctx)
    else:
        return await self._handle_busca_produto(question, user_context, t0, params, ctx)


# ============================================================
# MULTI-STEP EXECUTOR
# ============================================================

# Mapeamento intent → handler name (para chamar diretamente)
_INTENT_HANDLER = {
    "comissao": "_handle_comissao",
    "vendas": "_handle_vendas",
    "pendencia_compras": "_handle_pendencia_compras",
    "financeiro": "_handle_financeiro",
    "inadimplencia": "_handle_inadimplencia",
    "estoque": "_handle_estoque",
}


async def _execute_multistep(self, plan, question: str, user_context: dict,
                              t0: float, ctx, session) -> Optional[dict]:
    """
    Executa um plano multi-step: roda cada step como query independente,
    extrai KPIs e formata resultado comparativo.

    Retorna None se qualquer step falhar (fallback para fluxo normal).
    """
    results = []

    for i, step in enumerate(plan.steps):
        intent = step["intent"]
        step_params = dict(step["params"])
        label = step.get("label", f"Step {i+1}")

        handler_name = _INTENT_HANDLER.get(intent)
        if not handler_name:
            print(f"[MULTISTEP] Step {i+1}: intent '{intent}' sem handler mapeado")
            return None

        handler = getattr(self, handler_name, None)
        if not handler:
            print(f"[MULTISTEP] Step {i+1}: handler '{handler_name}' nao encontrado")
            return None

        try:
            # Executar handler com ctx=None para isolamento total
            step_result = await handler(
                question, user_context, t0,
                params=step_params,
                ctx=None,  # Isolado: não contamina nem herda contexto
            )
        except Exception as e:
            print(f"[MULTISTEP] Step {i+1} erro: {e}")
            return None

        if not step_result:
            print(f"[MULTISTEP] Step {i+1} retornou None")
            return None

        # Extrair KPIs
        kpis = extract_kpis_from_result(step_result)
        data = step_result.get("_detail_data") or step_result.get("detail_data") or []

        results.append(StepResult(
            label=label,
            data=data,
            kpis=kpis,
            params=step_params,
        ))

        print(f"[MULTISTEP] Step {i+1}/{len(plan.steps)}: {label} → "
              f"{step_result.get('query_results', 0)} registros, "
              f"{len(kpis)} KPIs")

    # Formatar resultado comparativo
    if len(results) < 2:
        return None

    comparison = format_comparison(results, plan)
    if not comparison:
        return None

    elapsed = int((time.time() - t0) * 1000)
    comparison["time_ms"] = elapsed

    # Atualizar sessão
    if session and ctx:
        ctx.update(
            intent=plan.steps[0]["intent"],
            params=plan.steps[0]["params"],
            result={"detail_data": results[0].data, "description": f"comparação: {results[0].label} vs {results[1].label}"},
            question=question,
        )
        session.add_assistant_message(
            content=comparison.get("response", "")[:200],
            tool_used="multistep_compare",
            params={"strategy": plan.merge_strategy, "steps": len(plan.steps)},
        )

    return comparison


# ============================================================
# MONKEY-PATCH para aplicar no SmartAgent existente
# ============================================================

def patch_smart_agent(SmartAgentClass):
    """
    Aplica o novo _ask_core V5 no SmartAgent.
    
    Usage:
        from src.agent.ask_core_v5 import patch_smart_agent
        from src.llm.smart_agent import SmartAgent
        patch_smart_agent(SmartAgent)
    """
    SmartAgentClass._ask_core = ask_core_v5
    SmartAgentClass._dispatch = lambda self, intent, question, user_context, t0, tokens, params=None, ctx=None: \
        dispatch_v5(self, ToolCall(INTENT_TO_TOOL.get(intent, intent), params or {}), 
                    question, user_context, t0, tokens, params or {}, ctx)
    SmartAgentClass._dispatch_product = _dispatch_product
    
    # Substituir _get_context e clear_user pra usar SessionStore
    SmartAgentClass._get_context = lambda self, user_id: session_store.get_context(user_id)
    
    _original_clear = SmartAgentClass.clear_user
    def _clear_with_session(self, user_id):
        _original_clear(self, user_id)
        # Sessão expira naturalmente, mas forçar limpeza do ctx
        session = session_store.get(user_id)
        session.ctx = ConversationContext(user_id)
        session.messages.clear()
    SmartAgentClass.clear_user = _clear_with_session
    
    print("[SMART] V5 Tool Use pattern ativado!")
    print(f"[SESSION] SessionStore inicializado ({session_store.active_count} sessões ativas)")