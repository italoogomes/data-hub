# PROMPT DE REFATORAÇÃO: Data Hub - Smart Agent v4

> **OBJETIVO**: Refatorar o `smart_agent.py` monolítico (4819 linhas) em módulos limpos, mantendo 100% da lógica existente. O Claude Code tem acesso ao projeto completo e deve executar esta refatoração.

---

## REGRA ZERO

**NUNCA altere lógica de negócio.** Esta é uma refatoração ESTRUTURAL. O comportamento do sistema deve ser IDÊNTICO antes e depois. Se encontrar bugs durante a refatoração, documente-os mas NÃO corrija - são tarefas separadas.

---

## ARQUITETURA ATUAL (monolítica)

```
src/llm/smart_agent.py  ← 4819 linhas, FAZ TUDO
├── GroqKeyPool (56-147)
├── _groq_request (150-204)
├── INTENT_SCORES (214-322)
├── INTENT_THRESHOLDS (325-336)
├── normalize/tokenize (346-364)
├── score_intent (367-386)
├── detect_view_mode (389-395)
├── LLM_CLASSIFIER_PROMPT (402-608)
├── groq_classify (610-680)
├── ollama_classify (690-820)
├── llm_classify (825-846)
├── NARRATOR_SYSTEM (853-867)
├── llm_narrate (870-905)
├── build_*_summary (908-1033)
├── extract_entities (1040-1289)
├── EMPRESA_DISPLAY (1292-1301)
├── SQL TEMPLATES (1304-1456)
├── FORMATTING (1492-1507)
├── PRODUTO resolvers (1510-1738)
├── format_produto_360 (1741-1820)
├── format_pendencia_response (2004-2128)
├── format_vendas_response (2131-2146)
├── format_estoque_response (2149-2243)
├── generate_excel (2215-2242)
├── ConversationContext (2775-2834)
├── FILTER_RULES (2273-2315)
├── COMPILED KNOWLEDGE (2318-2388)
├── COLUMN CONSTANTS (2392-2445)
├── _is_complex_query (2448-2482)
├── _llm_to_filters (2485-2548)
├── detect_followup (2551-2580)
├── detect_filter_request (2583-2623)
├── apply_filters (2626-2689)
├── daily_training (2698-2755)
├── SmartAgent class (2841-4820)
│   ├── __init__ (2842-2861)
│   ├── _load_entities (2882-2908)
│   ├── ask (entry point) (2910-2970)
│   ├── _ask_core (3013-3340)
│   ├── _dispatch (3341-3370)
│   ├── _handle_filter_followup (3372-3486)
│   ├── _handle_saudacao (3488-3499)
│   ├── _handle_ajuda (3501-3509)
│   ├── _handle_fallback (3511-3513)
│   ├── _handle_pendencia_compras (3515-3763)
│   ├── _handle_estoque (3765-3818)
│   ├── _handle_vendas (3820-3997)
│   ├── _handle_rastreio_pedido (3999-4310)
│   ├── _handle_busca_produto (4312-4410)
│   ├── _handle_busca_parceiro (4412-4490)
│   ├── _handle_busca_fabricante (4492-4580)
│   ├── _handle_similares (4582-4620)
│   ├── _handle_busca_aplicacao (4622-4650)
│   ├── _handle_produto_360 (4652-4797)
│   └── _handle_excel_followup (4799-4820)
```

## ARQUITETURA NOVA (modular)

```
src/
├── core/                          ← JÁ CRIADO
│   ├── __init__.py
│   ├── config.py                  ← Todas as env vars centralizadas
│   └── utils.py                   ← normalize, tokenize, fmt_brl, fmt_num, safe_sql, trunc, sanitize_code
│
├── llm/                           ← PARCIALMENTE REFATORADO
│   ├── groq_client.py             ← JÁ CRIADO - GroqKeyPool + groq_request + pools globais
│   ├── classifier.py              ← JÁ CRIADO - LLM_CLASSIFIER_PROMPT + groq/ollama/llm_classify
│   ├── narrator.py                ← JÁ CRIADO - NARRATOR + build_*_summary
│   ├── knowledge_base.py          ← MANTER (já modular)
│   ├── knowledge_compiler.py      ← MANTER (já modular)
│   ├── alias_resolver.py          ← MANTER (já modular)
│   ├── query_executor.py          ← MANTER (já modular)
│   ├── query_logger.py            ← MANTER (já modular)
│   ├── result_validator.py        ← MANTER (já modular)
│   ├── review_session.py          ← MANTER (já modular)
│   ├── chat.py                    ← MANTER (já modular)
│   ├── llm_client.py              ← MANTER (compatibilidade)
│   ├── agent.py                   ← MANTER (legado, usado no app.py)
│   ├── train.py                   ← MANTER
│   └── smart_agent.py             ← AGORA É SÓ UM SHIM de compatibilidade (ver abaixo)
│
├── agent/                         ← NOVO - lógica do Smart Agent modularizada
│   ├── __init__.py                ← JÁ CRIADO
│   ├── scoring.py                 ← JÁ CRIADO - INTENT_SCORES, thresholds, score_intent, compiled knowledge
│   ├── context.py                 ← JÁ CRIADO - ConversationContext, followup, FILTER_RULES
│   ├── entities.py                ← CRIAR - extract_entities, EMPRESA_DISPLAY
│   ├── filters.py                 ← CRIAR - apply_filters, detect_filter_request, _is_complex_query, _llm_to_filters
│   ├── columns.py                 ← CRIAR - COLUMN_LABELS, COLUMN_NORMALIZE, EXISTING_SQL_COLUMNS, EXTRA_SQL_FIELDS
│   ├── sql_builder.py             ← CRIAR - SQL templates, sql_pendencia_compras, _build_where_extra, _build_periodo_filter, _build_vendas_where
│   ├── formatters.py              ← CRIAR - format_pendencia_response, format_vendas_response, format_estoque_response, format_produto_360, generate_excel + aggregation views
│   ├── product.py                 ← CRIAR - resolve_manufacturer_code, buscar_similares, detect_product_query, SIMILAR_WORDS
│   ├── training.py                ← CRIAR - daily_training, _training_scheduler
│   ├── handlers/                  ← CRIAR - cada handler em seu arquivo
│   │   ├── __init__.py
│   │   ├── pendencia.py           ← _handle_pendencia_compras
│   │   ├── vendas.py              ← _handle_vendas
│   │   ├── estoque.py             ← _handle_estoque
│   │   ├── produto.py             ← _handle_busca_fabricante, _handle_similares, _handle_produto_360, _handle_busca_aplicacao
│   │   ├── busca.py               ← _handle_busca_produto, _handle_busca_parceiro
│   │   ├── rastreio.py            ← _handle_rastreio_pedido
│   │   └── misc.py                ← _handle_saudacao, _handle_ajuda, _handle_fallback, _handle_excel, _handle_filter_followup
│   └── smart_agent.py             ← NOVO SmartAgent class (~300 linhas) - orquestrador slim
│
├── elastic/                       ← MANTER (já modular)
├── api/                           ← MANTER (ajustar imports)
└── mcp/                           ← MANTER
```

---

## PASSO A PASSO DA REFATORAÇÃO

### PASSO 1: Criar src/agent/entities.py

Extrair de `smart_agent.py` linhas 1040-1301:
- `extract_entities()` - a função inteira
- `EMPRESA_DISPLAY` dict

**Imports necessários:**
```python
import re
from src.core.utils import normalize, tokenize
```

**CUIDADO:** A função usa `known_marcas`, `known_empresas`, `known_compradores` como parâmetros - manter isso.

### PASSO 2: Criar src/agent/columns.py

Extrair de `smart_agent.py` linhas 2392-2445:
- `EXISTING_SQL_COLUMNS`
- `EXTRA_SQL_FIELDS`
- `COLUMN_NORMALIZE`
- `COLUMN_LABELS`
- `COLUMN_MAX_WIDTH`

Sem imports especiais - são apenas constantes.

### PASSO 3: Criar src/agent/filters.py

Extrair de `smart_agent.py` linhas 2448-2689:
- `_is_complex_query()`
- `_llm_to_filters()`
- `detect_filter_request()`
- `apply_filters()`

**Imports necessários:**
```python
import re
from src.agent.context import FILTER_RULES
from src.agent.scoring import _COMPILED_RULES
```

**CUIDADO:** `detect_filter_request` usa `FILTER_RULES` do context.py e `_COMPILED_RULES` do scoring.py.

### PASSO 4: Criar src/agent/sql_builder.py

Extrair de `smart_agent.py` linhas 1304-1489:
- `JOINS_PENDENCIA`
- `WHERE_PENDENCIA`
- `_build_where_extra()`
- `sql_pendencia_compras()`
- `_build_periodo_filter()`
- `PERIODO_NOMES`
- `_build_vendas_where()`

**Imports necessários:**
```python
from src.core.utils import safe_sql
from src.agent.entities import EMPRESA_DISPLAY
```

### PASSO 5: Criar src/agent/formatters.py

Extrair de `smart_agent.py` linhas 1492-2243:
- `format_pendencia_response()`
- `format_vendas_response()`
- `format_estoque_response()`
- `format_produto_360()`
- `generate_excel()`
- `format_comprador_marca()` (se existir)
- `format_fornecedor_marca()` (se existir)
- `detect_aggregation_view()` (se existir)

**Imports necessários:**
```python
from src.core.utils import fmt_brl, fmt_num, trunc
from src.agent.columns import COLUMN_LABELS, COLUMN_MAX_WIDTH
```

### PASSO 6: Criar src/agent/product.py

Extrair de `smart_agent.py` linhas 1510-1738:
- `SIMILAR_WORDS`
- `resolve_manufacturer_code()`
- `buscar_similares()`
- `buscar_similares_por_codigo()`
- `detect_product_query()`

**Imports necessários:**
```python
import re
from src.core.utils import safe_sql, sanitize_code
```

### PASSO 7: Criar src/agent/training.py

Extrair de `smart_agent.py` linhas 2694-2773:
- `daily_training()`
- `_training_scheduler()`
- `TRAINING_HOUR`

**Imports necessários:**
```python
import os
import asyncio
from datetime import datetime
from src.core.config import TRAINING_HOUR
from src.llm.groq_client import pool_train
from src.agent.scoring import reload_compiled
```

### PASSO 8: Criar src/agent/handlers/ (cada handler em seu arquivo)

Cada handler é um método async que recebe `(self, question, user_context, t0, params, ctx, ...)` e retorna um dict com `{response, tipo, query_executed, query_results, time_ms}`.

Para cada handler, transformar de método da classe SmartAgent para uma **função standalone** que recebe o executor, elastic e outros como parâmetros:

```python
# Exemplo: src/agent/handlers/pendencia.py
async def handle_pendencia_compras(
    question, user_context, t0, params, view_mode, ctx,
    executor, elastic=None, llm_filters=None, extra_columns=None,
    known_marcas=None, known_empresas=None, known_compradores=None,
):
    # ... lógica extraída de SmartAgent._handle_pendencia_compras
```

**Handlers a criar:**
- `pendencia.py`: `handle_pendencia_compras` (linhas 3515-3763)
- `vendas.py`: `handle_vendas` (linhas 3820-3997)
- `estoque.py`: `handle_estoque` (linhas 3765-3818)
- `produto.py`: `handle_busca_fabricante`, `handle_similares`, `handle_produto_360`, `handle_busca_aplicacao` (linhas 4492-4797)
- `busca.py`: `handle_busca_produto`, `handle_busca_parceiro` (linhas 4312-4490)
- `rastreio.py`: `handle_rastreio_pedido` (linhas 3999-4310)
- `misc.py`: `handle_saudacao`, `handle_ajuda`, `handle_fallback`, `handle_excel_followup`, `handle_filter_followup`

### PASSO 9: Criar src/agent/smart_agent.py (orquestrador slim)

Este é o NOVO SmartAgent - apenas ~300 linhas. Ele:
1. Inicializa executor, elastic, knowledge_base, etc.
2. Implementa `ask()` e `_ask_core()` que são o roteador principal
3. Delega para os handlers importados dos módulos

```python
"""Smart Agent v4 - Orquestrador slim."""

import time
from typing import Optional

from src.core.utils import normalize, tokenize
from src.agent.scoring import (
    score_intent, detect_view_mode, INTENT_THRESHOLDS,
    CONFIRM_WORDS, load_compiled_knowledge,
)
from src.agent.context import (
    ConversationContext, detect_followup, build_context_hint,
)
from src.agent.entities import extract_entities
from src.agent.filters import (
    detect_filter_request, _is_complex_query, _llm_to_filters, apply_filters,
)
from src.agent.columns import COLUMN_NORMALIZE
from src.agent.product import detect_product_query
from src.llm.classifier import groq_classify, llm_classify
from src.llm.groq_client import pool_classify
from src.llm.knowledge_base import KnowledgeBase, score_knowledge
from src.llm.alias_resolver import AliasResolver
from src.llm.query_executor import SafeQueryExecutor
from src.llm.query_logger import QueryLogger, generate_auto_tags
from src.llm.result_validator import ResultValidator, build_result_data_summary

# Handlers
from src.agent.handlers.pendencia import handle_pendencia_compras
from src.agent.handlers.vendas import handle_vendas
from src.agent.handlers.estoque import handle_estoque
from src.agent.handlers.produto import (
    handle_busca_fabricante, handle_similares,
    handle_produto_360, handle_busca_aplicacao,
)
from src.agent.handlers.busca import handle_busca_produto, handle_busca_parceiro
from src.agent.handlers.rastreio import handle_rastreio_pedido
from src.agent.handlers.misc import (
    handle_saudacao, handle_ajuda, handle_fallback,
    handle_excel_followup, handle_filter_followup,
)


class SmartAgent:
    def __init__(self):
        self.executor = SafeQueryExecutor()
        self._known_marcas = set()
        self._known_empresas = set()
        self._known_compradores = set()
        self._entities_loaded = False
        self.kb = KnowledgeBase()
        self.alias_resolver = AliasResolver()
        self.query_logger = QueryLogger()
        self.result_validator = ResultValidator()
        try:
            from src.elastic.search import ElasticSearchEngine
            self.elastic = ElasticSearchEngine()
        except Exception:
            self.elastic = None
        self._user_contexts = {}
        load_compiled_knowledge()

    # ... _get_context, _load_entities, ask, _ask_core, _dispatch
    # Cada handler chama a função importada passando self.executor, self.elastic, etc.
```

### PASSO 10: Criar shim de compatibilidade em src/llm/smart_agent.py

O `app.py` importa de `src.llm.smart_agent`, então manter compatibilidade:

```python
"""Shim de compatibilidade - redireciona para src.agent.smart_agent."""
# Tudo que app.py e outros módulos importam daqui
from src.agent.smart_agent import SmartAgent
from src.agent.training import daily_training, _training_scheduler
from src.llm.groq_client import pool_classify, pool_narrate, pool_train

# Compatibilidade total - qualquer import antigo continua funcionando
from src.agent.scoring import *
from src.agent.context import *
from src.agent.entities import *
from src.agent.filters import *
from src.agent.columns import *
from src.agent.formatters import *
from src.agent.product import *
from src.core.utils import normalize, tokenize, fmt_brl, fmt_num
from src.core.utils import safe_sql as _safe_sql, trunc as _trunc, sanitize_code as _sanitize_code
```

---

## CHECKLIST DE VALIDAÇÃO

Após cada passo, verificar:
- [ ] `python -c "from src.agent.MODULE import *"` funciona sem erro
- [ ] `python -c "from src.llm.smart_agent import SmartAgent"` continua funcionando
- [ ] `python start.py` inicia sem erro (se possível testar)

Após tudo:
- [ ] `smart_agent.py` original pode ser deletado
- [ ] O novo `src/llm/smart_agent.py` é apenas um shim de ~20 linhas
- [ ] O novo `src/agent/smart_agent.py` é o orquestrador slim (~300-400 linhas)
- [ ] Todos os handlers estão em `src/agent/handlers/`
- [ ] Nenhuma lógica foi alterada, apenas reorganizada

---

## ARQUIVOS JÁ CRIADOS (na refatoração parcial)

Os seguintes arquivos JÁ foram criados e estão prontos:

1. `src/core/__init__.py` ✅
2. `src/core/config.py` ✅ - Todas as env vars centralizadas
3. `src/core/utils.py` ✅ - normalize, tokenize, fmt_brl, fmt_num, safe_sql, trunc, sanitize_code
4. `src/llm/groq_client.py` ✅ - GroqKeyPool + pools globais + groq_request
5. `src/llm/classifier.py` ✅ - LLM_CLASSIFIER_PROMPT + groq_classify + ollama_classify + llm_classify
6. `src/llm/narrator.py` ✅ - NARRATOR_SYSTEM + llm_narrate + build_*_summary
7. `src/agent/__init__.py` ✅
8. `src/agent/scoring.py` ✅ - INTENT_SCORES, thresholds, compiled knowledge, score_intent
9. `src/agent/context.py` ✅ - ConversationContext, followup, FILTER_RULES, build_context_hint

**ATENÇÃO:** O Claude Code deve LER esses arquivos antes de criar os restantes para evitar duplicação e garantir consistência nos imports.

---

## ORDEM DE EXECUÇÃO

1. Ler todos os arquivos já criados em `src/core/` e `src/agent/`
2. Criar `src/agent/entities.py`
3. Criar `src/agent/columns.py`
4. Criar `src/agent/filters.py`
5. Criar `src/agent/sql_builder.py`
6. Criar `src/agent/formatters.py`
7. Criar `src/agent/product.py`
8. Criar `src/agent/training.py`
9. Criar todos os handlers em `src/agent/handlers/`
10. Criar `src/agent/smart_agent.py` (orquestrador slim)
11. Substituir `src/llm/smart_agent.py` pelo shim de compatibilidade
12. Testar imports: `python -c "from src.llm.smart_agent import SmartAgent; print('OK')"`
13. Atualizar `CLAUDE.md` com nova arquitetura
14. Backup do smart_agent.py original como `smart_agent_v3_backup.py`

---

## IMPORTANTE

- O arquivo original `smart_agent.py` tem 4819 linhas. Cada módulo novo deve ter 50-400 linhas MAX.
- Preservar TODOS os print() de debug - são essenciais para troubleshooting em produção.
- Manter os mesmos nomes de funções e assinaturas para compatibilidade.
- Se encontrar lógica duplicada entre handlers, extrair para utils ou um helper compartilhado.
- Os handlers no novo formato recebem `executor`, `elastic`, `kb` etc. como parâmetros em vez de acessar via `self.`
