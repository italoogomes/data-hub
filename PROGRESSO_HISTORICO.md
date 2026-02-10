# 📜 Historico de Sessoes - Data Hub

**Arquivo:** Historico completo de sessoes anteriores (1-25).
**Para estado atual:** Ver `PROGRESSO_ATUAL.md`

---

## SESSOES ANTERIORES

### 2026-02-09 (sessao 25) - Servidor 8080, Logo Transparente e ITE.PENDENTE

**Contexto:** Continuacao da sessao 24. Usuario retomou trabalho e tentou acessar servidor data-hub para testar conhecimento transferido.

**Problemas Resolvidos:**

1. **Porta do Servidor Errada**
   - Usuario tentou `localhost:8080` mas servidor configurado para porta 8000
   - **Solucao:** `start.py` alterado de `PORT = 8000` para `PORT = 8080`

2. **Logo com Fundo Preto**
   - Logo PNG base64 com fundo preto incorporado no HTML
   - **Solucao:**
     - Criada pasta `src/api/static/images/`
     - Usuario salvou `logo.png` (fundo transparente)
     - HTML atualizado: `src="imagens/logo.png"` (3 locais: header, welcome, messages)
     - CSS ajustado: `background: white`, `border-radius: 8px/12px`, `padding: 4px/8px`

3. **NUNOTA vs NUMNOTA na Query**
   - Query exemplo 22 mostrava ID interno (`NUNOTA` = 1185467) ao inves do numero visivel (`NUMNOTA` = 168)
   - **Solucao:** Nao precisou corrigir - exemplo ja estava correto com `NUMNOTA`
   - Usuario identificou erro na propria query copiada

**Descoberta CRITICA: ITE.PENDENTE = 'S'**

**Problema Identificado pelo Usuario:**
> "Quando eu corto um item do pedido e marco ele como nao pendente, ele continua aparecendo nessa consulta. Seria como se eu ligasse pro fornecedor e falasse: 'Eu nao vou mais precisar desse item, vc pode cancelar ele desse pedido'. Com essa consulta ele nunca vai sumir pq ele nunca vai chegar entende?"

**Causa Raiz:**
- Query calculava `QTD_PENDENTE = QTDNEG - TOTAL_ATENDIDO`
- Se item cancelado/cortado pelo usuario:
  - Nunca sera entregue (`TOTAL_ATENDIDO` sempre 0)
  - `QTD_PENDENTE` sempre > 0
  - Item aparece eternamente na consulta

**Solucao Implementada:**
```sql
WHERE ITE.PENDENTE = 'S'  -- CRITICO!
```

**Comportamento do Sankhya:**
- Quando usuario cancela/corta um item → `ITE.PENDENTE` muda de 'S' para 'N'
- Query filtra por `ITE.PENDENTE = 'S'` → Itens cancelados nao aparecem

**Diferenca entre campos PENDENTE:**
- `CAB.PENDENTE` = Pedido tem algum item pendente (nivel cabecalho, calculado pelo sistema)
- `ITE.PENDENTE` = Item especifico esta pendente (nivel item, controlado pelo usuario)

**Arquivos Atualizados:**

1. **start.py:** `PORT = 8080`
2. **src/api/static/index.html:** Logos: `src="imagens/logo.png"` (3 locais), CSS: background branco
3. **knowledge/sankhya/exemplos_sql.md:** Exemplos 19, 20, 22 atualizados com `ITE.PENDENTE = 'S'`
4. **Nova Regra Critica:** Secao "REGRA CRITICA: ITE.PENDENTE para itens cancelados/cortados"

**Aprendizados:**

| Campo | Significado | Quando Muda |
|-------|-------------|-------------|
| NUNOTA | ID unico interno (PK) | Nunca (chave primaria) |
| NUMNOTA | Numero pedido visivel | Numero sequencial por tipo |
| CAB.PENDENTE | Pedido tem pendencias | Sistema atualiza (soma ITE.PENDENTE) |
| ITE.PENDENTE | Item esta pendente | Usuario cancela/corta → 'N' |
| TGFVAR.QTDATENDIDA | Qtd entregue | A cada entrega parcial |

---

### 2026-02-09 (sessao 24) - Integracao com mmarra-data-hub-v2 + CODTIPOPER especificos

**Contexto:** Usuario esta usando o projeto `data-hub` (LLM chat com Ollama) separado do projeto principal `mmarra-data-hub-v2` (ETL + Azure + Agentes). Solicitou ajuda para melhorar acuracia das queries de compras.

**Problema identificado:** A LLM gerava queries genericas que nao usavam os filtros especificos da MMarra.

**Descobertas transferidas do mmarra-data-hub-v2:**

1. **CODTIPOPER especificos da MMarra:**
   - 1301 = Compra Casada (vinculada a venda, empenho)
   - 1313 = Entrega Futura (compra programada)
   - Mais preciso que `TIPMOV='O'` generico

2. **CODUSUCOMPRADOR:** Ja estava documentado (linha 99 TGFCAB.md)

3. **Query completa para pendencia de compra:**
   - Nivel ITEM (porque filtra marca)
   - TGFVAR agregado (pendencia real)
   - Comprador via TGFMAR.AD_CODVEND

**3 arquivos atualizados:**
- `knowledge/glossario/sinonimos.md` - CODTIPOPER especificos
- `knowledge/sankhya/exemplos_sql.md` - Exemplo 22 completo
- `knowledge/sankhya/tabelas/TGFCAB.md` - Verificado OK

**Nota tecnica:** Esta sessao demonstra a importancia de manter dois projetos sincronizados. O `mmarra-data-hub-v2` tem o mapeamento mais completo, enquanto o `data-hub` usa esse conhecimento para treinar a LLM.

---

### 2026-02-07 (sessao 23) - Correcao PENDENTE='S' + TIPMOV='O' + fix_pendencia_sql

**Problema resolvido:** Duas correcoes criticas na geracao de SQL para pendencia de compra.

**Correcao 1 - PENDENTE='S' em vez de STATUSNOTA='P':**
- STATUSNOTA eh o estado da NOTA (A=Atendimento, P=Pendente aprovacao, L=Liberada, C=Cancelada)
- PENDENTE (S/N) eh o campo que indica se falta receber itens
- "pedidos pendentes" = `PENDENTE = 'S'`, NUNCA `STATUSNOTA = 'P'`

**Correcao 2 - TIPMOV='O' em vez de TIPMOV IN ('C','O'):**
- TIPMOV='O' = Pedido de compra (pode estar pendente)
- TIPMOV='C' = Nota de compra (entrada ja efetivada)

**Correcao 3 - fix_pendencia_sql() (pos-processamento):**
- Modelo 8B frequentemente ignora regras no prompt (contexto muito longo ~53k chars)
- Funcao Python que corrige SQL APOS geracao

**8 arquivos corrigidos retroativamente:**
1. `src/llm/agent.py` - Regras reescritas, fix_pendencia_sql()
2. `knowledge/sankhya/erros_sql.md` - Erros 17-22 atualizados
3. `knowledge/glossario/sinonimos.md` - Desambiguacao
4. `knowledge/sankhya/exemplos_sql.md` - Exemplos 3, 13, 14, 19, 20, 21
5. `knowledge/sankhya/relacionamentos.md` - Regras de Pendencia
6. `knowledge/processos/compras/fluxo_compra.md` - 3 queries + fluxo entrega
7. `knowledge/sankhya/tabelas/TGFCAB.md` - PENDENTE como campo critico
8. `knowledge/processos/compras/rotina_comprador.md`

**Resultados: 4/4 PENDENTE/TIPMOV corretos**

---

### 2026-02-07 (sessao 22) - Regra Cabecalho vs Item + NVL tipo DATE

**Regra fundamental introduzida:**

| Pergunta menciona | Nivel da query | FROM principal | Valor |
|---|---|---|---|
| MARCA ou PRODUTO | ITEM | TGFITE ITE JOIN TGFCAB CAB | ITE.VLRTOT |
| Nada especifico | CABECALHO | TGFCAB C | VLRNOTA (confiavel) |

**6 arquivos atualizados** com regras de nivel CABECALHO vs ITEM e fix NVL DATE.

**Resultados: 4/4 PASS** (apos fix NVL)

---

### 2026-02-07 (sessao 21) - Correcao de 5 problemas na geracao SQL

**5 erros corrigidos:**

| # | Erro | Correcao |
|---|------|----------|
| 1 | Case sensitivity | `UPPER(M.DESCRICAO) = UPPER('Donaldson')` |
| 2 | IS NOT NULL desnecessario | Removido filtro, NVL para tratar NULL |
| 3 | STATUSNOTA = 'P' restritivo | `STATUSNOTA <> 'C'` (tudo menos cancelado) |
| 4 | JOIN multiplica linhas | EXISTS subquery |
| 5 | TIPMOV = 'C' incompleto | `TIPMOV IN ('C','O')` |

**Resultados: 3/3 PASS**

---

### 2026-02-07 (sessao 20) - Correcao CASE...END no Query Executor

- Removido `"END"` da lista `FORBIDDEN_KEYWORDS` em query_executor.py
- `BEGIN` permanece na lista (bloqueia PL/SQL)
- `CASE WHEN...END` eh SQL padrao e seguro

**Resultados: 5/5 PASS**

---

### 2026-02-07 (sessao 19) - Previsao de Entrega, TGFMAR e TGFVAR

**Tabelas investigadas e documentadas:**
1. **TGFMAR** (Marcas) - 1.441 registros
2. **TGFVAR** (Variacoes/Atendimentos) - 28.171 registros

**Descobertas:**
- TGFCAB.DTPREVENT = previsao de entrega
- TGFPRO.CODMARCA = FK para TGFMAR.CODIGO
- TGFVAR formula: QTD_PENDENTE = TGFITE.QTDNEG - SUM(TGFVAR.QTDATENDIDA)

**8 arquivos atualizados.** Resultados: 5/5 (100%)

---

### 2026-02-07 (sessao 18) - Extracao do Dicionario de Dados (TDD*)

**13 tabelas documentadas automaticamente** a partir do dicionario interno do Sankhya (tabelas TDD*).

**Correcoes importantes descobertas:**
1. **STATUSNOTA 'A'** = "Atendimento" (NAO "Aberto")
2. **TIPMOV** tem 23 valores (tinhamos documentado apenas 7)
3. **TIPLIBERACAO** mapeado: S/P/A/R
4. **TGFEST.TIPO**: P=Proprio, T=Terceiro
5. **AD_TIPOSROTA**: 10 rotas de expedicao MMarra

---

### 2026-02-07 (sessao 17) - Desambiguacao de Pendencia (3 tipos)

**3 tipos de pendencia documentados:**
1. **Pendencia de COMPRA** (padrao): STATUSNOTA='P', TIPMOV IN ('C','O')
2. **Pendencia FINANCEIRA**: DHBAIXA IS NULL, RECDESP=-1
3. **Pendencia de VENDA**: STATUSNOTA='P', TIPMOV IN ('V','P')

**Regra:** "pendencia" sem especificar = COMPRA (sem TGFFIN).

**Resultados: 4/4 (100%)**

---

### 2026-02-07 (sessao 16) - Correcao de Padroes SQL (Multiplicacao + ROWNUM)

- Problema: JOIN TGFFIN + TGFITE multiplica valores
- `fix_rownum_syntax()` implementada (detecta e corrige ORDER BY + ROWNUM)
- **Resultados: 3/4 (75%)**

---

### 2026-02-07 (sessao 15) - Base de Conhecimento SQL Obrigatoria

**4 arquivos criados e integrados ao agente:**
1. `knowledge/sankhya/exemplos_sql.md` (12 exemplos validados)
2. `knowledge/glossario/sinonimos.md`
3. `knowledge/sankhya/erros_sql.md` (10 erros)
4. `knowledge/processos/compras/rotina_comprador.md`

**Resultados: 4/4 (100%)** - LLM copia padroes dos exemplos validados!

---

### 2026-02-07 (sessao 14) - Migracao para Qwen3:8b

**Troca: llama3.1:8b -> qwen3:8b**
- strip_thinking() para tags `<think>` do Qwen3
- Remocao automatica de FETCH FIRST
- **Resultados: 4/4 (100%)**

---

### 2026-02-07 (sessao 13) - Relacionamentos + Auto-correcao SQL + ngrok

- `knowledge/sankhya/relacionamentos.md` com todos os JOINs
- Agent.py reescrito com referencia SQL condensada
- Auto-correcao de SQL (detecta ORA-*, chama LLM para fix)
- `start.py` com ngrok integrado
- **Resultados: 3/5 (60%)**

---

### 2026-02-06 (sessao 12) - Acesso Remoto via ngrok

- Script `start.py` na raiz
- CORS habilitado
- .env corrigido Groq → Ollama

---

### 2026-02-06 (sessao 11) - Correcao de Classificacao para Modelo 8B

- Prompts simplificados em 3 etapas (CLASSIFIER → SQL_GENERATOR → FORMATTER)
- Modelo 8B nao gerava JSON complexo → simplificado para "BANCO" ou "DOC"

---

### 2026-02-06 (sessao 10) - Migracao para Ollama (LLM local)

- **Groq → Ollama** (sem rate limit, sem custo, dados na rede interna)
- llama3.1:8b (4.9GB) local
- FORMATTER_PROMPT melhorado

---

### 2026-02-06 (sessao 9) - LLM + Agente com acesso ao banco

- `src/llm/chat.py` - Chat CLI com RAG
- `src/llm/query_executor.py` - Executor seguro (SELECT only, ROWNUM <= 500)
- `src/llm/agent.py` - Agente decide DOC vs SQL
- `src/api/app.py` - API FastAPI
- `src/api/static/index.html` - Frontend

---

### 2026-02-06 (sessao 8) - Partes 1-6

**Parte 6:** DataHubAgent com classificacao + execucao SQL
**Parte 5:** SafeQueryExecutor (14 testes passando)
**Parte 4:** LLM Chat + Interface Web (RAG com TF-IDF + Groq)
**Parte 3:** Regras de Negocio (aprovacao, solicitacao, cotacao, custos, codigos auxiliares)
**Parte 2:** Mapeamento das 142 tabelas AD_* (95 com dados, 47 vazias)
**Parte 1:** Mapeamento compras (TGFLIB vazia, TGFCOT 2839, Solicitacao via TIPMOV='J')

---

### 2026-02-05 (sessao 7) - Aprofundamento Compras

- TGFEST documentada (36.769 posicoes)
- TGFFIN documentada (54.441 titulos)
- fluxo_compra.md com status e transicoes

---

### 2026-02-05 (sessao 6) - Queries SQL

- 15 arquivos SQL criados em /queries/ (vendas, compras, estoque, financeiro)

---

### 2026-02-05 (sessao 5) - Processos de Negocio

- Fluxo de Venda, Compra, Devolucao, Transferencia documentados

---

### 2026-02-05 (sessao 4) - TSIEMP + TGFVEN

- 10 empresas/filiais documentadas
- 111 vendedores (86 vendedores, 20 compradores, 4 gerentes)

---

### 2026-02-05 (sessao 3) - TGFPAR + TGFPRO + TGFTOP

- 57k parceiros, 394k produtos, 1.3k tipos de operacao documentados

---

### 2026-02-05 (sessao 2) - MCP Server

- MCP Server configurado, OAuth 2.0 funcionando
- Descoberta: banco eh Oracle (nao SQL Server)

---

### 2026-02-05 (sessao 1) - Inicio do Projeto

- Projeto iniciado do zero (v3)
- Estrutura preparada para repositorio de dados inteligente
- CLAUDE.md criado

---

*Este arquivo contem o historico de sessoes 1-25.*
*Para estado atual, ver `PROGRESSO_ATUAL.md`.*
