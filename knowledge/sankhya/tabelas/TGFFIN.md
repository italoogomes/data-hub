# TGFFIN

**Descricao:** Titulos financeiros (contas a receber e a pagar). Armazena todas as parcelas, vencimentos, baixas e informacoes de cobranca.

**Total de registros:** 54.441

---

## Resumo por Tipo

| RECDESP | Tipo | Qtd Titulos | Valor Total |
|---------|------|-------------|-------------|
| 1 | A Receber | 36.408 | R$ 46.482.415,97 |
| -1 | A Pagar | 17.906 | R$ 113.433.634,72 |
| 0 | Outros | 127 | R$ 156.236,76 |

---

## Campos Principais

| Campo | Tipo | Tamanho | Obrig. | PK | Descricao |
|-------|------|---------|--------|----|----|
| NUFIN | NUMBER | 22 | Sim | PK | Numero unico do titulo |
| CODEMP | NUMBER | 22 | Sim | FK | Empresa do titulo |
| NUNOTA | NUMBER | 22 | Nao | FK | Nota de origem |
| CODPARC | NUMBER | 22 | Sim | FK | Parceiro (cliente/fornecedor) |
| RECDESP | NUMBER | 22 | Sim | - | 1=Receber, -1=Pagar, 0=Outros |
| VLRDESDOB | FLOAT | 22 | Sim | - | Valor do desdobramento/parcela |
| DTVENC | DATE | 7 | Nao | - | Data de vencimento |
| DTNEG | DATE | 7 | Sim | - | Data da negociacao |
| PROVISAO | VARCHAR2 | 1 | Sim | - | S=Provisao, N=Real |

---

## Campos de Identificacao

| Campo | Tipo | Tamanho | Descricao |
|-------|------|---------|-----------|
| NUFIN | NUMBER | 22 | PK - Numero unico do titulo |
| CODEMP | NUMBER | 22 | Empresa dona do titulo |
| NUMNOTA | NUMBER | 22 | Numero da nota fiscal |
| SERIENOTA | VARCHAR2 | 3 | Serie da nota fiscal |
| NUNOTA | NUMBER | 22 | FK para TGFCAB (nota origem) |
| DESDOBRAMENTO | VARCHAR2 | 7 | Identificador da parcela (001, 002...) |
| NUMDUPL | NUMBER | 22 | Numero da duplicata |
| DESDOBDUPL | VARCHAR2 | 2 | Desdobramento da duplicata |
| NOSSONUM | VARCHAR2 | 12 | Nosso numero (boleto bancario) |

---

## Campos de Data

| Campo | Tipo | Descricao |
|-------|------|-----------|
| DTNEG | DATE | Data da negociacao/emissao |
| DHMOV | DATE | Data/hora do movimento |
| DTVENCINIC | DATE | Data vencimento inicial (original) |
| DTVENC | DATE | Data vencimento atual |
| DHBAIXA | DATE | Data/hora da baixa |
| DTCONTAB | DATE | Data de contabilizacao |
| DTCONTABBAIXA | DATE | Data contabilizacao da baixa |
| DTBAIXAPREV | DATE | Data baixa prevista |
| DTENTSAI | DATE | Data entrada/saida |
| DTALTER | DATE | Data ultima alteracao |

---

## Campos de Valor

| Campo | Tipo | Descricao |
|-------|------|-----------|
| VLRDESDOB | FLOAT | Valor da parcela |
| VLRBAIXA | FLOAT | Valor baixado |
| VLRDESC | FLOAT | Valor de desconto |
| VLRMULTA | FLOAT | Valor da multa |
| VLRJURO | FLOAT | Valor de juros |
| VLRIRF | FLOAT | Valor IRF retido |
| VLRISS | FLOAT | Valor ISS retido |
| VLRINSS | FLOAT | Valor INSS retido |
| VLRVENDOR | FLOAT | Valor de vendor |
| VLRCHEQUE | FLOAT | Valor em cheque |
| VLRPROV | NUMBER | Valor provisionado |

---

## Campos de Classificacao

| Campo | Tipo | Tamanho | Descricao |
|-------|------|---------|-----------|
| CODPARC | NUMBER | 22 | FK - Parceiro |
| CODTIPOPER | NUMBER | 22 | FK - Tipo de operacao |
| DHTIPOPER | DATE | 7 | Data/hora da TOP |
| CODBCO | NUMBER | 22 | FK - Banco |
| CODCTABCOINT | NUMBER | 22 | FK - Conta bancaria |
| CODNAT | NUMBER | 22 | FK - Natureza |
| CODCENCUS | NUMBER | 22 | FK - Centro de custo |
| CODPROJ | NUMBER | 22 | FK - Projeto |
| CODVEND | NUMBER | 22 | FK - Vendedor |
| CODMOEDA | NUMBER | 22 | FK - Moeda |
| CODTIPTIT | NUMBER | 22 | FK - Tipo de titulo |

---

## Campos de Controle

| Campo | Tipo | Descricao |
|-------|------|-----------|
| RECDESP | NUMBER | Tipo: 1=Receber, -1=Pagar, 0=Outros |
| PROVISAO | VARCHAR2(1) | S=Provisao, N=Real |
| AUTORIZADO | VARCHAR2(1) | S=Autorizado, N=Nao |
| ORIGEM | VARCHAR2(1) | E=Manual, N=Nota |
| RATEADO | VARCHAR2(1) | S=Rateado, N=Nao |
| FINCONFIRMADO | CHAR(1) | S=Confirmado, N=Nao |

---

## Campos de Baixa

| Campo | Tipo | Descricao |
|-------|------|-----------|
| DHBAIXA | DATE | Data/hora da baixa |
| VLRBAIXA | FLOAT | Valor efetivamente baixado |
| CODEMPBAIXA | NUMBER | Empresa da baixa |
| CODTIPOPERBAIXA | NUMBER | TOP da baixa |
| DHTIPOPERBAIXA | DATE | Data/hora TOP baixa |
| CODUSUBAIXA | NUMBER | Usuario que baixou |

---

## Chave Primaria

```
PK: NUFIN (campo unico sequencial)
```

---

## Relacionamentos (FKs)

| Campo | Tabela | Campo Ref | Descricao |
|-------|--------|-----------|-----------|
| NUNOTA | TGFCAB | NUNOTA | Nota de origem |
| CODPARC | TGFPAR | CODPARC | Parceiro |
| CODEMP | TGFEMP | CODEMP | Empresa |
| CODBCO | TSIBCO | CODBCO | Banco |
| CODCTABCOINT | TSICTA | CODCTABCOINT | Conta bancaria |
| CODNAT | TGFNAT | CODNAT | Natureza financeira |
| CODCENCUS | TSICUS | CODCENCUS | Centro de custo |
| CODPROJ | TCSPRJ | CODPROJ | Projeto |
| CODVEND | TGFVEN | CODVEND | Vendedor |
| CODMOEDA | TSIMOE | CODMOEDA | Moeda |
| CODTIPTIT | TGFTIT | CODTIPTIT | Tipo de titulo |
| CODTIPOPER | TGFTOP | CODTIPOPER+DHALTER | TOP de origem |

---

## Valores de Dominio

### RECDESP (Tipo do Titulo)

| Valor | Significado | Uso |
|-------|-------------|-----|
| 1 | Receita/Receber | Vendas, receitas diversas |
| -1 | Despesa/Pagar | Compras, despesas diversas |
| 0 | Outros | Transferencias, ajustes |

### PROVISAO

| Valor | Significado |
|-------|-------------|
| S | Provisao - Titulo previsto mas nao realizado |
| N | Real - Titulo efetivo |

### AUTORIZADO

| Valor | Significado |
|-------|-------------|
| S | Sim - Autorizado para pagamento/recebimento |
| N | Nao - Aguardando autorizacao |

### ORIGEM

| Valor | Significado |
|-------|-------------|
| E | Manual - Criado manualmente |
| N | Nota - Gerado automaticamente por nota |

---

## Como Titulos Sao Criados

### Na Venda (ATUALFIN = 1)

Quando uma nota de venda eh confirmada com TOP que tem `ATUALFIN = 1`:

```sql
-- Sistema cria titulo a receber
INSERT INTO TGFFIN (
    NUFIN, CODEMP, NUNOTA, CODPARC,
    RECDESP, VLRDESDOB, DTVENC, PROVISAO
) VALUES (
    [sequencial],
    [empresa da nota],
    [NUNOTA da venda],
    [cliente],
    1,  -- RECEBER
    [valor da parcela],
    [data vencimento],
    'S'  -- Provisao ate baixar
)
```

### Na Compra (ATUALFIN = -1)

Quando uma nota de compra eh confirmada com TOP que tem `ATUALFIN = -1`:

```sql
-- Sistema cria titulo a pagar
INSERT INTO TGFFIN (
    NUFIN, CODEMP, NUNOTA, CODPARC,
    RECDESP, VLRDESDOB, DTVENC, PROVISAO
) VALUES (
    [sequencial],
    [empresa da nota],
    [NUNOTA da compra],
    [fornecedor],
    -1,  -- PAGAR
    [valor da parcela],
    [data vencimento],
    'S'
)
```

---

## Vinculo Nota -> Financeiro

Titulos sao vinculados a notas pelo campo `NUNOTA`:

```sql
-- Encontrar titulos de uma nota
SELECT * FROM TGFFIN WHERE NUNOTA = [numero_nota]
```

**Importante:** Nem toda nota gera financeiro:
- ATUALFIN = 0 nao gera titulos (transferencias, bonificacoes)
- Algumas notas podem ter NUNOTA = NULL em TGFFIN (titulos manuais)

---

## Queries Uteis

### Titulos a receber vencidos

```sql
SELECT
    F.NUFIN, F.CODPARC, P.NOMEPARC,
    F.DTVENC, F.VLRDESDOB,
    TRUNC(SYSDATE) - TRUNC(F.DTVENC) AS DIAS_ATRASO
FROM TGFFIN F
JOIN TGFPAR P ON F.CODPARC = P.CODPARC
WHERE F.RECDESP = 1
  AND F.DHBAIXA IS NULL
  AND F.DTVENC < TRUNC(SYSDATE)
ORDER BY DIAS_ATRASO DESC
```

### Titulos a pagar proximos 30 dias

```sql
SELECT
    F.NUFIN, F.CODPARC, P.NOMEPARC,
    F.DTVENC, F.VLRDESDOB, F.NUNOTA
FROM TGFFIN F
JOIN TGFPAR P ON F.CODPARC = P.CODPARC
WHERE F.RECDESP = -1
  AND F.DHBAIXA IS NULL
  AND F.DTVENC BETWEEN SYSDATE AND SYSDATE + 30
ORDER BY F.DTVENC
```

### Resumo financeiro por empresa

```sql
SELECT
    F.CODEMP,
    E.NOMEFANTASIA,
    SUM(CASE WHEN F.RECDESP = 1 AND F.DHBAIXA IS NULL THEN F.VLRDESDOB ELSE 0 END) AS A_RECEBER,
    SUM(CASE WHEN F.RECDESP = -1 AND F.DHBAIXA IS NULL THEN F.VLRDESDOB ELSE 0 END) AS A_PAGAR
FROM TGFFIN F
JOIN TSIEMP E ON F.CODEMP = E.CODEMP
GROUP BY F.CODEMP, E.NOMEFANTASIA
ORDER BY A_RECEBER DESC
```

### Titulos de uma nota especifica

```sql
SELECT
    F.NUFIN, F.DESDOBRAMENTO, F.DTVENC,
    F.VLRDESDOB, F.RECDESP,
    CASE F.RECDESP WHEN 1 THEN 'RECEBER' WHEN -1 THEN 'PAGAR' END AS TIPO,
    F.DHBAIXA
FROM TGFFIN F
WHERE F.NUNOTA = [numero_nota]
ORDER BY F.DTVENC
```

### Inadimplencia por cliente

```sql
SELECT
    P.CODPARC, P.NOMEPARC,
    COUNT(*) AS QTD_TITULOS,
    SUM(F.VLRDESDOB) AS VLR_VENCIDO,
    MIN(F.DTVENC) AS MAIS_ANTIGO,
    MAX(TRUNC(SYSDATE) - TRUNC(F.DTVENC)) AS MAIOR_ATRASO
FROM TGFFIN F
JOIN TGFPAR P ON F.CODPARC = P.CODPARC
WHERE F.RECDESP = 1
  AND F.DHBAIXA IS NULL
  AND F.DTVENC < TRUNC(SYSDATE)
GROUP BY P.CODPARC, P.NOMEPARC
ORDER BY VLR_VENCIDO DESC
```

---

## Campos Especificos de Impostos/Retencoes

| Campo | Descricao |
|-------|-----------|
| VLRIRF | Valor IRF retido |
| VLRISS | Valor ISS retido |
| VLRINSS | Valor INSS retido |
| IRFRETIDO | Flag se reteve IRF (S/N) |
| ISSRETIDO | Flag se reteve ISS (S/N) |
| INSSRETIDO | Flag se reteve INSS (S/N) |
| BASEIRF | Base de calculo IRF |
| BASEINSS | Base de calculo INSS |
| BASEICMS | Base de calculo ICMS |
| ALIQICMS | Aliquota ICMS |

---

## Campos de Boleto/Cobranca

| Campo | Descricao |
|-------|-----------|
| NOSSONUM | Nosso numero (boleto) |
| CODIGOBARRA | Codigo de barras |
| LINHADIGITAVEL | Linha digitavel |
| NUMREMESSA | Numero da remessa bancaria |
| CONVENIO | Convenio bancario |

---

## Campos Customizados MMarra (AD_)

| Campo | Descricao |
|-------|-----------|
| AD_UNICO | ID unico customizado |
| AD_CHAVENFEIMP | Chave NFe importacao |
| AD_DDACNPJ | CNPJ para DDA |
| AD_DDARAZAOSOCIAL | Razao social DDA |
| AD_IDEXTERNO | ID externo integracao |
| AD_VLRBASECOMINT | Valor base comissao |
| AD_VLRCOMINT | Valor comissao |
| AD_NOMEVEND_MMA | Nome vendedor MMarra |
| AD_CODVEND_MMA | Codigo vendedor MMarra |

---

## Estatisticas MMarra

| Metrica | Valor |
|---------|-------|
| Total titulos | 54.441 |
| A Receber | 36.408 (R$ 46,5M) |
| A Pagar | 17.906 (R$ 113,4M) |
| Outros | 127 |
| Ticket medio receber | R$ 1.277 |
| Ticket medio pagar | R$ 6.335 |

---

## Tabelas Relacionadas

| Tabela | Relacao |
|--------|---------|
| TGFCAB | Nota origem (NUNOTA) |
| TGFPAR | Parceiro (cliente/fornecedor) |
| TSIEMP/TGFEMP | Empresa |
| TSIBCO | Banco |
| TSICTA | Conta bancaria |
| TGFNAT | Natureza financeira |
| TSICUS | Centro de custo |
| TGFVEN | Vendedor |
| TGFTIT | Tipo de titulo |
| TGFTOP | Tipo de operacao |

---

## Observacoes

1. **NUFIN sequencial** - Cada titulo tem um numero unico
2. **NUNOTA pode ser NULL** - Para titulos criados manualmente
3. **PROVISAO = S** - Titulo esperado, vira N quando baixado
4. **DHBAIXA indica titulo pago/recebido** - NULL = em aberto
5. **Desdobramento** - Permite multiplas parcelas por nota
6. **RECDESP define direcao** - 1=entrada de dinheiro, -1=saida
7. **Campos AD_** - Customizacoes MMarra para integracao

---

## Processos que Criam Titulos

- [Fluxo de Venda](../../processos/vendas/fluxo_venda.md) - ATUALFIN = 1 cria a receber
- [Fluxo de Compra](../../processos/compras/fluxo_compra.md) - ATUALFIN = -1 cria a pagar
- [Devolucao Venda](../../processos/estoque/devolucao.md) - ATUALFIN = -1 cria credito cliente
- [Devolucao Compra](../../processos/estoque/devolucao.md) - ATUALFIN = 1 cria credito fornecedor
