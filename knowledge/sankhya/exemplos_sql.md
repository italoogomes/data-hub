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
  PRO.CODPROD,
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
  AND ITE.PENDENTE = 'S'
  AND UPPER(MAR.DESCRICAO) = UPPER('DONALDSON')
  AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0
  AND ROWNUM <= 500
ORDER BY CAB.DTPREVENT NULLS LAST, PRO.DESCRPROD
```

**Explicacao:** Nivel ITEM porque filtra por marca. (1) FROM TGFITE (nivel item, nao cabecalho). (2) TGFVAR para pendencia real (QTD_PEDIDA - QTD_ATENDIDA). (3) ITE.VLRTOT e VLR_PENDENTE em vez de VLRNOTA (valor correto por item/marca). (4) UPPER() no filtro. (5) CAB.PENDENTE='S' para pedidos pendentes. (6) **ITE.PENDENTE='S' CRITICO** para excluir itens cancelados/cortados. (7) TIPMOV='O' (pedido de compra). (8) SEM IS NOT NULL no DTPREVENT, trata NULL com NVL.

---

## 20. Itens pendentes de entrega por pedido (TGFVAR)

**Pergunta:** Quais itens do pedido X ainda estao pendentes de entrega?

```sql
SELECT I.NUNOTA, I.SEQUENCIA, PR.CODPROD, PR.DESCRPROD, M.DESCRICAO AS MARCA,
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
  AND I.PENDENTE = 'S'
  AND I.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0) > 0
ORDER BY QTD_PENDENTE DESC
```

**Explicacao:** TGFVAR registra entregas parciais. QTD_PENDENTE = QTDNEG - SUM(QTDATENDIDA). LEFT JOIN obrigatorio (nem todo item tem entrega). Filtrar TGFVAR apenas de notas nao canceladas (STATUSNOTA <> 'C'). **I.PENDENTE='S' CRITICO** para excluir itens cancelados/cortados. NVL para tratar NULL quando nao ha atendimento.

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

## 22. Pedidos pendentes por marca - MMarra especifico (CODTIPOPER)

**Pergunta:** Quantos pedidos da marca X eu tenho em aberto? Quantos itens pendentes por marca?

**IMPORTANTE:** Este eh o exemplo MAIS COMPLETO para compras MMarra. Usa CODTIPOPER (mais preciso que TIPMOV).

```sql
SELECT
    CAB.NUNOTA AS PEDIDO,
    TO_CHAR(CAB.DTNEG, 'DD/MM/YYYY') AS DT_PEDIDO,
    MAR.DESCRICAO AS MARCA,
    VEN.APELIDO AS COMPRADOR,
    COUNT(DISTINCT ITE.SEQUENCIA) AS QTD_ITENS,
    SUM(ITE.QTDNEG) AS QTD_TOTAL_PEDIDA,
    SUM(NVL(V_AGG.TOTAL_ATENDIDO, 0)) AS QTD_TOTAL_ENTREGUE,
    SUM(ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) AS QTD_TOTAL_PENDENTE,
    SUM(ITE.VLRTOT) AS VLR_TOTAL_PEDIDO,
    SUM(ROUND(NVL(V_AGG.TOTAL_ATENDIDO, 0) * ITE.VLRUNIT, 2)) AS VLR_TOTAL_ATENDIDO,
    SUM(ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2)) AS VLR_TOTAL_PENDENTE,
    NVL(TO_CHAR(CAB.DTPREVENT, 'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO_ENTREGA,
    TRUNC(SYSDATE) - TRUNC(CAB.DTNEG) AS DIAS_ABERTO
FROM TGFCAB CAB
JOIN TGFITE ITE ON CAB.NUNOTA = ITE.NUNOTA
JOIN TGFPRO PRO ON ITE.CODPROD = PRO.CODPROD
LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
LEFT JOIN TGFVEN VEN ON VEN.CODVEND = MAR.AD_CODVEND
LEFT JOIN (
    SELECT V.NUNOTAORIG, V.SEQUENCIAORIG,
           SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
    FROM TGFVAR V
    JOIN TGFCAB C ON C.NUNOTA = V.NUNOTA
    WHERE C.STATUSNOTA <> 'C'
    GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
) V_AGG ON V_AGG.NUNOTAORIG = ITE.NUNOTA
       AND V_AGG.SEQUENCIAORIG = ITE.SEQUENCIA
WHERE CAB.CODTIPOPER IN (1301, 1313)
  AND CAB.PENDENTE = 'S'
  AND CAB.STATUSNOTA <> 'C'
  AND ITE.PENDENTE = 'S'
  AND UPPER(MAR.DESCRICAO) = UPPER('DONALDSON')
  AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0
GROUP BY CAB.NUNOTA, CAB.DTNEG,
         MAR.DESCRICAO, VEN.APELIDO, CAB.DTPREVENT
ORDER BY QTD_TOTAL_PENDENTE DESC, DIAS_ABERTO DESC
```

**Explicacao:** (1) CODTIPOPER IN (1301, 1313) filtra tipos especificos MMarra (mais preciso que TIPMOV='O'). (2) Nivel ITEM porque filtra por marca. (3) TGFVAR com agregacao para pendencia real. (4) Comprador vem de TGFMAR.AD_CODVEND. (5) UPPER() no filtro de marca. (6) GROUP BY no final para consolidar por pedido. (7) **Colunas de valor**: VLR_TOTAL_PEDIDO = SUM do valor pedido. VLR_TOTAL_ATENDIDO = SUM do valor ja entregue. VLR_TOTAL_PENDENTE = SUM do valor faltando. NAO usar VLRNOTA (inclui todas as marcas). (8) **ITE.PENDENTE='S' CRITICO** para excluir itens cancelados/cortados pelo usuario. (9) Retorna apenas itens com pendencia > 0.

**Uso:** Esta query responde "quantos pedidos da marca X em aberto", "quantos itens pendentes", "valor pendente", "valor ja recebido", "comprador responsavel", "dias em aberto".

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

---

## 23. Pendencia de compra detalhada por ITEM (query referencia)

**Pergunta:** Quais itens estao pendentes de entrega? / Detalhe dos itens pendentes / Produtos pendentes de compra / Itens pendentes por marca / Relatorio detalhado de pendencia

**IMPORTANTE:** Esta eh a query REFERENCIA para qualquer pergunta sobre itens/produtos pendentes de compra. Retorna CADA ITEM individualmente (sem GROUP BY). Usar quando o usuario quer ver DETALHES por item, produto, marca, fornecedor.

```sql
SELECT
    ITE.CODEMP AS COD_EMPRESA,
    EMP.NOMEFANTASIA AS NOME_EMPRESA,
    CAB.NUNOTA AS PEDIDO,
    CAB.CODTIPOPER,
    CASE
        WHEN CAB.CODTIPOPER = 1313 THEN 'Casada'
        WHEN CAB.CODTIPOPER = 1301 THEN 'Estoque'
    END AS TIPO_COMPRA,
    TO_CHAR(CAB.DTNEG, 'DD/MM/YYYY') AS DT_PEDIDO,
    NVL(TO_CHAR(CAB.DTPREVENT, 'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO_ENTREGA,
    CASE
        WHEN CAB.STATUSNOTA = 'L' THEN 'Sim'
        ELSE 'Nao'
    END AS CONFIRMADO,
    PAR.CODPARC,
    PAR.NOMEPARC AS FORNECEDOR,
    MAR.AD_CODVEND AS COD_COMPRADOR,
    VEN.APELIDO AS COMPRADOR,
    PRO.CODPROD,
    PRO.DESCRPROD AS PRODUTO,
    MAR.CODIGO AS COD_MARCA,
    MAR.DESCRICAO AS MARCA,
    PRO.AD_NUMFABRICANTE AS NUM_FABRICANTE,
    PRO.AD_NUMORIGINAL AS NUM_ORIGINAL,
    ITE.CODVOL AS UNIDADE,
    ITE.QTDNEG AS QTD_PEDIDA,
    NVL(V_AGG.TOTAL_ATENDIDO, 0) AS QTD_ATENDIDA,
    (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) AS QTD_PENDENTE,
    ITE.VLRUNIT AS VLR_UNITARIO,
    ITE.VLRTOT AS VLR_PEDIDO_ITEM,
    ROUND(NVL(V_AGG.TOTAL_ATENDIDO, 0) * ITE.VLRUNIT, 2) AS VLR_ATENDIDO,
    ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2) AS VLR_PENDENTE,
    TRUNC(SYSDATE) - TRUNC(CAB.DTNEG) AS DIAS_ABERTO,
    CASE
        WHEN CAB.DTPREVENT IS NULL THEN 'SEM PREVISAO'
        WHEN CAB.DTPREVENT < SYSDATE THEN 'ATRASADO'
        WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 'PROXIMO'
        ELSE 'NO PRAZO'
    END AS STATUS_ENTREGA
FROM TGFITE ITE
JOIN TGFCAB CAB ON CAB.NUNOTA = ITE.NUNOTA
JOIN TSIEMP EMP ON EMP.CODEMP = ITE.CODEMP
JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
LEFT JOIN TGFPAR PAR ON PAR.CODPARC = CAB.CODPARC
LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
LEFT JOIN TGFVEN VEN ON VEN.CODVEND = MAR.AD_CODVEND
LEFT JOIN (
    SELECT V.NUNOTAORIG, V.SEQUENCIAORIG,
           SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
    FROM TGFVAR V
    JOIN TGFCAB C ON C.NUNOTA = V.NUNOTA
    WHERE C.STATUSNOTA <> 'C'
    GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
) V_AGG ON V_AGG.NUNOTAORIG = ITE.NUNOTA
       AND V_AGG.SEQUENCIAORIG = ITE.SEQUENCIA
WHERE CAB.CODTIPOPER IN (1301, 1313)
  AND CAB.STATUSNOTA <> 'C'
  AND CAB.PENDENTE = 'S'
  AND ITE.PENDENTE = 'S'
  AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0
ORDER BY
    CASE
        WHEN CAB.DTPREVENT IS NULL THEN 1
        WHEN CAB.DTPREVENT < SYSDATE THEN 0
        WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 2
        ELSE 3
    END,
    MAR.DESCRICAO,
    PRO.DESCRPROD
```

**Filtros opcionais (adicionar no WHERE conforme necessidade):**
- Filtrar por marca: `AND UPPER(MAR.DESCRICAO) = UPPER('DONALDSON')`
- Filtrar por pedido: `AND CAB.NUNOTA = 1168013`
- Limitar resultados: envolver em `SELECT * FROM (...) WHERE ROWNUM <= 100`

**Explicacao detalhada:**
1. **Nivel ITEM** (sem GROUP BY): Mostra cada item individualmente, nao agrega por pedido.
2. **TIPO_COMPRA**: CODTIPOPER 1301='Estoque' (compra normal), 1313='Casada' (vinculada a venda/empenho).
3. **CONFIRMADO**: STATUSNOTA='L' (Liberado) = pedido confirmado. Regra de negocio MMarra: pedido so eh considerado confirmado quando status muda para Liberado, nao pelo campo APROVADO.
4. **NUM_FABRICANTE / NUM_ORIGINAL**: Campos customizados MMarra (AD_NUMFABRICANTE, AD_NUMORIGINAL) para referencia cruzada de pecas.
5. **ITE.CODEMP + TSIEMP**: Empresa do item (pode diferir do cabecalho em operacoes multi-empresa).
6. **Comprador via TGFMAR**: AD_CODVEND da marca indica o comprador responsavel por aquela marca.
7. **TGFVAR agregado**: Pendencia real = QTDNEG - SUM(QTDATENDIDA).
8. **ITE.PENDENTE='S'**: CRITICO - exclui itens cancelados/cortados pelo usuario.
9. **ORDER BY prioridade**: Atrasados (0) > Sem previsao (1) > Proximo (2) > No prazo (3).
10. **Colunas de valor (IMPORTANTE para a LLM escolher a coluna certa):**
    - `VLR_UNITARIO` = preco unitario do item (ITE.VLRUNIT)
    - `VLR_PEDIDO_ITEM` = valor TOTAL pedido daquele item (QTD_PEDIDA * VLRUNIT = ITE.VLRTOT)
    - `VLR_ATENDIDO` = valor ja ENTREGUE/RECEBIDO em R$ (QTD_ATENDIDA * VLRUNIT)
    - `VLR_PENDENTE` = valor que FALTA entregar em R$ (QTD_PENDENTE * VLRUNIT)
    - Regra: VLR_PEDIDO_ITEM = VLR_ATENDIDO + VLR_PENDENTE (sempre)
    - "quanto ja chegou em R$" / "valor recebido" → usar VLR_ATENDIDO
    - "quanto falta em R$" / "valor pendente" → usar VLR_PENDENTE
    - "valor do pedido" / "valor total" → usar VLR_PEDIDO_ITEM

**Quando usar este exemplo:**
- Usuario pergunta sobre ITENS pendentes, PRODUTOS pendentes, DETALHES de pendencia
- Usuario quer ver cada item individualmente (nao agregado)
- Usuario menciona "relatorio detalhado", "item por item", "detalhe"
- Usuario pergunta "quanto ja chegou em R$", "valor entregue", "valor pendente por item"

**Quando usar exemplo 22 (agregado):**
- Usuario quer TOTAIS por pedido (quantos itens, valor total)
- Usuario pergunta "quantos pedidos" (nao "quantos itens")
- Usuario quer SUM de valores por pedido/marca (VLR_TOTAL_PEDIDO, VLR_TOTAL_ATENDIDO, VLR_TOTAL_PENDENTE)

---

## REGRA CRITICA: ITE.PENDENTE para itens cancelados/cortados

Quando trabalhar com **pendencia de itens** (TGFITE), SEMPRE adicionar:

```sql
WHERE ITE.PENDENTE = 'S'
```

**Por que?**
- Quando usuario cancela/corta um item do pedido (ligou pro fornecedor e cancelou), o campo `ITE.PENDENTE` fica = 'N'
- Se nao filtrar por `ITE.PENDENTE = 'S'`, itens cancelados aparecem eternamente na consulta (nunca serao entregues, entao QTDNEG - TOTAL_ATENDIDO sempre > 0)
- CAB.PENDENTE indica pedido pendente (cabecalho)
- ITE.PENDENTE indica item pendente (granular, item a item)

**Usar em:**
- Consultas de pendencia de compra por marca/produto (exemplos 19, 20, 22)
- Qualquer query que mostre itens aguardando entrega

**NAO usar quando:**
- Quer ver historico completo incluindo itens cancelados
- Query eh nivel CABECALHO (sem filtro de marca/produto)

---

## 24. Consulta de pendencias de compras por item detalhada

**Pergunta:** Pendencias de compra detalhada / Itens pendentes de compra com marca e produto / O que falta chegar por item? / Pendencias de compra com previsao de entrega / Quais itens estao atrasados na compra?

```sql
-- Consulta de pendencias de compras por item detalhada
SELECT
    ITE.CODEMP AS COD_EMPRESA,
    EMP.NOMEFANTASIA AS NOME_EMPRESA,
    CAB.NUNOTA AS PEDIDO,
    CAB.CODTIPOPER,
    CASE
       WHEN CAB.CODTIPOPER = 1313 THEN 'Casada'
       WHEN CAB.CODTIPOPER = 1301 THEN 'Estoque'
    END AS TIPO_COMPRA,
    CAB.DTNEG AS DT_PEDIDO,
    CAB.DTPREVENT AS PREVISAO_ENTREGA,
    CASE
       WHEN CAB.STATUSNOTA = 'L' THEN 'Sim'
       ELSE 'Não'
    END AS CONFIRMADO,
    PAR.CODPARC,
    PAR.NOMEPARC AS FORNECEDOR,
    MAR.AD_CODVEND AS COD_COMPRADOR,
    VEN.APELIDO AS COMPRADOR,
    PRO.CODPROD,
    PRO.DESCRPROD AS PRODUTO,
    MAR.CODIGO AS COD_MARCA,
    MAR.DESCRICAO AS MARCA,
    PRO.AD_NUMFABRICANTE AS NUM_FABRICANTE,
    PRO.AD_NUMORIGINAL AS NUM_ORIGINAL,
    ITE.CODVOL AS UNIDADE,
    ITE.QTDNEG AS QTD_PEDIDA,
    NVL(V_AGG.TOTAL_ATENDIDO, 0) AS QTD_ATENDIDA,
    (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) AS QTD_PENDENTE,
    ITE.VLRUNIT AS VLR_UNITARIO,
    ITE.VLRTOT AS VLR_TOTAL_PEDIDO,
    ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2) AS VLR_TOTAL_PENDENTE,
    TRUNC(SYSDATE) - TRUNC(CAB.DTNEG) AS DIAS_ABERTO,
    CASE
        WHEN CAB.DTPREVENT IS NULL THEN 'SEM PREVISÃO'
        WHEN CAB.DTPREVENT < SYSDATE THEN 'ATRASADO'
        WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 'PRÓXIMO'
        ELSE 'NO PRAZO'
    END AS STATUS_ENTREGA
FROM TGFITE ITE
JOIN TGFCAB CAB ON CAB.NUNOTA = ITE.NUNOTA
JOIN TSIEMP EMP ON EMP.CODEMP = ITE.CODEMP
JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
LEFT JOIN TGFPAR PAR ON PAR.CODPARC = CAB.CODPARC
LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
LEFT JOIN TGFVEN VEN ON VEN.CODVEND = MAR.AD_CODVEND
LEFT JOIN (
    SELECT V.NUNOTAORIG, V.SEQUENCIAORIG,
           SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
    FROM TGFVAR V
    JOIN TGFCAB C ON C.NUNOTA = V.NUNOTA
    WHERE C.STATUSNOTA <> 'C'
    GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
) V_AGG ON V_AGG.NUNOTAORIG = ITE.NUNOTA
       AND V_AGG.SEQUENCIAORIG = ITE.SEQUENCIA
WHERE CAB.CODTIPOPER IN (1301, 1313)
  AND CAB.STATUSNOTA <> 'C'
  AND CAB.PENDENTE = 'S'
  AND ITE.PENDENTE = 'S'
  --AND UPPER(MAR.DESCRICAO) = UPPER('TOME')
  AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0
  --AND CAB.NUNOTA = 1168013
ORDER BY
    CASE
        WHEN CAB.DTPREVENT IS NULL THEN 1
        WHEN CAB.DTPREVENT < SYSDATE THEN 0
        WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 2
        ELSE 3
    END,
    MAR.DESCRICAO,
    PRO.DESCRPROD
```

**Explicacao:** (1) Query no nivel mais granular: cada LINHA = 1 item pendente de 1 pedido. (2) Usa TGFVAR para calcular entregas parciais (QTD_ATENDIDA vs QTD_PENDENTE). (3) Filtro `ITE.PENDENTE = 'S'` exclui itens cancelados/cortados. (4) Filtro `(QTDNEG - TOTAL_ATENDIDO) > 0` garante que so aparecem itens com saldo pendente real. (5) STATUS_ENTREGA classifica em ATRASADO, PROXIMO (7 dias), NO PRAZO ou SEM PREVISAO. (6) Ordenacao prioriza atrasados primeiro, depois proximos, sem previsao, e por ultimo no prazo. (7) COMPRADOR vem de MAR.AD_CODVEND (comprador da marca), nao do cabecalho.

**Filtros opcionais (comentados na query):**
- Por marca: `AND UPPER(MAR.DESCRICAO) = UPPER('TOME')`
- Por pedido especifico: `AND CAB.NUNOTA = 1168013`
- Por fornecedor: `AND UPPER(PAR.NOMEPARC) LIKE UPPER('%NOME%')`
- Por comprador: `AND VEN.CODVEND = 123`

**Tabelas envolvidas:**
- TGFITE - Itens do pedido (base da query)
- TGFCAB - Cabecalho (pedido, datas, status)
- TSIEMP - Empresa
- TGFPRO - Produto (descricao, numeros fabricante/original)
- TGFPAR - Parceiro/Fornecedor
- TGFMAR - Marca (codigo, descricao, comprador AD_CODVEND)
- TGFVEN - Vendedor/Comprador (apelido)
- TGFVAR - Variacao/Entregas parciais (QTDATENDIDA)

**Quando usar este exemplo:**
- Usuario quer ver pendencias de compra no nivel mais detalhado (item a item)
- Usuario pergunta sobre itens atrasados ou proximos de vencer
- Usuario quer filtrar pendencias por marca, fornecedor ou comprador
- Diferenca do Exemplo 23: este eh a versao mais completa com empresa, tipo de compra, confirmacao, numeros de fabricante/original e STATUS_ENTREGA

---

## 25. Performance de fornecedor (ranking de atrasos)

**Pergunta:** Qual fornecedor atrasa mais? / Performance dos fornecedores / Ranking de atrasos / % de atraso por fornecedor / Fornecedores mais pontuais / Confiabilidade dos fornecedores

**IMPORTANTE:** Esta query analisa pedidos de compra e calcula metricas de pontualidade por fornecedor. Baseada em DTPREVENT (previsao) vs data atual para pedidos pendentes.

```sql
SELECT * FROM (
    SELECT
        PAR.CODPARC,
        PAR.NOMEPARC AS FORNECEDOR,
        COUNT(*) AS TOTAL_PEDIDOS,
        SUM(CASE WHEN CAB.PENDENTE = 'N' THEN 1 ELSE 0 END) AS ENTREGUES,
        SUM(CASE WHEN CAB.PENDENTE = 'S' THEN 1 ELSE 0 END) AS PENDENTES,
        SUM(CASE WHEN CAB.PENDENTE = 'S' AND CAB.DTPREVENT IS NOT NULL
                  AND CAB.DTPREVENT < TRUNC(SYSDATE) THEN 1 ELSE 0 END) AS ATRASADOS,
        SUM(CASE WHEN CAB.PENDENTE = 'S' AND CAB.DTPREVENT IS NULL
                  THEN 1 ELSE 0 END) AS SEM_PREVISAO,
        ROUND(
            SUM(CASE WHEN CAB.PENDENTE = 'S' AND CAB.DTPREVENT IS NOT NULL
                      AND CAB.DTPREVENT < TRUNC(SYSDATE) THEN 1 ELSE 0 END) * 100.0
            / NULLIF(SUM(CASE WHEN CAB.PENDENTE = 'S' THEN 1 ELSE 0 END), 0)
        , 1) AS PERC_ATRASO,
        ROUND(AVG(
            CASE WHEN CAB.PENDENTE = 'S'
                 THEN TRUNC(SYSDATE) - TRUNC(CAB.DTNEG)
            END
        ), 0) AS MEDIA_DIAS_PENDENTE
    FROM TGFCAB CAB
    JOIN TGFPAR PAR ON PAR.CODPARC = CAB.CODPARC
    WHERE CAB.CODTIPOPER IN (1301, 1313)
      AND CAB.STATUSNOTA <> 'C'
      AND CAB.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE), -12)
    GROUP BY PAR.CODPARC, PAR.NOMEPARC
    ORDER BY ATRASADOS DESC, PERC_ATRASO DESC NULLS LAST
) WHERE ROWNUM <= 20
```

**Explicacao:** (1) Nivel CABECALHO agregado por fornecedor. (2) ATRASADOS = pedidos pendentes com DTPREVENT ja passada. (3) PERC_ATRASO = % dos pedidos pendentes que estao atrasados (quanto maior, menos confiavel). (4) NULLIF evita divisao por zero. (5) MEDIA_DIAS_PENDENTE = media de dias que pedidos pendentes estao abertos. (6) Ultimos 12 meses como padrao. (7) CODTIPOPER IN (1301, 1313) para compras MMarra.

**Filtros opcionais:**
- Fornecedor especifico: `AND UPPER(PAR.NOMEPARC) LIKE UPPER('%NOME%')`
- Apenas com pedidos pendentes: adicionar `HAVING SUM(CASE WHEN CAB.PENDENTE = 'S' THEN 1 ELSE 0 END) > 0`
- Top fornecedores mais pontuais: trocar ORDER BY para `PERC_ATRASO ASC NULLS LAST`

**Explicacao detalhada:**
1. **PERC_ATRASO**: Porcentagem dos pedidos PENDENTES que ja passaram da previsao (DTPREVENT < SYSDATE). Quanto maior, menos confiavel o fornecedor.
2. **MEDIA_DIAS_PENDENTE**: Media de dias que pedidos pendentes estao em aberto. Calcula apenas para pendentes.
3. **SEM_PREVISAO**: Pedidos pendentes sem data de previsao. Indica falta de follow-up do comprador.
4. **NULLIF**: Quando fornecedor nao tem pedidos pendentes, PERC_ATRASO = NULL (evita divisao por zero).
5. **Periodo 12 meses**: Historico suficiente para avaliar performance.

**Quando usar este exemplo:**
- Usuario pergunta sobre performance, pontualidade ou confiabilidade de fornecedores
- Usuario quer ranking dos piores ou melhores fornecedores
- Usuario pergunta "qual fornecedor atrasa mais"
- Para analise de fornecedor especifico, adicionar filtro de nome
