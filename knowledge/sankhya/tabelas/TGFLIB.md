# TGFLIB

**Descricao:** Registro de liberacoes/aprovacoes de notas. Tabela padrao do Sankhya para controle de workflow de aprovacao.

**Status MMarra:** VAZIA (0 registros) - MMarra utiliza sistema customizado de aprovacoes.

---

## Campos

| Campo | Tipo | Tamanho | PK | Permite Nulo | Descricao |
|-------|------|---------|----|--------------| ----------|
| NUNOTA | NUMBER | 22 | PK | N | Numero unico da nota |
| CODUSU | NUMBER | 22 | PK | N | Codigo do usuario que liberou |
| DT | DATE | 7 | | N | Data/hora da liberacao |
| LIBERACOES | VARCHAR2 | 50 | | S | Tipo/codigo da liberacao |
| OBS | VARCHAR2 | 255 | | S | Observacao da liberacao |

---

## Chaves

### Chave Primaria (PK)
- **PK_TGFLIB:** NUNOTA + CODUSU (composta)

### Chaves Estrangeiras (FK)
| Campo | Tabela Referenciada | Campo Referenciado |
|-------|--------------------|--------------------|
| NUNOTA | TGFCAB | NUNOTA |
| CODUSU | TSIUSU | CODUSU |

---

## Relacionamentos

- `NUNOTA` -> `TGFCAB.NUNOTA` (nota liberada)
- `CODUSU` -> `TSIUSU.CODUSU` (usuario que liberou)

---

## Uso Esperado (Sankhya Padrao)

No Sankhya padrao, TGFLIB armazena:
1. Cada aprovacao de nota por usuario
2. Permite multiplos usuarios aprovarem mesma nota
3. Campo LIBERACOES indica tipo (ex: 'ALCA', 'DESC', 'CRED')
4. Campo OBS permite justificativa

### Fluxo Padrao

```
Nota criada (STATUSNOTA = 'A')
    |
    v
Regra exige aprovacao
    |
    v
Nota fica pendente (STATUSNOTA = 'P')
    |
    v
Usuario aprova -> INSERT em TGFLIB
    |
    v
Se todas aprovacoes OK -> STATUSNOTA = 'L'
```

---

## Situacao MMarra

**A tabela esta VAZIA.**

MMarra utiliza sistema customizado de aprovacoes:

| Tabela | Uso |
|--------|-----|
| AD_APROVACAO | Aprovacoes customizadas |
| AD_LIBERACOESVENDA | Liberacoes especificas de venda |

Isso indica que:
1. Workflow de aprovacao foi customizado
2. Regras de negocio especificas da MMarra
3. Nao usa mecanismo padrao do Sankhya

---

## Queries Uteis

### Verificar se tem registros

```sql
SELECT COUNT(*) as total FROM TGFLIB
-- Resultado: 0
```

### Estrutura da tabela

```sql
SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE
FROM USER_TAB_COLUMNS
WHERE TABLE_NAME = 'TGFLIB'
ORDER BY COLUMN_ID
```

---

## Observacoes

1. **Tabela vazia** - MMarra nao usa TGFLIB padrao
2. **Sistema customizado** - Verificar AD_APROVACAO e AD_LIBERACOESVENDA
3. **PK composta** - Permite mesmo usuario aprovar varias vezes (diferentes tipos)
4. **Vinculo via NUNOTA** - Conecta com qualquer nota em TGFCAB
5. **Auditoria** - Campo DT registra momento da aprovacao

---

## Processos Relacionados

- [Fluxo de Compra](../../processos/compras/fluxo_compra.md) - Aprovacao de compras
- [Fluxo de Venda](../../processos/vendas/fluxo_venda.md) - Aprovacao de vendas

---

*Documentado em: 2026-02-06*
