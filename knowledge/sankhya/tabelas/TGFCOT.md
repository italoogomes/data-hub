# TGFCOT

**Descricao:** Cabecalho de cotacoes de compra. Armazena solicitacoes de cotacao enviadas a fornecedores para comparacao de precos e condicoes.

**Total de registros:** 2.839

---

## Campos

### Identificacao

| Campo | Tipo | Tamanho | PK | Permite Nulo | Descricao |
|-------|------|---------|----|--------------| ----------|
| NUMCOTACAO | NUMBER | 22 | PK | N | Numero unico da cotacao |
| CODEMP | NUMBER | 22 | | S | Empresa da cotacao |
| SITUACAO | VARCHAR2 | 1 | | S | Status da cotacao (default 'A') |
| DTALTER | DATE | 7 | | N | Data alteracao (default SYSDATE) |

### Periodo

| Campo | Tipo | Tamanho | Permite Nulo | Descricao |
|-------|------|---------|--------------|-----------|
| DHINIC | DATE | 7 | S | Data/hora inicio cotacao |
| DHFINAL | DATE | 7 | S | Data/hora fim cotacao |
| PRAZOENTREGA | NUMBER | 22 | S | Prazo entrega em dias |

### Usuarios

| Campo | Tipo | Tamanho | Permite Nulo | Descricao |
|-------|------|---------|--------------|-----------|
| CODUSURESP | NUMBER | 22 | N | Usuario responsavel pela cotacao |
| CODUSUREQ | NUMBER | 22 | N | Usuario requisitante (default 0) |
| CODUSU | NUMBER | 22 | S | Usuario criador |

### Pesos para Comparacao (0-100)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| PESOPRECO | NUMBER | Peso do preco na avaliacao |
| PESOCONDPAG | NUMBER | Peso da condicao de pagamento |
| PESOTAXAJURO | NUMBER | Peso da taxa de juros |
| PESOPRAZOENTREG | NUMBER | Peso do prazo de entrega |
| PESOQUALPROD | NUMBER | Peso da qualidade do produto |
| PESOCONFIABFORN | NUMBER | Peso da confiabilidade do fornecedor |
| PESOQUALATEND | NUMBER | Peso da qualidade do atendimento |
| PESOGARANTIA | NUMBER | Peso da garantia |
| PESOPRAZOMED | NUMBER | Peso do prazo medio |
| PESOAVALFORNEC | NUMBER | Peso da avaliacao do fornecedor |

### Classificacao Contabil

| Campo | Tipo | Tamanho | Permite Nulo | Descricao |
|-------|------|---------|--------------|-----------|
| CODNAT | NUMBER | 22 | N | Natureza financeira (default 0) |
| CODCENCUS | NUMBER | 22 | N | Centro de custo (default 0) |
| CODPROJ | NUMBER | 22 | N | Projeto (default 0) |
| CODTIPVENDA | NUMBER | 22 | S | Tipo de negociacao |

### Origem/Referencia

| Campo | Tipo | Tamanho | Permite Nulo | Descricao |
|-------|------|---------|--------------|-----------|
| NUNOTAORIG | NUMBER | 22 | S | NUNOTA origem (solicitacao) |
| NUMNOTAORIG | NUMBER | 22 | S | Numero nota origem |
| NUSCR | NUMBER | 22 | S | Numero solicitacao compra |
| SEQSCR | NUMBER | 22 | S | Sequencia solicitacao |

### Logistica

| Campo | Tipo | Tamanho | Permite Nulo | Descricao |
|-------|------|---------|--------------|-----------|
| LOCALENTREGA | VARCHAR2 | 100 | S | Local de entrega |
| LOCALCOLETA | VARCHAR2 | 40 | S | Local de coleta |
| MODFRETE | VARCHAR2 | 1 | S | Modalidade frete (C/F) |

### Outros

| Campo | Tipo | Tamanho | Permite Nulo | Descricao |
|-------|------|---------|--------------|-----------|
| GERPEDREAL | VARCHAR2 | 1 | S | Gera pedido real (default 'S') |
| VALPROPOSTA | NUMBER | 22 | S | Valor da proposta |
| OBSERVACAO | VARCHAR2 | 4000 | S | Observacoes |
| CODMOTCAN | NUMBER | 22 | S | Motivo cancelamento |
| OBSMOTCANC | VARCHAR2 | 255 | S | Obs motivo cancelamento |

---

## Chaves

### Chave Primaria (PK)
- **PK_TGFCOT:** NUMCOTACAO

### Chaves Estrangeiras (FK)
| Campo | Tabela Referenciada | Campo Referenciado |
|-------|--------------------|--------------------|
| CODCENCUS | TSICUS | CODCENCUS |
| CODEMP | TGFEMP | CODEMP |
| CODMOTCAN | TGFMTC | CODIGO |
| CODNAT | TGFNAT | CODNAT |
| CODPROJ | TCSPRJ | CODPROJ |
| CODUSU | TSIUSU | CODUSU |
| CODUSUREQ | TSIUSU | CODUSU |
| CODUSURESP | TSIUSU | CODUSU |

---

## Valores de Dominio

### SITUACAO (Status da Cotacao)

| Valor | Significado |
|-------|-------------|
| A | Aberta (default) |
| F | Finalizada |
| C | Cancelada |
| E | Em andamento |

### MODFRETE (Modalidade de Frete)

| Valor | Significado |
|-------|-------------|
| C | CIF - Fornecedor paga frete |
| F | FOB - Comprador paga frete |

### GERPEDREAL

| Valor | Significado |
|-------|-------------|
| S | Sim - Gera pedido de compra |
| N | Nao - Apenas cotacao |

---

## Tabelas Relacionadas

### Itens da Cotacao
- **TGFCOI** - Itens cotados (VAZIA na MMarra)
- **TGFCOC** - Fornecedores cotados (VAZIA na MMarra)
- **AD_COTACOESDEITENS** - Customizacao MMarra

### Outras
- **TGFITC_COT** - Itens customizados
- **TSICOT** - Configuracoes de cotacao

---

## Fluxo de Cotacao

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Solicitacao │───>│  Cotacao    │───>│  Analise    │───>│  Pedido     │
│  Compra     │    │  TGFCOT     │    │  Respostas  │    │  Compra     │
│  TIPMOV='J' │    │ SITUACAO=A  │    │  dos Forn.  │    │  TIPMOV='O' │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

**Passos:**
1. Solicitacao de compra identificada (TGFCAB TIPMOV='J')
2. Comprador abre cotacao (INSERT em TGFCOT)
3. Sistema envia para fornecedores (via portal/email)
4. Fornecedores respondem com precos e condicoes
5. Comprador avalia usando pesos configurados
6. Melhor proposta vira Pedido de Compra (GERPEDREAL='S')

---

## Sistema de Pesos

A MMarra pode configurar pesos para avaliacao automatica:

| Criterio | Campo | Importancia |
|----------|-------|-------------|
| Preco | PESOPRECO | Mais barato, melhor |
| Condicao Pagamento | PESOCONDPAG | Maior prazo, melhor |
| Taxa Juros | PESOTAXAJURO | Menor taxa, melhor |
| Prazo Entrega | PESOPRAZOENTREG | Mais rapido, melhor |
| Qualidade Produto | PESOQUALPROD | Maior qualidade, melhor |
| Confiabilidade | PESOCONFIABFORN | Mais confiavel, melhor |
| Atendimento | PESOQUALATEND | Melhor atendimento, melhor |
| Garantia | PESOGARANTIA | Maior garantia, melhor |

**Soma dos pesos deve ser 100.**

---

## Queries Uteis

### Cotacoes abertas

```sql
SELECT
    NUMCOTACAO,
    DHINIC,
    DHFINAL,
    SITUACAO,
    OBSERVACAO
FROM TGFCOT
WHERE SITUACAO = 'A'
ORDER BY DHINIC DESC
```

### Cotacoes por periodo

```sql
SELECT
    TO_CHAR(DHINIC, 'YYYY-MM') AS MES,
    COUNT(*) AS QTD_COTACOES,
    SUM(VALPROPOSTA) AS VLR_TOTAL
FROM TGFCOT
WHERE DHINIC IS NOT NULL
GROUP BY TO_CHAR(DHINIC, 'YYYY-MM')
ORDER BY MES DESC
```

### Cotacoes por usuario responsavel

```sql
SELECT
    c.CODUSURESP,
    u.NOMEUSU,
    COUNT(*) AS QTD_COTACOES
FROM TGFCOT c
JOIN TSIUSU u ON c.CODUSURESP = u.CODUSU
GROUP BY c.CODUSURESP, u.NOMEUSU
ORDER BY QTD_COTACOES DESC
```

### Cotacoes originadas de solicitacao

```sql
SELECT
    c.NUMCOTACAO,
    c.NUNOTAORIG,
    cab.NUMNOTA AS NUM_SOLICITACAO,
    c.SITUACAO
FROM TGFCOT c
JOIN TGFCAB cab ON c.NUNOTAORIG = cab.NUNOTA
WHERE c.NUNOTAORIG IS NOT NULL
ORDER BY c.NUMCOTACAO DESC
```

---

## Estatisticas MMarra

| Metrica | Valor |
|---------|-------|
| Total cotacoes | 2.839 |
| TGFCOI (itens) | 0 (vazia) |
| TGFCOC (fornecedores) | 0 (vazia) |

**Observacao:** Itens e fornecedores cotados podem estar em tabelas customizadas (AD_COTACOESDEITENS).

---

## Observacoes

1. **2.839 cotacoes** - MMarra usa processo de cotacao
2. **Tabelas de itens vazias** - Pode usar customizacao AD_*
3. **Sistema de pesos** - Permite avaliacao automatica de propostas
4. **Vinculo com solicitacao** - NUNOTAORIG liga com TGFCAB
5. **Gera pedido** - GERPEDREAL='S' cria pedido automaticamente
6. **Centro de custo** - Permite classificacao contabil
7. **Modalidade frete** - CIF/FOB definido na cotacao

---

## Processos Relacionados

- [Fluxo de Compra](../../processos/compras/fluxo_compra.md) - Processo completo
- [TGFCAB](TGFCAB.md) - Solicitacoes e pedidos
- [TGFPAR](TGFPAR.md) - Fornecedores

---

*Documentado em: 2026-02-06*
