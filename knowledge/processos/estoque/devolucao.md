# Fluxo de Devolucao

**Modulo:** Estoque / Vendas / Compras

**Descricao:** Processos de devolucao de mercadorias, seja devolucao de venda (cliente devolve) ou devolucao de compra (devolve ao fornecedor).

---

## Visao Geral

Existem dois tipos principais de devolucao:
1. **Devolucao de Venda** - Cliente devolve mercadoria comprada
2. **Devolucao de Compra** - MMarra devolve ao fornecedor

---

## TOPs de Devolucao de Venda (TIPMOV = D)

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | Qtd Notas | Valor |
|------------|-----------|----------|----------|-----------|-------|
| **1202** | Devolucao venda (NF terceiros) | E | -1 | 5.546 | R$ 6M |
| **1203** | Devolucao refatura | E | -1 | - | - |
| **1204** | Devolucao venda refatura | E | -1 | - | - |

**Comportamento:**
- ATUALEST = E (Entrada) - Mercadoria volta ao estoque
- ATUALFIN = -1 - Gera credito ao cliente (estorna receber)

---

## TOPs de Devolucao de Compra (TIPMOV = E)

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | Qtd Notas | Valor |
|------------|-----------|----------|----------|-----------|-------|
| **1501** | Devolucao compra | B | 1 | 806 | R$ 2M |

**Comportamento:**
- ATUALEST = B (Baixa) - Mercadoria sai do estoque
- ATUALFIN = 1 - Gera credito do fornecedor (estorna pagar)

---

## Fluxo de Devolucao de Venda

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Cliente    │───>│  Recebe     │───>│  Registra   │───>│  Estoque    │
│  devolve    │    │  mercadoria │    │  TOP 1202   │    │  atualizado │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                             │
                                             ▼
                                      ┌─────────────┐
                                      │ Gera credito│
                                      │ ao cliente  │
                                      └─────────────┘
```

**Passos:**
1. Cliente solicita devolucao
2. MMarra autoriza e recebe mercadoria
3. Confere estado da mercadoria
4. Registra nota de devolucao (TOP 1202)
5. Sistema adiciona ao estoque (ATUALEST = E)
6. Sistema gera credito ao cliente (ATUALFIN = -1)
7. Cliente recebe credito ou reembolso

---

## Fluxo de Devolucao de Compra

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Identifica │───>│   Emite     │───>│   Envia     │───>│  Estoque    │
│  problema   │    │  NFe saida  │    │ mercadoria  │    │  atualizado │
└─────────────┘    │  TOP 1501   │    │ fornecedor  │    └─────────────┘
                   └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ Gera credito│
                   │ fornecedor  │
                   └─────────────┘
```

**Passos:**
1. MMarra identifica problema na mercadoria
2. Solicita autorizacao do fornecedor
3. Emite NFe de devolucao (TOP 1501)
4. Sistema baixa estoque (ATUALEST = B)
5. Sistema gera credito do fornecedor (ATUALFIN = 1)
6. Envia mercadoria de volta

---

## Comparativo: Devolucao de Venda vs Compra

| Aspecto | Dev. Venda (1202) | Dev. Compra (1501) |
|---------|-------------------|-------------------|
| TIPMOV | D (Devolucao) | E (Entrada) |
| ATUALEST | E (Entrada) | B (Baixa) |
| ATUALFIN | -1 (Estorna receber) | 1 (Estorna pagar) |
| NFe | Entrada (cliente emite) | Saida (MMarra emite) |
| Estoque | Aumenta | Diminui |
| Financeiro | Credito ao cliente | Credito do fornecedor |

---

## Tabelas Envolvidas

| Tabela | Papel no Processo |
|--------|-------------------|
| **TGFCAB** | Cabecalho da nota devolucao |
| **TGFITE** | Itens devolvidos |
| **TGFPAR** | Cliente/Fornecedor |
| **TGFPRO** | Produtos devolvidos |
| **TGFTOP** | Define comportamento |
| **TSIEMP** | Empresa |
| **TGFEST** | Posicao de estoque |
| **TGFFIN** | Estorno/Credito financeiro |

---

## Campos Importantes

### TGFCAB (Cabecalho)

| Campo | Descricao | Dev. Venda | Dev. Compra |
|-------|-----------|------------|-------------|
| TIPMOV | Tipo movimento | D | E |
| CODTIPOPER | TOP | 1202 | 1501 |
| CODPARC | Parceiro | Cliente | Fornecedor |
| VLRNOTA | Valor | Valor devolvido | Valor devolvido |
| NUNOTA_ORIG | Nota original | Nota de venda | Nota de compra |

### Vinculo com Nota Original

A devolucao geralmente referencia a nota original:
- **NUNOTA_ORIG** ou campo similar
- Permite rastrear de onde veio a mercadoria
- Necessario para NFe (chave de acesso original)

---

## Impacto no Estoque

### Devolucao de Venda (TOP 1202)
```sql
-- Entrada estoque (ATUALEST = E)
-- Mercadoria volta ao estoque
-- TGFEST.ESTOQUE = TGFEST.ESTOQUE + TGFITE.QTDNEG
```

### Devolucao de Compra (TOP 1501)
```sql
-- Baixa estoque (ATUALEST = B)
-- Mercadoria sai do estoque
-- TGFEST.ESTOQUE = TGFEST.ESTOQUE - TGFITE.QTDNEG
```

---

## Impacto no Financeiro

### Devolucao de Venda (ATUALFIN = -1)
```sql
-- Estorna ou credita titulo a receber
-- TGFFIN com RECDESP = -1 (Credito ao cliente)
-- Pode abater de divida existente ou gerar reembolso
```

### Devolucao de Compra (ATUALFIN = 1)
```sql
-- Estorna ou credita titulo a pagar
-- TGFFIN com RECDESP = 1 (Credito do fornecedor)
-- Pode abater de divida existente
```

---

## Queries Uteis

### Devolucoes de venda do periodo
```sql
SELECT C.NUNOTA, C.DTNEG, P.NOMEPARC, C.VLRNOTA
FROM TGFCAB C
JOIN TGFPAR P ON C.CODPARC = P.CODPARC
WHERE C.TIPMOV = 'D'
  AND C.CODTIPOPER = 1202
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
ORDER BY C.DTNEG DESC
```

### Devolucoes de compra do periodo
```sql
SELECT C.NUNOTA, C.DTNEG, P.NOMEPARC, C.VLRNOTA
FROM TGFCAB C
JOIN TGFPAR P ON C.CODPARC = P.CODPARC
WHERE C.TIPMOV = 'E'
  AND C.CODTIPOPER = 1501
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
ORDER BY C.DTNEG DESC
```

### Taxa de devolucao de venda
```sql
SELECT
    ROUND(
        (SELECT COUNT(*) FROM TGFCAB WHERE TIPMOV = 'D' AND CODTIPOPER = 1202) * 100.0 /
        (SELECT COUNT(*) FROM TGFCAB WHERE TIPMOV = 'V' AND CODTIPOPER IN (1100, 1101)),
    2) AS PERC_DEVOLUCAO
FROM DUAL
```

### Produtos mais devolvidos
```sql
SELECT P.CODPROD, P.DESCRPROD,
       COUNT(*) AS QTD_DEVOLUCOES,
       SUM(I.QTDNEG) AS QTD_ITENS
FROM TGFITE I
JOIN TGFCAB C ON I.NUNOTA = C.NUNOTA
JOIN TGFPRO P ON I.CODPROD = P.CODPROD
WHERE C.TIPMOV = 'D'
GROUP BY P.CODPROD, P.DESCRPROD
ORDER BY QTD_DEVOLUCOES DESC
```

---

## Estatisticas MMarra

Baseado nos dados extraidos:

| Metrica | Valor |
|---------|-------|
| Devolucoes de venda | 5.546 notas |
| Valor dev. venda | R$ 6M |
| Devolucoes de compra | 806 notas |
| Valor dev. compra | R$ 2M |
| Taxa devolucao venda | ~2.5% |

---

## Observacoes

1. **Taxa baixa de devolucao** - ~2.5% das vendas sao devolvidas
2. **TOP 1202 principal** - Devolucao de venda com NF de terceiros (cliente emite)
3. **Refatura (1203, 1204)** - Casos especiais onde refatura a venda
4. **Vinculo com nota original** - Importante para rastreabilidade
5. **Impacto inverso** - Devolucao de venda ENTRA estoque, devolucao de compra SAI

---

## Motivos Comuns de Devolucao

### Devolucao de Venda
- Produto errado
- Defeito de fabrica
- Arrependimento (prazo legal)
- Erro na quantidade

### Devolucao de Compra
- Produto com defeito
- Produto diferente do pedido
- Qualidade abaixo do esperado
- Avaria no transporte

---

## Processos Relacionados

- [Fluxo de Venda](../vendas/fluxo_venda.md) - Origem da devolucao de venda
- [Fluxo de Compra](../compras/fluxo_compra.md) - Origem da devolucao de compra
- [Transferencia](transferencia.md) - Pode envolver devolucao entre filiais
