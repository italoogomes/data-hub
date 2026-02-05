# Fluxo de Transferencia

**Modulo:** Estoque

**Descricao:** Movimentacao de mercadorias entre filiais/empresas do grupo MMarra. Envolve duas operacoes: saida na origem e entrada no destino.

---

## Visao Geral

A transferencia eh uma operacao que envolve duas notas:
1. **Transferencia Saida** - Filial origem envia mercadoria
2. **Transferencia Entrada** - Filial destino recebe mercadoria

**Importante:** Nao gera impacto financeiro real (ATUALFIN = 0) pois eh movimentacao interna entre empresas do mesmo grupo.

---

## TOPs de Transferencia

### Transferencia Saida (TIPMOV = V)

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | NFE | Qtd Notas | Valor |
|------------|-----------|----------|----------|-----|-----------|-------|
| **1150** | Transferencia saida | B | 0 | T | 21.712 | R$ 47M |

**Comportamento:**
- ATUALEST = B (Baixa) - Sai do estoque da origem
- ATUALFIN = 0 - Nao gera financeiro
- NFE = T - Emite NFe de transferencia

### Transferencia Entrada (TIPMOV = C)

| CODTIPOPER | Descricao | ATUALEST | ATUALFIN | NFE | Qtd Notas | Valor |
|------------|-----------|----------|----------|-----|-----------|-------|
| **1452** | Transferencia entrada | E | 0 | N | 21.276 | R$ 46M |

**Comportamento:**
- ATUALEST = E (Entrada) - Entra no estoque do destino
- ATUALFIN = 0 - Nao gera financeiro
- NFE = N - Recebe NFe da filial origem

---

## Fluxo Detalhado

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          TRANSFERENCIA ENTRE FILIAIS                       │
├────────────────────────────────┬─────────────────────────────────────────┤
│        FILIAL ORIGEM           │           FILIAL DESTINO                │
├────────────────────────────────┼─────────────────────────────────────────┤
│                                │                                         │
│  ┌─────────────┐              │                                         │
│  │  Identifica │              │                                         │
│  │ necessidade │              │                                         │
│  └──────┬──────┘              │                                         │
│         │                      │                                         │
│         ▼                      │                                         │
│  ┌─────────────┐              │                                         │
│  │   Emite     │              │                                         │
│  │  TOP 1150   │──── NFe ────────────────────┐                         │
│  │   (Saida)   │              │              │                          │
│  └──────┬──────┘              │              │                          │
│         │                      │              ▼                          │
│         ▼                      │       ┌─────────────┐                  │
│  ┌─────────────┐              │       │   Recebe    │                  │
│  │ Baixa EST   │              │       │ mercadoria  │                  │
│  │ (ATUALEST=B)│              │       └──────┬──────┘                  │
│  └─────────────┘              │              │                          │
│                                │              ▼                          │
│                                │       ┌─────────────┐                  │
│                                │       │   Lanca     │                  │
│                                │       │  TOP 1452   │                  │
│                                │       │  (Entrada)  │                  │
│                                │       └──────┬──────┘                  │
│                                │              │                          │
│                                │              ▼                          │
│                                │       ┌─────────────┐                  │
│                                │       │ Entra EST   │                  │
│                                │       │ (ATUALEST=E)│                  │
│                                │       └─────────────┘                  │
│                                │                                         │
└────────────────────────────────┴─────────────────────────────────────────┘
```

---

## Passos Detalhados

### Na Filial Origem

1. Recebe solicitacao de transferencia
2. Verifica disponibilidade de estoque
3. Separa mercadoria
4. Cria nota de transferencia saida (TOP 1150)
5. Sistema baixa estoque (ATUALEST = B)
6. Sistema emite NFe
7. Envia mercadoria com NFe

### Na Filial Destino

1. Recebe mercadoria
2. Confere itens com NFe
3. Lanca nota de transferencia entrada (TOP 1452)
4. Sistema adiciona ao estoque (ATUALEST = E)
5. Processo concluido

---

## Filiais MMarra (Participantes)

| CODEMP | Nome | Volume Notas | Valor |
|--------|------|--------------|-------|
| 1 | Ribeirao Preto (SP) - MATRIZ | 181k | R$ 343M |
| 7 | Itumbiara (GO) | 85k | R$ 295M |
| 2 | Uberlandia (MG) | 38k | R$ 44M |
| 4 | Aracatuba (SP) | 24k | R$ 40M |
| 6 | Service Ribeirao (SP) | 9k | R$ 52M |
| 8 | Rio Verde (GO) | 5k | R$ 6M |

**Fluxo tipico:** Matriz (1) distribui para filiais (2, 4, 7, 8)

---

## Tabelas Envolvidas

| Tabela | Papel no Processo |
|--------|-------------------|
| **TGFCAB** | Cabecalho das notas (saida e entrada) |
| **TGFITE** | Itens transferidos |
| **TGFPRO** | Produtos movimentados |
| **TGFTOP** | Define comportamento |
| **TSIEMP** | Empresa origem e destino |
| **TGFEST** | Posicao de estoque (baixa origem, entrada destino) |

---

## Campos Importantes

### TGFCAB (Cabecalho)

| Campo | Transf. Saida | Transf. Entrada |
|-------|---------------|-----------------|
| CODTIPOPER | 1150 | 1452 |
| TIPMOV | V (Venda) | C (Compra) |
| CODEMP | Empresa origem | Empresa destino |
| CODPARC | Filial destino | Filial origem |
| VLRNOTA | Valor transf. | Valor transf. |
| NUNOTA_ORIG | - | Nota de saida |

### Vinculo Entre Notas

A entrada geralmente referencia a saida:
- **NUNOTA_ORIG** ou campo similar na entrada
- Permite rastrear origem da mercadoria
- Garante consistencia entre operacoes

---

## Impacto no Estoque

### Na Origem (TOP 1150)
```sql
-- Baixa estoque (ATUALEST = B)
-- TGFEST.ESTOQUE = TGFEST.ESTOQUE - TGFITE.QTDNEG
-- Onde: CODEMP = empresa origem
```

### No Destino (TOP 1452)
```sql
-- Entrada estoque (ATUALEST = E)
-- TGFEST.ESTOQUE = TGFEST.ESTOQUE + TGFITE.QTDNEG
-- Onde: CODEMP = empresa destino
```

### Estoque Consolidado
```sql
-- Soma zero no consolidado (999)
-- Saida origem (-X) + Entrada destino (+X) = 0
-- Total do grupo nao muda
```

---

## Impacto no Financeiro

**NAO GERA FINANCEIRO** - ATUALFIN = 0 em ambas as TOPs

A transferencia eh movimento interno:
- Nao cria titulo a pagar
- Nao cria titulo a receber
- Eh apenas movimentacao contabil/fiscal

---

## Queries Uteis

### Transferencias do mes
```sql
SELECT C.CODEMP, E.NOMEFANTASIA,
       CASE C.CODTIPOPER WHEN 1150 THEN 'SAIDA' ELSE 'ENTRADA' END AS TIPO,
       COUNT(*) AS QTD,
       SUM(C.VLRNOTA) AS VLR_TOTAL
FROM TGFCAB C
JOIN TSIEMP E ON C.CODEMP = E.CODEMP
WHERE C.CODTIPOPER IN (1150, 1452)
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
GROUP BY C.CODEMP, E.NOMEFANTASIA, C.CODTIPOPER
ORDER BY C.CODEMP, C.CODTIPOPER
```

### Matriz de transferencias entre filiais
```sql
SELECT
    ORIG.NOMEFANTASIA AS ORIGEM,
    DEST.NOMEFANTASIA AS DESTINO,
    COUNT(*) AS QTD_TRANSF,
    SUM(C.VLRNOTA) AS VLR_TOTAL
FROM TGFCAB C
JOIN TSIEMP ORIG ON C.CODEMP = ORIG.CODEMP
JOIN TGFPAR P ON C.CODPARC = P.CODPARC
JOIN TSIEMP DEST ON P.CODEMP = DEST.CODEMP
WHERE C.CODTIPOPER = 1150
GROUP BY ORIG.NOMEFANTASIA, DEST.NOMEFANTASIA
ORDER BY QTD_TRANSF DESC
```

### Produtos mais transferidos
```sql
SELECT P.CODPROD, P.DESCRPROD,
       COUNT(*) AS QTD_TRANSF,
       SUM(I.QTDNEG) AS QTD_ITENS
FROM TGFITE I
JOIN TGFCAB C ON I.NUNOTA = C.NUNOTA
JOIN TGFPRO P ON I.CODPROD = P.CODPROD
WHERE C.CODTIPOPER = 1150
GROUP BY P.CODPROD, P.DESCRPROD
ORDER BY QTD_TRANSF DESC
```

### Transferencias pendentes de entrada
```sql
-- Saidas sem entrada correspondente
SELECT S.NUNOTA, S.DTNEG, S.CODEMP, S.VLRNOTA
FROM TGFCAB S
WHERE S.CODTIPOPER = 1150
  AND NOT EXISTS (
      SELECT 1 FROM TGFCAB E
      WHERE E.CODTIPOPER = 1452
        AND E.NUNOTA_ORIG = S.NUNOTA
  )
ORDER BY S.DTNEG
```

---

## Estatisticas MMarra

Baseado nos dados extraidos:

| Metrica | Valor |
|---------|-------|
| Transferencias saida | 21.712 notas |
| Transferencias entrada | 21.276 notas |
| Valor total | R$ 46-47M |
| % das operacoes | ~6% do movimento |

**Diferenca saida/entrada:** 436 notas - pode indicar transferencias em transito ou inconsistencias a verificar.

---

## CFOP de Transferencia

| Situacao | CFOP |
|----------|------|
| Transf. saida dentro estado | 5.152 |
| Transf. saida fora estado | 6.152 |
| Transf. entrada dentro estado | 1.152 |
| Transf. entrada fora estado | 2.152 |

---

## Observacoes

1. **Operacao casada** - Toda saida deve ter entrada correspondente
2. **Diferenca de ~400 notas** - Pode indicar transferencias em transito
3. **Sem impacto financeiro** - Apenas movimentacao de estoque
4. **NFe obrigatoria** - Mesmo entre filiais, precisa de NFe fiscal
5. **Matriz como hub** - Provavelmente a matriz (CODEMP=1) centraliza e distribui
6. **Tempo de transito** - Saida e entrada podem ter datas diferentes

---

## Pontos de Atencao

### Riscos
- Transferencia sem entrada = mercadoria "perdida"
- Entrada sem saida = estoque inconsistente
- CFOP errado = problema fiscal

### Controles
- Conciliar saidas x entradas periodicamente
- Monitorar transferencias em transito
- Validar CFOPs por estado

---

## Processos Relacionados

- [Fluxo de Venda](../vendas/fluxo_venda.md) - Transferencia abastece filiais para venda
- [Fluxo de Compra](../compras/fluxo_compra.md) - Compra centralizada + transferencia
- [Devolucao](devolucao.md) - Pode haver devolucao de transferencia
