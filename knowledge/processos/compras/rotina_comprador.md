# Rotina Diaria do Time de Compras

**Modulo:** compras

---

## Perguntas do Dia a Dia

O time de compras da MMarra faz estas perguntas frequentemente. Cada uma se traduz em uma consulta ao banco:

### 1. "Quais pedidos de compra estao pendentes?"

**Significado:** Pedidos enviados ao fornecedor que ainda nao foram recebidos.

**Dados:** TGFCAB com TIPMOV='O' e PENDENTE='S' e STATUSNOTA<>'C'

**Campos importantes:** NUNOTA, DTNEG, VLRNOTA, NOMEPARC (fornecedor), APELIDO (comprador)

---

### 2. "Quais solicitacoes de compra estao abertas?"

**Significado:** Requisicoes internas que ainda nao viraram pedido de compra.

**Dados:** TGFCAB com TIPMOV='J' e STATUSNOTA IN ('A', 'P')

**Campos importantes:** NUNOTA, DTNEG, VLRNOTA, produtos solicitados (via TGFITE/TGFPRO)

---

### 3. "Quanto gastamos com fornecedor X este mes?"

**Significado:** Total de notas de compra de um fornecedor especifico no periodo.

**Dados:** TGFCAB com TIPMOV='C', filtrar por CODPARC ou NOMEPARC

**Campos importantes:** SUM(VLRNOTA), COUNT(*), NOMEPARC

---

### 4. "Quais os maiores fornecedores em valor?"

**Significado:** Ranking de fornecedores por valor total de compras.

**Dados:** TGFCAB JOIN TGFPAR, TIPMOV='C', GROUP BY parceiro

**Campos importantes:** NOMEPARC, SUM(VLRNOTA), COUNT(*)

---

### 5. "Quais marcas mais compramos?"

**Significado:** Ranking de marcas por quantidade ou valor de compra.

**Dados:** TGFCAB JOIN TGFITE JOIN TGFPRO, TIPMOV='C', GROUP BY MARCA

**Campos importantes:** PR.MARCA, SUM(I.QTDNEG), SUM(I.VLRTOT)

---

### 6. "Tem produto com estoque zerado?"

**Significado:** Produtos que precisam de reposicao urgente.

**Dados:** TGFEST com ESTOQUE <= 0

**Campos importantes:** CODPROD, DESCRPROD, ESTOQUE, CODEMP

---

### 7. "Quais titulos a pagar estao vencidos?"

**Significado:** Boletos/duplicatas de fornecedores que ja venceram.

**Dados:** TGFFIN com RECDESP=-1, DTVENC < SYSDATE, DHBAIXA IS NULL

**Campos importantes:** NUFIN, NOMEPARC, VLRDESDOB, DTVENC

---

### 8. "Quanto vamos pagar esta semana?"

**Significado:** Previsao de pagamentos proximos.

**Dados:** TGFFIN com RECDESP=-1, DTVENC entre hoje e +7 dias, DHBAIXA IS NULL

**Campos importantes:** NOMEPARC, VLRDESDOB, DTVENC

---

### 9. "Quais compras cada comprador fez este mes?"

**Significado:** Produtividade do time de compras por pessoa.

**Dados:** TGFCAB JOIN TGFVEN, TIPMOV='C', GROUP BY vendedor

**Campos importantes:** V.APELIDO, COUNT(*), SUM(VLRNOTA)

---

### 10. "Quais as ultimas compras recebidas?"

**Significado:** Notas de entrada mais recentes para acompanhamento.

**Dados:** TGFCAB com TIPMOV='C', ORDER BY DTNEG DESC

**Campos importantes:** NUNOTA, DTNEG, NOMEPARC, VLRNOTA, STATUSNOTA

---

## Fluxo Tipico do Comprador

1. **Manha:** Verificar solicitacoes abertas (TIPMOV='J') e pedidos pendentes (TIPMOV='O')
2. **Ao longo do dia:** Receber notas de compra (TIPMOV='C'), conferir valores
3. **Semanalmente:** Analisar maiores fornecedores, comparar precos, verificar vencimentos
4. **Mensalmente:** Relatorio de compras por marca, por fornecedor, por comprador

---

## Tabelas Envolvidas

| Tabela | Papel na rotina de compras |
|--------|---------------------------|
| TGFCAB (C) | Notas, pedidos, solicitacoes |
| TGFITE (I) | Itens comprados (produtos, quantidades, valores) |
| TGFPAR (P) | Fornecedores |
| TGFPRO (PR) | Produtos e marcas |
| TGFVEN (V) | Compradores responsaveis |
| TGFFIN (F) | Titulos a pagar |
| TGFEST (ES) | Posicao de estoque |
| TSIEMP (E) | Empresa/filial da compra |
| TGFTOP (T) | Tipo de operacao |
