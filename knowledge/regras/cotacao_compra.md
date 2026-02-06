# Cotacao de Compra

**Quando aplica:** Comparacao de precos entre fornecedores antes de fechar pedido

**O que acontece:** Comprador abre cotacao em TGFCOT vinculada a solicitacao

---

## Regra Principal

**MMarra usa TGFCOT para cotacoes, vinculadas a solicitacoes via NUNOTAORIG.**

| Metrica | Valor |
|---------|-------|
| Total cotacoes | 2.849 |
| Com NUNOTAORIG (vinculadas) | 2.848 (99.9%) |
| Sem origem | 1 |

---

## Status das Cotacoes (SITUACAO)

| Status | Significado | Quantidade | % |
|--------|-------------|------------|---|
| F | Finalizada | 1.526 | 54% |
| C | Cancelada | 848 | 30% |
| A | Aberta | 399 | 14% |
| E | Em andamento | 59 | 2% |
| P | Pendente | 17 | <1% |

**54% finalizadas**, indicando processo de cotacao ativo.

---

## Fluxo Completo

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ Solicitacao │───>│  Cotacao    │───>│  Melhor     │───>│  Pedido     │
│  TIPMOV='J' │    │   TGFCOT    │    │  Proposta   │    │  TIPMOV='O' │
│  TOP 1804   │    │ NUNOTAORIG  │    │  Avaliada   │    │  TOP 1301   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │
      │                  ▼
      │           ┌─────────────┐
      └──────────>│   Vinculo   │
                  │  NUNOTAORIG │
                  └─────────────┘
```

---

## Sistema de Pesos

TGFCOT permite configurar pesos para avaliacao automatica:

| Campo | Uso |
|-------|-----|
| PESOPRECO | Peso do preco |
| PESOCONDPAG | Peso da condicao de pagamento |
| PESOPRAZOENTREG | Peso do prazo de entrega |
| PESOQUALPROD | Peso da qualidade do produto |
| PESOCONFIABFORN | Peso da confiabilidade |

### Configuracao MMarra

**Apenas PESOPRECO=1 configurado.**

| NUM | PESOPRECO | PESOCONDPAG | PESOPRAZOENTREG |
|-----|-----------|-------------|-----------------|
| 2855 | 1 | NULL | NULL |
| 2854 | 1 | NULL | NULL |
| 2853 | 1 | NULL | NULL |

**Conclusao:** MMarra avalia cotacoes apenas por preco, sem considerar outros criterios.

---

## Tabelas de Itens

| Tabela | Status | Uso esperado |
|--------|--------|--------------|
| TGFCOI | VAZIA | Itens cotados padrao |
| TGFCOC | VAZIA | Fornecedores cotados |
| AD_COTACOESDEITENS | VAZIA | Itens customizado |

**Observacao:** Itens das cotacoes podem estar em outra estrutura ou nao sao registrados formalmente.

---

## Exemplo de Cotacao

| NUMCOTACAO | DHINIC | SITUACAO | NUNOTAORIG |
|------------|--------|----------|------------|
| 2845 | 06/02/2026 | A | (vinculada) |
| 2840 | 06/02/2026 | A | (vinculada) |
| 2852 | 06/02/2026 | A | (vinculada) |

---

## Queries Uteis

### Cotacoes abertas

```sql
SELECT
    c.NUMCOTACAO,
    c.DHINIC,
    c.DHFINAL,
    c.NUNOTAORIG,
    cab.NUMNOTA as NUM_SOLICITACAO,
    c.VALPROPOSTA
FROM TGFCOT c
LEFT JOIN TGFCAB cab ON c.NUNOTAORIG = cab.NUNOTA
WHERE c.SITUACAO = 'A'
ORDER BY c.DHINIC DESC
```

### Cotacoes por periodo

```sql
SELECT
    TO_CHAR(DHINIC, 'YYYY-MM') as MES,
    SITUACAO,
    COUNT(*) as QTD
FROM TGFCOT
WHERE DHINIC IS NOT NULL
GROUP BY TO_CHAR(DHINIC, 'YYYY-MM'), SITUACAO
ORDER BY MES DESC, QTD DESC
```

### Cotacoes de uma solicitacao

```sql
SELECT
    c.NUMCOTACAO,
    c.SITUACAO,
    c.DHINIC,
    c.VALPROPOSTA
FROM TGFCOT c
WHERE c.NUNOTAORIG = :nunota_solicitacao
ORDER BY c.NUMCOTACAO
```

---

## Regras de Negocio

1. **Vinculo obrigatorio** - 99.9% das cotacoes tem NUNOTAORIG
2. **Criterio unico** - Apenas preco (PESOPRECO=1)
3. **Alta taxa de cancelamento** - 30% canceladas
4. **Itens nao formalizados** - TGFCOI/TGFCOC vazias
5. **Sistema novo** - Todas cotacoes de 2026

---

## Ciclo de Vida

```
           A (Aberta)
               │
        ┌──────┼──────┐
        ▼      ▼      ▼
    E (Em    P (Pen-  C (Cance-
   andamento) dente)   lada)
        │      │
        └──────┘
             │
             ▼
        F (Finalizada)
             │
             ▼
      Pedido de Compra
```

---

## Observacoes

1. **Processo estruturado** - Solicitacao -> Cotacao -> Pedido
2. **Sem avaliacao multicritério** - Apenas preco importa
3. **30% cancelamento** - Verificar motivos
4. **Itens nao registrados** - Processo pode ser parcialmente manual
5. **Vinculo forte** - NUNOTAORIG liga cotacao a solicitacao

---

## Tabelas Relacionadas

- [TGFCOT](../sankhya/tabelas/TGFCOT.md) - Cabecalho cotacao
- [TGFCAB](../sankhya/tabelas/TGFCAB.md) - Solicitacoes/Pedidos
- [solicitacao_compra](solicitacao_compra.md) - Regra de solicitacao

---

*Documentado em: 2026-02-06*
