# Fluxo de Compra

**Modulo:** Compras

**Descricao:** Processo completo de aquisicao de mercadorias, desde a solicitacao ate o recebimento fisico, entrada no estoque e geracao do titulo financeiro a pagar.

---

## Visao Geral

A compra na MMarra segue um fluxo que envolve:
1. **Solicitacao de Compra** - Identificacao da necessidade (TGFCAB TIPMOV='J')
2. **Cotacao** - Comparacao de precos entre fornecedores (TGFCOT)
3. **Pedido de Compra** - Negociacao com fornecedor (TGFCAB TIPMOV='O')
4. **Recebimento** - Entrada da mercadoria e nota fiscal (TGFCAB TIPMOV='C')
5. **Estoque** - Atualizacao da posicao de estoque (TGFEST)
6. **Financeiro** - Geracao de titulo a pagar (TGFFIN)

---

## Tabelas Envolvidas no Processo Completo

| Tabela | Papel no Processo | Registros | Documentacao |
|--------|-------------------|-----------|--------------|
| **TGFCAB** | Cabecalho da nota/pedido | 343k | [TGFCAB.md](../../sankhya/tabelas/TGFCAB.md) |
| **TGFITE** | Itens comprados | 1.1M | [TGFITE.md](../../sankhya/tabelas/TGFITE.md) |
| **TGFCOT** | Cotacoes de compra | 2.839 | [TGFCOT.md](../../sankhya/tabelas/TGFCOT.md) |
| **TGFPAR** | Fornecedor (CODPARC) | 57k | [TGFPAR.md](../../sankhya/tabelas/TGFPAR.md) |
| **TGFPRO** | Produtos adquiridos | 394k | [TGFPRO.md](../../sankhya/tabelas/TGFPRO.md) |
| **TGFVEN** | Comprador responsavel (TIPVEND = C) | 20 | [TGFVEN.md](../../sankhya/tabelas/TGFVEN.md) |
| **TGFTOP** | Define comportamento da operacao | 1.3k | [TGFTOP.md](../../sankhya/tabelas/TGFTOP.md) |
| **TSIEMP** | Empresa compradora | 10 | [TSIEMP.md](../../sankhya/tabelas/TSIEMP.md) |
| **TGFEST** | Posicao de estoque | 36.7k | [TGFEST.md](../../sankhya/tabelas/TGFEST.md) |
| **TGFFIN** | Titulos a pagar | 54k | [TGFFIN.md](../../sankhya/tabelas/TGFFIN.md) |
| **TGFLIB** | Liberacoes/aprovacoes (VAZIA) | 0 | [TGFLIB.md](../../sankhya/tabelas/TGFLIB.md) |

### Tabelas de Solicitacao

| Tabela | Status | Observacao |
|--------|--------|------------|
| **TGFSOL** | VAZIA | Tabela padrao nao utilizada |
| **AD_SOLICITACAOCOMPRA** | Customizada | Verificar se utilizada |

**Conclusao:** Solicitacoes de compra ficam em **TGFCAB com TIPMOV='J'**

---

## Status das Notas (STATUSNOTA)

### Distribuicao no Sistema

| STATUSNOTA | Significado | Quantidade |
|------------|-------------|------------|
| **L** | Liberada/Confirmada | 76.313 |
| **P** | Pendente | 242 |
| **A** | Aberta/Em digitacao | 165 |

### Transicoes de Status

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│    A     │────>│    P     │────>│    L     │
│ (Aberta) │     │(Pendente)│     │(Liberada)│
└──────────┘     └──────────┘     └──────────┘
      │
      └────────────────────────────────┘
              (direto se sem aprovacao)
```

**Fluxo de Status:**
1. **A (Aberta)** - Nota em digitacao, pode ser editada
2. **P (Pendente)** - Aguardando aprovacao/liberacao
3. **L (Liberada)** - Confirmada, gerou estoque/financeiro

---

## Campos de Controle em TGFCAB

| Campo | Tipo | Tamanho | Funcao |
|-------|------|---------|--------|
| STATUSNOTA | VARCHAR2 | 1 | Status principal (A/P/L) |
| STATUSNFE | VARCHAR2 | 1 | Status NFe |
| PENDENTE | VARCHAR2 | 1 | Flag de pendencia |
| APROVADO | VARCHAR2 | 1 | Flag de aprovacao |
| CONFIRMNOTAFAT | VARCHAR2 | 1 | Confirmacao faturamento |
| STATUSCFE | CHAR | 1 | Status CF-e |
| STATUSCTE | CHAR | 1 | Status CT-e |
| STATUSNFSE | VARCHAR2 | 1 | Status NFS-e |
| STATUSNFCOM | VARCHAR2 | 1 | Status NF-e Comunicacao |

---

## TOPs Envolvidas no Processo de Compra

### TOPs de Solicitacao (TIPMOV = J)

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | Qtd Notas | Valor Total |
|------------|-----------|----------|----------|-----------|-------------|
| **1804** | Solicitacao de Compra | N | 0 | 2.868 | R$ 6.05M |

**Comportamento:**
- ATUALEST = N (Nao) - Nao afeta estoque
- ATUALFIN = 0 - Nao gera financeiro
- Apenas registro da necessidade
- Tabela: **TGFCAB** (nao usa TGFSOL)

### TOPs de Pedido de Compra (TIPMOV = O)

**Total:** 2.148 pedidos | R$ 15.43M

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | Qtd Notas |
|------------|-----------|----------|----------|-----------|
| **1313** | Pedido Compra - Entrega Futura (Empenho) | N | 0 | 751 |
| **1301** | Pedido Compra - Revenda | N | 0 | 571 |
| **1321** | Pedido Transferencia Entrada Empenho | N | 0 | 386 |
| **1304** | Pedido Compra - Servico Diversos | N | 0 | 141 |
| **1317** | Pedido Compra - Uso/Consumo Despesas | N | 0 | 82 |
| **1961** | Pedido Transferencia Entre Filiais Entrada | N | 0 | 58 |
| **1318** | Pedido Compra - Beneficios | N | 0 | 35 |
| **1305** | Pedido Compra - Clara | N | 0 | 33 |
| **1340** | Pedido Compra - Servico Prestacao | N | 0 | 32 |
| **1310** | Pedido Compra - Telecomunicacoes | N | 0 | 29 |

**Comportamento:**
- ATUALEST = N - Nao afeta estoque (ainda)
- ATUALFIN = 0 - Nao gera financeiro (ainda)
- Compromisso com fornecedor
- Tabela: **TGFCAB**

### TOPs de Entrada/Compra Efetiva (TIPMOV = C)

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | NFE | Qtd Notas | Valor |
|------------|-----------|----------|----------|-----|-----------|-------|
| **1209** | Compra mercadoria revenda | E | -1 | N | 47.523 | R$ 382M |
| **1401** | Compra WMS | E | -1 | N | - | - |
| **1402** | Compra uso/consumo | E | -1 | N | - | - |
| **1404** | Compra servico | N | -1 | N | - | - |
| **1451** | Bonificacao entrada | E | 0 | N | - | - |
| **1452** | Transferencia entrada | E | 0 | N | 21.276 | R$ 46M |
| **2000** | Compra entrada geral | E | -1 | N | - | - |

**Comportamento:**
- ATUALEST = E (Entrada) - Adiciona ao estoque
- ATUALFIN = -1 - Gera financeiro a pagar
- NFE = N - NFe do fornecedor (entrada)

---

## Cotacao de Compra (TGFCOT)

**Total:** 2.839 cotacoes

### O que e Cotacao

Processo de comparacao de precos e condicoes entre fornecedores antes de fechar pedido de compra.

### Estrutura

| Tabela | Descricao | Registros |
|--------|-----------|-----------|
| **TGFCOT** | Cabecalho da cotacao | 2.839 |
| TGFCOI | Itens cotados | 0 (vazia) |
| TGFCOC | Fornecedores cotados | 0 (vazia) |
| AD_COTACOESDEITENS | Itens (customizada) | Verificar |

Documentacao: [TGFCOT.md](../../sankhya/tabelas/TGFCOT.md)

### Sistema de Pesos

TGFCOT permite configurar pesos para avaliacao automatica:

| Criterio | Campo |
|----------|-------|
| Preco | PESOPRECO |
| Condicao Pagamento | PESOCONDPAG |
| Prazo Entrega | PESOPRAZOENTREG |
| Qualidade Produto | PESOQUALPROD |
| Confiabilidade Fornecedor | PESOCONFIABFORN |

### Fluxo com Cotacao

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Solicitacao │───>│  Cotacao    │───>│  Melhor     │───>│  Pedido     │
│  TIPMOV='J' │    │  TGFCOT     │    │  Proposta   │    │  TIPMOV='O' │
│  TOP 1804   │    │             │    │  Avaliada   │    │  TOP 1301   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## Fluxo Detalhado com Tabelas

### Cenario 1: Compra Padrao com Pedido

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Solicitacao │───>│  Pedido de  │───>│ Recebimento │───>│  Entrada    │
│  TOP 1804   │    │   Compra    │    │   Fisico    │    │  TOP 1209   │
│  TIPMOV=J   │    │  TOP 1301   │    │             │    │  TIPMOV=C   │
│             │    │  TIPMOV=O   │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                                      │
      ▼                  ▼                                      ▼
┌─────────────┐    ┌─────────────┐                       ┌─────────────┐
│   TGFCAB    │    │   TGFCAB    │                       │   TGFCAB    │
│   TGFITE    │    │   TGFITE    │                       │   TGFITE    │
│ (sem EST)   │    │ (sem EST)   │                       │   TGFEST +  │
│ (sem FIN)   │    │ (sem FIN)   │                       │   TGFFIN    │
└─────────────┘    └─────────────┘                       └─────────────┘
```

**Passos:**
1. Usuario identifica necessidade e cria solicitacao (TOP 1804)
   - Cria TGFCAB com TIPMOV='J'
   - Cria TGFITE com produtos solicitados
   - **Nao afeta TGFEST nem TGFFIN**
2. Comprador negocia com fornecedor
3. Comprador cria pedido de compra (TOP 1301)
   - Cria TGFCAB com TIPMOV='O'
   - Cria TGFITE com quantidades/precos negociados
   - **Nao afeta TGFEST nem TGFFIN**
4. Fornecedor envia mercadoria com NFe
5. Recebimento confere mercadoria
6. Entrada da nota fiscal (TOP 1209)
   - Cria TGFCAB com TIPMOV='C', STATUSNOTA='A'
   - Cria TGFITE com quantidades recebidas
7. Confirma nota (STATUSNOTA='L')
   - **TGFEST**: Incrementa estoque (ATUALEST = E)
   - **TGFFIN**: Cria titulo a pagar (ATUALFIN = -1)

### Cenario 2: Compra Direta (sem pedido)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ NFe chega   │───>│  Digitacao  │───>│ Confirmacao │───>│  Impacto    │
│ do fornec.  │    │  TGFCAB     │    │ STATUSNOTA  │    │  Sistema    │
│             │    │  TGFITE     │    │  'A' -> 'L' │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                               │
                          ┌────────────────────────────────────┼─────────────┐
                          ▼                                    ▼             ▼
                   ┌─────────────┐                      ┌─────────────┐┌─────────────┐
                   │   TGFEST    │                      │   TGFFIN    ││   TGFLIB    │
                   │   +QTDNEG   │                      │ RECDESP=-1  ││ (se aprova) │
                   └─────────────┘                      └─────────────┘└─────────────┘
```

**Passos:**
1. NFe do fornecedor chega
2. Comprador lanca entrada (TOP 1209)
   - Cria TGFCAB com TIPMOV='C'
   - Cria TGFITE com produtos
3. Confirma nota
   - Sistema adiciona ao estoque (TGFEST.ESTOQUE += QTDNEG)
   - Sistema cria titulo a pagar (TGFFIN com RECDESP=-1)
4. Processo concluido

---

## Impacto no Estoque (TGFEST)

### Compra Efetiva (TOP 1209, 1401, 1452)

Quando STATUSNOTA muda para 'L' e TOP tem ATUALEST = 'E':

```sql
-- Sistema incrementa estoque
UPDATE TGFEST SET
    ESTOQUE = ESTOQUE + [QTDNEG do item]
WHERE CODEMP = [empresa da nota]
  AND CODLOCAL = [local destino]
  AND CODPROD = [produto]
  AND CONTROLE = [controle/lote]
  AND TIPO = 'P'
  AND CODPARC = 0;

-- Se registro nao existe, cria
INSERT INTO TGFEST (CODEMP, CODLOCAL, CODPROD, CONTROLE, TIPO, CODPARC, ESTOQUE, ...)
VALUES ([empresa], [local], [produto], [controle], 'P', 0, [QTDNEG], ...);
```

### Chave do Estoque

A posicao de estoque eh identificada por 6 campos:
- **CODEMP** - Empresa/filial
- **CODLOCAL** - Local/deposito
- **CODPROD** - Produto
- **CONTROLE** - Lote/serie (vazio se nao usa)
- **TIPO** - 'P' para proprio
- **CODPARC** - 0 para estoque proprio

### Compra de Servico (TOP 1404)

```sql
-- Nao afeta estoque (ATUALEST = N)
-- Servico nao eh estocavel
```

---

## Impacto no Financeiro (TGFFIN)

### Compra gera titulo a pagar (ATUALFIN = -1)

Quando STATUSNOTA muda para 'L' e TOP tem ATUALFIN = -1:

```sql
-- Sistema cria titulo(s) a pagar
INSERT INTO TGFFIN (
    NUFIN,           -- Sequencial unico
    CODEMP,          -- Empresa da compra
    NUNOTA,          -- Vinculo com TGFCAB
    CODPARC,         -- Fornecedor
    RECDESP,         -- -1 (PAGAR)
    VLRDESDOB,       -- Valor da parcela
    DTVENC,          -- Data vencimento
    DTNEG,           -- Data negociacao
    PROVISAO,        -- 'S' (ate pagar)
    ...
) VALUES (...);
```

### Campos criados automaticamente

| Campo TGFFIN | Origem | Descricao |
|--------------|--------|-----------|
| NUFIN | Sequencial | ID unico do titulo |
| NUNOTA | TGFCAB.NUNOTA | Vinculo com a nota |
| CODPARC | TGFCAB.CODPARC | Fornecedor |
| CODEMP | TGFCAB.CODEMP | Empresa |
| VLRDESDOB | TGFCAB.VLRNOTA / parcelas | Valor da parcela |
| DTVENC | Condicao pagamento | Calculado |
| RECDESP | -1 | Sempre -1 para compra |
| PROVISAO | 'S' | Vira 'N' ao baixar |

### Bonificacao nao gera financeiro

```sql
-- TOP 1451 tem ATUALFIN = 0
-- Mercadoria entra mas nao gera divida
```

---

## Sistema de Aprovacoes

### TGFLIB (Tabela Padrao Sankhya)

**Status:** VAZIA (0 registros) - MMarra nao usa sistema padrao

| Campo | Tipo | Descricao |
|-------|------|-----------|
| NUNOTA | NUMBER | Nota aprovada |
| CODUSU | NUMBER | Usuario que aprovou |
| DT | DATE | Data/hora aprovacao |
| LIBERACOES | VARCHAR2(50) | Tipo de liberacao |
| OBS | VARCHAR2(255) | Observacao |

Documentacao: [TGFLIB.md](../../sankhya/tabelas/TGFLIB.md)

### Sistema Customizado MMarra

| Tabela | Uso |
|--------|-----|
| AD_APROVACAO | Aprovacoes customizadas |
| AD_LIBERACOESVENDA | Liberacoes de venda |

**MMarra utiliza tabelas AD_* para aprovacoes, nao o sistema padrao TGFLIB.**

### Fluxo com Aprovacao

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Nota      │───>│  Pendente   │───>│  Aprovacao  │───>│  Liberada   │
│ STATUSNOTA  │    │ STATUSNOTA  │    │  AD_* ou    │    │ STATUSNOTA  │
│    = 'A'    │    │    = 'P'    │    │  manual     │    │    = 'L'    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

---

## Campos Importantes

### TGFCAB (Cabecalho)

| Campo | Descricao | Valores Compra |
|-------|-----------|----------------|
| NUNOTA | Numero unico da nota | Sequencial |
| CODTIPOPER | TOP usada | 1209, 1401, 1804... |
| TIPMOV | Tipo movimento | C (compra), O (pedido), J (solicitacao) |
| STATUSNOTA | Status | A (aberta), P (pendente), L (liberada) |
| CODPARC | Fornecedor | FK para TGFPAR |
| CODVEND | Comprador | FK para TGFVEN (TIPVEND = C) |
| CODEMP | Empresa compradora | FK para TSIEMP |
| VLRNOTA | Valor total | Valor da compra |
| DTNEG | Data negociacao | Data da compra |
| NUMNOTA | Numero NFe fornecedor | Numero externo |
| SERIENOTA | Serie NFe fornecedor | Serie externa |
| PENDENTE | Flag pendencia | S/N |
| APROVADO | Flag aprovacao | S/N |

### TGFITE (Itens)

| Campo | Descricao |
|-------|-----------|
| NUNOTA | Nota pai |
| SEQUENCIA | Sequencia do item |
| CODPROD | Produto comprado |
| QTDNEG | Quantidade comprada |
| VLRUNIT | Valor unitario |
| VLRTOT | Valor total item |
| CODLOCALORIG | Local estoque destino |

---

## Queries Uteis

### Compras do mes por fornecedor

```sql
SELECT P.CODPARC, P.NOMEPARC,
       COUNT(*) AS QTD_COMPRAS,
       SUM(C.VLRNOTA) AS VLR_TOTAL
FROM TGFCAB C
JOIN TGFPAR P ON C.CODPARC = P.CODPARC
WHERE C.TIPMOV = 'C'
  AND C.CODTIPOPER = 1209
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
GROUP BY P.CODPARC, P.NOMEPARC
ORDER BY VLR_TOTAL DESC
```

### Compras por status

```sql
SELECT
    C.STATUSNOTA,
    CASE C.STATUSNOTA
        WHEN 'L' THEN 'Liberada'
        WHEN 'P' THEN 'Pendente'
        WHEN 'A' THEN 'Aberta'
    END AS DESCRICAO,
    COUNT(*) AS QTD,
    SUM(C.VLRNOTA) AS VLR_TOTAL
FROM TGFCAB C
WHERE C.TIPMOV = 'C'
GROUP BY C.STATUSNOTA
ORDER BY QTD DESC
```

### Notas de compra com titulos gerados

```sql
SELECT
    C.NUNOTA,
    C.CODTIPOPER,
    C.VLRNOTA,
    COUNT(F.NUFIN) AS QTD_TITULOS,
    SUM(F.VLRDESDOB) AS VLR_TITULOS
FROM TGFCAB C
LEFT JOIN TGFFIN F ON C.NUNOTA = F.NUNOTA
WHERE C.TIPMOV = 'C'
  AND C.STATUSNOTA = 'L'
GROUP BY C.NUNOTA, C.CODTIPOPER, C.VLRNOTA
HAVING COUNT(F.NUFIN) > 0
ORDER BY C.NUNOTA DESC
```

### Compras que atualizaram estoque

```sql
SELECT
    I.NUNOTA, I.CODPROD, I.QTDNEG,
    C.CODTIPOPER, T.ATUALEST,
    P.DESCRPROD
FROM TGFITE I
JOIN TGFCAB C ON I.NUNOTA = C.NUNOTA
JOIN TGFTOP T ON C.CODTIPOPER = T.CODTIPOPER AND C.DHTIPOPER = T.DHALTER
JOIN TGFPRO P ON I.CODPROD = P.CODPROD
WHERE C.TIPMOV = 'C'
  AND T.ATUALEST = 'E'
  AND C.STATUSNOTA = 'L'
ORDER BY I.NUNOTA DESC
```

### Solicitacoes de compra abertas

```sql
SELECT C.NUNOTA, C.DTNEG, C.VLRNOTA, C.STATUSNOTA
FROM TGFCAB C
WHERE C.TIPMOV = 'J'
  AND C.CODTIPOPER = 1804
  AND C.STATUSNOTA <> 'L'
ORDER BY C.DTNEG
```

### Titulos a pagar de compras

```sql
SELECT
    F.NUFIN, F.NUNOTA, F.CODPARC,
    P.NOMEPARC AS FORNECEDOR,
    F.DTVENC, F.VLRDESDOB,
    F.PROVISAO, F.DHBAIXA
FROM TGFFIN F
JOIN TGFPAR P ON F.CODPARC = P.CODPARC
WHERE F.RECDESP = -1
  AND F.DHBAIXA IS NULL
ORDER BY F.DTVENC
```

---

## Compradores MMarra

Baseado nos dados extraidos (TIPVEND = C):

| CODVEND | Nome | Email |
|---------|------|-------|
| 3 | JULIANO MARCHEZAM | juliano.marchezan@mmarra.com.br |
| 4 | BRUNO JERONIMO | bruno.jeronimo@mmarra.com.br |
| 5 | JULIANO NOVAES | juliano.novaes@mmarra.com.br |
| 6 | FELIPE PEREIRA | felipe.pereira@mmarra.com.br |
| 7 | NEVES | neves@mmarra.com.br |
| 8 | GUILHERME TRINDADE | guilherme@mmarra.com.br |
| 9 | PAULO BOVO | paulo.bovo@mmarra.com.br |
| 56 | EDUARDO PUTINATTO | - |

---

## Estatisticas MMarra

| Metrica | Valor |
|---------|-------|
| **Solicitacoes compra (TIPMOV=J)** | 2.868 (R$ 6.05M) |
| **Cotacoes (TGFCOT)** | 2.839 |
| **Pedidos compra (TIPMOV=O)** | 2.148 (R$ 15.43M) |
| **Compras efetivas (TOP 1209)** | 47.523 (R$ 382M) |
| Transferencias entrada | 21.276 (R$ 46M) |
| Qtd compradores | 20 |
| Posicoes estoque (TGFEST) | 36.769 |
| Titulos a pagar (TGFFIN) | 17.906 (R$ 113M) |
| Notas liberadas | 76.313 |
| Notas pendentes | 242 |
| Notas abertas | 165 |
| TGFLIB (aprovacoes) | 0 (vazia, usa AD_*) |
| TGFSOL (solicitacoes) | 0 (vazia, usa TGFCAB) |

---

## Fornecedores Principais

Os produtos MMarra vem principalmente de:
- **Cummins** - 44k SKUs (maior fornecedor)
- **MWM** - 15k SKUs
- **ZF** - 14k SKUs
- **Eaton** - 11k SKUs
- **Navistar** - 10k SKUs

---

## Observacoes

1. **TOP 1209 eh a principal** - Representa a grande maioria das compras de mercadoria
2. **Transferencia entrada (1452)** - Recebe mercadoria de outras filiais, nao gera financeiro
3. **Bonificacao entrada (1451)** - Entrada sem custo, promocoes de fornecedores
4. **Compra servico (1404)** - Nao afeta estoque, apenas financeiro
5. **NUMNOTA e SERIENOTA** - Armazena dados da NFe do fornecedor
6. **20 compradores ativos** - Equipe dedicada para compras
7. **STATUSNOTA controla o fluxo** - A->P->L ou A->L direto
8. **TGFLIB registra aprovacoes** - Quando nota precisa liberacao
9. **Vinculo via NUNOTA** - Liga TGFCAB -> TGFFIN e TGFCAB -> TGFLIB

---

## Processos Relacionados

- [Fluxo de Venda](../vendas/fluxo_venda.md) - Venda das mercadorias compradas
- [Devolucao de Compra](devolucao_compra.md) - Quando devolve ao fornecedor
- [Transferencia](../estoque/transferencia.md) - Movimentacao entre filiais

---

## Tabelas Documentadas

- [TGFCAB](../../sankhya/tabelas/TGFCAB.md) - Cabecalho das notas
- [TGFITE](../../sankhya/tabelas/TGFITE.md) - Itens das notas
- [TGFCOT](../../sankhya/tabelas/TGFCOT.md) - Cotacoes de compra
- [TGFLIB](../../sankhya/tabelas/TGFLIB.md) - Liberacoes/aprovacoes
- [TGFPAR](../../sankhya/tabelas/TGFPAR.md) - Parceiros/Fornecedores
- [TGFPRO](../../sankhya/tabelas/TGFPRO.md) - Produtos
- [TGFTOP](../../sankhya/tabelas/TGFTOP.md) - Tipos de operacao
- [TGFVEN](../../sankhya/tabelas/TGFVEN.md) - Vendedores/Compradores
- [TSIEMP](../../sankhya/tabelas/TSIEMP.md) - Empresas
- [TGFEST](../../sankhya/tabelas/TGFEST.md) - Estoque
- [TGFFIN](../../sankhya/tabelas/TGFFIN.md) - Financeiro
