# Fluxo de Venda

**Modulo:** Vendas

**Descricao:** Processo completo de venda de mercadorias, desde o pedido ate a emissao da nota fiscal e baixa no estoque.

---

## Visao Geral

A venda na MMarra segue um fluxo que pode variar conforme o tipo de operacao:
1. **Venda Balcao (TOP 1100)** - Cliente retira no local, mais rapida
2. **Venda NFe (TOP 1101)** - Entrega/envio, processo padrao
3. **Venda via Pedido** - Pedido (TOP 1000-1012) → Faturamento (TOP 1100/1101)

---

## TOPs Envolvidas no Processo de Venda

### TOPs de Pedido (TIPMOV = P)

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | Qtd Notas |
|------------|-----------|----------|----------|-----------|
| **1000** | Orcamento venda | N | 0 | - |
| **1001** | Pedido venda WMS consumo | R | 1 | 4.906 |
| **1007** | Pedido venda empenho | N | 1 | 2.327 |
| **1012** | Pedido venda WMS revenda | R | 1 | - |

**Comportamento:**
- ATUALEST = R (Reserva) - Reserva estoque mas nao baixa
- ATUALEST = N (Nao) - Nao afeta estoque
- ATUALFIN = 1 - Gera financeiro a receber (provisorio)

### TOPs de Venda Efetiva (TIPMOV = V)

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | NFE | Qtd Notas | Valor |
|------------|-----------|----------|----------|-----|-----------|-------|
| **1100** | Venda NF-e (Balcao) | B | 1 | T | 120.379 | R$ 254M |
| **1101** | Venda NF-e | B | 1 | T | 105.062 | R$ 233M |
| **1130** | Remessa exportacao | B | 0 | T | - | - |
| **1132** | Venda p/ industrializacao | B | 1 | T | - | - |
| **1151** | Bonificacao saida | B | 0 | T | - | - |

**Comportamento:**
- ATUALEST = B (Baixa) - Baixa estoque fisico
- ATUALFIN = 1 - Gera financeiro a receber
- NFE = T - Transmite NFe automaticamente

---

## Fluxo Detalhado

### Cenario 1: Venda Balcao (Rapida)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Cliente   │───>│  Cadastra   │───>│   Emite     │───>│  Entrega    │
│   chega     │    │   Nota      │    │   NFe       │    │  produto    │
└─────────────┘    │  TOP 1100   │    │  (auto)     │    └─────────────┘
                   └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ Baixa EST   │
                   │ Gera FIN    │
                   └─────────────┘
```

**Passos:**
1. Cliente chega na loja/balcao
2. Vendedor abre nota TGFCAB com TOP 1100
3. Adiciona itens em TGFITE
4. Confirma nota
5. Sistema baixa estoque (ATUALEST = B)
6. Sistema gera titulo a receber (ATUALFIN = 1)
7. Sistema transmite NFe (NFE = T)
8. Cliente retira produto

### Cenario 2: Venda com Pedido

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Pedido    │───>│  Separacao  │───>│ Faturamento │───>│  Expedicao  │
│  TOP 1001   │    │    WMS      │    │  TOP 1101   │    │  Entrega    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                                     │
       ▼                                     ▼
┌─────────────┐                       ┌─────────────┐
│ Reserva EST │                       │ Baixa EST   │
│ (ATUALEST=R)│                       │ Gera FIN    │
└─────────────┘                       └─────────────┘
```

**Passos:**
1. Vendedor cria pedido (TOP 1001/1007)
2. Sistema reserva estoque (ATUALEST = R)
3. WMS separa mercadoria
4. Faturamento gera nota fiscal (TOP 1101)
5. Sistema baixa estoque (ATUALEST = B)
6. Sistema gera titulo a receber (ATUALFIN = 1)
7. Sistema transmite NFe (NFE = T)
8. Expedicao envia produto

---

## Tabelas Envolvidas

| Tabela | Papel no Processo |
|--------|-------------------|
| **TGFCAB** | Cabecalho da nota/pedido |
| **TGFITE** | Itens vendidos |
| **TGFPAR** | Cliente (CODPARC) |
| **TGFPRO** | Produtos vendidos |
| **TGFVEN** | Vendedor responsavel |
| **TGFTOP** | Define comportamento |
| **TSIEMP** | Empresa vendedora |
| **TGFEST** | Posicao de estoque |
| **TGFFIN** | Titulos financeiros |

---

## Campos Importantes

### TGFCAB (Cabecalho)

| Campo | Descricao | Valores |
|-------|-----------|---------|
| NUNOTA | Numero unico da nota | Sequencial |
| CODTIPOPER | TOP usada | 1100, 1101, 1001... |
| TIPMOV | Tipo movimento | V (venda), P (pedido) |
| CODPARC | Cliente | FK para TGFPAR |
| CODVEND | Vendedor | FK para TGFVEN |
| CODEMP | Empresa vendedora | FK para TSIEMP |
| VLRNOTA | Valor total | Calculado |
| DTNEG | Data negociacao | Data da venda |
| STATUSNFE | Status NFe | A=Autorizada |
| STATUSNOTA | Status da nota | L=Liberada |

### TGFITE (Itens)

| Campo | Descricao |
|-------|-----------|
| NUNOTA | Nota pai |
| SEQUENCIA | Sequencia do item |
| CODPROD | Produto vendido |
| QTDNEG | Quantidade vendida |
| VLRUNIT | Valor unitario |
| VLRTOT | Valor total item |
| CODLOCALORIG | Local estoque origem |

---

## Impacto no Estoque

### Venda Efetiva (TOP 1100, 1101)
```sql
-- Baixa estoque (ATUALEST = B)
-- TGFEST.ESTOQUE = TGFEST.ESTOQUE - TGFITE.QTDNEG
-- Onde: CODPROD, CODEMP, CODLOCAL
```

### Pedido com Reserva (TOP 1001)
```sql
-- Reserva estoque (ATUALEST = R)
-- TGFEST.RESERVADO = TGFEST.RESERVADO + TGFITE.QTDNEG
-- Estoque disponivel = ESTOQUE - RESERVADO
```

---

## Impacto no Financeiro

### Venda gera titulo a receber (ATUALFIN = 1)
```sql
-- Cria registro em TGFFIN
-- TGFFIN.RECDESP = 1 (Receita)
-- TGFFIN.VLRDESDOB = valor da parcela
-- TGFFIN.DTVENC = data vencimento
-- TGFFIN.CODPARC = cliente
-- TGFFIN.NUNOTA = nota origem
```

---

## Queries Uteis

### Vendas do mes por TOP
```sql
SELECT T.CODTIPOPER, T.DESCROPER,
       COUNT(*) AS QTD_VENDAS,
       SUM(C.VLRNOTA) AS VLR_TOTAL
FROM TGFCAB C
JOIN TGFTOP T ON C.CODTIPOPER = T.CODTIPOPER AND C.DHTIPOPER = T.DHALTER
WHERE C.TIPMOV = 'V'
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
GROUP BY T.CODTIPOPER, T.DESCROPER
ORDER BY VLR_TOTAL DESC
```

### Vendas por vendedor
```sql
SELECT V.CODVEND, V.APELIDO,
       COUNT(*) AS QTD_VENDAS,
       SUM(C.VLRNOTA) AS VLR_TOTAL
FROM TGFCAB C
JOIN TGFVEN V ON C.CODVEND = V.CODVEND
WHERE C.TIPMOV = 'V'
  AND C.CODTIPOPER IN (1100, 1101)
GROUP BY V.CODVEND, V.APELIDO
ORDER BY VLR_TOTAL DESC
```

### Pedidos pendentes de faturamento
```sql
SELECT C.NUNOTA, C.DTNEG, P.NOMEPARC, C.VLRNOTA
FROM TGFCAB C
JOIN TGFPAR P ON C.CODPARC = P.CODPARC
WHERE C.TIPMOV = 'P'
  AND C.CODTIPOPER IN (1001, 1007)
  AND C.STATUSNOTA <> 'L'
ORDER BY C.DTNEG
```

---

## Estatisticas MMarra

Baseado nos dados extraidos:

| Metrica | Valor |
|---------|-------|
| Total vendas (TOP 1100+1101) | 225.441 notas |
| Valor total vendas | R$ 487M |
| TOP mais usada | 1100 (Balcao) - 53% |
| Vendas sem vendedor | 70% |
| Ticket medio | R$ 2.160 |
| Empresa com mais vendas | Ribeirao Preto (53%) |

---

## Observacoes

1. **70% das vendas sem vendedor** - Indica vendas de balcao/automaticas onde CODVEND = 0
2. **Venda Balcao (1100) vs Venda NFe (1101)** - Diferenca principal eh no processo operacional, nao no comportamento fiscal
3. **Pedido reserva estoque** - TOP 1001 usa ATUALEST = R para garantir disponibilidade
4. **NFe automatica** - Todas as TOPs de venda tem NFE = T (transmite automaticamente)
5. **Bonificacao nao gera financeiro** - TOP 1151 tem ATUALFIN = 0

---

## Processos Relacionados

- [Devolucao de Venda](../estoque/devolucao_venda.md) - Quando cliente devolve
- [Transferencia](../estoque/transferencia.md) - Movimentacao entre filiais
- [Empenho](../estoque/empenho.md) - Reserva de estoque para pedido
