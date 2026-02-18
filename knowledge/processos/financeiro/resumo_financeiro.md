# Financeiro — Contas a Pagar e Receber

**Modulo:** Financeiro
**Intent:** financeiro (NOVO - a ser implementado)
**Tabela principal:** TGFFIN

---

## Perguntas que os usuarios fazem

| Pergunta | Query |
|----------|-------|
| "contas a pagar" | TGFFIN RECDESP=-1, DHBAIXA IS NULL |
| "contas a receber" | TGFFIN RECDESP=1, DHBAIXA IS NULL |
| "titulos vencidos" | DTVENC < TRUNC(SYSDATE) AND DHBAIXA IS NULL |
| "fluxo de caixa" | GROUP BY DTVENC, SUM por dia |
| "resumo financeiro" | KPIs: a receber + a pagar + vencidos |

---

## Campos chave (TGFFIN)

| Campo | Descricao |
|-------|-----------|
| RECDESP | 1=receber (receita), -1=pagar (despesa) |
| VLRDESDOB | Valor da parcela |
| DTVENC | Data de vencimento |
| DHBAIXA | Data da baixa (NULL=em aberto, NOT NULL=pago/recebido) |
| CODPARC | Parceiro (cliente ou fornecedor) |
| NUNOTA | Nota de origem |
| NUFIN | Numero unico do titulo financeiro |
| CODEMP | Empresa |

---

## Query: Resumo financeiro (KPIs)

**Exemplo SQL:** #33

```sql
SELECT
  SUM(CASE WHEN F.RECDESP = 1 AND F.DHBAIXA IS NULL THEN F.VLRDESDOB ELSE 0 END) AS A_RECEBER,
  SUM(CASE WHEN F.RECDESP = -1 AND F.DHBAIXA IS NULL THEN F.VLRDESDOB ELSE 0 END) AS A_PAGAR,
  SUM(CASE WHEN F.RECDESP = 1 AND F.DHBAIXA IS NULL
           AND F.DTVENC < TRUNC(SYSDATE) THEN F.VLRDESDOB ELSE 0 END) AS VENCIDO_RECEBER,
  SUM(CASE WHEN F.RECDESP = -1 AND F.DHBAIXA IS NULL
           AND F.DTVENC < TRUNC(SYSDATE) THEN F.VLRDESDOB ELSE 0 END) AS VENCIDO_PAGAR
FROM TGFFIN F
```

---

## REGRA CRITICA: NUNCA juntar TGFFIN com TGFITE

- TGFFIN tem parcelas (1 nota = N parcelas)
- TGFITE tem itens (1 nota = N itens)
- JOIN das duas pela NUNOTA gera N x M linhas = valores MULTIPLICADOS
- Se quer VALOR FINANCEIRO → usar TGFFIN SEM TGFITE
- Se quer DADOS DE PRODUTO → usar TGFITE SEM TGFFIN
- Se quer VALOR DA NOTA → usar TGFCAB.VLRNOTA

---

## Observacoes para implementacao

1. **RBAC**: Financeiro geralmente restrito a admin/diretor. Vendedor NAO ve financeiro (exceto comissao dele).
2. **Empresa**: Sempre filtrar por CODEMP quando o usuario especifica empresa/filial.
3. **Periodo**: Se usuario nao especificar periodo, mostrar tudo em aberto (sem filtro de data de emissao, apenas DHBAIXA IS NULL).
