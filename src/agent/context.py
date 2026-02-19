"""
MMarra Data Hub - Contexto de Conversa.
Memoria por usuario, deteccao de follow-up, regras de filtro.
"""

import re

from src.core.utils import normalize


# ============================================================
# FOLLOW-UP DETECTION
# ============================================================

FOLLOWUP_WORDS = {
    "desses", "destes", "daqueles", "delas", "deles",
    "esses", "estes", "aqueles", "essas", "estas", "aquelas",
    "neles", "nelas", "nisso", "nesse", "nessa", "neste", "nesta",
    "mesma", "mesmo", "mesmos", "mesmas",
    "tambem", "alem", "ainda", "mais",
    "agora", "entao",
    "ele", "ela", "eles", "elas",
}

FOLLOWUP_PATTERNS = [
    r'\b(desse[s]?|deste[s]?|daquela?[s]?|dela[s]?|dele[s]?)\b',
    r'\b(esse[s]?|este[s]?|aquele[s]?|essa[s]?|esta[s]?|aquela[s]?)\b',
    r'\b(nele[s]?|nela[s]?|nisso|nesse[s]?|nessa[s]?)\b',
    r'\be (os|as|a|o) (itens|pedidos|pendentes|atrasados)\b',
    r'^e\s+(os|as|quais|quantos|quantas|qual|quanto)\b',
    r'^e\s+(da|do|de|das|dos)\s+',
    r'^(quais|quantos|quantas|qual|quanto)\s+(sao|estao|tem)\s+(os|as|atrasad)',
    r'^e\s+(ontem|hoje|semana|mes|ano|janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b',
    r'\b(qual|quais)\s+\w+\s+(ele|ela|eles|elas)\b',
]


def detect_followup(tokens: list, question_norm: str) -> bool:
    """Detecta se a pergunta e um follow-up referenciando dados anteriores.
    
    Args:
        tokens: pode ser list de tokens OU string normalizada (compatibilidade)
        question_norm: string normalizada da pergunta
    """
    # Compatibilidade: se tokens é string, converter
    if isinstance(tokens, str):
        question_norm = tokens
        tokens = tokens.split()
    if any(t in FOLLOWUP_WORDS for t in tokens):
        return True
    for pattern in FOLLOWUP_PATTERNS:
        if re.search(pattern, question_norm):
            return True
    if len(tokens) <= 7:
        followup_indicators = {"itens", "pedidos", "atrasados", "atrasado", "pendentes",
                                "pendente", "confirmados", "prazo", "previsao", "proximo",
                                "proximos", "urgente", "urgentes", "caro", "caros",
                                "barato", "baratos", "antigo", "antigos", "recente", "recentes"}
        has_indicator = any(t in followup_indicators for t in tokens)
        has_qualifier = any(t in tokens for t in ["marca", "fornecedor", "empresa", "produto"])
        if has_indicator and not has_qualifier:
            noise_words = {"quais", "quantos", "quantas", "estao", "sao", "como", "qual", "quem",
                           "itens", "pedidos", "atrasados", "atrasado", "pendentes", "pendente",
                           "confirmados", "valor", "maior", "menor", "mais", "menos",
                           "prazo", "previsao", "proximo", "proximos", "urgente", "caro",
                           "barato", "antigo", "recente", "total", "todos", "todas",
                           "pedido", "esta", "esse", "essa", "qual"}
            other_words = [t for t in tokens if t not in noise_words and len(t) >= 4]
            if not other_words:
                return True
    return False


# ============================================================
# FILTER RULES (pattern-matching para filtros comuns)
# ORDEM IMPORTA - mais especificos primeiro!
# ============================================================

FILTER_RULES = [
    # === TIPO DE COMPRA ===
    {"match": ["compra casada", "compras casadas", "pedido casado", "pedidos casados", "empenho", "empenhado", "empenhados", "vinculada"],
     "filter": {"TIPO_COMPRA": "Casada"}},
    {"match": ["compra estoque", "compra de estoque", "compra para estoque", "compras de estoque", "entrega futura", "reposicao"],
     "filter": {"TIPO_COMPRA": "Estoque"}},
    # === PREVISAO DE ENTREGA ===
    {"match": ["maior data de entrega", "maior previsao de entrega", "maior previsao entrega"],
     "sort": "PREVISAO_ENTREGA_DESC", "top": 1},
    {"match": ["menor data de entrega", "menor previsao de entrega", "menor previsao entrega"],
     "sort": "PREVISAO_ENTREGA_ASC", "top": 1},
    {"match": ["data de entrega mais distante", "previsao mais distante", "entrega mais longe"],
     "sort": "PREVISAO_ENTREGA_DESC", "top": 1},
    {"match": ["data de entrega mais proxima", "previsao mais proxima", "proxima entrega"],
     "sort": "PREVISAO_ENTREGA_ASC", "top": 1},
    # === SUPERLATIVOS ===
    {"match": ["mais atrasado"],     "sort": "DIAS_ABERTO_DESC",      "top": 1},
    {"match": ["mais atrasados"],    "sort": "DIAS_ABERTO_DESC",      "top": 5},
    {"match": ["mais caro"],         "sort": "VLR_PENDENTE_DESC",     "top": 1},
    {"match": ["mais caros"],        "sort": "VLR_PENDENTE_DESC",     "top": 5},
    {"match": ["mais barato"],       "sort": "VLR_PENDENTE_ASC",      "top": 1},
    {"match": ["mais baratos"],      "sort": "VLR_PENDENTE_ASC",      "top": 5},
    {"match": ["mais antigo"],       "sort": "DIAS_ABERTO_DESC",      "top": 1},
    {"match": ["mais antigos"],      "sort": "DIAS_ABERTO_DESC",      "top": 5},
    {"match": ["mais recente"],      "sort": "DT_PEDIDO_DESC",        "top": 1},
    {"match": ["mais recentes"],     "sort": "DT_PEDIDO_DESC",        "top": 5},
    {"match": ["maior valor"],       "sort": "VLR_PENDENTE_DESC",     "top": 1},
    {"match": ["menor valor"],       "sort": "VLR_PENDENTE_ASC",      "top": 1},
    {"match": ["maior quantidade"],  "sort": "QTD_PENDENTE_DESC",     "top": 1},
    {"match": ["mais urgente"],      "sort": "DIAS_ABERTO_DESC",      "top": 1},
    {"match": ["mais urgentes"],     "sort": "DIAS_ABERTO_DESC",      "top": 5},
    # === FILTROS por CAMPO ===
    {"match": ["sem previsao de entrega", "sem data de entrega", "sem previsao entrega"],
     "filter_fn": "empty", "filter_field": "PREVISAO_ENTREGA"},
    {"match": ["sem confirmacao", "nao confirmado", "nao confirmados"],
     "filter": {"CONFIRMADO": "N"}},
    {"match": ["confirmado", "confirmados"],           "filter": {"CONFIRMADO": "S"}},
    # === STATUS_ENTREGA ===
    {"match": ["sem previsao"],                        "filter": {"STATUS_ENTREGA": "SEM PREVISAO"}},
    {"match": ["no prazo", "dentro do prazo"],         "filter": {"STATUS_ENTREGA": "NO PRAZO"}},
    {"match": ["atrasado", "atrasados"],               "filter": {"STATUS_ENTREGA": "ATRASADO"}},
    {"match": ["proximo", "proximos"],                 "filter": {"STATUS_ENTREGA": "PROXIMO"}},
]

# Compiled rules (populated by knowledge_compiler at startup)
_COMPILED_RULES = []


def detect_filter_request(question_norm: str, tokens: list) -> dict:
    """Detecta se o usuario quer filtrar/ordenar dados anteriores. FILTER_RULES + compiladas."""
    result = {}

    all_rules = list(FILTER_RULES) + list(_COMPILED_RULES)
    for rule in all_rules:
        matched = any(m in question_norm for m in rule["match"])
        if not matched:
            continue

        if "filter" in rule:
            result.update(rule["filter"])
        if "filter_fn" in rule:
            result[f"_fn_{rule['filter_fn']}"] = rule["filter_field"]
        if "sort" in rule:
            if "_sort" not in result:
                result["_sort"] = rule["sort"]
        if "top" in rule:
            if "_top" not in result:
                result["_top"] = rule["top"]

        if "sort" in rule or "top" in rule:
            break

    # Detectar numero explicito: "5 mais caros", "top 10"
    num_match = re.search(r'\b(\d{1,3})\s+(?:mais|primeiro|primeiros|maior|menor|ultim)', question_norm)
    if not num_match:
        num_match = re.search(r'(?:top|os)\s+(\d{1,3})\b', question_norm)
    if num_match:
        result["_top"] = int(num_match.group(1))

    if result and "_top" not in result:
        if any(t in tokens for t in ["qual"]):
            result["_top"] = 1

    return result


def apply_filters(data: list, filters: dict) -> list:
    """Aplica filtros, ordenacao e limite aos dados ja retornados."""
    if not data or not filters:
        return data

    sort_key = filters.pop("_sort", None)
    top_n = filters.pop("_top", None)
    result = data

    fn_keys = [k for k in filters if k.startswith("_fn_")]
    for fn_key in fn_keys:
        field_spec = filters.pop(fn_key)
        fn_name = fn_key.replace("_fn_", "")
        if fn_name == "empty":
            result = [r for r in result if isinstance(r, dict) and not str(r.get(field_spec, "") or "").strip()]
        elif fn_name == "not_empty":
            result = [r for r in result if isinstance(r, dict) and str(r.get(field_spec, "") or "").strip()]
        elif fn_name in ("maior", "menor") and ":" in str(field_spec):
            campo, valor_str = str(field_spec).split(":", 1)
            try:
                threshold = float(valor_str)
                if fn_name == "maior":
                    result = [r for r in result if isinstance(r, dict) and float(r.get(campo, 0) or 0) > threshold]
                else:
                    result = [r for r in result if isinstance(r, dict) and float(r.get(campo, 0) or 0) < threshold]
            except (ValueError, TypeError):
                pass
        elif fn_name.startswith(("maior", "menor")) and ":" in str(field_spec):
            campo, valor_str = str(field_spec).split(":", 1)
            try:
                threshold = float(valor_str)
                if fn_name.startswith("maior"):
                    result = [r for r in result if isinstance(r, dict) and float(r.get(campo, 0) or 0) > threshold]
                else:
                    result = [r for r in result if isinstance(r, dict) and float(r.get(campo, 0) or 0) < threshold]
            except (ValueError, TypeError):
                pass
        elif fn_name == "contem" and ":" in str(field_spec):
            campo, texto = str(field_spec).split(":", 1)
            result = [r for r in result if isinstance(r, dict) and texto.upper() in str(r.get(campo, "")).upper()]

    for field, value in filters.items():
        if field.startswith("_"):
            continue
        result = [r for r in result if isinstance(r, dict) and str(r.get(field, "")).upper() == value.upper()]

    if sort_key and result:
        field, direction = sort_key.rsplit("_", 1)
        reverse = direction == "DESC"
        try:
            result = sorted(result, key=lambda r: float(r.get(field, 0) or 0), reverse=reverse)
        except (ValueError, TypeError):
            try:
                def _sort_key(r):
                    v = str(r.get(field, "") or "")
                    if re.match(r'\d{2}/\d{2}/\d{4}', v):
                        parts = v.split("/")
                        return f"{parts[2]}-{parts[1]}-{parts[0]}"
                    return v
                result = sorted(result, key=_sort_key, reverse=reverse)
            except Exception:
                pass

    if top_n and result:
        result = result[:top_n]

    return result


# ============================================================
# CONVERSATION CONTEXT
# ============================================================

class ConversationContext:
    """Contexto de conversa de um usuario. Guarda parametros e dados anteriores."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.intent = None
        self.params = {}
        self.last_result = {}
        self.last_question = ""
        self.last_view_mode = "pedidos"
        self.turn_count = 0
        self._extra_columns = []

    def merge_params(self, new_params: dict) -> dict:
        """Mescla parametros novos com contexto anterior."""
        merged = {}
        param_keys = ["marca", "fornecedor", "empresa", "comprador", "periodo",
                       "codprod", "codigo_fabricante", "produto_nome", "pedido", "aplicacao",
                       "vendedor", "parceiro"]
        for key in param_keys:
            new_val = new_params.get(key)
            old_val = self.params.get(key)
            if new_val:
                merged[key] = new_val
            elif old_val:
                merged[key] = old_val
        return merged

    def update(self, intent: str, params: dict, result: dict, question: str, view_mode: str = "pedidos"):
        """Atualiza contexto apos uma resposta bem-sucedida."""
        if intent != self.intent:
            self._extra_columns = []
        self.intent = intent
        for k, v in params.items():
            if v:
                self.params[k] = v
        self.last_result = result
        self.last_question = question
        self.last_view_mode = view_mode
        self.turn_count += 1

    def has_data(self) -> bool:
        return bool(self.last_result and self.last_result.get("detail_data"))

    def get_data(self) -> list:
        return self.last_result.get("detail_data", [])

    def get_description(self) -> str:
        return self.last_result.get("description", "")

    def __repr__(self):
        return f"<Ctx user={self.user_id} intent={self.intent} params={self.params} turns={self.turn_count}>"


def build_context_hint(ctx: ConversationContext) -> str:
    """Monta hint de contexto para enviar ao LLM junto com a pergunta."""
    if not ctx or not ctx.intent:
        return ""

    parts = [f"Intent anterior: {ctx.intent}"]
    if ctx.params:
        parts.append(f"Parametros: {ctx.params}")
    if ctx.has_data():
        data = ctx.get_data()
        parts.append(f"Dados anteriores: {len(data)} registros")
        # Resumo de status
        status_count = {}
        for item in data[:100]:
            if isinstance(item, dict):
                st = item.get("STATUS_ENTREGA", "")
                if st:
                    status_count[st] = status_count.get(st, 0) + 1
        if status_count:
            parts.append(f"Status: {status_count}")
    return "\n".join(parts)