# PROGRESSO_ATUAL.md

> Ultima atualizacao: 2026-02-13 (sessao 32)
> Historico de sessoes: Ver `PROGRESSO_HISTORICO.md`

---

## STATUS ATUAL

**Smart Agent v3 com Groq 3 Pools + Extra Columns via LLM + Toggle Frontend + Training Scheduler**

- **Web:** http://localhost:8000 (`python start.py`)
- **Login:** Autenticacao via Sankhya MobileLoginSP.login
- **Smart Agent:** `src/llm/smart_agent.py` (~3800+ linhas)
- **Groq 3 Pools:** classify (3 keys), narrate (3 keys), train (1 key) com round-robin e cooldown
- **LLM Classifier:** Groq API via pool_classify (~0.5s) + Ollama (fallback, ~10s)
- **Narrator:** Groq API via pool_narrate (migrado de Ollama)
- **Extra Columns:** Groq detecta colunas extras no prompt (NUM_FABRICANTE, REFERENCIA, etc.) e injeta no SQL
- **Frontend Toggle:** Chips de colunas na mensagem, re-renderiza tabela client-side
- **Training Scheduler:** Roda de madrugada (3h), compila knowledge + auto-aprova aliases
- **SQL Sanitizado:** `_safe_sql()` em todos os pontos de interpolacao
- **Scoring:** Keywords manuais + compiladas (Knowledge Compiler), resolve 90%+ em 0ms
- **Filtros:** FILTER_RULES manuais + compiladas + Groq interpretacao semantica
- **Contexto:** Conversa por usuario com heranca de parametros + extra_columns
- **Produto:** Busca por codigo fabricante + similares + visao 360 + aplicacao/veiculo
- **Apelidos:** AliasResolver com auto-learning (feedback + sequencia)

**Arquivos principais:**
- `src/llm/smart_agent.py` - Smart Agent v3 (GroqKeyPool + 3 pools + extra_columns + _safe_sql + daily_training)
- `src/llm/knowledge_compiler.py` - Knowledge Compiler (auto-gera inteligencia)
- `src/llm/train.py` - **NOVO** - CLI para treinamento manual
- `src/llm/alias_resolver.py` - Sistema de apelidos de produto
- `src/llm/knowledge_base.py` - Knowledge Base com TF-IDF
- `src/llm/query_executor.py` - Executor seguro de SQL
- `src/llm/query_logger.py` - Logger de queries
- `src/api/app.py` - API FastAPI (auth + pools admin + train endpoint + table_data)
- `src/api/static/index.html` - Frontend (login + chat + column toggles)
- `tests/test_smart_agent.py` - **NOVO** - Testes pytest basicos
- `.env` - Config (Sankhya, Groq pools, Ollama, Training)

---

## SESSAO 32 - Groq 3 Pools + Colunas Extras + Toggle + Training + Limpeza (2026-02-13)

### O que foi feito (12 fases):

#### Fase 1: GroqKeyPool + _groq_request + 3 pools
1. **`GroqKeyPool`** - Classe com round-robin, cooldown por rate limit, contadores de uso/erro, reset diario
2. **`_make_pool(env_var, name)`** - Factory que le chaves virgula-separadas do .env
3. **3 pools globais:** `pool_classify`, `pool_narrate`, `pool_train`
4. **Fallback legado** - Se `GROQ_POOL_CLASSIFY` vazio, usa `GROQ_API_KEY` para todos os pools
5. **`_groq_request()`** - Helper async via httpx com rate limit handling e mark_error

#### Fase 2: extra_columns no prompt do Groq
1. **LLM_CLASSIFIER_PROMPT** atualizado com campo `extra_columns` (lista de colunas extras)
2. **Todos os ~25 exemplos** receberam `,"extra_columns":null`
3. **4 novos exemplos** com extra_columns populado (NUM_FABRICANTE, REFERENCIA, etc.)
4. **`groq_classify()`** reescrita para usar `pool_classify` e `_groq_request()`

#### Fase 3: Narrador migrado de Ollama para Groq
1. **`llm_narrate()`** reescrita para usar `pool_narrate` via `_groq_request()`
2. **`clean_thinking_leak()`** removida (nao necessaria com Groq)
3. **`ollama_classify()`** usa inline regex no lugar de `clean_thinking_leak`

#### Fase 4: Backend - propagar extra_columns
1. **`EXISTING_SQL_COLUMNS`** - Set de colunas ja presentes no SQL base
2. **`EXTRA_SQL_FIELDS`** - Dict de campos extras injetaveis no SQL (NUM_ORIGINAL, REFERENCIA, etc.)
3. **`COLUMN_NORMALIZE`** - Mapa de normalizacao (FABRICANTE -> NUM_FABRICANTE, etc.)
4. **`ConversationContext._extra_columns`** substitui `visible_columns`
5. **Removidos:** `DEFAULT_COLUMNS`, `COLUMN_ALIASES`, `_resolve_column_names()`, `detect_column_request()`
6. **Layer 0.3 (COLUNAS DINAMICAS)** removida de `_ask_core`
7. **`_handle_pendencia_compras`** aceita `extra_columns`, injeta no SQL, persiste no contexto
8. **Layers 1+ e 2** extraem extra_columns do LLM result e passam para o handler

#### Fase 5: Formatter dinamico com colunas extras
1. **`format_pendencia_response()`** reescrita com parametro `extra_columns`
2. **View "itens"** - Colunas base + extras inseridas antes das numericas
3. **View "pedidos"** - Colunas agregadas + extras
4. **Feedback visual** - "Colunas extras: **Cod. Fabricante, Referencia**"

#### Fase 6: Frontend toggle de colunas
1. **`ChatResponse.table_data`** - Novo campo Pydantic (columns, rows, visible_columns)
2. **Endpoint `/api/chat`** extrai `_detail_data` e `_visible_columns` do smart_result
3. **CSS** - `.column-toggles`, `.col-chip`, `.col-chip.active` com estilo dark theme
4. **`TOGGLEABLE_COLUMNS`** - 18 colunas toggleaveis com labels amigaveis
5. **`renderColumnToggles()`** - Cria chips baseados nos dados disponiveis
6. **`rerenderTable()`** - Re-renderiza tabela HTML com colunas selecionadas, formatacao de valores
7. **`_detail_data` recolocado** no result do `ask()` para o endpoint usar

#### Fase 7: Training scheduler + monitoramento
1. **`daily_training()`** - Compila knowledge + auto-aprova aliases de alta confianca
2. **`_training_scheduler()`** - Loop infinito que roda no horario configurado (TRAINING_HOUR)
3. **`/api/admin/pools`** - Endpoint GET para status dos pools Groq (admin only)
4. **`/api/admin/train`** - Endpoint POST para treinamento manual (admin only)
5. **`src/llm/train.py`** - CLI: `--full` (reprocessar tudo), `--pools` (status)
6. **Scheduler startado** no `app.py` startup via `asyncio.create_task`

#### Fase 8: Limpeza de codigo antigo
1. **`_format_column_value()`** removida (substituida por inline no formatter)
2. **Verificado:** nenhuma referencia a DEFAULT_COLUMNS, detect_column_request, COLUMN_ALIASES

#### Fase 9: Sanitizar SQL (_safe_sql)
1. **`_safe_sql()`** - Remove `;`, `--`, `/*`, `\`, `\x00`; escapa aspas simples
2. **Aplicado em:** `_build_where_extra` (marca, fornecedor, empresa, comprador, produto_nome, aplicacao)
3. **Aplicado em:** `buscar_codigo_fabricante`, `buscar_similares_por_codigo`, `_handle_aplicacao`
4. **`nunota` e `codprod`** agora usam `int()` para garantir tipo numerico

#### Fase 10: requirements.txt
1. **`openpyxl>=3.1.0`** adicionado (ja existia o arquivo, faltava openpyxl)

#### Fase 11: Testes pytest basicos
1. **`tests/test_smart_agent.py`** com 5 classes:
   - `TestExtractEntities` (5 testes) - marca, fornecedor, empresa, noise word, sem entidade
   - `TestScoreIntent` (5 testes) - pendencia, saudacao, estoque, vendas, ajuda
   - `TestSafeSql` (5 testes) - normal, aspas, injection, vazio, semicolon
   - `TestColumnNormalize` (4 testes) - previsao, fabricante, original, referencia
   - `TestGroqKeyPool` (5 testes) - criacao vazia, round-robin, cooldown, stats, mark_error

#### Fase 12: .env com chaves dos pools
1. **`GROQ_POOL_CLASSIFY`**, **`GROQ_POOL_NARRATE`**, **`GROQ_POOL_TRAIN`** adicionados
2. **`TRAINING_HOUR=3`** adicionado
3. Por enquanto usa a mesma chave legado (usuario deve adicionar chaves extras depois)

### Pendente:
- [ ] Testar no servidor real com perguntas reais
- [ ] Obter chaves Groq adicionais para os pools (3 classify + 3 narrate)
- [ ] Implementar `_handle_financeiro()` (intent detectado pelo compiler)
- [ ] Dashboard HTML
- [ ] Tela admin de apelidos no frontend

---

> Sessoes anteriores (28-31): Ver `PROGRESSO_HISTORICO.md`
