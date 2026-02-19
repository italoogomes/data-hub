"""
MMarra Data Hub - Multi-Step Query Decomposition.

Detecta padrões de queries compostas e decompõe em sub-queries sequenciais.
NÃO usa LLM para planejar — usa regex/patterns para máxima confiabilidade.

Padrões suportados:
  - Comparação temporal: "comissão janeiro vs fevereiro"
  - Comparação de entidades: "compare comissão do rogerio vs rafael"
  - Variação temporal: "vendas aumentaram esse mês?"

Cada step reutiliza os handlers existentes via dispatch.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from src.core.utils import normalize


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class StepPlan:
    """Plano de execução multi-step."""
    steps: list              # Lista de dicts: {"intent", "params", "label"}
    merge_strategy: str      # "compare", "aggregate", "trend"
    presentation: str        # "side_by_side", "table", "narrative"
    original_question: str


@dataclass
class StepResult:
    """Resultado de um step executado."""
    label: str               # "Janeiro", "Fevereiro", "Rogerio", etc.
    data: list               # Dados retornados (detail_data)
    kpis: dict               # KPIs extraídos do resultado
    params: dict             # Params usados neste step


# ============================================================
# MAPEAMENTO DE PERÍODOS (nomes → enum do sistema)
# ============================================================

# Meses por nome → periodo "custom" com data_inicio/data_fim
_MONTH_NAMES = {
    "janeiro": "01", "fevereiro": "02", "marco": "03", "março": "03",
    "abril": "04", "maio": "05", "junho": "06",
    "julho": "07", "agosto": "08", "setembro": "09",
    "outubro": "10", "novembro": "11", "dezembro": "12",
    # Abreviados
    "jan": "01", "fev": "02", "mar": "03", "abr": "04",
    "mai": "05", "jun": "06", "jul": "07", "ago": "08",
    "set": "09", "out": "10", "nov": "11", "dez": "12",
}

# Labels bonitos para meses
_MONTH_LABELS = {
    "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
    "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
    "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro",
}

# Períodos relativos → enum do sistema
_RELATIVE_PERIODS = {
    "hoje": ("hoje", "Hoje"),
    "ontem": ("ontem", "Ontem"),
    "essa semana": ("semana", "Esta semana"),
    "esta semana": ("semana", "Esta semana"),
    "semana": ("semana", "Esta semana"),
    "semana passada": ("semana_passada", "Semana passada"),
    "esse mes": ("mes", "Este mês"),
    "este mes": ("mes", "Este mês"),
    "mes": ("mes", "Este mês"),
    "mes atual": ("mes", "Este mês"),
    "mes passado": ("mes_passado", "Mês passado"),
    "esse ano": ("ano", "Este ano"),
    "este ano": ("ano", "Este ano"),
    "ano": ("ano", "Este ano"),
}


def _resolve_period(text: str) -> tuple:
    """
    Resolve texto de período para (params_dict, label).
    Retorna params compatíveis com os handlers existentes.
    """
    t = normalize(text).strip()

    # Período relativo ("mês passado", "hoje", etc.)
    if t in _RELATIVE_PERIODS:
        enum_val, label = _RELATIVE_PERIODS[t]
        return {"periodo": enum_val}, label

    # Mês por nome ("janeiro", "fev")
    month = _MONTH_NAMES.get(t)
    if month:
        from datetime import datetime
        year = datetime.now().year
        from calendar import monthrange
        _, last_day = monthrange(year, int(month))
        label = _MONTH_LABELS.get(month, text.title())
        return {
            "periodo": "custom",
            "data_inicio": f"{year}-{month}-01",
            "data_fim": f"{year}-{month}-{last_day:02d}",
        }, label

    # Fallback: tentar como período enum direto
    return {"periodo": t}, text.title()


# ============================================================
# MAPEAMENTO DE DOMÍNIO
# ============================================================

def _domain_to_intent(domain: str) -> str:
    """Mapeia palavra de domínio para intent."""
    d = domain.lower()
    if "comiss" in d:
        return "comissao"
    if "venda" in d or "fatura" in d:
        return "vendas"
    if "pend" in d or "pedido" in d or "compra" in d:
        return "pendencia_compras"
    if "financeir" in d or "conta" in d or "bolet" in d:
        return "financeiro"
    if "inadimpl" in d or "deved" in d:
        return "inadimplencia"
    if "estoq" in d:
        return "estoque"
    return "vendas"


def _infer_intent(q: str) -> str:
    """Infere o intent da pergunta completa."""
    q = q.lower()
    if "comiss" in q:
        return "comissao"
    if "venda" in q or "fatura" in q:
        return "vendas"
    if "pend" in q or "atrasa" in q:
        return "pendencia_compras"
    if "financeir" in q or "pagar" in q or "receber" in q or "bolet" in q:
        return "financeiro"
    if "inadimpl" in q or "deved" in q:
        return "inadimplencia"
    return "vendas"


def _classify_entities(a: str, b: str) -> str:
    """
    Classifica par de entidades como vendedor, empresa ou marca.
    Heurística baseada nos nomes conhecidos.
    """
    city_hints = {"uberl", "ribeir", "aracat", "itumb", "preto", "paulo",
                  "ribeirao", "uberlandia", "aracatuba", "itumbiara"}
    a_lower = a.lower()
    b_lower = b.lower()

    if any(h in a_lower for h in city_hints) or any(h in b_lower for h in city_hints):
        return "empresa"

    # Marcas conhecidas: maiúsculas curtas, sem espaço
    brand_hints = {"mann", "sabo", "donaldson", "wega", "fleetguard", "eaton",
                   "zf", "nakata", "mahle", "cobreq", "fras-le", "frasle"}
    if a_lower in brand_hints or b_lower in brand_hints:
        return "marca"

    # Default: vendedor (mais comum em comparações de comissão)
    return "vendedor"


# ============================================================
# DETECTION: Comparação Temporal
# ============================================================

_TEMPORAL_PATTERNS = [
    # "comissão de janeiro vs fevereiro"
    # "vendas de janeiro contra fevereiro"
    (
        r'(comiss[aã]o|vendas?|faturamento|pend[eê]ncias?|financeiro|contas?)\s+'
        r'(?:de\s+|do\s+|da\s+)?'
        r'(\w+(?:\s+\w+)?)\s+'
        r'(?:vs\.?|versus|contra|x)\s+'
        r'(?:de\s+|do\s+|da\s+)?'
        r'(\w+(?:\s+\w+)?)'
    ),
    # "compare comissão de janeiro com fevereiro"
    (
        r'compar[ae]\w*\s+(?:a[s]?\s+)?'
        r'(comiss[aã]o|vendas?|faturamento)\s+'
        r'(?:de\s+|do\s+|da\s+)?'
        r'(\w+(?:\s+\w+)?)\s+'
        r'(?:vs\.?|versus|contra|com|x)\s+'
        r'(?:de\s+|do\s+|da\s+)?'
        r'(\w+(?:\s+\w+)?)'
    ),
]

# Palavras que são períodos válidos (para filtrar falsos positivos)
_VALID_PERIODS = set(_MONTH_NAMES.keys()) | set(_RELATIVE_PERIODS.keys()) | {
    "passado", "passada", "atual",
}


def _detect_temporal_comparison(q_norm: str) -> Optional[StepPlan]:
    """
    Detecta: "vendas janeiro vs fevereiro", "comissão mês vs mês passado",
    "compare faturamento esse mês com mês passado"
    """
    for pattern in _TEMPORAL_PATTERNS:
        m = re.search(pattern, q_norm)
        if not m:
            continue

        domain = m.group(1)
        raw_a = m.group(2).strip()
        raw_b = m.group(3).strip()

        # Validar que pelo menos um é período real
        a_words = set(raw_a.split())
        b_words = set(raw_b.split())
        a_is_period = bool(a_words & _VALID_PERIODS)
        b_is_period = bool(b_words & _VALID_PERIODS)

        if not a_is_period and not b_is_period:
            # Nenhum é período → não é comparação temporal (pode ser entidade)
            continue

        intent = _domain_to_intent(domain)
        params_a, label_a = _resolve_period(raw_a)
        params_b, label_b = _resolve_period(raw_b)

        return StepPlan(
            steps=[
                {"intent": intent, "params": params_a, "label": label_a},
                {"intent": intent, "params": params_b, "label": label_b},
            ],
            merge_strategy="compare",
            presentation="side_by_side",
            original_question=q_norm,
        )

    return None


# ============================================================
# DETECTION: Comparação de Entidades
# ============================================================

_ENTITY_PATTERNS = [
    # "compare comissão do rogerio vs rafael"
    (
        r'compar[ae]\w*\s+(?:a\s+)?'
        r'(comiss[aã]o|vendas?|faturamento|pend[eê]ncias?)\s+'
        r'(?:do|da|de)\s+'
        r'(.+?)\s+'
        r'(?:vs\.?|versus|contra|com|x|e\s+(?:do|da|de)\s+)'
        r'\s*(?:do\s+|da\s+|de\s+)?'
        r'(.+?)(?:\s*[?.!]?\s*$)'
    ),
    # "comissão do rogerio vs rafael"
    (
        r'(comiss[aã]o|vendas?|faturamento|pend[eê]ncias?)\s+'
        r'(?:do|da|de)\s+'
        r'(.+?)\s+'
        r'(?:vs\.?|versus|contra|x)\s+'
        r'(?:do\s+|da\s+|de\s+)?'
        r'(.+?)(?:\s*[?.!]?\s*$)'
    ),
    # "vendas uberlândia vs ribeirão"
    (
        r'(comiss[aã]o|vendas?|faturamento|pend[eê]ncias?)\s+'
        r'(?:de\s+|da\s+|do\s+)?'
        r'(\w+(?:\s+\w+)?)\s+'
        r'(?:vs\.?|versus|contra|x)\s+'
        r'(?:de\s+|da\s+|do\s+)?'
        r'(\w+(?:\s+\w+)?)(?:\s*[?.!]?\s*$)'
    ),
]


def _detect_entity_comparison(q_norm: str) -> Optional[StepPlan]:
    """
    Detecta: "compare comissão do rogerio vs rafael",
    "vendas uberlândia vs ribeirão"
    """
    for pattern in _ENTITY_PATTERNS:
        m = re.search(pattern, q_norm)
        if not m:
            continue

        domain = m.group(1)
        raw_a = m.group(2).strip()
        raw_b = m.group(3).strip()

        # Rejeitar se parece período (temporal_comparison deve pegar)
        a_words = set(raw_a.lower().split())
        b_words = set(raw_b.lower().split())
        if (a_words & _VALID_PERIODS) and (b_words & _VALID_PERIODS):
            continue

        intent = _domain_to_intent(domain)
        entity_type = _classify_entities(raw_a, raw_b)

        return StepPlan(
            steps=[
                {"intent": intent, "params": {entity_type: raw_a.upper()}, "label": raw_a.title()},
                {"intent": intent, "params": {entity_type: raw_b.upper()}, "label": raw_b.title()},
            ],
            merge_strategy="compare",
            presentation="side_by_side",
            original_question=q_norm,
        )

    return None


# ============================================================
# DETECTION: Variação Temporal ("aumentaram?", "caíram?")
# ============================================================

_TREND_PATTERNS = [
    # "vendas aumentaram esse mês?", "comissão caiu?", "comissao aumentou?"
    # Stems curtos para pegar todas as conjugações: aumentou/aumentaram/aumentar
    (
        r'(comiss[aã]o|vendas?|faturamento|pend[eê]ncias?)\s+'
        r'(aument\w+|cai\w*|cresc\w+|diminu\w+|subi\w+|melhor\w+|pior\w+)'
    ),
    (
        r'(aument\w+|cai\w*|cresc\w+|diminu\w+|subi\w+|melhor\w+|pior\w+)\s+'
        r'(?:as?\s+|os?\s+)?'
        r'(comiss[aã]o|comissoes|vendas?|faturamento|pend[eê]ncias?)'
    ),
]


def _detect_trend(q_norm: str) -> Optional[StepPlan]:
    """
    Detecta perguntas de tendência: "vendas aumentaram?"
    Compara mês atual vs mês passado automaticamente.
    """
    for pattern in _TREND_PATTERNS:
        m = re.search(pattern, q_norm)
        if not m:
            continue

        groups = m.groups()
        # Determinar qual grupo é o domínio
        domain = groups[0] if not re.match(r'(aumenta|cai|crescer|diminui|subir|cair|melhor|pior)', groups[0]) else groups[1]

        intent = _domain_to_intent(domain)

        return StepPlan(
            steps=[
                {"intent": intent, "params": {"periodo": "mes_passado"}, "label": "Mês passado"},
                {"intent": intent, "params": {"periodo": "mes"}, "label": "Este mês"},
            ],
            merge_strategy="compare",
            presentation="side_by_side",
            original_question=q_norm,
        )

    return None


# ============================================================
# MAIN DETECTOR
# ============================================================

def detect_multistep(question: str, ctx=None) -> Optional[StepPlan]:
    """
    Detecta se a query é multi-step e retorna o plano.
    Retorna None se for query simples.

    Prioridade dos patterns:
    1. Comparação temporal (janeiro vs fevereiro)
    2. Comparação de entidades (rogerio vs rafael)
    3. Tendência/variação (vendas aumentaram?)
    """
    q = normalize(question)

    # Pattern 1: Comparação temporal
    plan = _detect_temporal_comparison(q)
    if plan:
        return plan

    # Pattern 2: Comparação entre entidades
    plan = _detect_entity_comparison(q)
    if plan:
        return plan

    # Pattern 3: Tendência (mês atual vs anterior)
    plan = _detect_trend(q)
    if plan:
        return plan

    return None


# ============================================================
# KPI EXTRACTION (genérico, funciona com qualquer handler)
# ============================================================

# Campos conhecidos como KPIs (chave → label bonito)
_KPI_FIELDS = {
    # Comissão
    "QTD_NOTAS", "VLR_VENDAS", "VLR_DEVOLUCAO", "VLR_LIQUIDO",
    "COM_VENDAS", "COM_DEVOLUCAO", "COM_LIQUIDA", "MARGEM_MEDIA",
    # Vendas
    "QTD_VENDAS", "FATURAMENTO", "TICKET_MEDIO", "COMISSAO_TOTAL",
    # Pendências
    "QTD_PEDIDOS", "QTD_ITENS", "VLR_PENDENTE",
    # Financeiro
    "QTD_TITULOS", "TOTAL_VENCIDO", "TOTAL_A_VENCER",
}


def extract_kpis_from_result(result: dict) -> dict:
    """
    Extrai KPIs de um resultado de handler.
    Tenta múltiplas estratégias para encontrar dados numéricos.
    """
    if not result:
        return {}

    kpis = {}

    # Estratégia 1: O resultado tem "_detail_data" com rows → agregar campos numéricos
    detail = result.get("_detail_data") or result.get("detail_data") or []
    if detail and isinstance(detail, list) and isinstance(detail[0], dict):
        # Se é ranking (poucas rows com campos agregados), pegar a soma
        # Se é detalhe (muitas rows), contar
        kpis["qtd_registros"] = len(detail)

        # Campos que devem ser MÉDIA (não soma): percentuais, tickets
        _AVERAGE_FIELDS = {"MARGEM_MEDIA", "TICKET_MEDIO"}

        # Agregar campos numéricos conhecidos
        numeric_sums = {}
        numeric_counts = {}
        for row in detail:
            for fld in _KPI_FIELDS:
                val = row.get(fld)
                if val is not None:
                    try:
                        numeric_sums.setdefault(fld, 0)
                        numeric_counts.setdefault(fld, 0)
                        numeric_sums[fld] += float(val or 0)
                        numeric_counts[fld] += 1
                    except (ValueError, TypeError):
                        pass

        # Aplicar média nos campos de percentual/ticket, soma nos demais
        for fld, total in numeric_sums.items():
            cnt = numeric_counts.get(fld, 1) or 1
            if fld in _AVERAGE_FIELDS:
                kpis[fld] = round(total / cnt, 2)
            else:
                kpis[fld] = total

    # Estratégia 2: Parsear KPIs da response text (fallback)
    response = result.get("response", "")
    if not kpis.get("FATURAMENTO") and "faturamento" in response.lower():
        m = re.search(r'R\$\s*([\d.,]+)', response)
        if m:
            try:
                val_str = m.group(1).replace(".", "").replace(",", ".")
                kpis["FATURAMENTO"] = float(val_str)
            except ValueError:
                pass

    kpis["query_results"] = result.get("query_results", 0)

    return kpis
