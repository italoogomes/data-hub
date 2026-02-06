# AD_MARCAS

**Descricao:** Cadastro de marcas de produtos. Complementa ou substitui TGFMAR para marcas especificas da MMarra.

**Total de registros:** 799

**Tipo:** Tabela customizada MMarra (AD_*)

---

## Contexto MMarra

A MMarra trabalha com pecas automotivas de diversas marcas:
- **Cummins** - 44k SKUs (maior fornecedor)
- **MWM** - 15k SKUs
- **ZF** - 14k SKUs
- **Eaton** - 11k SKUs
- **Navistar** - 10k SKUs

Esta tabela armazena o cadastro dessas marcas para referencia cruzada.

---

## Uso no Negocio

1. **Cross-reference** - Saber qual marca fabrica cada peca
2. **Filtro de busca** - Cliente pede "peca Cummins"
3. **Relatorios** - Vendas por marca
4. **Codigos auxiliares** - Vinculo com AD_TGFPROAUXMMA

---

## Relacionamentos

- Vinculada a **AD_TGFPROAUXMMA** via campo CODIGO
- Cada codigo auxiliar de produto pode ter uma marca associada

---

## Queries Uteis

### Listar todas as marcas

```sql
SELECT * FROM AD_MARCAS ORDER BY 1
```

### Produtos por marca (via AD_TGFPROAUXMMA)

```sql
SELECT
    m.DESCRICAO AS MARCA,  -- ou campo equivalente
    COUNT(DISTINCT a.CODPROD) AS QTD_PRODUTOS
FROM AD_TGFPROAUXMMA a
JOIN AD_MARCAS m ON a.CODIGO = m.CODIGO  -- verificar nome do campo
GROUP BY m.DESCRICAO
ORDER BY QTD_PRODUTOS DESC
```

---

## Observacoes

1. **799 marcas** - Quantidade significativa de fabricantes
2. **Complementar a TGFMAR** - Pode ter dados adicionais
3. **Essencial para cross-reference** - Encontrar equivalencias

---

## Tabelas Relacionadas

- [AD_TGFPROAUXMMA](AD_TGFPROAUXMMA.md) - Numeros auxiliares de produtos
- [TGFPRO](TGFPRO.md) - Cadastro de produtos
- TGFMAR - Marcas padrao Sankhya

---

*Documentado em: 2026-02-06*
