# TGFCAB

**Descricao:** Cabecalho das notas/movimentacoes. Tabela central do comercial - armazena pedidos, notas fiscais, devolucoes e todas as movimentacoes de entrada/saida.

**Total de registros:** 343.215

---

## Campos Principais

| Campo | Tipo | Tamanho | Nulo | Descricao |
|-------|------|---------|------|-----------|
| NUNOTA | NUMBER | 22 | N | **PK** - Numero unico da nota (sequencial interno) |
| NUMNOTA | NUMBER | 22 | N | Numero da nota fiscal (pode repetir entre empresas) |
| SERIENOTA | VARCHAR2 | 3 | Y | Serie da nota fiscal |
| CODEMP | NUMBER | 22 | N | Codigo da empresa |
| CODPARC | NUMBER | 22 | N | Codigo do parceiro (cliente/fornecedor) |
| CODTIPOPER | NUMBER | 22 | N | Codigo da TOP (tipo de operacao) |
| TIPMOV | VARCHAR2 | 1 | N | Tipo de movimento (V/C/P/D/etc) |
| DTNEG | DATE | 7 | N | Data da negociacao |
| DTFATUR | DATE | 7 | Y | Data do faturamento |
| DTENTSAI | DATE | 7 | Y | Data de entrada/saida |
| VLRNOTA | FLOAT | 22 | N | Valor total da nota |
| VLRDESCTOT | FLOAT | 22 | N | Valor total de desconto |
| VLRFRETE | FLOAT | 22 | N | Valor do frete |
| STATUSNOTA | VARCHAR2 | 1 | N | Status da nota (L/P/A) |
| STATUSNFE | VARCHAR2 | 1 | Y | Status da NF-e (A/D/R/etc) |
| PENDENTE | VARCHAR2 | 1 | N | Indica se esta pendente (S/N) |
| CODVEND | NUMBER | 22 | N | Codigo do vendedor |
| CODPARCTRANSP | NUMBER | 22 | N | Codigo do parceiro transportador |
| CHAVENFE | VARCHAR2 | 44 | Y | Chave de acesso da NF-e |
| OBSERVACAO | VARCHAR2 | 4000 | Y | Observacoes da nota |

---

## Campos de Impostos

| Campo | Tipo | Descricao |
|-------|------|-----------|
| BASEICMS | FLOAT | Base de calculo ICMS |
| VLRICMS | FLOAT | Valor do ICMS |
| BASEIPI | FLOAT | Base de calculo IPI |
| VLRIPI | FLOAT | Valor do IPI |
| BASEISS | FLOAT | Base de calculo ISS |
| VLRISS | FLOAT | Valor do ISS |
| VLRSUBST | FLOAT | Valor ICMS-ST |
| BASESUBSTIT | FLOAT | Base ICMS-ST |
| BASEPIS | FLOAT | Base PIS |
| VLRPIS | FLOAT | Valor PIS |
| BASECOFINS | FLOAT | Base COFINS |
| VLRCOFINS | FLOAT | Valor COFINS |
| VLRIRF | FLOAT | Valor IR retido |
| VLRINSS | FLOAT | Valor INSS |

---

## Chave Primaria

| Campo | Constraint |
|-------|------------|
| NUNOTA | PK_TGFCAB |

---

## Relacionamentos (FK)

| Campo | Tabela Ref | Campo Ref | Descricao |
|-------|------------|-----------|-----------|
| CODEMP | TGFEMP | CODEMP | Empresa |
| CODPARC | TGFPAR | CODPARC | Parceiro (cliente/fornecedor) |
| CODPARCDEST | TGFPAR | CODPARC | Parceiro destino |
| CODPARCTRANSP | TGFPAR | CODPARC | Transportadora |
| CODTIPOPER + DHTIPOPER | TGFTOP | CODTIPOPER + DHALTER | Tipo de Operacao (TOP) |
| CODTIPVENDA + DHTIPVENDA | TGFTPV | CODTIPVENDA + DHALTER | Tipo de Venda |
| CODVEND | TGFVEN | CODVEND | Vendedor |
| CODCENCUS | TSICUS | CODCENCUS | Centro de custo |
| CODNAT | TGFNAT | CODNAT | Natureza |
| CODPROJ | TCSPRJ | CODPROJ | Projeto |
| CODVEICULO | TGFVEI | CODVEICULO | Veiculo |
| CODMOTORISTA | TGFPAR | CODPARC | Motorista |
| CODUSU | TSIUSU | CODUSU | Usuario |
| NUMCONTRATO | TCSCON | NUMCONTRATO | Contrato |
| NULOTENFE | TGFLNF | NULOTE | Lote NF-e |

---

## Valores de Dominio

### TIPMOV - Tipo de Movimento

| Valor | Significado | Quantidade |
|-------|-------------|------------|
| V | Venda | 249.724 |
| C | Compra | 71.760 |
| P | Pedido | 9.824 |
| D | Devolucao | 5.888 |
| J | Ajuste | 2.795 |
| O | Orcamento | 2.083 |
| E | Entrada | 823 |
| Z | Saldo Inicial | 143 |
| N | Nota Complementar | 141 |
| T | Transferencia | 5 |

### STATUSNOTA - Status da Nota

| Valor | Significado | Quantidade |
|-------|-------------|------------|
| L | Liberada | 341.713 |
| P | Pendente | 1.241 |
| A | Aguardando Aprovacao | 261 |

### STATUSNFE - Status NF-e

| Valor | Significado | Quantidade |
|-------|-------------|------------|
| A | Autorizada | 7.983 |
| D | Denegada | 773 |
| R | Rejeitada | 19 |
| V | Validada | 4 |
| I | Inutilizada | 2 |
| S | Em processamento | 1 |

### PENDENTE - Pendencia

| Valor | Significado | Quantidade |
|-------|-------------|------------|
| S | Sim (pendente) | 323.311 |
| N | Nao (processado) | 19.904 |

---

## Campos Customizados (AD_)

Campos que comecam com `AD_` sao customizados da MMarra:

| Campo | Tipo | Descricao |
|-------|------|-----------|
| AD_INF | CLOB | Informacoes adicionais |
| AD_NUOS | NUMBER | Numero da OS |
| AD_NUMIARA | VARCHAR2 | Numero IARA |
| AD_NUNOTAMAE | VARCHAR2 | Numero nota mae |
| AD_TIPOSROTA | VARCHAR2 | Tipo de rota |
| AD_NUMPEDCLIENTE | VARCHAR2 | Numero pedido cliente |
| AD_OBSINTERNO | VARCHAR2 | Observacao interna |
| AD_MARGEM | FLOAT | Margem |

---

## Tabelas Relacionadas

- **TGFITE** - Itens da nota (detalhe)
- **TGFPAR** - Parceiros (cliente/fornecedor)
- **TGFTOP** - Tipo de Operacao
- **TGFEMP** - Empresas
- **TGFVEN** - Vendedores
- **TGFPRO** - Produtos (via TGFITE)
- **TGFFIN** - Financeiro (titulos)

---

## Queries Uteis

### Vendas do mes
```sql
SELECT NUNOTA, NUMNOTA, DTNEG, CODPARC, VLRNOTA
FROM TGFCAB
WHERE TIPMOV = 'V'
  AND DTNEG >= TRUNC(SYSDATE, 'MM')
  AND STATUSNOTA = 'L'
ORDER BY DTNEG DESC
```

### Notas pendentes de NF-e
```sql
SELECT NUNOTA, NUMNOTA, DTNEG, CODPARC, VLRNOTA, STATUSNFE
FROM TGFCAB
WHERE TIPMOV = 'V'
  AND STATUSNOTA = 'L'
  AND (STATUSNFE IS NULL OR STATUSNFE NOT IN ('A', 'D'))
ORDER BY DTNEG
```

---

## Observacoes

- NUNOTA e o identificador unico interno, NUMNOTA e o numero da NF (pode repetir)
- Para vendas, usar `TIPMOV = 'V'` e `STATUSNOTA = 'L'`
- A chave da TOP e composta: CODTIPOPER + DHTIPOPER (versao historica)
- Campos AD_ sao customizacoes da MMarra
- Total de ~300 campos na tabela (muitos de NF-e, CT-e, etc)

---

*Documentado em: 2026-02-05*
