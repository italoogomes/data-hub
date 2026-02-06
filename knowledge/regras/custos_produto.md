# Custos de Produto

**Quando aplica:** Rastreamento e controle de custos de produtos

**O que acontece:** Sistema registra historico de custos em AD_TGFCUSMMA

---

## Regra Principal

**MMarra usa AD_TGFCUSMMA para historico de custos, alem do TGFCUS padrao.**

| Tabela | Registros | Uso |
|--------|-----------|-----|
| TGFCUS (padrao) | 289.309 | Custo atual (Sankhya) |
| AD_TGFCUSMMA (custom) | 709.230 | Historico completo |

**AD_TGFCUSMMA tem 2.5x mais registros** - guarda todo historico.

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Total registros | 709.230 |
| Produtos distintos | 61.159 |
| Periodo | 2020 a 2025 (5 anos) |
| Media por produto | ~12 registros |

---

## Distribuicao por Empresa

| Empresa | Registros | % |
|---------|-----------|---|
| 1 - Ribeirao (Matriz) | 430.896 | 61% |
| 2 - Campinas | 96.253 | 14% |
| 7 - Itumbiara | 94.130 | 13% |
| 4 - Uberlandia | 84.114 | 12% |
| 8 - Belo Horizonte | 3.837 | <1% |

**Matriz concentra 61% dos registros de custo.**

---

## Tipos de Custo

AD_TGFCUSMMA armazena varios tipos:

| Campo | Descricao | Uso |
|-------|-----------|-----|
| CUSCOMICM | Custo COM ICMS | Base para margem |
| CUSSEMICM | Custo SEM ICMS | Custo liquido |
| CUSREP | Custo de reposicao | Quanto custa comprar hoje |
| CUSGER | Custo gerencial | Analise interna |
| CUSVARIAVEL | Custo variavel | Varia com volume |
| CUSMEDSEMICM | Custo medio sem ICMS | Media ponderada |

---

## Exemplo de Historico

Produto 156635 (com 427 registros):

| Data | CustoComICM | CustoSemICM | Reposicao |
|------|-------------|-------------|-----------|
| 03/12/2025 | R$ 569,53 | R$ 569,53 | R$ 738,90 |
| 25/11/2025 | R$ 569,54 | R$ 569,54 | R$ 738,90 |
| 17/11/2025 | R$ 569,53 | R$ 569,53 | R$ 738,90 |
| 31/10/2025 | R$ 571,07 | R$ 571,07 | R$ 738,89 |
| 24/10/2025 | R$ 571,61 | R$ 571,61 | R$ 746,75 |

**Custo de reposicao eh ~30% maior que custo atual.**

---

## Fluxo de Atualizacao

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Compra    │───>│  Calcula    │───>│  Registra   │
│  TOP 1209   │    │   Custo     │    │ AD_TGFCUSMMA│
│  TIPMOV='C' │    │   Medio     │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   TGFCUS    │
                   │ (sobrescreve)│
                   └─────────────┘
```

---

## Diferenca TGFCUS vs AD_TGFCUSMMA

| Aspecto | TGFCUS | AD_TGFCUSMMA |
|---------|--------|--------------|
| Tipo | Padrao Sankhya | Customizada |
| Registros | 289k | 709k |
| Historico | Nao (sobrescreve) | Sim (acumula) |
| Campos | Custo basico | Varios tipos |
| Uso | Calculo fiscal | Analise gerencial |

---

## Queries Uteis

### Custo atual de um produto

```sql
SELECT * FROM (
    SELECT
        CODPROD,
        CODEMP,
        CUSCOMICM,
        CUSSEMICM,
        CUSREP,
        DTATUAL
    FROM AD_TGFCUSMMA
    WHERE CODPROD = :codprod
      AND CODEMP = :codemp
    ORDER BY DTATUAL DESC
) WHERE ROWNUM = 1
```

### Evolucao de custo

```sql
SELECT
    TRUNC(DTATUAL, 'MM') as MES,
    AVG(CUSCOMICM) as CUSTO_MEDIO,
    MIN(CUSCOMICM) as CUSTO_MIN,
    MAX(CUSCOMICM) as CUSTO_MAX
FROM AD_TGFCUSMMA
WHERE CODPROD = :codprod
  AND CODEMP = :codemp
GROUP BY TRUNC(DTATUAL, 'MM')
ORDER BY MES
```

### Produtos com maior variacao

```sql
SELECT
    CODPROD,
    MIN(CUSCOMICM) as CUSTO_MIN,
    MAX(CUSCOMICM) as CUSTO_MAX,
    ROUND((MAX(CUSCOMICM) - MIN(CUSCOMICM)) / NULLIF(MIN(CUSCOMICM), 0) * 100, 2) as VARIACAO_PERC
FROM AD_TGFCUSMMA
WHERE DTATUAL >= ADD_MONTHS(SYSDATE, -12)
  AND CUSCOMICM > 0
GROUP BY CODPROD
HAVING MIN(CUSCOMICM) > 0
ORDER BY VARIACAO_PERC DESC
```

### Comparar custo vs reposicao

```sql
SELECT
    CODPROD,
    CUSCOMICM as CUSTO_ATUAL,
    CUSREP as REPOSICAO,
    ROUND((CUSREP - CUSCOMICM) / NULLIF(CUSCOMICM, 0) * 100, 2) as DIFERENCA_PERC
FROM (
    SELECT CODPROD, CODEMP, CUSCOMICM, CUSREP,
           ROW_NUMBER() OVER (PARTITION BY CODPROD, CODEMP ORDER BY DTATUAL DESC) as RN
    FROM AD_TGFCUSMMA
)
WHERE RN = 1
  AND CUSCOMICM > 0
ORDER BY DIFERENCA_PERC DESC
```

---

## Regras de Negocio

1. **Historico completo** - 5 anos de dados
2. **Por empresa** - Custo pode variar por filial
3. **Varios tipos** - Com/sem ICMS, reposicao, gerencial
4. **Nao sobrescreve** - Mantem registro de cada alteracao
5. **Custo de reposicao** - Indica tendencia de preco

---

## Uso para Analise

1. **Margem de lucro** - Compara CUSCOMICM com preco de venda
2. **Tendencia** - Custo subindo ou descendo?
3. **Reposicao** - Vai custar mais na proxima compra?
4. **Por filial** - Qual empresa tem melhor custo?

---

## Observacoes

1. **Tabela grande** - 709k registros
2. **Essencial para precificacao** - Base para definir preco de venda
3. **Historico extenso** - 5 anos permite analise de tendencia
4. **Matriz concentra dados** - 61% dos registros
5. **Reposicao > Atual** - Indica inflacao de custos

---

## Tabelas Relacionadas

- [AD_TGFCUSMMA](../sankhya/tabelas/AD_TGFCUSMMA.md) - Tabela de custos
- [TGFPRO](../sankhya/tabelas/TGFPRO.md) - Cadastro de produtos
- [TSIEMP](../sankhya/tabelas/TSIEMP.md) - Empresas

---

*Documentado em: 2026-02-06*
