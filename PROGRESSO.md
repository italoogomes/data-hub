# PROGRESSO.md

> Última atualização: 2026-02-05

---

## STATUS ATUAL

✅ **MCP Server funcionando! Conexão com API Sankhya testada com sucesso.**

---

## O QUE ESTÁ PRONTO

- [x] Estrutura de pastas
- [x] CLAUDE.md com instruções e templates
- [x] Pronto para receber documentação
- [x] MCP Server do Sankhya (`src/mcp/server.py`)

---

## PRÓXIMOS PASSOS

1. [x] ~~Configurar MCP Server para Sankhya~~
2. [x] ~~Testar conexão com API~~
3. [x] ~~Varredura das tabelas principais (TGFCAB, TGFPAR, TGFPRO, TGFTOP, TSIEMP, TGFVEN)~~
4. [x] ~~Documentar processos (venda, compra, devolucao, transferencia)~~
5. [ ] Documentar glossario e regras de negocio
6. [x] ~~Criar queries SQL uteis em /queries~~

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

### Processos Documentados
- [x] **Fluxo de Venda** - Balcao (1100), NFe (1101), Pedido → Faturamento
- [x] **Fluxo de Compra** - Solicitacao → Pedido → Recebimento (1209)
- [x] **Fluxo de Devolucao** - Dev. venda (1202), Dev. compra (1501)
- [x] **Fluxo de Transferencia** - Saida (1150), Entrada (1452)

### Glossário
_Vazio - adicionar termos conforme aparecem_

### Regras de Negócio
_Nenhuma ainda_

### Erros Conhecidos
_Nenhum ainda_

---

## SESSÕES ANTERIORES

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
