# Comprador

**O que e:** Funcionario da MMarra responsavel por negociar e gerenciar pedidos de compra de determinadas marcas.

**No sistema:** Tabela TGFVEN com TIPVEND = 'C' (comprador). Cada marca (TGFMAR) tem um comprador vinculado via AD_CODVEND.

**Relacao Comprador -> Marca:**
- Cada marca tem UM comprador responsavel
- Um comprador pode ser responsavel por VARIAS marcas
- O comprador aparece nos pedidos de compra como VEN.APELIDO

**Tabelas:** TGFVEN (compradores), TGFMAR.AD_CODVEND (vinculo marca->comprador)

**Exemplos de perguntas:**
- "quem compra a marca SABO?" -> agrupar por COMPRADOR onde MARCA = 'SABO'
- "quais marcas o Joao compra?" -> agrupar por MARCA onde COMPRADOR = 'JOAO'
- "pedidos do comprador Ana" -> filtrar COMPRADOR = 'ANA'
