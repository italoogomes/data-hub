# TGFVEN

**Descricao:** Cadastro de Vendedores - armazena informacoes de vendedores, compradores e gerentes comerciais, incluindo comissoes, metas e hierarquia.

**Total de registros:** 111 vendedores

## Chave Primaria

| Campo | Tipo | Descricao |
|-------|------|-----------|
| CODVEND | NUMBER(22) | Codigo do vendedor |

## Campos de Identificacao

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| CODVEND | NUMBER(22) | N | Codigo do vendedor |
| APELIDO | VARCHAR2(30) | N | Nome/apelido do vendedor |
| TIPVEND | VARCHAR2(1) | Y | Tipo de vendedor (V/C/G) |
| CODPARC | NUMBER(22) | N | Parceiro associado |
| ATIVO | VARCHAR2(1) | N | Vendedor ativo (S/N) |
| EMAIL | VARCHAR2(80) | Y | E-mail do vendedor |

## Campos de Hierarquia

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| CODGER | NUMBER(22) | N | Codigo do gerente (outro vendedor) |
| CODREG | NUMBER(22) | N | Codigo da regiao |
| CODEMP | NUMBER(22) | Y | Empresa do vendedor |

## Campos de Comissao

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| COMVENDA | FLOAT | Y | Percentual comissao venda |
| COMGER | FLOAT | Y | Percentual comissao gerencia |
| COMISSAO2 | FLOAT | Y | Comissao secundaria |
| CODFORM | NUMBER(22) | N | Formula de comissao |
| CODFORMFLEX | NUMBER(22) | Y | Formula flex de comissao |
| TIPCALC | VARCHAR2(1) | N | Tipo de calculo comissao |
| TIPFECHCOM | CHAR(1) | N | Tipo fechamento comissao |
| DIACOM | NUMBER(22) | Y | Dia do mes para comissao |

## Campos de Limites

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| DESCMAX | FLOAT | Y | Desconto maximo permitido (%) |
| ACRESCMAX | FLOAT | Y | Acrescimo maximo permitido (%) |
| PERCTROCA | FLOAT | N | Percentual troca |
| SALDODISP | FLOAT | N | Saldo disponivel |
| PROVACRESC | FLOAT | N | Provisao acrescimo |

## Campos de Meta

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| PARTICMETA | FLOAT | Y | Participacao meta |
| PERCCUSVAR | FLOAT | Y | Percentual custo variavel |

## Campos de Controle

| Campo | Tipo | Nulo | Descricao |
|-------|------|------|-----------|
| DTALTER | DATE | N | Data ultima alteracao |
| CODUSU | NUMBER(22) | Y | Usuario ultima alteracao |
| NUVERSAO | NUMBER(22) | Y | Numero versao |
| SENHA | NUMBER(22) | Y | Senha acesso |
| CODCARGAHOR | NUMBER(22) | N | Carga horaria |
| CODCENCUSPAD | NUMBER(22) | N | Centro de custo padrao |
| VLRHORA | FLOAT | Y | Valor hora |

## Campos Customizados MMarra (AD_*)

| Campo | Tipo | Descricao |
|-------|------|-----------|
| AD_IDEXTERNO | VARCHAR2(100) | ID externo integracao |
| AD_ID_EXTERNO_CODEMP | VARCHAR2(100) | ID externo por empresa |
| AD_CODUSU | NUMBER(22) | Usuario MMarra |
| AD_CODUNG | NUMBER(22) | Unidade negocio |

## Valores de Dominio - TIPVEND (Tipo de Vendedor)

| Valor | Qtd | Descricao |
|-------|-----|-----------|
| V | 86 | Vendedor |
| C | 20 | Comprador |
| G | 4 | Gerente |
| null | 1 | Nao definido |

## Relacionamentos (FKs)

| Campo | Tabela Ref | Campo Ref | Descricao |
|-------|------------|-----------|-----------|
| CODGER | TGFVEN | CODVEND | Gerente (auto-referencia) |
| CODREG | TSIREG | CODREG | Regiao de atuacao |
| CODEMP | TGFEMP | CODEMP | Empresa |
| CODFORM | TGFFOC | CODFORM | Formula comissao |
| CODFORMFLEX | TGFFDM | CODFORM | Formula flex |
| CODCENCUSPAD | TSICUS | CODCENCUS | Centro de custo |
| CODUSU | TSIUSU | CODUSU | Usuario alteracao |
| AD_CODUNG | TMIUNG | CODUNG | Unidade negocio (customizado) |
| AD_CODUSU | TSIUSU | CODUSU | Usuario MMarra |

## Vendedores Mais Ativos (Vendas)

| CODVEND | Nome | Qtd Notas | Valor Total |
|---------|------|-----------|-------------|
| **0** | SEM VENDEDOR | 241.416 | R$ 406,2M |
| **32** | LICIANE | 953 | R$ 1,0M |
| **21** | LEONARDO ZUELI | 917 | R$ 287k |
| **37** | VALERIO | 727 | R$ 1,0M |
| **42** | ROGERIO FERNANDES | 365 | R$ 371k |
| **36** | VALDICE | 315 | R$ 704k |
| **33** | MIRAO SILVA | 308 | R$ 229k |
| **23** | MATHEUS SILVA | 246 | R$ 378k |
| **38** | CLEVERTON | 238 | R$ 249k |
| **22** | LUIZ PAULO TAVARES | 227 | R$ 258k |

**Observacao:** 70% das notas de venda (241k) estao sem vendedor associado (CODVEND=0).

## Hierarquia de Gerentes

| CODGER | Gerente | Qtd Vendedores |
|--------|---------|----------------|
| 0 | Sem gerente | 62 |
| 26 | PAULO TEIXEIRA | 20 |
| 45 | FYLIPPE VELOSO | 8 |
| 32 | LICIANE | 8 |
| 51 | ALESSANDRO CALDEIRA | 5 |
| 86 | PEDRO CORREIA | 3 |
| 2 | CARLOS H MARRA | 3 |
| 96 | FERNANDO CARRETA | 1 |
| 71 | MURILO RIBEIRO | 1 |

## Gerentes (TIPVEND = G)

| CODVEND | Nome | Email |
|---------|------|-------|
| 1 | CARLOS MARRA | carlosmarra@mmarra.com.br |
| 10 | LARISSA MARRA | Larissa@mmarra.com.br |
| 26 | PAULO TEIXEIRA | - |

## Compradores (TIPVEND = C)

| CODVEND | Nome | Empresa |
|---------|------|---------|
| 3 | JULIANO MARCHEZAM | Emp 1 |
| 4 | BRUNO JERONIMO | Emp 1 |
| 5 | JULIANO NOVAES | Emp 1 |
| 6 | FELIPE PEREIRA | Emp 1 |
| 7 | NEVES | Emp 1 |
| 8 | GUILHERME TRINDADE | Emp 1 |
| 9 | PAULO BOVO | Emp 1 |
| 11 | LARISSA FERREIRA | Emp 1 |
| 12 | LARISSA CANDIDO | Emp 1 |
| 56 | EDUARDO PUTINATTO | - |
| 99 | CARLOS ALBERTO | - |

## Como Usar

### Listar vendedores ativos
```sql
SELECT CODVEND, APELIDO, TIPVEND, EMAIL
FROM TGFVEN
WHERE ATIVO = 'S'
ORDER BY APELIDO
```

### Vendedores por gerente
```sql
SELECT G.APELIDO AS GERENTE, V.CODVEND, V.APELIDO AS VENDEDOR
FROM TGFVEN V
LEFT JOIN TGFVEN G ON V.CODGER = G.CODVEND
WHERE V.TIPVEND = 'V'
  AND V.ATIVO = 'S'
ORDER BY G.APELIDO, V.APELIDO
```

### Performance de vendedores
```sql
SELECT V.CODVEND, V.APELIDO,
       COUNT(*) AS QTD_VENDAS,
       SUM(C.VLRNOTA) AS VLR_TOTAL,
       AVG(C.VLRNOTA) AS TICKET_MEDIO
FROM TGFCAB C
JOIN TGFVEN V ON C.CODVEND = V.CODVEND
WHERE C.TIPMOV = 'V'
  AND V.CODVEND > 0
GROUP BY V.CODVEND, V.APELIDO
ORDER BY VLR_TOTAL DESC
```

### Vendedores com comissao configurada
```sql
SELECT CODVEND, APELIDO, COMVENDA, COMGER, DESCMAX
FROM TGFVEN
WHERE COMVENDA > 0
   OR COMGER > 0
ORDER BY CODVEND
```

## Observacoes

- CODVEND 0 eh reservado para "SEM VENDEDOR" - usado quando nota nao tem vendedor associado
- 70% das notas de venda estao sem vendedor - indica que vendedor nao eh obrigatorio na operacao
- TIPVEND diferencia vendedor (V), comprador (C) e gerente (G)
- Compradores sao usados para notas de compra, vendedores para notas de venda
- Gerentes podem ter vendedores subordinados via CODGER
- DESCMAX e ACRESCMAX definem limites de negociacao do vendedor
- COMVENDA e COMGER definem percentuais de comissao
- Vendedor pode estar associado a um parceiro (CODPARC) e uma empresa (CODEMP)
- Equipe de vendas eh pequena (~90 vendedores ativos) comparado ao volume de operacao
- Top vendedor (LICIANE) representa menos de 1% das notas de venda

## Uso nas Outras Tabelas

A TGFVEN eh referenciada em:
- **TGFCAB.CODVEND** - Vendedor da nota/pedido
- **TGFPAR.CODVEND** - Vendedor padrao do parceiro
- **TGFCOM.CODVEND** - Comissoes calculadas
