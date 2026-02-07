# TGFMAR

**Descricao:** Marcas de Produtos
**Total de registros:** 1.441

## Campos

| Campo | Tipo | PK/FK | Descricao |
|-------|------|-------|-----------|
| CODIGO | Inteiro | PK | Codigo da marca |
| DESCRICAO | Texto | | Nome da marca (ex: 'DONALDSON', 'CUMMINS', 'MWM') |
| AD_CODVEND | Inteiro | FK -> TGFVEN.CODVEND | Comprador responsavel pela marca |
| AD_CONSIDLISTAFORN | Texto | | Considera Lista Fornecedor (S/N) |
| AD_IDEXTERNO | Texto | | ID Externo (integracao) |

## Relacionamentos

- `TGFPRO.CODMARCA` -> `TGFMAR.CODIGO` (produto pertence a uma marca)
- `TGFMAR.AD_CODVEND` -> `TGFVEN.CODVEND` (comprador responsavel pela marca)
- `AD_TGFPROAUXMMA.CODIGO` -> `TGFMAR.CODIGO` (numeros auxiliares por marca)

## Valores de Dominio

### AD_CONSIDLISTAFORN (Considera Lista Fornecedor)

| Valor | Significado |
|-------|-------------|
| S | Sim |
| N | Nao |

## Observacoes

- Para filtrar por marca, SEMPRE usar: `JOIN TGFPRO PR ON I.CODPROD = PR.CODPROD JOIN TGFMAR M ON M.CODIGO = PR.CODMARCA WHERE M.DESCRICAO = 'NOME_MARCA'`
- NUNCA usar `TGFPRO.MARCA` diretamente para filtrar - pode nao conter o nome legivel
- Campo `AD_CODVEND` permite saber quem eh o comprador responsavel por cada marca
- Top marcas: Mercedes, VW, Ford, Cummins, MWM (pecas automotivas)
