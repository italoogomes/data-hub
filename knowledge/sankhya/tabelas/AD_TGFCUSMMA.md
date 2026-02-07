# AD_TGFCUSMMA

**Descricao:** Historico de Custos (MMarra)
**Total de campos no dicionario:** 10

## Campos Principais

| Campo | Tipo | Descricao |
|-------|------|-----------|
| CODEMP | Inteiro | Cód. Empresa |
| CODPROD | Inteiro | Código |
| CUSCOMICM | Decimal | CUSCOMICM |
| CUSGER | Decimal | CUSGER |
| CUSMEDSEMICM | Decimal | CUSMEDSEMICM |
| CUSREP | Decimal | CUSREP |
| CUSSEMICM | Decimal | CUSSEMICM |
| CUSVARIAVEL | Decimal | CUSVARIAVEL |
| DTATUAL | Texto | DTATUAL |
| SEQUENCIA | Inteiro | Sequência |

## Relacionamentos (via TDDLIG)

- AD_TGFCUSMMA -> Empresa (TSIEMP) [I]
- AD_TGFCUSMMA -> Produto (TGFPRO) [I]
