# PROGRESSO_ATUAL.md

> Ultima atualizacao: 2026-02-19 (sessao 36)
> Historico de sessoes: Ver `PROGRESSO_HISTORICO.md`

---

## STATUS ATUAL

**Smart Agent V5 Tool Use + Guardrails + Elastic Hybrid Search + Vendas com Devolucoes**

- **Web:** http://localhost:8000 (`python start.py`)
- **Login:** Autenticacao via Sankhya MobileLoginSP.login
- **Arquitetura V5:** `route() → ToolCall → dispatch() → handler → result` (src/agent/ask_core_v5.py)
- **3-Layer Routing:** Layer 0.5 (Produto) → Layer 0.5a (Codigo Produto) → Layer 1 (Scoring) → Layer 2 (Groq FC) → Layer 3 (Fallback)
- **Groq 3 Pools:** classify (3 keys, 70b), narrate (3 keys, 8b), train (1 key) com round-robin e cooldown
- **Elasticsearch 8.17:** 393k produtos, 57k parceiros indexados
- **Guardrails:** Rate limiting (30/min), table whitelist (11 tabelas), security event logging
- **Multi-step:** Comparacoes temporais/entidade (ex: "compare janeiro vs fevereiro")
- **Narrator:** Groq com summaries especificos por dominio (pendencia, vendas, produto, estoque)
- **SQL Sanitizado:** `safe_sql()` + `SafeQueryExecutor` com whitelist ativa + callback security events
- **Testes:** 48 testes (46 passando, 2 pre-existentes em v3_backup)

**Intents ativos:** `pendencia_compras`, `estoque`, `vendas`, `comissao`, `financeiro`, `inadimplencia`, `rastreio_pedido`, `busca_produto`, `busca_parceiro`, `produto_360`, `buscar_similares`, `conhecimento`, `saudacao`, `ajuda`

---

## ARQUITETURA V5 - ARQUIVOS PRINCIPAIS

### Core (novo - refatoracao modular)
- `src/agent/ask_core_v5.py` — Core dispatch V5 (~480 linhas) - route → dispatch → handler
- `src/agent/tool_router.py` — Router: scoring → Groq FC → fallback
- `src/agent/tools.py` — Definicoes de tools + ToolCall + INTENT_TO_TOOL
- `src/agent/scoring.py` — Score por keywords + COLUMN_NORMALIZE + detect_view_mode
- `src/agent/entities.py` — Entity extraction (marca, empresa, vendedor, etc)
- `src/agent/context.py` — ConversationContext + follow-up detection
- `src/agent/session.py` — SessionStore (memoria por usuario)
- `src/agent/product.py` — detect_product_query + is_product_code + resolve_manufacturer_code
- `src/agent/narrator.py` — llm_narrate + build_*_summary (pendencia, vendas, estoque, produto)
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
- `tests/test_smart_agent.py` — 48 testes (entities, scoring, safe_sql, columns, pool, is_product_code, elastic_query, produto_summary, vendas_where, vendas_devolucoes)

---

## SESSAO 36 - V5 Completo + Guardrails + Elastic + Vendas (2026-02-19)

### O que foi feito (6 partes)

#### Parte 1: Fix Multi-step valores identicos
- `_handle_comissao` e `_handle_financeiro` perdiam `data_inicio`/`data_fim` ao criar dict pro periodo
- `extract_kpis_from_result` somava MARGEM_MEDIA em vez de calcular media
- **Arquivos:** `smart_agent.py:2448,2153`, `multistep.py:440`

#### Parte 2: 3 Guardrails Cirurgicos
1. **Rate Limiting:** `SimpleRateLimiter` (30 req/60s por usuario, in-memory sliding window)
2. **Table Whitelist:** 11 tabelas permitidas no SafeQueryExecutor + callback on_security_event
3. **Security Logging:** `log_security_event()` em QueryLogger (rate_limit, sql_blocked, login_failed)
- **Arquivos:** `app.py:84-109,512-525`, `query_executor.py:81,276-279`, `query_logger.py:90-115`, `smart_agent.py:165`

#### Parte 3: Busca Hibrida Elasticsearch
1. `is_product_code()` — detecta codigos puros (P618689, W950, 0986B02486, HU727/1X)
2. `search_products()` reescrito com 3 prioridades:
   - P1 (boost 10): exact term em .raw + all_codes match/fuzzy/wildcard + CODPROD
   - P2 (boost 5): match_phrase em descricao/full_text (slop 2)
   - P3 (boost 1-4): multi_match best_fields + cross_fields + text-as-code
3. Layer 0.5a interceptor: `is_product_code(question)` → direto pro Elastic
- **Arquivos:** `product.py:17-49`, `search.py` (reescrito), `ask_core_v5.py:102-110`

#### Parte 4: Fix Narrador alucina em busca Elastic
- Criou `build_produto_summary()` com contexto explicito "PRODUTOS DO CATALOGO"
- Substitui summary generico que induzia LLM a inventar valores monetarios
- **Arquivos:** `narrator.py:200-259`, `smart_agent.py:52,1902-1908`

#### Parte 5: Fix Vendedor nao filtra em vendas
- `_build_vendas_where` usava chave `vendedor_nome` mas extraction retorna `vendedor`
- Fix: `vendedor = params.get("vendedor") or params.get("vendedor_nome")`
- Adicionou vendedor na descricao do titulo
- **Arquivos:** `src/sql/__init__.py:189-191`, `smart_agent.py:1175`

#### Parte 6: Vendas com Devolucoes (TIPMOV V+D)
- 3 SQLs reescritos com `TIPMOV IN ('V','D')` + CASE WHEN:
  - KPIs: VLR_VENDAS, VLR_DEVOLUCAO, FATURAMENTO (liquido)
  - Top Vendedores: +VLR_VENDAS, +VLR_DEVOLUCAO, ORDER BY liquido
  - Detail: +TIPMOV, FATURAMENTO→VALOR
- Formatter: mostra "Vendas brutas | Devolucoes | Liquido" quando dev > 0
- Tabela top vendedores: 3 formatos (com dev, com margem, basico)
- build_vendas_summary: inclui devolucoes no resumo pro narrador
- **Arquivos:** `smart_agent.py:1183-1328`, `formatters/__init__.py:227-248`, `narrator.py:133-164`

### Testes adicionados nesta sessao (22 novos)
- `TestIsProductCode` (8): alfanumerico, separadores, numerico, texto, curto, sem digito, 2 tokens, multi-palavra
- `TestElasticHybridQuery` (5): prioridade 1 codigo, prioridade 2+3 texto, cross_fields, marca filter, codprod numerico
- `TestBuildProdutoSummary` (4): identifica produtos, codigo buscado, dados produtos, nao inventa valores
- `TestBuildVendasWhere` (4): vendedor gera filtro, vendedor_nome retrocompat, sem vendedor, vendedor+marca
- `TestFormatVendasDevolucoes` (3): sem devolucao, com devolucao, zero vendas

---

## PENDENTE

- [ ] Testar no servidor real: busca hibrida Elastic com codigos (P618689, W950)
- [ ] Testar no servidor real: vendas com devolucoes ("faturamento do alvaro" → "quanto de devolucao?")
- [ ] Testar no servidor real: filtro de vendedor ("faturamento do rafael")
- [ ] Monitorar narrador: verificar que busca Elastic nao alucina mais
- [ ] Implementar `_handle_financeiro()` completo (atualmente basico)
- [ ] Dashboard HTML (substituir Power BI)
- [ ] Tela admin de apelidos no frontend
- [ ] Corrigir 2 testes pre-existentes em v3_backup (test_sem_entidade, test_cooldown)

---

> Sessoes anteriores (1-35d): Ver `PROGRESSO_HISTORICO.md`
