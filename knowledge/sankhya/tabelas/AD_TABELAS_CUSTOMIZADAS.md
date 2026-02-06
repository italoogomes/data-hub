# Tabelas AD_* - Customizacoes MMarra

**Descricao:** Mapeamento completo das tabelas customizadas (prefixo AD_) criadas pela MMarra no Sankhya.

**Total:** 142 tabelas
- Com dados: 95
- Vazias: 47

**Levantamento:** 2026-02-06

---

## Categorias de Tabelas AD_*

### 1. Tabelas de Negocio (Documentadas)

| Tabela | Registros | Uso | Documentacao |
|--------|-----------|-----|--------------|
| AD_TGFPROAUXMMA | 1.145.087 | Numeros auxiliares de produtos | [AD_TGFPROAUXMMA.md](AD_TGFPROAUXMMA.md) |
| AD_TGFCUSMMA | 709.230 | Historico de custos | [AD_TGFCUSMMA.md](AD_TGFCUSMMA.md) |
| AD_MARCAS | 799 | Marcas de produtos | [AD_MARCAS.md](AD_MARCAS.md) |

### 2. Tabelas de Workflow (VAZIAS)

Estas tabelas existem mas **nunca foram populadas**. MMarra nao usa workflow customizado.

| Tabela | Status | Proposito Original |
|--------|--------|-------------------|
| AD_APROVACAO | VAZIA | Aprovacoes customizadas |
| AD_LIBERACOESVENDA | VAZIA | Liberacoes de venda |
| AD_COTACOESDEITENS | VAZIA | Itens de cotacao |
| AD_SOLICITACAOCOMPRA | VAZIA | Solicitacao de compra |
| AD_SOLICITACAOADIANTAMENTO | VAZIA | Adiantamentos |

**Conclusao:** MMarra usa TGFCAB com TIPMOV para solicitacoes e nao implementou workflow de aprovacao.

### 3. Tabelas de Importacao/Integracao

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_IMPNUMAUX_MMA | 1.048.301 | Comandos INSERT para importacao |
| AD_CSV_LINHA | 343.834 | Linhas de CSV importados |
| AD_IMPORTACSV | - | Controle de importacao CSV |
| AD_ENTIDADES_MMA | 103.402 | Entidades de integracao |
| AD_ENTIDADES_RSYS2_MMA | 106.289 | Integracao RSYS |

### 4. Tabelas de Produto

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_CADPRODMMA | 397.422 | Cadastro de produtos MMarra |
| AD_CADPRODCODIGO_MMA | 397.709 | Codigos de produtos |
| AD_CODBARRAS_MMA | 339.931 | Codigos de barras |
| AD_PRODCESTRSYS_MMA | 407.860 | CEST dos produtos |
| AD_TGFGRUMMA | 390.374 | Grupos de produtos |
| AD_TGFPROIPI | 13.024 | IPI de produtos |
| AD_PRODGIRO_MMA | 86.307 | Giro de produtos |

### 5. Tabelas Financeiras

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_DUPLICATAS3_MMA | 425.373 | Duplicatas para comissao |
| AD_BASECOMDUPLICATA_MMA | 8.355 | Base comissao duplicatas |
| AD_BASECOMDUPLICATA2_MMA | 13.728 | Base comissao duplicatas v2 |
| AD_MOVBAIXA_MMA | 1.703 | Movimento de baixa |
| AD_INTDDA | 2.949 | Integracao DDA |

### 6. Tabelas de Custo

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_TGFCUSMMA | 709.230 | Historico de custos |
| AD_CUSTOIMP_2312_MMA | 710.194 | Custos importados |
| AD_CUSTOIMP_REL_TGFCUS | 275.164 | Relatorio custos |
| AD_CUSTOPRODCOMISSAO_MMA | - | Custo para comissao |

### 7. Tabelas de Backup/Log

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_BKP_TGWEXP_12012026 | 40.432.998 | Backup WMS enderecamento |
| AD_BKP_TGFVOA_12012026 | 156.403 | Backup volumes |
| AD_BKP_TGWEST_12012026 | 39.381 | Backup estoque WMS |
| AD_LOG_* | varios | Logs de operacoes |
| AD_*_0401 | varios | Snapshots de 01/04 |

### 8. Tabelas de WMS/Estoque

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_GESTAO_ATUALESTOQUE_MMA | 36.426 | Gestao de estoque |
| AD_SALDO_EST_0401 | 35.552 | Saldo estoque |
| AD_SALDOTRANSF | - | Saldo transferencias |
| AD_TRANSFFALTA | - | Faltas em transferencia |
| AD_LOCAL_IMP_MMA | 41.905 | Locais importados |
| AD_LOCALITEM_IMP_MMA | 397.473 | Itens por local |

### 9. Tabelas de Parceiro/Fornecedor

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_FORNEMPPRO | 46.968 | Fornecedor x Empresa x Produto |
| AD_COMPLPARC | VAZIA | Complemento parceiro |
| AD_NATUREZASPARC | VAZIA | Naturezas por parceiro |

### 10. Tabelas DRE/Contabil

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_DRE | - | DRE customizado |
| AD_DREITEM | - | Itens DRE |
| AD_DREMENSAL | VAZIA | DRE mensal |
| AD_CLASSDRE | VAZIA | Classificacao DRE |

### 11. Outras Tabelas

| Tabela | Registros | Uso |
|--------|-----------|-----|
| AD_TABPRCCAB_1 | 248.670 | Tabela de precos |
| AD_TABCOMISSAO_MMA | - | Comissoes |
| AD_PARAM | - | Parametros |
| AD_PARAMETER | - | Parametros v2 |
| AD_PARVALUE | - | Valores de parametros |
| AD_VISITATEC | - | Visitas tecnicas |

---

## Tabelas Vazias Completas (47)

```
AD_ACLMPSSCRIPTS
AD_APROVACAO
AD_CLASSDRE
AD_COMPLPARC
AD_COMPRASEMENT
AD_CONCARGA
AD_COTACOESDEITENS
AD_DESPADIANTAMENTO
AD_DREMENSAL
AD_DREMENSALITEM
AD_DREMENSALTST
AD_DUPLICATAS2_MMA
AD_EMPDESTINO
AD_EMPORIGEM
AD_IMGLAUDO
AD_IMPENDLOG
AD_ITEMPEDIDO
AD_LAUDOTECOS
AD_LIBERACOESVENDA
AD_LOG_TGWREV_IMP_MMA
ADMINSERVICE$PARAMPROCMGE
AD_MODETIQUETAS
AD_MONSESS
AD_MOTORCRED_HISTORICO
AD_NATUREZAS
AD_NATUREZASCR
AD_NATUREZASPARC
AD_NATUREZATIT
AD_NOVOPSOLIC
AD_NUMAUX_IMP_MMA
AD_OCOCOB
AD_ORCA
AD_ORCNATCC
AD_PARAMETER
AD_PARCOMPANY
AD_PARVALUE
AD_PEDIDOVENDA
AD_PENDENCIASVENDA
AD_PLANESTDET
AD_PLANESTPROD
AD_PROANE
AD_PROCMPS
AD_REDEGRUPO
AD_STPRECO
AD_TESEVE
AD_TIPNAT
AD_TSCGUSU
```

---

## Conclusoes

1. **Workflow nao implementado** - AD_APROVACAO e AD_LIBERACOESVENDA vazias
2. **Foco em produtos** - Muitas tabelas para codigos auxiliares, custos, grupos
3. **Integracao pesada** - Tabelas de importacao CSV, entidades, logs
4. **Backups frequentes** - Muitas tabelas AD_BKP_* e snapshots de datas
5. **Sistema de custos customizado** - AD_TGFCUSMMA com historico completo
6. **Cross-reference robusto** - 1.1M codigos auxiliares de produtos

---

*Documentado em: 2026-02-06*
