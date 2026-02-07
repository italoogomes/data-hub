# Relacionamentos entre Tabelas do Sankhya

## Regras de JOIN

### TGFCAB (C) - Cabecalho de Notas - TABELA CENTRAL
- TGFCAB.NUNOTA = TGFITE.NUNOTA (itens da nota)
- TGFCAB.CODPARC = TGFPAR.CODPARC (parceiro/fornecedor/cliente)
- TGFCAB.CODVEND = TGFVEN.CODVEND (vendedor/comprador responsavel)
- TGFCAB.CODTIPOPER = TGFTOP.CODTIPOPER (tipo de operacao)
- TGFCAB.CODEMP = TSIEMP.CODEMP (empresa/filial)
- TGFCAB.NUNOTA = TGFFIN.NUNOTA (financeiro da nota)
- TGFCAB.CODPARCDEST = TGFPAR.CODPARC (parceiro destino)
- TGFCAB.CODPARCTRANSP = TGFPAR.CODPARC (transportadora)
- TGFCAB.DTPREVENT = Data de previsao de entrega (pode ser NULL)

### TGFITE (I) - Itens da Nota - PONTE PARA PRODUTOS
- TGFITE.NUNOTA = TGFCAB.NUNOTA (nota pai)
- TGFITE.CODPROD = TGFPRO.CODPROD (produto)
- TGFITE.CODVEND = TGFVEN.CODVEND (vendedor do item)
- TGFITE.CODVOL = TGFVOL.CODVOL (unidade de medida)

### TGFPAR (P) - Parceiros/Clientes/Fornecedores
- TGFPAR.CODPARC = TGFCAB.CODPARC (notas do parceiro)
- TGFPAR.CODPARC = TGFFIN.CODPARC (financeiro do parceiro)
- TGFPAR.CODVEND = TGFVEN.CODVEND (vendedor responsavel)
- TGFPAR.CODEMP = TSIEMP.CODEMP (empresa padrao)

### TGFPRO (PR) - Produtos
- TGFPRO.CODPROD = TGFITE.CODPROD (itens que usam este produto)
- TGFPRO.CODPROD = TGFEST.CODPROD (estoque do produto)
- TGFPRO.CODPROD = AD_TGFPROAUXMMA.CODPROD (codigos auxiliares)
- TGFPRO.CODPROD = AD_TGFCUSMMA.CODPROD (historico de custos)
- TGFPRO.CODPARCFORN = TGFPAR.CODPARC (fornecedor padrao)
- TGFPRO.CODMARCA = TGFMAR.CODIGO (marca do produto)

### TGFMAR (M) - Marcas de Produtos
- TGFMAR.CODIGO = TGFPRO.CODMARCA (produtos desta marca)
- TGFMAR.AD_CODVEND = TGFVEN.CODVEND (comprador responsavel pela marca)

### TGFVAR - Variacoes/Atendimentos de Pedido
- TGFVAR.NUNOTAORIG = TGFCAB.NUNOTA (pedido original)
- TGFVAR.SEQUENCIAORIG = TGFITE.SEQUENCIA (item original no pedido)
- TGFVAR.NUNOTA = TGFCAB.NUNOTA (nota de atendimento)

### TGFTOP (T) - Tipos de Operacao
- TGFTOP.CODTIPOPER = TGFCAB.CODTIPOPER (notas com esta TOP)

### TGFVEN (V) - Vendedores/Compradores
- TGFVEN.CODVEND = TGFCAB.CODVEND (notas do vendedor)
- TGFVEN.CODGER = TGFVEN.CODVEND (gerente - auto-referencia)
- TGFVEN.CODEMP = TSIEMP.CODEMP (empresa do vendedor)

### TSIEMP (E) - Empresas/Filiais
- TSIEMP.CODEMP = TGFCAB.CODEMP (notas da empresa)
- TSIEMP.CODEMP = TGFEST.CODEMP (estoque da empresa)
- TSIEMP.CODEMP = TGFFIN.CODEMP (financeiro da empresa)
- TSIEMP.CODEMPMATRIZ = TSIEMP.CODEMP (empresa matriz)

### TGFEST (ES) - Posicao de Estoque
- TGFEST.CODPROD = TGFPRO.CODPROD (produto)
- TGFEST.CODEMP = TSIEMP.CODEMP (empresa)
- TGFEST.CODPARC = TGFPAR.CODPARC (parceiro consignado)

### TGFFIN (F) - Titulos Financeiros
- TGFFIN.NUNOTA = TGFCAB.NUNOTA (nota de origem)
- TGFFIN.CODPARC = TGFPAR.CODPARC (parceiro)
- TGFFIN.CODEMP = TSIEMP.CODEMP (empresa)
- TGFFIN.CODVEND = TGFVEN.CODVEND (vendedor)
- TGFFIN.CODTIPOPER = TGFTOP.CODTIPOPER (tipo de operacao)

### TGFCOT (COT) - Cotacoes de Compra
- TGFCOT.NUNOTAORIG = TGFCAB.NUNOTA (solicitacao de origem)
- TGFCOT.CODEMP = TSIEMP.CODEMP (empresa)

### AD_TGFPROAUXMMA - Numeros Auxiliares de Produtos
- AD_TGFPROAUXMMA.CODPROD = TGFPRO.CODPROD (produto)
- AD_TGFPROAUXMMA.CODIGO = TGFMAR.CODMARCA (marca do produto)

### AD_TGFCUSMMA - Historico de Custos
- AD_TGFCUSMMA.CODPROD = TGFPRO.CODPROD (produto)
- AD_TGFCUSMMA.CODEMP = TSIEMP.CODEMP (empresa)

> **Nota:** Relacionamentos confirmados pelo dicionario oficial (TDDLIG) em 2026-02-07. 500+ registros validados.

---

## Regra de Nivel: Cabecalho vs Item (CRITICA)

A MARCA esta no ITEM (TGFITE -> TGFPRO -> TGFMAR), NAO no pedido (TGFCAB).
O VALOR por marca esta no ITEM (TGFITE.VLRTOT), NAO no pedido (TGFCAB.VLRNOTA).
A PENDENCIA real eh via TGFVAR (QTD_PEDIDA - QTD_ATENDIDA), NAO via STATUSNOTA.

**REGRA:** Se a pergunta menciona MARCA ou PRODUTO, a query DEVE ser no nivel de ITEM (FROM TGFITE).

| Pergunta | Nivel | Motivo |
|----------|-------|--------|
| "Pedidos pendentes" (geral) | CABECALHO | Sem filtro de item, VLRNOTA correto |
| "Pedidos da marca X" | ITEM | Marca esta no item, valor = ITE.VLRTOT |
| "Quantidades pendentes" | ITEM | Precisa TGFVAR |
| "Previsao de entrega" (geral) | CABECALHO | DTPREVENT eh do cabecalho |
| "Previsao da marca X" | ITEM | Filtro por marca exige nivel item |
| "Valor pendente da marca X" | ITEM | Valor da marca = SUM(ITE.VLRTOT) |
| "Pedidos de um fornecedor" | CABECALHO | Fornecedor esta no cabecalho |

VLRNOTA so eh confiavel quando NAO ha filtro por marca/produto. Se filtrar por marca e usar VLRNOTA, o valor sera MUITO maior que o real (inclui todas as marcas do pedido).

---

## Caminhos Importantes (SEMPRE SEGUIR ESTES)

### Para acessar PRODUTO a partir de NOTA:
TGFCAB C JOIN TGFITE I ON C.NUNOTA = I.NUNOTA JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
NUNCA fazer TGFCAB JOIN TGFPRO direto! TGFCAB NAO TEM CODPROD!

### Para acessar MARCA a partir de NOTA:
TGFCAB C JOIN TGFITE I ON C.NUNOTA = I.NUNOTA JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD JOIN TGFMAR M ON PR.CODMARCA = M.CODIGO
Usar UPPER(M.DESCRICAO) = UPPER('nome') para filtrar (NUNCA usar PR.MARCA)

### Quando filtrar por MARCA - usar nivel ITEM (NAO EXISTS no cabecalho):
Se a pergunta menciona marca/produto, a query DEVE comecar do ITEM:
```
FROM TGFITE ITE
JOIN TGFCAB CAB ON CAB.NUNOTA = ITE.NUNOTA
JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
LEFT JOIN TGFVAR V_AGG ... (para pendencia real)
WHERE UPPER(MAR.DESCRICAO) = UPPER('DONALDSON')
```
Valor = ITE.VLRTOT (NAO VLRNOTA). Pendencia = QTD_PEDIDA - QTD_ATENDIDA via TGFVAR.

### Para acessar PREVISAO DE ENTREGA:
TGFCAB.DTPREVENT (campo Data, pode ser NULL)
Previsao informada pelo comprador apos contato com fornecedor.
MOSTRAR com NVL, NAO filtrar IS NOT NULL a menos que usuario peca explicitamente.

### Para acessar ESTOQUE a partir de NOTA:
TGFCAB C JOIN TGFITE I ON C.NUNOTA = I.NUNOTA JOIN TGFEST ES ON I.CODPROD = ES.CODPROD AND C.CODEMP = ES.CODEMP

### Para acessar FINANCEIRO de uma NOTA:
TGFCAB C JOIN TGFFIN F ON C.NUNOTA = F.NUNOTA

### Para acessar NOME DO PARCEIRO:
TGFCAB C JOIN TGFPAR P ON C.CODPARC = P.CODPARC
Usar P.NOMEPARC para o nome

### Para acessar NOME DO VENDEDOR:
TGFCAB C JOIN TGFVEN V ON C.CODVEND = V.CODVEND
Usar V.APELIDO para o nome

### Para acessar DESCRICAO DA TOP:
TGFCAB C JOIN TGFTOP T ON C.CODTIPOPER = T.CODTIPOPER
Usar T.DESCROPER para a descricao

### Para acessar NOME DA EMPRESA:
TGFCAB C JOIN TSIEMP E ON C.CODEMP = E.CODEMP
Usar E.NOMEFANTASIA para o nome

---

## Filtros Comuns de Negocio

### Tipos de Movimento (TGFCAB.TIPMOV) - COMPLETO (do dicionario oficial):
- 'V' = Venda
- 'C' = Compra
- 'D' = Devolucao de venda
- 'E' = Devolucao de compra
- 'O' = Pedido de compra
- 'P' = Pedido de venda
- 'J' = Pedido de Requisicao (solicitacao de compra)
- 'T' = Transferencia
- 'K' = Pedido de Transferencia
- 'Q' = Requisicao
- 'R' = Recebimento
- 'N' = Entradas
- 'B' = Movimento bancario
- 'F' = Producao
- 'G' = Pagamento
- 'I' = Financeiro
- 'L' = Devolucao de Requisicao
- 'M' = Devolucao de Transferencia
- '1' = NF Deposito
- '2' = PD Devol./Procuracao/Warrant
- '3' = Saidas
- '4' = Faturamento
- '8' = RD8

### Status da Nota (TGFCAB.STATUSNOTA):
- 'P' = Pendente
- 'L' = Liberada
- 'A' = Atendimento

### TOPs mais usadas (TGFCAB.CODTIPOPER):
- 1100 = Venda Balcao (120k notas)
- 1101 = Venda NFe (105k notas)
- 1209 = Compra Revenda (47k notas)
- 1301 = Compra Revenda alternativa
- 1313 = Entrega Futura/Empenho
- 1321 = Transferencia Empenho
- 1804 = Solicitacao de Compra

### Liberacao (TGFCAB.TIPLIBERACAO):
- 'S' = Sem pendencia
- 'P' = Pendente
- 'A' = Aprovado
- 'R' = Reprovado

### Financeiro (TGFFIN.RECDESP):
- 1 = A Receber
- -1 = A Pagar

### Estoque (TGFEST.TIPO):
- 'P' = Proprio
- 'T' = Terceiro

---

## Aliases Padrao para SQL

| Tabela | Alias | Descricao |
|--------|-------|-----------|
| TGFCAB | C | Cabecalho de notas |
| TGFITE | I | Itens das notas |
| TGFPAR | P | Parceiros |
| TGFPRO | PR | Produtos |
| TGFTOP | T | Tipos de operacao |
| TGFVEN | V | Vendedores |
| TSIEMP | E | Empresas |
| TGFEST | ES | Estoque |
| TGFFIN | F | Financeiro |
| TGFCOT | COT | Cotacoes |
| TGFMAR | M | Marcas |
| TGFVAR | VAR | Variacoes/Atendimentos |

---

## JOINs PERIGOSOS - CUIDADO

### NUNCA juntar TGFFIN com TGFITE na mesma query
- TGFFIN tem parcelas (1 nota = N parcelas)
- TGFITE tem itens (1 nota = N itens)
- JOIN das duas pela NUNOTA gera N x M linhas = valores MULTIPLICADOS
- Se precisa dos dois, usar SUBQUERIES separadas

### Quando usar cada tabela:
- Quer VALOR FINANCEIRO (quanto deve, vencido, pago) -> TGFFIN (sem TGFITE)
- Quer DADOS DE PRODUTO (marca, descricao, quantidade) -> TGFITE + TGFPRO (sem TGFFIN)
- Quer VALOR DA NOTA (total) -> TGFCAB.VLRNOTA (sem TGFFIN nem TGFITE)
- Quer ambos -> usar SUBQUERY ou CTE

---

## Regras de Pendencia (IMPORTANTE - LER ANTES DE GERAR SQL)

A palavra "pendencia" tem significados diferentes. IDENTIFICAR o tipo ANTES de gerar SQL.

### Pendencia de COMPRA (pedidos pendentes de entrega):
- Tabelas: TGFCAB + TGFITE + TGFPRO + TGFPAR
- Filtros: PENDENTE = 'S' AND TIPMOV = 'O' AND STATUSNOTA <> 'C'
- Valor: usar TGFCAB.VLRNOTA (SUM DISTINCT)
- NAO usar TGFFIN
- PENDENTE = 'S' indica que o pedido ainda tem itens faltando (Sankhya calcula via TGFVAR)
- TIPMOV = 'O' = pedido de compra. TIPMOV = 'C' = nota de compra (ja recebida)

### Pendencia de VENDA (pedidos de venda pendentes):
- Tabelas: TGFCAB + TGFITE + TGFPRO + TGFPAR
- Filtros: PENDENTE = 'S' AND TIPMOV = 'P' AND STATUSNOTA <> 'C'
- Valor: usar TGFCAB.VLRNOTA (SUM DISTINCT)
- NAO usar TGFFIN

### Pendencia FINANCEIRA (titulos nao pagos):
- Tabelas: TGFFIN + TGFPAR
- Filtros: DHBAIXA IS NULL
- RECDESP = -1 para contas a PAGAR
- RECDESP = 1 para contas a RECEBER
- Valor: usar TGFFIN.VLRDESDOB
- NAO usar TGFITE

### Regra de desambiguacao:
- "pendencia" SEM especificar = pendencia de COMPRA: PENDENTE='S', TIPMOV='O', STATUSNOTA<>'C' (TGFCAB, SEM TGFFIN)
- "pendencia financeira/contas a pagar/titulo" = TGFFIN, SEM TGFITE
- "pendencia de venda" = PENDENTE='S', TIPMOV='P', STATUSNOTA<>'C' (TGFCAB)
- NUNCA usar STATUSNOTA='P' para pendencia. STATUSNOTA eh estado da NOTA (A/P/L/C). PENDENTE (S/N) eh o campo correto.

---

## Erros Comuns de SQL

1. JOIN TGFCAB com TGFPRO direto: ERRADO. Passar por TGFITE.
2. Usar LIMIT em vez de ROWNUM: Oracle nao tem LIMIT.
3. Alias com espaco ou aspas: Oracle nao aceita.
4. GROUP BY incompleto: todas as colunas nao-agregadas devem estar no GROUP BY.
5. MARCA esta em TGFPRO, nao em TGFCAB nem TGFITE.
6. NOMEPARC esta em TGFPAR, nao em TGFCAB.
7. DESCRPROD esta em TGFPRO, nao em TGFITE.
8. APELIDO esta em TGFVEN, nao em TGFCAB.
9. NUNCA juntar TGFFIN com TGFITE (multiplica valores).
10. Para FILTRAR por marca, usar TGFMAR.DESCRICAO (NUNCA TGFPRO.MARCA para filtro).
11. Para dados no nivel do CABECALHO com filtro de marca, usar EXISTS (NAO JOIN direto com TGFITE).
12. DTPREVENT pode ser NULL - sempre tratar com NVL ou IS NOT NULL.
