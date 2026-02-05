# CLAUDE.md - MMarra Data Hub

> Repositório de dados inteligente. Leia TUDO antes de agir.

---

## REGRA ZERO

**NUNCA faça nada pela metade.** Termina o que começou. Documenta o que descobriu.

---

## ANTES DE QUALQUER TAREFA

1. Leia `PROGRESSO.md`
2. Pergunte o que o usuário quer fazer
3. Confirme ANTES de executar

---

## MAPA COMPLETO - ONDE COLOCAR CADA COISA

### 📊 ESTRUTURA DE TABELA (schema, campos, tipos)
```
knowledge/sankhya/tabelas/{TABELA}.md

Exemplo: knowledge/sankhya/tabelas/TGFCAB.md
```

### 🔄 PROCESSO DE NEGÓCIO (fluxos, etapas, como funciona)
```
knowledge/processos/{modulo}/{processo}.md

Módulos: compras, vendas, estoque, wms, financeiro, fiscal

Exemplo: knowledge/processos/estoque/empenho.md
         knowledge/processos/compras/recebimento.md
         knowledge/processos/wms/separacao.md
```

### 📖 TERMO/CONCEITO (o que significa algo no contexto MMarra)
```
knowledge/glossario/{termo}.md

Exemplo: knowledge/glossario/empenho.md
         knowledge/glossario/top.md
         knowledge/glossario/parceiro.md
```

### ⚖️ REGRA DE NEGÓCIO (quando acontece X, por que bloqueia Y)
```
knowledge/regras/{regra}.md

Exemplo: knowledge/regras/bloqueio_credito.md
         knowledge/regras/estoque_minimo.md
```

### ❌ ERRO/PROBLEMA CONHECIDO (por que falha, como resolver)
```
knowledge/erros/{descricao}.md

Exemplo: knowledge/erros/pedido_nao_empenhado.md
         knowledge/erros/nota_rejeitada_sefaz.md
```

### 🔍 QUERY SQL ÚTIL
```
queries/{modulo}/{descricao}.sql

Exemplo: queries/vendas/vendas_mes.sql
         queries/estoque/posicao_atual.sql
```

### ✅ QUALQUER PROGRESSO
```
PROGRESSO.md → Atualiza a seção "SESSÕES ANTERIORES"
```

---

## TEMPLATES

### Template: Tabela (knowledge/sankhya/tabelas/)

```markdown
# {TABELA}

**Descrição:** [O que armazena]

## Campos

| Campo | Tipo | PK/FK | Descrição |
|-------|------|-------|-----------|
| CAMPO | TIPO | PK/FK | Descrição |

## Relacionamentos

- `CAMPO` → `OUTRA_TABELA.CAMPO`

## Valores de Domínio

| Campo | Valor | Significado |
|-------|-------|-------------|
| TIPMOV | 'V' | Venda |

## Observações

- Notas importantes
```

### Template: Processo (knowledge/processos/)

```markdown
# {Nome do Processo}

**Módulo:** compras | vendas | estoque | wms | financeiro | fiscal

## Fluxo

1. Passo 1
2. Passo 2
3. Passo 3

## Tabelas Envolvidas

- TGFCAB - papel no processo
- TGFITE - papel no processo

## Campos Importantes

| Tabela.Campo | Papel no processo |
|--------------|-------------------|
| TGFCAB.STATUS | Indica se... |

## Quando Falha

- Situação 1: causa e solução
- Situação 2: causa e solução

## Queries Relacionadas

- `queries/modulo/query.sql`
```

### Template: Glossário (knowledge/glossario/)

```markdown
# {Termo}

**O que é:** Explicação simples

**No sistema:** Como aparece no Sankhya

**Tabelas relacionadas:** TABELA1, TABELA2

**Exemplo prático:** Situação real de uso
```

### Template: Regra (knowledge/regras/)

```markdown
# {Nome da Regra}

**Quando aplica:** Situação

**O que acontece:** Comportamento

**Tabelas/Campos:** Onde está configurado

**Como verificar:** Query ou caminho no sistema

**Exceções:** Casos que não aplica
```

### Template: Erro (knowledge/erros/)

```markdown
# {Descrição do Erro}

**Sintoma:** O que o usuário vê

**Causas possíveis:**
1. Causa 1
2. Causa 2

**Como diagnosticar:**
- Query ou verificação

**Como resolver:**
- Solução para cada causa

**Prevenção:** Como evitar
```

### Template: Query (queries/)

```sql
-- ================================================
-- Descrição: [O que faz]
-- Módulo: vendas | compras | estoque | etc
-- Tabelas: TABELA1, TABELA2
-- ================================================

SELECT ...
FROM ...
```

---

## ESTRUTURA DO PROJETO

```
mmarra-data-hub/
├── CLAUDE.md                   ← Este arquivo
├── PROGRESSO.md                ← Estado atual (SEMPRE atualizar)
│
├── knowledge/                  ← BASE DE CONHECIMENTO
│   ├── sankhya/tabelas/        ← Schema das tabelas
│   ├── processos/              ← Fluxos de negócio
│   │   ├── compras/
│   │   ├── vendas/
│   │   ├── estoque/
│   │   ├── wms/
│   │   ├── financeiro/
│   │   └── fiscal/
│   ├── glossario/              ← Termos e conceitos
│   ├── regras/                 ← Regras de negócio
│   └── erros/                  ← Problemas conhecidos
│
├── queries/                    ← SQLs úteis
│   ├── vendas/
│   ├── compras/
│   ├── estoque/
│   ├── financeiro/
│   ├── fiscal/
│   └── wms/
│
├── src/                        ← Código fonte
│   ├── mcp/                    ← MCP Server
│   ├── api/                    ← API da plataforma
│   └── utils/                  ← Utilitários
│
├── data/                       ← Dados
│   ├── raw/                    ← Brutos
│   └── processed/              ← Processados
│
└── output/                     ← Relatórios/exports
```

---

## CHECKLIST ANTES DE FINALIZAR

- [ ] Descobri tabela? → `knowledge/sankhya/tabelas/`
- [ ] Descobri processo? → `knowledge/processos/{modulo}/`
- [ ] Descobri termo novo? → `knowledge/glossario/`
- [ ] Descobri regra? → `knowledge/regras/`
- [ ] Encontrei erro comum? → `knowledge/erros/`
- [ ] Criei query útil? → `queries/{modulo}/`
- [ ] Atualizei `PROGRESSO.md`?

---

## OBJETIVO FINAL

Este repositório alimenta uma plataforma com:
1. **Dashboards** - Substituir Power BI
2. **LLM** - Chat que responde perguntas de negócio

A LLM precisa saber:
- Estrutura do banco (tabelas, campos)
- Processos (como funciona compra, venda, empenho)
- Glossário (o que significa cada termo)
- Regras (por que bloqueia, quando libera)
- Erros (por que falhou, como resolver)

**Quanto mais documentado, mais inteligente a LLM fica.**

---

*Versão 3.0 - Fevereiro 2026*
