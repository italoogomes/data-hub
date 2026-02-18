# PROGRESSO_ATUAL.md

> Ultima atualizacao: 2026-02-18 (sessao 33)
> Historico de sessoes: Ver `PROGRESSO_HISTORICO.md`

---

## STATUS ATUAL

**Smart Agent v3 com Groq 3 Pools + Context-Aware Classifier + Extra Columns + Toggle Frontend + Training Scheduler**

- **Web:** http://localhost:8000 (`python start.py`)
- **Login:** Autenticacao via Sankhya MobileLoginSP.login
- **Smart Agent:** `src/llm/smart_agent.py` (~3900+ linhas)
- **Groq 3 Pools:** classify (3 keys), narrate (3 keys), train (1 key) com round-robin e cooldown
- **LLM Classifier:** Groq API via pool_classify (~0.5s) + Ollama (fallback, ~10s)
- **Context-Aware:** `_build_context_hint()` injeta contexto da conversa no classificador LLM
- **Narrator:** Groq API via pool_narrate (migrado de Ollama)
- **Extra Columns:** Groq detecta colunas extras no prompt (NUM_FABRICANTE, REFERENCIA, etc.) e injeta no SQL
- **Frontend Toggle:** Chips de colunas na mensagem, re-renderiza tabela client-side
- **Training Scheduler:** Roda de madrugada (3h), compila knowledge + auto-aprova aliases
- **SQL Sanitizado:** `_safe_sql()` em todos os pontos de interpolacao
- **Scoring:** Keywords manuais + compiladas (Knowledge Compiler), resolve 90%+ em 0ms
- **Filtros:** FILTER_RULES manuais + compiladas + Groq interpretacao semantica
- **Contexto:** Conversa por usuario com heranca de parametros + extra_columns + context_hint para LLM
- **Produto:** Busca por codigo fabricante + similares + visao 360 + aplicacao/veiculo
- **Apelidos:** AliasResolver com auto-learning (feedback + sequencia)

**Arquivos principais:**
- `src/llm/smart_agent.py` - Smart Agent v3 (GroqKeyPool + 3 pools + context_hint + extra_columns + _safe_sql + daily_training)
- `src/llm/knowledge_compiler.py` - Knowledge Compiler (auto-gera inteligencia)
- `src/llm/train.py` - CLI para treinamento manual
- `src/llm/alias_resolver.py` - Sistema de apelidos de produto
- `src/llm/knowledge_base.py` - Knowledge Base com TF-IDF
- `src/llm/query_executor.py` - Executor seguro de SQL
- `src/llm/query_logger.py` - Logger de queries
- `src/api/app.py` - API FastAPI (auth + pools admin + train endpoint + table_data)
- `src/api/static/index.html` - Frontend (login + chat + column toggles)
- `tests/test_smart_agent.py` - Testes pytest basicos
- `.env` - Config (Sankhya, Groq pools, Ollama, Training)

---

## SESSAO 33 - Context-Aware LLM Classifier (2026-02-18)

### Problema

O classificador Groq recebia perguntas de follow-up **sem contexto da conversa anterior**, causando interpretacoes erradas:

**Exemplo:**
1. Usuario: "pendencias da donaldson" → 116 itens (41 ATRASADO, 55 NO PRAZO, 20 PROXIMO)
2. Usuario: "me passa os 41 atrasados"
3. **ANTES:** Groq interpretava como `DIAS_ABERTO > 41` (numero literal)
4. **AGORA:** Groq interpreta como `STATUS_ENTREGA = ATRASADO` (referencia ao contexto)

### O que foi feito (5 passos):

#### Passo 1: `_build_context_hint(ctx)` (linha ~555)
- Funcao que monta resumo compacto (~80-120 tokens) do contexto da conversa
- Inclui: intent anterior, filtros ativos (marca/empresa/etc), contagem por STATUS_ENTREGA, descricao, pergunta anterior
- Retorna string vazia se nao ha contexto relevante (turn_count == 0)

#### Passo 2: Assinaturas atualizadas
- `groq_classify(question, context_hint="")` (linha ~596)
- `ollama_classify(question, context_hint="")` (linha ~644)
- `llm_classify(question, context_hint="")` (linha ~710)
- Todas as 3 funcoes appendam o context_hint ao final do prompt quando presente

#### Passo 3: Injecao no prompt
```python
if context_hint:
    prompt += f"\n\n# CONTEXTO DA CONVERSA ANTERIOR (use para interpretar referencias):\n{context_hint}"
```
- Adicionado em `groq_classify()` e `ollama_classify()`
- Context hint fica **fora** do template, appendado dinamicamente

#### Passo 4: Propagacao no `_ask_core`
```python
ctx = self._get_context(user_id)
context_hint = _build_context_hint(ctx)
```
- Layer 1+ (scoring resolveu mas query complexa): `groq_classify(question, context_hint)`
- Layer 2 (scoring nao resolveu): `llm_classify(question, context_hint)`

#### Passo 5: Instrucoes + exemplos no LLM_CLASSIFIER_PROMPT
- **Secao "CONTEXTO DE CONVERSA"** (linha ~429) com regras explicitas:
  - Numeros que coincidem com contagens anteriores = filtro de STATUS, nao campo numerico
  - "desses", "e os atrasados?", "os mais caros" = referencia aos dados anteriores
- **4 exemplos com contexto** (linha ~532):
  1. "me passa os 41 atrasados" (com contexto 41 ATRASADO) → STATUS_ENTREGA=ATRASADO
  2. "e os atrasados?" (com contexto NAKATA+RIBEIR) → herda marca+empresa
  3. "qual o pedido mais caro?" (com contexto MANN) → VLR_PENDENTE_DESC + top 1
  4. "quais estao sem previsao?" (com contexto SABO) → PREVISAO_ENTREGA vazio

### Cenarios corrigidos:

| Follow-up | Antes | Agora |
|-----------|-------|-------|
| "me passa os 41 atrasados" | DIAS_ABERTO > 41 | STATUS_ENTREGA = ATRASADO |
| "e os atrasados?" | Perdia marca/empresa | Herda filtros do contexto |
| "qual o mais caro?" | Sem referencia | VLR_PENDENTE_DESC dos dados anteriores |
| "quais sem previsao?" | Sem referencia | PREVISAO_ENTREGA vazio dos anteriores |

### Impacto:
- ~80-120 tokens extras por chamada (~12% do prompt)
- Sem impacto na primeira pergunta (context_hint vazio)
- Melhora significativa em follow-ups que referenciam dados anteriores

### Pendente:
- [ ] Testar no servidor real com os 6 cenarios especificados
- [ ] Implementar `_handle_financeiro()` (intent detectado pelo compiler)
- [ ] Dashboard HTML
- [ ] Tela admin de apelidos no frontend

---

> Sessoes anteriores (1-32): Ver `PROGRESSO_HISTORICO.md`
