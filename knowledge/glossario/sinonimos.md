# Sinonimos e Mapeamento de Termos

> Quando o usuario usa estes termos, a LLM deve traduzir para os campos/filtros corretos do banco.

---

## Tipos de Documento (TIPMOV) - COMPLETO (dicionario oficial)

| Termo do usuario | Significado no banco | Filtro SQL |
|------------------|---------------------|------------|
| compra, nota de compra, NF entrada | Nota fiscal de compra | TIPMOV = 'C' |
| venda, nota de venda, NF saida | Nota fiscal de venda | TIPMOV = 'V' |
| pedido de compra | Pedido de compra | TIPMOV = 'O' |
| pedido de venda | Pedido de venda | TIPMOV = 'P' |
| solicitacao, requisicao de compra | Pedido de Requisicao | TIPMOV = 'J' |
| devolucao de venda | Devolucao de venda | TIPMOV = 'D' |
| devolucao de compra | Devolucao de compra | TIPMOV = 'E' |
| transferencia | Transferencia entre filiais | TIPMOV = 'T' |
| pedido de transferencia | Pedido de transferencia | TIPMOV = 'K' |
| requisicao | Requisicao | TIPMOV = 'Q' |
| recebimento | Recebimento | TIPMOV = 'R' |
| entrada | Entradas | TIPMOV = 'N' |
| producao | Producao | TIPMOV = 'F' |
| pagamento | Pagamento | TIPMOV = 'G' |
| financeiro | Financeiro | TIPMOV = 'I' |
| movimento bancario | Movimento bancario | TIPMOV = 'B' |
| faturamento | Faturamento | TIPMOV = '4' |

---

## TOPs de Compra MMarra (CODTIPOPER) - ESPECIFICO

> Filtros mais precisos para pedidos de compra. Usar CODTIPOPER em vez de TIPMOV quando possivel.

| Termo do usuario | CODTIPOPER | Descrição | Uso |
|---|---|---|---|
| pedidos de compra, compras em aberto, pendencia de compra | 1301, 1313 | Compra Casada (empenho) + Entrega Futura | CODTIPOPER IN (1301, 1313) AND PENDENTE='S' |
| compra casada, empenho, compra vinculada | 1301 | Vinculado a venda específica | CODTIPOPER = 1301 |
| entrega futura, compra programada | 1313 | Compra com entrega programada | CODTIPOPER = 1313 |

**Quando usar:**
- "pedidos de compra" / "pendencia por marca" → `CODTIPOPER IN (1301, 1313)` (mais preciso)
- Se nao souber CODTIPOPER → `TIPMOV = 'O'` (generico, funciona)
- NUNCA usar `TIPMOV = 'C'` para pedidos pendentes (C = nota de entrada, ja recebida)

---

## Status (STATUSNOTA) - CORRIGIDO (dicionario oficial)

| Termo do usuario | Significado no banco | Filtro SQL |
|------------------|---------------------|------------|
| pendente, em aberto, aguardando | Nota pendente | STATUSNOTA = 'P' (status da nota) |
| liberado, aprovado, confirmado | Nota liberada | STATUSNOTA = 'L' |
| atendimento, em atendimento | Nota em atendimento | STATUSNOTA = 'A' |

### Confirmado (Regra MMarra)
- Na MMarra, "pedido confirmado" = STATUSNOTA = 'L' (Liberado), NAO o campo APROVADO.
- CASE WHEN CAB.STATUSNOTA = 'L' THEN 'Sim' ELSE 'Nao' END AS CONFIRMADO
- Um pedido pode estar APROVADO internamente mas so eh "confirmado" quando o status muda para Liberado.

### Liberacao (TGFCAB.TIPLIBERACAO)

| Termo do usuario | Significado no banco | Filtro SQL |
|------------------|---------------------|------------|
| sem pendencia | Sem pendencia de liberacao | TIPLIBERACAO = 'S' |
| pendente de liberacao | Pendente de liberacao | TIPLIBERACAO = 'P' |
| aprovado, liberado | Aprovado/liberado | TIPLIBERACAO = 'A' |
| reprovado | Reprovado | TIPLIBERACAO = 'R' |

### Estoque (TGFEST.TIPO)

| Termo do usuario | Significado no banco | Filtro SQL |
|------------------|---------------------|------------|
| estoque proprio | Estoque proprio | TIPO = 'P' |
| estoque terceiro, consignado | Estoque de terceiro | TIPO = 'T' |

---

## Pessoas/Entidades

| Termo do usuario | Tabela/Campo | Como acessar |
|------------------|-------------|--------------|
| fornecedor | TGFPAR (P) | C JOIN P ON CODPARC, filtrar TIPMOV='C' |
| cliente | TGFPAR (P) | C JOIN P ON CODPARC, filtrar TIPMOV='V' |
| parceiro | TGFPAR (P) | C JOIN P ON CODPARC |
| vendedor | TGFVEN (V) | C JOIN V ON CODVEND |
| comprador | TGFVEN (V) | C JOIN V ON CODVEND, filtrar TIPMOV='C' ou 'O' |
| empresa, filial, loja | TSIEMP (E) | C JOIN E ON CODEMP |
| transportadora | TGFPAR (P) | C JOIN P ON CODPARCTRANSP = P.CODPARC |

---

## Produtos e Estoque

| Termo do usuario | Tabela/Campo | Como acessar |
|------------------|-------------|--------------|
| produto | TGFPRO (PR) | C JOIN I ON NUNOTA, I JOIN PR ON CODPROD |
| marca | TGFMAR (M) | C JOIN I ON NUNOTA, I JOIN PR ON CODPROD, JOIN M ON PR.CODMARCA = M.CODIGO, usar M.DESCRICAO |
| estoque, saldo | TGFEST (ES) | ES JOIN PR ON CODPROD |
| reservado, empenhado | TGFEST.RESERVADO | ES.RESERVADO |
| disponivel | TGFEST.ESTOQUE - TGFEST.RESERVADO | Calcular |
| previsao de entrega, previsao | TGFCAB.DTPREVENT | Campo Data, pode ser NULL |
| sem previsao | TGFCAB.DTPREVENT IS NULL | Pedidos sem data de previsao |
| atendido, entregue | TGFVAR.QTDATENDIDA | SUM(TGFVAR.QTDATENDIDA) por item |
| pendente de entrega, quantidade pendente | TGFITE.QTDNEG - SUM(TGFVAR.QTDATENDIDA) | Calculo com LEFT JOIN TGFVAR |

### Regra de Nivel: Cabecalho vs Item (CRITICA - LER ANTES DE GERAR SQL)
- Se a pergunta menciona MARCA ou PRODUTO → query nivel ITEM (FROM TGFITE + TGFPRO + TGFMAR + TGFVAR)
- Se a pergunta eh geral (sem marca/produto) → query nivel CABECALHO (FROM TGFCAB)
- NUNCA usar VLRNOTA quando filtrando por marca (VLRNOTA = valor do pedido INTEIRO, todas as marcas)
- Valor por marca = ITE.VLRTOT ou SUM(ITE.VLRTOT) dos itens filtrados
- Pendencia real por marca = TGFVAR (QTD_PEDIDA - QTD_ATENDIDA > 0)

### Marca - REGRA IMPORTANTE
- Para EXIBIR nome da marca: usar TGFMAR.DESCRICAO (via TGFPRO.CODMARCA = TGFMAR.CODIGO)
- Para FILTRAR por marca: UPPER(TGFMAR.DESCRICAO) = UPPER('nome') (NUNCA usar TGFPRO.MARCA para filtro)
- SEMPRE usar UPPER() em AMBOS os lados ao comparar texto (nomes cadastrados em MAIUSCULO)
- Se menciona marca: query nivel ITEM (FROM TGFITE), valor = ITE.VLRTOT

### Previsao de Entrega (MOSTRAR vs FILTRAR)
- TGFCAB.DTPREVENT = data prevista de entrega do pedido de compra
- Pode ser NULL (comprador ainda nao informou)
- "previsao de entrega" / "relatorio de previsao" = MOSTRAR coluna DTPREVENT (NAO filtrar IS NOT NULL!)
- Tratar NULL com NVL: NVL(TO_CHAR(C.DTPREVENT,'DD/MM/YYYY'),'Sem previsao')
- "pedidos COM previsao" = filtrar C.DTPREVENT IS NOT NULL (usuario pediu EXPLICITAMENTE)
- "pedidos SEM previsao" = filtrar C.DTPREVENT IS NULL (usuario pediu EXPLICITAMENTE)
- Usar TO_CHAR(C.DTPREVENT, 'MM/YYYY') para agrupar por mes

### Status em Relatorios vs Filtros de Pendencia
- "pedidos pendentes" / "pendentes" = PENDENTE = 'S' (campo correto do Sankhya, indica itens faltando)
- NUNCA usar STATUSNOTA = 'P' para filtrar pendencia (STATUSNOTA eh estado da NOTA, nao pendencia)
- "relatório de pedidos" / "acompanhamento" / "previsao" = STATUSNOTA <> 'C' (tudo menos cancelado)
- Pendencia real de itens = calcular via TGFVAR (QTD_PEDIDA - QTD_ATENDIDA > 0)
- "pedidos de compra" = TIPMOV = 'O' (pedido/ordem). "notas de compra" = TIPMOV = 'C' (entrada efetivada)
- "tudo de compra" (pedidos + notas) = TIPMOV IN ('C','O')

### Quantidade Pendente de Entrega (TGFVAR)
- TGFVAR registra entregas parciais de pedidos
- QTD_PENDENTE = TGFITE.QTDNEG - SUM(TGFVAR.QTDATENDIDA)
- SEMPRE usar LEFT JOIN na TGFVAR (nem todo item tem atendimento)
- Filtrar apenas variacoes de notas NAO canceladas (STATUSNOTA <> 'C')

---

## Financeiro

| Termo do usuario | Tabela/Campo | Filtro SQL |
|------------------|-------------|------------|
| a pagar, contas a pagar, divida | TGFFIN (F) | RECDESP = -1 |
| a receber, contas a receber | TGFFIN (F) | RECDESP = 1 |
| vencido | TGFFIN (F) | DTVENC < TRUNC(SYSDATE) AND DHBAIXA IS NULL |
| pago, baixado | TGFFIN (F) | DHBAIXA IS NOT NULL |
| em aberto, nao pago | TGFFIN (F) | DHBAIXA IS NULL |
| titulo, parcela, boleto | TGFFIN (F) | Registro financeiro |
| valor da nota | TGFCAB.VLRNOTA | Campo direto |
| valor do item | TGFITE.VLRTOT | Campo direto |

### Colunas de Valor em Pendencia (CRITICO - LLM DEVE ESCOLHER A COLUNA CERTA)

| Termo do usuario | Coluna correta | Quando usar |
|------------------|---------------|-------------|
| valor do pedido, valor total pedido, quanto custa o pedido | VLR_PEDIDO_ITEM (item) ou VLR_TOTAL_PEDIDO (agregado) | Valor TOTAL que foi pedido (inclui entregue + pendente) |
| valor entregue, valor recebido, quanto ja chegou em R$, valor atendido | VLR_ATENDIDO (item) ou VLR_TOTAL_ATENDIDO (agregado) | Valor em R$ que JA FOI ENTREGUE/RECEBIDO |
| valor pendente, valor faltando, quanto falta em R$, valor nao entregue | VLR_PENDENTE (item) ou VLR_TOTAL_PENDENTE (agregado) | Valor em R$ que FALTA ENTREGAR |
| valor da nota, vlrnota | TGFCAB.VLRNOTA | SOMENTE nivel CABECALHO sem filtro de marca. NUNCA com filtro de marca |

**Regra:** VLR_PEDIDO = VLR_ATENDIDO + VLR_PENDENTE (sempre)
**Nivel ITEM** (exemplo 23): VLR_PEDIDO_ITEM, VLR_ATENDIDO, VLR_PENDENTE (cada item)
**Nivel AGREGADO** (exemplo 22): VLR_TOTAL_PEDIDO, VLR_TOTAL_ATENDIDO, VLR_TOTAL_PENDENTE (SUM por pedido)

---

## Periodos de Tempo

| Termo do usuario | Filtro SQL Oracle |
|------------------|------------------|
| este mes, mes atual | DTNEG >= TRUNC(SYSDATE, 'MM') |
| mes passado | DTNEG >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1) AND DTNEG < TRUNC(SYSDATE, 'MM') |
| este ano, ano atual | DTNEG >= TRUNC(SYSDATE, 'YYYY') |
| hoje | DTNEG >= TRUNC(SYSDATE) AND DTNEG < TRUNC(SYSDATE) + 1 |
| ontem | DTNEG >= TRUNC(SYSDATE) - 1 AND DTNEG < TRUNC(SYSDATE) |
| ultima semana, semana passada | DTNEG >= TRUNC(SYSDATE) - 7 |
| ultimos 30 dias | DTNEG >= TRUNC(SYSDATE) - 30 |
| ultimos 3 meses | DTNEG >= ADD_MONTHS(TRUNC(SYSDATE), -3) |

---

## Rotas de Expedicao MMarra (TGFCAB.AD_TIPOSROTA)

| Termo do usuario | Significado no banco | Filtro SQL |
|------------------|---------------------|------------|
| entrega carro | Entrega por carro | AD_TIPOSROTA = 'EE' |
| entrega moto | Entrega por moto | AD_TIPOSROTA = 'EM' |
| presencial, retira | Cliente retira presencialmente | AD_TIPOSROTA = 'EPR' |
| rota barretos | Entrega Rota Barretos | AD_TIPOSROTA = 'ERBAR' |
| entrega dedicada | Entrega Dedicada (com OK supervisor) | AD_TIPOSROTA = 'ERDED' |
| retira expedicao | Retira na Expedicao | AD_TIPOSROTA = 'EREXP' |
| rota franca | Entrega Rota Franca | AD_TIPOSROTA = 'ERFR' |
| rota igarapava | Entrega Rota Igarapava | AD_TIPOSROTA = 'ERIGA' |
| rota sertaozinho | Entrega Rota Sertaozinho | AD_TIPOSROTA = 'ERSERT' |
| transportadora | Via transportadora | AD_TIPOSROTA = 'TRAN' |

---

## Acoes e Relatorios

| Termo do usuario | O que significa |
|------------------|----------------|
| ranking, top, maiores | ORDER BY ... DESC + ROWNUM <= N |
| quantos, total | COUNT(*) ou SUM() |
| lista, listar, mostrar | SELECT com detalhes |
| comparar | GROUP BY + ORDER BY |
| pendencia | Ver secao "Tipos de Pendencia" abaixo |
| faturamento | SUM(VLRNOTA) com TIPMOV = 'V' |
| previsao de entrega | TGFCAB.DTPREVENT - data prevista |
| pedidos atrasados | DTPREVENT < TRUNC(SYSDATE) AND PENDENTE = 'S' |
| itens pendentes de entrega | TGFITE.QTDNEG - SUM(TGFVAR.QTDATENDIDA) |
| itens pendentes, produtos pendentes, detalhe pendencia, item por item | Query nivel ITEM detalhada (exemplo 23). Sem GROUP BY, mostra cada item. |
| relatorio detalhado de pendencia, detalhar itens | Query nivel ITEM detalhada (exemplo 23). Inclui marca, fornecedor, comprador, tipo compra. |
| tipo de compra, casada, estoque | CODTIPOPER: 1301=Estoque, 1313=Casada. CASE para traduzir. |
| numero fabricante, referencia fabricante | PRO.AD_NUMFABRICANTE (campo customizado MMarra) |
| numero original, referencia original | PRO.AD_NUMORIGINAL (campo customizado MMarra) |
| historico de compras, compras por fornecedor, pedidos do fornecedor | Exemplo 24. TIPMOV IN ('C','O'), filtro por PAR.NOMEPARC. VLR_TOTAL_PEDIDO, VLR_TOTAL_ATENDIDO, VLR_TOTAL_PENDENTE por pedido. |
| quanto compramos, total comprado, valor comprado | Exemplo 24. SUM(VLR_TOTAL_PEDIDO) por fornecedor ou periodo. |
| valor entregue do fornecedor, quanto chegou do fornecedor, valor recebido do fornecedor | Exemplo 24 com VLR_TOTAL_ATENDIDO (por pedido). Ou Exemplo 23 com filtro fornecedor para detalhe por item. |
| valor pendente do fornecedor, quanto falta do fornecedor | Exemplo 24 com VLR_TOTAL_PENDENTE (por pedido). Ou Exemplo 23 com filtro fornecedor para detalhe por item. |
| performance fornecedor, pontualidade, confiabilidade | Exemplo 25. Ranking de atrasos com PERC_ATRASO e MEDIA_DIAS_PENDENTE. |
| fornecedor que atrasa, ranking atrasos, piores fornecedores | Exemplo 25. ORDER BY ATRASADOS DESC, PERC_ATRASO DESC. |
| fornecedores pontuais, melhores fornecedores | Exemplo 25. ORDER BY PERC_ATRASO ASC NULLS LAST. |

---

## Status de Entrega de Pedidos

| Termo do usuario | Significado | Como calcular |
|------------------|-------------|---------------|
| atrasado, atrasados | Previsao passou e pedido ainda pendente | DTPREVENT < TRUNC(SYSDATE) AND PENDENTE = 'S' |
| sem previsao | Pedido sem data de previsao | DTPREVENT IS NULL AND TIPMOV = 'O' AND PENDENTE = 'S' |
| com previsao | Pedido com data de previsao | DTPREVENT IS NOT NULL |
| entrega parcial | Item parcialmente entregue | QTDNEG > SUM(TGFVAR.QTDATENDIDA) > 0 |
| totalmente entregue | Item 100% entregue | SUM(TGFVAR.QTDATENDIDA) >= QTDNEG |
| nao entregue | Item sem nenhuma entrega | Sem registros na TGFVAR |

---

## Tipos de Pendencia (IMPORTANTE - LER ANTES DE GERAR SQL)

A palavra "pendencia" tem 3 significados diferentes. A LLM DEVE identificar qual tipo antes de gerar SQL.

| Usuario fala | Tipo | Tabelas | Filtros |
|---|---|---|---|
| pendencia de compra, pedido pendente, pendencia por marca | Pendencia de COMPRA | TGFCAB + TGFITE + TGFPRO | PENDENTE = 'S' AND TIPMOV = 'O' AND STATUSNOTA <> 'C' |
| pendencia financeira, contas a pagar, titulos pendentes | Pendencia FINANCEIRA | TGFFIN + TGFPAR | RECDESP = -1 AND DHBAIXA IS NULL |
| pendencia de venda, pedido de venda pendente | Pendencia de VENDA | TGFCAB + TGFITE + TGFPRO | PENDENTE = 'S' AND TIPMOV = 'P' AND STATUSNOTA <> 'C' |
| vencido, atrasado, contas atrasadas | Titulo VENCIDO | TGFFIN + TGFPAR | DHBAIXA IS NULL AND DTVENC < TRUNC(SYSDATE) |
| contas a receber, clientes devendo | A RECEBER | TGFFIN + TGFPAR | RECDESP = 1 AND DHBAIXA IS NULL |

### Regra de desambiguacao:
- "pendencia" SEM especificar = pendencia de COMPRA (usar TGFCAB, SEM TGFFIN)
- "pendencia" COM "financeira/pagar/titulo/boleto" = pendencia FINANCEIRA (usar TGFFIN, SEM TGFITE)
- "pendencia" COM "venda/cliente" = pendencia de VENDA (usar TGFCAB)
- Pendencia de compra/venda usa TGFCAB.VLRNOTA para valor. NAO usar TGFFIN.
- Pendencia financeira usa TGFFIN.VLRDESDOB para valor. NAO usar TGFITE.
- NUNCA usar STATUSNOTA='P' para pendencia. Usar PENDENTE='S' (campo correto do Sankhya).
- "pedidos de compra" = TIPMOV='O'. "notas de compra" = TIPMOV='C'.
