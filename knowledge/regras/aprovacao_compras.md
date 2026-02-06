# Aprovacao de Compras

**Quando aplica:** Processo de liberacao/aprovacao de notas no sistema

**Status:** MMarra NAO usa sistema de aprovacao formal

---

## Descoberta Principal

**As tabelas de aprovacao estao VAZIAS:**

| Tabela | Registros | Uso esperado |
|--------|-----------|--------------|
| TGFLIB | 0 | Liberacoes padrao Sankhya |
| AD_APROVACAO | 0 | Aprovacoes customizadas |
| AD_LIBERACOESVENDA | 0 | Liberacoes de venda |
| TGFALL | 0 | Alertas/limites |

**Conclusao:** MMarra nao implementou workflow de aprovacao.

---

## Como Funciona na Pratica

### Campos em TGFCAB

| Campo | Valores | Quantidade |
|-------|---------|------------|
| PENDENTE='S', APROVADO='S' | Aprovado | 317.748 notas |
| PENDENTE='N', APROVADO='N' | Normal | 20.460 notas |
| PENDENTE='S', APROVADO='N' | Aguardando | 5.708 notas |
| PENDENTE='N', APROVADO='S' | Aprovado direto | 50 notas |

### Status das Notas Pendentes (STATUSNOTA='P')

| TIPMOV | Tipo | Quantidade | Valor |
|--------|------|------------|-------|
| V | Venda | 798 | R$ 2.77M |
| C | Compra | 265 | R$ 1.99M |
| Z | Outras | 139 | R$ 0 |
| D | Devolucao | 24 | R$ 25k |
| P | Pedido | 14 | R$ 308k |

---

## Fluxo Real

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Nota     │───>│  Pendente?  │───>│  Liberada   │
│ STATUSNOTA  │    │  Manual ou  │    │ STATUSNOTA  │
│    = 'A'    │    │  Automatico │    │    = 'L'    │
└─────────────┘    └─────────────┘    └─────────────┘
```

**Observacao:** A maioria das notas (317k) tem PENDENTE='S' e APROVADO='S', indicando que o sistema "aprova" automaticamente ou que a aprovacao eh feita manualmente sem registro em tabela especifica.

---

## Notas de Compra Liberadas (Exemplo)

| NUNOTA | NUMNOTA | TOP | PENDENTE | APROVADO | VALOR |
|--------|---------|-----|----------|----------|-------|
| 1195240 | 1068122061 | 1427 | S | N | R$ 780 |
| 1195220 | 1302260364 | 1427 | S | N | R$ 1.383 |
| 1196962 | 4330 | 1440 | N | N | R$ 1.800 |

**TOP 1427** aparece frequentemente (verificar o que eh).

---

## Como Verificar Status

### Notas pendentes de aprovacao

```sql
SELECT
    TIPMOV,
    CODTIPOPER,
    COUNT(*) as qtd,
    SUM(VLRNOTA) as valor
FROM TGFCAB
WHERE STATUSNOTA = 'P'
GROUP BY TIPMOV, CODTIPOPER
ORDER BY qtd DESC
```

### Notas aguardando (PENDENTE='S', APROVADO='N')

```sql
SELECT
    NUNOTA,
    NUMNOTA,
    TIPMOV,
    CODTIPOPER,
    VLRNOTA,
    DTNEG
FROM TGFCAB
WHERE PENDENTE = 'S'
  AND APROVADO = 'N'
  AND STATUSNOTA <> 'L'
ORDER BY DTNEG DESC
```

---

## Regra de Negocio

1. **Nao ha workflow formal** - Aprovacao eh feita manualmente
2. **STATUSNOTA controla** - 'A' (aberta) -> 'P' (pendente) -> 'L' (liberada)
3. **Campos PENDENTE/APROVADO** - Informativos, nao bloqueiam
4. **Sem registro de quem aprovou** - TGFLIB vazia
5. **Liberacao manual** - Usuario confirma nota diretamente

---

## Implicacoes

1. **Auditoria limitada** - Nao ha registro de quem aprovou
2. **Sem alçadas** - Qualquer usuario pode liberar
3. **Sem limites de valor** - TGFALL vazia
4. **Controle operacional** - Feito fora do sistema ou por costume

---

## Tabelas Relacionadas

- [TGFCAB](../sankhya/tabelas/TGFCAB.md) - Cabecalho das notas
- [TGFLIB](../sankhya/tabelas/TGFLIB.md) - Liberacoes (vazia)
- [AD_TABELAS_CUSTOMIZADAS](../sankhya/tabelas/AD_TABELAS_CUSTOMIZADAS.md) - Tabelas AD_*

---

*Documentado em: 2026-02-06*
