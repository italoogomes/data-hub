# PROGRESSO_ATUAL.md

> Ultima atualizacao: 2026-02-20 (sessao 38)
> Historico de sessoes: Ver `PROGRESSO_HISTORICO.md`

---

## STATUS ATUAL

**Smart Agent V5 Tool Use + Haiku Classifier + Guardrails + Elastic Hybrid Search + Vendas com Devolucoes + Cerebro Analitico V2**

- **Web:** http://localhost:8000 (`python start.py`)
- **Login:** Autenticacao via Sankhya MobileLoginSP.login
- **Arquitetura V5:** `route() → ToolCall → dispatch() → handler → result` (src/agent/ask_core_v5.py)
- **Routing:** Brain (analitica) → Multi-step → Product → **Haiku classifier** → FC Groq (backup) → Scoring + Fallback
- **Classificador:** Claude Haiku (Layer 1) substitui scoring keywords. Groq FC vira backup. Scoring vira ultimo recurso.
- **Groq 3 Pools:** classify (3 keys, 70b), narrate (3 keys, 8b), train (1 key) com round-robin e cooldown
- **Cerebro Analitico V2:** Intercepta no roteamento (com contexto → 70b direto) + na narracao (sem contexto → routing normal + 70b narracao)
- **Elasticsearch 8.17:** 393k produtos, 57k parceiros indexados
- **Guardrails:** Rate limiting (30/min), table whitelist (11 tabelas), security event logging
- **Multi-step:** Comparacoes temporais/entidade (ex: "compare janeiro vs fevereiro")
- **Narrator:** Groq com summaries especificos por dominio (pendencia, vendas, produto, estoque)
- **SQL Sanitizado:** `safe_sql()` + `SafeQueryExecutor` com whitelist ativa + callback security events
- **Testes:** 100 testes (98 passando, 2 pre-existentes em v3_backup)

**Intents ativos:** `pendencia_compras`, `estoque`, `vendas`, `comissao`, `financeiro`, `inadimplencia`, `rastreio_pedido`, `busca_produto`, `busca_parceiro`, `produto_360`, `buscar_similares`, `conhecimento`, `saudacao`, `ajuda`, `brain_analyze`

---

## ARQUITETURA V5 - ARQUIVOS PRINCIPAIS

### Core (novo - refatoracao modular)
- `src/agent/ask_core_v5.py` — Core dispatch V5 (~530 linhas) - brain → multistep → route → dispatch → handler
- `src/agent/haiku_classifier.py` — **NOVO** — Classificador Claude Haiku (Layer 1): haiku_classify + _parse_haiku_response + CLASSIFIER_SYSTEM
- `src/agent/brain.py` — Cerebro Analitico V2: is_analytical_query + collect_session_context + brain_analyze + ANALYTICAL_SYSTEM
- `src/agent/tool_router.py` — Router: Haiku → FC Groq → Scoring + Fallback
- `src/agent/tools.py` — Definicoes de tools + ToolCall + INTENT_TO_TOOL (inclui brain_analyze)
- `src/agent/scoring.py` — Score por keywords (agora Layer 3 fallback) + COLUMN_NORMALIZE + detect_view_mode
- `src/agent/entities.py` — Entity extraction (marca, empresa, vendedor, etc)
- `src/agent/context.py` — ConversationContext + follow-up detection
- `src/agent/session.py` — SessionStore (memoria por usuario)
- `src/agent/product.py` — detect_product_query + is_product_code + resolve_manufacturer_code
- `src/agent/narrator.py` — llm_narrate + build_*_summary (pendencia, vendas, estoque, produto) + brain narracao
- `src/agent/multistep.py` — detect_multistep + extract_kpis_from_result + StepResult

### SQL
- `src/sql/__init__.py` — _build_periodo_filter + _build_pendencia_where + _build_vendas_where

### Formatters
- `src/formatters/__init__.py` — format_pendencia_response + format_vendas_response + format_estoque_response
- `src/formatters/comparison.py` — format_comparison (multi-step)

### Elasticsearch
- `src/elastic/search.py` — ElasticSearchEngine (search_products, search_partners, health)
- `src/elastic/mappings.py` — Schema dos indices (code_analyzer, brazilian analyzer)
- `src/elastic/indexer.py` — Indexador de produtos e parceiros

### LLM
- `src/llm/smart_agent.py` — Smart Agent (~2700 linhas) - handlers de cada dominio
- `src/llm/groq_client.py` — Groq 3 pools + groq_request + groq_classify
- `src/llm/classifier.py` — LLM classifier (70b → 8b → Ollama)
- `src/llm/knowledge_base.py` — Knowledge Base com TF-IDF
- `src/llm/knowledge_compiler.py` — Compila knowledge em scores/filtros
- `src/llm/query_executor.py` — SafeQueryExecutor (whitelist + row limit + security callback)
- `src/llm/query_logger.py` — QueryLogger (JSONL + security events)
- `src/llm/alias_resolver.py` — AliasResolver (apelidos de produto)
- `src/llm/train.py` — CLI para treinamento manual

### API + Frontend
- `src/api/app.py` — FastAPI (auth + rate limiter + pools admin + train)
- `src/api/static/index.html` — Frontend (login + chat + column toggles)

### Testes
- `tests/test_smart_agent.py` — 86 testes (entities, scoring, safe_sql, columns, pool, is_product_code, elastic_query, produto_summary, vendas_where, vendas_devolucoes, is_analytical_query, collect_session_context, brain_result, detail_data_key_fix, summarize_data, format_context_rich)
- `tests/test_haiku_classifier.py` — **NOVO** — 14 testes (parse_json, parse_markdown, parse_texto_extra, texto_invalido, json_sem_tool, string_vazia, brain_analyze, params_complexos, build_user_message, config, intent_to_tool)

---

## SESSAO 38 - Substituir Scoring por Classificador Inteligente (Claude Haiku) (2026-02-20)

### O que foi feito

#### Problema
O scoring por keywords errava queries ambiguas:
- "qual a proxima entrega do item P618689?" → scoring dava `estoque` (por "item") quando deveria ser `pendencia_compras`
- "como melhorar a entrega?" → scoring dava `estoque` quando deveria ser `brain_analyze`
- "boletos do cliente X" → confundia `financeiro` com `busca_cliente`

#### Solucao: Claude Haiku como Layer 1

Nova arquitetura de roteamento (3 camadas):
```
Triviais (saudacao/ajuda/excel) → scoring rapido (<1ms)
Layer 1 (Haiku): classificacao inteligente (~200ms) — entende contexto semantico
Layer 2 (Groq FC): backup se Haiku falhar (~300ms)
Layer 3 (Scoring + Fallback): ultimo recurso se tudo falhar
```

#### Arquivos criados
1. **`src/agent/haiku_classifier.py`** (novo):
   - `CLASSIFIER_SYSTEM`: prompt completo com 12 ferramentas, regras de classificacao, exemplos, disambiguacao
   - `haiku_classify()`: chama Anthropic Messages API via httpx, retorna ToolCall
   - `_build_user_message()`: monta mensagem com contexto da sessao
   - `_parse_haiku_response()`: parse robusto de JSON (suporta markdown wrappers, texto extra, JSON aninhado)
   - Config: `USE_HAIKU_CLASSIFIER`, `HAIKU_MODEL`, `HAIKU_TIMEOUT`, `ANTHROPIC_API_KEY`

2. **`tests/test_haiku_classifier.py`** (novo):
   - 14 testes: parse JSON, markdown, texto extra, invalido, brain_analyze, params complexos, config, build_user_message
   - Lista `EXPECTED_CLASSIFICATIONS` com 17 cenarios para validacao manual

#### Arquivos modificados
3. **`src/agent/tool_router.py`** — Reescrita da funcao `route()`:
   - Triviais (scoring) → Haiku (Layer 1) → FC Groq (Layer 2) → Scoring + Fallback (Layer 3)
   - Feature flag `USE_HAIKU_CLASSIFIER` — quando false, fluxo antigo intacto
   - Merge de params Haiku com regex entities via `_merge_fc_with_entities()`
   - Logs: `[ROUTER] Layer 1 (Haiku): consultar_pendencias(...) conf=95% | 203ms`

4. **`src/agent/ask_core_v5.py`** — Adicionado handler `brain_analyze` no dispatch:
   - Se Haiku retorna brain_analyze → tenta brain com contexto → fallback knowledge base
   - Dois caminhos para brain: (a) is_analytical_query() antes do router, (b) Haiku via router

5. **`src/agent/tools.py`** — `brain_analyze` adicionado a `INTENT_TO_TOOL` e `TOOL_TO_INTENT`

6. **`.env`** — Adicionado `USE_HAIKU_CLASSIFIER=true`, `HAIKU_MODEL`, `HAIKU_TIMEOUT`

7. **`src/core/config.py`** — Adicionada secao Anthropic Haiku

8. **`requirements.txt`** — `anthropic>=0.40.0` (descomentado)

#### Feature flags
- `USE_HAIKU_CLASSIFIER=true` → Haiku como Layer 1, FC como backup, scoring como fallback
- `USE_HAIKU_CLASSIFIER=false` → fluxo antigo intacto (scoring → FC → fallback)
- Sem ANTHROPIC_API_KEY → Haiku pulado silenciosamente, cai pro FC

#### Fluxo completo
```
Pergunta: "qual a proxima entrega do item P618689?"

1. Brain check: is_analytical=False → skip
2. Multi-step: nao detectado → skip
3. Product: is_product_code=True → Layer 0.5a roteia pro Elastic

Pergunta: "pendencias atrasadas acima de 50 mil"

1. Brain check: is_analytical=False → skip
2. Triviais: nao → skip
3. [HAIKU] consultar_pendencias({"apenas_atrasados": true, "valor_minimo": 50000}) conf=95% | 0.2s
4. Merge: regex adiciona marca se detectada
5. [ROUTER] Layer 1 (Haiku): consultar_pendencias conf=95% | 203ms
6. Dispatch → handler → resultado

Pergunta: "por que caiu o faturamento?" (sem contexto)

1. Brain check: is_analytical=True, sem contexto → skip
2. Triviais: nao → skip
3. [HAIKU] brain_analyze({}) conf=90% | 0.2s
4. Dispatch: brain_analyze → collect_session_context() → None → knowledge base → fallback
```

### Testes (100 total, 98 passando)
- **test_smart_agent.py:** 84/86 (mesmos 2 pre-existentes em v3_backup)
- **test_haiku_classifier.py:** 14/14

---

## PENDENTE

- [ ] Testar no servidor real: Haiku classificando queries diversas
- [ ] Testar no servidor real: fallback FC quando Haiku timeout
- [ ] Testar no servidor real: USE_HAIKU_CLASSIFIER=false (fluxo antigo)
- [ ] Testar no servidor real: brain follow-up ("pendencias nakata" → "o que posso fazer?")
- [ ] Testar no servidor real: brain standalone ("por que caiu o faturamento?")
- [ ] Testar no servidor real: brain fallback (rate limit 70b → 8b → routing normal)
- [ ] Testar no servidor real: brain vs multi-step ("como melhorar o faturamento?" com/sem contexto)
- [ ] Testar no servidor real: busca hibrida Elastic com codigos (P618689, W950)
- [ ] Testar no servidor real: vendas com devolucoes ("faturamento do alvaro" → "quanto de devolucao?")
- [ ] Monitorar custo Haiku (~$1/dia estimado para 4000 queries)
- [ ] Implementar `_handle_financeiro()` completo (atualmente basico)
- [ ] Dashboard HTML (substituir Power BI)
- [ ] Tela admin de apelidos no frontend
- [ ] Corrigir 2 testes pre-existentes em v3_backup (test_sem_entidade, test_cooldown)

---

> Sessoes anteriores (1-37f): Ver `PROGRESSO_HISTORICO.md`
