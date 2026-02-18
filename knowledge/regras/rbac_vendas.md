# RBAC — Regras de Visibilidade em Vendas

**Modulo:** Vendas / RBAC

---

## Perfis e visibilidade

| Perfil | O que ve |
|--------|---------|
| Admin / Diretor / TI | Tudo — todas as vendas, todos os vendedores, margem geral |
| Gerente | Vendas da equipe dele (team_codvends) |
| Vendedor | So as vendas dele (CODVEND = :codvend) |

---

## Regras por tipo de dado

### Vendas gerais (KPIs, faturamento)
- **Vendedor:** Filtra CODVEND = :codvend (so ve as dele)
- **Gerente:** Filtra CODVEND IN (:team_codvends) (ve a equipe)
- **Admin:** Sem filtro de vendedor

### Margem (AD_MARGEM)
- **Vendedor:** So ve a DELE. OBRIGATORIO filtrar CODVEND.
- **Gerente:** Ve da equipe.
- **Admin:** Ve tudo.

### Comissao (AD_VLRCOMINT, AD_ALIQCOMINT)
- **Vendedor:** So ve a DELE. OBRIGATORIO filtrar CODVEND.
- **Gerente/Admin:** Pode ver de todos.

### Ranking de vendedores
- **Vendedor:** Ve a posicao dele no ranking geral, MAS sem ver o valor dos outros.
- **Gerente:** Ve ranking completo da equipe.
- **Admin:** Ve ranking geral com valores.

### Rastreio de pedido
- **Vendedor:** So ve pedidos dele (CODVEND = :codvend).
- **Admin:** Ve qualquer pedido.

### Financeiro
- **Vendedor:** NAO ve financeiro (exceto comissao dele).
- **Gerente:** Acesso limitado.
- **Admin:** Acesso total.

---

## Como aplicar no SQL

```sql
-- Vendedor
AND C.CODVEND = :codvend

-- Gerente (equipe)
AND C.CODVEND IN (:team_codvends)

-- Admin (sem filtro)
-- nao adicionar filtro de CODVEND
```

---

## Identificacao do perfil

O perfil do usuario eh definido por:
- ADMIN_USERS no .env (lista de nomes admin, ex: ITALO)
- CODVEND do usuario logado (identifica vendedor/gerente)
- team_codvends (lista de vendedores sob gerente)
