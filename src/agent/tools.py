"""
MMarra Data Hub - Tool Registry.

Define as ferramentas disponíveis para o agente usar via Function Calling.
Cada tool tem: nome, descrição, parâmetros tipados (JSON Schema).

O LLM recebe essas definições e escolhe qual tool chamar com quais parâmetros.
Isso substitui o prompt gigante de classificação por um mecanismo nativo e tipado.
"""

from typing import Callable, Optional


# ============================================================
# TOOL DEFINITIONS (OpenAI-compatible function calling format)
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_pendencias",
            "description": (
                "Consulta pedidos de compra pendentes no ERP Sankhya. "
                "Use quando o usuário perguntar sobre pendências, o que falta chegar, "
                "entregas, previsões, pedidos de compra abertos, pedidos atrasados, "
                "quem compra/fornece uma marca."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "marca": {
                        "type": "string",
                        "description": "Nome da marca (MAIÚSCULO). Ex: MANN, SABO, DONALDSON"
                    },
                    "fornecedor": {
                        "type": "string",
                        "description": "Nome do fornecedor"
                    },
                    "empresa": {
                        "type": "string",
                        "description": "Prefixo da empresa/filial. Ex: RIBEIR, UBERL, ARACAT, ITUMBI"
                    },
                    "comprador": {
                        "type": "string",
                        "description": "Nome do comprador responsável"
                    },
                    "tipo_compra": {
                        "type": "string",
                        "enum": ["casada", "estoque"],
                        "description": "casada=empenho/vinculada a venda, estoque=reposição geral"
                    },
                    "view": {
                        "type": "string",
                        "enum": ["pedidos", "itens"],
                        "description": "pedidos=agrupado por pedido (padrão), itens=produtos individuais"
                    },
                    "filtro_campo": {
                        "type": "string",
                        "description": "Campo para filtrar. Opções: STATUS_ENTREGA, PREVISAO_ENTREGA, CONFIRMADO, VLR_PENDENTE, DIAS_ABERTO, TIPO_COMPRA"
                    },
                    "filtro_operador": {
                        "type": "string",
                        "enum": ["igual", "vazio", "nao_vazio", "maior", "menor"],
                        "description": "Operador do filtro"
                    },
                    "filtro_valor": {
                        "type": "string",
                        "description": "Valor do filtro. Ex: ATRASADO, S, N, 50000"
                    },
                    "apenas_atrasados": {
                        "type": "boolean",
                        "description": "true = mostrar APENAS pedidos atrasados"
                    },
                    "valor_minimo": {
                        "type": "number",
                        "description": "Valor pendente mínimo. Ex: 50000 para 'acima de 50 mil'"
                    },
                    "valor_maximo": {
                        "type": "number",
                        "description": "Valor pendente máximo. Ex: 10000 para 'abaixo de 10 mil'"
                    },
                    "dias_minimo": {
                        "type": "integer",
                        "description": "Dias aberto mínimo. Ex: 30 para 'mais de 30 dias'"
                    },
                    "ordenar": {
                        "type": "string",
                        "description": "Campo_DIRECAO para ordenar. Ex: VLR_PENDENTE_DESC, DIAS_ABERTO_DESC, PREVISAO_ENTREGA_ASC, DT_PEDIDO_DESC"
                    },
                    "top": {
                        "type": "integer",
                        "description": "Limitar a N resultados. Ex: 1 para 'qual o...', 5 para 'top 5'"
                    },
                    "extra_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Colunas extras para incluir. Opções: NUM_FABRICANTE, NUM_ORIGINAL, REFERENCIA, PREVISAO_ENTREGA, TIPO_COMPRA, COMPRADOR, EMPRESA, DIAS_ABERTO"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_vendas",
            "description": (
                "Consulta vendas e faturamento. Use quando o usuário perguntar sobre "
                "vendas, faturamento, notas fiscais de venda, receita, ticket médio, "
                "ranking de vendedores, margem."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "periodo": {
                        "type": "string",
                        "enum": ["hoje", "ontem", "semana", "semana_passada", "mes", "mes_passado", "ano"],
                        "description": "Período da consulta. Padrão: mes"
                    },
                    "marca": {
                        "type": "string",
                        "description": "Filtrar por marca"
                    },
                    "empresa": {
                        "type": "string",
                        "description": "Prefixo da empresa/filial"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_estoque",
            "description": (
                "Consulta estoque de produtos. Use quando o usuário perguntar sobre "
                "saldo em estoque, disponibilidade, estoque crítico, estoque zerado, "
                "estoque mínimo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codprod": {
                        "type": "integer",
                        "description": "Código interno do produto"
                    },
                    "produto_nome": {
                        "type": "string",
                        "description": "Nome/descrição do produto para busca"
                    },
                    "marca": {
                        "type": "string",
                        "description": "Filtrar por marca"
                    },
                    "empresa": {
                        "type": "string",
                        "description": "Prefixo da empresa/filial"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_produto",
            "description": (
                "Busca produto no catálogo por nome, código ou referência via Elasticsearch. "
                "Use quando o usuário quer ENCONTRAR/PROCURAR um produto. "
                "Palavras-chave: 'tem', 'busca', 'procura', 'encontra', 'existe', 'cadastrado', "
                "'lista', 'quais correias', 'produtos da marca X'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "texto_busca": {
                        "type": "string",
                        "description": "Texto para buscar (nome do produto, código, referência)"
                    },
                    "marca": {
                        "type": "string",
                        "description": "Filtrar por marca"
                    },
                    "aplicacao": {
                        "type": "string",
                        "description": "Veículo/motor para filtrar aplicação. Ex: SCANIA R450, MERCEDES ACTROS"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_parceiro",
            "description": (
                "Busca cliente ou fornecedor por nome, CNPJ, cidade. "
                "Use quando o usuário quer dados de contato, telefone, endereço de um parceiro."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "texto_busca": {
                        "type": "string",
                        "description": "Nome, CNPJ ou cidade para buscar"
                    },
                    "tipo": {
                        "type": "string",
                        "enum": ["cliente", "fornecedor"],
                        "description": "Tipo de parceiro"
                    }
                },
                "required": ["texto_busca", "tipo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rastrear_pedido",
            "description": (
                "Rastreia um pedido de VENDA específico por NUNOTA. "
                "Mostra status, conferência, separação, se as peças foram compradas, "
                "se chegou. Use para 'como está o pedido X', 'status do pedido', "
                "'meu pedido', 'conferência do pedido'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "nunota": {
                        "type": "integer",
                        "description": "Número único da nota/pedido de venda (NUNOTA)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "produto_360",
            "description": (
                "Visão completa de um produto: estoque + pendências + vendas + info cadastral. "
                "Use para 'tudo sobre o produto X', 'situação do produto', 'resumo do produto'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codprod": {
                        "type": "integer",
                        "description": "Código interno do produto"
                    },
                    "codigo_fabricante": {
                        "type": "string",
                        "description": "Código do fabricante (ex: HU711/51, WK950/21)"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_similares",
            "description": (
                "Busca códigos similares/equivalentes/cross-reference de um produto. "
                "Use para 'similares do produto X', 'equivalente', 'outras marcas', "
                "'quais marcas tem o filtro X'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "codprod": {
                        "type": "integer",
                        "description": "Código interno do produto"
                    },
                    "codigo_fabricante": {
                        "type": "string",
                        "description": "Código do fabricante para buscar similares"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_financeiro",
            "description": (
                "Consulta financeira: contas a pagar, contas a receber e fluxo de caixa. "
                "Use quando o usuário perguntar sobre boletos, duplicatas, títulos, vencimentos, "
                "contas a pagar, contas a receber, fluxo de caixa, pagamentos, cobranças."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["pagar", "receber", "fluxo"],
                        "description": "Tipo da consulta: pagar=contas a pagar/despesas, receber=contas a receber/receitas, fluxo=fluxo de caixa (entradas vs saídas)"
                    },
                    "empresa": {
                        "type": "string",
                        "description": "Prefixo da empresa/filial. Ex: RIBEIR, UBERL, ARACAT, ITUMBI"
                    },
                    "periodo": {
                        "type": "string",
                        "enum": ["hoje", "semana", "mes", "mes_passado", "ano"],
                        "description": "Período de vencimento. Padrão: mes"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["vencido", "a_vencer", "todos"],
                        "description": "Filtrar por status: vencido=títulos vencidos, a_vencer=títulos a vencer, todos=ambos"
                    },
                    "parceiro": {
                        "type": "string",
                        "description": "Nome do parceiro/fornecedor/cliente para filtrar"
                    },
                    "valor_minimo": {
                        "type": "number",
                        "description": "Valor mínimo do título. Ex: 10000 para 'acima de 10 mil'"
                    },
                    "valor_maximo": {
                        "type": "number",
                        "description": "Valor máximo do título. Ex: 5000 para 'abaixo de 5 mil'"
                    },
                    "top": {
                        "type": "integer",
                        "description": "Limitar a N resultados. Ex: 10 para 'top 10'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_inadimplencia",
            "description": (
                "Consulta inadimplência de clientes. Títulos a receber vencidos e não pagos. "
                "Use quando o usuário perguntar sobre inadimplentes, devedores, quem deve, "
                "clientes atrasados, calote, cobrança de vencidos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "empresa": {
                        "type": "string",
                        "description": "Prefixo da empresa/filial. Ex: RIBEIR, UBERL, ARACAT, ITUMBI"
                    },
                    "parceiro": {
                        "type": "string",
                        "description": "Nome do cliente para filtrar"
                    },
                    "dias_minimo": {
                        "type": "integer",
                        "description": "Dias mínimo de atraso. Ex: 30 para 'mais de 30 dias'"
                    },
                    "valor_minimo": {
                        "type": "number",
                        "description": "Valor mínimo inadimplente. Ex: 50000 para 'acima de 50 mil'"
                    },
                    "top": {
                        "type": "integer",
                        "description": "Limitar a N clientes. Ex: 10 para 'top 10 devedores'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_comissao",
            "description": (
                "Consulta comissão de vendedores internos. Mostra ranking de vendedores, "
                "valores de comissão, margem, alíquota, base de cálculo. "
                "Use quando o usuário perguntar sobre comissão, comissões, quanto o vendedor ganha, "
                "ranking de comissão, margem de venda, alíquota."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vendedor": {
                        "type": "string",
                        "description": "Nome/apelido do vendedor. Ex: JOAO, MARIA"
                    },
                    "empresa": {
                        "type": "string",
                        "description": "Prefixo da empresa/filial. Ex: RIBEIR, UBERL, ARACAT, ITUMBI"
                    },
                    "periodo": {
                        "type": "string",
                        "enum": ["hoje", "ontem", "semana", "semana_passada", "mes", "mes_passado", "ano"],
                        "description": "Período da consulta. Padrão: mes"
                    },
                    "view": {
                        "type": "string",
                        "enum": ["ranking", "detalhe"],
                        "description": "ranking=agrupado por vendedor (padrão), detalhe=notas individuais"
                    },
                    "marca": {
                        "type": "string",
                        "description": "Filtrar por marca vendida"
                    },
                    "top": {
                        "type": "integer",
                        "description": "Limitar a N resultados. Ex: 10 para 'top 10'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_conhecimento",
            "description": (
                "Responde perguntas sobre processos, regras e políticas da empresa. "
                "Use para 'como funciona...', 'o que é...', 'qual a diferença entre...', "
                "'qual a política de...'. NÃO use para consultar dados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pergunta": {
                        "type": "string",
                        "description": "A pergunta sobre processos/regras"
                    }
                },
                "required": ["pergunta"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "saudacao",
            "description": "Responde saudações como 'oi', 'bom dia', 'olá'. Use APENAS para cumprimentos.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ajuda",
            "description": "Mostra menu de ajuda com exemplos do que o sistema faz. Use para 'help', 'ajuda', 'o que você faz'.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
]


# ============================================================
# TOOL NAME MAPPING (intent antigo → tool name)
# ============================================================

# Mapeamento do sistema de scoring (Layer 1) para tool names
INTENT_TO_TOOL = {
    "pendencia_compras": "consultar_pendencias",
    "vendas": "consultar_vendas",
    "estoque": "consultar_estoque",
    "busca_produto": "buscar_produto",
    "busca_cliente": "buscar_parceiro",
    "busca_fornecedor": "buscar_parceiro",
    "rastreio_pedido": "rastrear_pedido",
    "produto": "produto_360",
    "financeiro": "consultar_financeiro",
    "inadimplencia": "consultar_inadimplencia",
    "comissao": "consultar_comissao",
    "conhecimento": "consultar_conhecimento",
    "saudacao": "saudacao",
    "ajuda": "ajuda",
    "gerar_excel": "gerar_excel",
}

# Reverse: tool name → intent (para compatibilidade com contexto/logs)
TOOL_TO_INTENT = {v: k for k, v in INTENT_TO_TOOL.items()}
TOOL_TO_INTENT["buscar_parceiro"] = "busca_parceiro"
TOOL_TO_INTENT["gerar_excel"] = "gerar_excel"


# ============================================================
# TOOL CALL DATACLASS
# ============================================================

class ToolCall:
    """Representa uma chamada de ferramenta resolvida pelo router."""

    def __init__(self, name: str, params: dict = None, source: str = "unknown",
                 confidence: float = 0.0):
        self.name = name
        self.params = params or {}
        self.source = source  # "scoring", "function_calling", "fallback"
        self.confidence = confidence

    @property
    def intent(self) -> str:
        """Retorna o intent equivalente para compatibilidade."""
        return TOOL_TO_INTENT.get(self.name, self.name)

    def __repr__(self):
        return f"<ToolCall {self.name}({self.params}) via {self.source} conf={self.confidence:.0%}>"


# ============================================================
# HELPER: Extrair filtros do tool call params
# ============================================================

def tool_params_to_filters(params: dict) -> dict:
    """Converte parâmetros do tool call em formato de apply_filters."""
    filters = {}

    # ---- Atalhos diretos (mais fácil pro LLM preencher) ----
    if params.get("apenas_atrasados"):
        filters["STATUS_ENTREGA"] = "ATRASADO"

    if params.get("valor_minimo") is not None:
        filters["_fn_maior"] = f"VLR_PENDENTE:{params['valor_minimo']}"

    if params.get("valor_maximo") is not None:
        filters["_fn_menor"] = f"VLR_PENDENTE:{params['valor_maximo']}"

    if params.get("dias_minimo") is not None:
        filters["_fn_maior_dias"] = f"DIAS_ABERTO:{params['dias_minimo']}"

    # ---- Filtro genérico (filtro_campo/operador/valor) ----
    campo = params.get("filtro_campo")
    operador = params.get("filtro_operador")
    valor = params.get("filtro_valor")

    if operador == "igual" and campo and valor:
        filters[campo] = str(valor).upper()
    elif operador == "vazio" and campo:
        filters["_fn_empty"] = campo
    elif operador == "nao_vazio" and campo:
        filters["_fn_not_empty"] = campo
    elif operador == "maior" and campo and valor:
        # Não sobrescrever se atalho já preencheu
        key = "_fn_maior" if "_fn_maior" not in filters else "_fn_maior_2"
        filters[key] = f"{campo}:{valor}"
    elif operador == "menor" and campo and valor:
        key = "_fn_menor" if "_fn_menor" not in filters else "_fn_menor_2"
        filters[key] = f"{campo}:{valor}"

    # Ordenação
    if params.get("ordenar"):
        filters["_sort"] = params["ordenar"].upper()

    # Top N
    if params.get("top"):
        filters["_top"] = int(params["top"])

    # Tipo compra como filtro SQL
    tc = (params.get("tipo_compra") or "").lower()
    if tc in ("casada", "empenho", "vinculada"):
        filters["TIPO_COMPRA"] = "Casada"
    elif tc in ("estoque", "futura", "reposicao"):
        filters["TIPO_COMPRA"] = "Estoque"

    return filters


def get_tool_by_name(name: str) -> dict | None:
    """Retorna a definição de um tool pelo nome."""
    for tool in TOOLS:
        if tool["function"]["name"] == name:
            return tool
    return None