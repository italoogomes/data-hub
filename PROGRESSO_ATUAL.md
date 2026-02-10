# PROGRESSO_ATUAL.md

> Ultima atualizacao: 2026-02-10 (sessao 26)
> Historico de sessoes: Ver `PROGRESSO_HISTORICO.md`

---

## STATUS ATUAL

**Agente LLM com consulta ao banco + Login Sankhya + Menu Lateral**

- **Web:** http://localhost:8080 (`python start.py`)
- **Login:** Autenticacao via Sankhya MobileLoginSP.login (credenciais do ERP)
- **Sessoes:** Em memoria, timeout 8h, token Bearer
- **Menu Lateral:** Chat IA + Relatorios (placeholder)
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
- `src/api/app.py` - API FastAPI (com auth Sankhya + sessoes)
- `src/api/static/index.html` - Frontend (login + sidebar + chat + relatorios)

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
- [x] Login Sankhya (`/api/login`) - autenticacao via MobileLoginSP.login
- [x] Sessoes em memoria (`/api/logout`, `/api/me`) - timeout 8h, token Bearer
- [x] Menu lateral de navegacao (Chat IA + Relatorios)
- [x] Area de Relatorios (placeholder com 6 cards)
- [x] Agente LLM (`src/llm/agent.py`) - decide entre DOC e SQL

---

## PROXIMOS PASSOS

1. [ ] **Implementar relatorio Pendencia de Compras** (primeiro relatorio real)
2. [ ] Testar RBAC com vendedor e comprador reais
3. [ ] Testar LLM na maquina pessoal (GPU)
4. [ ] Sessao de testes com usuario real do time de compras
5. [ ] Criar avisos.md (limitacoes conhecidas)
6. [ ] Atingir 90/100 no checklist beta

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

### Regras de Negocio
- [x] **aprovacao_compras** - MMarra NAO usa workflow formal (TGFLIB, AD_APROVACAO vazias)
- [x] **solicitacao_compra** - Usa TGFCAB TIPMOV='J' (2.878 registros, sistema novo 2026)
- [x] **cotacao_compra** - TGFCOT vinculada via NUNOTAORIG, apenas PESOPRECO=1
- [x] **custos_produto** - AD_TGFCUSMMA com 709k registros (5 anos historico)
- [x] **codigos_auxiliares** - AD_TGFPROAUXMMA com 1.1M codigos cross-reference

### Erros Conhecidos
_Nenhum ainda_

---

## SESSAO MAIS RECENTE

### 2026-02-10 (sessao 26) - Login Sankhya + Menu Lateral + Area de Relatorios

**Contexto:** Usuario solicitou pausa no trabalho de LLM/SQL para implementar tela de login e area de relatorios. Escolheu: login via credenciais Sankhya + menu lateral (sidebar esquerda).

**Implementado:**

**1. Backend - Autenticacao via Sankhya (`src/api/app.py`):**
- Rota `POST /api/login`: Autentica usuario via Sankhya MobileLoginSP.login
  - Envia NOMUSU + INTERNO (senha) para `https://api.sankhya.com.br/mge/service.sbr`
  - Se `status == "1"`: cria sessao local, retorna token
  - Se falha: retorna 401
- Rota `POST /api/logout`: Remove sessao do dict
- Rota `GET /api/me`: Valida token e retorna info do usuario
- Funcao `get_current_user()`: Extrai token do header `Authorization: Bearer {token}`, valida sessao e timeout
- Sessoes em memoria: `{token: {user, login_time, last_activity}}`
- Timeout: 8 horas de inatividade
- Rotas protegidas: `/api/chat`, `/api/clear`, `/api/status` (requerem token)
- Rota `/` (index.html): publica (JS controla tela de login)

**2. Frontend - Tela de Login (`src/api/static/index.html`):**
- `<div class="login-screen">` com logo MMarra centralizada
- Campos: usuario e senha
- Botao "Entrar" com loading state
- Mensagem de erro se falhar
- Token salvo em `localStorage` (datahub_token, datahub_user)
- Validacao de sessao ao carregar pagina (`checkSession()` via GET /api/me)
- Auto-redirect para login em resposta 401

**3. Frontend - Menu Lateral Esquerdo:**
- `<div class="nav-sidebar">` fixa, 220px de largura
- Items de navegacao: Chat IA (icone chat) + Relatorios (icone grafico)
- Item ativo com borda lateral azul
- Rodape: nome do usuario logado + botao Sair
- Funcao `switchSection()` alterna entre chat e relatorios
- Mobile responsive: sidebar esconde < 768px com hamburger toggle

**4. Frontend - Area de Relatorios (Placeholder):**
- 6 cards placeholder em grid:
  1. Pendencia de Compras
  2. Historico por Fornecedor
  3. Performance de Fornecedores
  4. Vendas por Periodo
  5. Estoque Critico
  6. Curva ABC
- Todos com badge "Em breve"

**5. Ajustes no Layout:**
- Chat area agora usa flex layout (input nao mais position:fixed)
- Content area com margin-left: 220px (espaco para sidebar)
- Toda requisicao API inclui header `Authorization: Bearer {token}`

**Arquivos modificados:**
- `src/api/app.py` - Auth completo (290 linhas)
- `src/api/static/index.html` - Frontend completo com login + sidebar (~1730 linhas)

**Testes pendentes:**
1. Testar login com credenciais Sankhya reais
2. Testar timeout de sessao
3. Testar navegacao entre Chat e Relatorios
4. Testar responsividade mobile

---

*Este arquivo contem apenas o estado atual e a sessao mais recente.*
*Para historico de sessoes anteriores (1-25), ver `PROGRESSO_HISTORICO.md`.*
