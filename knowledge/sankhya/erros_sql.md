# Erros SQL Conhecidos

> Erros que a LLM ja cometeu ao gerar SQL. Consultar para EVITAR repeti-los.

---

## 1. JOIN direto TGFCAB com TGFPRO

**Query errada:**
```sql
SELECT PR.DESCRPROD FROM TGFCAB C JOIN TGFPRO PR ON C.CODPROD = PR.CODPROD
```

**Motivo:** TGFCAB NAO tem campo CODPROD. O campo CODPROD esta em TGFITE.

**Query correta:**
```sql
SELECT PR.DESCRPROD FROM TGFCAB C JOIN TGFITE I ON C.NUNOTA = I.NUNOTA JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
```

**Regra:** SEMPRE passar por TGFITE para acessar TGFPRO a partir de TGFCAB.

---

## 2. Usar LIMIT em vez de ROWNUM

**Query errada:**
```sql
SELECT * FROM TGFCAB WHERE TIPMOV = 'V' ORDER BY VLRNOTA DESC LIMIT 10
```

**Motivo:** Oracle NAO suporta LIMIT. Isso e sintaxe MySQL/PostgreSQL.

**Query correta:**
```sql
SELECT * FROM (SELECT * FROM TGFCAB WHERE TIPMOV = 'V' ORDER BY VLRNOTA DESC) WHERE ROWNUM <= 10
```

**Regra:** Usar subquery + ROWNUM para limitar resultados em Oracle.

---

## 3. Usar FETCH FIRST em vez de ROWNUM

**Query errada:**
```sql
SELECT * FROM TGFCAB ORDER BY VLRNOTA DESC FETCH FIRST 10 ROWS ONLY
```

**Motivo:** Versao do Oracle pode nao suportar FETCH FIRST (Oracle 12c+). Usar ROWNUM que funciona em todas as versoes.

**Query correta:**
```sql
SELECT * FROM (SELECT * FROM TGFCAB ORDER BY VLRNOTA DESC) WHERE ROWNUM <= 10
```

---

## 4. Alias de coluna sem qualificador de tabela

**Query errada:**
```sql
SELECT NOMEPARC, VLRNOTA FROM TGFCAB C JOIN TGFPAR P ON C.CODPARC = P.CODPARC
```

**Motivo:** Colunas ambiguas ou sem qualificador podem dar erro ORA-00918.

**Query correta:**
```sql
SELECT P.NOMEPARC, C.VLRNOTA FROM TGFCAB C JOIN TGFPAR P ON C.CODPARC = P.CODPARC
```

**Regra:** SEMPRE qualificar colunas com alias da tabela (C., P., PR., etc).

---

## 5. GROUP BY incompleto

**Query errada:**
```sql
SELECT P.NOMEPARC, SUM(C.VLRNOTA) FROM TGFCAB C JOIN TGFPAR P ON C.CODPARC = P.CODPARC GROUP BY P.CODPARC
```

**Motivo:** NOMEPARC esta no SELECT mas NAO no GROUP BY. Oracle exige todas as colunas nao-agregadas no GROUP BY.

**Query correta:**
```sql
SELECT P.NOMEPARC, SUM(C.VLRNOTA) FROM TGFCAB C JOIN TGFPAR P ON C.CODPARC = P.CODPARC GROUP BY P.CODPARC, P.NOMEPARC
```

---

## 6. Ponto-e-virgula no final

**Query errada:**
```sql
SELECT COUNT(*) FROM TGFCAB WHERE TIPMOV = 'V';
```

**Motivo:** O executor de queries bloqueia multiplas statements (;).

**Query correta:**
```sql
SELECT COUNT(*) FROM TGFCAB WHERE TIPMOV = 'V'
```

**Regra:** NUNCA colocar ponto-e-virgula no final da query.

---

## 7. MARCA em tabela errada

**Query errada:**
```sql
SELECT C.MARCA FROM TGFCAB C
```

**Motivo:** MARCA esta em TGFPRO, nao em TGFCAB nem TGFITE.

**Query correta:**
```sql
SELECT PR.MARCA FROM TGFCAB C JOIN TGFITE I ON C.NUNOTA = I.NUNOTA JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
```

---

## 8. NOMEPARC em tabela errada

**Query errada:**
```sql
SELECT C.NOMEPARC FROM TGFCAB C
```

**Motivo:** NOMEPARC esta em TGFPAR, nao em TGFCAB.

**Query correta:**
```sql
SELECT P.NOMEPARC FROM TGFCAB C JOIN TGFPAR P ON C.CODPARC = P.CODPARC
```

---

## 9. APELIDO em tabela errada

**Query errada:**
```sql
SELECT C.APELIDO FROM TGFCAB C
```

**Motivo:** APELIDO (nome do vendedor) esta em TGFVEN, nao em TGFCAB.

**Query correta:**
```sql
SELECT V.APELIDO FROM TGFCAB C JOIN TGFVEN V ON C.CODVEND = V.CODVEND
```

---

## 10. Subquery com alias de escopo errado

**Query errada:**
```sql
SELECT E.NOMEFANTASIA, COUNT(*)
FROM (SELECT C.CODEMP FROM TGFCAB C) sub
JOIN TSIEMP E ON sub.CODEMP = E.CODEMP
GROUP BY E.NOMEFANTASIA
```

**Motivo:** Subquery desnecessaria cria complexidade e pode perder alias.

**Query correta:**
```sql
SELECT E.NOMEFANTASIA, COUNT(*)
FROM TGFCAB C
JOIN TSIEMP E ON C.CODEMP = E.CODEMP
GROUP BY E.NOMEFANTASIA
```

**Regra:** Preferir JOINs diretos em vez de subqueries quando possivel.

---

## 11. Multiplicacao de valores em JOIN TGFFIN + TGFITE

**Query errada:**
```sql
SELECT PR.MARCA, SUM(F.VLRDESDOB)
FROM TGFCAB C
JOIN TGFFIN F ON C.NUNOTA = F.NUNOTA
JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
GROUP BY PR.MARCA
```

**Motivo:** JOIN entre TGFFIN e TGFITE pela NUNOTA multiplica registros. Se a nota tem 3 parcelas e 5 itens, gera 15 linhas e o SUM fica 5x maior.

**Regra:** NUNCA fazer JOIN de TGFFIN com TGFITE na mesma query. Escolher um:
- Quer VALORES FINANCEIROS -> usar TGFFIN, SEM TGFITE
- Quer DADOS DE PRODUTO (marca, descricao) -> usar TGFITE, SEM TGFFIN
- Precisa dos dois -> usar SUBQUERIES separadas

**Query correta (valor financeiro por marca com subquery):**
```sql
SELECT MARCA, SUM(TOTAL_PENDENTE) AS TOTAL_PENDENTE
FROM (
    SELECT DISTINCT C.NUNOTA, PR.MARCA,
        (SELECT SUM(F2.VLRDESDOB) FROM TGFFIN F2 WHERE F2.NUNOTA = C.NUNOTA AND F2.RECDESP = -1 AND F2.DHBAIXA IS NULL) AS TOTAL_PENDENTE
    FROM TGFCAB C
    JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
    JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
    WHERE C.TIPMOV = 'C'
) SUB
WHERE TOTAL_PENDENTE > 0
GROUP BY MARCA
ORDER BY TOTAL_PENDENTE DESC
```

**Alternativa simples (pendencia por marca usando valor da nota):**
```sql
SELECT PR.MARCA, COUNT(DISTINCT C.NUNOTA) AS QTD_NOTAS, SUM(DISTINCT C.VLRNOTA) AS TOTAL
FROM TGFCAB C
JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
WHERE C.PENDENTE = 'S' AND C.STATUSNOTA <> 'C'
GROUP BY PR.MARCA
ORDER BY TOTAL DESC
```

---

## 12. Filtrar pendencia financeira por DTNEG em vez de DTVENC

**Query errada:**
```sql
SELECT * FROM TGFFIN F WHERE F.DTNEG >= TRUNC(SYSDATE, 'MM')
```

**Motivo:** Um titulo pode ser de nota do mes passado e ainda estar pendente. DTNEG filtra pela data da nota, nao pela data de vencimento.

**Query correta para pendencias:**
```sql
WHERE F.DHBAIXA IS NULL
```

**Query correta para vencidos:**
```sql
WHERE F.DTVENC < TRUNC(SYSDATE) AND F.DHBAIXA IS NULL
```

**Query correta para vencendo este mes:**
```sql
WHERE F.DTVENC BETWEEN TRUNC(SYSDATE, 'MM') AND LAST_DAY(SYSDATE) AND F.DHBAIXA IS NULL
```

---

## 13. FETCH FIRST sem mostrar ranking completo

**Query errada:**
```sql
SELECT PR.MARCA, SUM(C.VLRNOTA) FROM ... FETCH FIRST 1 ROW ONLY
```

**Motivo:** O usuario quer ver o ranking, nao so o primeiro. Sempre mostrar top 10 para dar contexto.

**Query correta:**
```sql
SELECT * FROM (...) WHERE ROWNUM <= 10
```

---

## 14. WHERE ROWNUM apos ORDER BY (fora de subquery)

**Query errada:**
```sql
SELECT PR.CODPROD, PR.DESCRPROD, SUM(I.QTDNEG) AS QTD
FROM TGFCAB C JOIN TGFITE I ON C.NUNOTA = I.NUNOTA JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
GROUP BY PR.CODPROD, PR.DESCRPROD
ORDER BY QTD DESC
WHERE ROWNUM <= 10
```

**Motivo:** WHERE ROWNUM nao pode vir apos ORDER BY. Oracle processa WHERE antes de ORDER BY, entao ROWNUM limita ANTES de ordenar.

**Query correta:**
```sql
SELECT * FROM (
  SELECT PR.CODPROD, PR.DESCRPROD, SUM(I.QTDNEG) AS QTD
  FROM TGFCAB C JOIN TGFITE I ON C.NUNOTA = I.NUNOTA JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
  GROUP BY PR.CODPROD, PR.DESCRPROD
  ORDER BY QTD DESC
) WHERE ROWNUM <= 10
```

**Regra:** SEMPRE envolver em subquery quando usar ORDER BY com ROWNUM.

---

## 15. Filtrar marca usando TGFPRO.MARCA em vez de TGFMAR

**Query errada:**
```sql
SELECT PR.MARCA, COUNT(*) FROM TGFCAB C
JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
WHERE PR.MARCA = 'DONALDSON'
GROUP BY PR.MARCA
```

**Motivo:** TGFPRO.MARCA eh um campo texto livre, pode ter inconsistencias (maiuscula/minuscula, acentos, espacos). TGFMAR.DESCRICAO eh o cadastro oficial de marcas.

**Query correta:**
```sql
SELECT M.DESCRICAO AS MARCA, COUNT(*) FROM TGFCAB C
JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
JOIN TGFMAR M ON PR.CODMARCA = M.CODIGO
WHERE M.DESCRICAO = 'DONALDSON'
GROUP BY M.DESCRICAO
```

**Regra:** SEMPRE usar TGFMAR.DESCRICAO para filtrar por marca. JOIN via TGFPRO.CODMARCA = TGFMAR.CODIGO.

---

## 16. Multiplicacao de linhas ao filtrar marca no nivel CABECALHO

**Query errada:**
```sql
SELECT C.NUNOTA, C.VLRNOTA, C.DTPREVENT
FROM TGFCAB C
JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
JOIN TGFMAR M ON PR.CODMARCA = M.CODIGO
WHERE M.DESCRICAO = 'DONALDSON' AND C.TIPMOV = 'O'
```

**Motivo:** Se o pedido tem 10 itens da marca Donaldson, a query retorna 10 linhas IDENTICAS para o mesmo pedido. VLRNOTA aparece 10 vezes e SUM fica inflado 10x.

**Query correta (usar EXISTS):**
```sql
SELECT C.NUNOTA, C.VLRNOTA, C.DTPREVENT
FROM TGFCAB C
WHERE C.TIPMOV = 'O'
  AND EXISTS (
    SELECT 1 FROM TGFITE I
    JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
    JOIN TGFMAR M ON PR.CODMARCA = M.CODIGO
    WHERE I.NUNOTA = C.NUNOTA AND M.DESCRICAO = 'DONALDSON'
  )
```

**Regra:** Para dados de CABECALHO com filtro de marca, usar EXISTS. So usar JOIN direto quando precisar dos ITENS no resultado.

---

## 17. Ignorar DTPREVENT (previsao de entrega)

**Query errada:**
```sql
SELECT C.NUNOTA, C.VLRNOTA FROM TGFCAB C WHERE C.TIPMOV = 'O' AND C.PENDENTE = 'S'
```

**Motivo:** Quando o usuario pede "previsao de entrega", o campo DTPREVENT eh essencial. Sem ele, a query nao responde a pergunta.

**Query correta:**
```sql
SELECT C.NUNOTA, C.VLRNOTA, C.DTPREVENT,
  TO_CHAR(C.DTPREVENT, 'MM/YYYY') AS MES_PREVISAO
FROM TGFCAB C
WHERE C.TIPMOV = 'O' AND C.PENDENTE = 'S' AND C.DTPREVENT IS NOT NULL
```

**Regra:** Sempre incluir DTPREVENT quando a pergunta mencionar "previsao", "entrega", "quando chega". Tratar NULL com IS NOT NULL ou NVL. Usar TO_CHAR para formato legivel.

---

## 18. Case sensitivity em filtros de texto

**Query errada:**
```sql
SELECT M.DESCRICAO, COUNT(*) FROM TGFCAB C
JOIN TGFITE I ON C.NUNOTA = I.NUNOTA
JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD
JOIN TGFMAR M ON PR.CODMARCA = M.CODIGO
WHERE M.DESCRICAO = 'Donaldson'
GROUP BY M.DESCRICAO
```

**Motivo:** Na TGFMAR e outras tabelas cadastrais, nomes estao em MAIUSCULO (ex: 'DONALDSON'). O modelo escreve com caixa mista ('Donaldson'), retornando 0 registros.

**Query correta:**
```sql
WHERE UPPER(M.DESCRICAO) = UPPER('Donaldson')
```

**Regra:** SEMPRE usar UPPER() em AMBOS os lados ao comparar campos de texto (marca, fornecedor, produto, parceiro). Isso garante match independente de como o texto foi cadastrado.

---

## 19. Filtrar DTPREVENT IS NOT NULL quando usuario pede "previsao de entrega"

**Query errada:**
```sql
SELECT C.NUNOTA, C.DTPREVENT FROM TGFCAB C
WHERE C.TIPMOV IN ('C','O') AND C.DTPREVENT IS NOT NULL
```

**Motivo:** O usuario pediu "relatorio de previsao de entrega" — quer VER a previsao (inclusive quando nao tem). O filtro IS NOT NULL exclui pedidos sem previsao, que sao dados relevantes.

**Query correta:**
```sql
SELECT C.NUNOTA,
  NVL(TO_CHAR(C.DTPREVENT, 'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO_ENTREGA
FROM TGFCAB C
WHERE C.TIPMOV IN ('C','O')
```

**Regra:** "previsao de entrega" = MOSTRAR a coluna DTPREVENT (com NVL para tratar NULL). So filtrar IS NULL ou IS NOT NULL quando o usuario pedir EXPLICITAMENTE ("pedidos SEM previsao" ou "pedidos COM previsao").

---

## 20. Usar STATUSNOTA = 'P' para filtrar pedidos pendentes

**Query errada:**
```sql
SELECT C.NUNOTA, C.DTPREVENT FROM TGFCAB C
WHERE C.TIPMOV = 'O' AND C.STATUSNOTA = 'P'
```

**Motivo:** STATUSNOTA indica o estado da NOTA (P=Pendente, L=Liberado, A=Atendimento, C=Cancelado). NAO indica se o pedido tem itens pendentes de entrega. O campo correto eh TGFCAB.PENDENTE (S/N), que o Sankhya atualiza automaticamente via TGFVAR.

**Query correta:**
```sql
WHERE C.TIPMOV = 'O' AND C.PENDENTE = 'S' AND C.STATUSNOTA <> 'C'
```

**Regra:** "Pedidos pendentes" = `PENDENTE = 'S'`. NUNCA usar STATUSNOTA = 'P' para filtrar pendencia. Usar STATUSNOTA <> 'C' apenas para excluir cancelados.

---

## 21. Confusao entre TIPMOV 'C' e 'O' para compras

**Query errada:**
```sql
SELECT C.NUNOTA FROM TGFCAB C WHERE C.TIPMOV = 'C' AND C.PENDENTE = 'S'
```

**Motivo:** TIPMOV='C' eh nota de compra (entrada ja efetivada/recebida). TIPMOV='O' eh pedido de compra (ordem que pode estar pendente). Quando o usuario pede "pedidos de compra", quer TIPMOV='O'.

**Regras:**
- "Pedidos de compra" / "pedidos pendentes" → `TIPMOV = 'O'`
- "Notas de compra" / "entradas" → `TIPMOV = 'C'`
- "Tudo de compra" (pedidos + notas) → `TIPMOV IN ('C','O')`
- Na maioria dos casos quando fala "pedidos de compra", usar TIPMOV = 'O'

---

## 22. Usar nivel CABECALHO (EXISTS + VLRNOTA) quando filtrando por MARCA

**Query errada:**
```sql
SELECT C.NUNOTA, C.VLRNOTA, C.DTPREVENT
FROM TGFCAB C
WHERE C.TIPMOV = 'O' AND C.PENDENTE = 'S' AND C.STATUSNOTA <> 'C'
  AND EXISTS (SELECT 1 FROM TGFITE I JOIN TGFPRO PR ON I.CODPROD=PR.CODPROD
              JOIN TGFMAR M ON PR.CODMARCA=M.CODIGO
              WHERE I.NUNOTA=C.NUNOTA AND UPPER(M.DESCRICAO)=UPPER('DONALDSON'))
```

**Motivo:** VLRNOTA = valor TOTAL do pedido (todas as marcas). Se o pedido tem itens de 5 marcas diferentes, VLRNOTA inclui todas. Exemplo real: pedido com VLRNOTA = R$ 13M mas apenas R$ 1.874 em itens Donaldson.

**Query correta (nivel ITEM):**
```sql
SELECT CAB.NUNOTA, MAR.DESCRICAO AS MARCA, PRO.DESCRPROD,
  ITE.QTDNEG AS QTD_PEDIDA,
  NVL(V_AGG.TOTAL_ATENDIDO, 0) AS QTD_ATENDIDA,
  (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) AS QTD_PENDENTE,
  ITE.VLRTOT AS VLR_TOTAL_ITEM,
  NVL(TO_CHAR(CAB.DTPREVENT, 'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO
FROM TGFITE ITE
JOIN TGFCAB CAB ON CAB.NUNOTA = ITE.NUNOTA
JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
LEFT JOIN (
  SELECT V.NUNOTAORIG, V.SEQUENCIAORIG, SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
  FROM TGFVAR V JOIN TGFCAB CV ON CV.NUNOTA = V.NUNOTA WHERE CV.STATUSNOTA <> 'C'
  GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
) V_AGG ON V_AGG.NUNOTAORIG = ITE.NUNOTA AND V_AGG.SEQUENCIAORIG = ITE.SEQUENCIA
WHERE CAB.TIPMOV = 'O' AND CAB.PENDENTE = 'S' AND CAB.STATUSNOTA <> 'C'
  AND UPPER(MAR.DESCRICAO) = UPPER('DONALDSON')
  AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0
```

**Regra (CRITICA):** Se a pergunta menciona MARCA ou PRODUTO, a query DEVE ser no nivel de ITEM (FROM TGFITE). NUNCA usar VLRNOTA quando filtrando por marca — usar ITE.VLRTOT ou SUM(ITE.VLRTOT). Pendencia real = TGFVAR (QTD_PEDIDA - QTD_ATENDIDA > 0).

---

## 23. NVL com tipo errado em DTPREVENT (DATE vs VARCHAR)

**Query errada:**
```sql
SELECT NVL(CAB.DTPREVENT, 'Sem Previsao') AS PREVISAO
FROM TGFCAB CAB
```

**Motivo:** DTPREVENT eh campo DATE. NVL(DATE, VARCHAR) causa erro ORA de tipo incompativel. Oracle exige que ambos os argumentos do NVL sejam do mesmo tipo.

**Query correta:**
```sql
SELECT NVL(TO_CHAR(CAB.DTPREVENT, 'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO
FROM TGFCAB CAB
```

**Regra:** SEMPRE converter DATE para CHAR antes de usar NVL com texto: NVL(TO_CHAR(campo_date, 'DD/MM/YYYY'), 'texto').

---

## Resumo de Regras para Evitar Erros

1. NUNCA juntar TGFCAB com TGFPRO direto (passar por TGFITE)
2. NUNCA usar LIMIT (usar ROWNUM com subquery)
3. NUNCA usar FETCH FIRST (usar ROWNUM com subquery)
4. SEMPRE qualificar colunas com alias (C.campo, P.campo)
5. SEMPRE incluir todas colunas nao-agregadas no GROUP BY
6. NUNCA colocar ponto-e-virgula no final
7. MARCA esta em TGFPRO, NOMEPARC em TGFPAR, APELIDO em TGFVEN
8. Preferir JOINs diretos em vez de subqueries complexas
9. NUNCA juntar TGFFIN com TGFITE na mesma query (multiplica valores)
10. Para pendencias financeiras, filtrar por DHBAIXA IS NULL (nao por DTNEG)
11. Sempre mostrar top 10+ em rankings (nao FETCH FIRST 1 ROW)
12. Para FILTRAR por marca, usar TGFMAR.DESCRICAO (NUNCA TGFPRO.MARCA)
13. NUNCA usar nivel CABECALHO (EXISTS + VLRNOTA) quando filtrando por MARCA — usar nivel ITEM
14. DTPREVENT = previsao de entrega (incluir quando pergunta sobre entrega/previsao)
15. SEMPRE usar UPPER() ao comparar campos de texto (marca, fornecedor, produto)
16. "previsao de entrega" = MOSTRAR DTPREVENT com NVL, NAO filtrar IS NOT NULL (a menos que o usuario peca explicitamente)
17. Para relatorios/acompanhamento usar STATUSNOTA <> 'C' (excluir cancelados)
18. "Pedidos de compra" = TIPMOV = 'O'. "Notas de compra" = TIPMOV = 'C'. "Tudo de compra" = IN ('C','O')
19. Se menciona MARCA/PRODUTO: query nivel ITEM (FROM TGFITE). Valor = ITE.VLRTOT. Pendencia = TGFVAR (QTD_PEDIDA - QTD_ATENDIDA)
20. DTPREVENT eh DATE — usar NVL(TO_CHAR(DTPREVENT,'DD/MM/YYYY'),'Sem previsao'). NUNCA NVL(DTPREVENT,'texto') (erro ORA tipo DATE vs VARCHAR)
21. "Pedidos pendentes" = PENDENTE='S' (campo do Sankhya). NUNCA usar STATUSNOTA='P' para pendencia
22. STATUSNOTA indica estado da NOTA (P/L/A/C). PENDENTE indica se falta receber itens (S/N). Sao campos DIFERENTES
