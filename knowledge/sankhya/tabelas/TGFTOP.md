# TGFTOP

**Descricao:** Tipos de Operacao (TOP) - define o comportamento das operacoes de venda, compra, transferencia, devolucao, etc. Controla estoque, financeiro, fiscal e emissao de documentos.

**Total de registros:** 1.318 TOPs cadastradas

## Conceito

A TOP (Tipo de Operacao) eh o elemento central que determina TODO o comportamento de uma nota/pedido no Sankhya:
- Se atualiza estoque (entrada/saida)
- Se gera financeiro (pagar/receber)
- Se emite NFe/NFSe
- Quais CFOPs usar
- Quais impostos calcular

## Chave Primaria

| Campo | Tipo | Descricao |
|-------|------|-----------|
| CODTIPOPER | NUMBER(22) | Codigo da TOP |
| DHALTER | DATE | Data/hora alteracao (versionamento) |

**Nota:** A PK composta permite historico de alteracoes da mesma TOP.

## Campos Principais

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| CODTIPOPER | NUMBER(22) | N | Codigo da TOP |
| DESCROPER | VARCHAR2(100) | N | Descricao da operacao |
| TIPMOV | VARCHAR2(1) | N | Tipo de movimento |
| ATIVO | VARCHAR2(1) | N | TOP ativa (S/N) |
| DHALTER | DATE | N | Data/hora alteracao |

## Campos de Comportamento - ESTOQUE

| Campo | Tipo | Descricao |
|-------|------|-----------|
| ATUALEST | VARCHAR2(1) | Atualiza estoque (B=baixa, E=entrada, N=nao, R=reserva) |
| ATUALESTMP | NUMBER(22) | Atualiza estoque MP |
| ATUALESTTERC | VARCHAR2(1) | Atualiza estoque terceiros |
| ADIARATUALEST | VARCHAR2(1) | Adiar atualizacao estoque |
| VALEST | VARCHAR2(1) | Valida estoque |

## Campos de Comportamento - FINANCEIRO

| Campo | Tipo | Descricao |
|-------|------|-----------|
| ATUALFIN | NUMBER(22) | Atualiza financeiro (0=nao, 1=pagar, -1=receber) |
| TIPATUALFIN | VARCHAR2(1) | Tipo atualizacao financeira |
| VLRBASEPGTO | FLOAT(22) | Valor base pagamento |

## Campos de Comportamento - FISCAL/NFe

| Campo | Tipo | Descricao |
|-------|------|-----------|
| NFE | VARCHAR2(1) | Emite NFe (N=nao, T=transmite, M=manual) |
| NFSE | VARCHAR2(1) | Emite NFSe |
| CTE | CHAR(1) | Emite CTe |
| EMITENOTA | VARCHAR2(1) | Emite nota |
| ATUALLIVFIS | VARCHAR2(1) | Atualiza livros fiscais |

## Campos de CFOP

| Campo | Tipo | Descricao |
|-------|------|-----------|
| CODCFO_ENTRADA | NUMBER(22) | CFOP entrada dentro estado |
| CODCFO_SAIDA | NUMBER(22) | CFOP saida dentro estado |
| CODCFO_ENTRADA_FORA | NUMBER(22) | CFOP entrada fora estado |
| CODCFO_SAIDA_FORA | NUMBER(22) | CFOP saida fora estado |
| CODCFO_TERC | NUMBER(22) | CFOP terceiros |

## Campos de Impostos

| Campo | Tipo | Descricao |
|-------|------|-----------|
| TEMICMS | VARCHAR2(1) | Tem ICMS |
| TEMIPI | VARCHAR2(1) | Tem IPI |
| TEMPIS | VARCHAR2(1) | Tem PIS |
| TEMCOFINS | VARCHAR2(1) | Tem COFINS |
| TEMISS | VARCHAR2(1) | Tem ISS |
| TEMIRF | VARCHAR2(1) | Tem IRF |
| CALCICMS | VARCHAR2(1) | Calcula ICMS |

## Valores de Dominio - TIPMOV (Tipo de Movimento)

| Valor | Qtd | Descricao |
|-------|-----|-----------|
| C | 376 | Compra |
| V | 292 | Venda |
| P | 195 | Pedido |
| D | 124 | Devolucao |
| E | 91 | Entrada |
| O | 87 | Ordem/Pedido Compra |
| I | 45 | Inventario |
| J | 32 | Solicitacao |
| G | 20 | Gerencial |
| R | 14 | Requisicao |
| T | 13 | Transferencia |
| F | 10 | Fatura |
| Q | 9 | Cotacao |
| L | 6 | Lote |
| B | 4 | Bonificacao |

## Valores de Dominio - ATUALEST (Atualizacao Estoque)

| Valor | Significado |
|-------|-------------|
| B | Baixa estoque (saida) |
| E | Entrada estoque |
| N | Nao atualiza |
| R | Reserva |

## Valores de Dominio - ATUALFIN (Atualizacao Financeira)

| Valor | Significado |
|-------|-------------|
| 1 | Gera conta a PAGAR |
| -1 | Gera conta a RECEBER |
| 0 | Nao gera financeiro |

## Valores de Dominio - NFE (Emissao NFe)

| Valor | Significado |
|-------|-------------|
| N | Nao emite NFe |
| T | Transmite NFe automaticamente |
| M | NFe manual |

## TOPs Mais Usadas na MMarra

| CODTIPOPER | Descricao | TIPMOV | ATUALEST | ATUALFIN | Qtd Notas | Valor Total |
|------------|-----------|--------|----------|----------|-----------|-------------|
| **1100** | VENDA NF-E (BALCAO) | V | B | 1 | 120.379 | R$ 254M |
| **1101** | VENDA NF-E | V | B | 1 | 105.062 | R$ 233M |
| **1209** | COMPRA MERCADORIA REVENDA | C | E | -1 | 47.523 | R$ 382M |
| **1150** | TRANSFERENCIA SAIDA | V | B | 0 | 21.712 | R$ 47M |
| **1452** | TRANSFERENCIA ENTRADA | C | E | 0 | 21.276 | R$ 46M |
| **1202** | DEVOLUCAO VENDA | D | E | -1 | 5.546 | R$ 6M |
| **1001** | PEDIDO VENDA WMS | P | R | 1 | 4.906 | R$ 6M |
| **1804** | SOLICITACAO COMPRA | J | N | 0 | 2.801 | R$ 6M |
| **1007** | PEDIDO VENDA EMPENHO | P | N | 1 | 2.327 | R$ 5M |
| **1501** | DEVOLUCAO COMPRA | E | B | 1 | 806 | R$ 2M |

## TOPs por Categoria

### Vendas (TIPMOV = V)
- **1100** - Venda Balcao (mais usada)
- **1101** - Venda NFe padrao
- **1150** - Transferencia saida
- **1130** - Remessa exportacao
- **1132** - Venda p/ industrializacao
- **1151** - Bonificacao saida
- **1195** - Ajuste estoque saida

### Compras (TIPMOV = C)
- **1209** - Compra revenda (mais usada)
- **1452** - Transferencia entrada
- **1401** - Compra WMS
- **1402** - Compra uso/consumo
- **1404** - Compra servico
- **1451** - Bonificacao entrada

### Pedidos (TIPMOV = P)
- **1001** - Pedido venda WMS consumo
- **1007** - Pedido venda empenho
- **1012** - Pedido venda WMS revenda
- **1000** - Orcamento venda

### Devolucoes (TIPMOV = D)
- **1202** - Devolucao venda (NF terceiros)
- **1203** - Devolucao refatura
- **1204** - Devolucao venda refatura

### Pedidos Compra (TIPMOV = O)
- **1301** - Pedido compra revenda
- **1304** - Pedido compra servico
- **1313** - Pedido compra entrega futura

## Relacionamentos (FKs)

| Campo | Tabela Ref | Campo Ref | Descricao |
|-------|------------|-----------|-----------|
| CODCFO_ENTRADA | TGFCFO | CODCFO | CFOP entrada |
| CODCFO_SAIDA | TGFCFO | CODCFO | CFOP saida |
| CODCFO_ENTRADA_FORA | TGFCFO | CODCFO | CFOP entrada fora estado |
| CODCFO_SAIDA_FORA | TGFCFO | CODCFO | CFOP saida fora estado |
| CODMODNF | TGFMON | CODMODNF | Modelo nota fiscal |
| CODMODNFSE | TGFMON | CODMODNF | Modelo NFSe |
| NULAYOUT | TGFLAY | NULAYOUT | Layout impressao |
| NUCCO | TGFCCO | NUCCO | Classificacao contabil |
| NUFOP | TGFFOP | NUFOP | Forma pagamento |
| NUNOTAMODELO | TGFCAB | NUNOTA | Nota modelo |

## Como Usar

### Identificar comportamento de uma TOP
```sql
SELECT CODTIPOPER, DESCROPER, TIPMOV,
       ATUALEST, ATUALFIN, NFE,
       TEMICMS, TEMIPI
FROM TGFTOP
WHERE CODTIPOPER = 1100
  AND DHALTER = (SELECT MAX(DHALTER) FROM TGFTOP WHERE CODTIPOPER = 1100)
```

### TOPs que geram NFe
```sql
SELECT CODTIPOPER, DESCROPER, TIPMOV
FROM TGFTOP
WHERE NFE IN ('T', 'M')
  AND ATIVO = 'S'
ORDER BY CODTIPOPER
```

### TOPs que atualizam estoque
```sql
SELECT CODTIPOPER, DESCROPER, TIPMOV, ATUALEST
FROM TGFTOP
WHERE ATUALEST IN ('B', 'E')
  AND ATIVO = 'S'
ORDER BY CODTIPOPER
```

## Observacoes

- Uma TOP define TUDO sobre como a nota se comporta
- Alteracoes na TOP sao versionadas (DHALTER na PK)
- TOP incorreta pode causar: estoque errado, financeiro duplicado, impostos incorretos
- Sempre consultar a versao mais recente (MAX DHALTER)
- TOPs customizadas MMarra comecam com AD_* nos campos
- Campo TIPMOV eh fundamental para filtrar por tipo de operacao

## Campos Customizados MMarra (AD_*)

| Campo | Descricao |
|-------|-----------|
| AD_LOTECTB | Lote contabil |
| AD_ATUALESTANT | Atualiza estoque anterior |
| AD_AGRUPASERVICO | Agrupa servico |
| AD_ESTEMPENHO | Estoque empenho |
| AD_RESERVAEMPENHO | Reserva empenho |
| AD_OBS | Observacoes |
