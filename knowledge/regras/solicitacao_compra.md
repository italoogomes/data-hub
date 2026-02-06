# Solicitacao de Compra

**Quando aplica:** Processo de requisicao de compra de produtos

**O que acontece:** Usuario registra necessidade de compra em TGFCAB com TIPMOV='J'

---

## Regra Principal

**MMarra usa TGFCAB com TIPMOV='J' para solicitacoes.**

A tabela padrao TGFSOL existe mas esta **VAZIA**.

| Tabela | Status | Uso |
|--------|--------|-----|
| TGFSOL | VAZIA | Nao utilizada |
| AD_SOLICITACAOCOMPRA | VAZIA | Nao utilizada |
| **TGFCAB** | ATIVA | TIPMOV='J' para solicitacoes |

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Total solicitacoes | 2.878 |
| Valor total | R$ 6.09M |
| Liberadas (STATUSNOTA='L') | 2.869 |
| Abertas (STATUSNOTA='A') | 9 |
| TOP usada | 1804 (SOLICITACAO DE COMPRA) |

### Por Ano

| Ano | Quantidade | Valor |
|-----|------------|-------|
| 2026 | 2.875 | R$ 6.08M |
| 2025 | 3 | R$ 8.4k |

**Sistema novo:** Praticamente todas as solicitacoes sao de 2026.

### Por Empresa

| Empresa | Quantidade | % |
|---------|------------|---|
| 1 - Ribeirao Preto (Matriz) | 1.411 | 49% |
| 7 - Itumbiara | 949 | 33% |
| 2 - Campinas | 314 | 11% |
| 4 - Uberlandia | 147 | 5% |
| 8 - Belo Horizonte | 56 | 2% |

---

## Fluxo

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Necessidade │───>│ Solicitacao │───>│  Cotacao    │
│ identificada│    │  TIPMOV='J' │    │   TGFCOT    │
│             │    │  TOP 1804   │    │             │
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   TGFCAB    │
                   │   TGFITE    │
                   │ (sem EST)   │
                   │ (sem FIN)   │
                   └─────────────┘
```

---

## Comportamento da TOP 1804

| Campo | Valor | Significado |
|-------|-------|-------------|
| TIPMOV | J | Solicitacao |
| ATUALEST | N | Nao afeta estoque |
| ATUALFIN | 0 | Nao gera financeiro |

**Apenas registro da necessidade, sem impacto no sistema.**

---

## Vinculo com Cotacao

A investigacao mostrou que **2.848 cotacoes tem NUNOTAORIG preenchido**, indicando que:

1. Solicitacao eh criada (TGFCAB TIPMOV='J')
2. Cotacao eh aberta (TGFCOT com NUNOTAORIG = NUNOTA da solicitacao)
3. Melhor proposta vira Pedido de Compra (TIPMOV='O')
4. Pedido vira Compra efetiva (TIPMOV='C')

---

## Exemplo de Solicitacao

| NUNOTA | NUMNOTA | DATA | STATUS | VALOR |
|--------|---------|------|--------|-------|
| 1197416 | 2945 | 06/02/2026 | L | R$ 65,10 |
| 1197311 | 2937 | 06/02/2026 | L | R$ 1.099,00 |
| 1197373 | 2941 | 06/02/2026 | L | R$ 8,28 |

---

## Queries Uteis

### Solicitacoes abertas

```sql
SELECT
    c.NUNOTA,
    c.NUMNOTA,
    c.DTNEG,
    c.VLRNOTA,
    c.CODEMP,
    e.RAZAOSOCIAL
FROM TGFCAB c
JOIN TSIEMP e ON c.CODEMP = e.CODEMP
WHERE c.TIPMOV = 'J'
  AND c.STATUSNOTA = 'A'
ORDER BY c.DTNEG DESC
```

### Solicitacoes do mes

```sql
SELECT
    c.NUNOTA,
    c.NUMNOTA,
    c.DTNEG,
    c.VLRNOTA,
    c.STATUSNOTA
FROM TGFCAB c
WHERE c.TIPMOV = 'J'
  AND c.DTNEG >= TRUNC(SYSDATE, 'MM')
ORDER BY c.DTNEG DESC
```

### Itens de uma solicitacao

```sql
SELECT
    i.SEQUENCIA,
    i.CODPROD,
    p.DESCRPROD,
    i.QTDNEG,
    i.VLRUNIT,
    i.VLRTOT
FROM TGFITE i
JOIN TGFPRO p ON i.CODPROD = p.CODPROD
WHERE i.NUNOTA = :nunota
ORDER BY i.SEQUENCIA
```

---

## Observacoes

1. **Sistema recente** - 99% das solicitacoes sao de 2026
2. **Concentracao na matriz** - 49% das solicitacoes em Ribeirao Preto
3. **Vinculo via NUNOTAORIG** - Cotacao referencia a solicitacao
4. **TGFSOL nao utilizada** - Padrao Sankhya ignorado
5. **Sem impacto operacional** - ATUALEST=N, ATUALFIN=0

---

## Tabelas Relacionadas

- [TGFCAB](../sankhya/tabelas/TGFCAB.md) - Cabecalho
- [TGFITE](../sankhya/tabelas/TGFITE.md) - Itens
- [TGFCOT](../sankhya/tabelas/TGFCOT.md) - Cotacoes
- [TGFTOP](../sankhya/tabelas/TGFTOP.md) - TOP 1804

---

*Documentado em: 2026-02-06*
