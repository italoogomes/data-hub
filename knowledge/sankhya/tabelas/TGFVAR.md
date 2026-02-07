# TGFVAR

**Descricao:** Variacoes/Atendimentos de Pedido
**Total de registros:** 28.171

## Campos

| Campo | Tipo | PK/FK | Descricao |
|-------|------|-------|-----------|
| NUNOTAORIG | Inteiro | FK -> TGFCAB.NUNOTA | Nro. unico do pedido original |
| SEQUENCIAORIG | Inteiro | FK -> TGFITE.SEQUENCIA | Seq. do item no pedido original |
| NUNOTA | Inteiro | FK -> TGFCAB.NUNOTA | Nro. unico da nota de atendimento |
| SEQUENCIA | Inteiro | | Seq. do item na nota de atendimento |
| QTDATENDIDA | Decimal | | Quantidade atendida nessa variacao |
| CUSATEND | Decimal | | Custo do atendimento |
| ORDEMPROD | Inteiro | | Ordem do produto |
| STATUSNOTA | Texto | | Status da nota de atendimento |
| FIXACAO | Texto | | Fixacao |
| NROATOCONCDRAW | Texto | | Numero do ato concessorio de Drawback |
| NROMEMORANDO | Inteiro | | Nro Memorando Exportacao |
| NROREGEXPORT | Texto | | Numero do Registro de Exportacao |

## Relacionamentos

- `TGFVAR.NUNOTAORIG` -> `TGFCAB.NUNOTA` (pedido original)
- `TGFVAR.SEQUENCIAORIG` -> `TGFITE.SEQUENCIA` (item original no pedido)
- `TGFVAR.NUNOTA` -> `TGFCAB.NUNOTA` (nota de atendimento)
- `TGFVAR.SEQUENCIA` -> `TGFITE.SEQUENCIA` (item na nota de atendimento)

## Observacoes

### Calculo de Quantidade Pendente (IMPORTANTE)

A TGFVAR registra quanto de cada item do pedido ja foi atendido (entregue/recebido).

**Formula:**
```
QTD_PENDENTE = TGFITE.QTDNEG - SUM(TGFVAR.QTDATENDIDA)
```

**Regras:**
- Pedido totalmente atendido quando QTD_PENDENTE = 0 para todos os itens
- SEMPRE usar LEFT JOIN na TGFVAR (nem todo item tem atendimento ainda)
- Filtrar apenas variacoes de notas NAO canceladas: `JOIN TGFCAB C ON C.NUNOTA = V.NUNOTA WHERE C.STATUSNOTA <> 'C'`
- Agrupar por NUNOTAORIG + SEQUENCIAORIG para somar todas as entregas parciais

### Exemplo de uso:
```sql
LEFT JOIN (
    SELECT V.NUNOTAORIG, V.SEQUENCIAORIG, SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
    FROM TGFVAR V
    JOIN TGFCAB C ON C.NUNOTA = V.NUNOTA
    WHERE C.STATUSNOTA <> 'C'
    GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
) V_AGG ON V_AGG.NUNOTAORIG = ITE.NUNOTA AND V_AGG.SEQUENCIAORIG = ITE.SEQUENCIA
```
