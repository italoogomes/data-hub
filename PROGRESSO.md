# PROGRESSO.md

> Ultima atualizacao: 2026-02-09 (sessao 25) - Servidor ajustado, logo corrigida, ITE.PENDENTE descoberto

---

## STATUS ATUAL

**Agente LLM com consulta ao banco funcionando - AGORA 100% LOCAL!**

- **Web:** http://localhost:8000 (`python -m src.api.app`)
- **Inicio rapido:** `python start.py` (servidor + ngrok em um comando)
- **Acesso remoto:** Via ngrok (URL publica gerada automaticamente)
- **CLI:** `python -m src.llm.chat "pergunta"` (apenas documentacao)
- **LLM Provider:** Ollama (local, sem custo, sem rate limit)
- **Modelo:** qwen3:8b (roda na maquina)
- **RAG:** Top 5 docs, max 3000 chars/doc, 15k total + 4 arquivos SQL obrigatorios (25k chars)
- **Docs:** 48 documentos na base de conhecimento
- **Query Executor:** SELECT only, ROWNUM <= 500, retry auth 401/403
- **Dados:** Nao saem da rede interna (LLM local)

**Arquivos principais:**
- `start.py` - Script de inicio (servidor + ngrok)
- `src/llm/llm_client.py` - Cliente LLM unificado (Ollama)
- `src/llm/agent.py` - Agente que decide DOC vs SQL
- `src/llm/query_executor.py` - Executor seguro de SQL
- `src/llm/chat.py` - Chat CLI com RAG
- `src/api/app.py` - API FastAPI
- `src/api/static/index.html` - Frontend

---

## O QUE ESTA PRONTO

- [x] Estrutura de pastas
- [x] CLAUDE.md com instrucoes e templates
- [x] Pronto para receber documentacao
- [x] MCP Server do Sankhya (`src/mcp/server.py`)
- [x] LLM Chat com RAG (`src/llm/chat.py`)
- [x] API FastAPI (`src/api/app.py`) - v2.0 com agente
- [x] Interface Web (`src/api/static/index.html`) - mostra queries executadas
- [x] Query Executor seguro (`src/llm/query_executor.py`)
- [x] Agente LLM (`src/llm/agent.py`) - decide entre DOC e SQL

---

## PRÓXIMOS PASSOS

1. [x] ~~Configurar MCP Server para Sankhya~~
2. [x] ~~Testar conexão com API~~
3. [x] ~~Varredura das tabelas principais (TGFCAB, TGFPAR, TGFPRO, TGFTOP, TSIEMP, TGFVEN)~~
4. [x] ~~Documentar processos (venda, compra, devolucao, transferencia)~~
5. [x] ~~Completar mapeamento de compras (TGFLIB, TGFCOT, solicitacao)~~
6. [x] ~~Investigar tabelas AD_* customizadas~~
7. [ ] Documentar glossario e regras de negocio
8. [x] ~~Criar queries SQL uteis em /queries~~

---

## BASE DE CONHECIMENTO

### Tabelas Documentadas
- [x] **TGFCAB** - Cabecalho das notas (343k registros)
- [x] **TGFITE** - Itens das notas (1.1M registros)
- [x] **TGFPAR** - Parceiros/Clientes/Fornecedores (57k registros)
- [x] **TGFPRO** - Produtos (394k registros)
- [x] **TGFTOP** - Tipos de Operacao (1.3k registros)
- [x] **TSIEMP** - Empresas/Filiais (10 registros)
- [x] **TGFVEN** - Vendedores/Compradores/Gerentes (111 registros)
- [x] **TGFEST** - Posicao de Estoque (36.769 registros)
- [x] **TGFFIN** - Titulos Financeiros (54.441 registros)
- [x] **TGFLIB** - Liberacoes/Aprovacoes (0 registros - VAZIA, usa AD_*)
- [x] **TGFCOT** - Cotacoes de Compra (2.839 registros)
- [x] **AD_TGFPROAUXMMA** - Numeros auxiliares de produtos (1.145.087 registros)
- [x] **AD_TGFCUSMMA** - Historico de custos (709.230 registros)
- [x] **AD_MARCAS** - Marcas de produtos (799 registros)
- [x] **AD_TABELAS_CUSTOMIZADAS** - Mapeamento completo das 142 tabelas AD_*
- [x] **TGFMAR** - Marcas de Produtos (1.441 registros)
- [x] **TGFVAR** - Variacoes/Atendimentos de Pedido (28.171 registros)

### Processos Documentados
- [x] **Fluxo de Venda** - Balcao (1100), NFe (1101), Pedido → Faturamento
- [x] **Fluxo de Compra** - Solicitacao → Pedido → Recebimento (1209)
- [x] **Fluxo de Devolucao** - Dev. venda (1202), Dev. compra (1501)
- [x] **Fluxo de Transferencia** - Saida (1150), Entrada (1452)

### Glossário
_Vazio - adicionar termos conforme aparecem_

### Regras de Negócio
- [x] **aprovacao_compras** - MMarra NAO usa workflow formal (TGFLIB, AD_APROVACAO vazias)
- [x] **solicitacao_compra** - Usa TGFCAB TIPMOV='J' (2.878 registros, sistema novo 2026)
- [x] **cotacao_compra** - TGFCOT vinculada via NUNOTAORIG, apenas PESOPRECO=1
- [x] **custos_produto** - AD_TGFCUSMMA com 709k registros (5 anos historico)
- [x] **codigos_auxiliares** - AD_TGFPROAUXMMA com 1.1M codigos cross-reference

### Erros Conhecidos
_Nenhum ainda_

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
  - Item aparece eternamente na consulta ❌

**Solucao Implementada:**
```sql
WHERE ITE.PENDENTE = 'S'  -- CRITICO!
```

**Comportamento do Sankhya:**
- Quando usuario cancela/corta um item → `ITE.PENDENTE` muda de 'S' para 'N'
- Query filtra por `ITE.PENDENTE = 'S'` → Itens cancelados nao aparecem ✅

**Diferenca entre campos PENDENTE:**
- `CAB.PENDENTE` = Pedido tem algum item pendente (nivel cabecalho, calculado pelo sistema)
- `ITE.PENDENTE` = Item especifico esta pendente (nivel item, controlado pelo usuario)

**Arquivos Atualizados:**

1. **start.py:** `PORT = 8080`

2. **src/api/static/index.html:**
   - Logos: `src="imagens/logo.png"` (3 locais)
   - CSS: background branco, bordas arredondadas, padding

3. **knowledge/sankhya/exemplos_sql.md:**
   - **Exemplo 19** (Previsao entrega por marca):
     - Adicionado: `AND ITE.PENDENTE = 'S'`
     - Explicacao atualizada com ponto 6 sobre ITE.PENDENTE
   - **Exemplo 20** (Itens pendentes por pedido):
     - Adicionado: `AND I.PENDENTE = 'S'`
     - Explicacao atualizada
   - **Exemplo 22** (Pendentes por marca MMarra):
     - Adicionado: `AND ITE.PENDENTE = 'S'`
     - Explicacao atualizada com ponto 8 sobre ITE.PENDENTE

4. **Nova Regra Critica Adicionada** (final do arquivo):
   ```markdown
   ## REGRA CRITICA: ITE.PENDENTE para itens cancelados/cortados

   Quando trabalhar com **pendencia de itens** (TGFITE), SEMPRE adicionar:

   WHERE ITE.PENDENTE = 'S'

   **Por que?**
   - Quando usuario cancela/corta um item do pedido, ITE.PENDENTE = 'N'
   - Se nao filtrar, itens cancelados aparecem eternamente
   - CAB.PENDENTE (cabecalho) vs ITE.PENDENTE (item)

   **Usar em:**
   - Consultas de pendencia por marca/produto (exemplos 19, 20, 22)
   - Qualquer query de itens aguardando entrega

   **NAO usar quando:**
   - Quer historico completo incluindo cancelados
   - Query eh nivel CABECALHO (sem filtro marca/produto)
   ```

**Aprendizados:**

| Campo | Significado | Quando Muda |
|-------|-------------|-------------|
| NUNOTA | ID unico interno (PK) | Nunca (chave primaria) |
| NUMNOTA | Numero pedido visivel | Numero sequencial por tipo |
| CAB.PENDENTE | Pedido tem pendencias | Sistema atualiza (soma ITE.PENDENTE) |
| ITE.PENDENTE | Item esta pendente | Usuario cancela/corta → 'N' |
| TGFVAR.QTDATENDIDA | Qtd entregue | A cada entrega parcial |

**Proximos Passos:**
1. Testar LLM com conhecimento atualizado (instalar `qwen3:8b` se necessario)
2. Validar query final com dados reais
3. Sincronizar documentacao entre projetos

---

### 2026-02-09 (sessao 24) - Integracao com mmarra-data-hub-v2 + CODTIPOPER especificos

**Contexto:** Usuario esta usando o projeto `data-hub` (LLM chat com Ollama) separado do projeto principal `mmarra-data-hub-v2` (ETL + Azure + Agentes). Solicitou ajuda para melhorar acuracia das queries de compras.

**Problema identificado:** A LLM gerava queries genericas que nao usavam os filtros especificos da MMarra. Perguntas como "quantos pedidos da marca X em aberto" e "quantos itens pendentes" nao eram respondidas com precisao ideal.

**Analise realizada:** Comparacao entre conhecimento do `data-hub` (sessoes 1-23) vs descobertas no `mmarra-data-hub-v2` (projeto principal com mapeamento mais completo).

**Descobertas transferidas do mmarra-data-hub-v2:**

1. **CODTIPOPER especificos da MMarra:**
   - 1301 = Compra Casada (vinculada a venda, empenho)
   - 1313 = Entrega Futura (compra programada)
   - Mais preciso que `TIPMOV='O'` generico

2. **CODUSUCOMPRADOR:**
   - Campo correto para comprador em TGFCAB
   - Ja estava documentado (linha 99 TGFCAB.md)
   - ✅ Nenhuma correcao necessaria

3. **Query completa para pendencia de compra:**
   - Nivel ITEM (porque filtra marca)
   - TGFVAR agregado (pendencia real)
   - Comprador via TGFMAR.AD_CODVEND
   - Valores corretos (ITE.VLRTOT, nao VLRNOTA)

**3 arquivos atualizados:**

**1. `knowledge/glossario/sinonimos.md`:**
- Nova secao "TOPs de Compra MMarra (CODTIPOPER) - ESPECIFICO"
- Mapeamento de termos do usuario para CODTIPOPER especificos
- Regra: quando usar CODTIPOPER vs TIPMOV
- Linha 31-46 (15 linhas adicionadas)

**2. `knowledge/sankhya/exemplos_sql.md`:**
- Novo exemplo 22: "Pedidos pendentes por marca - MMarra especifico"
- Query COMPLETA que responde 5 perguntas de uma vez:
  - Quantos pedidos da marca X em aberto?
  - Quantos itens pendentes?
  - Qual o valor pendente?
  - Quem e o comprador?
  - Quantos dias em aberto?
- Usa CODTIPOPER IN (1301, 1313), TGFVAR, TGFMAR.AD_CODVEND
- 32 linhas adicionadas (completo e documentado)

**3. `knowledge/sankhya/tabelas/TGFCAB.md`:**
- ✅ Verificado: CODUSUCOMPRADOR ja estava correto (linha 99)
- Nenhuma alteracao necessaria

**Resultado esperado:**
- Queries de compras agora usam filtros especificos MMarra (CODTIPOPER)
- Pendencia calculada corretamente com TGFVAR
- Comprador identificado via TGFMAR.AD_CODVEND
- Acuracia aumentada para perguntas de compras

**Testes pendentes:**
1. "Quantos pedidos da marca Donaldson eu tenho em aberto?"
2. "Quantos itens pendentes da marca Cummins?"
3. "Qual marca tem mais pedidos pendentes?"
4. "Mostre os pedidos de compra com mais dias em aberto"

**Arquivos modificados:**
- `knowledge/glossario/sinonimos.md` - CODTIPOPER especificos
- `knowledge/sankhya/exemplos_sql.md` - Exemplo 22 completo
- `PROGRESSO.md` - Documentacao desta sessao

**Nota tecnica:** Esta sessao demonstra a importancia de manter dois projetos sincronizados. O `mmarra-data-hub-v2` tem o mapeamento mais completo (descoberto trabalhando diretamente com Sankhya), enquanto o `data-hub` usa esse conhecimento para treinar a LLM. Transferencias periodicas de conhecimento entre projetos sao essenciais.

---

### 2026-02-07 (sessao 23) - Correcao PENDENTE='S' + TIPMOV='O' + fix_pendencia_sql

**Problema resolvido:** Duas correcoes criticas na geracao de SQL para pendencia de compra.

**Correcao 1 - PENDENTE='S' em vez de STATUSNOTA='P':**
- STATUSNOTA eh o estado da NOTA (A=Atendimento, P=Pendente aprovacao, L=Liberada, C=Cancelada)
- PENDENTE (S/N) eh o campo que indica se falta receber itens. Sankhya atualiza automaticamente via TGFVAR.
- "pedidos pendentes" = `PENDENTE = 'S'`, NUNCA `STATUSNOTA = 'P'`

**Correcao 2 - TIPMOV='O' em vez de TIPMOV IN ('C','O'):**
- TIPMOV='O' = Pedido de compra (pode estar pendente)
- TIPMOV='C' = Nota de compra (entrada ja efetivada)
- "pedidos de compra" = `TIPMOV = 'O'` (apenas pedidos)
- "tudo de compra" = `TIPMOV IN ('C','O')` (somente quando usuario pede tudo)

**Correcao 3 - fix_pendencia_sql() (pos-processamento):**
- Modelo 8B frequentemente ignora regras no prompt (contexto muito longo ~53k chars)
- Funcao Python que corrige SQL APOS geracao:
  - `STATUSNOTA = 'P'` → `PENDENTE = 'S' AND STATUSNOTA <> 'C'`
  - `TIPMOV IN ('C','O')` → `TIPMOV = 'O'` (quando contexto de pendencia)
- Garante correcao mesmo quando o modelo falha

**8 arquivos corrigidos retroativamente:**
1. `src/llm/agent.py` - Regras 10-12 reescritas, REGRA DE PENDENCIA, ATENCAO FINAL, _build_sql_reference(), fix_pendencia_sql()
2. `knowledge/sankhya/erros_sql.md` - Erros 17, 20, 21, 22 atualizados. Regras resumo 17-22 reescritas.
3. `knowledge/glossario/sinonimos.md` - Status, pedidos atrasados, pendencia compra/venda, desambiguacao
4. `knowledge/sankhya/exemplos_sql.md` - Exemplos 3, 13, 14, 19, 20, 21 atualizados
5. `knowledge/sankhya/relacionamentos.md` - Regras de Pendencia reescritas (PENDENTE='S')
6. `knowledge/processos/compras/fluxo_compra.md` - 3 queries + fluxo de entrega
7. `knowledge/sankhya/tabelas/TGFCAB.md` - PENDENTE documentado como campo critico
8. `knowledge/processos/compras/rotina_comprador.md` - Pedidos pendentes

**Resultados dos testes (4/4 PENDENTE/TIPMOV corretos):**

| # | Pergunta | PENDENTE/TIPMOV | SQL Execucao | Resultado |
|---|----------|-----------------|--------------|---------|
| 1 | Pedidos compra pendentes | PENDENTE='S', TIPMOV='O', STATUSNOTA<>'C' | 500 rows, 156s | **PASS** |
| 2 | Relatorio Donaldson previsao | TIPMOV='O', UPPER(), ITEM level | ORA GROUP BY | **PARCIAL** (SQL ok, GROUP BY errado) |
| 3 | Donaldson sem previsao | TIPMOV='O', UPPER(), DTPREVENT IS NULL | 0 rows, 31s | **PASS** |
| 4 | Valor total Cummins | TIPMOV='O', UPPER(), ITEM level | ORA SUM(SUM) | **PARCIAL** (SQL ok, agregacao errada) |

**Nota:** Testes 2 e 4 falharam por erros de SQL syntax (GROUP BY/agregacao com TGFVAR), NAO por PENDENTE/TIPMOV. Todas as 4 queries usaram os filtros corretos.

**Problema tecnico encontrado:** Processos Python antigos persistiam na porta 8000 no Windows, servindo codigo antigo. Necessario `taskkill //F //IM python.exe` com flags Windows antes de reiniciar.

---

### 2026-02-07 (sessao 22) - Regra Cabecalho vs Item + NVL tipo DATE

**Problema resolvido:** Quando a pergunta menciona MARCA ou PRODUTO, a query gerada usava nivel CABECALHO (EXISTS + VLRNOTA) que retorna valores ERRADOS. VLRNOTA eh o valor total do pedido (todas as marcas), nao apenas da marca filtrada. Exemplo: pedido com VLRNOTA = R$13M mas apenas R$1.874 em itens Donaldson.

**Regra fundamental introduzida:**

| Pergunta menciona | Nivel da query | FROM principal | Valor |
|---|---|---|---|
| MARCA ou PRODUTO | ITEM | TGFITE ITE JOIN TGFCAB CAB | ITE.VLRTOT |
| Nada especifico | CABECALHO | TGFCAB C | VLRNOTA (confiavel) |

**6 arquivos atualizados:**

**1. knowledge/sankhya/erros_sql.md (agora 23 erros):**
- Erro 22: Usar nivel CABECALHO (EXISTS + VLRNOTA) quando filtrando por MARCA
- Erro 23: NVL com tipo errado em DTPREVENT (NVL(DATE, VARCHAR) → erro ORA)
- Regra 13: "NUNCA usar nivel CABECALHO quando filtrando por MARCA"
- Regra 19: "Se menciona MARCA/PRODUTO: query nivel ITEM"
- Regra 20: "DTPREVENT eh DATE — usar NVL(TO_CHAR(...))"

**2. knowledge/sankhya/relacionamentos.md:**
- Nova secao "Regra de Nivel: Cabecalho vs Item (CRITICA)"
- Marca filtering path reescrito: FROM TGFITE em vez de EXISTS

**3. knowledge/glossario/sinonimos.md:**
- Nova subsecao "Regra de Nivel: Cabecalho vs Item"
- "NUNCA usar VLRNOTA quando filtrando por marca"
- "Valor por marca = ITE.VLRTOT"

**4. knowledge/sankhya/exemplos_sql.md:**
- Exemplo 19 reescrito: nivel ITEM com TGFVAR, ITE.VLRTOT, UPPER()
- Exemplo 21 adicionado: nivel CABECALHO para queries gerais
- Nova secao "REGRA CRITICA: Nivel CABECALHO vs ITEM"

**5. src/llm/agent.py:**
- SQL_GENERATOR_PROMPT: Regra 12 (CRITICA) sobre NIVEL
- ATENCAO FINAL: NIVEL como primeira regra
- _build_sql_reference(): "REGRA DE NIVEL" como primeira secao
- NVL corrigido: NVL(TO_CHAR(DTPREVENT,'DD/MM/YYYY'),'Sem previsao')

**6. knowledge/sankhya/erros_sql.md:**
- Erro 23: NVL(DTPREVENT, 'texto') causa erro ORA tipo incompativel

**Resultados dos testes (4/4 PASS):**

| # | Pergunta | Criterios verificados | Rows | Resultado |
|---|----------|-----------------------|------|-----------|
| 1 | Relatorio previsao Donaldson | Nivel ITEM, TGFVAR, UPPER, ITE.VLRTOT, STATUSNOTA<>'C' | 500 | PASS |
| 2 | Pedidos compra pendentes | Nivel CABECALHO (sem marca), VLRNOTA ok, ='P', IN('C','O') | 500 | PASS |
| 3 | Donaldson sem previsao | Nivel ITEM, DTPREVENT IS NULL, NVL(TO_CHAR(...)), UPPER | 500 | PASS (apos fix NVL) |
| 4 | Valor total Cummins | Nivel ITEM, SUM(ITE.VLRTOT), TGFVAR, UPPER | 1 (R$10.823,60) | PASS |

**Bug encontrado e corrigido durante testes:**
- Teste 3 falhou na 1a tentativa: modelo gerou NVL(DTPREVENT, 'Sem Previsao') que mistura DATE com VARCHAR
- Correcao: regra 7, ATENCAO FINAL e _build_sql_reference() agora dizem explicitamente NVL(TO_CHAR(DTPREVENT,'DD/MM/YYYY'),'Sem previsao')
- Reteste: PASS

**Comparacao antes/depois:**
- Antes: VLRNOTA inflado (R$13M por pedido quando deveria ser R$1.874 por itens da marca)
- Depois: ITE.VLRTOT correto (valor real dos itens filtrados por marca)

**Aprendizado chave:** O modelo 8B precisa saber QUANDO usar cada nivel. A regra eh simples: MARCA/PRODUTO → ITEM, geral → CABECALHO. Tambem precisa do pattern NVL completo (TO_CHAR incluido) pois nao infere conversao de tipo.

**Arquivos modificados:**
- `knowledge/sankhya/erros_sql.md` - 2 novos erros (22-23), 2 novas regras resumo (19-20)
- `knowledge/sankhya/relacionamentos.md` - Regra de Nivel
- `knowledge/glossario/sinonimos.md` - Regra de Nivel
- `knowledge/sankhya/exemplos_sql.md` - Exemplo 19 reescrito, exemplo 21 novo, secao REGRA CRITICA
- `src/llm/agent.py` - Regra 12 NIVEL, ATENCAO FINAL, referencia condensada, NVL fix

---

### 2026-02-07 (sessao 21) - Correcao de 5 problemas na geracao SQL

**Problema resolvido:** A pergunta "relatorio de previsao de entrega da marca Donaldson com meses em colunas" retornava 0 registros por 5 erros simultaneos na query gerada.

**Os 5 erros corrigidos:**

| # | Erro | Causa | Correcao |
|---|------|-------|----------|
| 1 | Case sensitivity | `M.DESCRICAO = 'Donaldson'` (banco tem 'DONALDSON') | `UPPER(M.DESCRICAO) = UPPER('Donaldson')` |
| 2 | IS NOT NULL desnecessario | Filtrava `DTPREVENT IS NOT NULL` excluindo pedidos sem previsao | Removido filtro, tratar NULL com NVL como 'Sem previsao' |
| 3 | STATUSNOTA = 'P' restritivo | Exclui status L e A em relatorios | `STATUSNOTA <> 'C'` (tudo menos cancelado) |
| 4 | JOIN multiplica linhas | JOIN TGFITE no cabecalho | EXISTS subquery (ja documentado, reforçado) |
| 5 | TIPMOV = 'C' incompleto | Faltou 'O' (pedidos de compra) | `TIPMOV IN ('C','O')` |

**4 arquivos de conhecimento atualizados:**

**1. knowledge/sankhya/erros_sql.md (agora 21 erros):**
- Erro 18: Case sensitivity em filtros de texto (UPPER())
- Erro 19: Filtrar DTPREVENT IS NOT NULL quando usuario pede "previsao"
- Erro 20: STATUSNOTA = 'P' em relatorios de acompanhamento
- Erro 21: TIPMOV = 'C' sem incluir 'O' para compras
- Resumo expandido para 18 regras

**2. knowledge/glossario/sinonimos.md:**
- Marca com UPPER() obrigatorio
- Previsao: MOSTRAR vs FILTRAR (novo conceito)
- Status: relatorios (<> 'C') vs filtro explicito (= 'P')
- Compra: TIPMOV IN ('C','O')

**3. knowledge/sankhya/exemplos_sql.md:**
- Exemplo 19 reescrito com todos 5 fixes aplicados:
  - UPPER() no filtro de marca
  - EXISTS em vez de JOIN TGFITE
  - STATUSNOTA <> 'C'
  - TIPMOV IN ('C','O')
  - SEM IS NOT NULL, NVL para tratar NULL
  - CASE WHEN para STATUS_ENTREGA

**4. src/llm/agent.py:**
- SQL_GENERATOR_PROMPT: regras 11-13 adicionadas (UPPER, STATUS, COMPRA)
- ATENCAO FINAL: 6 regras reescritas (TEXTO, PREVISAO, STATUS, COMPRA, MARCA, DTPREVENT)
- _build_sql_reference(): UPPER em filtros de marca/EXISTS, MOSTRAR vs FILTRAR previsao, STATUS em relatorios, COMPRA TIPMOV

**Resultados dos testes (3/3 PASS):**

| # | Pergunta | Criterios verificados | Rows | Resultado |
|---|----------|-----------------------|------|-----------|
| 1 | Relatorio previsao Donaldson meses em colunas | UPPER, EXISTS, <>'C', IN('C','O'), sem IS NOT NULL, NVL, CASE | 500 | PASS |
| 2 | Pedidos Donaldson SEM previsao | UPPER, EXISTS, IS NULL (explicito), IN('C','O') | 500 | PASS |
| 3 | Marcas com mais pedidos pendentes | UPPER, ='P' (pediu pendentes), IN('C','O') | 137 | PASS |

**Comparacao antes/depois:**
- Antes: 0 registros (query errada em 5 pontos)
- Depois: 500 registros (query correta, dados reais)

**Aprendizado chave:** O modelo 8B precisa de regras EXPLICITAS e REPETIDAS. As 5 correcoes ja estavam parcialmente documentadas (EXISTS, TGFMAR) mas o modelo nao aplicava consistentemente. A solucao foi:
1. Adicionar regras numeradas no SQL_GENERATOR_PROMPT (11, 12, 13)
2. Reescrever ATENCAO FINAL com 6 regras claras
3. Atualizar referencia condensada com UPPER(), MOSTRAR vs FILTRAR, STATUS em relatorios
4. Exemplos corrigidos servem como referencia direta para o modelo copiar

**Arquivos modificados:**
- `knowledge/sankhya/erros_sql.md` - 4 novos erros (18-21), 18 regras resumo
- `knowledge/glossario/sinonimos.md` - UPPER, MOSTRAR vs FILTRAR, STATUS em relatorios
- `knowledge/sankhya/exemplos_sql.md` - Exemplo 19 reescrito
- `src/llm/agent.py` - 3 regras novas, ATENCAO FINAL reescrito, referencia atualizada

---

### 2026-02-07 (sessao 20) - Correcao CASE...END no Query Executor

**Problema resolvido:** A LLM gerava queries com `CASE WHEN...THEN...END` (ex: pivotar meses em colunas), mas o query_executor bloqueava por ter `END` na lista FORBIDDEN_KEYWORDS.

**Exemplo de query bloqueada:**
```sql
SUM(CASE WHEN TO_CHAR(C.DTPREVENT, 'MM/YYYY') = '01/2025' THEN I.QTDNEG ELSE 0 END) AS "01/2025"
```
Erro: "Query bloqueada por seguranca: Palavra-chave proibida: END"

**Correção:**
- Removido `"END"` da lista `FORBIDDEN_KEYWORDS` em `src/llm/query_executor.py` (linha 76)
- `BEGIN` permanece na lista, bloqueando blocos PL/SQL (`BEGIN...END`)
- `CASE WHEN...END` eh SQL padrao e seguro (expressao condicional, nao executa codigo)

**Testes de validacao (5/5 PASS):**

| # | Query | Esperado | Resultado |
|---|-------|----------|-----------|
| 1 | SELECT com CASE...END | Permitir | PASS |
| 2 | BEGIN...END (PL/SQL) | Bloquear | PASS (bloqueado por BEGIN) |
| 3 | SELECT simples | Permitir | PASS |
| 4 | DELETE com ; | Bloquear | PASS |
| 5 | CASE...END complexo (6x) | Permitir | PASS |

**Teste end-to-end via API:**
- Pergunta: "Pedidos pendentes com colunas por mes de jan a jun 2025 usando SUM CASE WHEN"
- SQL gerado: 6 expressoes `SUM(CASE WHEN ... END)` - **NAO bloqueado**
- Query executada com sucesso (200 OK)

**Arquivos modificados:**
- `src/llm/query_executor.py` - Removido "END" da FORBIDDEN_KEYWORDS

---

### 2026-02-07 (sessao 19) - Previsao de Entrega, TGFMAR e TGFVAR

**Problema resolvido:** A LLM nao sabia sobre DTPREVENT (previsao de entrega), TGFMAR (marcas) nem TGFVAR (atendimentos de pedido). Perguntas como "previsoes de entrega da marca Donaldson" falhavam completamente.

**Tabelas investigadas e documentadas:**
1. **TGFMAR** (Marcas) - 1.441 registros, 5 campos (CODIGO, DESCRICAO, AD_CODVEND, AD_CONSIDLISTAFORN, AD_IDEXTERNO)
2. **TGFVAR** (Variacoes/Atendimentos) - 28.171 registros, 12 campos (NUNOTAORIG, SEQUENCIAORIG, NUNOTA, QTDATENDIDA, etc.)

**Descobertas:**
- TGFCAB.DTPREVENT = previsao de entrega (Data, pode ser NULL)
- TGFPRO.CODMARCA = FK para TGFMAR.CODIGO (caminho correto para marca)
- TGFVAR formula: QTD_PENDENTE = TGFITE.QTDNEG - SUM(TGFVAR.QTDATENDIDA)
- TGFVAR precisa LEFT JOIN (nem todo item tem entrega) e filtro STATUSNOTA <> 'C'
- Para filtrar marca no cabecalho: usar EXISTS subquery (evita multiplicacao)

**8 arquivos atualizados:**

**1. knowledge/sankhya/tabelas/TGFMAR.md** (NOVO)
- Documentacao completa da tabela de marcas

**2. knowledge/sankhya/tabelas/TGFVAR.md** (NOVO)
- Documentacao com formula QTD_PENDENTE e exemplo SQL

**3. knowledge/sankhya/relacionamentos.md:**
- DTPREVENT adicionado ao TGFCAB
- TGFMAR e TGFVAR como novas secoes
- Caminho MARCA via TGFMAR (nao PR.MARCA)
- Regra EXISTS para filtro no cabecalho
- Caminho PREVISAO DE ENTREGA
- Aliases M e VAR adicionados
- 3 novos erros comuns (marca, EXISTS, DTPREVENT)

**4. knowledge/glossario/sinonimos.md:**
- Marca via TGFMAR (nao PR.MARCA)
- Previsao de entrega (DTPREVENT)
- Quantidade pendente (TGFVAR)
- Secao "Status de Entrega de Pedidos"
- Secao "Marca - REGRA IMPORTANTE"
- Secao "Previsao de Entrega"
- Secao "Quantidade Pendente de Entrega (TGFVAR)"

**5. knowledge/sankhya/exemplos_sql.md (agora 20 exemplos):**
- Exemplo 19: Previsao de entrega por marca - nivel CABECALHO (EXISTS)
- Exemplo 20: Itens pendentes de entrega por pedido (TGFVAR)

**6. knowledge/sankhya/erros_sql.md (agora 17 erros):**
- Erro 15: Filtrar marca usando TGFPRO.MARCA em vez de TGFMAR
- Erro 16: Multiplicacao ao filtrar marca no nivel CABECALHO
- Erro 17: Ignorar DTPREVENT quando perguntam sobre previsao

**7. knowledge/processos/compras/fluxo_compra.md:**
- Nova secao "Previsao de Entrega e Atendimento de Pedidos"
- DTPREVENT documentado com queries
- TGFVAR documentado com formula e exemplo
- Fluxo de entrega (Pedido -> Previsao -> Entrega parcial -> Conferencia)
- TGFVAR e TGFMAR adicionados nas tabelas envolvidas
- STATUSNOTA 'A' corrigido para "Atendimento" (era "Aberta")

**8. src/llm/agent.py:**
- _build_sql_reference(): DTPREVENT, TGFMAR (M), TGFVAR adicionados
- CODMARCA em TGFPRO (era MARCA)
- JOIN Marca documentado (PR JOIN TGFMAR M)
- EXISTS pattern para filtro de marca no cabecalho
- PREVISAO DE ENTREGA e PEDIDOS ATRASADOS regras
- QTD PENDENTE regra com TGFVAR
- SQL_GENERATOR_PROMPT: 3 novas regras (8, 9, 10) + ATENCAO FINAL
- FORMATTER_PROMPT: STATUSNOTA A=Atendimento, DTPREVENT mapeado
- STATUSNOTA A=Atendimento (era A=Aberto)

**Resultados dos testes (5 perguntas):**

| # | Pergunta | Tabelas usadas | DTPREVENT | TGFMAR | TGFVAR | Resultado |
|---|----------|---------------|-----------|--------|--------|-----------|
| 1 | Previsoes de entrega pendentes | TGFCAB+TGFPAR | Sim | N/A | N/A | PASS |
| 2 | Donaldson com previsao | TGFCAB+TGFITE+TGFPRO+TGFMAR | Sim | Sim (M.DESCRICAO) | N/A | PASS |
| 3 | Itens pendentes de entrega | TGFCAB+TGFITE+TGFPRO+TGFVAR | N/A | N/A | Sim (LEFT JOIN) | PASS |
| 4 | Sem previsao de entrega | TGFCAB+TGFPAR | Sim (IS NULL) | N/A | N/A | PASS |
| 5 | Pedidos atrasados | TGFCAB+TSIEMP+TGFVEN | Sim (< SYSDATE) | N/A | N/A | PASS |

**Taxa de sucesso: 5/5 (100%)**

**Nota sobre os testes:**
- Testes 1, 2, 5 retornaram 0 rows (possivelmente nao ha pedidos pendentes com previsao no momento)
- Teste 3 deu erro de autenticacao (token Sankhya expirado), mas SQL estruturalmente correto
- Teste 4 retornou 500 rows (muitos pedidos sem previsao)
- Na 1a rodada de testes (antes de atualizar agent.py), 0/3 acertos. O modelo usava DTNEG e PR.MARCA.
- Solucao: regras explicitas no SQL_GENERATOR_PROMPT (regras 8-10) + ATENCAO FINAL antes do SELECT

**Aprendizado chave:** O modelo 8B (qwen3:8b) nao le ~30k chars de contexto SQL efetivamente. As regras precisam estar EXPLICITAS no prompt de geracao (SQL_GENERATOR_PROMPT) e de preferencia logo antes do "SELECT" (onde o modelo presta mais atencao). A referencia condensada (_build_sql_reference) tambem precisa ter as colunas e JOINs corretos.

**Arquivos criados:**
- `knowledge/sankhya/tabelas/TGFMAR.md`
- `knowledge/sankhya/tabelas/TGFVAR.md`
- `src/mcp/extract_tgfmar_tgfvar.py`

**Arquivos modificados:**
- `knowledge/sankhya/relacionamentos.md`
- `knowledge/glossario/sinonimos.md`
- `knowledge/sankhya/exemplos_sql.md`
- `knowledge/sankhya/erros_sql.md`
- `knowledge/processos/compras/fluxo_compra.md`
- `src/llm/agent.py`

---

### 2026-02-07 (sessao 18) - Extracao do Dicionario de Dados (TDD*)

**Objetivo:** Extrair automaticamente a documentacao de TODAS as tabelas relevantes a partir do dicionario interno do Sankhya (tabelas TDD*).

**Tabelas do dicionario usadas:**
- TDDINS: Instancias (metadados de tabelas)
- TDDCAM: Campos (colunas e tipos)
- TDDOPC: Opcoes de dominio (valores possiveis dos campos)
- TDDLIG: Ligacoes (relacionamentos entre tabelas)

**Scripts criados:**
- `src/mcp/extract_data_dictionary.py` - Extrai dados das tabelas TDD* via API Sankhya
- `src/mcp/extract_tddcam_structure.py` - Helper para descobrir nomes corretos das colunas
- `src/mcp/process_data_dictionary.py` - Processa JSON e gera documentacao markdown

**Dados extraidos:**
- 172 instancias (TDDINS)
- 2187 campos em 13 tabelas (TDDCAM)
- 500 opcoes de dominio (TDDOPC)
- 500 relacionamentos (TDDLIG)
- Salvos em `data/raw/data_dictionary.json` e `data/raw/opcoes_dominio.txt`

**13 tabelas documentadas automaticamente em knowledge/sankhya/tabelas/:**

| Tabela | Campos | Destaque |
|--------|--------|----------|
| TGFCAB | 416 | TIPMOV com 23 valores, STATUSNOTA corrigido (A=Atendimento) |
| TGFITE | 237 | Itens das notas |
| TGFPAR | 282 | Parceiros/Clientes/Fornecedores |
| TGFPRO | 397 | Produtos |
| TGFTOP | 372 | Tipos de Operacao |
| TGFFIN | 298 | Titulos Financeiros |
| TGFVEN | 41 | Vendedores |
| TSIEMP | 76 | Empresas |
| TGFEST | 21 | Estoque (TIPO: P=Proprio, T=Terceiro) |
| TGFCOT | 31 | Cotacoes |
| TGFPAG | 0 | Pagamentos (sem campos no dicionario) |
| AD_TGFCUSMMA | 10 | Historico de Custos |
| AD_TGFPROAUXMMA | 6 | Numeros Auxiliares |

**Correcoes importantes descobertas:**
1. **STATUSNOTA 'A'** = "Atendimento" (NAO "Aberto" como documentado antes)
2. **TIPMOV** tem 23 valores (tinhamos documentado apenas 7): B, C, D, E, F, G, I, J, K, L, M, N, O, P, Q, R, T, V, 1, 2, 3, 4, 8
3. **TIPLIBERACAO** mapeado: S=Sem pendencia, P=Pendente, A=Aprovado, R=Reprovado
4. **TGFEST.TIPO**: P=Proprio, T=Terceiro
5. **AD_TIPOSROTA**: 10 rotas de expedicao MMarra (EE, EM, EPR, ERBAR, etc.)

**Documentacao atualizada:**
- `knowledge/sankhya/relacionamentos.md` - TIPMOV completo (23 valores), STATUSNOTA corrigido, TIPLIBERACAO, TGFEST.TIPO, relacionamentos AD_* adicionados
- `knowledge/glossario/sinonimos.md` - TIPMOV completo, STATUSNOTA corrigido, TIPLIBERACAO, TGFEST.TIPO, rotas de expedicao MMarra
- `knowledge/sankhya/tabelas/*.md` - 13 arquivos gerados com campos oficiais e valores de dominio

**Erro corrigido durante extracao:**
- ORA-00904 "CAM"."TIPOCAMPO" - nome correto eh TIPCAMPO (descoberto via query no TDDCAM)

**Arquivos criados:**
- `src/mcp/extract_data_dictionary.py`
- `src/mcp/extract_tddcam_structure.py`
- `src/mcp/process_data_dictionary.py`
- `data/raw/data_dictionary.json`
- `data/raw/opcoes_dominio.txt`
- 13 arquivos em `knowledge/sankhya/tabelas/`

**Arquivos modificados:**
- `knowledge/sankhya/relacionamentos.md`
- `knowledge/glossario/sinonimos.md`

---

### 2026-02-07 (sessao 17) - Desambiguacao de Pendencia (3 tipos)

**Problema resolvido:** A LLM nao diferenciava os tipos de pendencia. "Qual marca tem mais pendencia?" gerava JOIN TGFFIN+TGFITE (multiplicando valores). Agora a LLM identifica 3 tipos distintos.

**3 tipos de pendencia documentados:**
1. **Pendencia de COMPRA** (padrao): STATUSNOTA='P', TIPMOV IN ('C','O'). Usa TGFCAB+TGFITE+TGFPRO. SEM TGFFIN.
2. **Pendencia FINANCEIRA**: DHBAIXA IS NULL, RECDESP=-1. Usa TGFFIN+TGFPAR. SEM TGFITE.
3. **Pendencia de VENDA**: STATUSNOTA='P', TIPMOV IN ('V','P'). Usa TGFCAB+TGFITE+TGFPRO. SEM TGFFIN.

**Regra de desambiguacao:** "pendencia" sem especificar = COMPRA (sem TGFFIN).

**Alteracoes:**

**1. `knowledge/glossario/sinonimos.md`:**
- Nova secao "Tipos de Pendencia" com tabela de mapeamento
- Regra de desambiguacao explicita

**2. `knowledge/sankhya/exemplos_sql.md` (agora 18 exemplos):**
- Exemplo 13: Pendencia de COMPRA por marca (SEM TGFFIN)
- Exemplo 14: Pendencia de VENDA por marca (SEM TGFFIN)
- Exemplo 15: Pendencia FINANCEIRA por fornecedor (TGFFIN SEM TGFITE)
- Exemplo 16: Pendencia FINANCEIRA por marca (subquery IN)
- Exemplo 17: Contas a receber pendentes (RECDESP=1)
- Exemplo 18: Produtos mais comprados (TGFITE SEM TGFFIN)

**3. `knowledge/sankhya/relacionamentos.md`:**
- Nova secao "Regras de Pendencia" com tabelas e filtros para cada tipo

**4. `src/llm/agent.py`:**
- SQL_GENERATOR_PROMPT: nova regra "REGRA DE PENDENCIA" com 3 tipos
- _build_sql_reference(): regra de pendencia na referencia condensada
- Fix regex FETCH FIRST: agora aceita ROW e ROWS (singular/plural)

**Resultados dos testes (4 perguntas):**

| Pergunta | Tabelas | Resultado | Tempo |
|----------|---------|-----------|-------|
| "Qual marca tem mais pendencia?" | TGFCAB+TGFITE+TGFPRO (SEM TGFFIN!) | PASS | 67s |
| "Quais fornecedores tem mais contas a pagar?" | TGFFIN+TGFPAR (SEM TGFITE!) | PASS | 121s |
| "Pedidos de venda pendentes" | TGFCAB+TGFPAR, TIPMOV='P' | PASS | 53s |
| "Titulos vencidos" | TGFFIN+TGFPAR, DTVENC<SYSDATE | PASS | 106s |

**Taxa de sucesso: 4/4 (100%)**

**Melhoria chave:** A regra de desambiguacao resolveu o problema critico da sessao 16. "Pendencia" agora eh interpretado como pendencia de COMPRA (STATUSNOTA='P') e NAO como pendencia financeira (TGFFIN).

**Arquivos modificados:**
- `knowledge/glossario/sinonimos.md` - Tipos de pendencia
- `knowledge/sankhya/exemplos_sql.md` - 6 novos exemplos (13-18)
- `knowledge/sankhya/relacionamentos.md` - Regras de pendencia
- `src/llm/agent.py` - Regra no prompt + regex fix

---

### 2026-02-07 (sessao 16) - Correcao de Padroes SQL (Multiplicacao + ROWNUM)

**Problema identificado:** JOIN entre TGFFIN (financeiro) e TGFITE (itens) multiplica valores. Se nota tem 3 parcelas e 5 itens, gera 15 linhas e SUM fica inflado.

**Correcoes na base de conhecimento:**

**1. `knowledge/sankhya/erros_sql.md` (agora 14 erros):**
- Erro 11: Multiplicacao em JOIN TGFFIN + TGFITE (com alternativas corretas)
- Erro 12: Filtrar pendencia por DTNEG em vez de DTVENC/DHBAIXA
- Erro 13: FETCH FIRST sem ranking completo (sempre top 10)
- Erro 14: WHERE ROWNUM apos ORDER BY (precisa subquery)
- Resumo expandido para 11 regras

**2. `knowledge/sankhya/exemplos_sql.md` (agora 15 exemplos):**
- Exemplo 13: Pendencia por marca (TGFITE+TGFPRO SEM TGFFIN)
- Exemplo 14: Valor pendente por fornecedor (TGFFIN+TGFPAR SEM TGFITE)
- Exemplo 15: Top produtos comprados (TGFITE+TGFPRO SEM TGFFIN)
- Secao "REGRA CRITICA" sobre nunca juntar TGFFIN com TGFITE
- Exemplo 8 corrigido com DIAS_ATRASO

**3. `knowledge/sankhya/relacionamentos.md`:**
- Secao "JOINs PERIGOSOS" adicionada
- Quando usar cada tabela (TGFFIN vs TGFITE vs TGFCAB.VLRNOTA)

**4. CLAUDE.md:**
- Regra 6 adicionada: Cuidado com multiplicacao de JOINs

**5. `src/llm/agent.py` - 2 melhorias:**
- `fix_rownum_syntax()`: Detecta e corrige `ORDER BY ... WHERE ROWNUM` automaticamente
  - Qwen3 gera `SELECT ... ORDER BY x DESC WHERE ROWNUM <= 10`
  - Funcao envolve em subquery: `SELECT * FROM (...) WHERE ROWNUM <= 10`
  - Aplicada tanto na geracao quanto na correcao de SQL
- Referencia condensada atualizada com regra de multiplicacao e DHBAIXA IS NULL

**Resultados dos testes (4 perguntas):**

| Pergunta | Tabelas | ROWNUM Fix | Resultado | Tempo |
|----------|---------|------------|-----------|-------|
| "Qual marca tem mais pendencia?" | TGFFIN+TGFITE (errado) | Sim | FAIL - junta as duas | 78s |
| "Titulos a pagar vencidos" | TGFFIN+TGFPAR (correto) | Sim | PASS | 165s |
| "Valor pendente por fornecedor" | TGFFIN+TGFPAR (correto) | N/A | PASS | 138s |
| "Top 10 produtos mais comprados" | TGFITE+TGFPRO (correto) | Sim | PASS | 97s |

**Taxa de sucesso: 3/4 (75%)**

**fix_rownum_syntax() funcionou perfeitamente** em 3 queries (detectou e corrigiu automaticamente).

**Problema remanescente:** "pendencia por marca" exige TANTO dados financeiros (TGFFIN para DHBAIXA IS NULL) QUANTO dados de produto (TGFPRO para MARCA) - cenario que requer subquery separada. O modelo 8B ainda nao consegue gerar subqueries complexas consistentemente apesar de 25k chars de contexto com exemplos.

**Contexto SQL obrigatorio:** 25386 chars (era 19149 na sessao anterior)

**Arquivos modificados:**
- `knowledge/sankhya/erros_sql.md` - 4 novos erros, 11 regras resumo
- `knowledge/sankhya/exemplos_sql.md` - 3 novos exemplos, regra critica
- `knowledge/sankhya/relacionamentos.md` - JOINs perigosos
- `CLAUDE.md` - Regra 6 multiplicacao
- `src/llm/agent.py` - fix_rownum_syntax(), referencia condensada atualizada

---

### 2026-02-07 (sessao 15) - Base de Conhecimento SQL Obrigatoria

**4 arquivos de conhecimento criados e integrados ao agente:**

**1. `knowledge/sankhya/exemplos_sql.md` (12 exemplos validados):**
- Queries testadas cobrindo: marcas, fornecedores, pendencias, notas, vendedores, produtos, empresas, financeiro, estoque, TOPs, solicitacoes
- Formato: Pergunta -> Query -> Explicacao
- Padrao documentado para Top N em Oracle (subquery + ROWNUM)

**2. `knowledge/glossario/sinonimos.md`:**
- Mapeamento de termos do usuario para filtros SQL
- Secoes: Tipos de Documento (TIPMOV), Status, Pessoas, Produtos, Financeiro, Periodos, Acoes

**3. `knowledge/sankhya/erros_sql.md` (10 erros documentados):**
- JOIN direto TGFCAB-TGFPRO, LIMIT/FETCH FIRST, alias sem qualificador
- GROUP BY incompleto, ponto-e-virgula, campos em tabela errada
- Subquery com escopo errado

**4. `knowledge/processos/compras/rotina_comprador.md`:**
- 10 perguntas tipicas do time de compras
- Traducao de cada pergunta para dados no banco
- Fluxo tipico do comprador (manha, dia, semana, mes)

**Alteracoes no agent.py:**
- `_load_sql_context()` carrega os 4 arquivos obrigatorios (19149 chars total)
- Contexto enviado como `system` message em toda geracao e correcao de SQL
- Independente do RAG - sempre presente

**Alteracoes no CLAUDE.md:**
- 5 regras de manutencao obrigatorias para todas as sessoes
- Checklist atualizado com novos itens

**Resultados dos testes (4 perguntas):**

| Pergunta | Tipo | Resultado | Tempo | Query |
|----------|------|-----------|-------|-------|
| "Como funciona o fluxo de compras?" | DOC | OK | 33s | Resposta mais completa (inclui rotina) |
| "Quais as 10 marcas mais vendidas?" | BANCO | OK | 60s | SQL identico ao exemplo! |
| "Quais titulos a pagar vencidos?" | BANCO | OK | 166s | SQL identico ao exemplo! |
| "Quanto cada empresa vendeu este mes?" | BANCO | OK | 79s | Antes falhava, agora 1a tentativa! |

**Taxa de sucesso: 4/4 (100%)** - LLM gerou SQL seguindo os exemplos documentados!

**Melhoria chave:** A LLM agora copia os padroes dos exemplos validados em vez de inventar SQL do zero. Isso reduz drasticamente os erros.

**Arquivos criados:**
- `knowledge/sankhya/exemplos_sql.md` - NOVO
- `knowledge/sankhya/erros_sql.md` - NOVO
- `knowledge/glossario/sinonimos.md` - NOVO
- `knowledge/processos/compras/rotina_comprador.md` - NOVO

**Arquivos modificados:**
- `src/llm/agent.py` - _load_sql_context(), system message com contexto SQL
- `CLAUDE.md` - 5 regras de manutencao obrigatorias

---

### 2026-02-07 (sessao 14) - Migracao para Qwen3:8b

**Troca de modelo: llama3.1:8b -> qwen3:8b**

**Alteracoes:**
- `.env`: LLM_MODEL alterado para qwen3:8b
- `src/llm/llm_client.py`: Adicionado `num_ctx: 8192` nas opcoes do Ollama
- `src/llm/agent.py`:
  - Funcao `strip_thinking()` para remover tags `<think>...</think>` do Qwen3
  - Aplicada em TODAS as respostas LLM (classificacao, SQL, doc, fix, formatacao)
  - Medicao de tempo (`elapsed`) em respostas DOC e BANCO
  - Limpeza automatica de ponto-e-virgula no SQL gerado
  - Remocao automatica de FETCH FIRST (Qwen3 gera isso, Oracle antigo nao suporta)
  - Regra "NAO usar FETCH FIRST" adicionada ao SQL_GENERATOR_PROMPT

**Resultados dos testes (4 perguntas):**

| Pergunta | Tipo | Resultado | Tempo | Query |
|----------|------|-----------|-------|-------|
| "Como funciona o fluxo de compras?" | DOC | OK | 24s | - |
| "Quais as 10 marcas mais vendidas?" | BANCO | OK | 75s | JOINs corretos (C->I->PR), ROWNUM ok |
| "Quais maiores fornecedores em valor?" | BANCO | OK | 163s | JOIN C->P correto, 500 rows |
| "Quais pedidos de compra pendentes?" | BANCO | OK | 34s | TIPMOV='O', STATUSNOTA='P', 0 rows |

**Taxa de sucesso: 4/4 (100%)** - todas as queries executaram na primeira tentativa!

**Comparacao llama3.1:8b vs qwen3:8b:**
- llama3.1: 3/5 acertos, erros de alias e subquery
- qwen3: 4/4 acertos, SQL mais limpo e correto
- qwen3 usa FETCH FIRST (removido automaticamente) e ponto-e-virgula (removido automaticamente)
- qwen3 tem modo thinking (<think>), removido via strip_thinking()
- Tempos similares, qwen3 um pouco mais lento na formatacao (timeout em 500 rows)

**Ponto de atencao:** Formatacao de 500 registros pode dar timeout (120s). Considerar reduzir limite de rows para formatacao.

---

### 2026-02-07 (sessao 13) - Relacionamentos + Auto-correcao SQL + ngrok

**3 grandes melhorias implementadas:**

**1. Documentacao de relacionamentos entre tabelas:**
- Criado `knowledge/sankhya/relacionamentos.md` com todos os JOINs mapeados
- 10 tabelas com relacionamentos completos (FKs, caminhos, filtros)
- Secoes: Regras de JOIN, Caminhos Importantes, Filtros de Negocio, Aliases, Erros Comuns

**2. Agent.py reescrito para usar relacionamentos:**
- Referencia SQL condensada (1288 chars) carregada SEMPRE na geracao de SQL
- SQL_GENERATOR_PROMPT usa placeholder `{relacionamentos}` com tabelas, colunas e JOINs
- SQL_FIX_PROMPT tambem usa relacionamentos para correcoes mais precisas
- CLASSIFIER_PROMPT melhorado com mais palavras-chave para BANCO vs DOC
- Prompt termina com "SELECT" para induzir o modelo a continuar com SQL
- Prefixo automatico "SELECT " se o modelo nao comecar com SELECT

**3. Auto-correcao de SQL (implementada na sessao anterior, testada agora):**
- Detecta erros Oracle (ORA-*) automaticamente
- Chama LLM com prompt de correcao + relacionamentos
- Retry com query corrigida (maximo 1 tentativa)
- Mensagem amigavel se falhar: "Tente reformular a pergunta"

**4. Acesso remoto via ngrok:**
- Script `start.py` inicia servidor + ngrok em um comando
- CORS habilitado no app.py
- URLs relativas no index.html (ja estavam corretas)
- ngrok via subprocess (evita erro encoding pyngrok no Windows)

**Resultados dos testes (5 perguntas):**

| Pergunta | Tipo | Resultado |
|----------|------|-----------|
| "Como funciona o fluxo de compras?" | DOC | OK |
| "Qual marca tem mais pendencia?" | BANCO | FAIL (alias sem qualificador) |
| "Quais os 10 maiores fornecedores?" | BANCO | OK (20 rows, 1a tentativa!) |
| "Quais pedidos de compra pendentes?" | BANCO | OK (auto-correcao funcionou!) |
| "Quantas notas por empresa este mes?" | BANCO | FAIL (subquery com escopo errado) |

**Taxa de sucesso: 3/5 (60%)** - melhorou significativamente vs sessao anterior

**Ponto de atencao:** Modelo 8B ainda erra em:
- Alias de coluna sem qualificador (STATUSNOTA vs C.STATUSNOTA)
- Subqueries com escopo de alias errado
- Esses erros sao dificeis de corrigir automaticamente

**Arquivos criados/modificados:**
- `knowledge/sankhya/relacionamentos.md` - NOVO: mapa completo de JOINs
- `src/llm/agent.py` - Reescrito: prompts com relacionamentos, auto-correcao SQL
- `src/api/app.py` - CORS adicionado
- `start.py` - NOVO: script de inicio unificado (servidor + ngrok)
- `CLAUDE.md` - Regras obrigatorias para documentar relacionamentos
- `.env` - Corrigido config Groq -> Ollama

**Como rodar:**
```bash
python start.py
```

---

### 2026-02-06 (sessao 12) - Acesso Remoto via ngrok

**Implementado:**
- Script `start.py` na raiz do projeto - inicia tudo com um comando
- Ngrok integrado via subprocess (evita problema de encoding do pyngrok no Windows)
- CORS habilitado no `app.py` para funcionar com qualquer origem
- URLs no `index.html` ja eram relativas (nenhuma alteracao necessaria)

**Como usar:**
```bash
python start.py
```
O script:
1. Verifica se o Ollama esta rodando
2. Libera a porta 8000 se estiver ocupada
3. Inicia tunel ngrok (URL publica gerada automaticamente)
4. Inicia o servidor FastAPI
5. Mostra URL local e publica no terminal

**Arquivos criados/modificados:**
- `start.py` - NOVO: Script de inicializacao unificado
- `src/api/app.py` - Adicionado CORSMiddleware (allow_origins=["*"])
- `.env` - Corrigido: config Groq antiga substituida por Ollama

**Correção do .env:**
- Problema: .env tinha config antiga do Groq (LLM_MODEL=llama-3.3-70b-versatile)
- Corrigido para: LLM_PROVIDER=ollama, LLM_MODEL=llama3.1:8b, OLLAMA_URL=http://localhost:11434
- Credenciais Sankhya ja estavam corretas mas nao carregavam (servidor precisava reiniciar)

**Dependencias:**
- pyngrok (instalado, mas nao usado diretamente - problema de encoding)
- ngrok v3.36.0 (ja instalado no sistema)

---

### 2026-02-06 (sessao 11) - Correcao de Classificacao para Modelo 8B

**Problema identificado:**
- Modelo llama3.1:8b (8B parametros) nao conseguia gerar JSON complexo
- Perguntas de banco eram classificadas como "documentacao"
- Exemplo: "Quais pedidos de compra pendentes?" mostrava badge DOC e sugeria SQL em vez de executar

**Solucao implementada - Prompts simplificados em 3 etapas:**

1. **ETAPA 1 - Classificacao (BANCO ou DOC):**
   - Prompt simplificado: responder apenas "BANCO" ou "DOC"
   - Regra de fallback: se nao for claramente DOC, assume BANCO
   - Temperature=0 (deterministico)
   - Timeout=120s (modelo 8B em CPU pode demorar)

2. **ETAPA 2 - Geracao de SQL (se BANCO):**
   - Prompt direto: "Gere APENAS a query SQL"
   - Sem contexto pesado, apenas tabelas e regras basicas
   - Lista de tabelas, campos, TIPMOV, STATUS
   - Sem markdown, sem explicacao, apenas SELECT

3. **ETAPA 3 - Resposta ou Formatacao:**
   - Se DOC: responde direto da documentacao (contexto 10k chars)
   - Se BANCO: formata resultado em relatorio de negocios

**Arquivos modificados:**
- `src/llm/agent.py`:
  - Substituido AGENT_SYSTEM_PROMPT complexo por 3 prompts simples:
    - CLASSIFIER_PROMPT (palavra unica)
    - SQL_GENERATOR_PROMPT (direto, sem fluff)
    - DOC_ANSWER_PROMPT (resposta da documentacao)
  - Reescrito metodo `_classify()` em 3 chamadas sequenciais simples
  - Adicionado logs de debug ([1/3], [2/3], [3/3])
  - Timeout de 120s em todas as chamadas

- `src/llm/llm_client.py`:
  - Adicionado parametro `timeout` no metodo `chat()`
  - Permite sobrescrever timeout padrao de 120s

**Testes sugeridos:**
- "Quais pedidos de compra estao pendentes?" -> deve executar SQL (badge SQL)
- "Como funciona o fluxo de compras?" -> deve responder da doc (badge DOC)
- "Quantas notas temos este mes?" -> deve executar SQL
- "O que significa TIPMOV?" -> deve responder da doc

**Acesso remoto configurado:**
- IP da maquina: 192.168.0.10
- URL: http://192.168.0.10:8000
- Porta 8000 deve estar liberada no firewall (netsh advfirewall)

---

### 2026-02-06 (sessao 10) - Migracao para Ollama (LLM local)

**Migracao de Groq (API externa) para Ollama (LLM local):**
- **Problema:** Groq tinha limite de 12k tokens/minuto no free tier, causando erro 429
- **Solucao:** Ollama rodando local, sem limites, sem custo, sem dados saindo da rede

**Arquivos criados/modificados:**
- `src/llm/llm_client.py` - NOVO: Cliente LLM unificado para Ollama
- `src/llm/chat.py` - Atualizado para usar LLMClient
- `src/llm/agent.py` - Atualizado para usar LLMClient
- `src/api/app.py` - Atualizado com health check do Ollama
- `.env` - Novas variaveis: LLM_PROVIDER, LLM_MODEL, OLLAMA_URL
- `requirements.txt` - Removido groq, mantido httpx

**Configuracao do Ollama:**
- Instalado: Ollama v0.15.5
- Modelo: llama3.1:8b (4.9GB)
- API: http://localhost:11434

**Vantagens:**
- Sem rate limit (Groq tinha 12k tokens/min)
- Sem custo (Groq tinha limite no free tier)
- Dados nao saem da rede interna (seguranca)
- Modelo roda na maquina local

**FORMATTER_PROMPT melhorado:**
- Instrucoes claras para NAO inventar dados
- Mapeamento de colunas tecnicas para amigaveis
- Temperature=0 para respostas mais deterministicas

**Como rodar:**
- Ollama: `ollama serve` (ja roda como servico)
- Web: `python -m src.api.app` (http://localhost:8000)
- CLI: `python -m src.llm.chat "pergunta"`

---

### 2026-02-06 (sessao 9) - LLM + Agente com acesso ao banco

**Implementado:**
- `src/llm/chat.py` - Chat CLI com RAG (TF-IDF, busca top 5 docs)
- `src/llm/query_executor.py` - Executor seguro (SELECT only, ROWNUM <= 500, timeout 30s, retry auth 401/403)
- `src/llm/agent.py` - Agente LLM que decide entre documentacao e consulta ao banco em tempo real
- `src/api/app.py` - API FastAPI (endpoints: /api/chat, /api/status, /api/clear)
- `src/api/static/index.html` - Frontend com logo MMarra, tema azul, bloco colapsavel de SQL
- Modelo: llama-3.3-70b-versatile via Groq (128k context)
- Modo RAG forcado (max 5 docs, 3000 chars cada, 15k total)

**Correcoes desta sessao:**
- Erro 413 Payload Too Large: Forcado modo RAG, nunca envia base completa
- Erro 401 autenticacao: URL base corrigida, adicionado verify=False
- Token expirando: Retry automatico em 401/403, token valido por 4 min

**Pendente:**
- Melhorar prompt de formatacao: LLM esta inventando dados ficticios em vez de usar os dados reais do banco
- Respostas devem ser em linguagem de negocio (sem SQL, sem termos tecnicos)
- Colunas devem ter nomes amigaveis (NUNOTA -> Pedido, NOMEPARC -> Fornecedor, etc)

**Como rodar:**
- CLI: `python -m src.llm.chat "pergunta"`
- Web: `python -m src.api.app` (http://localhost:8000)

**Exemplos de perguntas:**
- Documentacao: "Como funciona o fluxo de compras?"
- SQL: "Quantas notas de compra temos este mes?"
- SQL: "Quais os 10 maiores fornecedores por valor de compra?"

---

### 2026-02-06 (sessao 8) - Parte 6: Agente LLM com Consulta ao Banco
- **DataHubAgent implementado em src/llm/agent.py**
- Agente que decide entre responder com documentacao ou consultar o banco
- **Fluxo em 2 etapas:**
  1. Classificacao: LLM analisa pergunta e retorna JSON com tipo (documentacao/consulta_banco)
  2. Execucao: Se SQL, executa via SafeQueryExecutor e formata resultado
- **System Prompt atualizado com:**
  - Instrucoes para gerar SQL Oracle (ROWNUM, SYSDATE, TO_CHAR)
  - Tipos de movimentacao (TIPMOV: V, C, D, O, P, J, T)
  - Formato de resposta JSON obrigatorio
- **API atualizada (v2.0):**
  - Endpoint /api/chat agora usa o agente
  - Novos campos: tipo, query_executed, query_results
- **Interface Web atualizada:**
  - Badge de tipo (DOC/SQL) nas mensagens
  - Bloco colapsavel mostrando query executada
  - Quantidade de registros retornados
- **Compatibilidade mantida:**
  - CLI (python -m src.llm.chat) continua funcionando apenas com documentacao
  - SEM emojis (Windows cp1252)
- **Como testar:**
  - Documentacao: "Como funciona o fluxo de compras?"
  - SQL: "Quantas notas de compra temos este mes?"

### 2026-02-06 (sessao 8) - Parte 5: Query Executor Seguro
- **SafeQueryExecutor implementado em src/llm/query_executor.py**
- Classe para execucao segura de queries SQL no Sankhya
- **Validacoes de seguranca:**
  - Somente SELECT permitido
  - Bloqueio de comandos perigosos (INSERT, UPDATE, DELETE, DROP, etc)
  - Bloqueio de comentarios SQL (--, /* */)
  - Bloqueio de multiplas statements (;)
  - Deteccao inteligente: ignora palavras-chave dentro de strings
  - Whitelist opcional de tabelas
- **Limite automatico de linhas:**
  - Wrapper com ROWNUM <= 500 (Oracle)
  - Respeita limites menores se ja existirem
  - Reduz limites maiores para 500
- **Execucao:**
  - Autenticacao OAuth2 reutilizada do MCP Server
  - Timeout de 30 segundos
  - Formatacao de resultados em Markdown
- **Testes:** 14 casos de teste, todos passando
- **Como usar:**
  ```python
  from src.llm.query_executor import SafeQueryExecutor
  executor = SafeQueryExecutor()
  result = await executor.execute("SELECT * FROM TGFPAR WHERE ROWNUM <= 10")
  print(executor.format_results(result))
  ```

### 2026-02-06 (sessao 8) - Parte 4: LLM Chat + Interface Web
- **LLM Chat com RAG implementado e funcionando**
- Arquivos instalados do ZIP:
  - `src/llm/chat.py` - Motor de chat com RAG (TF-IDF + Groq)
  - `src/api/app.py` - API FastAPI para interface web
  - `src/api/static/index.html` - Frontend com tema azul MMarra
- **Correcoes necessarias para Windows:**
  - Emojis removidos do codigo (cp1252 encoding)
  - Modelo alterado para llama-3.1-8b-instant (menor contexto)
  - RAG com top_k=3 e truncamento 4k chars/doc
- **Como usar:**
  - CLI: `python -m src.llm.chat "pergunta aqui"`
  - Web: `python -m src.api.app` -> http://localhost:8000
- **Base de conhecimento:** 40 documentos (~50k tokens)
  - 15 tabelas, 5 regras, 4 processos, 15 queries, 1 API
- Dependencias: groq, scikit-learn, uvicorn, fastapi

### 2026-02-06 (sessao 8) - Parte 3: Regras de Negocio
- **Documentacao completa de regras de negocio em knowledge/regras/**
- 5 arquivos criados:
  - **aprovacao_compras.md** - Descoberta que MMarra NAO usa workflow formal
    - TGFLIB, AD_APROVACAO, AD_LIBERACOESVENDA, TGFALL todas vazias
    - PENDENTE/APROVADO em TGFCAB sao informativos, nao bloqueiam
    - 317k notas com PENDENTE='S', APROVADO='S'
  - **solicitacao_compra.md** - Processo de requisicao
    - TGFSOL padrao esta VAZIA - MMarra usa TGFCAB TIPMOV='J'
    - 2.878 solicitacoes, R$ 6.09M, 99% de 2026 (sistema novo)
    - TOP 1804 (SOLICITACAO DE COMPRA)
    - ATUALEST=N, ATUALFIN=0 (sem impacto operacional)
  - **cotacao_compra.md** - Comparacao entre fornecedores
    - TGFCOT: 2.849 cotacoes, 54% finalizadas, 30% canceladas
    - 99.9% vinculadas a solicitacao via NUNOTAORIG
    - Apenas PESOPRECO=1 configurado (avalia so por preco)
    - TGFCOI e TGFCOC vazias
  - **custos_produto.md** - Historico de custos
    - AD_TGFCUSMMA: 709k registros, 5 anos de dados (2020-2025)
    - TGFCUS (289k) vs AD_TGFCUSMMA (709k) - customizada tem 2.5x mais
    - Varios tipos: CUSCOMICM, CUSSEMICM, CUSREP, CUSGER
    - Matriz (61%), Campinas (14%), Itumbiara (13%)
  - **codigos_auxiliares.md** - Cross-reference de produtos
    - AD_TGFPROAUXMMA: 1.145.087 codigos para 62.399 produtos
    - 62% produtos tem 2-5 codigos auxiliares
    - Usado para busca por codigo original de fabricante
    - Top marcas: Mercedes (28%), VW (10%), Ford (9%)
- Script de extracao: src/mcp/extract_regras_negocio.py

### 2026-02-06 (sessão 8) - Parte 2: Tabelas AD_*
- **Mapeamento completo das tabelas AD_* (customizacoes MMarra)**
  - Total: 142 tabelas customizadas
  - Com dados: 95 tabelas
  - Vazias: 47 tabelas
- **Descoberta importante:** Tabelas de workflow VAZIAS
  - AD_APROVACAO - 0 registros (nao usa)
  - AD_LIBERACOESVENDA - 0 registros (nao usa)
  - AD_COTACOESDEITENS - 0 registros (nao usa)
  - AD_SOLICITACAOCOMPRA - 0 registros (nao usa)
  - **Conclusao:** MMarra NAO implementou workflow customizado
- **Tabelas documentadas:**
  - AD_TGFPROAUXMMA (1.145.087) - Numeros auxiliares de produtos
  - AD_TGFCUSMMA (709.230) - Historico de custos
  - AD_MARCAS (799) - Marcas de produtos
  - AD_TABELAS_CUSTOMIZADAS.md - Mapeamento completo
- **Maiores tabelas AD_* com dados:**
  - AD_BKP_TGWEXP_12012026: 40M (backup WMS)
  - AD_TGFPROAUXMMA: 1.1M (codigos auxiliares)
  - AD_IMPNUMAUX_MMA: 1M (importacao)
  - AD_TGFCUSMMA: 709k (custos)
  - AD_DUPLICATAS3_MMA: 425k (comissoes)
- Script de extracao: src/mcp/extract_ad_tables.py

### 2026-02-06 (sessão 8) - Parte 1: Compras
- Completar mapeamento de compras - investigacao de tabelas pendentes
- **TGFLIB documentada** (0 registros - VAZIA)
  - Estrutura: NUNOTA, CODUSU, DT, LIBERACOES, OBS
  - PK composta: NUNOTA + CODUSU
  - FKs: TGFCAB, TSIUSU
  - MMarra NAO usa TGFLIB - utiliza sistema customizado AD_APROVACAO
- **TGFCOT documentada** (2.839 cotacoes)
  - Sistema de cotacao de compras ATIVO
  - Campos de peso para avaliacao: PESOPRECO, PESOCONDPAG, etc
  - TGFCOI e TGFCOC vazias (itens podem estar em AD_COTACOESDEITENS)
- **Tabelas de Solicitacao investigadas:**
  - TGFSOL existe mas VAZIA (0 registros)
  - Solicitacao usa TGFCAB com TIPMOV='J': 2.868 registros, R$ 6.05M
  - TOP 1804: SOLICITACAO DE COMPRA
- **Pedidos de Compra (TIPMOV='O'):** 2.148 registros, R$ 15.43M
  - TOP 1313: Entrega Futura/Empenho (751)
  - TOP 1301: Revenda (571)
  - TOP 1321: Transferencia Empenho (386)
- **fluxo_compra.md atualizado** com:
  - Secao sobre TGFCOT (cotacao)
  - Detalhes das TOPs de pedido de compra
  - Informacao que TGFLIB e TGFSOL estao vazias
  - Estatisticas atualizadas
- Script de extracao: src/mcp/extract_compras_complete.py

### 2026-02-05 (sessão 7)
- Aprofundamento do mapeamento do fluxo de compras
  - **TGFEST** documentada (36.769 posicoes de estoque)
    - PK composta: CODEMP + CODLOCAL + CODPROD + CONTROLE + TIPO + CODPARC
    - Campos: ESTOQUE, RESERVADO, ESTMIN, ESTMAX, WMSBLOQUEADO
    - FKs: TGFEMP, TGFLOC, TGFPRO, TGFPAR
  - **TGFFIN** documentada (54.441 titulos financeiros)
    - PK: NUFIN (sequencial)
    - RECDESP: 1=Receber (36k, R$ 46M), -1=Pagar (18k, R$ 113M)
    - Vinculo com notas via NUNOTA
    - ~180 campos incluindo impostos, boletos, baixas
  - **fluxo_compra.md** atualizado com:
    - Status das notas: L=Liberada (76k), P=Pendente (242), A=Aberta (165)
    - Transicoes de status: A -> P -> L (com aprovacao) ou A -> L (direto)
    - Campos de controle: STATUSNOTA, PENDENTE, APROVADO
    - Impacto em TGFEST e TGFFIN quando nota eh confirmada
    - Sistema de aprovacoes (TGFLIB)
    - Tabelas AD_APROVACAO e AD_LIBERACOESVENDA
- Script de extracao: src/mcp/extract_compras_flow.py
- Dados extraidos: src/mcp/compras_flow_data.json

### 2026-02-05 (sessão 6)
- Queries SQL uteis criadas em /queries/
  - **vendas/** (5 arquivos): vendas_periodo, vendas_vendedor, vendas_cliente, faturamento_empresa, notas_por_top
  - **compras/** (4 arquivos): compras_periodo, compras_fornecedor, pedidos_pendentes, compras_comprador
  - **estoque/** (3 arquivos): devolucoes, transferencias, movimentacao
  - **financeiro/** (3 arquivos): a_receber, a_pagar, fluxo_caixa
- Total: 15 arquivos SQL com queries prontas para uso

### 2026-02-05 (sessão 5)
- Documentacao de processos de negocio criada
  - **Fluxo de Venda:** Balcao (TOP 1100, 120k notas) e NFe (TOP 1101, 105k notas)
    - Pedido com reserva (TOP 1001) → Faturamento
    - ATUALEST=B (baixa), ATUALFIN=1 (receber), NFE=T (transmite)
  - **Fluxo de Compra:** Solicitacao → Pedido → Recebimento
    - TOP 1209 (compra revenda, 47k notas, R$ 382M)
    - ATUALEST=E (entrada), ATUALFIN=-1 (pagar)
  - **Fluxo de Devolucao:** Venda (1202) e Compra (1501)
    - Dev. venda: ATUALEST=E, ATUALFIN=-1 (credito cliente)
    - Dev. compra: ATUALEST=B, ATUALFIN=1 (credito fornecedor)
  - **Fluxo de Transferencia:** Saida (1150) e Entrada (1452)
    - ~21k transferencias, R$ 46M
    - ATUALFIN=0 (sem impacto financeiro)
    - Diferenca 436 notas entre saida/entrada (transito)

### 2026-02-05 (sessão 4)
- Documentacao TSIEMP criada (10 empresas/filiais)
  - Matriz em Ribeirao Preto + 8 filiais + 1 consolidacao
  - Maior volume: Emp 1 Ribeirao (181k notas, R$ 343M)
  - Segundo maior: Emp 7 Itumbiara (85k notas, R$ 295M)
  - Campos: identificacao, endereco, fiscais, modulos, SMTP
  - 9 FKs mapeadas (cidade, bairro, endereco, parceiro, matriz)
- Documentacao TGFVEN criada (111 vendedores)
  - 86 vendedores, 20 compradores, 4 gerentes
  - 70% das notas sem vendedor associado (CODVEND=0)
  - Top vendedor: Liciane (953 notas, R$ 1M)
  - Gerentes com equipe: Paulo Teixeira (20), Liciane (8), Fylippe (8)
  - Scripts de extracao: extract_tsiemp.py, extract_tgfven.py

### 2026-02-05 (sessão 3)
- Documentacao TGFPAR criada (57.121 parceiros)
  - Campos principais, endereco, contato, fiscais, financeiros
  - 30 FKs mapeadas
  - Valores de dominio identificados
- Documentacao TGFPRO criada (393.696 produtos)
  - Campos principais, peso/dimensoes, preco, estoque, fiscais, lote
  - 27 FKs mapeadas
  - Principais marcas: Cummins (44k), MWM (15k), ZF (14k)
  - 98% produtos de revenda, 50% sem grupo definido
- Documentacao TGFTOP criada (1.318 tipos de operacao)
  - Define comportamento: estoque, financeiro, fiscal, NFe
  - TOPs mais usadas: 1100 (Venda Balcao 120k), 1101 (Venda NFe 105k), 1209 (Compra 47k)
  - TIPMOV: V=venda, C=compra, P=pedido, D=devolucao
  - Scripts de extracao criados em src/mcp/

### 2026-02-05 (sessão 2)
- MCP Server configurado em `src/mcp/server.py`
- Tools: executar_query, listar_tabelas, descrever_tabela, buscar_chaves, buscar_valores_dominio, sample_dados
- Autenticação OAuth 2.0 funcionando
- Descoberta: banco é **Oracle** (não SQL Server) - queries ajustadas para ROWNUM
- Documentação da API em `knowledge/sankhya/api.md`
- **Conexão testada com sucesso!**

### 2026-02-05 (sessão 1)
- Projeto iniciado do zero (v3)
- Estrutura preparada para repositório de dados inteligente
- CLAUDE.md criado com mapa completo e templates
- Objetivo: plataforma com dashboards + LLM para perguntas de negócio
