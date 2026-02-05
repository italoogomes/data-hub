# TGFEST

**Descricao:** Posicao de estoque dos produtos. Armazena saldo atual, reservas, minimos/maximos e controles por empresa, local e produto.

**Total de registros:** 36.769

---

## Campos

| Campo | Tipo | Tamanho | Obrig. | PK | FK | Descricao |
|-------|------|---------|--------|----|----|-----------|
| CODEMP | NUMBER | 22 | Sim | PK | FK | Codigo da empresa |
| CODLOCAL | NUMBER | 22 | Sim | PK | FK | Codigo do local de estoque |
| CODPROD | NUMBER | 22 | Sim | PK | FK | Codigo do produto |
| CONTROLE | VARCHAR2 | 17 | Sim | PK | - | Controle de lote/serie |
| TIPO | VARCHAR2 | 1 | Sim | PK | - | Tipo de estoque (P=Proprio, T=Terceiro) |
| CODPARC | NUMBER | 22 | Sim | PK | FK | Parceiro (para consignacao) |
| ESTOQUE | FLOAT | 22 | Sim | - | - | Quantidade em estoque |
| RESERVADO | FLOAT | 22 | Nao | - | - | Quantidade reservada |
| ESTMIN | FLOAT | 22 | Sim | - | - | Estoque minimo |
| ESTMAX | FLOAT | 22 | Sim | - | - | Estoque maximo |
| ATIVO | VARCHAR2 | 1 | Sim | - | - | Se posicao esta ativa (S/N) |
| CODBARRA | VARCHAR2 | 25 | Nao | - | - | Codigo de barras alternativo |
| DTVAL | DATE | 7 | Nao | - | - | Data de validade (lotes) |
| DTFABRICACAO | DATE | 7 | Nao | - | - | Data de fabricacao (lotes) |
| DTENTRADA | DATE | 7 | Nao | - | - | Data da ultima entrada |
| STATUSLOTE | VARCHAR2 | 1 | Sim | - | - | Status do lote |
| PERCPUREZA | FLOAT | 22 | Nao | - | - | Percentual de pureza |
| PERCGERMIN | FLOAT | 22 | Nao | - | - | Percentual germinacao minima |
| PERCVC | FLOAT | 22 | Nao | - | - | Percentual VC |
| QTDPEDPENDEST | FLOAT | 22 | Nao | - | - | Qtd pedido pendente estoque |
| WMSBLOQUEADO | FLOAT | 22 | Nao | - | - | Quantidade bloqueada WMS |
| MD5PAF | VARCHAR2 | 32 | Nao | - | - | Hash MD5 PAF-ECF |
| CODAGREGACAO | VARCHAR2 | 20 | Nao | - | - | Codigo de agregacao |
| AD_IDEXTERNO | VARCHAR2 | 100 | Nao | - | - | ID externo (integracao) |

---

## Chave Primaria

A PK de TGFEST eh **composta** por 6 campos:

```
PK: CODEMP + CODLOCAL + CODPROD + CONTROLE + TIPO + CODPARC
```

Isso significa que o estoque eh controlado por:
- **Empresa** - Cada filial tem seu estoque
- **Local** - Cada deposito dentro da empresa
- **Produto** - O item em si
- **Controle** - Lote ou serie (vazio se nao usa)
- **Tipo** - Proprio (P) ou de terceiros (T)
- **Parceiro** - Para estoque consignado

---

## Relacionamentos

| Campo | Tabela | Campo Ref | Descricao |
|-------|--------|-----------|-----------|
| CODEMP | TGFEMP | CODEMP | Empresa do estoque |
| CODLOCAL | TGFLOC | CODLOCAL | Local de armazenamento |
| CODPROD | TGFPRO | CODPROD | Produto estocado |
| CODPARC | TGFPAR | CODPARC | Parceiro (consignacao) |

---

## Valores de Dominio

### TIPO (Tipo de Estoque)

| Valor | Significado |
|-------|-------------|
| P | Proprio - Estoque da empresa |
| T | Terceiro - Estoque consignado/em poder de terceiros |

### ATIVO

| Valor | Significado |
|-------|-------------|
| S | Sim - Posicao ativa |
| N | Nao - Posicao inativa |

### STATUSLOTE

| Valor | Significado |
|-------|-------------|
| A | Aprovado |
| B | Bloqueado |
| Q | Quarentena |

---

## Como o Estoque e Atualizado

### Na Compra (ATUALEST = E)

Quando uma nota de compra eh confirmada com TOP que tem `ATUALEST = 'E'`:

```sql
-- Sistema incrementa o estoque
UPDATE TGFEST SET
    ESTOQUE = ESTOQUE + [QTDNEG do item]
WHERE CODEMP = [empresa da nota]
  AND CODLOCAL = [local destino]
  AND CODPROD = [produto]
  AND CONTROLE = [controle/lote]
  AND TIPO = 'P'
  AND CODPARC = 0
```

### Na Venda (ATUALEST = B)

Quando uma nota de venda eh confirmada com TOP que tem `ATUALEST = 'B'`:

```sql
-- Sistema decrementa o estoque
UPDATE TGFEST SET
    ESTOQUE = ESTOQUE - [QTDNEG do item]
WHERE CODEMP = [empresa da nota]
  AND CODLOCAL = [local origem]
  AND CODPROD = [produto]
  AND CONTROLE = [controle/lote]
  AND TIPO = 'P'
  AND CODPARC = 0
```

### Na Reserva (ATUALEST = R)

Quando um pedido reserva estoque (TOP com `ATUALEST = 'R'`):

```sql
-- Sistema reserva (nao baixa)
UPDATE TGFEST SET
    RESERVADO = RESERVADO + [QTDNEG do item]
WHERE ...
```

---

## Campos de Controle WMS

| Campo | Uso |
|-------|-----|
| WMSBLOQUEADO | Quantidade bloqueada pelo WMS (separacao em andamento) |
| QTDPEDPENDEST | Quantidade em pedidos pendentes |

---

## Queries Uteis

### Posicao de estoque por empresa

```sql
SELECT
    E.CODEMP,
    EMP.NOMEFANTASIA,
    COUNT(DISTINCT E.CODPROD) AS QTD_PRODUTOS,
    SUM(E.ESTOQUE) AS ESTOQUE_TOTAL,
    SUM(E.RESERVADO) AS RESERVADO_TOTAL
FROM TGFEST E
JOIN TSIEMP EMP ON E.CODEMP = EMP.CODEMP
WHERE E.ATIVO = 'S'
  AND E.ESTOQUE > 0
GROUP BY E.CODEMP, EMP.NOMEFANTASIA
ORDER BY ESTOQUE_TOTAL DESC
```

### Produtos abaixo do minimo

```sql
SELECT
    E.CODEMP, E.CODLOCAL, E.CODPROD,
    P.DESCRPROD,
    E.ESTOQUE,
    E.ESTMIN,
    (E.ESTMIN - E.ESTOQUE) AS FALTA
FROM TGFEST E
JOIN TGFPRO P ON E.CODPROD = P.CODPROD
WHERE E.ATIVO = 'S'
  AND E.ESTOQUE < E.ESTMIN
  AND E.ESTMIN > 0
ORDER BY FALTA DESC
```

### Estoque reservado (com pedidos)

```sql
SELECT
    E.CODEMP, E.CODPROD,
    P.DESCRPROD,
    E.ESTOQUE,
    E.RESERVADO,
    (E.ESTOQUE - E.RESERVADO) AS DISPONIVEL
FROM TGFEST E
JOIN TGFPRO P ON E.CODPROD = P.CODPROD
WHERE E.ATIVO = 'S'
  AND E.RESERVADO > 0
ORDER BY E.RESERVADO DESC
```

### Produtos bloqueados no WMS

```sql
SELECT
    E.CODEMP, E.CODLOCAL, E.CODPROD,
    P.DESCRPROD,
    E.ESTOQUE,
    E.WMSBLOQUEADO,
    (E.ESTOQUE - NVL(E.WMSBLOQUEADO, 0)) AS LIVRE
FROM TGFEST E
JOIN TGFPRO P ON E.CODPROD = P.CODPROD
WHERE E.ATIVO = 'S'
  AND NVL(E.WMSBLOQUEADO, 0) > 0
ORDER BY E.WMSBLOQUEADO DESC
```

---

## Estatisticas MMarra

| Metrica | Valor |
|---------|-------|
| Total posicoes | 36.769 |
| Posicoes com estoque > 0 | ~30k (estimado) |

---

## Tabelas Relacionadas

| Tabela | Relacao |
|--------|---------|
| TGFEMP/TSIEMP | Empresa do estoque |
| TGFLOC | Local de armazenamento |
| TGFPRO | Produto |
| TGFPAR | Parceiro (consignacao) |
| TGFCAB | Notas que movimentam estoque |
| TGFITE | Itens que movimentam estoque |

---

## Observacoes

1. **PK composta de 6 campos** - Permite controle fino por empresa/local/produto/lote/tipo/parceiro
2. **CONTROLE vazio** - Quando produto nao usa controle de lote/serie
3. **CODPARC = 0** - Para estoque proprio (sem consignacao)
4. **TIPO = 'P'** - Maioria do estoque eh proprio
5. **ESTOQUE pode ser negativo** - Em casos excepcionais (venda antes da entrada)
6. **RESERVADO** - Bloqueia para venda mas ainda nao baixou
7. **WMSBLOQUEADO** - Reserva especifica do WMS para separacao

---

## Processos que Afetam

- [Fluxo de Compra](../../processos/compras/fluxo_compra.md) - ATUALEST = E
- [Fluxo de Venda](../../processos/vendas/fluxo_venda.md) - ATUALEST = B ou R
- [Transferencia](../../processos/estoque/transferencia.md) - ATUALEST = B (saida) e E (entrada)
- [Devolucao](../../processos/estoque/devolucao.md) - Inverte entrada/saida
