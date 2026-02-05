# TGFITE

**Descricao:** Itens das notas/movimentacoes. Cada registro e um produto/servico de uma nota. Relaciona com TGFCAB (cabecalho) via NUNOTA.

**Total de registros:** 1.109.248

---

## Relacionamento com TGFCAB

```
TGFCAB (1) -----> (N) TGFITE
         NUNOTA
```

Uma nota (TGFCAB) pode ter varios itens (TGFITE). O campo `NUNOTA` e a FK que conecta as tabelas.

**Exemplo de JOIN:**
```sql
SELECT
    c.NUNOTA, c.NUMNOTA, c.TIPMOV, c.DTNEG, c.VLRNOTA,
    i.SEQUENCIA, i.CODPROD, i.QTDNEG, i.VLRTOT
FROM TGFCAB c
JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
WHERE c.TIPMOV = 'V'
  AND ROWNUM <= 100
```

---

## Campos Principais

| Campo | Tipo | Tamanho | Nulo | Descricao |
|-------|------|---------|------|-----------|
| NUNOTA | NUMBER | 22 | N | **PK** - Numero unico da nota (FK para TGFCAB) |
| SEQUENCIA | NUMBER | 22 | N | **PK** - Sequencia do item na nota |
| CODPROD | NUMBER | 22 | N | Codigo do produto (FK para TGFPRO) |
| CODEMP | NUMBER | 22 | N | Codigo da empresa |
| CODLOCALORIG | NUMBER | 22 | N | Local de estoque origem |
| QTDNEG | FLOAT | 22 | N | Quantidade negociada |
| QTDENTREGUE | FLOAT | 22 | N | Quantidade entregue |
| QTDCONFERIDA | FLOAT | 22 | N | Quantidade conferida |
| VLRUNIT | FLOAT | 22 | N | Valor unitario |
| VLRTOT | FLOAT | 22 | N | Valor total do item |
| VLRDESC | FLOAT | 22 | N | Valor desconto |
| VLRCUS | FLOAT | 22 | N | Valor custo |
| CODVOL | VARCHAR2 | 6 | N | Codigo da unidade de medida |
| CODVEND | NUMBER | 22 | N | Codigo do vendedor do item |
| USOPROD | VARCHAR2 | 1 | N | Uso do produto (R/C/S/V/M) |
| ATUALESTOQUE | NUMBER | 22 | N | Atualiza estoque (-1/0/1) |
| STATUSNOTA | VARCHAR2 | 1 | N | Status do item (P/L/A) |
| PENDENTE | VARCHAR2 | 1 | N | Item pendente (S/N) |
| CONTROLE | VARCHAR2 | 17 | N | Controle/lote do produto |
| OBSERVACAO | VARCHAR2 | 4000 | Y | Observacoes do item |

---

## Campos de Impostos

| Campo | Tipo | Descricao |
|-------|------|-----------|
| BASEICMS | FLOAT | Base ICMS |
| VLRICMS | FLOAT | Valor ICMS |
| ALIQICMS | FLOAT | Aliquota ICMS |
| BASEIPI | FLOAT | Base IPI |
| VLRIPI | FLOAT | Valor IPI |
| ALIQIPI | FLOAT | Aliquota IPI |
| BASESUBSTIT | FLOAT | Base ICMS-ST |
| VLRSUBST | FLOAT | Valor ICMS-ST |
| BASEISS | FLOAT | Base ISS |
| VLRISS | FLOAT | Valor ISS |
| ALIQISS | FLOAT | Aliquota ISS |

---

## Campos de Comissao

| Campo | Tipo | Descricao |
|-------|------|-----------|
| PERCCOM | FLOAT | Percentual comissao |
| VLRCOM | FLOAT | Valor comissao |
| PERCCOMGER | FLOAT | Percentual comissao gerente |
| VLRCOMGER | FLOAT | Valor comissao gerente |

---

## Chave Primaria (Composta)

| Campo | Constraint |
|-------|------------|
| NUNOTA | PK_TGFITE |
| SEQUENCIA | PK_TGFITE |

**Importante:** A PK e composta por NUNOTA + SEQUENCIA. Cada item tem uma sequencia unica dentro da nota.

---

## Relacionamentos (FK)

| Campo | Tabela Ref | Campo Ref | Descricao |
|-------|------------|-----------|-----------|
| NUNOTA | TGFCAB | NUNOTA | Cabecalho da nota |
| CODPROD | TGFPRO | CODPROD | Produto |
| CODEMP | TGFEMP | CODEMP | Empresa |
| CODLOCALORIG | TGFLOC | CODLOCAL | Local de estoque |
| CODVEND | TGFVEN | CODVEND | Vendedor |
| CODEXEC | TGFVEN | CODVEND | Executante |
| CODVOL | TGFVOL | CODVOL | Unidade de medida |
| CODCFO | TGFCFO | CODCFO | CFOP |
| CODUSU | TSIUSU | CODUSU | Usuario |
| NUTAB | TGFTAB | NUTAB | Tabela de preco |
| CODPARCEXEC | TGFPAR | CODPARC | Parceiro executante |
| CODPROMO | TGFPROM | CODPROMO | Promocao |

---

## Valores de Dominio

### USOPROD - Uso do Produto

| Valor | Significado | Quantidade |
|-------|-------------|------------|
| R | Revenda | 1.105.264 |
| C | Consumo | 2.367 |
| S | Servico | 1.142 |
| V | Veiculo | 470 |
| M | Materia-prima | 1 |

### ATUALESTOQUE - Atualizacao de Estoque

| Valor | Significado | Quantidade |
|-------|-------------|------------|
| -1 | Baixa estoque (saida) | 659.132 |
| 1 | Entrada estoque | 419.599 |
| 0 | Nao atualiza estoque | 30.517 |

### STATUSNOTA - Status do Item

| Valor | Significado | Quantidade |
|-------|-------------|------------|
| P | Pendente | 1.025.482 |
| L | Liberado | 63.536 |
| A | Aguardando | 20.230 |

---

## Campos Customizados (AD_)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| AD_PRODUTOOS | VARCHAR2 | Produto OS |
| AD_EMPENHADO | VARCHAR2 | Indica se empenhado |
| AD_PRODUTOPARCEIRO | VARCHAR2 | Codigo produto no parceiro |
| AD_NUNOTAVENDAEMP | NUMBER | Nota de venda do empenho |
| AD_SEQITEVENDA | NUMBER | Sequencia item venda |
| AD_VLRCUSTOIARA | FLOAT | Custo IARA |

---

## Queries Uteis

### Itens de uma nota especifica
```sql
SELECT
    i.SEQUENCIA, i.CODPROD, p.DESCRPROD,
    i.QTDNEG, i.VLRUNIT, i.VLRTOT, i.VLRDESC
FROM TGFITE i
JOIN TGFPRO p ON i.CODPROD = p.CODPROD
WHERE i.NUNOTA = 123456
ORDER BY i.SEQUENCIA
```

### Produtos mais vendidos (quantidade)
```sql
SELECT * FROM (
    SELECT
        i.CODPROD,
        SUM(i.QTDNEG) as QTD_TOTAL,
        SUM(i.VLRTOT) as VLR_TOTAL,
        COUNT(*) as NUM_VENDAS
    FROM TGFITE i
    JOIN TGFCAB c ON i.NUNOTA = c.NUNOTA
    WHERE c.TIPMOV = 'V'
      AND c.STATUSNOTA = 'L'
      AND c.DTNEG >= ADD_MONTHS(SYSDATE, -12)
    GROUP BY i.CODPROD
    ORDER BY QTD_TOTAL DESC
) WHERE ROWNUM <= 50
```

### Verificar itens pendentes de separacao
```sql
SELECT
    c.NUNOTA, c.NUMNOTA, c.DTNEG, c.CODPARC,
    i.SEQUENCIA, i.CODPROD, i.QTDNEG, i.QTDENTREGUE
FROM TGFCAB c
JOIN TGFITE i ON c.NUNOTA = i.NUNOTA
WHERE c.TIPMOV = 'V'
  AND c.STATUSNOTA = 'L'
  AND i.PENDENTE = 'S'
  AND i.QTDENTREGUE < i.QTDNEG
ORDER BY c.DTNEG
```

---

## Observacoes

- A PK e composta: NUNOTA + SEQUENCIA
- SEQUENCIA comeca em 1 e e sequencial dentro de cada nota
- ATUALESTOQUE define se movimenta estoque: -1 (baixa), 1 (entrada), 0 (nao)
- USOPROD = 'R' (Revenda) e o mais comum (99%+ dos registros)
- Para calcular valor liquido: VLRTOT - VLRDESC
- QTDENTREGUE vs QTDNEG permite rastrear entregas parciais
- Media de ~3.2 itens por nota (1.1M itens / 343k notas)

---

## Tabelas Relacionadas

- **TGFCAB** - Cabecalho da nota (pai)
- **TGFPRO** - Cadastro de produtos
- **TGFLOC** - Locais de estoque
- **TGFVOL** - Unidades de medida
- **TGFVEN** - Vendedores
- **TGFCFO** - CFOPs

---

*Documentado em: 2026-02-05*
