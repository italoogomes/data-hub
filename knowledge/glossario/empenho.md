# Empenho

**O que e:** Reserva de estoque vinculada a um pedido de venda. Quando um cliente faz um pedido e o produto nao esta disponivel, o sistema cria um pedido de compra "casado" (empenho) vinculado aquela venda especifica.

**No sistema:** Pedidos de compra com CODTIPOPER = 1313 (Compra Casada). O campo TIPO_COMPRA aparece como "Casada" na consulta de pendencias.

**Diferenca para compra de estoque:**
- **Compra Casada (empenho):** Vinculada a uma venda especifica. Produto ja esta "reservado" para um cliente. CODTIPOPER = 1313.
- **Compra para Estoque:** Compra para reposicao geral do estoque, sem vinculo com venda. CODTIPOPER = 1301.

**Tabelas relacionadas:** TGFCAB (CODTIPOPER), TGFVAR (vinculo pedido compra -> pedido venda)

**Termos equivalentes:** empenho, compra casada, compra vinculada, reserva

**Exemplo pratico:**
- Cliente pede 10 filtros MANN. Estoque tem 3.
- Sistema cria pedido de compra casada para 7 unidades (empenho).
- Esses 7 ja estao "prometidos" para o cliente.
