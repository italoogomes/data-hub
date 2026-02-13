# PROGRESSO_ATUAL.md

> Ultima atualizacao: 2026-02-12 (sessao 29)
> Historico de sessoes: Ver `PROGRESSO_HISTORICO.md`

---

## STATUS ATUAL

**Smart Agent v3 com Groq + Scoring + Produto 360 + Aplicacao + Apelidos**

- **Web:** http://localhost:8000 (`python start.py`)
- **Login:** Autenticacao via Sankhya MobileLoginSP.login
- **Smart Agent:** `src/llm/smart_agent.py` (~3200 linhas)
- **LLM Classifier:** Groq API (principal, ~0.5s) + Ollama (fallback, ~10s)
- **Scoring:** Keywords com pesos, resolve 80-90% em 0ms
- **Filtros:** Pattern-matching (FILTER_RULES) + Groq interpretacao semantica
- **Contexto:** Conversa por usuario com heranca de parametros
- **Knowledge Base:** 48 documentos, TF-IDF, RAG
- **Modelo Ollama:** qwen3:4b (fallback CPU-only)
- **Modelo Groq:** llama-3.1-8b-instant (free tier, 14.4K req/dia)
- **Produto:** Busca por codigo fabricante + similares + visao 360 + aplicacao/veiculo
- **Apelidos:** AliasResolver com auto-learning (feedback + sequencia)

**Arquivos principais:**
- `src/llm/smart_agent.py` - Smart Agent v3 (scoring + Groq + filtros + contexto + produto + aplicacao)
- `src/llm/alias_resolver.py` - **NOVO** - Sistema de apelidos de produto
- `src/llm/knowledge_base.py` - Knowledge Base com TF-IDF
- `src/llm/query_executor.py` - Executor seguro de SQL
- `src/llm/query_logger.py` - Logger de queries (+ get_entry)
- `src/api/app.py` - API FastAPI (auth Sankhya + sessoes + aliases admin)
- `src/api/static/index.html` - Frontend (login + chat)
- `knowledge/glossario/apelidos_produto.json` - **NOVO** - Base de apelidos
- `.env` - Config (Sankhya, Groq, Ollama)

---

## SESSAO 29 - Aplicacao/Veiculo + Sistema de Apelidos (2026-02-12)

### O que foi feito:

#### ENTREGA A: Descricao + Aplicacao em todas as respostas

1. **CARACTERISTICAS (aplicacao) em 8 queries SQL**
   - `resolve_manufacturer_code()`: +APLICACAO
   - `buscar_similares()` (prod query): +APLICACAO
   - `buscar_similares_por_codigo()`: +APLICACAO
   - `sql_pendencia_compras` (detail): +APLICACAO
   - `_handle_estoque` (codprod): +APLICACAO
   - `_handle_estoque` (nome): +APLICACAO
   - `_handle_produto_360` (info): +APLICACAO, +COMPLEMENTO, +NUM_ORIGINAL, +REF_FORNECEDOR
   - `_handle_produto_360` (find by name): +APLICACAO
   - SKIP: _handle_estoque critico (GROUP BY), _handle_vendas (nao mostra produtos)

2. **5 format functions atualizadas**
   - `format_produto_360()`: Mostra Aplicacao, Complemento, Nro. Original, Ref. Fornecedor
   - `format_busca_fabricante()`: Mostra Aplicacao (1 produto = tabela vertical, N = coluna)
   - `format_similares()`: Mostra Aplicacao do produto principal
   - `format_estoque_response()`: Mostra Aplicacao para produto individual
   - `format_pendencia_response()`: Coluna Aplicacao na view "itens" (se dados tiverem)

3. **Helper `_trunc(text, max_len)`**: Trunca texto para tabelas markdown

4. **Busca por aplicacao/veiculo (A2)**
   - `extract_entities()`: Novo parametro `aplicacao` com 3 patterns:
     - "serve/aplica/compativel no/para [VEICULO]"
     - "pecas/filtros do/para [VEICULO]"
     - "motor/veiculo/caminhao [MODELO]"
   - `_build_where_extra()`: Filtro `UPPER(PRO.CARACTERISTICAS) LIKE UPPER('%{app}%')`
   - `detect_product_query()`: Novo tipo "busca_aplicacao"
   - `_handle_busca_aplicacao()`: Query TGFPRO por CARACTERISTICAS com filtro marca
   - Routing: Layer 0.5, Layer 2 (LLM classify), _dispatch
   - Scoring: +aplicacao, +aplica, +serve, +compativel, +veiculo, +motor, +caminhao, +scania, +mercedes, +volvo, etc
   - Groq prompt: Campo `aplicacao` + 3 exemplos novos

#### ENTREGA B: Sistema de Apelidos de Produto

5. **AliasResolver (`src/llm/alias_resolver.py`) - NOVO**
   - Classe completa: load, save, normalize, resolve, add_alias, remove_alias
   - suggest_alias: registra sugestoes para review
   - detect_alias_from_feedback (B3): feedback negativo reforca sugestoes
   - detect_alias_from_sequence (B4): detecta quando usuario falha com termo A e acerta com B
   - auto_promote_suggestions (B5): promove automaticamente sugestoes com count >= 5
   - approve_suggestion, reject_suggestion: gerenciamento manual
   - stats(): estatisticas do sistema

6. **Base de apelidos (`knowledge/glossario/apelidos_produto.json`) - NOVO**
   - Estrutura: _meta + aliases (dict) + suggestions (list)
   - Seed: "boneca" -> "PINO DO CABECALHO" (manual, conf=0.90)

7. **Integracao no SmartAgent**
   - Layer 0.4 (ALIAS RESOLVER): antes do Layer 0.5 (produto)
   - Resolve apelido -> codprod ou nome_real
   - Prefixo na resposta: "*'boneca' = PINO DO CABECALHO*"
   - B2: Registra termos sem match como sugestao (suggest_alias)
   - B4: Detecta sequencia falha->sucesso entre queries do mesmo usuario

8. **Endpoints admin (app.py)**
   - `GET /api/aliases` - Lista aliases + sugestoes + stats (admin only)
   - `POST /api/aliases` - Gerencia: add, approve, reject, remove (admin only)
   - Feedback B3: integrado no `POST /api/feedback`

9. **QueryLogger melhorado**
   - `get_entry(message_id)`: busca entrada por ID (para feedback B3)

### Funcoes/classes novas:
- `_trunc(text, max_len)` - trunca texto para tabelas
- `_handle_busca_aplicacao()` - handler de busca por veiculo/aplicacao
- `AliasResolver` - classe completa em `src/llm/alias_resolver.py`
- `AliasRequest` - Pydantic model em app.py
- `get_entry()` - em query_logger.py

### Testes sugeridos:
- [ ] "estoque do produto 231943" - deve mostrar APLICACAO
- [ ] "tudo sobre o produto 133346" - deve mostrar APLICACAO + refs completas
- [ ] "pecas para scania r450" - deve listar produtos por CARACTERISTICAS
- [ ] "qual filtro serve no mercedes actros" - deve buscar CARACTERISTICAS
- [ ] "filtros mann para motor dc13" - deve buscar CARACTERISTICAS + filtro marca
- [ ] "boneca em estoque" - deve resolver para PINO DO CABECALHO (alias)
- [ ] "HU711/51" - deve mostrar APLICACAO na busca fabricante
- [ ] GET /api/aliases - deve retornar aliases + sugestoes + stats

### Pendente:
- [ ] Testar no servidor real com perguntas reais
- [ ] Narrator com Groq nos handlers novos
- [ ] Mais intents: financeiro, fiscal
- [ ] Dashboard HTML
- [ ] Tela admin de apelidos no frontend

---

## SESSAO 28 - Inteligencia de Produto: Visao 360, Codigo Fabricante, Similares (2026-02-12)

### O que foi feito:

1. **Busca por codigo fabricante (`_handle_busca_fabricante`)**
   - Funcao `resolve_manufacturer_code()` busca em TGFPRO: REFERENCIA, AD_NUMFABRICANTE, AD_NUMFABRICANTE2, AD_NUMORIGINAL, REFFORN
   - Normaliza codigos: remove espacos, tracos, barras antes de comparar (`_sanitize_code`)
   - Funciona com: "HU711/51", "WK 950/21", "F026407032", "078115561J"
   - Identifica qual campo matchou (campo_match)

2. **Busca de similares/cross-reference (`_handle_similares`)**
   - Funcao `buscar_similares()` consulta AD_TGFPROAUXMMA (1.1M codigos auxiliares)
   - Funcao `buscar_similares_por_codigo()` encontra produto pelo texto auxiliar
   - Agrupamento por marca na formatacao
   - Funciona com: "similares do produto 133346", "similares do HU711/51"

3. **Visao 360 de produto (`_handle_produto_360`)**
   - Combina: dados do produto + estoque + pendencias de compra + vendas (3 meses)
   - Consultas em paralelo com `asyncio.gather`
   - Resolve CODPROD por: codigo numerico, nome, ou codigo fabricante
   - Se multiplos resultados, mostra lista para usuario escolher
   - Funciona com: "tudo sobre o produto 133346", "situacao do produto 145678"

4. **Deteccao e roteamento (`detect_product_query`)**
   - Layer 0.5 em `_ask_core`: roda ANTES do scoring
   - Classifica: "busca_fabricante" | "similares" | "produto_360" | "busca_aplicacao" | None
   - Integrado em: _ask_core (Layer 0.5), _dispatch, Layer 2 (LLM classify)

5-8. Ver sessao 28 no PROGRESSO_HISTORICO.md

---

## O QUE ESTA PRONTO

- [x] Smart Agent v3 (scoring + LLM + knowledge base)
- [x] Groq como classificador principal
- [x] Ollama como fallback local
- [x] Pattern matching com FILTER_RULES
- [x] Interpretacao semantica via LLM (filtros, sort, top)
- [x] Pos-processamento de confusoes da LLM
- [x] Sort de datas (dd/mm/yyyy)
- [x] Entity extraction robusto (+ codigo fabricante + aplicacao)
- [x] Conversation context com heranca
- [x] Follow-up detection + filter followup
- [x] Excel export (via chat)
- [x] Knowledge Base com TF-IDF (48 docs)
- [x] Login Sankhya + sessoes
- [x] RBAC (admin vs usuario)
- [x] Frontend com chat + tabelas + KPIs
- [x] **Busca por codigo fabricante**
- [x] **Similares/cross-reference (AD_TGFPROAUXMMA)**
- [x] **Visao 360 de produto**
- [x] **Roteamento inteligente de queries de produto**
- [x] **APLICACAO/veiculo em todas as respostas de produto**
- [x] **Busca por aplicacao/veiculo (CARACTERISTICAS)**
- [x] **Sistema de apelidos com auto-learning**
- [x] **Endpoints admin de apelidos**
