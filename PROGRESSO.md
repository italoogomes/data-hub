# PROGRESSO.md

> Última atualização: 2026-02-06 (sessão 11)

---

## STATUS ATUAL

**Agente LLM com consulta ao banco funcionando - AGORA 100% LOCAL!**

- **Web:** http://localhost:8000 (`python -m src.api.app`)
- **CLI:** `python -m src.llm.chat "pergunta"` (apenas documentacao)
- **LLM Provider:** Ollama (local, sem custo, sem rate limit)
- **Modelo:** llama3.1:8b (4.9GB, roda na maquina)
- **RAG:** Top 5 docs, max 3000 chars/doc, 15k total
- **Query Executor:** SELECT only, ROWNUM <= 500, retry auth 401/403
- **Dados:** Nao saem da rede interna (LLM local)

**Arquivos principais:**
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
