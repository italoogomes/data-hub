# Codigos Auxiliares de Produto

**Quando aplica:** Busca de produtos por codigo do fabricante/marca

**O que acontece:** Sistema armazena multiplos codigos alternativos para cada produto em AD_TGFPROAUXMMA

---

## Regra Principal

**Cada produto pode ter multiplos codigos auxiliares (cross-reference).**

Quando cliente pede por codigo do fabricante (ex: "77596615"), sistema busca em AD_TGFPROAUXMMA e encontra o produto correto.

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Total codigos | 1.145.087 |
| Produtos com codigos | 203.974 |
| Media por produto | 5.6 codigos |
| Produto com mais codigos | 388 codigos |

---

## Distribuicao de Codigos por Produto

| Faixa | Produtos | % |
|-------|----------|---|
| 1 codigo | 21.315 | 10% |
| 2-5 codigos | 125.757 | 62% |
| 6-10 codigos | 33.480 | 16% |
| 10+ codigos | 23.422 | 11% |

**62% dos produtos tem 2-5 codigos auxiliares.**

---

## Codigos por Marca (Top 10)

| Marca | Codigos | % |
|-------|---------|---|
| MERCEDES BENZ | 56.231 | 4.9% |
| VW | 47.542 | 4.2% |
| FORD | 38.549 | 3.4% |
| EURORICAMBI | 25.910 | 2.3% |
| EATON | 24.250 | 2.1% |
| VOLVO | 22.706 | 2.0% |
| LNG | 21.498 | 1.9% |
| SCANIA | 17.674 | 1.5% |
| RP IMPORTS | 17.370 | 1.5% |
| CUMMINS | 15.927 | 1.4% |

**Marcas de veiculos pesados dominam.**

---

## Uso Pratico

### Cenario 1: Cliente pede por codigo

```
Cliente: "Preciso da peca 77596615"
         ↓
Sistema busca em AD_TGFPROAUXMMA
         ↓
Encontra CODPROD = 476
         ↓
Produto: "JOGO BRONZINA MANCAL STD MOTOR"
```

### Cenario 2: Cross-reference entre marcas

```
Produto CODPROD = 476 tem:
- Codigo 77596615 (Marca A)
- Codigo BC048037500361420 (Marca B)
         ↓
Mesma peca, codigos diferentes
```

---

## Exemplo de Produto com Muitos Codigos

Produto 103594 tem **388 codigos auxiliares**:

| Codigo | Observacao | Origem |
|--------|------------|--------|
| 078115561J | - | - |
| 07811561J | - | - |
| 1,05001E+11 | - | - |
| 1,06001E+11 | - | - |
| ... | | |

**Peca compativel com muitos veiculos/marcas.**

---

## Estrutura AD_TGFPROAUXMMA

| Campo | Tipo | Uso |
|-------|------|-----|
| CODPROD | NUMBER | Produto (PK) |
| IDNUMAUX | NUMBER | Sequencial (PK) |
| NUMAUX | VARCHAR2(100) | O codigo auxiliar |
| CODIGO | NUMBER | Marca (FK TGFMAR) |
| OBSERVACAO | VARCHAR2(100) | Obs sobre o codigo |
| ORIGEM | VARCHAR2(100) | De onde veio |

---

## Queries Uteis

### Buscar produto por codigo auxiliar

```sql
SELECT
    a.NUMAUX,
    a.CODPROD,
    p.DESCRPROD,
    p.REFERENCIA,
    m.DESCRICAO as MARCA
FROM AD_TGFPROAUXMMA a
JOIN TGFPRO p ON a.CODPROD = p.CODPROD
LEFT JOIN TGFMAR m ON a.CODIGO = m.CODIGO
WHERE UPPER(a.NUMAUX) LIKE UPPER('%:codigo%')
```

### Todos os codigos de um produto

```sql
SELECT
    a.NUMAUX,
    m.DESCRICAO as MARCA,
    a.OBSERVACAO,
    a.ORIGEM
FROM AD_TGFPROAUXMMA a
LEFT JOIN TGFMAR m ON a.CODIGO = m.CODIGO
WHERE a.CODPROD = :codprod
ORDER BY m.DESCRICAO, a.NUMAUX
```

### Produtos com mais codigos

```sql
SELECT
    a.CODPROD,
    p.DESCRPROD,
    COUNT(*) as QTD_CODIGOS
FROM AD_TGFPROAUXMMA a
JOIN TGFPRO p ON a.CODPROD = p.CODPROD
GROUP BY a.CODPROD, p.DESCRPROD
ORDER BY QTD_CODIGOS DESC
```

### Cross-reference (encontrar equivalentes)

```sql
-- Dado um codigo, encontrar outros codigos do mesmo produto
SELECT DISTINCT a2.NUMAUX, m.DESCRICAO as MARCA
FROM AD_TGFPROAUXMMA a1
JOIN AD_TGFPROAUXMMA a2 ON a1.CODPROD = a2.CODPROD
LEFT JOIN TGFMAR m ON a2.CODIGO = m.CODIGO
WHERE a1.NUMAUX = ':codigo_origem'
  AND a2.NUMAUX <> a1.NUMAUX
```

---

## Regras de Negocio

1. **Busca flexivel** - Cliente pode informar qualquer codigo
2. **Cross-reference** - Encontrar equivalentes entre marcas
3. **Multiplas origens** - Codigos de fabricantes, distribuidores, etc
4. **Vinculo com marca** - Saber de qual fabricante eh o codigo
5. **Sem duplicacao** - PK composta evita codigo duplicado por produto

---

## Importancia para Vendas

1. **Agilidade no atendimento** - Vendedor encontra peca rapidamente
2. **Nao perde venda** - Cliente informa codigo errado, sistema encontra
3. **Compatibilidade** - Saber que pecas de marcas diferentes servem
4. **Catalogo unificado** - Varios codigos, um produto

---

## Observacoes

1. **1.1M codigos** - Base extensa de cross-reference
2. **62% tem 2-5 codigos** - Maioria tem alternativas
3. **Marcas de caminhao/onibus** - Mercedes, VW, Ford, Scania
4. **Essencial para vendas** - Cliente nao sabe codigo interno
5. **Manter atualizado** - Novos codigos de fabricantes

---

## Tabelas Relacionadas

- [AD_TGFPROAUXMMA](../sankhya/tabelas/AD_TGFPROAUXMMA.md) - Tabela de codigos
- [TGFPRO](../sankhya/tabelas/TGFPRO.md) - Cadastro de produtos
- [AD_MARCAS](../sankhya/tabelas/AD_MARCAS.md) - Marcas
- TGFMAR - Marcas padrao Sankhya

---

*Documentado em: 2026-02-06*
