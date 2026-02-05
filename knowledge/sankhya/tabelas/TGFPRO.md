# TGFPRO

**Descricao:** Cadastro de Produtos - armazena todos os produtos, servicos e materiais de consumo

**Total de registros:** 393.696

## Campos Principais

| Campo | Tipo | PK/FK | Nulo | Descricao |
|-------|------|-------|------|-----------|
| CODPROD | NUMBER(22) | PK | N | Codigo do produto |
| DESCRPROD | VARCHAR2(120) | - | N | Descricao do produto |
| COMPLDESC | VARCHAR2(100) | - | Y | Complemento da descricao |
| REFERENCIA | VARCHAR2(15) | - | Y | Codigo de referencia |
| CODGRUPOPROD | NUMBER(22) | FK | N | Grupo do produto |
| CODVOL | VARCHAR2(6) | FK | N | Unidade de medida |
| MARCA | VARCHAR2(20) | - | Y | Marca do produto |
| ATIVO | VARCHAR2(1) | - | N | Produto ativo (S/N) |
| USOPROD | VARCHAR2(1) | - | Y | Uso do produto |
| NCM | VARCHAR2(10) | - | Y | Codigo NCM fiscal |

## Campos de Peso e Dimensoes

| Campo | Tipo | Descricao |
|-------|------|-----------|
| PESOBRUTO | FLOAT(22) | Peso bruto |
| PESOLIQ | FLOAT(22) | Peso liquido |
| ALTURA | FLOAT(22) | Altura |
| LARGURA | FLOAT(22) | Largura |
| ESPESSURA | FLOAT(22) | Espessura |
| M3 | FLOAT(22) | Cubagem (metros cubicos) |
| UNIDADE | VARCHAR2(2) | Unidade das dimensoes |

## Campos de Preco e Custo

| Campo | Tipo | Descricao |
|-------|------|-----------|
| CODTAB | NUMBER(22) | Tabela de precos |
| CODFORMPREC | NUMBER(22) | Formula de precificacao |
| MARGLUCRO | FLOAT(22) | Margem de lucro |
| DESCMAX | FLOAT(22) | Desconto maximo permitido |
| DECCUSTO | NUMBER(22) | Decimais no custo |
| DECVLR | NUMBER(22) | Decimais no valor |

## Campos de Estoque

| Campo | Tipo | Descricao |
|-------|------|-----------|
| ESTMIN | FLOAT(22) | Estoque minimo |
| ESTMAX | FLOAT(22) | Estoque maximo |
| ESTSEGQTD | FLOAT(22) | Estoque de seguranca |
| ESTSEGDIAS | NUMBER(22) | Dias de estoque seguranca |
| LOCALIZACAO | VARCHAR2(15) | Localizacao no deposito |
| CODLOCALPADRAO | NUMBER(22) | Local padrao de estoque |
| MULTIPVENDA | FLOAT(22) | Multiplo de venda |
| AGRUPMIN | FLOAT(22) | Agrupamento minimo |
| LEADTIME | NUMBER(22) | Lead time de reposicao |

## Campos Fiscais

| Campo | Tipo | Descricao |
|-------|------|-----------|
| NCM | VARCHAR2(10) | Codigo NCM |
| CODIPI | NUMBER(22) | Codigo IPI |
| TEMICMS | VARCHAR2(1) | Tem ICMS (S/N) |
| TEMISS | VARCHAR2(1) | Tem ISS (S/N) |
| TEMIPIVENDA | VARCHAR2(1) | Tem IPI na venda |
| TEMIPICOMPRA | VARCHAR2(1) | Tem IPI na compra |
| ORIGPROD | VARCHAR2(1) | Origem do produto |
| GRUPOICMS | NUMBER(22) | Grupo tributacao ICMS |
| GRUPOPIS | VARCHAR2(30) | Grupo tributacao PIS |
| GRUPOCOFINS | VARCHAR2(30) | Grupo tributacao COFINS |

## Campos de Controle

| Campo | Tipo | Descricao |
|-------|------|-----------|
| DTALTER | DATE | Data ultima alteracao |
| CODUSU | NUMBER(22) | Usuario que alterou |
| CODMOEDA | NUMBER(22) | Moeda |
| USALOCAL | VARCHAR2(1) | Usa controle por local |
| UTILIZAWMS | VARCHAR2(1) | Usa WMS |

## Campos de Lote/Serie

| Campo | Tipo | Descricao |
|-------|------|-----------|
| IMPLAUDOLOTE | VARCHAR2(1) | Implementa laudo de lote |
| USASTATUSLOTE | VARCHAR2(1) | Usa status de lote |
| TAMLOTE | NUMBER(22) | Tamanho do lote |
| TAMSERIE | NUMBER(22) | Tamanho da serie |
| TEMRASTROLOTE | CHAR(1) | Tem rastreabilidade lote |
| PRAZOVAL | NUMBER(22) | Prazo de validade |
| SHELFLIFE | NUMBER(22) | Vida util (shelf life) |

## Relacionamentos (FKs)

| Campo | Tabela Ref | Campo Ref | Descricao |
|-------|------------|-----------|-----------|
| CODGRUPOPROD | TGFGRU | CODGRUPOPROD | Grupo de produtos |
| CODVOL | TGFVOL | CODVOL | Unidade de medida |
| CODIPI | TGFIPI | CODIPI | Tabela IPI |
| CODTAB | TGFNTA | CODTAB | Tabela de precos |
| CODCTACTB | TCBPLA | CODCTACTB | Conta contabil |
| CODNAT | TGFNAT | CODNAT | Natureza financeira |
| CODCENCUS | TSICUS | CODCENCUS | Centro de custo |
| CODPROJ | TCSPRJ | CODPROJ | Projeto |
| CODPARCFORN | TGFPAR | CODPARC | Fornecedor padrao |
| CODFAB | TGFPAR | CODPARC | Fabricante |
| CODMOEDA | TSIMOE | CODMOEDA | Moeda |
| CODPAIS | TSIPAI | CODPAIS | Pais de origem |
| CODLOCALPADRAO | TGFLOC | CODLOCAL | Local de estoque padrao |
| CODMARCA | TGFMAR | CODIGO | Marca |
| CODAREASEP | TGWARS | CODAREASEP | Area de separacao WMS |

## Valores de Dominio

| Campo | Valor | Qtd | Significado |
|-------|-------|-----|-------------|
| USOPROD | 'R' | 386.620 | Revenda |
| USOPROD | 'C' | 6.832 | Consumo |
| USOPROD | 'S' | 227 | Servico |
| USOPROD | 'M' | 15 | Materia-prima |
| USOPROD | 'V' | 2 | Veiculo |
| ATIVO | 'S' | 393.624 | Ativo |
| ATIVO | 'N' | 72 | Inativo |
| TEMICMS | 'S' | 393.216 | Tem ICMS |
| TEMICMS | 'N' | 480 | Nao tem ICMS |

## Principais Grupos de Produto (CODGRUPOPROD)

| Codigo | Qtd Produtos | Descricao Provavel |
|--------|--------------|-------------------|
| 0 | 198.716 | Sem grupo definido |
| 20299 | 64.626 | Grupo generico |
| 10109 | 16.480 | - |
| 10101 | 14.372 | - |
| 10102 | 13.955 | - |
| 11301 | 7.854 | - |
| 10401 | 7.029 | - |

## Principais Marcas

| Marca | Qtd Produtos |
|-------|--------------|
| CUMMINS | 44.655 |
| MWM | 15.664 |
| ZF DO BRASIL | 13.884 |
| EATON | 10.835 |
| FPT | 10.359 |
| VW | 7.251 |
| MERCEDES BENZ | 6.920 |
| LNG | 6.707 |
| PATRAL | 6.628 |
| DONALDSON | 5.764 |

## Produtos Especiais

| CODPROD | DESCRPROD | Uso |
|---------|-----------|-----|
| 0 | <SEM DESCRICAO> | Registro padrao |
| 100100 | INDUSTRIALIZACAO EM TERCEIROS | Servicos |

## Campos Customizados MMarra (AD_*)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| AD_NUMFABRICANTE | VARCHAR2(100) | Numero do fabricante |
| AD_NUMORIGINAL | VARCHAR2(100) | Numero original |
| AD_LINHA | VARCHAR2(10) | Linha do produto |
| AD_DESCRPRODDEPLOY | VARCHAR2(120) | Descricao para deploy |
| AD_NUMAUX | VARCHAR2(4000) | Numeros auxiliares |
| AD_GRUPOICMSPROD | NUMBER(22) | Grupo ICMS customizado |
| AD_IDEXTERNO | VARCHAR2(100) | ID externo (integracoes) |

## Observacoes

- 98% dos produtos sao para revenda (USOPROD = 'R')
- Quase metade (50%) dos produtos nao tem grupo definido
- Marcas automotivas dominam o cadastro (Cummins, MWM, ZF, Eaton)
- NCM eh obrigatorio para operacoes fiscais
- Campos de estoque (ESTMIN, ESTMAX) usados para MRP
- WMS controlado pelo campo UTILIZAWMS

## Queries Relacionadas

- Buscar produto: `SELECT * FROM TGFPRO WHERE CODPROD = ?`
- Buscar por referencia: `SELECT * FROM TGFPRO WHERE REFERENCIA = ?`
- Produtos por marca: `SELECT * FROM TGFPRO WHERE MARCA = ? AND ATIVO = 'S'`
- Produtos com estoque baixo: Requer join com TGFEST
