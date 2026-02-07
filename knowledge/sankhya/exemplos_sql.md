# Exemplos de Queries SQL Validadas

> Queries testadas e que funcionaram corretamente no banco Oracle do Sankhya.
> A LLM deve usar estes exemplos como referencia para gerar queries similares.

---

## 1. Marcas mais vendidas (Top N)

**Pergunta:** Quais as 10 marcas mais vendidas?

```sql
SELECT * FROM (
  SELECT PR.MARCA, SUM(I.QTDNEG) AS TOTAL_VENDIDO
  FROM TGFCAB C
  JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
  JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
  WHERE C.TIPMOV = 'V'
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
  GROUP BY PR.MARCA
  ORDER BY TOTAL_VENDIDO DESC
) WHERE ROWNUM <= 10
```

**Explicacao:** Para acessar MARCA, sempre passar por TGFITE (C -> I -> PR). Usar subquery com ROWNUM para limitar.

---

## 2. Maiores fornecedores em valor

**Pergunta:** Quais os maiores fornecedores em valor este mes?

```sql
SELECT * FROM (
  SELECT P.CODPARC, P.NOMEPARC, SUM(C.VLRNOTA) AS TOTAL
  FROM TGFCAB C
  JOIN TGFPAR P ON C.CODPARC = P.CODPARC
  WHERE C.TIPMOV = 'C'
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
  GROUP BY P.CODPARC, P.NOMEPARC
  ORDER BY TOTAL DESC
) WHERE ROWNUM <= 20
```

**Explicacao:** Fornecedor = parceiro em notas de compra (TIPMOV='C'). JOIN direto C -> P.

---

## 3. Pedidos de compra pendentes

**Pergunta:** Quais pedidos de compra estao pendentes?

```sql
SELECT C.NUNOTA, C.NUMNOTA, C.DTNEG, C.VLRNOTA, C.STATUSNOTA,
       P.NOMEPARC, V.APELIDO, E.NOMEFANTASIA
FROM TGFCAB C
JOIN TGFPAR P ON C.CODPARC = P.CODPARC
JOIN TGFVEN V ON C.CODVEND = V.CODVEND
JOIN TSIEMP E ON C.CODEMP = E.CODEMP
WHERE C.TIPMOV = 'O'
AND C.PENDENTE = 'S'
AND C.STATUSNOTA <> 'C'
AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
ORDER BY C.VLRNOTA DESC
```

**Explicacao:** Pedido de compra = TIPMOV='O', pendente = PENDENTE='S' (campo que indica itens faltando). STATUSNOTA<>'C' exclui cancelados.

---

## 4. Notas de compra do mes

**Pergunta:** Quantas notas de compra temos este mes?

```sql
SELECT COUNT(*) AS TOTAL_NOTAS, SUM(C.VLRNOTA) AS VALOR_TOTAL
FROM TGFCAB C
WHERE C.TIPMOV = 'C'
AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
```

**Explicacao:** Compra = TIPMOV='C'. Mes atual = DTNEG >= TRUNC(SYSDATE, 'MM').

---

## 5. Vendas por vendedor

**Pergunta:** Quais vendedores mais venderam este mes?

```sql
SELECT * FROM (
  SELECT V.APELIDO, COUNT(*) AS QTD_NOTAS, SUM(C.VLRNOTA) AS VALOR_TOTAL
  FROM TGFCAB C
  JOIN TGFVEN V ON C.CODVEND = V.CODVEND
  WHERE C.TIPMOV = 'V'
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
  AND C.CODVEND > 0
  GROUP BY V.APELIDO
  ORDER BY VALOR_TOTAL DESC
) WHERE ROWNUM <= 20
```

**Explicacao:** Vendedor = TGFVEN via CODVEND. Filtrar CODVEND > 0 para ignorar notas sem vendedor.

---

## 6. Produtos mais vendidos

**Pergunta:** Quais os 10 produtos mais vendidos?

```sql
SELECT * FROM (
  SELECT PR.CODPROD, PR.DESCRPROD, PR.MARCA, SUM(I.QTDNEG) AS QTD_VENDIDA
  FROM TGFCAB C
  JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
  JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
  WHERE C.TIPMOV = 'V'
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
  GROUP BY PR.CODPROD, PR.DESCRPROD, PR.MARCA
  ORDER BY QTD_VENDIDA DESC
) WHERE ROWNUM <= 10
```

**Explicacao:** Produto via TGFITE (C -> I -> PR). Nunca juntar C com PR direto.

---

## 7. Notas por empresa/filial

**Pergunta:** Quantas notas cada empresa teve este mes?

```sql
SELECT E.CODEMP, E.NOMEFANTASIA, COUNT(*) AS QTD_NOTAS, SUM(C.VLRNOTA) AS VALOR_TOTAL
FROM TGFCAB C
JOIN TSIEMP E ON C.CODEMP = E.CODEMP
WHERE C.DTNEG >= TRUNC(SYSDATE, 'MM')
GROUP BY E.CODEMP, E.NOMEFANTASIA
ORDER BY VALOR_TOTAL DESC
```

**Explicacao:** Empresa via TSIEMP (C -> E). GROUP BY com ambas colunas nao-agregadas.

---

## 8. Titulos a pagar vencidos

**Pergunta:** Quais titulos a pagar estao vencidos?

```sql
SELECT * FROM (
  SELECT P.NOMEPARC, F.NUFIN, F.VLRDESDOB, F.DTVENC,
      TRUNC(SYSDATE) - TRUNC(F.DTVENC) AS DIAS_ATRASO
  FROM TGFFIN F
  JOIN TGFPAR P ON F.CODPARC = P.CODPARC
  WHERE F.RECDESP = -1
  AND F.DHBAIXA IS NULL
  AND F.DTVENC < TRUNC(SYSDATE)
  ORDER BY F.DTVENC ASC
) WHERE ROWNUM <= 100
```

**Explicacao:** A pagar = RECDESP=-1. Vencido = DTVENC < hoje. Nao baixado = DHBAIXA IS NULL. NAO faz join com TGFITE pois nao precisa de dados de produto.

---

## 9. Estoque de um produto

**Pergunta:** Qual o estoque do produto X por empresa?

```sql
SELECT ES.CODEMP, E.NOMEFANTASIA, PR.DESCRPROD, ES.ESTOQUE, ES.RESERVADO
FROM TGFEST ES
JOIN TGFPRO PR ON ES.CODPROD = PR.CODPROD
JOIN TSIEMP E ON ES.CODEMP = E.CODEMP
WHERE ES.CODPROD = :codprod
ORDER BY ES.ESTOQUE DESC
```

**Explicacao:** Estoque direto em TGFEST. JOIN com TGFPRO e TSIEMP para nomes.

---

## 10. Compras por tipo de operacao

**Pergunta:** Quais tipos de operacao de compra mais usados?

```sql
SELECT * FROM (
  SELECT T.CODTIPOPER, T.DESCROPER, COUNT(*) AS QTD_NOTAS, SUM(C.VLRNOTA) AS VALOR_TOTAL
  FROM TGFCAB C
  JOIN TGFTOP T ON C.CODTIPOPER = T.CODTIPOPER
  WHERE C.TIPMOV = 'C'
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
  GROUP BY T.CODTIPOPER, T.DESCROPER
  ORDER BY QTD_NOTAS DESC
) WHERE ROWNUM <= 20
```

**Explicacao:** TOP = tipo de operacao via TGFTOP (C -> T).

---

## 11. Titulos a receber por cliente

**Pergunta:** Quanto cada cliente deve (a receber)?

```sql
SELECT * FROM (
  SELECT P.NOMEPARC, COUNT(*) AS QTD_TITULOS, SUM(F.VLRDESDOB) AS TOTAL_RECEBER
  FROM TGFFIN F
  JOIN TGFPAR P ON F.CODPARC = P.CODPARC
  WHERE F.RECDESP = 1
  AND F.DHBAIXA IS NULL
  GROUP BY P.NOMEPARC
  ORDER BY TOTAL_RECEBER DESC
) WHERE ROWNUM <= 20
```

**Explicacao:** A receber = RECDESP=1. Nao baixado = DHBAIXA IS NULL.

---

## 12. Solicitacoes de compra abertas

**Pergunta:** Quais solicitacoes de compra estao abertas?

```sql
SELECT C.NUNOTA, C.DTNEG, C.VLRNOTA, C.STATUSNOTA, P.NOMEPARC
FROM TGFCAB C
JOIN TGFPAR P ON C.CODPARC = P.CODPARC
WHERE C.TIPMOV = 'J'
AND C.STATUSNOTA IN ('A', 'P')
ORDER BY C.DTNEG DESC
```

**Explicacao:** Solicitacao = TIPMOV='J'. Aberta/Pendente = STATUSNOTA IN ('A','P').

---

## 13. Pendencia de COMPRA por marca (SEM TGFFIN)

**Pergunta:** Qual marca tem mais pendencia?

```sql
SELECT * FROM (
  SELECT PR.MARCA, COUNT(DISTINCT C.NUNOTA) AS QTD_PEDIDOS, SUM(DISTINCT C.VLRNOTA) AS TOTAL_VALOR
  FROM TGFCAB C
  JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
  JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
  WHERE C.PENDENTE = 'S'
  AND C.TIPMOV = 'O'
  AND C.STATUSNOTA <> 'C'
  GROUP BY PR.MARCA
  ORDER BY TOTAL_VALOR DESC
) WHERE ROWNUM <= 10
```

**Explicacao:** "Pendencia" sem especificar = pendencia de COMPRA. Usa PENDENTE='S' e TIPMOV='O' (pedido de compra). Valor via VLRNOTA (cabecalho). NAO usa TGFFIN. SEM TGFFIN!

---

## 14. Pendencia de VENDA por marca

**Pergunta:** Qual marca tem mais pendencia de venda?

```sql
SELECT * FROM (
  SELECT PR.MARCA, COUNT(DISTINCT C.NUNOTA) AS QTD_PEDIDOS, SUM(DISTINCT C.VLRNOTA) AS TOTAL_VALOR
  FROM TGFCAB C
  JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
  JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
  WHERE C.PENDENTE = 'S'
  AND C.TIPMOV = 'P'
  AND C.STATUSNOTA <> 'C'
  GROUP BY PR.MARCA
  ORDER BY TOTAL_VALOR DESC
) WHERE ROWNUM <= 10
```

**Explicacao:** Pendencia de VENDA = pedidos/notas de venda pendentes. Mesma logica da compra mas com TIPMOV V/P. SEM TGFFIN!

---

## 15. Pendencia FINANCEIRA por fornecedor (contas a pagar)

**Pergunta:** Pendencia financeira por fornecedor? / Contas a pagar pendentes?

```sql
SELECT * FROM (
  SELECT P.NOMEPARC, COUNT(*) AS QTD_TITULOS, SUM(F.VLRDESDOB) AS TOTAL_PENDENTE
  FROM TGFFIN F
  JOIN TGFPAR P ON F.CODPARC = P.CODPARC
  WHERE F.RECDESP = -1
  AND F.DHBAIXA IS NULL
  GROUP BY P.NOMEPARC
  ORDER BY TOTAL_PENDENTE DESC
) WHERE ROWNUM <= 10
```

**Explicacao:** Pendencia FINANCEIRA = titulos nao pagos. Usa TGFFIN direto com TGFPAR. SEM TGFITE (nao precisa de produto).

---

## 16. Pendencia FINANCEIRA por marca (subquery)

**Pergunta:** Pendencia financeira por marca?

```sql
SELECT * FROM (
  SELECT MARCA, SUM(VLRNOTA) AS TOTAL_PENDENTE, COUNT(*) AS QTD_NOTAS FROM (
    SELECT DISTINCT C.NUNOTA, PR.MARCA, C.VLRNOTA
    FROM TGFCAB C
    JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
    JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
    WHERE C.NUNOTA IN (
      SELECT F.NUNOTA FROM TGFFIN F WHERE F.RECDESP = -1 AND F.DHBAIXA IS NULL
    )
  ) SUB
  GROUP BY MARCA
  ORDER BY TOTAL_PENDENTE DESC
) WHERE ROWNUM <= 10
```

**Explicacao:** Cruza financeiro com produto usando subquery IN. Evita multiplicacao de valores. So usar quando o usuario pedir EXPLICITAMENTE "pendencia financeira por marca".

---

## 17. Contas a receber pendentes (clientes devendo)

**Pergunta:** Contas a receber pendentes? / Clientes devendo?

```sql
SELECT * FROM (
  SELECT P.NOMEPARC, COUNT(*) AS QTD_TITULOS, SUM(F.VLRDESDOB) AS TOTAL_A_RECEBER
  FROM TGFFIN F
  JOIN TGFPAR P ON F.CODPARC = P.CODPARC
  WHERE F.RECDESP = 1
  AND F.DHBAIXA IS NULL
  GROUP BY P.NOMEPARC
  ORDER BY TOTAL_A_RECEBER DESC
) WHERE ROWNUM <= 10
```

**Explicacao:** Contas a RECEBER = RECDESP = 1. Mesma logica do contas a pagar mas com sinal trocado. SEM TGFITE.

---

## 18. Produtos mais comprados (TGFITE SEM TGFFIN)

**Pergunta:** Top 10 produtos mais comprados?

```sql
SELECT * FROM (
  SELECT PR.CODPROD, PR.DESCRPROD, PR.MARCA, SUM(I.QTDNEG) AS QTD_COMPRADA
  FROM TGFCAB C
  JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
  JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
  WHERE C.TIPMOV = 'C'
  AND C.DTNEG >= TRUNC(SYSDATE, 'MM')
  GROUP BY PR.CODPROD, PR.DESCRPROD, PR.MARCA
  ORDER BY QTD_COMPRADA DESC
) WHERE ROWNUM <= 10
```

**Explicacao:** Produtos de compra via TGFITE (C -> I -> PR). SEM TGFFIN (nao precisa de financeiro).

---

## 19. Previsao de entrega por marca - nivel ITEM (com TGFVAR)

**Pergunta:** Previsoes de entrega dos pedidos de compra da marca Donaldson

**REGRA:** Quando a pergunta menciona MARCA ou PRODUTO, SEMPRE usar nivel ITEM (FROM TGFITE). NUNCA usar nivel CABECALHO com EXISTS + VLRNOTA (VLRNOTA = valor do pedido INTEIRO, nao so da marca filtrada).

```sql
SELECT
  CAB.NUNOTA AS PEDIDO,
  TO_CHAR(CAB.DTNEG, 'DD/MM/YYYY') AS DT_PEDIDO,
  NVL(TO_CHAR(CAB.DTPREVENT, 'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO_ENTREGA,
  NVL(TO_CHAR(CAB.DTPREVENT, 'MM/YYYY'), 'Sem previsao') AS MES_PREVISAO,
  PAR.NOMEPARC AS FORNECEDOR,
  PRO.DESCRPROD AS PRODUTO,
  MAR.DESCRICAO AS MARCA,
  ITE.QTDNEG AS QTD_PEDIDA,
  NVL(V_AGG.TOTAL_ATENDIDO, 0) AS QTD_ATENDIDA,
  (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) AS QTD_PENDENTE,
  ITE.VLRUNIT AS VLR_UNITARIO,
  ITE.VLRTOT AS VLR_TOTAL_ITEM,
  ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2) AS VLR_PENDENTE,
  CASE
    WHEN CAB.DTPREVENT IS NULL THEN 'SEM PREVISAO'
    WHEN CAB.DTPREVENT < SYSDATE THEN 'ATRASADO'
    WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 'PROXIMO'
    ELSE 'NO PRAZO'
  END AS STATUS_ENTREGA
FROM TGFITE ITE
JOIN TGFCAB CAB ON CAB.NUNOTA = ITE.NUNOTA
JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
LEFT JOIN TGFPAR PAR ON PAR.CODPARC = CAB.CODPARC
LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
LEFT JOIN (
  SELECT V.NUNOTAORIG, V.SEQUENCIAORIG, SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
  FROM TGFVAR V
  JOIN TGFCAB CV ON CV.NUNOTA = V.NUNOTA
  WHERE CV.STATUSNOTA <> 'C'
  GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
) V_AGG ON V_AGG.NUNOTAORIG = ITE.NUNOTA AND V_AGG.SEQUENCIAORIG = ITE.SEQUENCIA
WHERE CAB.TIPMOV = 'O'
  AND CAB.PENDENTE = 'S'
  AND CAB.STATUSNOTA <> 'C'
  AND UPPER(MAR.DESCRICAO) = UPPER('DONALDSON')
  AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0
  AND ROWNUM <= 500
ORDER BY CAB.DTPREVENT NULLS LAST, PRO.DESCRPROD
```

**Explicacao:** Nivel ITEM porque filtra por marca. (1) FROM TGFITE (nivel item, nao cabecalho). (2) TGFVAR para pendencia real (QTD_PEDIDA - QTD_ATENDIDA). (3) ITE.VLRTOT e VLR_PENDENTE em vez de VLRNOTA (valor correto por item/marca). (4) UPPER() no filtro. (5) PENDENTE='S' para pedidos pendentes. (6) TIPMOV='O' (pedido de compra). (7) SEM IS NOT NULL no DTPREVENT, trata NULL com NVL.

---

## 20. Itens pendentes de entrega por pedido (TGFVAR)

**Pergunta:** Quais itens do pedido X ainda estao pendentes de entrega?

```sql
SELECT I.NUNOTA, I.SEQUENCIA, PR.DESCRPROD, M.DESCRICAO AS MARCA,
  I.QTDNEG AS QTD_PEDIDA,
  NVL(V_AGG.TOTAL_ATENDIDO, 0) AS QTD_ENTREGUE,
  I.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0) AS QTD_PENDENTE
FROM TGFCAB C
JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
LEFT JOIN TGFMAR M ON PR.CODMARCA = M.CODIGO
LEFT JOIN (
  SELECT V.NUNOTAORIG, V.SEQUENCIAORIG, SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
  FROM TGFVAR V
  JOIN TGFCAB CV ON CV.NUNOTA = V.NUNOTA
  WHERE CV.STATUSNOTA <> 'C'
  GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
) V_AGG ON V_AGG.NUNOTAORIG = I.NUNOTA AND V_AGG.SEQUENCIAORIG = I.SEQUENCIA
WHERE C.TIPMOV = 'O'
  AND C.PENDENTE = 'S'
  AND C.STATUSNOTA <> 'C'
  AND I.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0) > 0
ORDER BY QTD_PENDENTE DESC
```

**Explicacao:** TGFVAR registra entregas parciais. QTD_PENDENTE = QTDNEG - SUM(QTDATENDIDA). LEFT JOIN obrigatorio (nem todo item tem entrega). Filtrar TGFVAR apenas de notas nao canceladas (STATUSNOTA <> 'C'). NVL para tratar NULL quando nao ha atendimento.

---

## 21. Previsao de entrega geral - nivel CABECALHO (sem marca)

**Pergunta:** Quais pedidos de compra tem previsao de entrega?

**AVISO:** Usar SOMENTE quando a pergunta NAO menciona marca ou produto. Se mencionar marca, usar exemplo 19 (nivel ITEM).

```sql
SELECT C.NUNOTA AS PEDIDO,
  TO_CHAR(C.DTNEG, 'DD/MM/YYYY') AS DATA_PEDIDO,
  P.NOMEPARC AS FORNECEDOR,
  C.VLRNOTA AS VALOR,
  NVL(TO_CHAR(C.DTPREVENT, 'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO_ENTREGA,
  CASE
    WHEN C.DTPREVENT IS NULL THEN 'SEM PREVISAO'
    WHEN C.DTPREVENT < SYSDATE THEN 'ATRASADO'
    WHEN C.DTPREVENT < SYSDATE + 7 THEN 'PROXIMO'
    ELSE 'NO PRAZO'
  END AS STATUS_ENTREGA
FROM TGFCAB C
JOIN TGFPAR P ON P.CODPARC = C.CODPARC
WHERE C.TIPMOV = 'O'
  AND C.PENDENTE = 'S'
  AND C.STATUSNOTA <> 'C'
  AND ROWNUM <= 500
ORDER BY C.DTPREVENT NULLS LAST
```

**Explicacao:** Nivel CABECALHO porque NAO filtra por marca. VLRNOTA eh confiavel aqui. TIPMOV='O' para pedidos de compra. PENDENTE='S' para pedidos com itens faltando. Se a pergunta mencionasse marca, deveria usar nivel ITEM (exemplo 19).

---

## REGRA CRITICA: Nivel CABECALHO vs ITEM

- Pergunta menciona MARCA ou PRODUTO → nivel ITEM (FROM TGFITE, exemplo 19)
- Pergunta geral (sem marca/produto) → nivel CABECALHO (FROM TGFCAB, exemplo 21)
- VLRNOTA so eh confiavel SEM filtro de marca. COM filtro de marca usar ITE.VLRTOT.

---

## REGRA CRITICA: NUNCA juntar TGFFIN com TGFITE

- TGFFIN tem parcelas (1 nota = N parcelas)
- TGFITE tem itens (1 nota = N itens)
- JOIN das duas pela NUNOTA gera N x M linhas = valores MULTIPLICADOS
- Se quer VALOR FINANCEIRO -> usar TGFFIN SEM TGFITE
- Se quer DADOS DE PRODUTO -> usar TGFITE SEM TGFFIN
- Se quer VALOR DA NOTA -> usar TGFCAB.VLRNOTA

---

## Padrao para Top N em Oracle

SEMPRE usar subquery + ROWNUM para limitar resultados:

```sql
SELECT * FROM (
  SELECT ... FROM ... WHERE ... ORDER BY ... DESC
) WHERE ROWNUM <= N
```

NUNCA usar LIMIT ou FETCH FIRST.
