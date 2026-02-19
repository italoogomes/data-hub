"""
MMarra Data Hub - Sistema de Scoring.
Classificacao de intents por palavras-chave com pesos.
Resolve ~90% das perguntas em 0ms.
"""

import json
from pathlib import Path

from src.core.utils import normalize, tokenize
from src.llm.knowledge_compiler import COMPILED_PATH


# ============================================================
# INTENT SCORES - Palavras-chave e seus pesos por intent
# ============================================================

INTENT_SCORES = {
    "pendencia_compras": {
        "pendencia": 10, "pendencias": 10, "pendente": 10, "pendentes": 10,
        "pend": 8,
        "compra": 6, "compras": 6, "pedido": 5, "pedidos": 5,
        "aberto": 5, "abertos": 5, "atraso": 5, "atrasado": 5, "atrasados": 5,
        "marca": 3, "fornecedor": 3, "comprador": 3, "empresa": 3, "filial": 3,
        "quantos": 2, "quais": 2, "qual": 2, "quanto": 2,
        "tem": 1, "temos": 1, "total": 2, "valor": 2,
        "falta": 4, "faltam": 4, "faltando": 4, "chegar": 3, "chegando": 3,
        "entrega": 3, "entregar": 3, "previsao": 3,
        "casada": 6, "casadas": 6, "empenho": 6, "empenhado": 6, "empenhados": 6,
        "vinculada": 5, "vinculado": 5,
        "reposicao": 5, "futura": 4,
        "quem": 4, "responsavel": 4,
        "fornece": 5,
    },
    "estoque": {
        "estoque": 10, "saldo": 8, "disponivel": 6,
        "produto": 3, "peca": 3, "pecas": 3, "item": 2,
        "critico": 5, "baixo": 4, "zerado": 5, "minimo": 4,
        "acabando": 5, "faltando": 4,
        "quantos": 2, "quanto": 2, "quais": 2,
        "codigo": 2, "cod": 2,
        "referencia": 4, "fabricante": 4, "similar": 5, "similares": 5,
        "equivalente": 5, "equivalentes": 5, "crossref": 5,
        "aplicacao": 5, "aplica": 5, "serve": 4, "compativel": 4,
        "veiculo": 3, "motor": 3, "caminhao": 3,
        "scania": 3, "mercedes": 3, "volvo": 3, "vw": 3, "man": 3, "daf": 3, "iveco": 3,
    },
    "vendas": {
        "vendas": 10, "venda": 10, "faturamento": 10,
        "faturou": 8, "vendeu": 8, "vendemos": 8, "faturamos": 8,
        "faturada": 6, "faturadas": 6, "faturado": 6,
        "hoje": 3, "ontem": 3, "semana": 3, "mes": 3, "ano": 3,
        "ticket": 5, "tiquete": 5, "medio": 3,
        "quanto": 3, "total": 3, "valor": 2,
        "ranking": 4, "top": 4, "maiores": 3, "melhores": 3,
        "vendedor": 3, "vendedores": 3,
    },
    "gerar_excel": {
        "excel": 10, "planilha": 10, "xlsx": 10, "csv": 8,
        "arquivo": 8, "download": 8, "baixar": 8, "exportar": 8,
        "gera": 6, "gerar": 6, "gere": 6,
        "relatorio": 5,
    },
    "saudacao": {
        "oi": 10, "ola": 10, "bom": 5, "dia": 3, "boa": 5,
        "tarde": 3, "noite": 3, "fala": 6, "hey": 8, "hello": 8,
        "eai": 8, "eae": 8,
    },
    "ajuda": {
        "ajuda": 10, "help": 10, "menu": 8, "comandos": 8, "opcoes": 8,
        "funciona": 5, "consegue": 5, "funcoes": 6,
    },
    "busca_produto": {
        "busca": 8, "buscar": 8, "procura": 8, "procurar": 8,
        "encontra": 8, "encontrar": 8, "acha": 7, "achar": 7,
        "existe": 6, "tem": 4,
        "produto": 3, "peca": 3, "pecas": 3, "filtro": 3, "filtros": 3,
        "catalogo": 6,
        "traga": 5, "traz": 5, "lista": 4, "listar": 4, "preciso": 4,
        "correia": 3, "correias": 3, "disco": 3, "discos": 3,
        "pastilha": 3, "pastilhas": 3, "abracadeira": 3, "rolamento": 3,
        "cadastrado": 4, "cadastrada": 4, "cadastrados": 4,
        "codigo": 4, "referencia": 4,
    },
    "busca_cliente": {
        "cliente": 8, "clientes": 8,
        "dados": 5, "contato": 5, "telefone": 5, "cnpj": 8, "cpf": 7,
        "endereco": 4, "email": 4,
        "busca": 3, "procura": 3, "encontra": 3,
    },
    "busca_fornecedor": {
        "fornecedor": 8, "fornecedores": 8,
        "contato": 5, "telefone": 5, "dados": 5,
        "cnpj": 6, "email": 4,
        "busca": 3, "procura": 3,
    },
    "financeiro": {
        "financeiro": 10, "financeira": 10,
        "boleto": 10, "boletos": 10, "duplicata": 10, "duplicatas": 10,
        "titulo": 8, "titulos": 8,
        "pagar": 8, "receber": 8,
        "vencido": 8, "vencidos": 8, "vencida": 8, "vencidas": 8,
        "vencimento": 8, "vencimentos": 8, "vencer": 6,
        "pagamento": 6, "pagamentos": 6,
        "cobranca": 6, "cobrancas": 6,
        "fluxo": 8, "caixa": 6,
        "contas": 6, "conta": 4,
        "despesa": 5, "despesas": 5, "receita": 5, "receitas": 5,
        "baixa": 4, "baixado": 4, "baixados": 4,
        "quanto": 2, "total": 2, "valor": 2,
    },
    "inadimplencia": {
        "inadimplencia": 10, "inadimplente": 10, "inadimplentes": 10,
        "devendo": 10, "devedor": 10, "devedores": 10, "deve": 6,
        "calote": 10, "caloteiro": 10,
        "atraso": 6, "atrasado": 5, "atrasados": 5,
        "cobranca": 5, "cobrar": 5,
        "cliente": 3, "clientes": 3,
        "quem": 3, "mais": 2,
    },
    "comissao": {
        "comissao": 10, "comissoes": 10, "comissionamento": 10,
        "aliquota": 10, "aliquotas": 10,
        "margem": 8, "margens": 8,
        "ranking": 5,
        "vendedor": 4, "vendedores": 4,
        "prazo": 3, "pmv": 8,
        "quanto": 2, "ganha": 6, "ganhou": 6, "ganham": 6,
        "percentual": 6, "porcentagem": 6,
        "base": 3, "calculo": 5,
    },
    "rastreio_pedido": {
        "rastrear": 10, "rastreio": 10, "rastreamento": 10,
        "status": 6, "acompanhar": 6,
        "conferencia": 8, "conferindo": 8, "conferido": 8, "conferir": 8,
        "separacao": 7, "separando": 7, "separado": 7,
        "wms": 8, "expedicao": 6,
        "chegou": 6, "entregou": 6, "comprado": 6, "comprou": 6,
        "faturado": 6, "faturou": 6,
        "pedido": 5, "pedidos": 5,
        "venda": 4, "vendeu": 4, "vendi": 4,
        "cade": 6, "onde": 3, "como": 3, "quando": 4,
    },
}

INTENT_THRESHOLDS = {
    "pendencia_compras": 8,
    "estoque": 8,
    "vendas": 8,
    "gerar_excel": 8,
    "saudacao": 8,
    "ajuda": 8,
    "busca_produto": 8,
    "financeiro": 8,
    "inadimplencia": 8,
    "comissao": 8,
    "busca_cliente": 10,
    "busca_fornecedor": 10,
    "rastreio_pedido": 10,
}

CONFIRM_WORDS = {"sim", "quero", "pode", "claro", "isso", "ok", "beleza", "bora", "vamos", "manda", "faz", "gera", "gere"}

VIEW_ITEM_WORDS = {"itens", "item", "produtos", "produto", "detalhe", "detalhes", "detalhado", "lista", "listagem", "peca", "pecas"}
VIEW_ORDER_WORDS = {"pedidos", "pedido", "resumo", "agrupado", "consolidado"}


# ============================================================
# COMPILED KNOWLEDGE (auto-gerado pelo Knowledge Compiler)
# ============================================================

_COMPILED_SCORES = {}
_COMPILED_RULES = []
_COMPILED_EXAMPLES = []
_COMPILED_SYNONYMS = []
_COMPILED_LOADED = False


def load_compiled_knowledge():
    """Carrega compiled_knowledge.json e monta dicts de merge."""
    global _COMPILED_SCORES, _COMPILED_RULES, _COMPILED_EXAMPLES, _COMPILED_SYNONYMS, _COMPILED_LOADED
    if _COMPILED_LOADED:
        return
    _COMPILED_LOADED = True

    if not COMPILED_PATH.exists():
        return

    try:
        with open(COMPILED_PATH, "r", encoding="utf-8") as f:
            compiled = json.load(f)
    except Exception as e:
        print(f"[SMART] Erro ao carregar compiled_knowledge: {e}")
        return

    for intent, keywords in compiled.get("intent_keywords", {}).items():
        if intent == "unknown":
            continue
        if intent not in _COMPILED_SCORES:
            _COMPILED_SCORES[intent] = {}
        for kw in keywords:
            word = kw.get("word", "").lower().strip()
            weight = kw.get("weight", 3)
            if word and len(word) >= 2:
                if intent in INTENT_SCORES and word in INTENT_SCORES[intent]:
                    continue
                _COMPILED_SCORES[intent][word] = weight

    from src.agent.context import FILTER_RULES
    for rule in compiled.get("filter_rules", []):
        matches = rule.get("match", [])
        if not matches:
            continue
        manual_matches = set()
        for mr in FILTER_RULES:
            for m in mr.get("match", []):
                manual_matches.add(m.lower())
        if all(m.lower() in manual_matches for m in matches):
            continue
        _COMPILED_RULES.append(rule)

    _COMPILED_EXAMPLES.extend(compiled.get("groq_examples", []))
    _COMPILED_SYNONYMS.extend(compiled.get("synonyms", []))

    total_kw = sum(len(v) for v in _COMPILED_SCORES.values())
    print(f"[SMART] Compiled knowledge: +{total_kw} keywords em {len(_COMPILED_SCORES)} intents, "
          f"+{len(_COMPILED_RULES)} filter rules, +{len(_COMPILED_EXAMPLES)} examples")

    for pi in compiled.get("potential_intents", []):
        print(f"[SMART] ** Intent potencial: {pi['name']} ({pi['keywords_count']} keywords) - {pi.get('note', '')}")


def reload_compiled():
    """Forca recarga do compiled knowledge."""
    global _COMPILED_LOADED
    _COMPILED_LOADED = False
    load_compiled_knowledge()


# ============================================================
# SCORING FUNCTIONS
# ============================================================

def score_intent(tokens: list) -> dict:
    """Calcula score de cada intent baseado nos tokens (manual + compilado)."""
    scores = {}
    for intent_id, keywords in INTENT_SCORES.items():
        s = 0
        for token in tokens:
            if token in keywords:
                s += keywords[token]
        scores[intent_id] = s
    for intent_id, keywords in _COMPILED_SCORES.items():
        if intent_id not in scores:
            scores[intent_id] = 0
        for token in tokens:
            if token in keywords:
                if intent_id not in INTENT_SCORES or token not in INTENT_SCORES[intent_id]:
                    scores[intent_id] += keywords[token]
    return scores


def detect_view_mode(tokens: list) -> str:
    """Decide se mostra itens ou pedidos."""
    item_score = sum(1 for t in tokens if t in VIEW_ITEM_WORDS)
    order_score = sum(1 for t in tokens if t in VIEW_ORDER_WORDS)
    if item_score > order_score:
        return "itens"
    return "pedidos"


# ============================================================
# COLUMN CONSTANTS (personalizacao de relatorios via Groq)
# ============================================================

EXISTING_SQL_COLUMNS = {
    "EMPRESA", "PEDIDO", "TIPO_COMPRA", "COMPRADOR", "DT_PEDIDO",
    "PREVISAO_ENTREGA", "CONFIRMADO", "FORNECEDOR", "CODPROD", "PRODUTO",
    "MARCA", "APLICACAO", "UNIDADE", "QTD_PEDIDA", "QTD_ATENDIDA",
    "QTD_PENDENTE", "VLR_UNITARIO", "VLR_PENDENTE", "DIAS_ABERTO", "STATUS_ENTREGA",
    "NUM_FABRICANTE",
}

# Campos EXTRAS que precisam ser adicionados ao SQL
EXTRA_SQL_FIELDS = {
    "NUM_ORIGINAL":    "NVL(PRO.AD_NUMORIGINAL, '') AS NUM_ORIGINAL",
    "REFERENCIA":      "NVL(PRO.REFERENCIA, '') AS REFERENCIA",
    "REF_FORNECEDOR":  "NVL(PRO.REFFORN, '') AS REF_FORNECEDOR",
    "COMPLEMENTO":     "NVL(PRO.COMPLDESC, '') AS COMPLEMENTO",
    "NCM":             "NVL(PRO.NCM, '') AS NCM",
}

# Normalizacao (Groq pode retornar variacoes)
COLUMN_NORMALIZE = {
    "PREVISAO": "PREVISAO_ENTREGA", "PREVISAO_ENTREGA": "PREVISAO_ENTREGA",
    "DIAS": "DIAS_ABERTO", "DIAS_ABERTO": "DIAS_ABERTO",
    "FABRICANTE": "NUM_FABRICANTE", "NUM_FABRICANTE": "NUM_FABRICANTE",
    "NUMERO_FABRICANTE": "NUM_FABRICANTE", "CODIGO_FABRICANTE": "NUM_FABRICANTE",
    "ORIGINAL": "NUM_ORIGINAL", "NUM_ORIGINAL": "NUM_ORIGINAL",
    "REFERENCIA": "REFERENCIA", "EMPRESA": "EMPRESA",
    "TIPO_COMPRA": "TIPO_COMPRA", "COMPRADOR": "COMPRADOR",
    "FORNECEDOR": "FORNECEDOR", "CONFIRMADO": "CONFIRMADO",
    "UNIDADE": "UNIDADE", "QTD_PEDIDA": "QTD_PEDIDA",
    "QTD_ATENDIDA": "QTD_ATENDIDA", "VLR_UNITARIO": "VLR_UNITARIO",
    "APLICACAO": "APLICACAO",
}

# Labels amigaveis para headers de tabela
COLUMN_LABELS = {
    "PEDIDO": "Pedido", "CODPROD": "CodProd", "PRODUTO": "Produto",
    "MARCA": "Marca", "QTD_PENDENTE": "Qtd Pend.", "VLR_PENDENTE": "Valor",
    "STATUS_ENTREGA": "Status", "FORNECEDOR": "Fornecedor", "DT_PEDIDO": "Data",
    "PREVISAO_ENTREGA": "Previsao", "EMPRESA": "Empresa", "TIPO_COMPRA": "Tipo",
    "COMPRADOR": "Comprador", "CONFIRMADO": "Confirmado", "APLICACAO": "Aplicacao",
    "UNIDADE": "Unid.", "QTD_PEDIDA": "Qtd Pedida", "QTD_ATENDIDA": "Qtd Atend.",
    "VLR_UNITARIO": "Vlr Unit.", "DIAS_ABERTO": "Dias",
    "NUM_FABRICANTE": "Cod. Fabricante", "NUM_ORIGINAL": "Nro. Original",
    "REFERENCIA": "Referencia", "REF_FORNECEDOR": "Ref. Forn.",
    "COMPLEMENTO": "Complemento", "NCM": "NCM",
}

COLUMN_MAX_WIDTH = {
    "PRODUTO": 30, "FORNECEDOR": 25, "EMPRESA": 20, "APLICACAO": 25,
    "COMPLEMENTO": 25, "NUM_FABRICANTE": 18, "REFERENCIA": 18, "COMPRADOR": 15,
}
