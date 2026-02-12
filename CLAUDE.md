# CLAUDE.md - MMarra Data Hub

> Repositório de dados inteligente. Leia TUDO antes de agir.

---

## REGRA ZERO

**NUNCA faça nada pela metade.** Termina o que começou. Documenta o que descobriu.

---

## ANTES DE QUALQUER TAREFA

1. Leia `PROGRESSO_ATUAL.md` para entender onde paramos (estado atual + sessao mais recente)
2. Consulte `PROGRESSO_HISTORICO.md` se precisar de contexto de sessoes anteriores (1-25)
3. Pergunte o que o usuário quer fazer
4. Confirme ANTES de executar

### Ao finalizar uma sessao:
- Atualize `PROGRESSO_ATUAL.md` com o que foi feito
- Mova a sessao anterior para `PROGRESSO_HISTORICO.md` (manter apenas a mais recente no ATUAL)

---

## ESTRUTURA DO PROJETO

```
mmarra-data-hub/
├── CLAUDE.md                   ← Este arquivo
├── PROGRESSO_ATUAL.md          ← Estado atual (SEMPRE atualizar)
├── PROGRESSO_HISTORICO.md      ← Sessoes anteriores
├── .env                        ← Configuracoes (Sankhya, Groq, Ollama)
│
├── knowledge/                  ← BASE DE CONHECIMENTO
│   ├── sankhya/tabelas/        ← Schema das tabelas
│   ├── processos/              ← Fluxos de negócio
│   │   ├── compras/
│   │   ├── vendas/
│   │   ├── estoque/
│   │   ├── wms/
│   │   ├── financeiro/
│   │   └── fiscal/
│   ├── glossario/              ← Termos e conceitos
│   ├── regras/                 ← Regras de negócio
│   └── erros/                  ← Problemas conhecidos
│
├── queries/                    ← SQLs úteis
│   ├── vendas/
│   ├── compras/
│   ├── estoque/
│   ├── financeiro/
│   ├── fiscal/
│   └── wms/
│
├── src/                        ← Código fonte
│   ├── llm/                    ← Smart Agent + Knowledge Base
│   │   ├── smart_agent.py      ← ★ ARQUIVO PRINCIPAL (~2200 linhas)
│   │   ├── knowledge_base.py   ← RAG com TF-IDF
│   │   ├── query_executor.py   ← Executor seguro de SQL
│   │   ├── agent.py            ← Agente LLM legado
│   │   └── chat.py             ← Motor de chat
│   ├── api/                    ← API FastAPI
│   │   ├── app.py              ← Endpoints REST
│   │   └── static/             ← Frontend (index.html)
│   ├── mcp/                    ← MCP Server (experimental)
│   └── utils/                  ← Utilitários
│
└── start.py                    ← Script de inicialização
```

---

## SMART AGENT v3 - ARQUITETURA (src/llm/smart_agent.py)

O `smart_agent.py` é o coração do sistema. Entenda sua arquitetura:

### Fluxo de Processamento (3 camadas)

```
Pergunta do usuario
     │
     ▼
 SCORING (0ms) ─────── score alto? ──── SIM ──┐
     │                                         │
     │ score baixo                              ▼
     ▼                                   Query complexa?
 GROQ API (~0.5s) ──── resolve? ──── SIM ──── Groq interpreta filtros
     │                                    │    (sort/filter/top)
     │ falhou                             │
     ▼                                    ▼
 OLLAMA LOCAL (~10s) ── resolve? ──── Executa SQL + aplica filtros
     │                                    │
     │ falhou                             ▼
     ▼                              Formata resposta
 FALLBACK                           (tabela/card/KPIs)
 "nao entendi"
```

### Camadas em Detalhe

#### Layer 1: Scoring (linhas ~50-165)
- `INTENT_SCORES`: dicionario de palavras-chave com pesos por intent
- `INTENT_THRESHOLDS`: score minimo pra acionar cada intent
- Resolve 80-90% das perguntas em 0ms
- Intents: `pendencia_compras`, `estoque`, `vendas`, `conhecimento`, `saudacao`, `ajuda`

#### Layer 1+: Groq para Queries Complexas (linhas ~1503-1530)
- Acionado quando scoring resolve o intent MAS a query tem complexidade (filtros, ordenacao)
- Funcao `_is_complex_query()` detecta: "maior data de entrega", "acima de 50 mil", etc
- Groq retorna JSON estruturado com: intent + entidades + filtro + ordenar + top
- Pos-processamento `_llm_to_filters()` corrige confusoes comuns (ex: DT_PEDIDO vs PREVISAO_ENTREGA)

#### Layer 2: LLM Classifier (linhas ~1543-1580)
- Acionado quando scoring NAO resolve (score ambiguo)
- Cadeia: Groq (rapido, gratis) → Ollama (fallback local)
- Mesmo prompt e formato de resposta da Layer 1+

#### Layer 3: Fallback (linhas ~1583-1600)
- Se tudo falhar, tenta entidade como pendencia ou knowledge base
- Ultimo recurso: mensagem amigavel de "nao entendi"

### Componentes Criticos

#### FILTER_RULES (linhas ~1130-1175)
Regras de pattern-matching para filtros comuns. ORDEM IMPORTA - mais especificos primeiro:
```python
FILTER_RULES = [
    # "maior data de entrega" → PREVISAO_ENTREGA_DESC (NÃO DT_PEDIDO!)
    {"match": ["maior data de entrega"], "sort": "PREVISAO_ENTREGA_DESC", "top": 1},
    # "mais atrasado" → DIAS_ABERTO_DESC
    {"match": ["mais atrasado"], "sort": "DIAS_ABERTO_DESC", "top": 1},
    # "sem previsao de entrega" → campo PREVISAO_ENTREGA vazio
    {"match": ["sem previsao de entrega"], "filter_fn": "empty", "filter_field": "PREVISAO_ENTREGA"},
    # "atrasado" → STATUS_ENTREGA = ATRASADO
    {"match": ["atrasado"], "filter": {"STATUS_ENTREGA": "ATRASADO"}},
]
```

#### Entity Extraction (linhas ~640-740)
Extrai marca, fornecedor, empresa, comprador da pergunta:
- Regex "DA/DE/DO" + lista de noise words (ENTREGA, PREVISAO, DATA, etc)
- Matching com entidades do banco (known_marcas, known_empresas)
- CUIDADO: "data DE ENTREGA DA donaldson" → regex pode pegar "ENTREGA" como marca

#### Conversation Context (linhas ~1284-1370)
Estado por usuario: intent anterior, parametros, dados retornados.
- Follow-up detection: "desses", "e os atrasados?", "agora mostra..."
- Heranca de parametros: "pedidos da Mann" → "e os atrasados?" herda marca=MANN

#### apply_filters (linhas ~1255-1350)
Aplica filtros, sort e top sobre dados ja retornados:
- Filtros: campo=valor, _fn_empty, _fn_maior, _fn_menor, _fn_contem
- Sort: suporta numeros E datas (dd/mm/yyyy → yyyy-mm-dd pra sort)
- Top N: limita resultados
- View pedidos: top=1 agrupa por PEDIDO e mostra todos itens do pedido

### Campos Importantes (pendencia_compras)

| Campo | Significado | Cuidado |
|-------|-------------|---------|
| DT_PEDIDO | Data em que compramos | "quando pediu", "data do pedido" |
| PREVISAO_ENTREGA | Data prevista de chegada | "data de entrega", "previsao", "quando chega" |
| DIAS_ABERTO | Dias em aberto sem receber | "mais atrasado", "mais antigo" |
| STATUS_ENTREGA | ATRASADO/NO PRAZO/PROXIMO/SEM PREVISAO | |
| VLR_PENDENTE | Valor em R$ do que falta | "mais caro", "maior valor" |
| CONFIRMADO | S/N - fornecedor confirmou? | |

**⚠️ CONFUSAO MAIS COMUM:** "data de entrega" = PREVISAO_ENTREGA, NÃO DT_PEDIDO!

### LLM Classifier Prompt (linhas ~172-255)

O prompt enviado ao Groq/Ollama com:
- Intents possiveis + descricao
- Campos disponiveis com descricao detalhada
- Disambiguacao explicita (DT_PEDIDO vs PREVISAO_ENTREGA)
- Exemplos de input/output JSON
- Filtros estruturados: {campo, operador, valor}

---

## CONFIGURACAO (.env)

```env
# Sankhya API
SANKHYA_CLIENT_ID=...
SANKHYA_CLIENT_SECRET=...
SANKHYA_X_TOKEN=...

# Azure Data Lake
AZURE_STORAGE_ACCOUNT=mmarradatalake
AZURE_STORAGE_KEY=...
AZURE_CONTAINER=datahub

# LLM (Ollama - fallback local)
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:4b
OLLAMA_URL=http://localhost:11434

# LLM Classifier (Groq - principal, rapido e gratis)
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.1-8b-instant   # 14,400 req/dia, 500K tokens/dia (gratis)
GROQ_TIMEOUT=10

# Smart Agent
USE_LLM_CLASSIFIER=true            # Habilitar Layer 2 (Groq/Ollama)
LLM_CLASSIFIER_TIMEOUT=30          # Timeout do Ollama fallback
USE_LLM_NARRATOR=false             # Narrator desabilitado
SMART_ONLY=true                     # Usar apenas Smart Agent

# RBAC
ADMIN_USERS=ITALO
```

### Limites Groq Free Tier
- llama-3.1-8b-instant: 14,400 req/dia, 500K tokens/dia
- llama-3.3-70b-versatile: 1,000 req/dia, 100K tokens/dia
- Se bater limite (429), cai pro Ollama automaticamente
- Nunca cobra (free tier retorna 429, nao fatura)

---

## COMO INICIAR

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Garantir Ollama rodando (fallback)
ollama serve
ollama pull qwen3:4b

# 3. Iniciar servidor
python start.py
# Acesse: http://localhost:8000
```

---

## BUGS CONHECIDOS E ARMADILHAS

### 1. Entity Extraction pega palavras erradas como marca
- "data DE ENTREGA DA Donaldson" → regex pega "ENTREGA" como marca
- FIX: lista de noise words no regex (ENTREGA, PREVISAO, DATA, etc)
- SE ENCONTRAR NOVO CASO: adicionar palavra na lista `noise` em `extract_entities()`

### 2. LLM confunde DT_PEDIDO com PREVISAO_ENTREGA
- "maior data de entrega" → LLM retorna DT_PEDIDO_DESC
- FIX: Pos-processamento em `_llm_to_filters()` corrige automaticamente
- FILTER_RULES tem patterns explicitos pra "data de entrega" → PREVISAO_ENTREGA

### 3. Top 1 mostra item em vez de pedido
- "qual pedido..." com top=1 mostrava 1 item (linha de produto)
- FIX: view=pedidos + top=1 agora agrupa por PEDIDO e mostra todos itens

### 4. Groq nao conecta
- Verificar GROQ_API_KEY no .env
- Verificar se o servidor tem acesso a api.groq.com (firewall/proxy)
- Sistema cai automaticamente pro Ollama se Groq falhar

### 5. Ollama lento (30s+)
- CPU-only no servidor: qwen3:4b leva 10-30s
- Groq como Layer 1+ resolve 80% dos casos sem Ollama
- Se necessario, considerar GPU ou modelo menor

---

## MAPA DE CONHECIMENTO - ONDE COLOCAR CADA COISA

### 📊 ESTRUTURA DE TABELA → `knowledge/sankhya/tabelas/{TABELA}.md`
### 🔄 PROCESSO DE NEGÓCIO → `knowledge/processos/{modulo}/{processo}.md`
### 📖 TERMO/CONCEITO → `knowledge/glossario/{termo}.md`
### ⚖️ REGRA DE NEGÓCIO → `knowledge/regras/{regra}.md`
### ❌ ERRO/PROBLEMA → `knowledge/erros/{descricao}.md`
### 🔍 QUERY SQL → `queries/{modulo}/{descricao}.sql`

---

## CHECKLIST ANTES DE FINALIZAR

- [ ] Descobri tabela? → `knowledge/sankhya/tabelas/` + ATUALIZAR `relacionamentos.md`
- [ ] Descobri processo? → `knowledge/processos/{modulo}/`
- [ ] Descobri termo novo? → `knowledge/glossario/`
- [ ] Descobri regra? → `knowledge/regras/`
- [ ] Encontrei erro comum? → `knowledge/erros/`
- [ ] Criei query util? → `queries/{modulo}/`
- [ ] Query funcionou? → ADICIONAR em `knowledge/sankhya/exemplos_sql.md`
- [ ] Query deu erro? → ADICIONAR em `knowledge/sankhya/erros_sql.md`
- [ ] Termo novo do usuario? → ADICIONAR em `knowledge/glossario/sinonimos.md`
- [ ] Atualizei `PROGRESSO_ATUAL.md`?

---

## REGRAS DE MANUTENCAO DA BASE DE CONHECIMENTO

### NUNCA ignorar essas regras
A inteligencia do sistema depende DIRETAMENTE desses 4 arquivos:
- `knowledge/sankhya/relacionamentos.md` - Mapa de JOINs
- `knowledge/sankhya/exemplos_sql.md` - Queries validadas
- `knowledge/sankhya/erros_sql.md` - Erros conhecidos
- `knowledge/glossario/sinonimos.md` - Traducao de termos

### Cuidado com multiplicacao de JOINs
Tabelas com relacao 1:N a partir de TGFCAB:
- TGFITE (1 nota = N itens)
- TGFFIN (1 nota = N parcelas)
- NUNCA juntar TGFITE com TGFFIN na mesma query sem subquery

---

## OBJETIVO FINAL

Este repositorio alimenta uma plataforma com:
1. **Dashboards** - Substituir Power BI
2. **Smart Agent** - Chat inteligente que responde perguntas em linguagem natural, consulta banco em tempo real, filtra/ordena dados

**Quanto mais documentado, mais inteligente o sistema fica.**

---

*Versao 4.0 - Fevereiro 2026 (Smart Agent v3 + Groq + Ollama fallback)*
