# TGFPAR

**Descricao:** Cadastro de Parceiros - armazena todos os parceiros de negocio (clientes, fornecedores, transportadoras, vendedores, etc.)

**Total de registros:** 57.121

## Campos Principais

| Campo | Tipo | PK/FK | Nulo | Descricao |
|-------|------|-------|------|-----------|
| CODPARC | NUMBER(22) | PK | N | Codigo do parceiro |
| NOMEPARC | VARCHAR2(100) | - | N | Nome/razao social resumida |
| RAZAOSOCIAL | VARCHAR2(100) | - | Y | Razao social completa |
| CGC_CPF | VARCHAR2(14) | - | Y | CNPJ ou CPF |
| TIPPESSOA | VARCHAR2(1) | - | N | Tipo pessoa (F/J) |
| CODVEND | NUMBER(22) | FK | N | Vendedor responsavel |
| CLIENTE | VARCHAR2(1) | - | N | Eh cliente (S/N) |
| FORNECEDOR | VARCHAR2(1) | - | N | Eh fornecedor (S/N) |
| TRANSPORTADORA | VARCHAR2(1) | - | N | Eh transportadora (S/N) |
| VENDEDOR | VARCHAR2(1) | - | N | Eh vendedor (S/N) |
| ATIVO | VARCHAR2(1) | - | N | Cadastro ativo (S/N) |
| BLOQUEAR | VARCHAR2(1) | - | N | Bloqueado para operacoes |
| LIMCRED | FLOAT(22) | - | Y | Limite de credito |
| CODTIPPARC | NUMBER(22) | FK | N | Tipo de parceiro |

## Campos de Endereco

| Campo | Tipo | FK | Descricao |
|-------|------|----|-----------|
| CODEND | NUMBER(22) | TSIEND.CODEND | Codigo endereco (logradouro) |
| NUMEND | VARCHAR2(6) | - | Numero do endereco |
| COMPLEMENTO | VARCHAR2(30) | - | Complemento |
| CODBAI | NUMBER(22) | TSIBAI.CODBAI | Codigo do bairro |
| CODCID | NUMBER(22) | TSICID.CODCID | Codigo da cidade |
| CODREG | NUMBER(22) | TSIREG.CODREG | Codigo da regiao |
| CEP | VARCHAR2(8) | - | CEP |
| LATITUDE | VARCHAR2(255) | - | Latitude GPS |
| LONGITUDE | VARCHAR2(255) | - | Longitude GPS |

## Campos de Contato

| Campo | Tipo | Descricao |
|-------|------|-----------|
| TELEFONE | VARCHAR2(13) | Telefone principal |
| FAX | VARCHAR2(13) | Fax |
| EMAIL | VARCHAR2(80) | Email principal |
| EMAILNFE | VARCHAR2(255) | Email para NFe |
| EMAILNFSE | VARCHAR2(255) | Email para NFSe |
| HOMEPAGE | VARCHAR2(255) | Site |

## Campos Fiscais

| Campo | Tipo | Descricao |
|-------|------|-----------|
| IDENTINSCESTAD | VARCHAR2(16) | Inscricao estadual |
| INSCMUN | VARCHAR2(16) | Inscricao municipal |
| CNAE | VARCHAR2(10) | Codigo CNAE |
| SIMPLES | VARCHAR2(1) | Optante Simples Nacional |
| REGAPUR | VARCHAR2(50) | Regime de apuracao |

## Campos Financeiros

| Campo | Tipo | Descricao |
|-------|------|-----------|
| LIMCRED | FLOAT(22) | Limite de credito |
| LIMCREDMENSAL | FLOAT(22) | Limite de credito mensal |
| CODTAB | NUMBER(22) | Tabela de precos padrao |
| PRAZOPAG | NUMBER(22) | Prazo de pagamento |
| TOLERINADIMP | NUMBER(22) | Tolerancia de inadimplencia |
| PERCJURO | FLOAT(22) | Percentual de juros |
| PERCMULTA | FLOAT(22) | Percentual de multa |
| CHAVEPIX | VARCHAR2(77) | Chave PIX |

## Campos de Controle

| Campo | Tipo | Descricao |
|-------|------|-----------|
| DTCAD | DATE | Data de cadastro |
| DTALTER | DATE | Data ultima alteracao |
| CODUSU | NUMBER(22) | Usuario que alterou |
| MOTBLOQ | VARCHAR2(4000) | Motivo do bloqueio |

## Relacionamentos (FKs)

| Campo | Tabela Ref | Campo Ref | Descricao |
|-------|------------|-----------|-----------|
| CODVEND | TGFVEN | CODVEND | Vendedor responsavel |
| CODASSESSOR | TGFVEN | CODVEND | Assessor comercial |
| CODBAI | TSIBAI | CODBAI | Bairro |
| CODCID | TSICID | CODCID | Cidade |
| CODREG | TSIREG | CODREG | Regiao |
| CODEND | TSIEND | CODEND | Endereco |
| CODBCO | TSIBCO | CODBCO | Banco |
| CODTIPPARC | TGFTPP | CODTIPPARC | Tipo de parceiro |
| CODTAB | TGFNTA | CODTAB | Tabela de precos |
| CODEMP | TSIEMP | CODEMP | Empresa |
| CODPARCMATRIZ | TGFPAR | CODPARC | Parceiro matriz |
| CODPARCGRUECONOMICO | TGFPAR | CODPARC | Grupo economico |
| CODROTA | TGFROT | CODROTA | Rota de entrega |
| CODGRUPO | TGFGCB | CODGRUPO | Grupo de parceiros |

## Valores de Dominio

| Campo | Valor | Qtd | Significado |
|-------|-------|-----|-------------|
| TIPPESSOA | 'J' | 31.293 | Pessoa Juridica |
| TIPPESSOA | 'F' | 25.828 | Pessoa Fisica |
| CLIENTE | 'S' | 54.810 | Eh cliente |
| CLIENTE | 'N' | 2.311 | Nao eh cliente |
| FORNECEDOR | 'S' | 47.195 | Eh fornecedor |
| FORNECEDOR | 'N' | 9.926 | Nao eh fornecedor |
| TRANSPORTADORA | 'S' | 999 | Eh transportadora |
| TRANSPORTADORA | 'N' | 56.122 | Nao eh transportadora |
| VENDEDOR | 'S' | 1 | Eh vendedor |
| VENDEDOR | 'N' | 57.120 | Nao eh vendedor |
| ATIVO | 'S' | 57.116 | Ativo |
| ATIVO | 'N' | 5 | Inativo |

## Parceiros Especiais

| CODPARC | NOMEPARC | Uso |
|---------|----------|-----|
| 0 | SEM PARCEIRO | Registro padrao para operacoes sem parceiro |
| 1 | MMARRA RIBEIRAO PRETO SP | Empresa principal |
| 101 | CONSUMIDOR PADRAO | Vendas balcao/PDV |

## Observacoes

- Um mesmo parceiro pode ter multiplos papeis (cliente E fornecedor, por exemplo)
- Campo BLOQUEAR impede operacoes de venda/compra
- LIMCRED controla liberacao automatica de pedidos
- Campos AD_* sao customizacoes da MMarra
- 96% dos parceiros sao clientes
- 55% sao pessoas juridicas

## Queries Relacionadas

- Ver cadastro: `SELECT * FROM TGFPAR WHERE CODPARC = ?`
- Buscar por CNPJ: `SELECT * FROM TGFPAR WHERE CGC_CPF = ?`
- Clientes ativos: `SELECT * FROM TGFPAR WHERE CLIENTE = 'S' AND ATIVO = 'S'`
