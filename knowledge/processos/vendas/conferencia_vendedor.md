# Conferencia de Pedido — Traducao pro Vendedor

**Modulo:** Vendas / WMS
**Tabela principal:** TGFCAB

**Descricao:** Como traduzir os codigos de conferencia e WMS para linguagem que o vendedor entende.

---

## STATUSCONFERENCIA (TGFCAB)

Campo principal que indica o estado da conferencia do pedido.

| Codigo | Significado tecnico | O que dizer pro vendedor |
|--------|--------------------|-----------------------------|
| AL | Aguardando liberacao p/ conferencia | "Seu pedido ainda nao foi liberado pra conferencia" |
| AC | Aguardando conferencia | "Seu pedido ta na fila de conferencia" |
| A | Em andamento | "Seu pedido ta sendo conferido agora" |
| Z | Aguardando finalizacao | "Conferencia terminou, aguardando finalizacao" |
| F | Finalizada OK | "Conferencia OK! Pronto pra faturar" |
| D | Finalizada divergente | "Conferencia encontrou divergencia — vai recontar" |
| R | Aguardando recontagem | "Pedido em recontagem" |
| RA | Recontagem em andamento | "Pedido em recontagem" |
| RF | Recontagem finalizada OK | "Recontagem OK" |
| RD | Recontagem finalizada divergente | "Recontagem com divergencia" |
| C | Aguardando liberacao de corte | "Aguardando liberacao de corte (falta de estoque)" |

---

## SITUACAOWMS (TGFCAB)

Estado operacional no WMS — rastreia desde a separacao ate a expedicao.

| Codigo | Status tecnico | Fase | O que dizer pro vendedor |
|--------|---------------|------|--------------------------|
| -1 | Nao Enviado | — | "Ainda nao foi pra separacao" |
| 0 | Aguardando separacao | Inicio | "Na fila de separacao" |
| 1 | Enviado para separacao | WMS | "Ja ta sendo separado" |
| 2 | Em processo separacao | WMS | "Separando agora" |
| 3 | Aguardando conferencia | Conferencia | "Separado, aguardando conferencia" |
| 4 | Em processo conferencia | Conferencia | "Sendo conferido agora" |
| 9 | Conferencia validada | OK | "Conferencia OK, pronto pra faturar" |
| 10 | Aguardando conferencia (pos-separacao) | Conferencia | "Aguardando conferencia apos separacao" |
| 12 | Conferencia com divergencia | Problema | "Conferencia encontrou diferenca" |
| 13 | Parcialmente conferido | Conferencia | "Parte do pedido ja foi conferida" |
| 16 | Concluido | Finalizado | "Processo concluido" |
| 17 | Aguardando conferencia volumes | Conferencia | "Aguardando conferencia dos volumes" |
| 7 | Pedido totalmente cortado | Problema | "Pedido foi cortado (sem estoque)" |
| 8 | Pedido parcialmente cortado | Problema | "Cortaram parte do pedido" |
| 100 | Cancelada | — | "Cancelado" |

---

## Campos complementares

| Campo | Tipo | Descricao |
|-------|------|-----------|
| LIBCONF | Texto (S/N) | Flag se foi liberado para conferencia |
| NUCONFATUAL | Inteiro | Numero da conferencia atual (sequencial) |

---

## Nivel de ITEM: TGFITE.QTDCONFERIDA

Quantidade ja conferida do item — permite saber o progresso item a item.

```sql
SELECT ITE.SEQUENCIA, PRO.DESCRPROD,
       ITE.QTDNEG AS QTD_PEDIDA,
       NVL(ITE.QTDCONFERIDA, 0) AS QTD_CONFERIDA,
       ITE.QTDNEG - NVL(ITE.QTDCONFERIDA, 0) AS QTD_FALTANDO
FROM TGFITE ITE
JOIN TGFPRO PRO ON ITE.CODPROD = PRO.CODPROD
WHERE ITE.NUNOTA = :nunota
ORDER BY ITE.SEQUENCIA
```

---

## Query completa de conferencia

```sql
SELECT CAB.NUNOTA,
       CAB.STATUSCONFERENCIA,
       CAB.LIBCONF,
       CAB.NUCONFATUAL,
       CAB.SITUACAOWMS
FROM TGFCAB CAB
WHERE CAB.NUNOTA = :nunota
```

---

## Fluxo tipico WMS (pedido de venda TOP 1001)

```
Pedido criado (TOP 1001)
  ↓
WMS separa mercadoria (SITUACAOWMS: 0→1→2)
  ↓
Conferencia (SITUACAOWMS: 3→4→9)
  ↓
Faturamento (TOP 1101)
  ↓
Entrega
```

---

## Observacoes

1. **STATUSCONFERENCIA e SITUACAOWMS sao complementares**: STATUSCONFERENCIA foca no resultado da conferencia, SITUACAOWMS rastreia todo o fluxo operacional.
2. **Nem todo pedido passa por WMS**: Vendas balcao (TOP 1100) geralmente nao tem conferencia.
3. **Divergencia**: Quando STATUSCONFERENCIA = 'D' ou SITUACAOWMS = 12, significa que a quantidade conferida nao bateu com a pedida.
