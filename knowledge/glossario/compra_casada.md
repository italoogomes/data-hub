# Compra Casada

**O que e:** Pedido de compra vinculado a uma venda especifica (empenho). O fornecedor vai entregar diretamente para atender um pedido de cliente.

**No sistema:** CODTIPOPER = 1313. Na consulta de pendencias, TIPO_COMPRA = 'Casada'.

**Sinonimos:** empenho, compra vinculada, pedido casado

**Tabelas:** TGFCAB.CODTIPOPER = 1313

**Filtro SQL:** `CAB.CODTIPOPER = 1313`

**Exemplos de perguntas:**
- "quais pedidos casados estao pendentes?" -> filtrar TIPO_COMPRA = 'Casada'
- "pendencias de compra casada da Mann" -> TIPO_COMPRA = 'Casada' AND MARCA = 'MANN'
- "quanto temos em empenho?" -> somar VLR_PENDENTE onde TIPO_COMPRA = 'Casada'
