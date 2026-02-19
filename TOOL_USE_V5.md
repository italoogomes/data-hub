# Data Hub V5 — Tool Use Pattern

## O Que Mudou (seguindo o guia arquitetural)

### ✅ Passo 1: Definir Ferramentas por Domínio
**Arquivo:** `src/agent/tools.py` (413 linhas)

11 ferramentas tipadas com JSON Schema:
| Tool | Domínio | Descrição |
|------|---------|-----------|
| `consultar_pendencias` | Compras | Pedidos pendentes, entregas, previsões |
| `consultar_vendas` | Vendas | Faturamento, ranking vendedores, margem |
| `consultar_estoque` | Estoque | Saldo, disponibilidade, crítico |
| `buscar_produto` | Catálogo | Busca Elasticsearch por nome/código |
| `buscar_parceiro` | Cadastro | Cliente/fornecedor por nome/CNPJ |
| `rastrear_pedido` | Vendas | Status de pedido de venda |
| `produto_360` | Catálogo | Visão completa (estoque+pend+vendas) |
| `buscar_similares` | Catálogo | Cross-reference entre marcas |
| `consultar_conhecimento` | KB | Processos e regras da empresa |
| `saudacao` | Sistema | Cumprimentos |
| `ajuda` | Sistema | Menu de ajuda |

Cada tool tem parâmetros tipados (string, integer, enum, array).

### ✅ Passo 2: Implementar Function Calling
**Arquivo:** `src/agent/tool_router.py` (370 linhas)

Roteador de 3 camadas:
```
Layer 1 (Scoring)     → Keywords rápidos (<5ms) para intents óbvios
Layer 2 (FC)          → Groq Function Calling - LLM escolhe tool + params (~300ms)
Layer 3 (Fallback)    → Heurística com entidades detectadas
```

**ANTES:** Prompt gigante de 23k chars enviado ao LLM, que retornava JSON com intent.
**DEPOIS:** LLM recebe as 11 tool definitions e CHAMA a ferramenta diretamente com parâmetros tipados.

### ✅ Passo 3: Memória de Sessão
**Arquivo:** `src/agent/session.py` (227 linhas)

- `SessionMemory`: histórico de mensagens (user + assistant) por sessão
- `SessionStore`: store global com TTL (1h) e cleanup automático
- `get_history_for_llm()`: últimas N mensagens formatadas pro LLM
- Acumula entidades entre turnos

### ✅ Passo 4: Novo Orchestrator
**Arquivo:** `src/agent/ask_core_v5.py` (281 linhas)

Substitui `_ask_core` de ~370 linhas por ~80 linhas:
```python
# ANTES (v4) - 370 linhas de if/elif
scores = score_intent(tokens)
if best_score >= threshold:
    if best_intent == "pendencia_compras": ...
    elif best_intent == "vendas": ...
    # ... 15 elifs
elif has_entity:
    # ... mais lógica
elif USE_LLM_CLASSIFIER:
    llm_result = await llm_classify(question)
    intent = llm_result["intent"]
    if intent == "pendencia_compras": ...
    # ... mais 15 elifs
else:
    # fallback

# DEPOIS (v5) - ~80 linhas
tool_call = await tool_route(question, ctx=ctx, ...)
result = await dispatch_v5(self, tool_call, ...)
```

### Arquivos Modificados
| Arquivo | Mudança |
|---------|---------|
| `src/core/groq_client.py` | +tools/tool_choice params no groq_request |
| `src/agent/context.py` | +detect_filter_request, +apply_filters (faltavam) |

---

## Como Ativar

### Opção A: Monkey-patch (zero risco, reversível)
Adicionar no final do `src/llm/smart_agent.py` (ou v4):

```python
# ===== V5 TOOL USE ACTIVATION =====
from src.agent.ask_core_v5 import patch_smart_agent
patch_smart_agent(SmartAgent)
```

Para reverter: remover essas 2 linhas.

### Opção B: Substituir _ask_core diretamente
Editar `SmartAgent.__init__` ou `_ask_core` no smart_agent.py para importar e usar as novas funções.

### Opção C: Flag de ambiente (recomendada)
```python
# No smart_agent.py, no final do arquivo:
import os
if os.getenv("USE_TOOL_ROUTER", "false").lower() in ("true", "1"):
    from src.agent.ask_core_v5 import patch_smart_agent
    patch_smart_agent(SmartAgent)
    print("[SMART] V5 Tool Use ativado via env USE_TOOL_ROUTER=true")
```

Depois: `USE_TOOL_ROUTER=true python start.py`

---

## Arquitetura V5

```
Pergunta do usuário
    │
    ├─── Alias Resolver (pré-processamento)
    │
    ├─── Layer 0.5: Produto Detection (códigos fabricante, similares)
    │
    └─── Tool Router
         ├── Layer 1: Scoring (<5ms, keywords)
         │   └── Score alto? → ToolCall direto
         │
         ├── Layer 2: Function Calling (~300ms, Groq)
         │   └── LLM recebe 11 tools → chama 1 com params tipados
         │
         └── Layer 3: Fallback (entidades + heurística)
    │
    ▼
ToolCall(name="consultar_vendas", params={marca:"MANN", periodo:"mes"})
    │
    ▼
Dispatch → _handle_vendas(params)
    │
    ▼
Session Memory atualizada
```

## Diferenças Chave vs V4

| Aspecto | V4 | V5 |
|---------|----|----|
| Classificação | Prompt 23k chars → JSON | Function Calling nativo |
| Parâmetros | Regex + LLM separados | FC extrai + regex enriquece |
| Dispatch | if/elif 370 linhas | Dict lookup ~80 linhas |
| Sessão | ConversationContext básico | SessionMemory com histórico |
| Groq API | Só text completion | tools + tool_choice |
| Reversível | Não | Sim (flag env) |

## Próximos Passos
1. Ativar com Opção C (flag env) em ambiente de teste
2. Comparar latência e acurácia vs V4
3. Adicionar domínios: `financeiro.py`, `comissao.py` como novas tools
4. Extrair handlers para `src/handlers/` (redução adicional)
