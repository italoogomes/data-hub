# Compra para Estoque (Entrega Futura)

**O que e:** Pedido de compra para reposicao de estoque geral, sem vinculo com venda especifica. Compra programada para manter o estoque abastecido.

**No sistema:** CODTIPOPER = 1301. Na consulta de pendencias, TIPO_COMPRA = 'Estoque'.

**Sinonimos:** compra de estoque, entrega futura, compra programada, reposicao

**Tabelas:** TGFCAB.CODTIPOPER = 1301

**Filtro SQL:** `CAB.CODTIPOPER = 1301`

**Exemplos de perguntas:**
- "quais compras de estoque estao pendentes?" -> filtrar TIPO_COMPRA = 'Estoque'
- "pedidos de entrega futura" -> TIPO_COMPRA = 'Estoque'
