# Rastreio de Pedido de Venda

**Modulo:** Vendas
**Intent:** rastreio_pedido (NOVO - a ser implementado)

**Descricao:** O vendedor quer rastrear o ciclo completo do pedido dele: vendeu → peça tem estoque? → foi comprada? → fornecedor entregou? → tá na conferência? → quando vai estar disponível?

---

## Filosofia

O vendedor NAO pensa em modulos. Ele pensa no **pedido dele**:

```
"Vendi pro cliente X → peça não tinha estoque → comprador fez pedido →
 fornecedor mandou? → tá na conferência? → quando vai tá disponível?"
```

O Data Hub precisa responder **qualquer ponto desse ciclo** com uma unica pergunta.

---

## Perguntas que o vendedor faz

| Pergunta | Dados necessarios |
|----------|-------------------|
| "status do meu pedido 5000" | TGFCAB.NUNOTA=5000 (cabecalho) |
| "meus pedidos pendentes" | PENDENTE='S', TIPMOV='P' |
| "a peça X do pedido já foi comprada?" | TGFVAR + compra vinculada |
| "já chegou a peça do pedido 5000?" | TGFVAR entregas |
| "tá na conferência?" | STATUSCONFERENCIA / SITUACAOWMS |
| "quando vai chegar a peça?" | DTPREVENT do pedido compra |
| "onde foi comprado esse item?" | Pedido compra → TGFPAR fornecedor |

---

## Fluxo de rastreio (3 etapas)

### Etapa 1: Status do pedido de venda

Busca cabecalho do pedido com status geral, NFe, conferencia e vendedor.

**Query:** Exemplo SQL #34

**Campos retornados:**
- STATUSNOTA (P=Pendente, L=Liberada, A=Em Atendimento)
- STATUSNFE (A=Autorizada, I=Enviada, R=Rejeitada)
- STATUSCONFERENCIA (ver conferencia_vendedor.md)
- SITUACAOWMS (ver conferencia_vendedor.md)
- PENDENTE (S/N)

### Etapa 2: Itens do pedido com estoque

Para cada item do pedido, verifica se tem estoque disponivel.

**Query:** Exemplo SQL #35

**Classificacao por item:**
- DISPONIVEL: estoque - reservado >= qtd vendida
- PARCIAL: tem estoque mas nao suficiente
- SEM ESTOQUE: zerado

### Etapa 3: Rastreio de compra vinculada

Para itens SEM ESTOQUE, busca pedidos de compra pendentes com o mesmo CODPROD.

**Query:** Exemplo SQL #36

**Status da compra:**
- ENTREGUE: TGFVAR.QTDATENDIDA >= QTDNEG
- ENTREGA PARCIAL: chegou parte
- ATRASADO: DTPREVENT < hoje e nao entregue
- AGUARDANDO: tem previsao, ainda no prazo
- SEM PREVISAO: sem data prevista

---

## Vinculo Compra Casada (TOP 1313)

Quando vendedor vende com empenho (TOP 1007), pode gerar pedido de compra casada (TOP 1313):

```
Pedido Venda (TOP 1007, NUNOTA=5000)
  └─> Item: CODPROD=12345, QTD=10
        └─> Pedido Compra Casada (TOP 1313, NUNOTA=6000)
              └─> Item: CODPROD=12345, QTD=10
                    └─> TGFVAR: NUNOTAORIG=6000 → NUNOTA=7000 (nota entrada)
```

Rastrear vinculo via:
- AD_NUNOTAVENDAEMP (pedido de venda que originou a compra)
- AD_NUNOTAMAE (pedido mae)
- TGFVAR (entregas parciais do pedido de compra)

---

## Exemplo de resposta completa pro vendedor

```
Pedido #5000 — Cliente: Auto Pecas Ribeirao
Status: Liberado | NFe: Autorizada | Vendedor: Joao

Itens do pedido:
| Produto               | Qtd | Estoque | Status             |
|-----------------------|-----|---------|---------------------|
| FILTRO AR MANN C25710 |  10 |   45    | DISPONIVEL          |
| FILTRO OLEO HU711    |   5 |    0    | COMPRADO-AGUARDANDO |
| CORREIA GATES 2PK    |   3 |    8    | DISPONIVEL          |

Compra pendente — FILTRO OLEO HU711:
  Pedido compra: #6000 | Fornecedor: MANN FILTER
  Comprado: 5 un | Entregue: 0 | Faltando: 5
  Previsao: 25/02/2026
  Status: AGUARDANDO ENTREGA DO FORNECEDOR
```

---

## Tabelas envolvidas

| Tabela | Papel |
|--------|-------|
| TGFCAB | Cabecalho pedido venda e compra |
| TGFITE | Itens do pedido |
| TGFPRO | Produto (descricao, marca) |
| TGFMAR | Marca |
| TGFPAR | Cliente / Fornecedor |
| TGFVEN | Vendedor |
| TGFEST | Estoque atual |
| TGFVAR | Entregas parciais (rastreio) |
| TSIEMP | Empresa |

---

## Observacoes para implementacao

1. **RBAC**: Vendedor so ve pedidos dele (CODVEND = :codvend). Admin ve tudo.
2. **Follow-up**: "ja ta na conferencia?" deve herdar o contexto do pedido anterior.
3. **NUNOTA vs NUMNOTA**: Vendedor pode informar NUNOTA (numero unico) ou NUMNOTA (numero da nota fiscal). Priorizar NUNOTA.
4. **Multiplos itens**: Um pedido pode ter 1 ou 100 itens. Mostrar resumo + detalhe dos problematicos.
