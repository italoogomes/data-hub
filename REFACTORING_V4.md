# DATA HUB v4 - REFATORAÇÃO MODULAR

## O que foi feito

O monolito `src/llm/smart_agent.py` (4.819 linhas) foi decomposto em 14 módulos especializados.

### Antes vs Depois

```
ANTES: 1 arquivo monolítico
  src/llm/smart_agent.py ........... 4.819 linhas (TUDO misturado)

DEPOIS: 14 módulos com responsabilidades claras
  src/core/utils.py ................ 81 linhas  (normalize, tokenize, fmt_brl)
  src/core/groq_client.py ......... 170 linhas  (GroqKeyPool, pools, groq_request)
  src/agent/scoring.py ............. 287 linhas  (INTENT_SCORES, score_intent)
  src/agent/entities.py ............ 266 linhas  (extract_entities, empresas, cidades)
  src/agent/context.py ............. 189 linhas  (ConversationContext, followup, filters)
  src/agent/classifier.py .......... 472 linhas  (LLM prompt, groq/ollama classify)
  src/agent/narrator.py ............ 200 linhas  (llm_narrate, build summaries)
  src/agent/product.py ............. 409 linhas  (produto 360, fabricante, similares)
  src/agent/training.py ............. 86 linhas  (daily_training, scheduler)
  src/sql/__init__.py .............. 194 linhas  (SQL templates pendência/vendas)
  src/formatters/__init__.py ....... 276 linhas  (format_pendencia/vendas/estoque)
  src/formatters/excel.py ........... 69 linhas  (generate_excel, generate_csv)
  src/llm/smart_agent_v4.py ....... 2.140 linhas (orchestrator + handlers)
```

**Redução do monolito: 55%** (de 4.819 → 2.140 linhas no arquivo principal)

### Módulos preservados (sem alteração)
- `src/api/app.py` - FastAPI server
- `src/api/reports.py` - Relatórios
- `src/elastic/` - Elasticsearch search/sync
- `src/llm/query_executor.py` - Executor SQL Sankhya
- `src/llm/knowledge_base.py` - Knowledge base
- `src/llm/knowledge_compiler.py` - Compilador
- `src/llm/alias_resolver.py` - Aliases
- `src/llm/query_logger.py` - Logger
- `src/llm/result_validator.py` - Validador

## Como ativar

### Passo 1: Backup
```bash
cp src/llm/smart_agent.py src/llm/smart_agent_v3_original.py
```

### Passo 2: Substituir
```bash
mv src/llm/smart_agent_v4.py src/llm/smart_agent.py
```

### Passo 3: Verificar imports em app.py
O `app.py` importa estes símbolos de `smart_agent.py`:
- `SmartAgent` ✅ (presente no v4)
- `_load_compiled_knowledge`, `_COMPILED_LOADED` ✅ (re-exportados)
- `_training_scheduler`, `TRAINING_HOUR` ✅ (re-exportados)
- `pool_classify`, `pool_narrate`, `pool_train` ✅ (re-exportados via imports)
- `daily_training` ✅ (re-exportado)
- `INTENT_SCORES`, `FILTER_RULES` ✅ (re-exportados)

### Passo 4: Verificar imports em knowledge_compiler.py
O `knowledge_compiler.py` importa:
- `INTENT_SCORES` ← agora em `src/agent/scoring.py`
- `FILTER_RULES` ← agora em `src/agent/context.py`

**Precisa atualizar**:
```python
# ANTES (em knowledge_compiler.py)
from src.llm.smart_agent import INTENT_SCORES, FILTER_RULES

# DEPOIS
from src.agent.scoring import INTENT_SCORES
from src.agent.context import FILTER_RULES
```

### Passo 5: Testar
```bash
python -c "from src.llm.smart_agent import SmartAgent; print('OK')"
python -c "from src.agent.scoring import score_intent; print('OK')"
python -c "from src.agent.classifier import llm_classify; print('OK')"
python start.py  # Iniciar o servidor
```

## Arquitetura de Dependências

```
app.py
  └── SmartAgent (src/llm/smart_agent.py)
        ├── core/utils.py         (funções utilitárias)
        ├── core/groq_client.py   (API Groq + key pools)
        ├── agent/scoring.py      (scoring por keywords)
        ├── agent/entities.py     (extração de entidades)
        ├── agent/context.py      (contexto de conversa)
        ├── agent/classifier.py   (LLM classifier Layer 2)
        ├── agent/narrator.py     (narração natural)
        ├── agent/product.py      (busca produto/fabricante)
        ├── agent/training.py     (treinamento diário)
        ├── sql/__init__.py       (templates SQL)
        ├── formatters/           (formatação de respostas)
        └── [módulos existentes preservados]
            ├── llm/query_executor.py
            ├── llm/knowledge_base.py
            ├── llm/alias_resolver.py
            └── elastic/search.py
```

## Próximos passos (evolução futura)

1. **Handlers como módulos separados**: Extrair `_handle_pendencia_compras`, `_handle_vendas`, etc. de `smart_agent.py` para `src/handlers/` (mais ~1000 linhas de redução)

2. **Tool Use / Function Calling**: Com a arquitetura modular, cada handler pode ser registrado como uma "tool" que o LLM pode chamar via Function Calling. O classificador atual (scoring + LLM) pode evoluir para o LLM escolhendo diretamente qual tool chamar.

3. **Testes unitários por módulo**: Agora é possível testar cada módulo independentemente (scoring, entities, formatters, SQL templates).

4. **Novos domínios**: Adicionar `src/handlers/financeiro.py`, `src/handlers/comissao.py` sem tocar no orchestrator.
