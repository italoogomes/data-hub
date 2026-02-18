# PROGRESSO_ATUAL.md

> Ultima atualizacao: 2026-02-18 (sessao 35f)
> Historico de sessoes: Ver `PROGRESSO_HISTORICO.md`

---

## STATUS ATUAL

**Smart Agent v3 com Groq 3 Pools + Context-Aware Classifier + Rastreio Pedido + Vendas Expandido + Extra Columns + Toggle Frontend + Training Scheduler**

- **Web:** http://localhost:8000 (`python start.py`)
- **Login:** Autenticacao via Sankhya MobileLoginSP.login
- **Smart Agent:** `src/llm/smart_agent.py` (~4700 linhas)
- **Groq 3 Pools:** classify (3 keys), narrate (3 keys), train (1 key) com round-robin e cooldown
- **LLM Classifier:** Groq 70b (Layer 2, forte) → Groq 8b (Layer 1+, filtros) → Ollama (fallback)
- **Context-Aware:** `_build_context_hint()` injeta contexto da conversa no classificador LLM
- **Rastreio Pedido:** `_handle_rastreio_pedido()` - 3 etapas (status + itens + compra vinculada)
- **Vendas Expandido:** `_handle_vendas()` com margem, comissao, vendas por marca, detail query (500 rows)
- **Narrator:** Groq API via pool_narrate (migrado de Ollama)
- **Extra Columns:** Groq detecta colunas extras no prompt (NUM_FABRICANTE, REFERENCIA, etc.) e injeta no SQL
- **Frontend Toggle:** Chips de colunas na mensagem, re-renderiza tabela client-side
- **Training Scheduler:** Roda de madrugada (3h), compila knowledge + auto-aprova aliases
- **SQL Sanitizado:** `_safe_sql()` em todos os pontos de interpolacao
- **Scoring:** Keywords manuais + compiladas (Knowledge Compiler, cap=3), resolve 90%+ em 0ms
- **Filtros:** FILTER_RULES manuais + compiladas + Groq interpretacao semantica
- **Contexto:** Conversa por usuario com heranca de parametros (so em follow-ups) + limpeza ao mudar intent
- **Produto:** Busca por codigo fabricante + similares + visao 360 + aplicacao/veiculo
- **Busca Elastic:** Fix: ignora marca de regex quando LLM fornece texto_busca
- **Apelidos:** AliasResolver com auto-learning (feedback + sequencia)

**Intents ativos:** `pendencia_compras`, `estoque`, `vendas`, `rastreio_pedido`, `busca_produto`, `busca_cliente`, `busca_fornecedor`, `conhecimento`, `saudacao`, `ajuda`

**Arquivos principais:**
- `src/llm/smart_agent.py` - Smart Agent v3 (~4700 linhas)
- `src/llm/knowledge_compiler.py` - Knowledge Compiler (auto-gera inteligencia)
- `src/llm/train.py` - CLI para treinamento manual
- `src/llm/alias_resolver.py` - Sistema de apelidos de produto
- `src/llm/knowledge_base.py` - Knowledge Base com TF-IDF
- `src/llm/query_executor.py` - Executor seguro de SQL
- `src/llm/query_logger.py` - Logger de queries
- `src/api/app.py` - API FastAPI (auth + pools admin + train endpoint + table_data)
- `src/api/static/index.html` - Frontend (login + chat + column toggles)
- `tests/test_smart_agent.py` - Testes pytest basicos
- `PROMPT_MASTER.md` - Documentacao completa da arquitetura v5.0
- `.env` - Config (Sankhya, Groq pools, Ollama, Training)

---

## SESSAO 35f - Fix Definitivo: Heranca de Contexto + Compiled Scores (2026-02-18)

### Contexto

Apos 4 tentativas de fix (35b, 35c, 35d, 35e), o bot continuava retornando "Nao encontrei informacoes de estoque para POLIFILTRO" para queries completamente diferentes. Investigacao profunda revelou **4 causas raiz** que se combinavam:

### Diagnostico (4 causas raiz)

1. **Handlers faziam merge_params SEM verificar is_followup** — `_handle_estoque` (ln 3770), `_handle_pendencia_compras` (ln 3520), `_handle_vendas` (ln 3825) todos chamavam `ctx.merge_params()` quando params atual estava esparso, INDEPENDENTE de ser follow-up. Resultado: qualquer query sem marca/fornecedor herdava params antigos.

2. **ctx.update NUNCA limpava params ao mudar de intent** — Se o usuario perguntava "busca_produto" (que salvava marca=POLIFILTRO dos resultados) e depois "estoque" (sem marca), o ctx.params ACUMULAVA a marca antiga. O intent mudava, mas os params persistiam.

3. **compiled_knowledge.json poluia estoque** — O Knowledge Compiler atribuiu keywords como "compra"(6), "pedidos"(5), "marca"(5) ao intent "estoque" (porque os arquivos de glossario mencionam estoque no contexto). Isso fazia estoque pontuar 8+ para queries sobre compras.

4. **"produtos" (plural) ausente de busca_produto** — INTENT_SCORES so tinha "produto"(3) singular. "Qual o codigo dos **produtos** que contem filtro de ar" pontuava busca_produto=7 (abaixo do threshold 8), caindo no LLM que podia misclassificar como estoque.

### 7 Fixes implementados

#### Fix 1: Remover merge_params dos handlers
```python
# _handle_estoque, _handle_pendencia_compras, _handle_vendas:
# REMOVIDO:
if ctx and not (...):
    params = ctx.merge_params(params)
# O merge agora so acontece em _ask_core com guarda is_followup (ln 3083)
```
**Impacto:** Handlers recebem SOMENTE os params extraidos da pergunta atual. Merge so acontece em _ask_core quando `is_followup=True` e `not has_entity`.

#### Fix 2: Limpar params em ctx.update ao mudar de intent
```python
def update(self, intent, params, result, question, view_mode="pedidos"):
    if intent != self.intent:
        self._extra_columns = []
        self.params = {}  # NOVO: limpa params ao mudar de intent
    self.intent = intent
    for k, v in params.items():
        if v:
            self.params[k] = v
```
**Impacto:** Ao mudar de busca_produto para estoque (ou qualquer outro intent), os params antigos (marca, fornecedor) sao limpos. Dentro do mesmo intent, params continuam acumulando (ex: "vendas de hoje" → "vendas da Mann" herda periodo mas atualiza marca).

#### Fix 3: Adicionar keywords faltantes a busca_produto
```python
"busca_produto": {
    ...
    "produtos": 3,      # NOVO (plural)
    "contem": 4,         # NOVO ("que contem X na descricao")
    "descricao": 3,      # NOVO ("filtro de ar na descricao")
    "cadastradas": 4,    # NOVO (plural)
    ...
}
```
**Impacto:** "Qual o codigo dos produtos que contem filtro de ar na descricao" agora pontua: codigo(4)+produtos(3)+contem(4)+filtro(3)+descricao(3) = **17** >= 8. Resolve em Layer 1 sem LLM.

#### Fix 4: Limitar peso de compiled scores (cap=3)
```python
# score_intent(): compiled keywords agora contribuem no maximo 3 pontos cada
scores[intent_id] += min(keywords[token], 3)  # era: keywords[token]
```
**Impacto:** "compra"(6) compilado sob estoque agora contribui apenas 3. Estoque nao atinge threshold com keywords de compra. Manual continua dominante.

#### Fix 5: Debug logs detalhados
```python
# Em _ask_core, apos score:
print(f"[SMART] ---- Nova pergunta: '{question[:80]}' ----")
print(f"[SMART] Tokens: {tokens}")
print(f"[SMART] Scores(>=3): {_sig_scores} | best={best_intent}({best_score})")
print(f"[SMART] Contexto anterior: intent={ctx.intent} | params={ctx.params}")
print(f"[SMART] Entities extraidas: {_entity_params} | followup={is_followup}")
```
**Impacto:** Console mostra o caminho exato de cada query para debugging.

#### Fix 6: Suporte a codigo_fabricante em sql_pendencia_compras
```python
# Em _build_where_extra:
if params.get("codigo_fabricante") and not params.get("codprod"):
    w += f" AND UPPER(NVL(PRO.AD_NUMFABRICANTE,'')) LIKE UPPER('%{_safe_sql(params['codigo_fabricante'])}%')"
```
**Impacto:** "S2581 tem pedido de compra?" agora filtra por AD_NUMFABRICANTE no SQL, em vez de retornar TODAS as pendencias.

#### Fix 7: Exemplos LLM + regex de limpeza
- **LLM prompt:** +2 exemplos para queries que falhavam
- **Regex limpeza:** Adicionado "contem", "contendo", "conter", "descricao", "nome" para limpeza em busca_produto

### Resultado esperado

**Query 1:** "Qual o codigo dos produtos que contem filtro de ar na descricao?"
- Score: busca_produto=17 (Layer 1) → _dispatch → _handle_busca_produto
- Regex limpa → "filtro ar" → Elastic search → resultados

**Query 2:** "esse item S2581 tem pedido de compra?"
- Score: pendencia_compras=12 (Layer 1) → _dispatch → _handle_pendencia_compras
- params: {codigo_fabricante: "S2581"} → SQL filtra por AD_NUMFABRICANTE → resultados

**Context isolation:** Mesmo que query 1 rode antes de query 2:
- Query 1 salva ctx.intent="busca_produto", ctx.params={...}
- Query 2 muda intent para "pendencia_compras" → ctx.params e LIMPO → sem heranca

### Pendente:
- [ ] Testar no servidor real (reiniciar com `python start.py`)
- [ ] Implementar `_handle_financeiro()` (queries ja documentadas)
- [ ] Implementar devolucoes e venda liquida no handler vendas
- [ ] Dashboard HTML
- [ ] Tela admin de apelidos no frontend

---

## SESSAO 35 a 35e - Resumo (2026-02-18)

### Sessao 35: Fix Bug Busca Elastic + Handler Vendas Expandido
- Fix: ignorar marca quando texto_busca existe
- Vendas: reescrita completa com margem, comissao, detail query, por marca

### Sessao 35b: Fix Classificacao Busca por Nome de Produto
- Threshold busca_produto: 10 → 8
- +20 keywords, +6 exemplos LLM, +18 noise words
- Layer 1.5 guard para busca_score

### Sessao 35c: Upgrade Classificador Groq 70b
- GROQ_MODEL_CLASSIFY = llama-3.3-70b-versatile
- Cadeia: 70b → 8b → Ollama
- Layer 1+ usa 8b (filtros), Layer 2 usa 70b (classificacao)

### Sessao 35d: Fix Context Merge (has_entity + merge_params)
- has_entity ampliado com codprod/codigo_fabricante/produto_nome
- merge_params param_keys expandido

### Sessao 35e: Fix Layer 0.5 (scoring guard)
- detect_product_query nao intercepta quando scoring detectou intent forte

---

> Sessoes anteriores (1-34): Ver `PROGRESSO_HISTORICO.md`
