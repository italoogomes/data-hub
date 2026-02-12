# PROGRESSO_ATUAL.md

> Ultima atualizacao: 2026-02-12 (sessao 27)
> Historico de sessoes: Ver `PROGRESSO_HISTORICO.md`

---

## STATUS ATUAL

**Smart Agent v3 com Groq + Scoring + Conversation Context**

- **Web:** http://localhost:8000 (`python start.py`)
- **Login:** Autenticacao via Sankhya MobileLoginSP.login
- **Smart Agent:** `src/llm/smart_agent.py` (~2200 linhas)
- **LLM Classifier:** Groq API (principal, ~0.5s) + Ollama (fallback, ~10s)
- **Scoring:** Keywords com pesos, resolve 80-90% em 0ms
- **Filtros:** Pattern-matching (FILTER_RULES) + Groq interpretacao semantica
- **Contexto:** Conversa por usuario com heranca de parametros
- **Knowledge Base:** 48 documentos, TF-IDF, RAG
- **Modelo Ollama:** qwen3:4b (fallback CPU-only)
- **Modelo Groq:** llama-3.1-8b-instant (free tier, 14.4K req/dia)

**Arquivos principais:**
- `src/llm/smart_agent.py` - ★ Smart Agent v3 (scoring + Groq + filtros + contexto)
- `src/llm/knowledge_base.py` - Knowledge Base com TF-IDF
- `src/llm/query_executor.py` - Executor seguro de SQL
- `src/api/app.py` - API FastAPI (auth Sankhya + sessoes)
- `src/api/static/index.html` - Frontend (login + chat)
- `.env` - Config (Sankhya, Groq, Ollama)

---

## SESSAO 27 - Smart Agent: Groq Integration + Filter Intelligence (2026-02-12)

### O que foi feito:

1. **Groq API como classificador principal**
   - Substitui Ollama como Layer 2 (era 30s, agora <1s)
   - Free tier: 14,400 req/dia, 500K tokens/dia
   - Fallback automatico: Groq → Ollama → "nao entendi"
   - Funcoes: `groq_classify()`, `ollama_classify()`, `llm_classify()`

2. **Prompt inteligente com interpretacao semantica**
   - Prompt nao so classifica intent, mas interpreta filtros/sort/top
   - Campos estruturados: filtro={campo, operador, valor}, ordenar, top
   - Disambiguacao explicita: DT_PEDIDO vs PREVISAO_ENTREGA
   - Exemplos diversificados no prompt

3. **Layer 1+ (Groq em queries complexas)**
   - Funcao `_is_complex_query()` detecta queries que precisam de interpretacao LLM
   - Mesmo quando scoring resolve o intent, Groq interpreta filtros
   - Ex: score=10 (pendencia_compras ok) + "maior data de entrega" = chama Groq

4. **FILTER_RULES expandido**
   - Novos patterns: "maior/menor data de entrega", "previsao mais distante/proxima"
   - Resolve "data de entrega" → PREVISAO_ENTREGA_DESC sem precisar de LLM

5. **Pos-processamento de output da LLM**
   - `_llm_to_filters()` corrige confusoes: DT_PEDIDO → PREVISAO_ENTREGA quando query fala "entrega"
   - Novos operadores: _fn_maior, _fn_menor, _fn_contem

6. **Sort de datas corrigido**
   - `apply_filters()` agora converte dd/mm/yyyy → yyyy-mm-dd para sort correto

7. **View pedidos + Top 1**
   - "qual pedido..." com top=1 agora mostra o PEDIDO completo com todos itens
   - Antes mostrava apenas 1 item (1 linha de produto)

8. **Entity extraction fix**
   - Noise words expandidas: ENTREGA, PREVISAO, DATA, ESTA, ESTAO, etc
   - Regex DA/DE/DO com word boundary e stop em verbos/preposicoes
   - "data DE ENTREGA DA Donaldson" → marca=DONALDSON (nao ENTREGA)

9. **Conversation Context com filtros**
   - Follow-up detection + filter application em dados anteriores
   - Heranca de parametros (marca, fornecedor, etc)
   - 0 resultados = mensagem informativa (nao mostra tudo silenciosamente)

10. **CLAUDE.md atualizado v4.0**
    - Arquitetura Smart Agent v3 documentada
    - Bugs conhecidos e armadilhas
    - Configuracao Groq detalhada

### Bugs encontrados e corrigidos:
- Entity extraction pegava "ENTREGA DA DONALSON" como marca
- Groq confundia DT_PEDIDO com PREVISAO_ENTREGA
- Top 1 mostrava item em vez de pedido
- Sort de datas nao funcionava (06/01 aparecia antes de 02/03)
- Pattern matching nao tinha regras pra "data de entrega"

### Pendente:
- [ ] Testar "qual pedido da sabo tem a maior data de entrega" (correcao aplicada)
- [ ] Testar Groq no servidor real (proxy pode bloquear api.groq.com)
- [ ] Narrator com Groq (atualmente desabilitado)
- [ ] Mais intents: financeiro, fiscal
- [ ] Dashboard HTML

---

## O QUE ESTA PRONTO

- [x] Smart Agent v3 (scoring + LLM + knowledge base)
- [x] Groq como classificador principal
- [x] Ollama como fallback local
- [x] Pattern matching com FILTER_RULES
- [x] Interpretacao semantica via LLM (filtros, sort, top)
- [x] Pos-processamento de confusoes da LLM
- [x] Sort de datas (dd/mm/yyyy)
- [x] Entity extraction robusto
- [x] Conversation context com heranca
- [x] Follow-up detection + filter followup
- [x] Excel export (via chat)
- [x] Knowledge Base com TF-IDF (48 docs)
- [x] Login Sankhya + sessoes
- [x] RBAC (admin vs usuario)
- [x] Frontend com chat + tabelas + KPIs
