"""
MMarra Data Hub - Smart Agent v4 (Modular)

Arquitetura modular:
- src/core/utils.py: normalize, tokenize, fmt_brl, fmt_num
- src/core/groq_client.py: GroqKeyPool, pools, groq_request
- src/agent/scoring.py: INTENT_SCORES, score_intent, thresholds
- src/agent/entities.py: extract_entities, EMPRESA_DISPLAY
- src/agent/context.py: ConversationContext, detect_followup, detect_filter_request, apply_filters
- src/agent/classifier.py: LLM_CLASSIFIER_PROMPT, groq_classify, llm_classify
- src/agent/narrator.py: llm_narrate, build_*_summary
- src/agent/product.py: detect_product_query, resolve_manufacturer_code, buscar_similares
- src/sql/__init__.py: sql_pendencia_compras, _build_vendas_where, etc.
- src/formatters/__init__.py: format_pendencia_response, format_vendas_response, etc.
- src/formatters/excel.py: generate_excel, generate_csv
- src/agent/training.py: daily_training, _training_scheduler, TRAINING_HOUR

Fluxo:
    Pergunta -> Score (0ms) -> [se ambíguo: LLM classifica (1-3s)] -> SQL template -> Sankhya -> Python formata -> Resposta
"""

import re
import os
import time
import asyncio
from typing import Optional
from datetime import datetime

from src.core.utils import normalize, tokenize, fmt_brl, fmt_num, trunc, safe_sql
from src.core.groq_client import (
    GroqKeyPool, pool_classify, pool_narrate, pool_train,
    groq_request, GROQ_MODEL, GROQ_MODEL_CLASSIFY
)
from src.agent.scoring import (
    INTENT_SCORES, INTENT_THRESHOLDS, CONFIRM_WORDS,
    score_intent, detect_view_mode, load_compiled_knowledge,
    _COMPILED_SCORES, _COMPILED_RULES,
    COLUMN_NORMALIZE, COLUMN_LABELS, COLUMN_MAX_WIDTH,
    EXISTING_SQL_COLUMNS, EXTRA_SQL_FIELDS
)
from src.agent.entities import extract_entities, EMPRESA_DISPLAY, PERIODO_NOMES
from src.agent.context import (
    ConversationContext, build_context_hint,
    detect_followup, detect_filter_request, apply_filters,
    FILTER_RULES
)
from src.agent.classifier import (
    LLM_CLASSIFIER_PROMPT, groq_classify, ollama_classify, llm_classify,
    USE_LLM_CLASSIFIER
)
from src.agent.narrator import (
    llm_narrate, build_pendencia_summary, build_vendas_summary, build_estoque_summary,
    build_produto_summary, USE_LLM_NARRATOR
)
from src.agent.product import (
    detect_product_query, resolve_manufacturer_code,
    buscar_similares, buscar_similares_por_codigo,
    format_produto_360, format_busca_fabricante, format_similares,
    SIMILAR_WORDS
)
from src.sql import (
    JOINS_PENDENCIA, WHERE_PENDENCIA,
    sql_pendencia_compras, _build_where_extra, _build_vendas_where,
    _build_periodo_filter, PERIODO_NOMES as SQL_PERIODO_NOMES
)
from src.formatters import (
    format_pendencia_response, format_vendas_response, format_estoque_response,
    format_financeiro_response, format_inadimplencia_response, format_comissao_response,
    detect_aggregation_view, format_comprador_marca, format_fornecedor_marca
)
from src.formatters.excel import generate_excel, generate_csv
from src.agent.training import daily_training, _training_scheduler, TRAINING_HOUR

from src.llm.query_executor import SafeQueryExecutor
from src.llm.knowledge_base import KnowledgeBase, score_knowledge
from src.llm.alias_resolver import AliasResolver
from src.llm.query_logger import QueryLogger, generate_auto_tags
from src.llm.result_validator import ResultValidator, build_result_data_summary

# Backward compatibility aliases
_load_compiled_knowledge = load_compiled_knowledge
_COMPILED_LOADED = False


def _is_complex_query(q_norm: str, tokens: list, pattern_filters: dict) -> bool:
    """Detecta se a query tem complexidade além de intent+entidade simples."""
    if pattern_filters:
        return False
    complexity_words = {
        "maior", "menor", "mais", "menos", "primeiro", "ultimo", "ultima",
        "acima", "abaixo", "entre", "superior", "inferior",
        "sem", "com",
        "previsao", "entrega", "confirmado", "confirmacao",
        "prazo", "atraso", "atrasado", "atrasados",
        "caro", "barato", "urgente", "critico",
        "valor", "quantidade", "data",
        "diferente", "igual", "mesmo", "vazio",
    }
    found = [t for t in tokens if t in complexity_words]
    if len(found) >= 2:
        return True
    complex_patterns = [
        r'(?:maior|menor|mais|menos)\s+(?:data|valor|quantidade|previsao|prazo|dias)',
        r'(?:sem|com)\s+(?:previsao|confirmacao|data|entrega)',
        r'(?:acima|abaixo)\s+de\s+\d',
        r'(?:entre)\s+\d.*e\s+\d',
        r'(?:data|previsao)\s+de\s+entrega',
    ]
    for p in complex_patterns:
        if re.search(p, q_norm):
            return True
    return False


def _llm_to_filters(llm_result: dict, question: str = "") -> dict:
    """Converte resultado da LLM (filtro/ordenar/top) no formato de apply_filters."""
    filters = {}
    filtro = llm_result.get("filtro")
    if filtro and isinstance(filtro, dict):
        campo = filtro.get("campo", "")
        operador = filtro.get("operador", "")
        valor = filtro.get("valor")
        if operador == "igual" and campo and valor:
            filters[campo] = str(valor).upper()
        elif operador == "vazio" and campo:
            filters["_fn_empty"] = campo
        elif operador == "nao_vazio" and campo:
            filters["_fn_not_empty"] = campo
        elif operador == "maior" and campo and valor:
            filters["_fn_maior"] = f"{campo}:{valor}"
        elif operador == "menor" and campo and valor:
            filters["_fn_menor"] = f"{campo}:{valor}"
        elif operador == "contem" and campo and valor:
            filters["_fn_contem"] = f"{campo}:{valor}"
    ordenar = llm_result.get("ordenar")
    if ordenar and isinstance(ordenar, str):
        filters["_sort"] = ordenar.upper()
    top = llm_result.get("top")
    if top and isinstance(top, (int, float)):
        filters["_top"] = int(top)
    elif top and isinstance(top, str) and top.isdigit():
        filters["_top"] = int(top)
    tipo_compra = llm_result.get("tipo_compra")
    if tipo_compra and isinstance(tipo_compra, str):
        tc = tipo_compra.lower().strip()
        if tc in ("casada", "empenho", "vinculada"):
            filters["TIPO_COMPRA"] = "Casada"
        elif tc in ("estoque", "futura", "reposicao"):
            filters["TIPO_COMPRA"] = "Estoque"
    # Post-processing
    if question:
        q_lower = question.lower()
        sort_key = filters.get("_sort", "")
        entrega_words = ["entrega", "previsao", "chegar", "chegada"]
        pedido_words = ["data do pedido", "quando pediu", "quando comprou"]
        if any(w in q_lower for w in entrega_words) and not any(w in q_lower for w in pedido_words):
            if "DT_PEDIDO" in sort_key:
                filters["_sort"] = sort_key.replace("DT_PEDIDO", "PREVISAO_ENTREGA")
    return filters



class SmartAgent:
    def __init__(self):
        self.executor = SafeQueryExecutor(
            whitelist=[
                # Vendas/Compras
                "TGFCAB", "TGFITE", "TGFPAR", "TGFPRO", "TGFVEN", "TGFTOP", "TGFVAR",
                # Marcas
                "TGFMAR",
                # Financeiro
                "TGFFIN",
                # Empresas
                "TSIEMP",
                # Estoque
                "TGFEST",
            ],
            on_security_event=lambda evt, details: self.query_logger.log_security_event(
                "SYSTEM", evt, details
            ),
        )
        self._known_marcas = set()
        self._known_empresas = set()
        self._known_compradores = set()
        self._entities_loaded = False
        self.kb = KnowledgeBase()  # Knowledge Base para perguntas sobre processos
        self.alias_resolver = AliasResolver()  # Apelidos de produto
        self.query_logger = QueryLogger()
        self.result_validator = ResultValidator()
        # Elasticsearch (busca fuzzy)
        try:
            from src.elastic.search import ElasticSearchEngine
            self.elastic = ElasticSearchEngine()
        except Exception:
            self.elastic = None
        # Contexto POR USUARIO
        self._user_contexts = {}  # {user_id: ConversationContext}
        # Carregar knowledge compilado (auto-gerado)
        _load_compiled_knowledge()

    def _get_context(self, user_id: str) -> 'ConversationContext':
        """Retorna (ou cria) contexto do usuario."""
        if not user_id:
            user_id = "__default__"
        if user_id not in self._user_contexts:
            self._user_contexts[user_id] = ConversationContext(user_id)
        return self._user_contexts[user_id]

    def clear_user(self, user_id: str):
        """Limpa contexto de um usuario especifico (logout)."""
        if user_id in self._user_contexts:
            del self._user_contexts[user_id]
            print(f"[CTX] Contexto limpo: {user_id}")

    def clear(self):
        """Limpa todos os contextos (compatibilidade)."""
        self._user_contexts.clear()
        print(f"[CTX] Todos os contextos limpos")

    async def _load_entities(self):
        """Carrega entidades do banco (1x, depois cache)."""
        if self._entities_loaded:
            return
        try:
            # Marcas
            r = await self.executor.execute("SELECT UPPER(TRIM(DESCRICAO)) AS M FROM TGFMAR WHERE DESCRICAO IS NOT NULL")
            if r.get("success"):
                for row in r.get("data", []):
                    v = row.get("M", row[0] if isinstance(row, (list, tuple)) else "") if isinstance(row, dict) else (str(row[0]) if isinstance(row, (list, tuple)) and row else "")
                    if v and len(v) > 1: self._known_marcas.add(v.strip())
            # Empresas
            r = await self.executor.execute("SELECT UPPER(TRIM(NOMEFANTASIA)) AS E FROM TSIEMP WHERE NOMEFANTASIA IS NOT NULL")
            if r.get("success"):
                for row in r.get("data", []):
                    v = row.get("E", row[0] if isinstance(row, (list, tuple)) else "") if isinstance(row, dict) else (str(row[0]) if isinstance(row, (list, tuple)) and row else "")
                    if v and len(v) > 1: self._known_empresas.add(v.strip())
            # Compradores (via marcas)
            r = await self.executor.execute("SELECT DISTINCT UPPER(TRIM(V.APELIDO)) AS C FROM TGFVEN V JOIN TGFMAR M ON M.AD_CODVEND = V.CODVEND WHERE V.APELIDO IS NOT NULL")
            if r.get("success"):
                for row in r.get("data", []):
                    v = row.get("C", row[0] if isinstance(row, (list, tuple)) else "") if isinstance(row, dict) else (str(row[0]) if isinstance(row, (list, tuple)) and row else "")
                    if v and len(v) > 1: self._known_compradores.add(v.strip())
            print(f"[SMART] Entidades: {len(self._known_marcas)} marcas, {len(self._known_empresas)} empresas, {len(self._known_compradores)} compradores")
        except Exception as e:
            print(f"[SMART] Erro ao carregar entidades: {e}")
        self._entities_loaded = True

    async def ask(self, question: str, user_context: dict = None) -> Optional[dict]:
        """Entry point com logging integrado."""
        user_id = (user_context or {}).get("user", "")
        _log = self.query_logger.create_entry(question, user=user_id)

        try:
            result = await self._ask_core(question, user_context, _log)
        except Exception as e:
            print(f"[SMART] Erro no ask: {e}")
            result = self._handle_fallback(question)
            _log["processing"]["layer"] = "error"

        # Finalizar log e salvar
        try:
            _detail_data = result.pop("_detail_data", None) if result else None
            self._finalize_log(_log, result, _detail_data)
            self.query_logger.save(_log)
            # Recolocar _detail_data para o endpoint montar table_data (toggle frontend)
            if _detail_data and result:
                result["_detail_data"] = _detail_data
        except Exception:
            pass

        if result:
            result["message_id"] = _log["id"]

            # B2: Registrar termos sem match como sugestao de alias
            query_results = result.get("query_results")
            produto_nome_used = getattr(self, '_last_produto_nome', None)

            if query_results == 0 and produto_nome_used:
                self.alias_resolver.suggest_alias(
                    produto_nome_used,
                    context=question,
                    user=user_id
                )
                # B4: Salvar failed term para deteccao de sequencia
                if not hasattr(self, '_failed_terms'):
                    self._failed_terms = {}
                self._failed_terms[user_id] = produto_nome_used
            elif query_results and query_results > 0 and produto_nome_used:
                # B4: Sequencia detectada - query anterior falhou, esta passou
                failed = getattr(self, '_failed_terms', {}).get(user_id)
                if failed and failed != produto_nome_used:
                    codprod_found = None
                    detail = result.get("_detail_data") or []
                    if detail and isinstance(detail[0], dict):
                        codprod_found = detail[0].get("CODPROD")
                    self.alias_resolver.detect_alias_from_sequence(failed, produto_nome_used, codprod_found)
                    self._failed_terms.pop(user_id, None)

            self._last_produto_nome = None

            # Prefixar resposta com alias resolvido
            if hasattr(self, '_last_alias_resolved') and self._last_alias_resolved:
                alias_info = self._last_alias_resolved
                self._last_alias_resolved = None
                resp = result.get("response", "")
                prefix = f"*'{alias_info['from']}' = {alias_info['to']}*\n\n"
                result["response"] = prefix + resp
        return result

    def _finalize_log(self, _log: dict, result: dict, _detail_data: list = None):
        """Preenche metadata final do log a partir do resultado."""
        if not result:
            return
        proc = _log.get("processing", {})
        proc["time_ms"] = result.get("time_ms", 0)
        # Result type mapping
        tipo = result.get("tipo", "info")
        type_map = {"consulta_banco": "table", "info": "knowledge", "arquivo": "table", "erro": "error"}
        records = result.get("query_results") or 0
        _log["result"] = {
            "type": type_map.get(tipo, tipo),
            "records_found": records,
            "records_shown": records,
            "response_preview": (result.get("response") or "")[:200],
        }
        _log["auto_tags"] = generate_auto_tags(_log)

        # Result data summary (para validacao offline)
        if _detail_data and isinstance(_detail_data, list):
            _log["result_data_summary"] = build_result_data_summary(_detail_data, _log)

        # Auto-auditoria: validacao em tempo real
        try:
            validation = self.result_validator.validate(_log, _detail_data)
            _log["validation"] = {
                "passed": validation["passed"],
                "checks_run": validation["checks_run"],
                "checks_failed": validation["checks_failed"],
                "severity": validation.get("severity"),
                "suggested_fix": validation.get("suggested_fix"),
                "checks": validation.get("checks", []),
            }
            # Console warnings para severity alta
            if validation.get("severity") in ("high", "critical"):
                for check in validation.get("checks", []):
                    if not check.get("passed"):
                        print(f"[AUDIT] {check.get('check', '?')}: {check.get('detail', '?')}")
        except Exception as e:
            print(f"[AUDIT] Erro na validacao: {e}")

    async def _ask_core(self, question: str, user_context: dict = None, _log: dict = None) -> Optional[dict]:
        await self._load_entities()
        t0 = time.time()
        tokens = tokenize(question)
        q_norm = normalize(question)
        user_id = (user_context or {}).get("user", "__default__")
        ctx = self._get_context(user_id)
        context_hint = build_context_hint(ctx)

        # Score de cada intent
        scores = score_intent(tokens)
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        if _log:
            _log["processing"]["score"] = best_score

        # ========== CONFIRMACAO CURTA (follow-up excel) ==========
        if len(tokens) <= 3 and any(t in CONFIRM_WORDS for t in tokens) and ctx.has_data():
            print(f"[SMART] Follow-up: gerar_excel")
            if _log: _log["processing"].update(layer="scoring", intent="gerar_excel")
            return await self._handle_excel_followup(user_context, ctx)

        # Excel explicito
        if scores.get("gerar_excel", 0) >= INTENT_THRESHOLDS["gerar_excel"]:
            if ctx.has_data():
                if _log: _log["processing"].update(layer="scoring", intent="gerar_excel")
                return await self._handle_excel_followup(user_context, ctx)

        # Saudacao (so se for curta e score alto)
        if scores.get("saudacao", 0) >= INTENT_THRESHOLDS["saudacao"] and len(tokens) <= 5:
            if _log: _log["processing"].update(layer="scoring", intent="saudacao")
            return self._handle_saudacao(user_context)

        # Ajuda
        if scores.get("ajuda", 0) >= INTENT_THRESHOLDS["ajuda"]:
            if _log: _log["processing"].update(layer="scoring", intent="ajuda")
            return self._handle_ajuda()

        # ========== DETECTAR FOLLOW-UP (referencia a dados anteriores) ==========
        is_followup = detect_followup(tokens, q_norm)
        filters = detect_filter_request(q_norm, tokens) if is_followup else {}

        if is_followup and ctx.has_data() and filters:
            # Filtrar dados anteriores
            print(f"[CTX] Follow-up com filtro: {filters} | ctx={ctx}")
            if _log: _log["processing"].update(layer="scoring", intent=ctx.intent or "follow_up", filters_source="pattern", filters_applied={k: str(v) for k, v in filters.items()})
            result = self._handle_filter_followup(ctx, filters, question, t0)
            if result:
                return result

        # ========== EXTRAIR PARAMETROS + MERGE COM CONTEXTO ==========
        params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        has_entity = (params.get("marca") or params.get("fornecedor") or params.get("comprador")
                      or params.get("empresa") or params.get("codprod") or params.get("codigo_fabricante")
                      or params.get("produto_nome"))

        # Se e follow-up sem entidade nova, herda do contexto
        if is_followup and not has_entity and ctx.params:
            merged = ctx.merge_params(params)
            if merged != params:
                print(f"[CTX] Herdando contexto: {params} -> {merged}")
                params = merged
                has_entity = (params.get("marca") or params.get("fornecedor") or params.get("comprador")
                              or params.get("empresa") or params.get("codprod") or params.get("codigo_fabricante")
                              or params.get("produto_nome"))

        # Se score baixo mas tem contexto e a pergunta parece continuacao
        if best_score < INTENT_THRESHOLDS.get(best_intent, 8) and is_followup and ctx.intent:
            # Herdar intent anterior se nenhum novo foi detectado forte
            if best_score <= 3:
                best_intent = ctx.intent
                best_score = INTENT_THRESHOLDS.get(best_intent, 8)  # Forca threshold
                print(f"[CTX] Herdando intent: {best_intent} (follow-up sem score)")

        # Salvar produto_nome original para B2 (registro de termos sem match)
        self._last_produto_nome = params.get("produto_nome")

        # ========== LAYER 0.4: ALIAS RESOLVER ==========
        self._last_alias_resolved = None
        if params.get("produto_nome"):
            alias = self.alias_resolver.resolve(params["produto_nome"])
            if alias:
                original_term = params["produto_nome"]
                resolved_to = alias.get("nome_real") or str(alias.get("codprod"))
                if alias.get("codprod"):
                    params["codprod"] = alias["codprod"]
                    params.pop("produto_nome", None)
                elif alias.get("nome_real"):
                    params["produto_nome"] = alias["nome_real"]
                self._last_alias_resolved = {"from": original_term, "to": resolved_to}
                print(f"[ALIAS] Resolvido: '{original_term}' -> {resolved_to} (conf={alias.get('confidence',0):.0%})")

        # ========== LAYER 0.5: PRODUTO (roteamento especial) ==========
        # So intercepta se scoring NAO detectou intent forte nao-produto
        # Ex: "S2581 tem pedido de compra?" → pendencia_compras=12 >> busca → nao interceptar
        _non_product = ("pendencia_compras", "estoque", "vendas", "rastreio_pedido")
        _scoring_wins = best_intent in _non_product and best_score >= INTENT_THRESHOLDS.get(best_intent, 8)
        product_type = detect_product_query(q_norm, params)
        if product_type and not _scoring_wins:
            print(f"[SMART] Layer 0.5 (produto): type={product_type} | params={params}")
            if _log: _log["processing"].update(layer="produto", intent=product_type)
            if product_type == "busca_fabricante":
                return await self._handle_busca_fabricante(question, user_context, t0, params, ctx)
            elif product_type == "similares":
                return await self._handle_similares(question, user_context, t0, params, ctx)
            elif product_type == "produto_360":
                return await self._handle_produto_360(question, user_context, t0, params, ctx)
            elif product_type == "busca_aplicacao":
                return await self._handle_busca_aplicacao(question, user_context, t0, params, ctx)
        elif product_type and _scoring_wins:
            print(f"[SMART] Layer 0.5: produto detectado mas {best_intent}={best_score} mais forte, seguindo scoring")

        # ========== LAYER 1: SCORING (0ms) ==========
        print(f"[SMART] Scores: pend={scores.get('pendencia_compras',0)} est={scores.get('estoque',0)} vend={scores.get('vendas',0)} rast={scores.get('rastreio_pedido',0)} | best={best_intent}({best_score}) | followup={is_followup}")

        # Log: entities extraidas
        if _log:
            _log["processing"]["entities"] = {k: v for k, v in params.items() if v and k != "periodo"}

        # Checar knowledge score antes pra decidir rota
        kb_score = score_knowledge(question)

        # Se KB score alto E data score nao e dominante, vai pra knowledge
        if kb_score >= 8 and (best_score < kb_score or best_score < 12):
            print(f"[SMART] Layer 1.2 (knowledge): kb={kb_score} vs data={best_score}")
            if _log: _log["processing"].update(layer="scoring", intent="conhecimento")
            kb_result = await self.kb.answer(question)
            if kb_result:
                kb_result["time_ms"] = int((time.time() - t0) * 1000)
                return kb_result

        if best_score >= INTENT_THRESHOLDS.get(best_intent, 8):
            # Score alto = confianca alta no INTENT, mas query pode ter filtros complexos
            print(f"[SMART] Layer 1 (scoring): {best_intent} (score={best_score})")
            if _log: _log["processing"].update(layer="scoring", intent=best_intent)

            # Detectar se query e complexa (filtros/ordenacao que o pattern nao pegou)
            pattern_filters = detect_filter_request(q_norm, tokens)

            # Intent override: se filter rules detectou TIPO_COMPRA, forcar pendencia_compras
            # (evita "compras de estoque da eaton" cair em intent=estoque)
            if pattern_filters.get("TIPO_COMPRA") and best_intent != "pendencia_compras":
                print(f"[SMART] Intent override: {best_intent} -> pendencia_compras (TIPO_COMPRA detectado)")
                best_intent = "pendencia_compras"
                if _log: _log["processing"]["intent"] = "pendencia_compras"
                # Propagar tipo_compra para params (usado no _build_where_extra)
                params["tipo_compra"] = pattern_filters["TIPO_COMPRA"]

            is_complex = _is_complex_query(q_norm, tokens, pattern_filters)

            if is_complex and best_intent in ("pendencia_compras", "estoque", "vendas") and pool_classify.available:
                # Query complexa: usar Groq pra interpretar filtros (scoring ja resolveu intent)
                print(f"[SMART] Layer 1+ (Groq filtro): query complexa, consultando Groq...")
                llm_result = await groq_classify(question, context_hint)
                if llm_result:
                    if _log: _log["processing"].update(layer="scoring+groq", groq_raw=dict(llm_result))
                    llm_filters = _llm_to_filters(llm_result, question)
                    # Usar entidades da LLM se scoring nao extraiu direito
                    for key in ["marca", "fornecedor", "empresa", "comprador", "periodo", "aplicacao"]:
                        if llm_result.get(key) and not params.get(key):
                            params[key] = llm_result[key]
                        elif llm_result.get(key) and params.get(key):
                            llm_val = llm_result[key].upper()
                            cur_val = params[key].upper()
                            if key == "marca" and self._known_marcas:
                                if llm_val in self._known_marcas and cur_val not in self._known_marcas:
                                    print(f"[SMART] LLM corrigiu {key}: {cur_val} -> {llm_val}")
                                    params[key] = llm_val
                                    if _log: _log["processing"]["groq_corrected"] = True
                    # Extrair e normalizar extra_columns
                    extra_columns = []
                    raw_extra = llm_result.get("extra_columns") or []
                    for col in raw_extra:
                        norm = COLUMN_NORMALIZE.get(col.upper().replace(" ", "_"), col.upper())
                        if norm not in extra_columns:
                            extra_columns.append(norm)
                    if extra_columns:
                        print(f"[SMART] Extra columns: {extra_columns}")
                        if _log: _log["processing"]["extra_columns"] = extra_columns
                    view_mode = llm_result.get("view") or detect_view_mode(tokens)
                    if _log:
                        _log["processing"]["view_mode"] = view_mode
                        _log["processing"]["entities"] = {k: v for k, v in params.items() if v and k != "periodo"}
                    if llm_filters:
                        print(f"[SMART] LLM filters: {llm_filters}")
                        if _log: _log["processing"].update(filters_source="llm", filters_applied={k: str(v) for k, v in llm_filters.items()})
                    if best_intent == "pendencia_compras":
                        return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx, llm_filters=llm_filters, extra_columns=extra_columns)
                    elif best_intent == "estoque":
                        return await self._handle_estoque(question, user_context, t0, params, ctx)
                    elif best_intent == "vendas":
                        return await self._handle_vendas(question, user_context, t0, params, ctx)

            if _log and pattern_filters:
                _log["processing"].update(filters_source="pattern", filters_applied={k: str(v) for k, v in pattern_filters.items()})
            # Propagar tipo_compra do filter para params (SQL WHERE)
            if pattern_filters.get("TIPO_COMPRA") and not params.get("tipo_compra"):
                params["tipo_compra"] = pattern_filters["TIPO_COMPRA"]
            return await self._dispatch(best_intent, question, user_context, t0, tokens, params, ctx)

        # ========== LAYER 1.5: ENTITY DETECTION ==========
        # Se tem entidade E busca_produto tambem pontuou, deixar LLM decidir (Layer 2)
        busca_score = scores.get("busca_produto", 0)
        if has_entity and best_score >= 3 and busca_score < 3:
            # Tem entidade + algum score + NAO parece busca produto = provavelmente pendencia
            print(f"[SMART] Layer 1.5 (entidade + score): pendencia | params={params}")
            if _log: _log["processing"].update(layer="scoring", intent="pendencia_compras")
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx)
        elif has_entity and best_score >= 3 and busca_score >= 3:
            print(f"[SMART] Layer 1.5: entidade detectada mas busca_produto={busca_score}, delegando pra LLM...")

        # ========== LAYER 2: LLM CLASSIFIER (Groq ~0.5s / Ollama ~10s) ==========
        if USE_LLM_CLASSIFIER:
            print(f"[SMART] Layer 2 (LLM): score ambiguo ({best_score}), consultando LLM...")
            llm_result = await llm_classify(question, context_hint)

            if llm_result and llm_result.get("intent") not in (None, "desconhecido", ""):
                intent = llm_result["intent"]
                print(f"[SMART] LLM classificou: {intent} | filtro={llm_result.get('filtro')} | ordenar={llm_result.get('ordenar')} | top={llm_result.get('top')}")

                if _log:
                    _layer = "groq" if pool_classify.available else "ollama"
                    _log["processing"].update(layer=_layer, intent=intent, groq_raw=dict(llm_result) if pool_classify.available else None)

                # Se LLM classificou como conhecimento
                if intent == "conhecimento":
                    kb_result = await self.kb.answer(question)
                    if kb_result:
                        kb_result["time_ms"] = int((time.time() - t0) * 1000)
                        return kb_result

                # Usar entidades da LLM se nao extraiu pelo scoring
                for key in ["marca", "fornecedor", "empresa", "comprador", "periodo", "aplicacao"]:
                    if llm_result.get(key) and not params.get(key):
                        params[key] = llm_result[key]

                # Extrair e normalizar extra_columns
                extra_columns = []
                raw_extra = llm_result.get("extra_columns") or []
                for col in raw_extra:
                    norm = COLUMN_NORMALIZE.get(col.upper().replace(" ", "_"), col.upper())
                    if norm not in extra_columns:
                        extra_columns.append(norm)
                if extra_columns:
                    print(f"[SMART] Extra columns (L2): {extra_columns}")
                    if _log: _log["processing"]["extra_columns"] = extra_columns

                view_mode = llm_result.get("view") or detect_view_mode(tokens)

                # Converter filtro/ordenar/top da LLM em dict de filtros
                llm_filters = _llm_to_filters(llm_result, question)
                if llm_filters:
                    print(f"[SMART] LLM filters convertidos: {llm_filters}")
                    if _log: _log["processing"].update(filters_source="llm", filters_applied={k: str(v) for k, v in llm_filters.items()})

                # Propagar tipo_compra da LLM para params (SQL WHERE)
                if llm_result.get("tipo_compra") and not params.get("tipo_compra"):
                    tc = llm_result["tipo_compra"].lower()
                    if tc in ("casada", "empenho", "vinculada"):
                        params["tipo_compra"] = "Casada"
                    elif tc in ("estoque", "futura", "reposicao"):
                        params["tipo_compra"] = "Estoque"
                if llm_filters.get("TIPO_COMPRA") and not params.get("tipo_compra"):
                    params["tipo_compra"] = llm_filters["TIPO_COMPRA"]
                if params.get("tipo_compra") and intent != "pendencia_compras":
                    print(f"[SMART] Intent override (LLM): {intent} -> pendencia_compras (tipo_compra={params['tipo_compra']})")
                    intent = "pendencia_compras"
                    if _log: _log["processing"]["intent"] = "pendencia_compras"

                if _log:
                    _log["processing"]["view_mode"] = view_mode
                    _log["processing"]["entities"] = {k: v for k, v in params.items() if v and k != "periodo"}

                if intent == "pendencia_compras":
                    return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx, llm_filters=llm_filters, extra_columns=extra_columns)
                elif intent == "estoque":
                    return await self._handle_estoque(question, user_context, t0, params, ctx)
                elif intent == "vendas":
                    return await self._handle_vendas(question, user_context, t0, params, ctx)
                elif intent == "produto":
                    # Redirecionar para detect_product_query ou busca_produto como fallback
                    product_type = detect_product_query(q_norm, params)
                    if product_type == "similares":
                        return await self._handle_similares(question, user_context, t0, params, ctx)
                    elif product_type == "produto_360":
                        return await self._handle_produto_360(question, user_context, t0, params, ctx)
                    elif product_type == "busca_aplicacao":
                        return await self._handle_busca_aplicacao(question, user_context, t0, params, ctx)
                    elif product_type == "busca_fabricante":
                        return await self._handle_busca_fabricante(question, user_context, t0, params, ctx)
                    else:
                        # Sem codigo → busca por nome no Elastic
                        params["texto_busca"] = llm_result.get("texto_busca")
                        return await self._handle_busca_produto(question, user_context, t0, params, ctx)
                elif intent == "rastreio_pedido":
                    params["nunota"] = llm_result.get("nunota")
                    return await self._handle_rastreio_pedido(question, user_context, t0, params, ctx)
                elif intent == "busca_produto":
                    params["texto_busca"] = llm_result.get("texto_busca")
                    return await self._handle_busca_produto(question, user_context, t0, params, ctx)
                elif intent == "busca_cliente":
                    params["texto_busca"] = llm_result.get("texto_busca")
                    return await self._handle_busca_parceiro(question, user_context, t0, params, tipo="C", ctx=ctx)
                elif intent == "busca_fornecedor":
                    params["texto_busca"] = llm_result.get("texto_busca")
                    return await self._handle_busca_parceiro(question, user_context, t0, params, tipo="F", ctx=ctx)
                elif intent == "saudacao":
                    return self._handle_saudacao(user_context)
                elif intent == "ajuda":
                    return self._handle_ajuda()

        # ========== LAYER 3: FALLBACK ==========
        # Ultima tentativa: se tem entidade e nao parece busca de produto, assume pendencia
        if has_entity and busca_score < 3:
            print(f"[SMART] Layer 3 (fallback c/ entidade): {params}")
            if _log: _log["processing"].update(layer="fallback", intent="pendencia_compras")
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx)

        # Ultima tentativa: se tem algum score de knowledge, tenta KB
        if kb_score >= 4:
            print(f"[SMART] Layer 3 (fallback knowledge): kb_score={kb_score}")
            if _log: _log["processing"].update(layer="fallback", intent="conhecimento")
            kb_result = await self.kb.answer(question)
            if kb_result:
                kb_result["time_ms"] = int((time.time() - t0) * 1000)
                return kb_result

        if _log: _log["processing"]["layer"] = "fallback"
        return self._handle_fallback(question)

    async def _dispatch(self, intent: str, question: str, user_context: dict, t0: float, tokens: list, params: dict = None, ctx: ConversationContext = None):
        """Despacha para o handler correto baseado no intent."""
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        if intent == "pendencia_compras":
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx)
        elif intent == "estoque":
            return await self._handle_estoque(question, user_context, t0, params, ctx)
        elif intent == "vendas":
            return await self._handle_vendas(question, user_context, t0, params, ctx)
        elif intent == "produto":
            q_norm = normalize(question)
            product_type = detect_product_query(q_norm, params)
            if product_type == "similares":
                return await self._handle_similares(question, user_context, t0, params, ctx)
            elif product_type == "produto_360":
                return await self._handle_produto_360(question, user_context, t0, params, ctx)
            elif product_type == "busca_aplicacao":
                return await self._handle_busca_aplicacao(question, user_context, t0, params, ctx)
            elif product_type == "busca_fabricante":
                return await self._handle_busca_fabricante(question, user_context, t0, params, ctx)
            else:
                # Sem codigo fabricante/codprod → busca por nome no Elastic
                return await self._handle_busca_produto(question, user_context, t0, params, ctx)
        elif intent == "rastreio_pedido":
            return await self._handle_rastreio_pedido(question, user_context, t0, params, ctx)
        elif intent == "busca_produto":
            return await self._handle_busca_produto(question, user_context, t0, params, ctx)
        elif intent == "busca_cliente":
            return await self._handle_busca_parceiro(question, user_context, t0, params, tipo="C", ctx=ctx)
        elif intent == "busca_fornecedor":
            return await self._handle_busca_parceiro(question, user_context, t0, params, tipo="F", ctx=ctx)
        elif intent == "saudacao":
            return self._handle_saudacao(user_context)
        elif intent == "ajuda":
            return self._handle_ajuda()
        return self._handle_fallback(question)

    # ---- FILTRO FOLLOW-UP (dados anteriores) ----
    def _handle_filter_followup(self, ctx: ConversationContext, filters: dict, question: str, t0: float):
        """Filtra dados anteriores baseado na pergunta do usuario."""
        data = ctx.get_data()
        if not data:
            return None

        # Guardar meta antes de apply_filters (que faz pop)
        has_sort = "_sort" in filters
        has_top = "_top" in filters
        top_n = filters.get("_top", 0)
        sort_key = filters.get("_sort", "")
        filter_fields = {k: v for k, v in filters.items() if not k.startswith("_")}
        fn_fields = {k: v for k, v in filters.items() if k.startswith("_fn_")}

        filtered = apply_filters(list(data), dict(filters))

        if not filtered:
            desc = ctx.get_description()
            return {
                "response": f"\U0001f914 Nenhum resultado encontrado com esse filtro nos dados de **{desc}**.\n\nTente outra pergunta ou faca uma nova consulta.",
                "tipo": "consulta_banco",
                "query_executed": f"Filtro: {filters}",
                "query_results": 0,
                "time_ms": int((time.time() - t0) * 1000),
            }

        desc = ctx.get_description()
        prev_intent = ctx.intent or "pendencia_compras"

        # Construir descricao do filtro para o titulo
        filter_parts = []
        if filter_fields:
            filter_parts.append(", ".join(f"{v}" for v in filter_fields.values()))
        for fn_key, fn_field in fn_fields.items():
            fn_name = fn_key.replace("_fn_", "")
            if fn_name == "empty":
                filter_parts.append(f"sem {fn_field.lower().replace('_', ' ')}")
        if has_sort and sort_key:
            sort_names = {
                "DIAS_ABERTO_DESC": "mais atrasado", "DIAS_ABERTO_ASC": "mais recente",
                "VLR_PENDENTE_DESC": "maior valor", "VLR_PENDENTE_ASC": "menor valor",
                "DT_PEDIDO_DESC": "mais recente", "QTD_PENDENTE_DESC": "maior quantidade",
            }
            filter_parts.append(sort_names.get(sort_key, sort_key))

        filter_label = " | ".join(filter_parts) if filter_parts else "filtrado"

        if prev_intent == "pendencia_compras":
            # Resposta especial para top 1 (resposta direta)
            if top_n == 1 and len(filtered) == 1:
                r = filtered[0]
                pedido = r.get("PEDIDO", "?")
                produto = r.get("PRODUTO", "?")
                marca = r.get("MARCA", "")
                vlr = float(r.get("VLR_PENDENTE", 0) or 0)
                dias = int(r.get("DIAS_ABERTO", 0) or 0)
                qtd = int(r.get("QTD_PENDENTE", 0) or 0)
                status = r.get("STATUS_ENTREGA", "?")
                fornecedor = r.get("FORNECEDOR", "")

                response = f"\U0001f50d **{filter_label.title()}** de **{desc.title()}**:\n\n"
                response += f"| Campo | Valor |\n|---|---|\n"
                response += f"| **Pedido** | {pedido} |\n"
                if fornecedor: response += f"| **Fornecedor** | {fornecedor} |\n"
                response += f"| **Produto** | {produto} |\n"
                if marca: response += f"| **Marca** | {marca} |\n"
                response += f"| **Qtd. Pendente** | {fmt_num(qtd)} |\n"
                response += f"| **Valor Pendente** | R$ {fmt_num(vlr)} |\n"
                response += f"| **Dias em Aberto** | {dias} dias |\n"
                response += f"| **Status** | {status} |\n"
            else:
                # Tabela normal com KPIs
                view_mode = "itens"
                kpis_data = [{
                    "QTD_PEDIDOS": len(set(str(r.get("PEDIDO", "")) for r in filtered if isinstance(r, dict))),
                    "QTD_ITENS": len(filtered),
                    "VLR_PENDENTE": sum(float(r.get("VLR_PENDENTE", 0) or 0) for r in filtered if isinstance(r, dict)),
                }]
                response = format_pendencia_response(kpis_data, filtered, f"{desc} ({filter_label})", ctx.params, view_mode, extra_columns=ctx._extra_columns if ctx else [])
        elif prev_intent == "estoque":
            response = format_estoque_response(filtered, ctx.params)
        elif prev_intent == "vendas":
            kpi_row = {
                "QTD_VENDAS": len(filtered),
                "FATURAMENTO": sum(float(r.get("FATURAMENTO", 0) or 0) for r in filtered if isinstance(r, dict)),
                "TICKET_MEDIO": 0,
            }
            if kpi_row["QTD_VENDAS"]:
                kpi_row["TICKET_MEDIO"] = kpi_row["FATURAMENTO"] / kpi_row["QTD_VENDAS"]
            response = format_vendas_response(kpi_row, f"{desc} ({filter_label})")
        else:
            response = f"Encontrei **{len(filtered)}** registros com o filtro aplicado."

        elapsed = int((time.time() - t0) * 1000)
        return {
            "response": response,
            "tipo": "consulta_banco",
            "query_executed": f"Filtro: {filter_label}",
            "query_results": len(filtered),
            "time_ms": elapsed,
        }

    # ---- SAUDACAO ----
    def _handle_saudacao(self, user_context=None):
        nome = (user_context or {}).get("user", "")
        hora = datetime.now().hour
        saud = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
        r = f"{saud}{', ' + nome if nome else ''}! \U0001f44b\n\n"
        r += "Como posso ajudar? Posso consultar:\n\n"
        r += "\U0001f4e6 **Pendencia de compras** - *\"pendencia da marca Donaldson\"*\n"
        r += "\U0001f4ca **Vendas e faturamento** - *\"vendas de hoje\"*\n"
        r += "\U0001f4cb **Estoque** - *\"estoque do produto 133346\"*\n"
        r += "\U0001f50d **Rastreio de pedido** - *\"como esta o pedido 1199868?\"*\n\nE so perguntar!"
        return {"response": r, "tipo": "info", "query_executed": None, "query_results": None}

    def _handle_ajuda(self):
        r = "\U0001f916 **O que posso fazer:**\n\n"
        r += "**\U0001f4e6 Pendencia de Compras**\n- *\"Pendencia da marca Donaldson\"*\n- *\"Itens pendentes da Tome\"*\n- *\"Pedidos em aberto do comprador Juliano\"*\n\n"
        r += "**\U0001f4ca Vendas**\n- *\"Vendas de hoje\"* / *\"Faturamento do mes\"*\n\n"
        r += "**\U0001f4cb Estoque**\n- *\"Estoque do produto 133346\"*\n- *\"Estoque critico\"*\n\n"
        r += "**\U0001f4da Processos e Regras**\n- *\"Como funciona o fluxo de compras?\"*\n- *\"O que e compra casada?\"*\n- *\"Qual a diferenca entre TOP 1301 e 1313?\"*\n\n"
        r += "**\U0001f4e5 Excel**\n- Apos qualquer consulta, diga *\"sim\"* ou *\"gera excel\"*\n\n"
        r += "\U0001f4a1 Tambem temos **Relatorios** completos no menu lateral!"
        return {"response": r, "tipo": "info", "query_executed": None, "query_results": None}

    def _handle_fallback(self, question):
        r = "\U0001f914 Nao entendi a pergunta.\n\nTente algo como:\n- *\"Pendencia da marca Donaldson\"*\n- *\"Vendas de hoje\"*\n- *\"Estoque do produto 133346\"*\n\nOu digite **ajuda** para ver tudo que posso fazer."
        return {"response": r, "tipo": "info", "query_executed": None, "query_results": None}

    # ---- PENDENCIA ----
    async def _handle_pendencia_compras(self, question, user_context, t0, params=None, view_mode="pedidos", ctx=None, llm_filters=None, extra_columns=None):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        # Merge com contexto se disponivel
        if ctx and not (params.get("marca") or params.get("fornecedor") or params.get("comprador")):
            params = ctx.merge_params(params)
            print(f"[CTX] Params merged: {params}")

        # Herdar extra_columns do contexto se nao veio nesta pergunta
        if not extra_columns and ctx and hasattr(ctx, '_extra_columns') and ctx._extra_columns:
            extra_columns = ctx._extra_columns
            print(f"[CTX] Extra columns herdadas: {extra_columns}")

        extra_cols_normalized = extra_columns or []
        print(f"[SMART] Pendencia params: {params} | view: {view_mode} | llm_filters: {llm_filters} | extra_cols: {extra_cols_normalized}")

        sql_kpis, sql_detail, description = sql_pendencia_compras(params, user_context)

        # Verificar se precisa adicionar campos ao SQL
        needs_sql_extra = [c for c in extra_cols_normalized if c in EXTRA_SQL_FIELDS]
        if needs_sql_extra:
            extra_select = ", ".join(EXTRA_SQL_FIELDS[c] for c in needs_sql_extra)
            sql_detail = sql_detail.replace(
                f"\n        {JOINS_PENDENCIA}",
                f",\n            {extra_select}\n        {JOINS_PENDENCIA}"
            )
            print(f"[SMART] SQL com campos extras: {needs_sql_extra}")

        kpis_result = await self.executor.execute(sql_kpis)
        if not kpis_result.get("success"):
            return {"response": f"Erro ao consultar: {kpis_result.get('error','?')}", "tipo": "consulta_banco", "query_executed": sql_kpis[:200], "query_results": 0}

        kpis_data = kpis_result.get("data", [])
        if kpis_data and isinstance(kpis_data[0], (list, tuple)):
            cols = kpis_result.get("columns") or ["QTD_PEDIDOS", "QTD_ITENS", "VLR_PENDENTE"]
            kpis_data = [dict(zip(cols, row)) for row in kpis_data]

        qtd = int((kpis_data[0] if kpis_data else {}).get("QTD_PEDIDOS", 0) or 0)
        detail_data = []
        detail_columns = ["EMPRESA","PEDIDO","TIPO_COMPRA","COMPRADOR","DT_PEDIDO","PREVISAO_ENTREGA","CONFIRMADO","FORNECEDOR","CODPROD","PRODUTO","MARCA","APLICACAO","NUM_FABRICANTE","UNIDADE","QTD_PEDIDA","QTD_ATENDIDA","QTD_PENDENTE","VLR_UNITARIO","VLR_PENDENTE","DIAS_ABERTO","STATUS_ENTREGA"] + needs_sql_extra

        if qtd > 0:
            dr = await self.executor.execute(sql_detail)
            if dr.get("success"):
                detail_data = dr.get("data", [])
                if detail_data and isinstance(detail_data[0], (list, tuple)):
                    rc = dr.get("columns") or detail_columns
                    if rc and len(rc) == len(detail_data[0]):
                        detail_data = [dict(zip(rc, row)) for row in detail_data]
                    else:
                        detail_data = [dict(zip(detail_columns, row)) for row in detail_data]

        result_data = {"detail_data": detail_data, "columns": detail_columns, "description": description, "params": params, "intent": "pendencia_compras"}
        if ctx:
            ctx.update("pendencia_compras", params, result_data, question, view_mode)
            if extra_cols_normalized:
                ctx._extra_columns = extra_cols_normalized
            print(f"[CTX] Atualizado: {ctx}")

        # ========== VIEWS AGREGADAS (quem compra/fornece marca X?) ==========
        agg_view = detect_aggregation_view(normalize(question))
        if agg_view and detail_data:
            marca = params.get("marca", "")
            elapsed = int((time.time() - t0) * 1000)
            if agg_view == "comprador_marca" and marca:
                response = format_comprador_marca(detail_data, marca)
                return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": len(detail_data), "time_ms": elapsed, "_detail_data": detail_data}
            elif agg_view == "fornecedor_marca" and marca:
                response = format_fornecedor_marca(detail_data, marca)
                return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": len(detail_data), "time_ms": elapsed, "_detail_data": detail_data}

        # ========== FILTROS (LLM ou pattern-based) ==========
        # Prioridade: LLM filters > inline pattern filters
        active_filters = llm_filters if llm_filters else detect_filter_request(normalize(question), tokenize(question))
        filter_source = "LLM" if llm_filters else "pattern"

        if active_filters and detail_data:
            # Guardar meta antes de apply_filters
            has_top = "_top" in active_filters
            top_n = active_filters.get("_top", 0)
            sort_key = active_filters.get("_sort", "")
            filter_fields = {k: v for k, v in active_filters.items() if not k.startswith("_")}
            fn_fields = {k: v for k, v in active_filters.items() if k.startswith("_fn_")}

            filtered = apply_filters(list(detail_data), dict(active_filters))
            if filtered:
                print(f"[SMART] Filtro ({filter_source}): {active_filters} -> {len(filtered)}/{len(detail_data)} registros")

                # Construir label do filtro
                filter_parts = []
                if filter_fields:
                    filter_parts.append(", ".join(str(v) for v in filter_fields.values()))
                for fn_key, fn_field in fn_fields.items():
                    fn_name = fn_key.replace("_fn_", "")
                    if fn_name == "empty":
                        filter_parts.append(f"sem {fn_field.lower().replace('_', ' ')}")
                    elif fn_name == "not_empty":
                        filter_parts.append(f"com {fn_field.lower().replace('_', ' ')}")
                    elif fn_name in ("maior", "menor") and ":" in str(fn_field):
                        campo, val = str(fn_field).split(":", 1)
                        op = "acima de" if fn_name == "maior" else "abaixo de"
                        filter_parts.append(f"{campo.lower().replace('_', ' ')} {op} {val}")
                if sort_key:
                    sort_names = {"DIAS_ABERTO_DESC": "mais atrasado", "VLR_PENDENTE_DESC": "maior valor",
                                  "VLR_PENDENTE_ASC": "menor valor", "DT_PEDIDO_DESC": "pedido mais recente",
                                  "DT_PEDIDO_ASC": "pedido mais antigo",
                                  "PREVISAO_ENTREGA_DESC": "maior previsao de entrega",
                                  "PREVISAO_ENTREGA_ASC": "menor previsao de entrega",
                                  "QTD_PENDENTE_DESC": "maior quantidade"}
                    filter_parts.append(sort_names.get(sort_key, sort_key.lower().replace("_", " ")))
                filter_label = " | ".join(p for p in filter_parts if p)

                # Se view=pedidos e tem sort/top, agrupar por PEDIDO antes de aplicar top
                if view_mode == "pedidos" and top_n and sort_key:
                    # Pegar o pedido do primeiro item (ja esta ordenado)
                    top_pedido = str(filtered[0].get("PEDIDO", ""))
                    # Buscar TODOS os itens desse pedido nos dados originais
                    pedido_items = [r for r in detail_data if isinstance(r, dict) and str(r.get("PEDIDO", "")) == top_pedido]
                    if pedido_items:
                        filtered = pedido_items
                        print(f"[SMART] Pedido view: pedido {top_pedido} tem {len(pedido_items)} itens")

                # Top 1 + view pedidos = mostrar o PEDIDO completo
                if top_n == 1 and view_mode == "pedidos" and len(filtered) >= 1:
                    pedido_num = str(filtered[0].get("PEDIDO", "?"))
                    fornecedor = filtered[0].get("FORNECEDOR", "?")
                    dt_pedido = filtered[0].get("DT_PEDIDO", "?")
                    previsao = filtered[0].get("PREVISAO_ENTREGA", "?")
                    confirmado = filtered[0].get("CONFIRMADO", "?")
                    status = filtered[0].get("STATUS_ENTREGA", "?")
                    dias = int(filtered[0].get("DIAS_ABERTO", 0) or 0)

                    total_vlr = sum(float(r.get("VLR_PENDENTE", 0) or 0) for r in filtered)
                    total_itens = len(filtered)
                    total_qtd = sum(int(r.get("QTD_PENDENTE", 0) or 0) for r in filtered)

                    response = f"\U0001f50d **{filter_label.title() if filter_label else 'Resultado'}** de **{description.title()}**:\n\n"
                    response += f"| Campo | Valor |\n|---|---|\n"
                    response += f"| **Pedido** | {pedido_num} |\n"
                    response += f"| **Fornecedor** | {fornecedor} |\n"
                    response += f"| **Data Pedido** | {dt_pedido} |\n"
                    response += f"| **Previsao Entrega** | {previsao} |\n"
                    response += f"| **Confirmado** | {confirmado} |\n"
                    response += f"| **Status** | {status} |\n"
                    response += f"| **Dias em Aberto** | {dias} dias |\n"
                    response += f"| **Itens** | {total_itens} |\n"
                    response += f"| **Qtd. Pendente** | {fmt_num(total_qtd)} |\n"
                    response += f"| **Valor Pendente** | R$ {fmt_num(total_vlr)} |\n\n"

                    # Listar itens do pedido
                    if total_itens > 1:
                        response += f"**Itens do pedido {pedido_num}:**\n\n"
                        response += "| Produto | Marca | Qtd | Valor |\n|---|---|---|---|\n"
                        for r in filtered:
                            prod = str(r.get("PRODUTO", "?"))[:40]
                            marca_i = r.get("MARCA", "")
                            qtd_i = int(r.get("QTD_PENDENTE", 0) or 0)
                            vlr_i = float(r.get("VLR_PENDENTE", 0) or 0)
                            response += f"| {prod} | {marca_i} | {fmt_num(qtd_i)} | R$ {fmt_num(vlr_i)} |\n"

                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": total_itens, "time_ms": elapsed, "_detail_data": filtered}

                # Top 1 + view itens = mostrar 1 item (tabela vertical)
                elif top_n == 1 and len(filtered) == 1:
                    r = filtered[0]
                    response = f"\U0001f50d **{filter_label.title() if filter_label else 'Resultado'}** de **{description.title()}**:\n\n"
                    response += f"| Campo | Valor |\n|---|---|\n"
                    response += f"| **Pedido** | {r.get('PEDIDO', '?')} |\n"
                    if r.get("FORNECEDOR"): response += f"| **Fornecedor** | {r.get('FORNECEDOR')} |\n"
                    response += f"| **Produto** | {r.get('PRODUTO', '?')} |\n"
                    if r.get("MARCA"): response += f"| **Marca** | {r.get('MARCA')} |\n"
                    response += f"| **Qtd. Pendente** | {fmt_num(int(r.get('QTD_PENDENTE', 0) or 0))} |\n"
                    response += f"| **Valor Pendente** | R$ {fmt_num(float(r.get('VLR_PENDENTE', 0) or 0))} |\n"
                    response += f"| **Dias em Aberto** | {int(r.get('DIAS_ABERTO', 0) or 0)} dias |\n"
                    response += f"| **Status** | {r.get('STATUS_ENTREGA', '?')} |\n"
                    if r.get("PREVISAO_ENTREGA"): response += f"| **Previsao Entrega** | {r.get('PREVISAO_ENTREGA')} |\n"
                    if r.get("CONFIRMADO"): response += f"| **Confirmado** | {r.get('CONFIRMADO')} |\n"
                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": 1, "time_ms": elapsed, "_detail_data": filtered}
                else:
                    # Recalcular KPIs com dados filtrados
                    kpis_data = [{
                        "QTD_PEDIDOS": len(set(str(r.get("PEDIDO", "")) for r in filtered if isinstance(r, dict))),
                        "QTD_ITENS": len(filtered),
                        "VLR_PENDENTE": sum(float(r.get("VLR_PENDENTE", 0) or 0) for r in filtered if isinstance(r, dict)),
                    }]
                    detail_data = filtered
                    desc_filtered = f"{description} ({filter_label})" if filter_label else description
                    fallback_response = format_pendencia_response(kpis_data, detail_data, desc_filtered, params, "itens", extra_columns=extra_cols_normalized)
                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": fallback_response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": len(filtered), "time_ms": elapsed, "_detail_data": filtered}
            else:
                # Filtro retornou 0 resultados - avisar usuario
                print(f"[SMART] Filtro ({filter_source}): 0 resultados")
                filter_parts = []
                for k, v in filter_fields.items():
                    filter_parts.append(str(v))
                for fn_key, fn_field in fn_fields.items():
                    fn_name = fn_key.replace("_fn_", "")
                    if fn_name == "empty":
                        filter_parts.append(f"{fn_field} vazio")
                    elif fn_name in ("maior", "menor") and ":" in str(fn_field):
                        campo, val = str(fn_field).split(":", 1)
                        op = "acima de" if fn_name == "maior" else "abaixo de"
                        filter_parts.append(f"{campo} {op} {val}")
                filter_label = ", ".join(filter_parts) if filter_parts else "filtro aplicado"
                response = f"\U0001f4cb **{description.title()}**\n\n"
                response += f"\U0001f914 Nenhum item encontrado com **{filter_label}**.\n\n"
                response += f"Os {len(detail_data)} itens disponiveis tem os seguintes status: "
                statuses = set(str(r.get("STATUS_ENTREGA", "?")) for r in detail_data if isinstance(r, dict))
                response += ", ".join(f"**{s}**" for s in sorted(statuses)) + "."
                elapsed = int((time.time() - t0) * 1000)
                return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": 0, "time_ms": elapsed, "_detail_data": detail_data}

        fallback_response = format_pendencia_response(kpis_data, detail_data, description, params, view_mode, extra_columns=extra_cols_normalized)

        # Narrator: LLM explica os dados naturalmente
        if USE_LLM_NARRATOR and qtd > 0:
            summary = build_pendencia_summary(kpis_data, detail_data, params)
            narration = await llm_narrate(question, summary, "")
            if narration:
                # Monta resposta: analise da LLM + tabela resumida + oferta Excel
                parts = [f"\U0001f4e6 **{description.title()}**\n"]
                parts.append(narration)
                # Adicionar tabela resumida (sem KPIs, a LLM ja falou)
                table_lines = fallback_response.split("\n")
                table_start = next((i for i, l in enumerate(table_lines) if l.startswith("|")), None)
                if table_start is not None:
                    table_section = "\n".join(table_lines[table_start:])
                    parts.append(f"\n{table_section}")
                parts.append(f"\n\U0001f4e5 **Quer que eu gere um arquivo Excel com todos os {fmt_num(int((kpis_data[0] if kpis_data else {}).get('QTD_ITENS', 0) or 0))} itens?**")
                response = "\n".join(parts)
            else:
                response = fallback_response
        else:
            response = fallback_response

        elapsed = int((time.time() - t0) * 1000)
        return {
            "response": response,
            "tipo": "consulta_banco",
            "query_executed": sql_kpis[:200] + "...",
            "query_results": qtd,
            "time_ms": elapsed,
            "_detail_data": detail_data,
            "_visible_columns": extra_cols_normalized,
        }

    # ---- ESTOQUE ----
    async def _handle_estoque(self, question, user_context, t0, params=None, ctx=None):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        # Merge com contexto se disponivel
        if ctx and not (params.get("codprod") or params.get("produto_nome") or params.get("marca")):
            params = ctx.merge_params(params)
        print(f"[SMART] Estoque params: {params}")
        q_norm = normalize(question)
        is_critico = any(w in q_norm for w in ["critico", "baixo", "zerado", "minimo", "acabando", "faltando"])

        if params.get("codprod"):
            sql = f"SELECT EMP.NOMEFANTASIA AS EMPRESA, E.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA, NVL(PRO.CARACTERISTICAS,'') AS APLICACAO, NVL(E.ESTOQUE,0) AS ESTOQUE, NVL(E.ESTMIN,0) AS ESTMIN FROM TGFEST E JOIN TGFPRO PRO ON PRO.CODPROD=E.CODPROD LEFT JOIN TGFMAR MAR ON MAR.CODIGO=PRO.CODMARCA LEFT JOIN TSIEMP EMP ON EMP.CODEMP=E.CODEMP WHERE E.CODPROD={params['codprod']} AND E.CODLOCAL=0 AND NVL(E.ATIVO,'S')='S' ORDER BY EMP.NOMEFANTASIA"
            dcols = ["EMPRESA","CODPROD","PRODUTO","MARCA","APLICACAO","ESTOQUE","ESTMIN"]
        elif params.get("produto_nome"):
            sql = f"SELECT EMP.NOMEFANTASIA AS EMPRESA, E.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA, NVL(PRO.CARACTERISTICAS,'') AS APLICACAO, NVL(E.ESTOQUE,0) AS ESTOQUE, NVL(E.ESTMIN,0) AS ESTMIN FROM TGFEST E JOIN TGFPRO PRO ON PRO.CODPROD=E.CODPROD LEFT JOIN TGFMAR MAR ON MAR.CODIGO=PRO.CODMARCA LEFT JOIN TSIEMP EMP ON EMP.CODEMP=E.CODEMP WHERE UPPER(PRO.DESCRPROD) LIKE UPPER('%{params['produto_nome']}%') AND E.CODLOCAL=0 AND NVL(E.ATIVO,'S')='S' AND NVL(E.ESTOQUE,0)>0 ORDER BY E.ESTOQUE DESC"
            dcols = ["EMPRESA","CODPROD","PRODUTO","MARCA","APLICACAO","ESTOQUE","ESTMIN"]
        elif is_critico or params.get("marca"):
            we = f"AND UPPER(MAR.DESCRICAO) LIKE UPPER('%{params['marca']}%')" if params.get("marca") else ""
            sql = f"SELECT E.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA, SUM(NVL(E.ESTOQUE,0)) AS ESTOQUE, MAX(NVL(E.ESTMIN,0)) AS ESTMIN FROM TGFEST E JOIN TGFPRO PRO ON PRO.CODPROD=E.CODPROD LEFT JOIN TGFMAR MAR ON MAR.CODIGO=PRO.CODMARCA WHERE E.CODLOCAL=0 AND NVL(E.ATIVO,'S')='S' AND NVL(E.ESTMIN,0)>0 {we} GROUP BY E.CODPROD, PRO.DESCRPROD, MAR.DESCRICAO HAVING SUM(NVL(E.ESTOQUE,0))<=MAX(NVL(E.ESTMIN,0)) ORDER BY SUM(NVL(E.ESTOQUE,0))"
            dcols = ["CODPROD","PRODUTO","MARCA","ESTOQUE","ESTMIN"]
        else:
            return {"response": "\U0001f4cb Para consultar estoque, me diga:\n\n- O **codigo** do produto: *\"estoque do produto 133346\"*\n- O **nome** da peca: *\"estoque da correia ventilador\"*\n- **Estoque critico**: *\"produtos com estoque critico\"*", "tipo": "info", "query_executed": None, "query_results": None}

        result = await self.executor.execute(sql)
        if not result.get("success"):
            return {"response": f"Erro ao consultar estoque: {result.get('error','?')}", "tipo": "consulta_banco", "query_executed": sql[:200], "query_results": 0}
        data = result.get("data", [])
        if data and isinstance(data[0], (list, tuple)):
            rc = result.get("columns") or dcols
            data = [dict(zip(rc if rc and len(rc)==len(data[0]) else dcols, row)) for row in data]

        result_data = {"detail_data": data, "columns": dcols, "description": "estoque", "params": params, "intent": "estoque"}
        if ctx:
            ctx.update("estoque", params, result_data, question)
        fallback_response = format_estoque_response(data, params)

        if USE_LLM_NARRATOR and data:
            summary = build_estoque_summary(data, params)
            narration = await llm_narrate(question, summary, "")
            if narration:
                table_lines = fallback_response.split("\n")
                table_start = next((i for i, l in enumerate(table_lines) if l.startswith("|")), None)
                parts = [narration]
                if table_start is not None:
                    parts.append(f"\n{''.join(table_lines[table_start:])}")
                response = "\n".join(parts)
            else:
                response = fallback_response
        else:
            response = fallback_response

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql[:200] + "...", "query_results": len(data), "time_ms": elapsed, "_detail_data": data}

    # ---- VENDAS ----
    async def _handle_vendas(self, question, user_context, t0, params=None, ctx=None):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        # Merge com contexto se disponivel
        if ctx and not (params.get("marca") or params.get("empresa")):
            params = ctx.merge_params(params)
        print(f"[SMART] Vendas params: {params}")

        periodo = params.get("periodo", "mes")
        periodo_nome = PERIODO_NOMES.get(periodo, "este mes")
        pf = _build_periodo_filter(params)
        wv = _build_vendas_where(params, user_context)
        has_marca = bool(params.get("marca"))

        # Descricao para titulo/contexto
        desc_parts = [periodo_nome]
        if params.get("vendedor"):
            desc_parts.append(f"vendedor {params['vendedor']}")
        if params.get("marca"):
            desc_parts.append(f"marca {params['marca']}")
        if params.get("empresa"):
            desc_parts.append(f"{EMPRESA_DISPLAY.get(params['empresa'], params['empresa'])}")
        description = " | ".join(desc_parts)

        # ---- SQL KPIs (V+D para separar vendas/devoluções) ----
        if has_marca:
            # Com marca: usar ITE.VLRTOT (nivel item) para evitar contar valor de outras marcas
            sql_kpis = f"""SELECT
                COUNT(DISTINCT CASE WHEN C.TIPMOV = 'V' THEN C.NUNOTA END) AS QTD_VENDAS,
                NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN ITE.VLRTOT ELSE 0 END), 0) AS VLR_VENDAS,
                NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN ITE.VLRTOT ELSE 0 END), 0) AS VLR_DEVOLUCAO,
                NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN ITE.VLRTOT ELSE 0 END), 0)
                  - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN ITE.VLRTOT ELSE 0 END), 0) AS FATURAMENTO,
                NVL(ROUND(AVG(CASE WHEN C.TIPMOV = 'V' THEN ITE.VLRTOT END), 2), 0) AS TICKET_MEDIO,
                NVL(ROUND(AVG(CASE WHEN C.TIPMOV = 'V' THEN C.AD_MARGEM END), 2), 0) AS MARGEM_MEDIA,
                NVL(SUM(C.AD_VLRCOMINT), 0) AS COMISSAO_TOTAL
            FROM TGFCAB C
            JOIN TGFITE ITE ON ITE.NUNOTA = C.NUNOTA
            JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
            LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
            LEFT JOIN TGFVEN VEN ON VEN.CODVEND = C.CODVEND
            LEFT JOIN TSIEMP EMP ON EMP.CODEMP = C.CODEMP
            LEFT JOIN TGFPAR PAR ON PAR.CODPARC = C.CODPARC
            WHERE C.TIPMOV IN ('V', 'D')
                AND C.CODTIPOPER IN (1100, 1101)
                AND C.STATUSNOTA <> 'C'
                {pf} {wv}"""
        else:
            sql_kpis = f"""SELECT
                SUM(CASE WHEN C.TIPMOV = 'V' THEN 1 ELSE 0 END) AS QTD_VENDAS,
                NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.VLRNOTA ELSE 0 END), 0) AS VLR_VENDAS,
                NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.VLRNOTA ELSE 0 END), 0) AS VLR_DEVOLUCAO,
                NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.VLRNOTA ELSE 0 END), 0)
                  - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.VLRNOTA ELSE 0 END), 0) AS FATURAMENTO,
                NVL(ROUND(AVG(CASE WHEN C.TIPMOV = 'V' THEN C.VLRNOTA END), 2), 0) AS TICKET_MEDIO,
                NVL(ROUND(AVG(CASE WHEN C.TIPMOV = 'V' THEN C.AD_MARGEM END), 2), 0) AS MARGEM_MEDIA,
                NVL(SUM(C.AD_VLRCOMINT), 0) AS COMISSAO_TOTAL
            FROM TGFCAB C
            LEFT JOIN TGFVEN VEN ON VEN.CODVEND = C.CODVEND
            LEFT JOIN TSIEMP EMP ON EMP.CODEMP = C.CODEMP
            LEFT JOIN TGFPAR PAR ON PAR.CODPARC = C.CODPARC
            WHERE C.TIPMOV IN ('V', 'D')
                AND C.CODTIPOPER IN (1100, 1101)
                AND C.STATUSNOTA <> 'C'
                {pf} {wv}"""

        # ---- SQL Top Vendedores (com margem e devoluções) ----
        sql_top = f"""SELECT
            NVL(VEN.APELIDO, 'SEM VENDEDOR') AS VENDEDOR,
            SUM(CASE WHEN C.TIPMOV = 'V' THEN 1 ELSE 0 END) AS QTD,
            NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.VLRNOTA ELSE 0 END), 0) AS VLR_VENDAS,
            NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.VLRNOTA ELSE 0 END), 0) AS VLR_DEVOLUCAO,
            NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.VLRNOTA ELSE 0 END), 0)
              - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.VLRNOTA ELSE 0 END), 0) AS FATURAMENTO,
            NVL(ROUND(AVG(CASE WHEN C.TIPMOV = 'V' THEN C.AD_MARGEM END), 2), 0) AS MARGEM_MEDIA
        FROM TGFCAB C
        LEFT JOIN TGFVEN VEN ON VEN.CODVEND = C.CODVEND
        LEFT JOIN TSIEMP EMP ON EMP.CODEMP = C.CODEMP
        LEFT JOIN TGFPAR PAR ON PAR.CODPARC = C.CODPARC
        WHERE C.TIPMOV IN ('V', 'D')
            AND C.CODTIPOPER IN (1100, 1101)
            AND C.STATUSNOTA <> 'C'
            {pf} {wv}
        GROUP BY VEN.APELIDO
        ORDER BY (NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.VLRNOTA ELSE 0 END), 0)
                  - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.VLRNOTA ELSE 0 END), 0)) DESC"""

        # ---- SQL Detail (para follow-ups + Excel) ----
        sql_detail = f"""SELECT
            C.NUNOTA,
            TO_CHAR(C.DTNEG, 'DD/MM/YYYY') AS DATA,
            C.TIPMOV,
            NVL(VEN.APELIDO, 'SEM VENDEDOR') AS VENDEDOR,
            NVL(PAR.NOMEPARC, '?') AS CLIENTE,
            C.VLRNOTA AS VALOR,
            NVL(C.AD_MARGEM, 0) AS MARGEM,
            NVL(C.AD_VLRCOMINT, 0) AS COMISSAO,
            NVL(EMP.NOMEFANTASIA, '?') AS EMPRESA
        FROM TGFCAB C
        LEFT JOIN TGFVEN VEN ON VEN.CODVEND = C.CODVEND
        LEFT JOIN TSIEMP EMP ON EMP.CODEMP = C.CODEMP
        LEFT JOIN TGFPAR PAR ON PAR.CODPARC = C.CODPARC
        WHERE C.TIPMOV IN ('V', 'D')
            AND C.CODTIPOPER IN (1100, 1101)
            AND C.STATUSNOTA <> 'C'
            {pf} {wv}
        ORDER BY C.DTNEG DESC
        FETCH FIRST 500 ROWS ONLY"""

        # ---- Executar KPIs ----
        kr = await self.executor.execute(sql_kpis)
        if not kr.get("success"):
            return {"response": f"Erro ao consultar vendas: {kr.get('error','?')}", "tipo": "consulta_banco", "query_executed": sql_kpis[:200], "query_results": 0}
        kd = kr.get("data", [])
        if kd and isinstance(kd[0], (list, tuple)):
            cols = kr.get("columns") or ["QTD_VENDAS", "VLR_VENDAS", "VLR_DEVOLUCAO", "FATURAMENTO", "TICKET_MEDIO", "MARGEM_MEDIA", "COMISSAO_TOTAL"]
            kd = [dict(zip(cols, row)) for row in kd]
        kpi_row = kd[0] if kd else {}

        # ---- Executar Top Vendedores ----
        tr = await self.executor.execute(sql_top)
        td = []
        if tr.get("success"):
            td = tr.get("data", [])
            if td and isinstance(td[0], (list, tuple)):
                tc = tr.get("columns") or ["VENDEDOR", "QTD", "VLR_VENDAS", "VLR_DEVOLUCAO", "FATURAMENTO", "MARGEM_MEDIA"]
                td = [dict(zip(tc, row)) for row in td]

        # ---- Executar Detail (para follow-ups e Excel) ----
        detail_data = []
        detail_columns = ["NUNOTA", "DATA", "TIPMOV", "VENDEDOR", "CLIENTE", "VALOR", "MARGEM", "COMISSAO", "EMPRESA"]
        qtd_vendas = int(kpi_row.get("QTD_VENDAS", 0) or 0)
        if qtd_vendas > 0:
            dr = await self.executor.execute(sql_detail)
            if dr.get("success"):
                detail_data = dr.get("data", [])
                if detail_data and isinstance(detail_data[0], (list, tuple)):
                    rc = dr.get("columns") or detail_columns
                    if rc and len(rc) == len(detail_data[0]):
                        detail_data = [dict(zip(rc, row)) for row in detail_data]
                    else:
                        detail_data = [dict(zip(detail_columns, row)) for row in detail_data]

        # ---- Formatar resposta ----
        fallback_response = format_vendas_response(kpi_row, description)
        if td:
            has_dev = any(float(row.get("VLR_DEVOLUCAO", 0) or 0) > 0 for row in td[:10] if isinstance(row, dict))
            margem_col = any(float(row.get("MARGEM_MEDIA", 0) or 0) > 0 for row in td[:5] if isinstance(row, dict))
            if has_dev:
                fallback_response += "\n**Top vendedores:**\n| Vendedor | Notas | Vendas | Devoluções | Líquido | Margem |\n|----------|-------|--------|------------|---------|--------|\n"
                for row in td[:10]:
                    if isinstance(row, dict):
                        mg = float(row.get("MARGEM_MEDIA", 0) or 0)
                        fallback_response += (
                            f"| {str(row.get('VENDEDOR','?'))[:20]} | {fmt_num(row.get('QTD',0))} | "
                            f"{fmt_brl(row.get('VLR_VENDAS',0))} | {fmt_brl(row.get('VLR_DEVOLUCAO',0))} | "
                            f"{fmt_brl(row.get('FATURAMENTO',0))} | {mg:.1f}% |\n"
                        )
            elif margem_col:
                fallback_response += "\n**Top vendedores:**\n| Vendedor | Notas | Faturamento | Margem |\n|----------|-------|-------------|--------|\n"
                for row in td[:10]:
                    if isinstance(row, dict):
                        mg = float(row.get("MARGEM_MEDIA", 0) or 0)
                        fallback_response += f"| {str(row.get('VENDEDOR','?'))[:20]} | {fmt_num(row.get('QTD',0))} | {fmt_brl(row.get('FATURAMENTO',0))} | {mg:.1f}% |\n"
            else:
                fallback_response += "\n**Top vendedores:**\n| Vendedor | Notas | Faturamento |\n|----------|-------|-------------|\n"
                for row in td[:10]:
                    if isinstance(row, dict):
                        fallback_response += f"| {str(row.get('VENDEDOR','?'))[:20]} | {fmt_num(row.get('QTD',0))} | {fmt_brl(row.get('FATURAMENTO',0))} |\n"

        # ---- Narracao ----
        if USE_LLM_NARRATOR and qtd_vendas > 0:
            summary = build_vendas_summary(kpi_row, td, description)
            narration = await llm_narrate(question, summary, "")
            if narration:
                # Montar tabela de top vendedores
                table_lines = fallback_response.split("\n")
                table_start = next((i for i, l in enumerate(table_lines) if l.startswith("|")), None)
                parts = [narration]
                if table_start is not None:
                    parts.append("\n" + "\n".join(table_lines[table_start:]))
                response = "\n".join(parts)
            else:
                response = fallback_response
        else:
            response = fallback_response

        # ---- Salvar contexto ----
        result_data = {
            "detail_data": detail_data,
            "columns": detail_columns,
            "description": f"vendas - {description}",
            "params": params,
            "intent": "vendas",
        }
        if ctx:
            ctx.update("vendas", params, result_data, question)
            print(f"[CTX] Vendas atualizado: {ctx}")

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": qtd_vendas, "time_ms": elapsed, "_detail_data": detail_data}

    # ---- RASTREIO DE PEDIDO DE VENDA ----
    # Traducao de status para linguagem do vendedor
    CONF_STATUS_MAP = {
        "AL": "Aguardando liberacao p/ conferencia",
        "AC": "Na fila de conferencia",
        "A": "Sendo conferido agora",
        "Z": "Aguardando finalizacao",
        "F": "Conferencia OK",
        "D": "Conferencia com divergencia",
        "R": "Aguardando recontagem",
        "RA": "Recontagem em andamento",
        "RF": "Recontagem OK",
        "RD": "Recontagem com divergencia",
        "C": "Aguardando liberacao de corte",
    }
    WMS_STATUS_MAP = {
        -1: "Nao enviado p/ separacao",
        0: "Na fila de separacao",
        1: "Enviado p/ separacao",
        2: "Separando agora",
        3: "Separado, aguardando conferencia",
        4: "Sendo conferido",
        9: "Conferencia OK, pronto p/ faturar",
        10: "Aguardando conferencia (pos-separacao)",
        12: "Conferencia com divergencia",
        13: "Parcialmente conferido",
        16: "Concluido",
        17: "Aguardando conferencia de volumes",
        7: "Pedido totalmente cortado",
        8: "Pedido parcialmente cortado",
        100: "Cancelado",
    }

    async def _handle_rastreio_pedido(self, question, user_context, t0, params=None, ctx=None):
        """Rastreia um pedido de venda: status + itens + compras vinculadas."""
        params = params or {}

        # Extrair NUNOTA da pergunta
        nunota = params.get("nunota")
        if not nunota:
            # Tentar extrair numero grande da pergunta (NUNOTA geralmente > 100000)
            nums = re.findall(r'\b(\d{4,})\b', question)
            if nums:
                nunota = int(nums[0])

        if not nunota:
            # Sem numero: listar pedidos pendentes do vendedor
            user = (user_context or {}).get("user", "")
            codvend = (user_context or {}).get("codvend")

            where_vend = ""
            if codvend:
                where_vend = f"AND C.CODVEND = {int(codvend)}"

            sql = f"""SELECT C.NUNOTA, C.NUMNOTA, TO_CHAR(C.DTNEG, 'DD/MM/YYYY') AS DTNEG,
                P.NOMEPARC AS CLIENTE, C.VLRNOTA, C.STATUSNOTA, C.PENDENTE,
                C.STATUSCONFERENCIA, C.SITUACAOWMS
            FROM TGFCAB C
            JOIN TGFPAR P ON C.CODPARC = P.CODPARC
            WHERE C.TIPMOV = 'P'
                AND C.PENDENTE = 'S'
                AND C.STATUSNOTA <> 'C'
                AND C.CODTIPOPER IN (1001, 1007, 1012)
                {where_vend}
            ORDER BY C.DTNEG DESC"""

            result = await self.executor.execute(sql)
            if not result.get("success") or not result.get("data"):
                return {"response": "Nenhum pedido de venda pendente encontrado.", "tipo": "consulta_banco",
                        "query_executed": sql[:200], "query_results": 0, "time_ms": int((time.time() - t0) * 1000)}

            data = result["data"]
            if data and isinstance(data[0], (list, tuple)):
                cols = result.get("columns") or ["NUNOTA","NUMNOTA","DTNEG","CLIENTE","VLRNOTA","STATUSNOTA","PENDENTE","STATUSCONFERENCIA","SITUACAOWMS"]
                data = [dict(zip(cols, row)) for row in data]

            response = f"**Pedidos de venda pendentes** ({len(data)} encontrados):\n\n"
            response += "| Pedido | Data | Cliente | Valor | Conferencia |\n|---|---|---|---|---|\n"
            for row in data[:20]:
                nunota_r = row.get("NUNOTA", "?")
                dt = row.get("DTNEG", "?")
                cli = str(row.get("CLIENTE", ""))[:30]
                vlr = float(row.get("VLRNOTA", 0) or 0)
                conf = str(row.get("STATUSCONFERENCIA", "") or "")
                conf_desc = self.CONF_STATUS_MAP.get(conf, conf or "-")
                response += f"| {nunota_r} | {dt} | {cli} | R$ {vlr:,.2f} | {conf_desc} |\n"

            if len(data) > 20:
                response += f"\n*...e mais {len(data)-20} pedidos.*"

            elapsed = int((time.time() - t0) * 1000)
            return {"response": response, "tipo": "consulta_banco", "query_executed": sql[:200],
                    "query_results": len(data), "time_ms": elapsed}

        # ========== COM NUNOTA: rastreio completo ==========
        nunota = int(nunota)

        # ETAPA 1: Status do pedido
        sql_status = f"""SELECT
            C.NUNOTA, C.NUMNOTA, TO_CHAR(C.DTNEG, 'DD/MM/YYYY') AS DTNEG,
            P.NOMEPARC AS CLIENTE, C.VLRNOTA, C.TIPMOV,
            C.STATUSNOTA,
            CASE C.STATUSNOTA WHEN 'L' THEN 'Liberada' WHEN 'P' THEN 'Pendente' WHEN 'A' THEN 'Em Atendimento' ELSE C.STATUSNOTA END AS STATUS_DESC,
            C.PENDENTE,
            C.STATUSNFE,
            CASE C.STATUSNFE WHEN 'A' THEN 'NFe Autorizada' WHEN 'I' THEN 'NFe Enviada' WHEN 'R' THEN 'NFe Rejeitada' WHEN 'M' THEN 'Sem NFe' ELSE 'Nao enviada' END AS STATUS_NFE_DESC,
            NVL(C.STATUSCONFERENCIA, '') AS STATUSCONFERENCIA,
            NVL(C.LIBCONF, '') AS LIBCONF,
            NVL(C.SITUACAOWMS, -1) AS SITUACAOWMS,
            NVL(V.APELIDO, '') AS VENDEDOR,
            C.CODEMP
        FROM TGFCAB C
        JOIN TGFPAR P ON C.CODPARC = P.CODPARC
        LEFT JOIN TGFVEN V ON C.CODVEND = V.CODVEND
        WHERE C.NUNOTA = {nunota}"""

        r1 = await self.executor.execute(sql_status)
        if not r1.get("success") or not r1.get("data"):
            return {"response": f"Pedido **{nunota}** nao encontrado no sistema.",
                    "tipo": "consulta_banco", "query_executed": sql_status[:200],
                    "query_results": 0, "time_ms": int((time.time() - t0) * 1000)}

        d1 = r1["data"]
        if d1 and isinstance(d1[0], (list, tuple)):
            cols = r1.get("columns") or ["NUNOTA","NUMNOTA","DTNEG","CLIENTE","VLRNOTA","TIPMOV","STATUSNOTA","STATUS_DESC","PENDENTE","STATUSNFE","STATUS_NFE_DESC","STATUSCONFERENCIA","LIBCONF","SITUACAOWMS","VENDEDOR","CODEMP"]
            d1 = [dict(zip(cols, row)) for row in d1]
        cab = d1[0]

        # Traduzir status
        conf_code = str(cab.get("STATUSCONFERENCIA", "") or "")
        conf_desc = self.CONF_STATUS_MAP.get(conf_code, conf_code or "N/A")
        wms_code = int(cab.get("SITUACAOWMS", -1) or -1)
        wms_desc = self.WMS_STATUS_MAP.get(wms_code, f"Codigo {wms_code}")
        codemp = cab.get("CODEMP", 1)

        # Montar cabecalho
        response = f"**Pedido #{nunota}** — {cab.get('CLIENTE', '?')}\n\n"
        response += "| Campo | Status |\n|---|---|\n"
        response += f"| **Data** | {cab.get('DTNEG', '?')} |\n"
        response += f"| **Valor** | R$ {float(cab.get('VLRNOTA', 0) or 0):,.2f} |\n"
        response += f"| **Status Nota** | {cab.get('STATUS_DESC', '?')} |\n"
        response += f"| **NFe** | {cab.get('STATUS_NFE_DESC', '?')} |\n"
        response += f"| **Conferencia** | {conf_desc} |\n"
        response += f"| **WMS** | {wms_desc} |\n"
        if cab.get("VENDEDOR"):
            response += f"| **Vendedor** | {cab['VENDEDOR']} |\n"
        response += f"| **Pendente** | {'Sim' if cab.get('PENDENTE') == 'S' else 'Nao'} |\n"

        # ETAPA 2: Itens do pedido com estoque
        sql_itens = f"""SELECT
            ITE.SEQUENCIA, PRO.CODPROD, PRO.DESCRPROD AS PRODUTO,
            NVL(MAR.DESCRICAO, '') AS MARCA,
            ITE.QTDNEG AS QTD_VENDIDA,
            NVL(EST.ESTOQUE, 0) AS ESTOQUE,
            NVL(EST.RESERVADO, 0) AS RESERVADO,
            NVL(EST.ESTOQUE, 0) - NVL(EST.RESERVADO, 0) AS DISPONIVEL,
            CASE
                WHEN NVL(EST.ESTOQUE,0) - NVL(EST.RESERVADO,0) >= ITE.QTDNEG THEN 'DISPONIVEL'
                WHEN NVL(EST.ESTOQUE,0) > 0 THEN 'PARCIAL'
                ELSE 'SEM ESTOQUE'
            END AS STATUS_ESTOQUE
        FROM TGFITE ITE
        JOIN TGFPRO PRO ON ITE.CODPROD = PRO.CODPROD
        LEFT JOIN TGFMAR MAR ON PRO.CODMARCA = MAR.CODIGO
        LEFT JOIN (
            SELECT CODPROD, SUM(ESTOQUE) AS ESTOQUE, SUM(RESERVADO) AS RESERVADO
            FROM TGFEST WHERE CODLOCAL = 0 AND TIPO = 'P' AND CODPARC = 0
            GROUP BY CODPROD
        ) EST ON EST.CODPROD = ITE.CODPROD
        WHERE ITE.NUNOTA = {nunota}
        ORDER BY ITE.SEQUENCIA"""

        r2 = await self.executor.execute(sql_itens)
        itens = []
        sem_estoque_prods = []
        if r2.get("success") and r2.get("data"):
            itens_data = r2["data"]
            if itens_data and isinstance(itens_data[0], (list, tuple)):
                cols = r2.get("columns") or ["SEQUENCIA","CODPROD","PRODUTO","MARCA","QTD_VENDIDA","ESTOQUE","RESERVADO","DISPONIVEL","STATUS_ESTOQUE"]
                itens_data = [dict(zip(cols, row)) for row in itens_data]
            itens = itens_data

            response += f"\n**Itens do pedido** ({len(itens)}):\n\n"
            response += "| Produto | Marca | Qtd | Disponivel | Status |\n|---|---|---|---|---|\n"
            for it in itens:
                prod = str(it.get("PRODUTO", ""))[:35]
                marca = str(it.get("MARCA", ""))[:15]
                qtd = int(it.get("QTD_VENDIDA", 0) or 0)
                disp = int(it.get("DISPONIVEL", 0) or 0)
                st = str(it.get("STATUS_ESTOQUE", "?"))
                icon = {"DISPONIVEL": "OK", "PARCIAL": "PARCIAL", "SEM ESTOQUE": "SEM EST."}.get(st, st)
                response += f"| {prod} | {marca} | {qtd} | {disp} | {icon} |\n"

                if st in ("SEM ESTOQUE", "PARCIAL"):
                    sem_estoque_prods.append(int(it.get("CODPROD", 0) or 0))

        # ETAPA 3: Rastrear compras vinculadas (para itens sem estoque)
        if sem_estoque_prods:
            codprods_str = ",".join(str(c) for c in sem_estoque_prods if c > 0)
            if codprods_str:
                sql_compras = f"""SELECT
                    COMPRA.NUNOTA AS PEDIDO_COMPRA,
                    TO_CHAR(COMPRA.DTNEG, 'DD/MM/YYYY') AS DT_COMPRA,
                    FORN.NOMEPARC AS FORNECEDOR,
                    ITEM_COMPRA.CODPROD,
                    PRO.DESCRPROD AS PRODUTO,
                    ITEM_COMPRA.QTDNEG AS QTD_COMPRADA,
                    NVL(VAR_AGG.TOTAL_ATENDIDO, 0) AS QTD_ENTREGUE,
                    ITEM_COMPRA.QTDNEG - NVL(VAR_AGG.TOTAL_ATENDIDO, 0) AS QTD_FALTANDO,
                    NVL(TO_CHAR(COMPRA.DTPREVENT,'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO,
                    CASE
                        WHEN NVL(VAR_AGG.TOTAL_ATENDIDO,0) >= ITEM_COMPRA.QTDNEG THEN 'ENTREGUE'
                        WHEN NVL(VAR_AGG.TOTAL_ATENDIDO,0) > 0 THEN 'ENTREGA PARCIAL'
                        WHEN COMPRA.DTPREVENT < TRUNC(SYSDATE) THEN 'ATRASADO'
                        WHEN COMPRA.DTPREVENT IS NOT NULL THEN 'AGUARDANDO'
                        ELSE 'SEM PREVISAO'
                    END AS STATUS_COMPRA,
                    NVL(ENTRADA.STATUSCONFERENCIA, '') AS CONF_ENTRADA,
                    NVL(ENTRADA.SITUACAOWMS, -1) AS WMS_ENTRADA
                FROM TGFCAB COMPRA
                JOIN TGFITE ITEM_COMPRA ON COMPRA.NUNOTA = ITEM_COMPRA.NUNOTA
                JOIN TGFPAR FORN ON COMPRA.CODPARC = FORN.CODPARC
                JOIN TGFPRO PRO ON ITEM_COMPRA.CODPROD = PRO.CODPROD
                LEFT JOIN (
                    SELECT V.NUNOTAORIG, V.SEQUENCIAORIG,
                        SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO,
                        MAX(V.NUNOTA) AS ULTIMA_NOTA
                    FROM TGFVAR V
                    JOIN TGFCAB CV ON CV.NUNOTA = V.NUNOTA
                    WHERE CV.STATUSNOTA <> 'C'
                    GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
                ) VAR_AGG ON VAR_AGG.NUNOTAORIG = COMPRA.NUNOTA
                    AND VAR_AGG.SEQUENCIAORIG = ITEM_COMPRA.SEQUENCIA
                LEFT JOIN TGFCAB ENTRADA ON ENTRADA.NUNOTA = VAR_AGG.ULTIMA_NOTA
                WHERE ITEM_COMPRA.CODPROD IN ({codprods_str})
                    AND COMPRA.TIPMOV = 'O'
                    AND COMPRA.CODTIPOPER IN (1301, 1313)
                    AND COMPRA.STATUSNOTA <> 'C'
                    AND COMPRA.PENDENTE = 'S'
                ORDER BY COMPRA.DTNEG DESC"""

                r3 = await self.executor.execute(sql_compras)
                if r3.get("success") and r3.get("data"):
                    compras_data = r3["data"]
                    if compras_data and isinstance(compras_data[0], (list, tuple)):
                        cols = r3.get("columns") or ["PEDIDO_COMPRA","DT_COMPRA","FORNECEDOR","CODPROD","PRODUTO","QTD_COMPRADA","QTD_ENTREGUE","QTD_FALTANDO","PREVISAO","STATUS_COMPRA","CONF_ENTRADA","WMS_ENTRADA"]
                        compras_data = [dict(zip(cols, row)) for row in compras_data]

                    response += f"\n**Compras vinculadas** (itens sem estoque):\n\n"
                    response += "| Produto | Fornecedor | Ped.Compra | Comprado | Entregue | Faltando | Previsao | Status |\n|---|---|---|---|---|---|---|---|\n"
                    for c in compras_data:
                        prod = str(c.get("PRODUTO", ""))[:25]
                        forn = str(c.get("FORNECEDOR", ""))[:20]
                        ped = c.get("PEDIDO_COMPRA", "?")
                        qtd_c = int(c.get("QTD_COMPRADA", 0) or 0)
                        qtd_e = int(c.get("QTD_ENTREGUE", 0) or 0)
                        qtd_f = int(c.get("QTD_FALTANDO", 0) or 0)
                        prev = str(c.get("PREVISAO", "?"))
                        st = str(c.get("STATUS_COMPRA", "?"))

                        # Se tem nota de entrada, mostrar status conferencia
                        conf_e = str(c.get("CONF_ENTRADA", "") or "")
                        if conf_e:
                            conf_txt = self.CONF_STATUS_MAP.get(conf_e, conf_e)
                            st = f"{st} ({conf_txt})"

                        response += f"| {prod} | {forn} | {ped} | {qtd_c} | {qtd_e} | {qtd_f} | {prev} | {st} |\n"

                elif not r3.get("success"):
                    response += f"\n*Erro ao buscar compras vinculadas: {r3.get('error', '?')}*"
                else:
                    response += "\n*Nenhuma compra pendente encontrada para os itens sem estoque.*"

        # Narrar se habilitado
        if USE_LLM_NARRATOR and pool_narrate.available:
            try:
                narr_prompt = f"Resuma em 2-3 frases para o vendedor o status do pedido {nunota}. Dados:\n{response[:800]}"
                narr = await groq_request(pool_narrate, [{"role": "user", "content": narr_prompt}], temperature=0.3, max_tokens=200)
                if narr and narr.get("content"):
                    response = narr["content"].strip() + "\n\n---\n\n" + response
            except Exception:
                pass

        # Salvar contexto
        result_data = {"detail_data": itens, "description": f"rastreio pedido {nunota}", "params": params, "intent": "rastreio_pedido", "nunota": nunota}
        if ctx:
            ctx.update("rastreio_pedido", params, result_data, question)

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": f"Rastreio pedido {nunota}",
                "query_results": len(itens), "time_ms": elapsed}

    # ---- BUSCA POR CODIGO FABRICANTE ----
    async def _handle_busca_fabricante(self, question, user_context, t0, params=None, ctx=None):
        """Busca produto pelo codigo do fabricante (referencia, numfabricante, etc.)."""
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        cod_fab = params.get("codigo_fabricante")
        if not cod_fab:
            return {"response": "Informe o codigo do fabricante para buscar. Ex: *\"HU711/51\"* ou *\"referencia WK 950/21\"*", "tipo": "info", "query_executed": None, "query_results": None}

        print(f"[SMART] Busca fabricante: '{cod_fab}'")

        # Tentar Elastic primeiro (mais rapido, fuzzy)
        if self.elastic:
            elastic_results = await self.elastic.search_products(codigo=cod_fab, limit=10)
            if elastic_results:
                products = [{"codprod": r.get("codprod"), "produto": r.get("descricao",""),
                             "marca": r.get("marca",""), "referencia": r.get("referencia",""),
                             "aplicacao": r.get("aplicacao",""),
                             "campo_match": "elastic"} for r in elastic_results]
                resolved = {"found": True, "products": products, "code_searched": cod_fab}
                print(f"[SMART] Elastic encontrou {len(products)} produtos para '{cod_fab}'")
                response = format_busca_fabricante(resolved)

                if len(products) == 1 and ctx:
                    result_data = {"detail_data": products, "columns": ["codprod", "produto", "marca", "referencia"], "description": f"produto {cod_fab}", "params": params, "intent": "busca_fabricante"}
                    ctx.update("busca_fabricante", params, result_data, question)

                elapsed = int((time.time() - t0) * 1000)
                return {"response": response, "tipo": "consulta_banco", "query_executed": f"elastic: {cod_fab}", "query_results": len(products), "time_ms": elapsed}

        # Fallback SQL: Busca em TGFPRO (campos de referencia)
        resolved = await resolve_manufacturer_code(cod_fab, self.executor)

        # Se nao encontrou em TGFPRO, tenta em AD_TGFPROAUXMMA (auxiliares)
        if not resolved.get("found"):
            aux_result = await buscar_similares_por_codigo(cod_fab, self.executor)
            if aux_result.get("found"):
                response = format_similares(aux_result)
                elapsed = int((time.time() - t0) * 1000)
                return {"response": response, "tipo": "consulta_banco", "query_executed": f"busca auxiliar: {cod_fab}", "query_results": 1, "time_ms": elapsed}

        response = format_busca_fabricante(resolved)

        # Salvar no contexto se encontrou 1 produto
        products = resolved.get("products", [])
        if len(products) == 1 and ctx:
            result_data = {"detail_data": products, "columns": ["codprod", "produto", "marca", "referencia"], "description": f"produto {cod_fab}", "params": params, "intent": "busca_fabricante"}
            ctx.update("busca_fabricante", params, result_data, question)

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": f"busca fabricante: {cod_fab}", "query_results": len(products), "time_ms": elapsed}

    # ---- SIMILARES / CROSS-REFERENCE ----
    async def _handle_similares(self, question, user_context, t0, params=None, ctx=None):
        """Busca codigos auxiliares/similares de um produto."""
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)

        codprod = params.get("codprod")
        cod_fab = params.get("codigo_fabricante")

        if not codprod and not cod_fab:
            return {"response": "Para buscar similares, informe o codigo do produto ou referencia.\nEx: *\"similares do produto 133346\"* ou *\"similares do HU711/51\"*", "tipo": "info", "query_executed": None, "query_results": None}

        # Se tem codigo fabricante mas nao codprod, resolver primeiro
        if not codprod and cod_fab:
            resolved = await resolve_manufacturer_code(cod_fab, self.executor)
            if resolved.get("found"):
                products = resolved.get("products", [])
                if len(products) == 1:
                    codprod = products[0]["codprod"]
                else:
                    # Multiplos produtos: buscar similares pelo texto auxiliar
                    sim = await buscar_similares_por_codigo(cod_fab, self.executor)
                    response = format_similares(sim)
                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": response, "tipo": "consulta_banco", "query_executed": f"similares por codigo: {cod_fab}", "query_results": len(products), "time_ms": elapsed}
            else:
                # Tenta busca por codigo auxiliar direto
                sim = await buscar_similares_por_codigo(cod_fab, self.executor)
                response = format_similares(sim)
                elapsed = int((time.time() - t0) * 1000)
                return {"response": response, "tipo": "consulta_banco", "query_executed": f"similares por codigo: {cod_fab}", "query_results": 1 if sim.get("found") else 0, "time_ms": elapsed}

        print(f"[SMART] Similares: codprod={codprod}")
        sim_data = await buscar_similares(codprod, self.executor)
        response = format_similares(sim_data)

        if ctx and sim_data.get("found"):
            result_data = {"detail_data": sim_data.get("auxiliares", []), "columns": ["codigo", "marca", "observacao"], "description": f"similares produto {codprod}", "params": params, "intent": "similares"}
            ctx.update("similares", params, result_data, question)

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": f"similares: codprod={codprod}", "query_results": len(sim_data.get("auxiliares", [])), "time_ms": elapsed}

    # ---- BUSCA POR APLICACAO/VEICULO ----
    async def _handle_busca_aplicacao(self, question, user_context, t0, params=None, ctx=None):
        """Busca produtos por aplicacao/veiculo usando CARACTERISTICAS."""
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)

        aplicacao = params.get("aplicacao", "")
        if not aplicacao:
            return {"response": "Para buscar por aplicacao, informe o veiculo ou motor.\nEx: *\"pecas para scania r450\"* ou *\"filtros para motor dc13\"*", "tipo": "info", "query_executed": None, "query_results": None}

        # Tentar Elastic primeiro
        if self.elastic:
            elastic_results = await self.elastic.search_products(
                aplicacao=aplicacao, marca=params.get("marca"), limit=20
            )
            if elastic_results:
                data = [{"CODPROD": r.get("codprod"), "PRODUTO": r.get("descricao",""),
                         "MARCA": r.get("marca",""), "APLICACAO": r.get("aplicacao",""),
                         "REFERENCIA": r.get("referencia","")} for r in elastic_results]
                lines = [f"\U0001f50d Encontrei **{len(data)} produto(s)** para aplicacao **{aplicacao}**"]
                if params.get("marca"):
                    lines[0] += f" (marca {params['marca']})"
                lines[0] += ":\n"
                lines.append("| CodProd | Produto | Marca | Aplicacao | Ref. |")
                lines.append("|---------|---------|-------|-----------|------|")
                for r in data:
                    lines.append(f"| {r.get('CODPROD','')} | {trunc(str(r.get('PRODUTO','')), 30)} | {trunc(str(r.get('MARCA','')), 15)} | {trunc(str(r.get('APLICACAO','')), 35)} | {trunc(str(r.get('REFERENCIA','') or ''), 15)} |")
                if len(data) >= 20:
                    lines.append("\n*Mostrando os 20 primeiros. Refine com marca ou nome da peca.*")
                lines.append(f"\nPara detalhes: *\"tudo sobre o produto {data[0].get('CODPROD','')}\"*")
                response = "\n".join(lines)
                elapsed = int((time.time() - t0) * 1000)
                if ctx:
                    result_data = {"detail_data": data, "columns": ["CODPROD","PRODUTO","MARCA","APLICACAO","REFERENCIA"], "description": "aplicacao", "params": params, "intent": "produto"}
                    ctx.update("produto", params, result_data, question)
                return {"response": response, "tipo": "consulta_banco", "query_executed": "elastic:aplicacao", "query_results": len(data), "time_ms": elapsed, "_detail_data": data}

        # Fallback SQL
        safe_app = safe_sql(aplicacao)
        marca_filter = ""
        if params.get("marca"):
            marca_filter = f" AND UPPER(MAR.DESCRICAO) LIKE UPPER('%{safe_sql(params['marca'])}%')"

        sql = f"""SELECT DISTINCT PRO.CODPROD, PRO.DESCRPROD AS PRODUTO,
            NVL(MAR.DESCRICAO,'') AS MARCA,
            NVL(PRO.CARACTERISTICAS,'') AS APLICACAO, PRO.REFERENCIA
        FROM TGFPRO PRO
        LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
        WHERE PRO.ATIVO = 'S'
          AND UPPER(PRO.CARACTERISTICAS) LIKE UPPER('%{safe_app}%')
          {marca_filter}
          AND ROWNUM <= 20
        ORDER BY MAR.DESCRICAO, PRO.DESCRPROD"""

        print(f"[SMART] Busca aplicacao: '{aplicacao}' marca={params.get('marca')}")
        result = await self.executor.execute(sql)

        if not result.get("success"):
            return {"response": f"Erro ao buscar por aplicacao: {result.get('error','?')}", "tipo": "consulta_banco", "query_executed": sql[:200], "query_results": 0}

        data = result.get("data", [])
        if data and isinstance(data[0], (list, tuple)):
            cols = result.get("columns") or ["CODPROD", "PRODUTO", "MARCA", "APLICACAO", "REFERENCIA"]
            data = [dict(zip(cols, row)) for row in data]

        if not data:
            elapsed = int((time.time() - t0) * 1000)
            return {"response": f"Nenhum produto encontrado com aplicacao **{aplicacao}**.\n\nVerifique se o nome do veiculo/motor esta correto.", "tipo": "consulta_banco", "query_executed": sql[:200], "query_results": 0, "time_ms": elapsed}

        lines = [f"\U0001f50d Encontrei **{len(data)} produto(s)** para aplicacao **{aplicacao}**"]
        if params.get("marca"):
            lines[0] += f" (marca {params['marca']})"
        lines[0] += ":\n"
        lines.append("| CodProd | Produto | Marca | Aplicacao | Ref. |")
        lines.append("|---------|---------|-------|-----------|------|")
        for r in data:
            aplic = trunc(r.get('APLICACAO',''), 35)
            lines.append(f"| {r.get('CODPROD','')} | {str(r.get('PRODUTO',''))[:30]} | {str(r.get('MARCA',''))[:15]} | {aplic} | {str(r.get('REFERENCIA','') or '')[:15]} |")
        if len(data) >= 20:
            lines.append("\n*Mostrando os 20 primeiros resultados. Refine a busca com a marca ou nome da peca.*")
        lines.append(f"\nPara detalhes: *\"tudo sobre o produto {data[0].get('CODPROD','')}\"*")

        response = "\n".join(lines)
        elapsed = int((time.time() - t0) * 1000)

        result_data = {"detail_data": data, "columns": ["CODPROD","PRODUTO","MARCA","APLICACAO","REFERENCIA"], "description": "aplicacao", "params": params, "intent": "produto"}
        if ctx:
            ctx.update("produto", params, result_data, question)

        return {"response": response, "tipo": "consulta_banco", "query_executed": sql[:200] + "...", "query_results": len(data), "time_ms": elapsed, "_detail_data": data}

    # ---- BUSCA PRODUTO VIA ELASTICSEARCH ----
    async def _handle_busca_produto(self, question, user_context, t0, params=None, ctx=None):
        """Busca produto no Elasticsearch com fuzzy matching."""
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)

        text = params.get("texto_busca") or params.get("produto_nome")
        codigo = params.get("codigo_fabricante")
        # Se LLM forneceu texto_busca, ignorar marca do regex (pode ser poluida)
        # Ex: "filtro de ar" → regex extrai marca="AR" erroneamente
        marca = params.get("marca") if not params.get("texto_busca") else None
        aplicacao = params.get("aplicacao")

        # Se nao extraiu texto dos params, extrair da pergunta original
        if not text and not codigo:
            import re as _re
            clean = _re.sub(
                r'\b(busca|buscar|procura|procurar|encontra|encontrar|pesquisa|pesquisar|'
                r'tem|temos|existe|acha|achar|me|mostra|mostrar|quero|ver|o|a|os|as|um|uma|'
                r'do|da|dos|das|de|pra|para|no|na|nos|nas|pelo|pela|que|com|e|ou|'
                r'preciso|traga|traz|lista|listar|todos|todas|todo|toda|'
                r'produto|produtos|peca|pecas|cadastrado|cadastrada|cadastrados|cadastradas|'
                r'sistema|qual|quais|codigo)\b',
                '', question.lower()
            ).strip()
            clean = _re.sub(r'\s+', ' ', clean).strip()
            if clean:
                text = clean
            # Se marca foi extraida mas text nao, usar marca como text (se >= 3 chars)
            if not text and marca and len(marca) >= 3:
                text = marca
            if not text and aplicacao:
                text = aplicacao

        if not text and not codigo:
            return {"response": "O que voce esta procurando? Me diz o nome, codigo ou aplicacao do produto.", "tipo": "info", "query_executed": None, "query_results": None}

        if not self.elastic:
            # Fallback: sem Elastic, redirecionar para handlers existentes
            if codigo:
                return await self._handle_busca_fabricante(question, user_context, t0, params, ctx)
            if aplicacao:
                return await self._handle_busca_aplicacao(question, user_context, t0, params, ctx)
            return {"response": "Busca de produto indisponivel no momento (Elasticsearch offline).", "tipo": "info"}

        print(f"[SMART] Busca Elastic: text='{text}' codigo='{codigo}' marca='{marca}' aplicacao='{aplicacao}'")
        results = await self.elastic.search_products(
            text=text, codigo=codigo, marca=marca, aplicacao=aplicacao, limit=15
        )

        # Se nao encontrou com todos os filtros, tentar mais amplo
        if not results and marca:
            results = await self.elastic.search_products(
                text=text or codigo, aplicacao=aplicacao, limit=15
            )
        if not results and aplicacao:
            results = await self.elastic.search_products(
                text=text or codigo, marca=marca, limit=15
            )
        if not results:
            # Fallback SQL
            if codigo:
                return await self._handle_busca_fabricante(question, user_context, t0, params, ctx)
            return {"response": f"Nenhum produto encontrado para '{text or codigo}'.\n\nTente variando o nome ou busque por codigo.", "tipo": "consulta_banco", "query_executed": "elastic:search_products", "query_results": 0, "time_ms": int((time.time() - t0) * 1000)}

        # Formatar resposta
        lines = [f"\U0001f50d Encontrei **{len(results)} produto(s)**"]
        if marca:
            lines[0] += f" da marca **{marca}**"
        if aplicacao:
            lines[0] += f" para **{aplicacao}**"
        lines[0] += ":\n"

        lines.append("| CodProd | Produto | Marca | Referencia | Aplicacao |")
        lines.append("|---------|---------|-------|-----------|-----------|")
        for p in results:
            ref = str(p.get('referencia', '') or p.get('num_fabricante', '') or '')
            lines.append(f"| {p.get('codprod','')} | {trunc(str(p.get('descricao','')), 30)} | "
                         f"{trunc(str(p.get('marca','')), 15)} | {trunc(ref, 15)} | "
                         f"{trunc(str(p.get('aplicacao','')), 25)} |")
        if len(results) >= 15:
            lines.append("\n*Mostrando os 15 primeiros. Refine a busca com mais detalhes.*")
        if results:
            lines.append(f"\nPara detalhes: *\"tudo sobre o produto {results[0].get('codprod','')}\"*")

        response = "\n".join(lines)

        # Narrar se habilitado
        if USE_LLM_NARRATOR and len(results) > 0:
            summary = build_produto_summary(results, params or {})
            narration = await llm_narrate(question, summary, "")
            if narration:
                response = narration + "\n\n" + response

        elapsed = int((time.time() - t0) * 1000)

        if ctx:
            result_data = {"detail_data": results, "columns": list(results[0].keys()) if results else [],
                           "description": f"busca '{text or codigo}'", "params": params, "intent": "busca_produto"}
            ctx.update("busca_produto", params, result_data, question)

        return {"response": response, "tipo": "consulta_banco",
                "query_executed": "elastic:search_products", "query_results": len(results),
                "time_ms": elapsed, "_detail_data": results}

    # ---- BUSCA PARCEIRO (CLIENTE/FORNECEDOR) VIA ELASTICSEARCH ----
    async def _handle_busca_parceiro(self, question, user_context, t0, params=None, tipo="C", ctx=None):
        """Busca cliente ou fornecedor no Elasticsearch com fuzzy matching."""
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)

        text = params.get("texto_busca") or params.get("fornecedor") or params.get("empresa")
        cnpj = params.get("cnpj")
        cidade = params.get("cidade")

        tipo_nome = "cliente" if tipo == "C" else "fornecedor"

        if not text and not cnpj:
            return {"response": f"Qual {tipo_nome} voce esta procurando? Me diz o nome, CNPJ ou cidade.", "tipo": "info", "query_executed": None, "query_results": None}

        if not self.elastic:
            return {"response": f"Busca de {tipo_nome} indisponivel no momento (Elasticsearch offline).", "tipo": "info"}

        print(f"[SMART] Busca Elastic {tipo_nome}: text='{text}' cnpj='{cnpj}' cidade='{cidade}'")
        results = await self.elastic.search_partners(
            text=text, cnpj=cnpj, tipo=tipo, cidade=cidade, limit=10
        )

        if not results:
            return {"response": f"Nenhum {tipo_nome} encontrado para '{text or cnpj}'.\n\nVerifique o nome ou tente CNPJ parcial.",
                    "tipo": "consulta_banco", "query_executed": "elastic:search_partners",
                    "query_results": 0, "time_ms": int((time.time() - t0) * 1000)}

        lines = [f"\U0001f50d Encontrei **{len(results)} {tipo_nome}(s)**:\n"]
        lines.append("| Codigo | Nome | Fantasia | Cidade/UF | Telefone |")
        lines.append("|--------|------|----------|-----------|----------|")
        for p in results:
            cidade_uf = f"{p.get('cidade','')}/{p.get('uf','')}" if p.get('uf') else p.get('cidade', '')
            lines.append(f"| {p.get('codparc','')} | {trunc(str(p.get('nome','')), 30)} | "
                         f"{trunc(str(p.get('fantasia','')), 20)} | {trunc(cidade_uf, 20)} | {p.get('telefone','')} |")

        # Narrar se habilitado
        response = "\n".join(lines)
        if USE_LLM_NARRATOR and len(results) > 0:
            summary = f"Busca de {tipo_nome} por '{text or cnpj}'. {len(results)} resultados."
            narration = await llm_narrate(question, summary, "")
            if narration:
                response = narration + "\n\n" + response

        elapsed = int((time.time() - t0) * 1000)

        if ctx:
            result_data = {"detail_data": results, "columns": list(results[0].keys()) if results else [],
                           "description": f"busca {tipo_nome} '{text or cnpj}'", "params": params,
                           "intent": f"busca_{tipo_nome}"}
            ctx.update(f"busca_{tipo_nome}", params, result_data, question)

        return {"response": response, "tipo": "consulta_banco",
                "query_executed": "elastic:search_partners",
                "query_results": len(results), "time_ms": elapsed, "_detail_data": results}

    # ---- PRODUTO 360 (visao completa) ----
    async def _handle_produto_360(self, question, user_context, t0, params=None, ctx=None):
        """Combina estoque + pendencia + vendas para visao completa de um produto."""
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)

        codprod = params.get("codprod")
        cod_fab = params.get("codigo_fabricante")
        produto_nome = params.get("produto_nome")

        # Resolver CODPROD se necessario
        if not codprod and cod_fab:
            resolved = await resolve_manufacturer_code(cod_fab, self.executor)
            if resolved.get("found"):
                products = resolved.get("products", [])
                if len(products) == 1:
                    codprod = products[0]["codprod"]
                else:
                    response = format_busca_fabricante(resolved)
                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": response, "tipo": "consulta_banco", "query_executed": f"busca: {cod_fab}", "query_results": len(products), "time_ms": elapsed}
            else:
                elapsed = int((time.time() - t0) * 1000)
                return {"response": f"Nenhum produto encontrado com o codigo **{cod_fab}**.", "tipo": "consulta_banco", "query_executed": f"busca: {cod_fab}", "query_results": 0, "time_ms": elapsed}

        if not codprod and produto_nome:
            sql_find = f"SELECT PRO.CODPROD, PRO.DESCRPROD, NVL(PRO.CARACTERISTICAS,'') AS APLICACAO FROM TGFPRO PRO WHERE UPPER(PRO.DESCRPROD) LIKE UPPER('%{produto_nome.replace(chr(39), chr(39)+chr(39))}%') AND PRO.ATIVO='S' AND ROWNUM<=5"
            r_find = await self.executor.execute(sql_find)
            if r_find.get("success") and r_find.get("data"):
                fdata = r_find["data"]
                if fdata and isinstance(fdata[0], (list, tuple)):
                    fdata = [dict(zip(["CODPROD", "DESCRPROD", "APLICACAO"], row)) for row in fdata]
                if len(fdata) == 1:
                    codprod = int(fdata[0].get("CODPROD", 0) or 0)
                else:
                    lines = [f"Encontrei **{len(fdata)} produtos** com '{produto_nome}':\n"]
                    lines.append("| CodProd | Produto | Aplicacao |")
                    lines.append("|---------|---------|-----------|")
                    for r in fdata:
                        aplic = trunc(r.get('APLICACAO',''), 40)
                        lines.append(f"| {r.get('CODPROD','')} | {str(r.get('DESCRPROD',''))[:50]} | {aplic} |")
                    lines.append(f"\nEspecifique: *\"tudo sobre o produto {fdata[0].get('CODPROD','')}\"*")
                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": "\n".join(lines), "tipo": "consulta_banco", "query_executed": sql_find[:200], "query_results": len(fdata), "time_ms": elapsed}

        if not codprod:
            return {"response": "Para ver a visao 360, informe o codigo do produto.\nEx: *\"tudo sobre o produto 133346\"*", "tipo": "info", "query_executed": None, "query_results": None}

        print(f"[SMART] Produto 360: codprod={codprod}")

        # Executar consultas em paralelo
        sql_prod = f"""SELECT PRO.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA,
            PRO.REFERENCIA, PRO.AD_NUMFABRICANTE, PRO.NCM, PRO.CODVOL,
            NVL(PRO.CARACTERISTICAS,'') AS APLICACAO,
            NVL(PRO.COMPLDESC,'') AS COMPLEMENTO,
            NVL(PRO.AD_NUMORIGINAL,'') AS NUM_ORIGINAL,
            NVL(PRO.REFFORN,'') AS REF_FORNECEDOR
        FROM TGFPRO PRO LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
        WHERE PRO.CODPROD = {codprod}"""

        sql_est = f"""SELECT EMP.NOMEFANTASIA AS EMPRESA, NVL(E.ESTOQUE,0) AS ESTOQUE, NVL(E.ESTMIN,0) AS ESTMIN
        FROM TGFEST E
        LEFT JOIN TSIEMP EMP ON EMP.CODEMP = E.CODEMP
        WHERE E.CODPROD = {codprod} AND E.CODLOCAL = 0 AND NVL(E.ATIVO,'S') = 'S'
        ORDER BY EMP.NOMEFANTASIA"""

        sql_vendas = f"""SELECT COUNT(DISTINCT C.NUNOTA) AS QTD_VENDAS, SUM(I.QTDNEG) AS QTD_VENDIDA,
            SUM(I.VLRTOT) AS VLR_TOTAL
        FROM TGFITE I JOIN TGFCAB C ON C.NUNOTA = I.NUNOTA
        WHERE I.CODPROD = {codprod}
          AND C.TIPMOV = 'V' AND C.CODTIPOPER IN (1100,1101) AND C.STATUSNOTA <> 'C'
          AND C.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE), -3)"""

        # Executar em paralelo
        r_prod, r_est, r_vendas = await asyncio.gather(
            self.executor.execute(sql_prod),
            self.executor.execute(sql_est),
            self.executor.execute(sql_vendas),
        )

        # Montar info do produto
        prod_info = {"codprod": codprod, "produto": "?", "marca": "", "referencia": ""}
        if r_prod.get("success") and r_prod.get("data"):
            pdata = r_prod["data"]
            if pdata and isinstance(pdata[0], (list, tuple)):
                cols = r_prod.get("columns") or ["CODPROD", "PRODUTO", "MARCA", "REFERENCIA", "AD_NUMFABRICANTE", "NCM", "CODVOL", "APLICACAO", "COMPLEMENTO", "NUM_ORIGINAL", "REF_FORNECEDOR"]
                pdata = [dict(zip(cols, row)) for row in pdata]
            if pdata and isinstance(pdata[0], dict):
                p = pdata[0]
                prod_info["produto"] = str(p.get("PRODUTO", "?"))
                prod_info["marca"] = str(p.get("MARCA", ""))
                prod_info["referencia"] = str(p.get("REFERENCIA", "") or p.get("AD_NUMFABRICANTE", "") or "")
                prod_info["aplicacao"] = str(p.get("APLICACAO", "") or "")
                prod_info["complemento"] = str(p.get("COMPLEMENTO", "") or "")
                prod_info["num_original"] = str(p.get("NUM_ORIGINAL", "") or "")
                prod_info["ref_fornecedor"] = str(p.get("REF_FORNECEDOR", "") or "")

        # Estoque
        estoque_data = []
        if r_est.get("success") and r_est.get("data"):
            edata = r_est["data"]
            if edata and isinstance(edata[0], (list, tuple)):
                cols = r_est.get("columns") or ["EMPRESA", "ESTOQUE", "ESTMIN"]
                edata = [dict(zip(cols, row)) for row in edata]
            estoque_data = [r for r in edata if isinstance(r, dict)]

        # Pendencia de compras (usa handler existente internamente)
        pend_params = {"codprod": codprod}
        sql_pend = f"""SELECT CAB.NUNOTA AS PEDIDO,
            CASE WHEN CAB.CODTIPOPER = 1313 THEN 'Casada' WHEN CAB.CODTIPOPER = 1301 THEN 'Estoque' END AS TIPO_COMPRA,
            PAR.NOMEPARC AS FORNECEDOR, SUM(ITE.QTDNEG - NVL(ITE.QTDENTREGUE,0)) AS QTD_PENDENTE,
            SUM((ITE.QTDNEG - NVL(ITE.QTDENTREGUE,0)) * ITE.VLRUNIT) AS VLR_PENDENTE,
            CASE WHEN CAB.AD_DTPREVCHEG IS NULL THEN 'SEM PREVISAO'
                 WHEN CAB.AD_DTPREVCHEG < TRUNC(SYSDATE) THEN 'ATRASADO'
                 ELSE 'NO PRAZO' END AS STATUS_ENTREGA
        FROM TGFCAB CAB
        JOIN TGFITE ITE ON ITE.NUNOTA = CAB.NUNOTA
        JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
        JOIN TGFPAR PAR ON PAR.CODPARC = CAB.CODPARC
        WHERE CAB.CODTIPOPER IN (1301, 1313) AND CAB.PENDENTE = 'S'
          AND ITE.CODPROD = {codprod}
          AND (ITE.QTDNEG - NVL(ITE.QTDENTREGUE,0)) > 0
        GROUP BY CAB.NUNOTA, CAB.CODTIPOPER, PAR.NOMEPARC, CAB.AD_DTPREVCHEG
        ORDER BY CAB.NUNOTA"""

        r_pend = await self.executor.execute(sql_pend)
        pendencia_data = {"detail_data": []}
        if r_pend.get("success") and r_pend.get("data"):
            pd_data = r_pend["data"]
            if pd_data and isinstance(pd_data[0], (list, tuple)):
                cols = r_pend.get("columns") or ["PEDIDO", "TIPO_COMPRA", "FORNECEDOR", "QTD_PENDENTE", "VLR_PENDENTE", "STATUS_ENTREGA"]
                pd_data = [dict(zip(cols, row)) for row in pd_data]
            pendencia_data["detail_data"] = [r for r in pd_data if isinstance(r, dict)]

        # Vendas
        vendas_info = {}
        if r_vendas.get("success") and r_vendas.get("data"):
            vdata = r_vendas["data"]
            if vdata and isinstance(vdata[0], (list, tuple)):
                cols = r_vendas.get("columns") or ["QTD_VENDAS", "QTD_VENDIDA", "VLR_TOTAL"]
                vdata = [dict(zip(cols, row)) for row in vdata]
            if vdata and isinstance(vdata[0], dict):
                vendas_info = vdata[0]

        # Formatar resposta
        response = format_produto_360(prod_info, estoque_data, pendencia_data, vendas_info)

        # Salvar no contexto
        if ctx:
            all_data = estoque_data + pendencia_data.get("detail_data", [])
            result_data = {"detail_data": all_data, "columns": ["CODPROD"], "description": f"produto 360 - {codprod}", "params": params, "intent": "produto_360"}
            ctx.update("produto_360", params, result_data, question)

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": f"produto 360: codprod={codprod}", "query_results": 1, "time_ms": elapsed}

    # ---- FINANCEIRO (Contas a Pagar / Receber / Fluxo de Caixa) ----
    async def _handle_financeiro(self, question, user_context, t0, params=None, ctx=None):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        # Preservar params financeiros antes do merge (merge_params só mantém entity keys)
        _fin_save = {k: params[k] for k in ("tipo", "status", "valor_minimo", "valor_maximo", "parceiro", "top", "periodo") if params.get(k) is not None}
        if ctx and not (params.get("empresa") or params.get("parceiro")):
            params = ctx.merge_params(params)
        params.update(_fin_save)
        print(f"[SMART] Financeiro params: {params}")

        # Detectar tipo (pagar/receber/fluxo)
        q_norm = normalize(question)
        tipo = params.get("tipo", "")
        if not tipo:
            if any(w in q_norm for w in ["pagar", "despesa", "despesas", "fornecedor", "boleto", "boletos", "duplicata", "duplicatas", "pagamento", "pagamentos"]):
                tipo = "pagar"
            elif any(w in q_norm for w in ["receber", "receita", "receitas", "cliente", "clientes", "cobranca"]):
                tipo = "receber"
            elif any(w in q_norm for w in ["fluxo", "caixa"]):
                tipo = "fluxo"
            else:
                tipo = "receber"

        # Detectar status (vencido/a_vencer/todos)
        status = params.get("status", "todos")
        if any(w in q_norm for w in ["vencido", "vencidos", "vencida", "vencidas", "atrasado"]):
            status = "vencido"
        elif any(w in q_norm for w in ["vencer", "futuro", "futuros", "proximos"]):
            status = "a_vencer"

        # Periodo para filtro de vencimento
        periodo = params.get("periodo", "mes")
        pf = _build_periodo_filter({
            "periodo": periodo,
            "data_inicio": params.get("data_inicio"),
            "data_fim": params.get("data_fim"),
        }, date_col="FIN.DTVENC")

        # WHERE base
        recdesp = "-1" if tipo == "pagar" else "1"
        where_parts = [
            "FIN.PROVISAO = 'N'",
            "FIN.DHBAIXA IS NULL",
        ]
        if tipo != "fluxo":
            where_parts.append(f"FIN.RECDESP = {recdesp}")

        # Status filter
        if status == "vencido":
            where_parts.append("FIN.DTVENC < TRUNC(SYSDATE)")
        elif status == "a_vencer":
            where_parts.append("FIN.DTVENC >= TRUNC(SYSDATE)")

        # Empresa
        if params.get("empresa"):
            where_parts.append(f"UPPER(EMP.NOMEFANTASIA) LIKE UPPER('%{safe_sql(params['empresa'])}%')")

        # Parceiro
        if params.get("parceiro"):
            where_parts.append(f"UPPER(PAR.NOMEPARC) LIKE UPPER('%{safe_sql(params['parceiro'])}%')")

        # Valor minimo/maximo
        if params.get("valor_minimo") is not None:
            where_parts.append(f"FIN.VLRDESDOB >= {float(params['valor_minimo'])}")
        if params.get("valor_maximo") is not None:
            where_parts.append(f"FIN.VLRDESDOB <= {float(params['valor_maximo'])}")

        where_clause = " AND ".join(where_parts)

        # Build description
        desc_parts = [PERIODO_NOMES.get(periodo, "este mes")]
        if params.get("empresa"):
            desc_parts.append(EMPRESA_DISPLAY.get(params['empresa'].upper(), params['empresa']))
        if params.get("parceiro"):
            desc_parts.append(params['parceiro'])
        if status == "vencido":
            desc_parts.append("vencidos")
        elif status == "a_vencer":
            desc_parts.append("a vencer")
        description = " | ".join(desc_parts)

        # SQL KPIs
        if tipo == "fluxo":
            sql_kpis = f"""SELECT
                COUNT(*) AS QTD_TITULOS,
                NVL(SUM(CASE WHEN FIN.RECDESP = 1 THEN FIN.VLRDESDOB ELSE 0 END), 0) AS ENTRADAS,
                NVL(SUM(CASE WHEN FIN.RECDESP = -1 THEN FIN.VLRDESDOB ELSE 0 END), 0) AS SAIDAS,
                NVL(SUM(CASE WHEN FIN.RECDESP = 1 THEN FIN.VLRDESDOB ELSE 0 END), 0) -
                NVL(SUM(CASE WHEN FIN.RECDESP = -1 THEN FIN.VLRDESDOB ELSE 0 END), 0) AS SALDO,
                0 AS VLR_TOTAL, 0 AS VLR_VENCIDO, 0 AS VLR_A_VENCER
            FROM TGFFIN FIN
            LEFT JOIN TSIEMP EMP ON EMP.CODEMP = FIN.CODEMP
            LEFT JOIN TGFPAR PAR ON PAR.CODPARC = FIN.CODPARC
            WHERE FIN.PROVISAO = 'N' AND FIN.DHBAIXA IS NULL
                {pf}
                {(' AND UPPER(EMP.NOMEFANTASIA) LIKE UPPER(' + chr(39) + '%' + safe_sql(params['empresa']) + '%' + chr(39) + ')') if params.get('empresa') else ''}"""
        else:
            sql_kpis = f"""SELECT
                COUNT(*) AS QTD_TITULOS,
                NVL(SUM(FIN.VLRDESDOB), 0) AS VLR_TOTAL,
                NVL(SUM(CASE WHEN FIN.DTVENC < TRUNC(SYSDATE) THEN FIN.VLRDESDOB ELSE 0 END), 0) AS VLR_VENCIDO,
                NVL(SUM(CASE WHEN FIN.DTVENC >= TRUNC(SYSDATE) THEN FIN.VLRDESDOB ELSE 0 END), 0) AS VLR_A_VENCER,
                0 AS ENTRADAS, 0 AS SAIDAS, 0 AS SALDO
            FROM TGFFIN FIN
            LEFT JOIN TSIEMP EMP ON EMP.CODEMP = FIN.CODEMP
            LEFT JOIN TGFPAR PAR ON PAR.CODPARC = FIN.CODPARC
            WHERE {where_clause} {pf}"""

        # SQL Detail
        top_n = int(params.get("top", 200))
        if tipo == "fluxo":
            sql_detail = f"""SELECT
                PAR.NOMEPARC AS PARCEIRO,
                FIN.RECDESP,
                TO_CHAR(FIN.DTVENC, 'DD/MM/YYYY') AS DTVENC,
                FIN.VLRDESDOB,
                TRUNC(SYSDATE) - TRUNC(FIN.DTVENC) AS DIAS_VENCIDO,
                CASE WHEN FIN.DTVENC < TRUNC(SYSDATE) THEN 'VENCIDO' ELSE 'A VENCER' END AS STATUS,
                EMP.NOMEFANTASIA AS EMPRESA,
                FIN.NUFIN
            FROM TGFFIN FIN
            LEFT JOIN TSIEMP EMP ON EMP.CODEMP = FIN.CODEMP
            LEFT JOIN TGFPAR PAR ON PAR.CODPARC = FIN.CODPARC
            WHERE FIN.PROVISAO = 'N' AND FIN.DHBAIXA IS NULL
                {pf}
                {(' AND UPPER(EMP.NOMEFANTASIA) LIKE UPPER(' + chr(39) + '%' + safe_sql(params['empresa']) + '%' + chr(39) + ')') if params.get('empresa') else ''}
            ORDER BY FIN.DTVENC
            FETCH FIRST {top_n} ROWS ONLY"""
        else:
            sql_detail = f"""SELECT
                PAR.NOMEPARC AS PARCEIRO,
                TO_CHAR(FIN.DTVENC, 'DD/MM/YYYY') AS DTVENC,
                FIN.VLRDESDOB,
                TRUNC(SYSDATE) - TRUNC(FIN.DTVENC) AS DIAS_VENCIDO,
                CASE WHEN FIN.DTVENC < TRUNC(SYSDATE) THEN 'VENCIDO' ELSE 'A VENCER' END AS STATUS,
                EMP.NOMEFANTASIA AS EMPRESA,
                FIN.NUFIN
            FROM TGFFIN FIN
            LEFT JOIN TSIEMP EMP ON EMP.CODEMP = FIN.CODEMP
            LEFT JOIN TGFPAR PAR ON PAR.CODPARC = FIN.CODPARC
            WHERE {where_clause} {pf}
            ORDER BY FIN.DTVENC {'ASC' if status == 'a_vencer' else 'DESC'}
            FETCH FIRST {top_n} ROWS ONLY"""

        # Execute KPIs
        kr = await self.executor.execute(sql_kpis)
        if not kr.get("success"):
            return {"response": f"Erro ao consultar financeiro: {kr.get('error', '?')}", "tipo": "consulta_banco", "query_executed": sql_kpis[:200], "query_results": 0}

        kd = kr.get("data", [])
        if kd and isinstance(kd[0], (list, tuple)):
            cols = kr.get("columns") or ["QTD_TITULOS", "VLR_TOTAL", "VLR_VENCIDO", "VLR_A_VENCER", "ENTRADAS", "SAIDAS", "SALDO"]
            kd = [dict(zip(cols, row)) for row in kd]
        kpi_row = kd[0] if kd else {}

        # Execute Detail
        detail_data = []
        if tipo == "fluxo":
            detail_columns = ["PARCEIRO", "RECDESP", "DTVENC", "VLRDESDOB", "DIAS_VENCIDO", "STATUS", "EMPRESA", "NUFIN"]
        else:
            detail_columns = ["PARCEIRO", "DTVENC", "VLRDESDOB", "DIAS_VENCIDO", "STATUS", "EMPRESA", "NUFIN"]

        qtd = int(kpi_row.get("QTD_TITULOS", 0) or 0)
        if qtd > 0:
            dr = await self.executor.execute(sql_detail)
            if dr.get("success"):
                detail_data = dr.get("data", [])
                if detail_data and isinstance(detail_data[0], (list, tuple)):
                    rc = dr.get("columns") or detail_columns
                    if rc and len(rc) == len(detail_data[0]):
                        detail_data = [dict(zip(rc, row)) for row in detail_data]
                    else:
                        detail_data = [dict(zip(detail_columns, row)) for row in detail_data]

        # Context
        result_data = {"detail_data": detail_data, "columns": detail_columns, "description": f"financeiro - {description}", "params": params, "intent": "financeiro"}
        if ctx:
            ctx.update("financeiro", params, result_data, question)

        # Format
        response = format_financeiro_response(kpi_row, detail_data, tipo, description, params)

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": qtd, "time_ms": elapsed, "_detail_data": detail_data}

    # ---- INADIMPLENCIA ----
    async def _handle_inadimplencia(self, question, user_context, t0, params=None, ctx=None):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        # Preservar params financeiros antes do merge (merge_params só mantém entity keys)
        _fin_save = {k: params[k] for k in ("parceiro", "dias_minimo", "valor_minimo", "top") if params.get(k) is not None}
        if ctx and not (params.get("empresa") or params.get("parceiro")):
            params = ctx.merge_params(params)
        params.update(_fin_save)
        print(f"[SMART] Inadimplencia params: {params}")

        # WHERE
        where_parts = [
            "FIN.RECDESP = 1",
            "FIN.PROVISAO = 'N'",
            "FIN.DHBAIXA IS NULL",
            "FIN.DTVENC < TRUNC(SYSDATE)",
        ]
        if params.get("empresa"):
            where_parts.append(f"UPPER(EMP.NOMEFANTASIA) LIKE UPPER('%{safe_sql(params['empresa'])}%')")
        if params.get("parceiro"):
            where_parts.append(f"UPPER(PAR.NOMEPARC) LIKE UPPER('%{safe_sql(params['parceiro'])}%')")
        if params.get("dias_minimo") is not None:
            where_parts.append(f"(TRUNC(SYSDATE) - TRUNC(FIN.DTVENC)) >= {int(params['dias_minimo'])}")
        if params.get("valor_minimo") is not None:
            where_parts.append(f"FIN.VLRDESDOB >= {float(params['valor_minimo'])}")

        where_clause = " AND ".join(where_parts)

        # Description
        desc_parts = []
        if params.get("empresa"):
            desc_parts.append(EMPRESA_DISPLAY.get(params['empresa'].upper(), params['empresa']))
        if params.get("parceiro"):
            desc_parts.append(params['parceiro'])
        if params.get("dias_minimo"):
            desc_parts.append(f"mais de {params['dias_minimo']} dias")
        description = " | ".join(desc_parts) if desc_parts else "geral"

        top_n = int(params.get("top", 50))

        # SQL KPIs (agregado)
        sql_kpis = f"""SELECT
            COUNT(DISTINCT FIN.CODPARC) AS QTD_CLIENTES,
            NVL(SUM(FIN.VLRDESDOB), 0) AS VLR_INADIMPLENTE,
            NVL(ROUND(AVG(TRUNC(SYSDATE) - TRUNC(FIN.DTVENC)), 0), 0) AS DIAS_MEDIO_ATRASO
        FROM TGFFIN FIN
        LEFT JOIN TSIEMP EMP ON EMP.CODEMP = FIN.CODEMP
        LEFT JOIN TGFPAR PAR ON PAR.CODPARC = FIN.CODPARC
        WHERE {where_clause}"""

        # SQL Detail (agrupado por cliente)
        sql_detail = f"""SELECT
            PAR.NOMEPARC AS PARCEIRO,
            COUNT(*) AS QTD_TITULOS,
            NVL(SUM(FIN.VLRDESDOB), 0) AS VLR_INADIMPLENTE,
            MAX(TRUNC(SYSDATE) - TRUNC(FIN.DTVENC)) AS MAIOR_ATRASO
        FROM TGFFIN FIN
        LEFT JOIN TSIEMP EMP ON EMP.CODEMP = FIN.CODEMP
        LEFT JOIN TGFPAR PAR ON PAR.CODPARC = FIN.CODPARC
        WHERE {where_clause}
        GROUP BY PAR.NOMEPARC
        ORDER BY SUM(FIN.VLRDESDOB) DESC
        FETCH FIRST {top_n} ROWS ONLY"""

        # Execute KPIs
        kr = await self.executor.execute(sql_kpis)
        if not kr.get("success"):
            return {"response": f"Erro ao consultar inadimplencia: {kr.get('error', '?')}", "tipo": "consulta_banco", "query_executed": sql_kpis[:200], "query_results": 0}

        kd = kr.get("data", [])
        if kd and isinstance(kd[0], (list, tuple)):
            cols = kr.get("columns") or ["QTD_CLIENTES", "VLR_INADIMPLENTE", "DIAS_MEDIO_ATRASO"]
            kd = [dict(zip(cols, row)) for row in kd]
        kpi_row = kd[0] if kd else {}

        # Execute Detail
        detail_data = []
        detail_columns = ["PARCEIRO", "QTD_TITULOS", "VLR_INADIMPLENTE", "MAIOR_ATRASO"]
        qtd_clientes = int(kpi_row.get("QTD_CLIENTES", 0) or 0)

        if qtd_clientes > 0:
            dr = await self.executor.execute(sql_detail)
            if dr.get("success"):
                detail_data = dr.get("data", [])
                if detail_data and isinstance(detail_data[0], (list, tuple)):
                    rc = dr.get("columns") or detail_columns
                    if rc and len(rc) == len(detail_data[0]):
                        detail_data = [dict(zip(rc, row)) for row in detail_data]
                    else:
                        detail_data = [dict(zip(detail_columns, row)) for row in detail_data]

        # Context
        result_data = {"detail_data": detail_data, "columns": detail_columns, "description": f"inadimplencia - {description}", "params": params, "intent": "inadimplencia"}
        if ctx:
            ctx.update("inadimplencia", params, result_data, question)

        # Format
        response = format_inadimplencia_response(kpi_row, detail_data, description, params)

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": qtd_clientes, "time_ms": elapsed, "_detail_data": detail_data}

    # ---- COMISSAO ----
    async def _handle_comissao(self, question, user_context, t0, params=None, ctx=None):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        # Preservar params de comissão antes do merge (merge_params só mantém entity keys)
        _com_save = {k: params[k] for k in ("vendedor", "periodo", "view", "top", "marca") if params.get(k) is not None}
        if ctx and not (params.get("empresa") or params.get("vendedor")):
            params = ctx.merge_params(params)
        params.update(_com_save)
        # Fallback: se tem "marca" mas não "vendedor" em contexto de comissão,
        # provavelmente o entity extractor confundiu nome de vendedor com marca.
        # Estamos DENTRO do handler de comissão, então não precisa checar "comissao" no texto
        # (pode ser follow-up como "agora do rafael" onde intent vem do contexto).
        # Critério: marca NÃO é uma marca conhecida do ERP → tratar como vendedor.
        if params.get("marca") and not params.get("vendedor"):
            marca_check = params["marca"].upper()
            is_known_marca = self._known_marcas and (
                marca_check in self._known_marcas
                or any(marca_check in m for m in self._known_marcas)
            )
            if not is_known_marca:
                print(f"[SMART] Comissao fallback: marca '{params['marca']}' nao e marca ERP -> vendedor")
                params["vendedor"] = params.pop("marca")

        print(f"[SMART] Comissao params: {params}")

        q_norm = normalize(question)

        # Detectar view (ranking/detalhe)
        view = params.get("view", "")
        if not view:
            if any(w in q_norm for w in ["ranking", "top", "maiores", "melhores", "quem mais"]):
                view = "ranking"
            elif any(w in q_norm for w in ["detalhe", "detalhes", "nota", "notas", "detalhado"]):
                view = "detalhe"
            else:
                view = "ranking"

        # Detectar "por empresa" — agrupar por vendedor + empresa
        por_empresa = bool(re.search(r'por\s+empresa', q_norm) or re.search(r'por\s+filial', q_norm))

        # Periodo
        periodo = params.get("periodo", "mes")
        pf = _build_periodo_filter({
            "periodo": periodo,
            "data_inicio": params.get("data_inicio"),
            "data_fim": params.get("data_fim"),
        }, date_col="C.DTNEG")

        # WHERE base: vendas confirmadas com TOP de saída
        where_parts = [
            "C.TIPMOV IN ('V','D')",
            "C.STATUSNOTA = 'L'",
        ]

        # EXISTS TGFTOP com GolSinal = '-1' (saída)
        exists_top = """EXISTS (SELECT 1 FROM TGFTOP T
            WHERE T.CODTIPOPER = C.CODTIPOPER AND T.DHALTER = C.DHTIPOPER AND T.GOLSINAL = '-1')"""
        where_parts.append(exists_top)

        # Filtros opcionais
        if params.get("vendedor"):
            where_parts.append(f"UPPER(VEN.APELIDO) LIKE UPPER('%{safe_sql(params['vendedor'])}%')")
        if params.get("empresa"):
            where_parts.append(f"UPPER(EMP.NOMEFANTASIA) LIKE UPPER('%{safe_sql(params['empresa'])}%')")
        if params.get("marca"):
            where_parts.append(f"UPPER(MAR.DESCRICAO) LIKE UPPER('%{safe_sql(params['marca'])}%')")

        # RBAC: vendedor só vê suas próprias comissões
        if user_context:
            role = user_context.get("role", "vendedor")
            if role in ("admin", "diretor", "ti"):
                pass
            elif role == "gerente":
                team = user_context.get("team_codvends", [])
                if team:
                    where_parts.append(f"C.CODVEND IN ({','.join(str(int(c)) for c in team)})")
            elif role == "vendedor":
                codvend = user_context.get("codvend", 0)
                if codvend:
                    where_parts.append(f"C.CODVEND = {int(codvend)}")

        where_clause = " AND ".join(where_parts)

        # JOINs comuns (marca só quando filtrar por marca)
        joins_marca = ""
        if params.get("marca"):
            joins_marca = """LEFT JOIN TGFITE ITE ON ITE.NUNOTA = C.NUNOTA AND ROWNUM = 1
            LEFT JOIN TGFMAR MAR ON MAR.CODIGO = (SELECT PRO.CODMARCA FROM TGFPRO PRO WHERE PRO.CODPROD = ITE.CODPROD AND ROWNUM = 1)"""

        # Description
        desc_parts = [PERIODO_NOMES.get(periodo, "este mes")]
        if params.get("vendedor"):
            desc_parts.append(params['vendedor'])
        if params.get("empresa"):
            desc_parts.append(EMPRESA_DISPLAY.get(params['empresa'].upper(), params['empresa']))
        if params.get("marca"):
            desc_parts.append(f"marca {params['marca']}")
        if por_empresa:
            desc_parts.append("por empresa")
        description = " | ".join(desc_parts)

        top_n = int(params.get("top", 50))

        # SQL KPIs (agregado geral — separa vendas e devoluções)
        sql_kpis = f"""SELECT
            COUNT(DISTINCT C.NUNOTA) AS QTD_NOTAS,
            NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.AD_VLRBASECOMINT ELSE 0 END), 0) AS VLR_VENDAS,
            NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.AD_VLRBASECOMINT ELSE 0 END), 0) AS VLR_DEVOLUCAO,
            NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.AD_VLRBASECOMINT ELSE 0 END), 0)
              - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.AD_VLRBASECOMINT ELSE 0 END), 0) AS VLR_LIQUIDO,
            NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.AD_VLRCOMINT ELSE 0 END), 0) AS COM_VENDAS,
            NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.AD_VLRCOMINT ELSE 0 END), 0) AS COM_DEVOLUCAO,
            NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.AD_VLRCOMINT ELSE 0 END), 0)
              - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.AD_VLRCOMINT ELSE 0 END), 0) AS COM_LIQUIDA,
            NVL(ROUND(AVG(CASE WHEN C.TIPMOV = 'V' THEN C.AD_MARGEM END), 2), 0) AS MARGEM_MEDIA
        FROM TGFCAB C
        LEFT JOIN TSIEMP EMP ON EMP.CODEMP = C.CODEMP
        LEFT JOIN TGFVEN VEN ON VEN.CODVEND = C.CODVEND
        {joins_marca}
        WHERE {where_clause} {pf}"""

        kpi_columns = ["QTD_NOTAS", "VLR_VENDAS", "VLR_DEVOLUCAO", "VLR_LIQUIDO",
                        "COM_VENDAS", "COM_DEVOLUCAO", "COM_LIQUIDA", "MARGEM_MEDIA"]

        # SQL Detail depende da view
        if view == "ranking":
            group_cols = "VEN.APELIDO"
            select_empresa = ""
            if por_empresa:
                group_cols = "VEN.APELIDO, EMP.NOMEFANTASIA"
                select_empresa = "EMP.NOMEFANTASIA AS EMPRESA,"

            sql_detail = f"""SELECT
                VEN.APELIDO AS VENDEDOR,
                {select_empresa}
                COUNT(DISTINCT C.NUNOTA) AS QTD_NOTAS,
                NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.AD_VLRBASECOMINT ELSE 0 END), 0) AS VLR_VENDAS,
                NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.AD_VLRBASECOMINT ELSE 0 END), 0) AS VLR_DEVOLUCAO,
                NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.AD_VLRBASECOMINT ELSE 0 END), 0)
                  - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.AD_VLRBASECOMINT ELSE 0 END), 0) AS VLR_LIQUIDO,
                NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.AD_VLRCOMINT ELSE 0 END), 0)
                  - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.AD_VLRCOMINT ELSE 0 END), 0) AS COM_LIQUIDA,
                NVL(ROUND(AVG(CASE WHEN C.TIPMOV = 'V' THEN C.AD_MARGEM END), 2), 0) AS MARGEM_MEDIA,
                NVL(ROUND(AVG(CASE WHEN C.TIPMOV = 'V' THEN C.AD_ALIQCOMINT END), 2), 0) AS ALIQ_MEDIA
            FROM TGFCAB C
            LEFT JOIN TSIEMP EMP ON EMP.CODEMP = C.CODEMP
            LEFT JOIN TGFVEN VEN ON VEN.CODVEND = C.CODVEND
            {joins_marca}
            WHERE {where_clause} {pf}
            GROUP BY {group_cols}
            ORDER BY (NVL(SUM(CASE WHEN C.TIPMOV = 'V' THEN C.AD_VLRCOMINT ELSE 0 END), 0)
                      - NVL(SUM(CASE WHEN C.TIPMOV = 'D' THEN C.AD_VLRCOMINT ELSE 0 END), 0)) DESC
            FETCH FIRST {top_n} ROWS ONLY"""
            if por_empresa:
                detail_columns = ["VENDEDOR", "EMPRESA", "QTD_NOTAS", "VLR_VENDAS", "VLR_DEVOLUCAO", "VLR_LIQUIDO", "COM_LIQUIDA", "MARGEM_MEDIA", "ALIQ_MEDIA"]
            else:
                detail_columns = ["VENDEDOR", "QTD_NOTAS", "VLR_VENDAS", "VLR_DEVOLUCAO", "VLR_LIQUIDO", "COM_LIQUIDA", "MARGEM_MEDIA", "ALIQ_MEDIA"]
        else:
            sql_detail = f"""SELECT
                C.NUNOTA,
                VEN.APELIDO AS VENDEDOR,
                TO_CHAR(C.DTNEG, 'DD/MM/YYYY') AS DT_NEG,
                C.TIPMOV,
                C.AD_VLRBASECOMINT AS VLR_BASE_COM,
                C.AD_VLRCUSTOIARA AS VLR_CUSTO,
                C.AD_MARGEM AS MARGEM,
                C.AD_PMV AS PMV,
                C.AD_ALIQCOMINT AS ALIQUOTA,
                C.AD_VLRCOMINT AS VLR_COMISSAO,
                EMP.NOMEFANTASIA AS EMPRESA
            FROM TGFCAB C
            LEFT JOIN TSIEMP EMP ON EMP.CODEMP = C.CODEMP
            LEFT JOIN TGFVEN VEN ON VEN.CODVEND = C.CODVEND
            {joins_marca}
            WHERE {where_clause} {pf}
            ORDER BY C.DTNEG DESC, C.NUNOTA DESC
            FETCH FIRST {top_n} ROWS ONLY"""
            detail_columns = ["NUNOTA", "VENDEDOR", "DT_NEG", "TIPMOV", "VLR_BASE_COM", "VLR_CUSTO", "MARGEM", "PMV", "ALIQUOTA", "VLR_COMISSAO", "EMPRESA"]

        # Execute KPIs
        kr = await self.executor.execute(sql_kpis)
        if not kr.get("success"):
            return {"response": f"Erro ao consultar comissao: {kr.get('error', '?')}", "tipo": "consulta_banco", "query_executed": sql_kpis[:200], "query_results": 0}

        kd = kr.get("data", [])
        if kd and isinstance(kd[0], (list, tuple)):
            cols = kr.get("columns") or kpi_columns
            kd = [dict(zip(cols, row)) for row in kd]
        kpi_row = kd[0] if kd else {}

        # Execute Detail
        detail_data = []
        qtd_notas = int(kpi_row.get("QTD_NOTAS", 0) or 0)

        if qtd_notas > 0:
            dr = await self.executor.execute(sql_detail)
            if dr.get("success"):
                detail_data = dr.get("data", [])
                if detail_data and isinstance(detail_data[0], (list, tuple)):
                    rc = dr.get("columns") or detail_columns
                    if rc and len(rc) == len(detail_data[0]):
                        detail_data = [dict(zip(rc, row)) for row in detail_data]
                    else:
                        detail_data = [dict(zip(detail_columns, row)) for row in detail_data]

        # Context
        result_data = {"detail_data": detail_data, "columns": detail_columns, "description": f"comissao - {description}", "params": params, "intent": "comissao"}
        if ctx:
            ctx.update("comissao", params, result_data, question)

        # Format
        response = format_comissao_response(kpi_row, detail_data, view, description, params, por_empresa=por_empresa)

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": qtd_notas, "time_ms": elapsed, "_detail_data": detail_data}

    # ---- EXCEL ----
    async def _handle_excel_followup(self, user_context, ctx=None):
        last_result = ctx.last_result if ctx else {}
        if not last_result or not last_result.get("detail_data"):
            return {"response": "Nao tenho dados para gerar o arquivo. Faca uma consulta primeiro.", "tipo": "info", "query_executed": None, "query_results": None}
        data = last_result["detail_data"]
        columns = last_result["columns"]
        description = last_result["description"]
        params = last_result.get("params", {})
        intent = last_result.get("intent", "dados")
        fn = params.get("marca") or params.get("fornecedor") or params.get("empresa") or params.get("periodo", "geral")
        fn = re.sub(r'[^\w\s-]', '', str(fn)).strip().replace(' ', '_')
        filename = f"{intent}_{fn}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        try:
            fp = generate_excel(data=data, columns=columns, filename=filename, title=description.title())
            rp = Path(fp).name
            url = f"/static/exports/{rp}"
            s = "s" if len(data) > 1 else ""
            r = f"\U0001f4ca **Arquivo gerado com sucesso!**\n\n**{len(data)} registro{s}** exportado{s}.\n\n\U0001f4e5 **[Clique aqui para baixar]({url})**\n\n*Arquivo: {rp}*"
            return {"response": r, "tipo": "arquivo", "query_executed": None, "query_results": len(data), "download_url": url}
        except Exception as e:
            return {"response": f"Erro ao gerar arquivo: {str(e)}", "tipo": "erro", "query_executed": None, "query_results": None}

# ===== V5 TOOL USE ACTIVATION =====
from src.agent.ask_core_v5 import patch_smart_agent
patch_smart_agent(SmartAgent)