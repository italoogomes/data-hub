# PROMPT MASTER — Arquitetura Completa do Data Hub MMarra

> **O QUE E ESTE DOCUMENTO:** Referencia obrigatoria para o Claude Code no VS Code.
> Antes de implementar QUALQUER prompt de funcionalidade, leia este documento inteiro.
> Ele descreve a arquitetura, padroes, convencoes e armadilhas do sistema.
> **Data:** 2026-02-18 | **Versao:** 5.0 (alinhada com codigo real) | **smart_agent.py:** ~4602 linhas

---

## 1. VISAO GERAL DO SISTEMA

O Data Hub e uma plataforma de BI conversacional para a MMarra Distribuidora Automotiva (~200 funcionarios). Substituiu Power BI como principal ferramenta de consulta de dados do ERP Sankhya.

**Stack:**
- Backend: Python FastAPI (`src/api/app.py`)
- Smart Agent: `src/llm/smart_agent.py` (~4602 linhas, monolito)
- Knowledge Base: `src/llm/knowledge_base.py` (TF-IDF, ~48 docs)
- Knowledge Compiler: `src/llm/knowledge_compiler.py` (auto-gera scoring/rules de knowledge/)
- Query Executor: `src/llm/query_executor.py` (executa SQL via API Sankhya)
- Result Validator: `src/llm/result_validator.py` (audit de resultados)
- Alias Resolver: `src/llm/alias_resolver.py` (apelidos de produto com auto-learning)
- Query Logger: `src/llm/query_logger.py` (log de queries em JSONL)
- Elasticsearch: 8.17.0 (`src/elastic/`) — busca fuzzy de produtos e parceiros
- LLM: Groq API (classificacao + narracao) + Ollama local (fallback)
- ERP: Sankhya (Oracle DB via API REST)
- Frontend: HTML/JS single-page (`src/api/static/index.html`)
- Deploy: Servidor local na empresa (32GB RAM, RTX 4060 Ti 8GB)

**Estrutura de diretorios relevante:**
```
src/
├── api/
│   ├── app.py              # FastAPI — auth, chat endpoint, sessoes
│   ├── reports.py           # Relatorios visuais (Power BI replacement)
│   └── static/
│       ├── index.html       # Frontend (login + chat + tabelas + KPIs + column toggles)
│       └── exports/         # Arquivos Excel gerados
├── elastic/                 # Elasticsearch integration
│   ├── mappings.py          # Indices: idx_produtos, idx_parceiros
│   ├── search.py            # ElasticSearchEngine (busca fuzzy)
│   └── sync.py              # Sincronizacao Sankhya → Elasticsearch
├── llm/
│   ├── smart_agent.py       # ★ ARQUIVO PRINCIPAL — toda a inteligencia (~4602 linhas)
│   ├── knowledge_base.py    # Knowledge Base com TF-IDF
│   ├── knowledge_compiler.py # Auto-gera scoring/rules de knowledge/
│   ├── alias_resolver.py    # Apelidos de produto (auto-learning + feedback)
│   ├── query_executor.py    # Executor seguro de SQL via API Sankhya
│   ├── query_logger.py      # Logger de queries (JSONL)
│   ├── result_validator.py  # Auditoria de resultados (checks de consistencia)
│   ├── train.py             # CLI para treinamento manual
│   ├── chat.py              # Motor de chat (legado)
│   ├── agent.py             # Agente LLM (legado)
│   └── llm_client.py        # Cliente LLM generico
└── mcp/                     # MCP Server (Claude Code integration)

knowledge/                   # Documentacao que alimenta o Knowledge Base
├── processos/
│   ├── vendas/fluxo_venda.md, rastreio_pedido.md, conferencia_vendedor.md
│   ├── compras/fluxo_compra.md, rotina_comprador.md
│   ├── estoque/devolucao.md, transferencia.md
│   └── financeiro/resumo_financeiro.md
├── glossario/
│   └── sinonimos.md         # Mapeamento termos → SQL (CRITICO)
├── sankhya/
│   ├── exemplos_sql.md      # 36+ queries referencia
│   ├── relacionamentos.md   # Mapa de JOINs entre tabelas
│   ├── erros_sql.md         # Erros conhecidos
│   └── tabelas/             # Dicionarios: TGFCAB, TGFITE, TGFVEN, TGFFIN, TGFVAR, TGFPRO, TGFPAR, TGFMAR, TGFEST, TGFTOP, TSIEMP...
├── regras/
│   └── rbac_vendas.md, aprovacao_compras.md, cotacao_compra.md, custos_produto.md, solicitacao_compra.md, codigos_auxiliares.md

data/
└── query_log.jsonl          # Log de todas as queries
```

---

## 2. ARQUITETURA DO SMART AGENT

### 2.1 Fluxo de Classificacao (Layers 0 → 3)

```
Pergunta do usuario
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 0: PRE-PROCESSAMENTO (0ms)                            │
│  0.1: Confirmacao curta → gerar_excel (se ctx tem dados)     │
│  0.2: Saudacao/Ajuda (score + tokens <= 5)                   │
│  0.3: Follow-up detection → _handle_filter_followup          │
│       (filtra dados anteriores via FILTER_RULES)             │
│  0.4: AliasResolver (apelidos de produto)                    │
│  0.5: detect_product_query → busca_fabricante/similares/     │
│       produto_360/busca_aplicacao                             │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: SCORING (0ms)                                      │
│  INTENT_SCORES → palavras-chave com pesos por intent         │
│  _COMPILED_SCORES → complementar do Knowledge Compiler       │
│  INTENT_THRESHOLDS → score minimo por intent                 │
│  Se score >= threshold → intent resolvido                    │
│                                                              │
│  Intents: pendencia_compras, estoque, vendas, gerar_excel,   │
│  saudacao, ajuda, busca_produto, busca_cliente,              │
│  busca_fornecedor, rastreio_pedido                           │
└──────────────┬──────────────────────────────────────────────┘
               │
               ├── Score ALTO (>=threshold) ──┐
               │                               ▼
               │                    ┌──────────────────────┐
               │                    │ LAYER 1.5: GROQ p/   │
               │                    │ QUERIES COMPLEXAS     │
               │                    │ _is_complex_query()   │
               │                    │ detecta filtros,      │
               │                    │ ordenacao, top, extra │
               │                    │ columns (~0.5s)       │
               │                    └──────────┬───────────┘
               │                               │
               │                               ▼
               │                    Executa handler do intent
               │                    com params + filters
               │
               ├── Score BAIXO mas tem entidade
               │   → Layer 1.5 (entity fallback: assume pendencia_compras)
               │
               ├── Score BAIXO (<threshold)
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: LLM CLASSIFIER (~0.5s)                             │
│  Cadeia: Groq API → Ollama local (fallback)                  │
│  Prompt retorna JSON: {intent, marca, filtro, ordenar, ...}  │
│  Pos-processamento: _llm_to_filters() corrige confusoes      │
│  Context-aware: _build_context_hint() injeta conversa        │
└──────────────┬──────────────────────────────────────────────┘
               │
               ├── LLM resolve → Executa handler
               │
               ├── LLM falha
               │
               ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: FALLBACK                                           │
│  Entity match → Knowledge Base → "nao entendi"               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Regra de ouro: Scoring resolve 80-90% das perguntas

O scoring e a base. A LLM e fallback. NUNCA criar um intent novo que depende 100% da LLM — sempre ter keywords no scoring primeiro.

### 2.3 INTENT_SCORES — Estado atual (linhas 210-310)

```python
INTENT_SCORES = {
    "pendencia_compras": {
        "pendencia": 10, "pendencias": 10, "pendente": 10, "pendentes": 10, "pend": 8,
        "compra": 6, "compras": 6, "pedido": 5, "pedidos": 5,
        "aberto": 5, "abertos": 5, "atraso": 5, "atrasado": 5, "atrasados": 5,
        "marca": 3, "fornecedor": 3, "comprador": 3, "empresa": 3, "filial": 3,
        "quantos": 2, "quais": 2, "qual": 2, "quanto": 2,
        "tem": 1, "temos": 1, "total": 2, "valor": 2,
        "falta": 4, "faltam": 4, "faltando": 4, "chegar": 3, "chegando": 3,
        "entrega": 3, "entregar": 3, "previsao": 3,
        "casada": 6, "casadas": 6, "empenho": 6, "empenhado": 6, "empenhados": 6,
        "vinculada": 5, "vinculado": 5, "reposicao": 5, "futura": 4,
        "quem": 4, "responsavel": 4, "fornece": 5,
    },
    "estoque": {
        "estoque": 10, "saldo": 8, "disponivel": 6,
        "produto": 3, "peca": 3, "pecas": 3, "item": 2,
        "critico": 5, "baixo": 4, "zerado": 5, "minimo": 4, "acabando": 5, "faltando": 4,
        "quantos": 2, "quanto": 2, "quais": 2, "codigo": 2, "cod": 2,
        "referencia": 4, "fabricante": 4, "similar": 5, "similares": 5,
        "equivalente": 5, "equivalentes": 5, "crossref": 5,
        "aplicacao": 5, "aplica": 5, "serve": 4, "compativel": 4,
        "veiculo": 3, "motor": 3, "caminhao": 3,
        "scania": 3, "mercedes": 3, "volvo": 3, "vw": 3, "man": 3, "daf": 3, "iveco": 3,
    },
    "vendas": {
        "vendas": 10, "venda": 10, "faturamento": 10,
        "faturou": 8, "vendeu": 8, "vendemos": 8, "faturamos": 8,
        "faturada": 6, "faturadas": 6, "faturado": 6,
        "hoje": 3, "ontem": 3, "semana": 3, "mes": 3, "ano": 3,
        "ticket": 5, "tiquete": 5, "medio": 3,
        "quanto": 3, "total": 3, "valor": 2,
        "ranking": 4, "top": 4, "maiores": 3, "melhores": 3,
        "vendedor": 3, "vendedores": 3,
    },
    "gerar_excel": {
        "excel": 10, "planilha": 10, "xlsx": 10, "csv": 8,
        "arquivo": 8, "download": 8, "baixar": 8, "exportar": 8,
        "gera": 6, "gerar": 6, "gere": 6, "relatorio": 5,
    },
    "saudacao": {
        "oi": 10, "ola": 10, "bom": 5, "dia": 3, "boa": 5,
        "tarde": 3, "noite": 3, "fala": 6, "hey": 8, "hello": 8, "eai": 8, "eae": 8,
    },
    "ajuda": {
        "ajuda": 10, "help": 10, "menu": 8, "comandos": 8, "opcoes": 8,
        "funciona": 5, "consegue": 5, "funcoes": 6,
    },
    "busca_produto": {
        "busca": 8, "buscar": 8, "procura": 8, "procurar": 8,
        "encontra": 8, "encontrar": 8, "acha": 7, "achar": 7,
        "existe": 6, "tem": 4,
        "produto": 3, "peca": 3, "pecas": 3, "filtro": 3, "catalogo": 6,
    },
    "busca_cliente": {
        "cliente": 8, "clientes": 8,
        "dados": 5, "contato": 5, "telefone": 5, "cnpj": 8, "cpf": 7,
        "endereco": 4, "email": 4,
        "busca": 3, "procura": 3, "encontra": 3,
    },
    "busca_fornecedor": {
        "fornecedor": 8, "fornecedores": 8,
        "contato": 5, "telefone": 5, "dados": 5, "cnpj": 6, "email": 4,
        "busca": 3, "procura": 3,
    },
    "rastreio_pedido": {
        "rastrear": 10, "rastreio": 10, "rastreamento": 10,
        "status": 6, "acompanhar": 6,
        "conferencia": 8, "conferindo": 8, "conferido": 8, "conferir": 8,
        "separacao": 7, "separando": 7, "separado": 7,
        "wms": 8, "expedicao": 6,
        "chegou": 6, "entregou": 6, "comprado": 6, "comprou": 6,
        "faturado": 6, "faturou": 6,
        "pedido": 5, "pedidos": 5,
        "venda": 4, "vendeu": 4, "vendi": 4,
        "cade": 6, "onde": 3, "como": 3, "quando": 4,
    },
}
```

### 2.4 INTENT_THRESHOLDS — Estado atual (linhas 313-324)

```python
INTENT_THRESHOLDS = {
    "pendencia_compras": 8,
    "estoque": 8,
    "vendas": 8,
    "gerar_excel": 8,
    "saudacao": 8,
    "ajuda": 8,
    "busca_produto": 10,
    "busca_cliente": 10,
    "busca_fornecedor": 10,
    "rastreio_pedido": 10,
}
```

**Nota:** Intents de busca/rastreio tem thresholds mais altos (10) para evitar falsos positivos. Os 3 intents basicos (pendencia, estoque, vendas) usam threshold 8.

### 2.5 Knowledge Compiler — Scoring compilado

O `knowledge_compiler.py` analisa a pasta `knowledge/` e gera `compiled_knowledge.json` com:
- `_COMPILED_SCORES`: keywords extras por intent (complementam INTENT_SCORES, nunca sobrescrevem)
- `_COMPILED_RULES`: FILTER_RULES extras
- `_COMPILED_EXAMPLES`: exemplos Groq extras
- `_COMPILED_SYNONYMS`: sinonimos extras

O `score_intent()` soma manual + compilado. Manual SEMPRE ganha em caso de conflito.

### 2.6 FILTER_RULES — Pattern matching para filtros (linhas 2190-2232)

```python
FILTER_RULES = [
    # ORDEM IMPORTA — mais especificos primeiro!

    # === TIPO DE COMPRA ===
    {"match": ["compra casada", "compras casadas", "pedido casado", "empenho", ...],
     "filter": {"TIPO_COMPRA": "Casada"}},
    {"match": ["compra estoque", "compra de estoque", "entrega futura", "reposicao"],
     "filter": {"TIPO_COMPRA": "Estoque"}},

    # === PREVISAO DE ENTREGA (mais especificos primeiro!) ===
    {"match": ["maior data de entrega", ...], "sort": "PREVISAO_ENTREGA_DESC", "top": 1},
    {"match": ["menor data de entrega", ...], "sort": "PREVISAO_ENTREGA_ASC", "top": 1},
    {"match": ["data de entrega mais distante", ...], "sort": "PREVISAO_ENTREGA_DESC", "top": 1},
    {"match": ["data de entrega mais proxima", ...], "sort": "PREVISAO_ENTREGA_ASC", "top": 1},

    # === SUPERLATIVOS (sort + top N) ===
    {"match": ["mais atrasado"],    "sort": "DIAS_ABERTO_DESC",  "top": 1},
    {"match": ["mais atrasados"],   "sort": "DIAS_ABERTO_DESC",  "top": 5},
    {"match": ["mais caro"],        "sort": "VLR_PENDENTE_DESC", "top": 1},
    {"match": ["mais caros"],       "sort": "VLR_PENDENTE_DESC", "top": 5},
    {"match": ["mais barato"],      "sort": "VLR_PENDENTE_ASC",  "top": 1},
    {"match": ["mais baratos"],     "sort": "VLR_PENDENTE_ASC",  "top": 5},
    {"match": ["mais antigo"],      "sort": "DIAS_ABERTO_DESC",  "top": 1},
    {"match": ["mais recente"],     "sort": "DT_PEDIDO_DESC",    "top": 1},
    {"match": ["maior valor"],      "sort": "VLR_PENDENTE_DESC", "top": 1},
    {"match": ["menor valor"],      "sort": "VLR_PENDENTE_ASC",  "top": 1},
    {"match": ["maior quantidade"], "sort": "QTD_PENDENTE_DESC", "top": 1},
    {"match": ["mais urgente"],     "sort": "DIAS_ABERTO_DESC",  "top": 1},

    # === FILTROS por CAMPO ===
    {"match": ["sem previsao de entrega", ...], "filter_fn": "empty", "filter_field": "PREVISAO_ENTREGA"},
    {"match": ["sem confirmacao", ...],         "filter": {"CONFIRMADO": "N"}},
    {"match": ["confirmado", "confirmados"],    "filter": {"CONFIRMADO": "S"}},

    # === STATUS_ENTREGA ===
    {"match": ["sem previsao"],                 "filter": {"STATUS_ENTREGA": "SEM PREVISAO"}},
    {"match": ["no prazo", "dentro do prazo"],  "filter": {"STATUS_ENTREGA": "NO PRAZO"}},
    {"match": ["atrasado", "atrasados"],        "filter": {"STATUS_ENTREGA": "ATRASADO"}},
    {"match": ["proximo", "proximos"],          "filter": {"STATUS_ENTREGA": "PROXIMO"}},
]
```

**Armadilha:** Se colocar regra generica antes de especifica, a generica come a especifica. Sempre mais especifico primeiro.

### 2.7 extract_entities() — Extracao de entidades (linhas 997-1239)

Extrai parametros da pergunta do usuario via regex + match com dados do banco:
- `marca` — Estrategia 1: regex "MARCA X" ou "DA/DE/DO X" + noise list. Estrategia 2: match com known_marcas (carregadas do Sankhya)
- `fornecedor` — regex "FORNECEDOR X" (ignora "fornecedor DA marca")
- `empresa` — prefixo explicito ("empresa/filial X") ou cidade (mapa de 7 cidades → prefixo)
- `comprador` — regex "COMPRADOR X" + match com known_compradores
- `nunota` — regex "PEDIDO/NOTA/NUNOTA + numero"
- `codprod` — regex "CODIGO/COD/PRODUTO + numero"
- `codigo_fabricante` — alfanumerico (HU711/51, WK950/21, 078115561J)
- `produto_nome` — regex "PRODUTO/PECA/ITEM + texto"
- `aplicacao` — veiculo/modelo ("serve no X", "pecas do X")
- `periodo` — "hoje", "ontem", "semana", "mes", "mes_passado", "semana_passada"

**Noise list (linhas 1016-1026):**
```python
noise = {"COMPRA", "COMPRAS", "VENDA", "VENDAS", "EMPRESA", "FORNECEDOR",
         "MARCA", "PRODUTO", "PRODUTOS", "ESTOQUE", "PEDIDO", "PEDIDOS", "MES",
         "SEMANA", "ANO", "HOJE", "ONTEM", "PERIODO", "SISTEMA",
         "TODAS", "TODOS", "TUDO", "GERAL", "MINHA", "MINHAS",
         "ENTREGA", "PREVISAO", "DATA", "CONFIRMACAO", "COMPRADOR",
         "VALOR", "QUANTIDADE", "STATUS", "PRAZO", "ATRASO",
         "ESTA", "ESTAO", "ESSE", "ESSA", "ISSO", "AQUI", "ONDE",
         "QUEM", "RESPONSAVEL", "FORNECEDORES", "COMPRADORES",
         "CASADA", "CASADAS", "CASADO", "CASADOS", "EMPENHO",
         "FUTURA", "REPOSICAO", "FILIAL", "UNIDADE", "LOJA"}
```

**Mapa de cidades → empresa (linhas 1078-1087):**
```python
_CIDADES_EMPRESA = {
    "ARACATUBA": "ARACAT", "RIBEIRAO PRETO": "RIBEIR",
    "UBERLANDIA": "UBERL", "ITUMBIARA": "ITUMBI",
    "RIO VERDE": "RIO VERDE", "GOIANIA": "GOIAN", "SAO JOSE": "SAO JOSE",
}
```

**Armadilha conhecida:** O regex "DA/DE/DO" pode confundir palavras como "ENTREGA" com marca. A noise list filtra. SE ENCONTRAR NOVO CASO: adicionar a palavra na lista `noise`.

### 2.8 _build_where_extra() — Construcao de WHERE clause (linhas 1296-1332)

Converte params extraidos em clausulas SQL. **Todos os valores passam pelo `_safe_sql()`** (sanitizacao contra SQL injection):

```python
def _build_where_extra(params, user_context=None):
    w = ""
    if params.get("marca"):
        w += f" AND UPPER(MAR.DESCRICAO) LIKE UPPER('%{_safe_sql(params['marca'])}%')"
    if params.get("fornecedor"):
        w += f" AND UPPER(PAR.NOMEPARC) LIKE UPPER('%{_safe_sql(params['fornecedor'])}%')"
    if params.get("empresa"):
        w += f" AND UPPER(EMP.NOMEFANTASIA) LIKE UPPER('%{_safe_sql(params['empresa'])}%')"
    if params.get("comprador"):
        w += f" AND UPPER(VEN.APELIDO) LIKE UPPER('%{_safe_sql(params['comprador'])}%')"
    # ... + nunota, codprod, produto_nome, aplicacao, tipo_compra
    # + RBAC (admin/gerente/vendedor/comprador)
```

**`_safe_sql()` (linha 1284):** Remove chars perigosos (`;`, `--`, `/*`, `\`, `\x00`), escapa aspas simples (Oracle-style `''`).

---

## 3. ELASTICSEARCH

### 3.1 Estado atual
- Elasticsearch 8.17.0, cluster green
- `idx_produtos`: ~393K documentos (TGFPRO)
- `idx_parceiros`: ~57K documentos (TGFPAR)
- Modulo: `src/elastic/` (mappings.py, search.py, sync.py)

### 3.2 ElasticSearchEngine (`src/elastic/search.py`)

**Busca de produtos (`search_products`):**
- Por codigo: match exato (boost 10) → match limpo sem separadores (boost 8) → fuzzy (boost 5) → wildcard (boost 3)
- Por texto: multi_match em DESCRPROD, COMPLDESC, CARACTERISTICAS
- Filtro: marca, aplicacao, ativo=True
- Retorna: codprod, descricao, marca, referencia, estoque

**Busca de parceiros (`search_partners`):**
- multi_match em NOMEPARC, RAZAOSOCIAL, CGC_CPF, CODPARC
- Filtro: tipo C (cliente) ou F (fornecedor)
- Retorna: codparc, nome, fantasia, cidade/UF, telefone

### 3.3 Integracao com SmartAgent

O `SmartAgent.__init__` tenta importar `ElasticSearchEngine`. Se falhar (Elastic offline), `self.elastic = None` e buscas caem para SQL.

Handlers que usam Elastic:
- `_handle_busca_produto` (linha 4266)
- `_handle_busca_parceiro` (linha 4370) — generico, recebe tipo="C" ou tipo="F"

### 3.4 Bug conhecido: Follow-ups de busca Elastic

**Problema:** Resultado da busca Elastic NAO e totalmente salvo no ConversationContext. Se o usuario pergunta "e o primeiro, tem em estoque?", o sistema nao resolve a referencia.

**Mitigacao futura:** Salvar resultados Elastic no contexto com indice numerico.

---

## 4. CONVERSATION CONTEXT

### 4.1 Classe ConversationContext (linhas 2692-2751)

Cada usuario tem um `ConversationContext` armazenado em memoria (dict por user_id):

```python
class ConversationContext:
    user_id: str            # Identificador do usuario
    intent: str             # Ultimo intent resolvido
    params: dict            # {marca, fornecedor, empresa, comprador, periodo, codprod, produto_nome, pedido}
    last_result: dict       # {detail_data, columns, description, params, intent}
    last_question: str      # Ultima pergunta
    last_view_mode: str     # "pedidos" ou "itens"
    turn_count: int         # Quantas perguntas ja fez
    _extra_columns: list    # Colunas extras pedidas pelo usuario
```

**Metodos:**
- `merge_params(new)` — Mescla params novos com contexto. Novo sobrescreve, ausente herda.
- `update(intent, params, result, question, view_mode)` — Atualiza apos resposta. Limpa extra_columns ao mudar de intent.
- `has_data()` → bool — Tem dados anteriores?
- `get_data()` → list — Retorna detail_data
- `get_description()` → str — Descricao do ultimo resultado

### 4.2 Heranca de parametros

```
Usuario: "pendencias da MANN"     → marca=MANN (extraida)
Usuario: "e as atrasadas?"        → marca=MANN (herdada) + STATUS=ATRASADO
Usuario: "exporta pra excel"      → usa dados da ultima consulta
```

### 4.3 Follow-up detection (linhas 2468+)

```python
FOLLOWUP_WORDS = {"desses", "destes", "daqueles", "esses", "estes", "aqueles",
                   "mesma", "mesmo", "tambem", "alem", "ainda", "agora", "entao", ...}

FOLLOWUP_PATTERNS = [
    r'\b(desse[s]?|deste[s]?|daquela?[s]?)...',
    r'^e\s+(os|as|quais|quantos)...',
    # ...
]
```

### 4.4 Context-Aware Classifier

A funcao `_build_context_hint(ctx)` gera um texto com o contexto da conversa anterior e injeta no prompt do LLM Classifier. Isso permite que o Groq entenda referencias como "e os atrasados?" mesmo sem entidade explicita.

### 4.5 Padrao para novos handlers — CONTEXTO OBRIGATORIO

Quando criar um novo handler, SEMPRE:
1. Salvar params: `ctx.update(intent, params, result_data, question, view_mode)`
2. Montar result_data: `{"detail_data": [...], "columns": [...], "description": "...", "params": {...}, "intent": "..."}`
3. Suportar heranca: verificar se params vem do contexto anterior (`ctx.merge_params`)

---

## 5. HANDLERS — Estado atual

### 5.1 Padrao de retorno (REAL — todos os handlers)

```python
return {
    "response": str,           # Texto markdown da resposta
    "tipo": str,               # "consulta_banco" | "info" | "arquivo" | "erro"
    "query_executed": str,     # SQL ou metodo (primeiros 200 chars) ou None
    "query_results": int,      # Numero de rows retornadas (0 se info/error) ou None
    "time_ms": int,            # Milissegundos (opcional, presente em handlers async)
    "_detail_data": list,      # [INTERNO] Dados brutos para follow-ups — removido antes de enviar ao frontend
}
```

**Valores de `tipo`:**
- `"consulta_banco"` → Resultado de query SQL ou Elastic (tabela/KPIs)
- `"info"` → Knowledge/help/greeting (sem dados)
- `"arquivo"` → Excel gerado (inclui `download_url`)
- `"erro"` → Erro generico

**IMPORTANTE:** O `_detail_data` e removido pelo `ask()` antes de retornar ao frontend, mas recolocado internamente para que o endpoint `table_data` possa montar toggles de colunas.

### 5.2 Handlers existentes

| Handler | Intent | Linha | O que faz | Status |
|---------|--------|-------|-----------|--------|
| `_handle_saudacao` | saudacao | 3385 | Boas-vindas com hora do dia | ✅ |
| `_handle_ajuda` | ajuda | 3397 | Lista de capacidades | ✅ |
| `_handle_fallback` | — | 3407 | "Nao entendi" com exemplos | ✅ |
| `_handle_pendencia_compras` | pendencia_compras | 3412 | Pedidos compra pendentes (KPIs + tabela + narrador) | ✅ Completo |
| `_handle_estoque` | estoque | 3662 | Estoque por produto/codigo (SQL + narrador) | ✅ Completo |
| `_handle_vendas` | vendas | 3717 | KPIs vendas + top vendedores (basico) | ⚠️ Limitado |
| `_handle_rastreio_pedido` | rastreio_pedido | 3820 | Rastreio pedido venda: status + itens + compras | ✅ Completo |
| `_handle_busca_fabricante` | produto (sub) | 4080 | Busca por codigo fabricante | ✅ |
| `_handle_similares` | produto (sub) | 4132 | Cross-reference via AD_TGFPROAUXMMA | ✅ |
| `_handle_busca_aplicacao` | produto (sub) | 4175 | Busca por veiculo/aplicacao | ✅ |
| `_handle_busca_produto` | busca_produto | 4266 | Busca Elastic em idx_produtos | ✅ |
| `_handle_busca_parceiro` | busca_cliente/busca_fornecedor | 4370 | Busca Elastic em idx_parceiros (tipo C ou F) | ✅ |
| `_handle_produto_360` | produto (sub) | 4426 | Visao completa (estoque+vendas+pendencias) | ✅ |
| `_handle_excel_followup` | gerar_excel | 4582 | Exporta last_data para .xlsx | ✅ |
| `_handle_filter_followup` | (follow-up) | 3282 | Filtra dados anteriores via FILTER_RULES | ✅ |

**Nota:** `busca_cliente` e `busca_fornecedor` sao intents SEPARADOS no scoring, mas ambos chamam `_handle_busca_parceiro` com parametro `tipo="C"` ou `tipo="F"`.

### 5.3 _handle_rastreio_pedido — Detalhes (linha 3820)

Handler com 3 cenarios:

**Sem NUNOTA:** Lista pedidos de venda pendentes do vendedor
```sql
TGFCAB C JOIN TGFPAR P
WHERE C.TIPMOV='P' AND C.PENDENTE='S' AND C.CODTIPOPER IN (1001,1007,1012)
+ RBAC: AND C.CODVEND = :codvend (vendedor)
```

**Com NUNOTA — Etapa 1 (Status):**
```sql
TGFCAB + TGFPAR + TGFVEN
→ STATUSNOTA, STATUSCONFERENCIA, SITUACAOWMS, VLRNOTA, DTFATUR
→ Traduz codigos via CONF_STATUS_MAP e WMS_STATUS_MAP
```

**Com NUNOTA — Etapa 2 (Itens + Estoque):**
```sql
TGFITE + TGFPRO + TGFMAR + TGFEST
→ QTDNEG, QTDCONFERIDA, ESTOQUE, RESERVADO, DISPONIVEL
→ Classifica: DISPONIVEL / PARCIAL / SEM ESTOQUE
```

**Com NUNOTA — Etapa 3 (Compras vinculadas):**
```sql
TGFCAB(compra) + TGFITE + TGFVAR + TGFPAR(fornecedor)
WHERE CODTIPOPER IN (1301,1313) AND PENDENTE='S'
→ Mostra pedidos de compra dos itens sem estoque
```

**Status Maps (linhas 3789-3818):**
```python
CONF_STATUS_MAP = {
    "AL": "Aguardando liberacao p/ conferencia",
    "AC": "Na fila de conferencia",
    "A": "Sendo conferido agora",
    "Z": "Aguardando finalizacao",  # NAO e "zerada"!
    "F": "Conferencia OK",
    "D": "Conferencia com divergencia",
    "R": "Aguardando recontagem",
    "RA": "Recontagem em andamento",
    "RF": "Recontagem OK",
    "RD": "Recontagem com divergencia",
    "C": "Aguardando liberacao de corte",  # NAO e "cancelada"!
}
WMS_STATUS_MAP = {
    -1: "Nao enviado p/ separacao", 0: "Na fila de separacao",
    1: "Enviado p/ separacao", 2: "Separando agora",
    3: "Separado, aguardando conferencia", 4: "Sendo conferido",
    7: "Pedido totalmente cortado", 8: "Pedido parcialmente cortado",
    9: "Conferencia OK, pronto p/ faturar",
    10: "Aguardando conferencia (pos-separacao)",
    12: "Conferencia com divergencia", 13: "Parcialmente conferido",
    16: "Concluido", 17: "Aguardando conferencia de volumes", 100: "Cancelado",
}
```

---

## 6. GROQ API — Pools de chaves

### 6.1 GroqKeyPool (linhas 55-143)

3 pools de chaves Groq, rotacao round-robin com cooldown automatico:

```python
pool_classify = _make_pool("GROQ_POOL_CLASSIFY", "classify")  # Classificacao (Layer 2)
pool_narrate  = _make_pool("GROQ_POOL_NARRATE", "narrate")    # Narracao de respostas
pool_train    = _make_pool("GROQ_POOL_TRAIN", "train")        # Training/batch
```

Fallback: se env vars `GROQ_POOL_*` nao existem, usa `GROQ_API_KEY` legado para todos.

**Features:**
- Round-robin entre chaves do pool
- Cooldown automatico no 429 (rate limit)
- Retry com chave alternativa
- Reset diario de contadores
- Stats disponiveis via `.stats()`

### 6.2 Modelo e configuracao

```env
GROQ_MODEL=llama-3.1-8b-instant   # Rapido e gratuito
GROQ_TIMEOUT=10                     # Timeout em segundos
```
- Classificacao: temperature=0.0
- Narracao: temperature=0.6
- Limites free tier: 14,400 req/dia, 500K tokens/dia

### 6.3 LLM_CLASSIFIER_PROMPT — Estado atual (linhas 390-637)

Prompt completo com:
- **12 intents** definidos (pendencia_compras, estoque, vendas, produto, busca_produto, busca_cliente, busca_fornecedor, rastreio_pedido, conhecimento, saudacao, ajuda, desconhecido)
- **17 campos** no JSON de retorno (intent, marca, fornecedor, empresa, comprador, periodo, view, filtro, ordenar, top, tipo_compra, aplicacao, texto_busca, nunota, extra_columns)
- **34+ exemplos** cobrindo todos os intents, incluindo filtros, ordenacao, top N, tipo_compra, cidades, codigos fabricante, aplicacao, buscas, rastreio com NUNOTA, extra_columns
- **4 exemplos com contexto** (follow-up sobre dados anteriores)
- **Disambiguacao explicita**: DT_PEDIDO vs PREVISAO_ENTREGA, TIPO_COMPRA, view itens vs pedidos
- **Extra columns**: detecta "contendo X", "mostrando X", "com campo X" e mapeia para colunas SQL

**NAO SUBSTITUIR este prompt** — e o resultado de 30+ sessoes de refinamento. Apenas adicionar exemplos novos quando necessario.

### 6.4 Pos-processamento _llm_to_filters() (linhas 2402-2465)

Converte JSON do LLM em filtros internos:
- `filtro.operador="igual"` → `filters[campo] = valor`
- `filtro.operador="vazio"` → `filters["_fn_empty"] = campo`
- `filtro.operador="maior/menor"` → `filters["_fn_maior/_fn_menor"] = "campo:valor"`
- `ordenar` → `filters["_sort"]`
- `top` → `filters["_top"]`
- `tipo_compra` → `filters["TIPO_COMPRA"]`

**Correcao automatica (linhas 2449-2463):** Se a pergunta menciona "entrega/previsao/chegar" e o LLM retornou DT_PEDIDO, corrige para PREVISAO_ENTREGA.

---

## 7. RBAC — Controle de acesso

### 7.1 Perfis

| Role | Ve o que | Como filtra |
|------|----------|-------------|
| `admin` / `diretor` / `ti` | TUDO | Sem filtro |
| `gerente` | Equipe dele | `CODVEND IN (team_codvends)` |
| `vendedor` / `comprador` | So dele | `CODVEND = {codvend}` |

### 7.2 Implementacao

O `user_context` vem do login Sankhya:
```python
user_context = {
    "role": "admin",           # Definido por ADMIN_USERS no .env
    "codvend": 42,             # CODVEND do vendedor logado
    "team_codvends": [42, 55, 63],  # Se gerente, codigos da equipe
    "codemp": 1,               # Empresa do usuario
    "user": "ITALO",           # Username
}
```

O filtro RBAC e aplicado em `_build_where_extra()`:
```python
if role in ("admin", "diretor", "ti"):
    pass  # Ve tudo
elif role == "gerente":
    w += f" AND MAR.AD_CODVEND IN ({team})"  # Pendencia compras: comprador da marca
elif role in ("vendedor", "comprador"):
    w += f" AND MAR.AD_CODVEND = {codvend}"  # Pendencia compras
```

### 7.3 Armadilha: RBAC em novos handlers

**Todo novo handler DEVE aplicar RBAC.** Se esquecer, o vendedor ve dados de todo mundo.

Para handlers de vendas, o campo RBAC e:
- `CAB.CODVEND` (vendedor da nota) — NAO confundir com `MAR.AD_CODVEND` (comprador da marca, usado em pendencia de compras)

---

## 8. LLM NARRATOR

### 8.1 O que faz

Pega dados brutos (KPIs + tabela) e gera resposta em linguagem natural.

**Sem narrador:** "Tabela com 42 registros. Total: R$ 1.2M"
**Com narrador:** "Encontrei 42 itens pendentes da MANN, totalizando R$ 1.2M. O pedido mais antigo e de 15/01..."

### 8.2 Fluxo

```python
if USE_LLM_NARRATOR and len(results) > 0:
    summary = build_{intent}_summary(kpis, table_data, params)
    narration = await llm_narrate(question, summary, "")
    if narration:
        response = narration + "\n\n" + formatted_table
    else:
        response = formatted_table  # fallback: so tabela
```

### 8.3 build_*_summary — Funcoes existentes

| Funcao | Linha | Intent |
|--------|-------|--------|
| `build_pendencia_summary()` | 871 | pendencia_compras |
| `build_vendas_summary()` | 932 | vendas |
| `build_estoque_summary()` | 960 | estoque |
| `build_result_data_summary()` | (importado de result_validator) | generico |

Pool dedicado: `pool_narrate` (chaves separadas para nao competir com classificacao).

---

## 9. COLUNAS DINAMICAS (Extra Columns)

### 9.1 Como funciona (linhas 2308-2362)

O Groq detecta colunas extras no prompt do usuario ("contendo codigo fabricante", "mostrando empresa e previsao") e retorna em `extra_columns`.

**EXISTING_SQL_COLUMNS** — Ja existem no SQL base (nao precisa modificar query):
```
EMPRESA, PEDIDO, TIPO_COMPRA, COMPRADOR, DT_PEDIDO, PREVISAO_ENTREGA, CONFIRMADO,
FORNECEDOR, CODPROD, PRODUTO, MARCA, APLICACAO, NUM_FABRICANTE, UNIDADE,
QTD_PEDIDA, QTD_ATENDIDA, QTD_PENDENTE, VLR_UNITARIO, VLR_PENDENTE, DIAS_ABERTO, STATUS_ENTREGA
```

**EXTRA_SQL_FIELDS** — Precisam ser adicionados ao SQL:
```python
"NUM_ORIGINAL":    "NVL(PRO.AD_NUMORIGINAL, '') AS NUM_ORIGINAL"
"REFERENCIA":      "NVL(PRO.REFERENCIA, '') AS REFERENCIA"
"REF_FORNECEDOR":  "NVL(PRO.REFFORN, '') AS REF_FORNECEDOR"
"COMPLEMENTO":     "NVL(PRO.COMPLDESC, '') AS COMPLEMENTO"
"NCM":             "NVL(PRO.NCM, '') AS NCM"
```

**COLUMN_NORMALIZE** — Normaliza variacoes do Groq (ex: "PREVISAO" → "PREVISAO_ENTREGA").
**COLUMN_LABELS** — Labels amigaveis para headers no frontend.
**COLUMN_MAX_WIDTH** — Largura maxima para truncar no frontend.

---

## 10. QUERY EXECUTOR — Acesso ao banco

### 10.1 Como funciona
`query_executor.py` executa SQL via API REST do Sankhya (nao acessa Oracle diretamente).

```python
result = await self.executor.execute(sql)
# Retorna: {"success": bool, "data": list, "columns": list, "error": str}
```

### 10.2 Endpoint Sankhya
- URL: `{SANKHYA_URL}/mge/service.sbr?serviceName=DbExplorerSP.executeQuery`
- Autenticacao: Token de sessao via MobileLoginSP.login
- Limite: Queries SELECT apenas (read-only)

### 10.3 Regras de SQL no Sankhya

**NUNCA juntar TGFITE com TGFFIN na mesma query sem subquery:**
- TGFCAB → TGFITE = 1:N (1 nota = N itens)
- TGFCAB → TGFFIN = 1:N (1 nota = N parcelas)
- JOIN direto multiplica registros! Usar subqueries separadas.

**Aliases obrigatorios:**
```sql
TGFCAB CAB   -- Cabecalho de notas/pedidos
TGFITE ITE   -- Itens da nota
TGFFIN FIN   -- Financeiro (parcelas)
TGFVEN VEN   -- Vendedor
TGFPAR PAR   -- Parceiro (cliente/fornecedor)
TGFPRO PRO   -- Produto
TGFMAR MAR   -- Marca (em compras: AD_CODVEND e o comprador)
TGFVAR VAR   -- Variacoes/entregas parciais
TSIEMP EMP   -- Empresa
```

**TOP N no Oracle (Sankhya):**
```sql
-- ERRADO: SELECT TOP 10 ...  (nao existe no Oracle)

-- CERTO (opcao 1 — ROWNUM):
SELECT * FROM (SELECT ... ORDER BY X DESC) WHERE ROWNUM <= 10

-- CERTO (opcao 2 — FETCH FIRST, Oracle 12c+):
SELECT ... ORDER BY X DESC FETCH FIRST 10 ROWS ONLY
```

**JOIN com TGFTOP (Tipos de Operacao):**
```sql
-- TGFTOP tem versionamento por DHALTER. Usar subconsulta para pegar versao mais recente:
JOIN TGFTOP TOP ON CAB.CODTIPOPER = TOP.CODTIPOPER AND CAB.DHTIPOPER = TOP.DHALTER
-- Se nao precisar de dados da TGFTOP, filtrar direto pelo CODTIPOPER na TGFCAB
```

**Datas no Oracle:**
```sql
WHERE CAB.DTFATUR >= TRUNC(SYSDATE, 'MM')                         -- Mes corrente
WHERE CAB.DTFATUR BETWEEN TO_DATE('01/01/2026', 'DD/MM/YYYY')
                       AND TO_DATE('31/01/2026', 'DD/MM/YYYY')    -- Periodo especifico
```

---

## 11. TABELAS SANKHYA — Referencia rapida

### 11.1 TGFCAB — Cabecalho de notas/pedidos (416 campos)
- `NUNOTA` — PK, numero unico da nota
- `NUMNOTA` — Numero da NF (pode repetir entre empresas)
- `CODEMP` — Empresa
- `CODPARC` — Parceiro (cliente ou fornecedor)
- `CODVEND` — Vendedor
- `CODTIPOPER` — Tipo de operacao (TOP)
- `TIPMOV` — Tipo movimento: V=Venda, P=Pedido de Venda, C=Compra(entrada), D=Devolucao, O=Pedido de Compra, J=Solicitacao, E=Devolucao de Compra(saida)
- `DTFATUR` — Data faturamento (quando a NF-e foi emitida)
- `DTNEG` — Data negociacao (quando o pedido/venda foi registrado)
  **Usar DTNEG para filtros de periodo em vendas (DTFATUR pode ser NULL em pedidos nao faturados).**
- `STATUSNOTA` — L=Liberada, P=Pendente, A=Em andamento, C=Cancelada
- `VLRNOTA` — Valor total da nota
- `AD_MARGEM` — Margem % (campo customizado, testado)
- `AD_VLRCOMINT` — Valor comissao interna
- `AD_ALIQCOMINT` — Aliquota comissao interna %
- `AD_TIPOSROTA` — Tipo de expedicao/entrega (EE, EM, TRAN, EPR, etc.)
- `AD_NUNOTAVENDAEMP` — NUNOTA do pedido de venda que originou compra casada
- `AD_NUNOTAMAE` — NUNOTA do pedido mae
- `DTPREVENT` — Data previsao de entrega (pedidos de compra)
- `PENDENTE` — S=tem itens pendentes, N=tudo atendido
- `STATUSCONFERENCIA` — Status conferencia WMS
- `SITUACAOWMS` — Estado operacional WMS
- `LIBCONF` — Liberado para conferencia (S/N)

### 11.2 TOPs (Tipos de Operacao) relevantes

**Vendas:**
| TOP | Descricao | TIPMOV |
|-----|-----------|--------|
| 1100 | Venda Balcao NF-e | V |
| 1101 | Venda NF-e | V |
| 1000 | Orcamento venda | P |
| 1001 | Pedido venda WMS consumo | P |
| 1007 | Pedido venda empenho | P |
| 1012 | Pedido venda | P |

**Compras:**
| TOP | Descricao | TIPMOV |
|-----|-----------|--------|
| 1804 | Solicitacao de compra | J |
| 1301 | Pedido Compra Revenda | O |
| 1313 | Pedido Compra Entrega Futura (Casada) | O |
| 1209 | Compra mercadoria revenda | C |
| 1452 | Transferencia entrada | C |

**Devolucoes:**
| TOP | Descricao | TIPMOV |
|-----|-----------|--------|
| 1202 | Devolucao de venda | D |
| 1501 | Devolucao de compra | E |

**ARMADILHA CRITICA:** TIPMOV de pedido de compra e `O`, NAO `C`. TIPMOV=C e so quando a nota fiscal de ENTRADA e lancada. Se filtrar pedidos pendentes com TIPMOV=C, nao vai encontrar nada!

### 11.3 TGFITE — Itens (237 campos)
- `NUNOTA` + `SEQUENCIA` — PK composta
- `CODPROD` — Produto
- `QTDNEG` — Quantidade negociada
- `VLRTOT` — Valor total do item
- `VLRUNIT` — Valor unitario
- `QTDCONFERIDA` — Quantidade conferida (WMS)
- `PENDENTE` — S/N (item pendente)

### 11.4 TGFVEN — Vendedor (41 campos)
- `CODVEND` — PK
- `APELIDO` — Nome/apelido
- `CODGER` — Codigo do gerente
- `ATIVO` — S/N
- `TIPVEND` — Tipo: R=Representante, I=Interno, E=Externo, G=Gerente
- `AD_ALIQCOMINT` — Aliquota comissao do vendedor

### 11.5 TGFFIN — Financeiro (298 campos)
- `NUFIN` — PK
- `NUNOTA` — Nota de origem
- `DTVENC` — Data vencimento
- `VLRDESDOB` — Valor da parcela
- `DHBAIXA` — Data/hora baixa (pagamento)
- `RECDESP` — 1=Receita (receber), -1=Despesa (pagar)
- `CODTIPTIT` — Tipo titulo (boleto, duplicata, etc.)

### 11.6 TGFVAR — Variacoes/entregas parciais
- `NUNOTA` + `SEQUENCIA` — PK
- `NUNOTAORIG` + `SEQUENCIAORIG` — Item original do pedido de compra
- `QTDATENDIDA` — Quantidade entregue nessa variacao
- Formula: `QTD_PENDENTE = TGFITE.QTDNEG - SUM(TGFVAR.QTDATENDIDA)`
- SEMPRE usar LEFT JOIN na TGFVAR (nem todo item tem entrega ainda)
- SEMPRE filtrar `STATUSNOTA <> 'C'` nas notas de variacao

### 11.7 STATUSCONFERENCIA — Valores
| Codigo | Significado | Linguagem do vendedor |
|--------|-------------|------------------------|
| AL | Aguardando liberacao p/ conferencia | "Ainda nao foi liberado pra conferencia" |
| AC | Aguardando conferencia | "Ta na fila de conferencia" |
| A | Em andamento | "Ta sendo conferido agora" |
| Z | Aguardando finalizacao | "Conferencia terminou, aguardando finalizacao" |
| F | Finalizada OK | "Conferencia OK! Pronto pra faturar" |
| D | Finalizada divergente | "Conferencia encontrou divergencia" |
| R | Aguardando recontagem | "Vai recontar" |
| RA | Recontagem em andamento | "Recontando agora" |
| RF | Recontagem finalizada OK | "Recontagem OK" |
| RD | Recontagem finalizada divergente | "Recontagem com divergencia" |
| C | Aguardando liberacao de corte | "Aguardando liberar corte (falta estoque)" |

**ATENCAO:** `Z` NAO e "zerada", e "aguardando finalizacao". `C` NAO e "cancelada", e "aguardando liberacao de corte".

### 11.8 SITUACAOWMS — Estado operacional WMS
| Codigo | Status |
|--------|--------|
| -1 | Nao enviado p/ separacao |
| 0 | Na fila de separacao |
| 1 | Enviado p/ separacao |
| 2 | Separando agora |
| 3 | Separado, aguardando conferencia |
| 4 | Sendo conferido |
| 7 | Pedido totalmente cortado |
| 8 | Pedido parcialmente cortado |
| 9 | Conferencia OK, pronto p/ faturar |
| 10 | Aguardando conferencia (pos-separacao) |
| 12 | Conferencia com divergencia |
| 13 | Parcialmente conferido |
| 16 | Concluido |
| 17 | Aguardando conferencia de volumes |
| 100 | Cancelado |

### 11.9 AD_TIPOSROTA — Tipo de expedicao/entrega
| Codigo | Significado |
|--------|-------------|
| EE | Entrega Carro |
| EM | Entrega Moto |
| EPR | Presencial (cliente retira) |
| TRAN | Transportadora |
| ERBAR | Entrega Regional Barueri |
| ERFR | Entrega Regional Franco da Rocha |
| ERIGA | Entrega Regional Itaquaquecetuba/Guarulhos |
| ERSERT | Entrega Regional Sertaozinho |

### 11.10 Vinculo Compra Casada — Como rastrear venda → compra → entrega

**Fluxo:**
```
Pedido Venda (TOP 1007, NUNOTA=5000)
  └─> Item: CODPROD=12345, QTD=10
        └─> Pedido Compra Casada (TOP 1313, NUNOTA=6000)
              └─> AD_NUNOTAVENDAEMP = 5000 (vinculo direto)
              └─> Item: CODPROD=12345, QTD=10
                    └─> TGFVAR: NUNOTAORIG=6000 → NUNOTA=7000 (nota de entrada)
```

**Campos de vinculo (TGFCAB):**
- `AD_NUNOTAVENDAEMP` — NUNOTA do pedido de venda que originou a compra casada
- `AD_NUNOTAMAE` — NUNOTA do pedido mae

**Query rastreamento (venda → compras casadas):**
```sql
SELECT COMPRA.NUNOTA AS PEDIDO_COMPRA, FORN.NOMEPARC AS FORNECEDOR,
       COMPRA.DTPREVENT AS PREVISAO, COMPRA.PENDENTE
FROM TGFCAB COMPRA
JOIN TGFPAR FORN ON COMPRA.CODPARC = FORN.CODPARC
WHERE COMPRA.AD_NUNOTAVENDAEMP = :nunota_venda
  AND COMPRA.TIPMOV = 'O'
  AND COMPRA.CODTIPOPER = 1313
  AND COMPRA.STATUSNOTA <> 'C'
```

---

## 12. SQL TEMPLATES — Estrutura atual

### 12.1 JOINS_PENDENCIA (linhas 1258-1275)

```sql
FROM TGFITE ITE
JOIN TGFCAB CAB ON CAB.NUNOTA = ITE.NUNOTA
JOIN TSIEMP EMP ON EMP.CODEMP = ITE.CODEMP
JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
LEFT JOIN TGFPAR PAR ON PAR.CODPARC = CAB.CODPARC
LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
LEFT JOIN TGFVEN VEN ON VEN.CODVEND = MAR.AD_CODVEND    -- Comprador da marca!
LEFT JOIN (
    SELECT V.NUNOTAORIG, V.SEQUENCIAORIG, SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
    FROM TGFVAR V JOIN TGFCAB C ON C.NUNOTA = V.NUNOTA WHERE C.STATUSNOTA <> 'C'
    GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
) V_AGG ON V_AGG.NUNOTAORIG = ITE.NUNOTA AND V_AGG.SEQUENCIAORIG = ITE.SEQUENCIA
```

### 12.2 WHERE_PENDENCIA (linhas 1277-1281)

```sql
CAB.CODTIPOPER IN (1301, 1313)     -- Pedidos de compra (revenda + casada)
AND CAB.STATUSNOTA <> 'C'          -- Nao cancelados
AND CAB.PENDENTE = 'S'             -- Ainda pendentes
AND ITE.PENDENTE = 'S'             -- Item pendente
AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0   -- Qtd restante > 0
```

---

## 13. PADROES OBRIGATORIOS PARA NOVOS HANDLERS

### 13.1 Checklist

Antes de finalizar qualquer handler novo, verificar:

- [ ] RBAC aplicado (via `_build_where_extra(params, user_context)` ou inline)
- [ ] Campo CODVEND correto (CAB.CODVEND para vendas, MAR.AD_CODVEND para compras)
- [ ] Nao junta TGFITE + TGFFIN no mesmo JOIN
- [ ] TOP N usa ROWNUM ou FETCH FIRST (Oracle), nao "TOP N" (SQL Server)
- [ ] Datas usam TO_DATE() ou TRUNC(SYSDATE)
- [ ] Usa DTNEG para filtros de periodo em vendas (nao DTFATUR)
- [ ] Aliases seguem o padrao (CAB, ITE, FIN, VEN, PAR, PRO, MAR, EMP)
- [ ] TIPMOV corretos: V=venda, P=pedido venda, O=pedido compra, C=entrada, D=devolucao venda
- [ ] Valores sanitizados via `_safe_sql()` antes de interpolacao
- [ ] Contexto salvo via `ctx.update(intent, params, result_data, question, view_mode)`
- [ ] result_data tem: `{detail_data, columns, description, params, intent}`
- [ ] Follow-up suportado (herda params do contexto)
- [ ] Narrador integrado (build_summary + llm_narrate)
- [ ] Excel export funciona (dados em list[dict])
- [ ] Keywords adicionadas no INTENT_SCORES com pesos adequados
- [ ] Threshold definido no INTENT_THRESHOLDS
- [ ] Exemplos adicionados no LLM_CLASSIFIER_PROMPT
- [ ] Testado com pelo menos 5 variacoes de pergunta
- [ ] Palavras novas do dominio adicionadas na noise list do extract_entities()

### 13.2 Padrao de retorno (OBRIGATORIO)

```python
return {
    "response": str,           # Texto markdown
    "tipo": str,               # "consulta_banco" | "info" | "arquivo" | "erro"
    "query_executed": str,     # SQL[:200] ou None
    "query_results": int,      # N rows ou None
    "time_ms": int,            # Milissegundos
    "_detail_data": list,      # Dados brutos (para follow-up/toggle/excel)
}
```

### 13.3 Padrao de nomenclatura

- Handler: `_handle_vendas`, `_handle_rastreio_pedido`, `_handle_financeiro`
- Summary builder: `build_vendas_summary`, `build_rastreio_summary`
- Format function: `format_vendas_response`, `format_estoque_response`
- SQL builder: `sql_pendencia_compras`

---

## 14. BUGS CONHECIDOS E ARMADILHAS

### 14.1 Entity extraction confunde termos
**Impacto:** "data de entrega da Donaldson" → marca="ENTREGA DA DONALDSON"
**Fix:** Noise list expandida (ja aplicada). Se encontrar novo caso, adicionar na noise list.

### 14.2 Groq confunde campos de data
**Impacto:** LLM retorna "DT_PEDIDO" quando deveria ser "PREVISAO_ENTREGA"
**Fix:** `_llm_to_filters()` com pos-processamento (ja implementado).

### 14.3 Follow-up de busca Elastic nao funciona
**Impacto:** "e o primeiro?" apos busca nao resolve
**Fix:** Salvar resultados Elastic no contexto (pendente).

### 14.4 Scoring pode conflitar entre intents
**Impacto:** Palavras compartilhadas (ex: "pedido") podem ativar o intent errado
**Prevencao:** Testar com 5+ variacoes, ajustar pesos se conflitar.

### 14.5 TGFITE x TGFFIN = multiplicacao de registros
**Impacto:** JOIN direto gera registros duplicados
**Fix:** Sempre usar subqueries quando precisar de dados de ambas.

### 14.6 TIPMOV de pedido de compra != C
**Impacto:** Se filtrar pedidos pendentes com TIPMOV=C nao encontra nada
**Correto:** Pedido de compra = TIPMOV='O' (TOP 1301/1313). TIPMOV='C' e nota de ENTRADA.

### 14.7 VLRNOTA vs ITE.VLRTOT ao filtrar por marca/produto
**Impacto:** Se a nota tem itens de varias marcas, VLRNOTA conta o total da nota pra cada marca
**Correto:** Usar ITE.VLRTOT quando filtrar por marca ou produto.

### 14.8 STATUSCONFERENCIA e SITUACAOWMS mal interpretados
**Impacto:** `Z` confundido com "zerada", `C` com "cancelada"
**Correto:** Z = aguardando finalizacao, C = aguardando liberacao de corte.

---

## 15. KNOWLEDGE BASE

### 15.1 Como funciona
- ~48 documentos markdown em `knowledge/`
- Indexados por TF-IDF (sklearn)
- Busca: pergunta → match com documentos → retorna top 3
- Usado quando intent = "conhecimento" ou fallback

### 15.2 Como adicionar novo conhecimento
1. Criar arquivo .md em `knowledge/{categoria}/`
2. Reiniciar o servidor (re-indexa automaticamente)
3. Testar com perguntas que deveriam achar o documento

---

## 16. FRONTEND — O que esperar

### 16.1 Tipos de resposta no chat
- **Texto simples:** Saudacao, ajuda, narracao
- **Tabela:** Dados tabulares com scroll horizontal + toggle de colunas
- **KPI cards:** Cards com numeros grandes
- **Tabela + KPI:** Combinacao (mais comum)
- **Excel link:** Link para download do arquivo gerado

### 16.2 Column toggles
O frontend permite ativar/desativar colunas via chips na mensagem. Usa `_detail_data` para re-renderizar a tabela client-side.

---

## 17. CONTEXTO DE NEGOCIO

### 17.1 Quem usa o Data Hub
- ~200 funcionarios da MMarra Distribuidora Automotiva
- Vendedores (maioria): perguntam sobre SEUS pedidos, SUAS vendas, pecas, estoque
- Compradores: pendencias de compra, previsao de entrega
- Gerentes: visao de equipe, KPIs
- Diretoria/Admin: visao geral, margens, financeiro

### 17.2 Como o vendedor pensa
O vendedor NAO pensa em modulos (vendas, compras, estoque). Ele pensa no PEDIDO dele:
- "A peca que o cliente pediu ja chegou?"
- "O fornecedor ja entregou?"
- "Ta na conferencia?"
- "Quando vai pro estoque?"

O Data Hub precisa cruzar vendas <> compras <> estoque <> conferencia numa unica resposta. O `_handle_rastreio_pedido` ja faz isso.

### 17.3 Vocabulario do usuario
O `glossario/sinonimos.md` mapeia termos do dia-a-dia para campos SQL:
- "faturamento" / "vendeu" / "faturou" → DTFATUR, VLRNOTA
- "pendencia" / "ta pra chegar" → pedidos com STATUSNOTA != 'L'
- "margem" / "lucro" → AD_MARGEM
- "comissao" → AD_VLRCOMINT, AD_ALIQCOMINT

---

## 18. REGRAS PARA O CLAUDE CODE

### 18.1 Antes de qualquer implementacao:
1. Leia CLAUDE.md e PROGRESSO_ATUAL.md
2. Leia ESTE prompt master
3. Identifique os arquivos que serao modificados
4. Confirme com o usuario ANTES de executar

### 18.2 Durante a implementacao:
1. NAO reescreva o smart_agent.py inteiro — altere APENAS o necessario
2. Mantenha a estrutura existente (aliases, patterns, nomenclatura)
3. Teste keywords de scoring — nunca adicione keywords que conflitem com intents existentes
4. Preserve o fluxo Layer 0 → 1 → 1.5 → 2 → 3
5. Aplique RBAC em TUDO que acessa dados
6. Use `_safe_sql()` em TODA interpolacao de valor em SQL

### 18.3 Depois de implementar:
1. Mostre um diff claro do que mudou
2. Liste as queries SQL novas para validacao manual
3. Sugira 5+ perguntas para testar
4. Documente em PROGRESSO_ATUAL.md

### 18.4 NUNCA faca isso:
- Nunca remova intents ou keywords existentes sem pedir confirmacao
- Nunca altere FILTER_RULES sem testar conflitos
- Nunca mude o fluxo principal de classificacao
- Nunca use TOP N (SQL Server syntax) — use ROWNUM ou FETCH FIRST
- Nunca junte TGFITE + TGFFIN no mesmo JOIN
- Nunca esqueca o RBAC
- Nunca hardcode marcas/empresas — use known_marcas do banco
- Nunca use TIPMOV=C para pedido de compra — TIPMOV=C e ENTRADA, pedido e TIPMOV=O
- Nunca use DTFATUR para filtros de vendas — use DTNEG (DTFATUR pode ser NULL)
- Nunca use VLRNOTA quando filtra por marca/produto — use ITE.VLRTOT
- Nunca confunda STATUSCONFERENCIA 'Z' com "zerada" ou 'C' com "cancelada"
- Nunca substitua o LLM_CLASSIFIER_PROMPT inteiro — apenas adicione exemplos/intents

---

## 19. PENDENCIAS E PROXIMO ROADMAP

### Pendentes:
- [ ] Testar rastreio_pedido no servidor real (conferencia, WMS, 3 etapas)
- [ ] Implementar `_handle_financeiro()` (contas pagar/receber, vencidos, fluxo caixa)
- [ ] Melhorar `_handle_vendas` com sub-queries (margem, comissao, marca, devolucoes, venda liquida)
- [ ] Fix follow-ups de busca Elastic (salvar resultados no contexto)
- [ ] Dashboard HTML
- [ ] Tela admin de apelidos no frontend

### Proximos dominios:
- Financeiro (contas pagar/receber, vencidos, fluxo de caixa)
- Comissao (comissao por vendedor, aliquotas)
- Metas (investigar TGFMET ou tabela customizada)

---

*Versao 5.0 — 2026-02-18 (Alinhada com smart_agent.py 4602 linhas, sessao 34)*
