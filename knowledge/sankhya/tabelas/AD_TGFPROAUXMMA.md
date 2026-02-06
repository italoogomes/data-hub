# AD_TGFPROAUXMMA

**Descricao:** Numeros auxiliares de produtos. Armazena codigos alternativos, referencias de fabricantes e codigos de outras marcas para o mesmo produto.

**Total de registros:** 1.145.087

**Tipo:** Tabela customizada MMarra (AD_*)

---

## Campos

| Campo | Tipo | Tamanho | PK | Descricao |
|-------|------|---------|----| ----------|
| CODPROD | NUMBER | 22 | PK | Codigo do produto |
| IDNUMAUX | NUMBER | 22 | PK | ID sequencial do numero auxiliar |
| NUMAUX | VARCHAR2 | 100 | | O numero/codigo auxiliar |
| CODIGO | NUMBER | 22 | | Codigo da marca (FK TGFMAR) |
| OBSERVACAO | VARCHAR2 | 100 | | Observacao sobre o codigo |
| ORIGEM | VARCHAR2 | 100 | | Origem do codigo |

---

## Chaves

### Chave Primaria (PK)
- **CODPROD + IDNUMAUX** (composta)

### Chaves Estrangeiras (FK)
| Campo | Tabela Referenciada | Campo Referenciado |
|-------|--------------------|--------------------|
| CODPROD | TGFPRO | CODPROD |
| CODIGO | TGFMAR | CODIGO |

---

## Uso no Negocio

Esta tabela permite:
1. **Busca por codigo alternativo** - Cliente informa codigo do fabricante
2. **Cross-reference** - Saber qual codigo de outra marca equivale
3. **Importacao** - Codigo usado em sistemas legados

### Exemplo Pratico

Produto CODPROD=476 pode ter varios numeros auxiliares:
- `77596615` (codigo fabricante X)
- `BC048037500361420` (codigo fabricante Y)

Quando cliente pede por qualquer desses codigos, sistema encontra o produto correto.

---

## Estatisticas

| Metrica | Valor |
|---------|-------|
| Total de registros | 1.145.087 |
| Media por produto | ~3 codigos auxiliares |
| Produtos com auxiliares | ~380.000 |

---

## Queries Uteis

### Buscar produto por codigo auxiliar

```sql
SELECT
    a.CODPROD,
    p.DESCRPROD,
    a.NUMAUX,
    m.DESCRICAO AS MARCA
FROM AD_TGFPROAUXMMA a
JOIN TGFPRO p ON a.CODPROD = p.CODPROD
LEFT JOIN TGFMAR m ON a.CODIGO = m.CODIGO
WHERE UPPER(a.NUMAUX) LIKE '%CODIGO_BUSCADO%'
```

### Produtos com mais codigos auxiliares

```sql
SELECT
    a.CODPROD,
    p.DESCRPROD,
    COUNT(*) AS QTD_CODIGOS
FROM AD_TGFPROAUXMMA a
JOIN TGFPRO p ON a.CODPROD = p.CODPROD
GROUP BY a.CODPROD, p.DESCRPROD
ORDER BY QTD_CODIGOS DESC
```

### Codigos por marca

```sql
SELECT
    m.DESCRICAO AS MARCA,
    COUNT(*) AS QTD_CODIGOS
FROM AD_TGFPROAUXMMA a
JOIN TGFMAR m ON a.CODIGO = m.CODIGO
GROUP BY m.DESCRICAO
ORDER BY QTD_CODIGOS DESC
```

---

## Observacoes

1. **Tabela grande** - Mais de 1M de registros
2. **Essencial para vendas** - Vendedor busca por codigo do cliente
3. **Cross-reference** - Permite encontrar equivalencias entre marcas
4. **Vinculo com TGFMAR** - Identifica a marca de cada codigo

---

## Tabelas Relacionadas

- [TGFPRO](TGFPRO.md) - Cadastro de produtos
- TGFMAR - Cadastro de marcas

---

*Documentado em: 2026-02-06*
