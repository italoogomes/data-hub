# TSIEMP

**Descricao:** Cadastro de Empresas/Filiais - armazena informacoes das empresas e filiais do grupo, incluindo dados fiscais, endereco, configuracoes de modulos e SMTP.

**Total de registros:** 10 empresas/filiais

## Chave Primaria

| Campo | Tipo | Descricao |
|-------|------|-----------|
| CODEMP | NUMBER(22) | Codigo da empresa |

## Campos de Identificacao

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| CODEMP | NUMBER(22) | N | Codigo da empresa |
| NOMEFANTASIA | VARCHAR2(40) | Y | Nome fantasia |
| RAZAOSOCIAL | VARCHAR2(40) | Y | Razao social |
| RAZAOABREV | VARCHAR2(15) | N | Razao social abreviada |
| RAZAOSOCIALCOMPLETA | VARCHAR2(250) | Y | Razao social completa |
| CODEMPMATRIZ | NUMBER(22) | Y | Codigo da empresa matriz |

## Campos de Endereco

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| CODEND | NUMBER(22) | Y | Codigo do endereco (logradouro) |
| NUMEND | VARCHAR2(6) | Y | Numero do endereco |
| COMPLEMENTO | VARCHAR2(10) | Y | Complemento |
| CODBAI | NUMBER(22) | N | Codigo do bairro |
| CODCID | NUMBER(22) | Y | Codigo da cidade |
| CEP | VARCHAR2(8) | Y | CEP |
| LATITUDE | VARCHAR2(255) | Y | Latitude (geolocalizacao) |
| LONGITUDE | VARCHAR2(255) | Y | Longitude (geolocalizacao) |

## Campos de Contato

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| TELEFONE | VARCHAR2(13) | Y | Telefone principal |
| FAX | VARCHAR2(13) | Y | Fax |
| TELEX | VARCHAR2(12) | Y | Telex (legado) |
| EMAIL | VARCHAR2(80) | Y | E-mail |
| HOMEPAGE | VARCHAR2(255) | Y | Site |
| PRINCTITULAR | VARCHAR2(40) | Y | Principal titular |
| CPFRESP | VARCHAR2(11) | Y | CPF do responsavel |

## Campos Fiscais

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| CGC | VARCHAR2(14) | Y | CNPJ |
| INSCESTAD | VARCHAR2(16) | Y | Inscricao estadual |
| INSCMUN | VARCHAR2(16) | Y | Inscricao municipal |
| CODMUN | NUMBER(22) | Y | Codigo municipio IBGE |
| CODREGTRIB | NUMBER(22) | Y | Codigo regime tributario |
| SIMPLES | VARCHAR2(1) | Y | Optante Simples (S/N) |
| TIPOSN | NUMBER(22) | Y | Tipo Simples Nacional |
| CLASSTRIB | NUMBER(22) | Y | Classificacao tributaria |
| CNAEPREPON | NUMBER(22) | Y | CNAE preponderante |
| NATESTAB | NUMBER(22) | Y | Natureza estabelecimento |
| NATJUR | NUMBER(22) | Y | Natureza juridica |
| RAMOATIV | VARCHAR2(40) | Y | Ramo de atividade |
| ATIVECON | NUMBER(22) | Y | Atividade economica |
| REGJUNTACOM | VARCHAR2(12) | Y | Registro junta comercial |
| DTREGJUNTA | DATE | Y | Data registro junta |
| REGESPTRIBUT | VARCHAR2(2) | Y | Regime especial tributacao |
| RNTRC | VARCHAR2(8) | Y | RNTRC (transporte) |
| PRODUTORRURAL | VARCHAR2(1) | Y | Produtor rural (S/N) |

## Campos de Configuracao de Modulos

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| FINANCEIRO | VARCHAR2(1) | N | Usa modulo financeiro (S/N) |
| ESTOQUE | VARCHAR2(1) | N | Usa modulo estoque (S/N) |
| CARGAS | VARCHAR2(1) | N | Usa modulo cargas (S/N) |
| COMISSOES | VARCHAR2(1) | N | Usa modulo comissoes (S/N) |
| PRODUCAO | VARCHAR2(1) | N | Usa modulo producao (S/N) |
| SUPDECISAO | VARCHAR2(1) | N | Usa suporte decisao (S/N) |
| LIVROSFISCAIS | VARCHAR2(1) | N | Usa livros fiscais (S/N) |
| CONTABILIDADE | DATE | Y | Data inicio contabilidade |
| FOLHAPAGTO | VARCHAR2(1) | N | Usa folha pagamento (S/N) |

## Campos de Configuracao SMTP (E-mail)

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| SERVIDORSMTP | VARCHAR2(80) | Y | Servidor SMTP |
| TIPOSMTP | CHAR(1) | N | Tipo SMTP |
| USUARIOSMTP | VARCHAR2(80) | Y | Usuario SMTP |
| SENHASMTP | VARCHAR2(80) | Y | Senha SMTP |
| PORTASMTP | NUMBER(22) | N | Porta SMTP |
| SEGURANCASMTP | CHAR(1) | N | Seguranca SMTP (SSL/TLS) |

## Campos de NFSe

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| TIPTRANSMNFSE | VARCHAR2(1) | N | Tipo transmissao NFSe |
| EXIGEISSQN | VARCHAR2(2) | Y | Exige ISSQN |
| CNPJPREFEITURA | VARCHAR2(14) | Y | CNPJ prefeitura (NFSe) |

## Campos de Controle

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| CODUSU | NUMBER(22) | Y | Usuario ultima alteracao |
| DHALTER | DATE | N | Data/hora ultima alteracao |
| NUVERSAO | NUMBER(22) | Y | Numero versao |
| LOGOMARCA | BLOB | Y | Logomarca da empresa |
| COREMPRESA | NUMBER(22) | Y | Cor identificadora |

## Relacionamentos (FKs)

| Campo | Tabela Ref | Campo Ref | Descricao |
|-------|------------|-----------|-----------|
| CODBAI | TSIBAI | CODBAI | Bairro |
| CODCID | TSICID | CODCID | Cidade |
| CODEND | TSIEND | CODEND | Endereco (logradouro) |
| CODEMPMATRIZ | TSIEMP | CODEMP | Empresa matriz (auto-ref) |
| CODPARC | TGFPAR | CODPARC | Parceiro correspondente |
| CODPARCDIV | TGFPAR | CODPARC | Parceiro diverso |
| CODPARCRESP | TGFPAR | CODPARC | Parceiro responsavel |
| CODPARCEMPSOFT | TGFPAR | CODPARC | Parceiro software |
| CODUSU | TSIUSU | CODUSU | Usuario alteracao |

## Empresas MMarra Cadastradas

| CODEMP | Nome Fantasia | UF | Tipo |
|--------|---------------|----|----- |
| 1 | MMARRA - RIBEIRAO PRETO (SP) | SP | Matriz |
| 2 | MMARRA - UBERLANDIA (MG) | MG | Filial |
| 4 | MMARRA - ARACATUBA (SP) | SP | Filial |
| 5 | MMARRA - SERVICE ARACATUBA (SP) | SP | Service |
| 6 | MMARRA - SERVICE RIBEIRAO PRETO (SP) | SP | Service |
| 7 | MMARRA - ITUMBIARA (GO) | GO | Filial |
| 8 | MMARRA - RIO VERDE (GO) | GO | Filial |
| 9 | MMARRA - VAREJO RIBEIRAO PRETO (SP) | SP | Varejo |
| 16 | MMARRA - ARACATUBA (SP) INATIVO | SP | Inativo |
| 999 | MMARRA CONSOLIDADA | - | Consolidacao |

## Volume por Empresa (Notas Fiscais)

| CODEMP | Nome | Qtd Notas | Valor Total |
|--------|------|-----------|-------------|
| **1** | MMARRA - RIBEIRAO PRETO (SP) | 181.366 | R$ 343,9M |
| **7** | MMARRA - ITUMBIARA (GO) | 85.380 | R$ 295,2M |
| **2** | MMARRA - UBERLANDIA (MG) | 38.288 | R$ 44,9M |
| **4** | MMARRA - ARACATUBA (SP) | 23.934 | R$ 40,8M |
| **6** | MMARRA - SERVICE RIBEIRAO PRETO (SP) | 9.275 | R$ 52,6M |
| **8** | MMARRA - RIO VERDE (GO) | 4.743 | R$ 6,7M |
| **16** | MMARRA - ARACATUBA (SP) INATIVO | 262 | R$ 934k |
| **5** | MMARRA - SERVICE ARACATUBA (SP) | 14 | R$ 8,6k |
| **9** | MMARRA - VAREJO RIBEIRAO PRETO (SP) | 1 | R$ 0 |

**Total geral:** ~343.000 notas | ~R$ 785M

## Estrutura do Grupo

```
MMARRA CONSOLIDADA (999) - Para relatorios consolidados
│
└── MMARRA - RIBEIRAO PRETO (1) - MATRIZ
    ├── MMARRA - UBERLANDIA (2) - MG
    ├── MMARRA - ARACATUBA (4) - SP
    ├── MMARRA - SERVICE ARACATUBA (5) - SP
    ├── MMARRA - SERVICE RIBEIRAO PRETO (6) - SP
    ├── MMARRA - ITUMBIARA (7) - GO
    ├── MMARRA - RIO VERDE (8) - GO
    ├── MMARRA - VAREJO RIBEIRAO PRETO (9) - SP
    └── MMARRA - ARACATUBA INATIVO (16) - SP
```

## Como Usar

### Listar todas as empresas
```sql
SELECT CODEMP, NOMEFANTASIA, RAZAOSOCIAL, CGC
FROM TSIEMP
ORDER BY CODEMP
```

### Empresas ativas (excluindo consolidacao)
```sql
SELECT CODEMP, NOMEFANTASIA
FROM TSIEMP
WHERE CODEMP < 999
ORDER BY CODEMP
```

### Volume por empresa
```sql
SELECT E.CODEMP, E.NOMEFANTASIA,
       COUNT(*) AS QTD_NOTAS,
       SUM(C.VLRNOTA) AS VLR_TOTAL
FROM TGFCAB C
JOIN TSIEMP E ON C.CODEMP = E.CODEMP
GROUP BY E.CODEMP, E.NOMEFANTASIA
ORDER BY QTD_NOTAS DESC
```

### Empresas por estado
```sql
SELECT E.CODEMP, E.NOMEFANTASIA, C.UF
FROM TSIEMP E
JOIN TSICID C ON E.CODCID = C.CODCID
ORDER BY C.UF, E.CODEMP
```

## Observacoes

- CODEMP 1 eh a matriz (RIBEIRAO PRETO) - todas as outras filiais apontam para ela via CODEMPMATRIZ
- CODEMP 999 eh uma empresa virtual para consolidacao de relatorios
- CODEMP 16 esta marcado como INATIVO no nome fantasia
- Todas as empresas pertencem ao mesmo CNPJ base (67380170) com filiais diferentes
- Os campos de modulos (FINANCEIRO, ESTOQUE, etc) estao todos com 'N' - configuracao especifica
- A maior operacao eh em RIBEIRAO PRETO (53% das notas, 44% do valor)
- ITUMBIARA tem alto valor medio por nota (R$ 3.456 vs R$ 1.896 de Ribeirao)
- SERVICE sao unidades de servico tecnico
- VAREJO eh unidade de venda direta ao consumidor

## Uso nas Outras Tabelas

A TSIEMP eh referenciada em praticamente todas as tabelas operacionais:
- **TGFCAB.CODEMP** - Empresa da nota/pedido
- **TGFPAR.CODEMP** - Empresa do cadastro do parceiro
- **TGFPRO.CODEMP** - Empresa do cadastro do produto (se multi-empresa)
- **TGFEST.CODEMP** - Empresa do estoque
- **TGFFIN.CODEMP** - Empresa do titulo financeiro
