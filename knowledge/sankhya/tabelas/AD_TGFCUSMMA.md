# AD_TGFCUSMMA

**Descricao:** Historico de custos de produtos. Armazena diferentes tipos de custo (com ICMS, sem ICMS, reposicao, gerencial, variavel) ao longo do tempo.

**Total de registros:** 709.230

**Tipo:** Tabela customizada MMarra (AD_*)

---

## Campos

| Campo | Tipo | Tamanho | PK | Descricao |
|-------|------|---------|----| ----------|
| SEQUENCIA | NUMBER | 22 | PK | ID sequencial do registro |
| CODPROD | NUMBER | 22 | | Codigo do produto |
| CODEMP | NUMBER | 22 | | Codigo da empresa |
| CUSCOMICM | FLOAT | 22 | | Custo COM ICMS |
| CUSREP | FLOAT | 22 | | Custo de reposicao |
| CUSSEMICM | FLOAT | 22 | | Custo SEM ICMS |
| CUSGER | FLOAT | 22 | | Custo gerencial |
| CUSVARIAVEL | FLOAT | 22 | | Custo variavel |
| CUSMEDSEMICM | FLOAT | 22 | | Custo medio SEM ICMS |
| DTATUAL | DATE | 7 | | Data da atualizacao |

---

## Chaves

### Chave Primaria (PK)
- **SEQUENCIA**

### Chaves Estrangeiras (FK)
| Campo | Tabela Referenciada | Campo Referenciado |
|-------|--------------------|--------------------|
| CODPROD | TGFPRO | CODPROD |
| CODEMP | TSIEMP | CODEMP |

---

## Tipos de Custo

| Campo | Descricao | Uso |
|-------|-----------|-----|
| CUSCOMICM | Custo com ICMS incluso | Base para margem bruta |
| CUSSEMICM | Custo sem ICMS | Custo liquido |
| CUSREP | Custo de reposicao | Quanto custa comprar hoje |
| CUSGER | Custo gerencial | Para analise interna |
| CUSVARIAVEL | Custo variavel | Custos que variam com volume |
| CUSMEDSEMICM | Custo medio sem ICMS | Media ponderada |

---

## Uso no Negocio

Esta tabela permite:
1. **Historico de custos** - Ver evolucao do custo ao longo do tempo
2. **Analise de margem** - Comparar preco de venda vs custo
3. **Custo por empresa** - Cada filial pode ter custo diferente
4. **Decisao de preco** - Base para formacao de preco de venda

---

## Amostra de Dados

```
SEQUENCIA | CODPROD | CODEMP | CUSCOMICM | CUSREP  | CUSSEMICM | DTATUAL
----------|---------|--------|-----------|---------|-----------|----------
10850     | 4993    | 1      | 24.18     | 29.97   | 20.15     | 2023-12-15
10851     | 4993    | 1      | 22.79     | 28.24   | 19.00     | 2023-12-20
10852     | 4993    | 1      | 22.79     | 28.24   | 19.00     | 2023-12-27
```

---

## Queries Uteis

### Custo atual de um produto

```sql
SELECT *
FROM (
    SELECT
        CODPROD,
        CODEMP,
        CUSCOMICM,
        CUSREP,
        CUSSEMICM,
        DTATUAL
    FROM AD_TGFCUSMMA
    WHERE CODPROD = :codprod
      AND CODEMP = :codemp
    ORDER BY DTATUAL DESC
)
WHERE ROWNUM = 1
```

### Evolucao de custo de um produto

```sql
SELECT
    CODPROD,
    CODEMP,
    TRUNC(DTATUAL, 'MM') AS MES,
    AVG(CUSCOMICM) AS CUSTO_MEDIO
FROM AD_TGFCUSMMA
WHERE CODPROD = :codprod
GROUP BY CODPROD, CODEMP, TRUNC(DTATUAL, 'MM')
ORDER BY MES
```

### Produtos com maior variacao de custo

```sql
SELECT
    CODPROD,
    MIN(CUSCOMICM) AS CUSTO_MIN,
    MAX(CUSCOMICM) AS CUSTO_MAX,
    MAX(CUSCOMICM) - MIN(CUSCOMICM) AS VARIACAO,
    ROUND((MAX(CUSCOMICM) - MIN(CUSCOMICM)) / NULLIF(MIN(CUSCOMICM), 0) * 100, 2) AS PERC_VARIACAO
FROM AD_TGFCUSMMA
WHERE DTATUAL >= ADD_MONTHS(SYSDATE, -12)
GROUP BY CODPROD
HAVING MIN(CUSCOMICM) > 0
ORDER BY PERC_VARIACAO DESC
```

### Custo medio por empresa

```sql
SELECT
    c.CODEMP,
    e.RAZAOSOCIAL,
    COUNT(DISTINCT c.CODPROD) AS QTD_PRODUTOS,
    AVG(c.CUSCOMICM) AS CUSTO_MEDIO
FROM AD_TGFCUSMMA c
JOIN TSIEMP e ON c.CODEMP = e.CODEMP
WHERE c.DTATUAL >= ADD_MONTHS(SYSDATE, -1)
GROUP BY c.CODEMP, e.RAZAOSOCIAL
ORDER BY CUSTO_MEDIO DESC
```

---

## Observacoes

1. **Historico completo** - Guarda todas as alteracoes de custo
2. **Por empresa** - Custo pode variar por filial
3. **Varios tipos** - Diferencia custo fiscal vs gerencial
4. **709k registros** - Historico extenso

---

## Diferenca para TGFCUS (padrao)

| Aspecto | AD_TGFCUSMMA | TGFCUS |
|---------|--------------|--------|
| Tipo | Customizada | Padrao Sankhya |
| Campos | Mais tipos de custo | Custo basico |
| Historico | Sim | Nao (sobrescreve) |
| Uso | Analise gerencial | Calculo fiscal |

---

## Tabelas Relacionadas

- [TGFPRO](TGFPRO.md) - Cadastro de produtos
- [TSIEMP](TSIEMP.md) - Empresas
- TGFCUS - Custo padrao Sankhya

---

*Documentado em: 2026-02-06*
