"""
MMarra Data Hub - Formatadores de Comparação.

Formata resultados multi-step lado a lado para o chat.
Usa Markdown (compatível com o frontend existente).
"""

from src.core.utils import fmt_brl, fmt_num


# ============================================================
# KPI LABELS (chave do banco → label bonito)
# ============================================================

_KPI_LABELS = {
    # Comissão
    "QTD_NOTAS": "Notas",
    "VLR_VENDAS": "Vendas",
    "VLR_DEVOLUCAO": "Devoluções",
    "VLR_LIQUIDO": "Líquido",
    "COM_VENDAS": "Com. Vendas",
    "COM_DEVOLUCAO": "Com. Devoluções",
    "COM_LIQUIDA": "Com. Líquida",
    "MARGEM_MEDIA": "Margem Média",
    # Vendas
    "QTD_VENDAS": "Notas",
    "FATURAMENTO": "Faturamento",
    "TICKET_MEDIO": "Ticket Médio",
    "COMISSAO_TOTAL": "Comissão",
    # Pendências
    "QTD_PEDIDOS": "Pedidos",
    "QTD_ITENS": "Itens",
    "VLR_PENDENTE": "Vlr Pendente",
    # Financeiro
    "QTD_TITULOS": "Títulos",
    "TOTAL_VENCIDO": "Vencido",
    "TOTAL_A_VENCER": "A Vencer",
    # Genéricos
    "qtd_registros": "Registros",
    "query_results": "Total",
}

# Campos que representam valores monetários (para fmt_brl)
_MONETARY_FIELDS = {
    "VLR_VENDAS", "VLR_DEVOLUCAO", "VLR_LIQUIDO",
    "COM_VENDAS", "COM_DEVOLUCAO", "COM_LIQUIDA",
    "FATURAMENTO", "TICKET_MEDIO", "COMISSAO_TOTAL",
    "VLR_PENDENTE", "TOTAL_VENCIDO", "TOTAL_A_VENCER",
}

# Campos de percentual
_PERCENT_FIELDS = {"MARGEM_MEDIA"}

# Campos de contagem inteira
_COUNT_FIELDS = {
    "QTD_NOTAS", "QTD_VENDAS", "QTD_PEDIDOS", "QTD_ITENS",
    "QTD_TITULOS", "qtd_registros", "query_results",
}

# Ordem de exibição preferencial dos KPIs
_KPI_ORDER = [
    "QTD_NOTAS", "QTD_VENDAS", "QTD_PEDIDOS",
    "FATURAMENTO", "VLR_VENDAS", "VLR_DEVOLUCAO", "VLR_LIQUIDO", "VLR_PENDENTE",
    "COM_LIQUIDA", "COM_VENDAS", "COM_DEVOLUCAO", "COMISSAO_TOTAL",
    "TICKET_MEDIO", "MARGEM_MEDIA",
    "TOTAL_VENCIDO", "TOTAL_A_VENCER", "QTD_TITULOS",
]


def _format_value(key: str, val) -> str:
    """Formata valor baseado no tipo do campo."""
    if val is None or val == 0:
        return "-"
    if key in _MONETARY_FIELDS:
        return fmt_brl(val)
    if key in _PERCENT_FIELDS:
        return f"{float(val):.1f}%"
    if key in _COUNT_FIELDS:
        return fmt_num(val)
    try:
        f = float(val)
        return f"{f:,.2f}" if f != int(f) else fmt_num(int(f))
    except (ValueError, TypeError):
        return str(val)


def _format_diff(key: str, val_a, val_b) -> str:
    """Formata a diferença entre dois valores com cor e seta."""
    try:
        a = float(val_a or 0)
        b = float(val_b or 0)
    except (ValueError, TypeError):
        return "-"

    if a == 0 and b == 0:
        return "-"

    diff = b - a
    if a != 0:
        pct = (diff / abs(a)) * 100
        pct_str = f" ({pct:+.1f}%)"
    else:
        pct_str = ""

    # Seta e emoji para direção
    if diff > 0:
        arrow = "↑"
    elif diff < 0:
        arrow = "↓"
    else:
        return "="

    if key in _MONETARY_FIELDS:
        diff_str = fmt_brl(abs(diff))
    elif key in _PERCENT_FIELDS:
        diff_str = f"{abs(diff):.1f}pp"
        pct_str = ""  # Percentuais usam pontos percentuais
    elif key in _COUNT_FIELDS:
        diff_str = fmt_num(abs(int(diff)))
    else:
        diff_str = f"{abs(diff):,.2f}"

    return f"{arrow} {diff_str}{pct_str}"


# ============================================================
# MAIN FORMATTER
# ============================================================

def format_comparison(step_results: list, plan) -> dict:
    """
    Formata resultado de comparação lado a lado em Markdown.

    Args:
        step_results: lista de StepResult com label, data, kpis
        plan: StepPlan original

    Returns:
        dict compatível com response do SmartAgent
    """
    if not step_results or len(step_results) < 2:
        return None

    a = step_results[0]
    b = step_results[1]

    # Coletar KPIs presentes em pelo menos um dos resultados
    all_keys = []
    seen = set()
    # Usar ordem preferencial
    for key in _KPI_ORDER:
        if key in a.kpis or key in b.kpis:
            if key not in seen:
                all_keys.append(key)
                seen.add(key)
    # Adicionar chaves restantes não na ordem preferencial
    for key in list(a.kpis.keys()) + list(b.kpis.keys()):
        if key not in seen and key in _KPI_LABELS:
            all_keys.append(key)
            seen.add(key)

    # Filtrar chaves sem dados úteis
    all_keys = [k for k in all_keys if
                (a.kpis.get(k) or 0) != 0 or (b.kpis.get(k) or 0) != 0]

    if not all_keys:
        return None

    # Construir resposta Markdown
    lines = []
    lines.append(f"**Comparação: {a.label} vs {b.label}**\n")

    # Tabela Markdown
    lines.append(f"| Métrica | {a.label} | {b.label} | Variação |")
    lines.append("|---------|---------|---------|----------|")

    for key in all_keys:
        label = _KPI_LABELS.get(key, key)
        val_a = a.kpis.get(key, 0)
        val_b = b.kpis.get(key, 0)
        formatted_a = _format_value(key, val_a)
        formatted_b = _format_value(key, val_b)
        diff = _format_diff(key, val_a, val_b)
        lines.append(f"| {label} | {formatted_a} | {formatted_b} | {diff} |")

    lines.append("")

    # Resumo textual das diferenças mais relevantes
    summary = _build_summary(a, b, all_keys)
    if summary:
        lines.append(summary)

    response = "\n".join(lines)

    return {
        "response": response,
        "tipo": "comparacao",
        "query_results": (a.kpis.get("query_results", 0) or 0) + (b.kpis.get("query_results", 0) or 0),
        "_detail_data": (a.data or [])[:5] + (b.data or [])[:5],
    }


def _build_summary(a, b, keys: list) -> str:
    """Constrói resumo textual das variações mais relevantes."""
    insights = []

    # Procurar variação mais significativa em campos monetários
    best_key = None
    best_pct = 0
    for key in keys:
        if key not in _MONETARY_FIELDS:
            continue
        try:
            va = float(a.kpis.get(key, 0) or 0)
            vb = float(b.kpis.get(key, 0) or 0)
            if va != 0:
                pct = abs((vb - va) / va) * 100
                if pct > best_pct:
                    best_pct = pct
                    best_key = key
        except (ValueError, TypeError):
            pass

    if best_key and best_pct >= 1:
        va = float(a.kpis.get(best_key, 0) or 0)
        vb = float(b.kpis.get(best_key, 0) or 0)
        label = _KPI_LABELS.get(best_key, best_key)
        diff = vb - va
        direction = "aumento" if diff > 0 else "queda"
        insights.append(
            f"**{label}**: {direction} de **{best_pct:.1f}%** "
            f"({fmt_brl(va)} → {fmt_brl(vb)})"
        )

    # Variação de margem (se presente)
    if "MARGEM_MEDIA" in a.kpis and "MARGEM_MEDIA" in b.kpis:
        ma = float(a.kpis.get("MARGEM_MEDIA", 0) or 0)
        mb = float(b.kpis.get("MARGEM_MEDIA", 0) or 0)
        if abs(mb - ma) >= 0.5:
            direction = "subiu" if mb > ma else "caiu"
            insights.append(f"Margem {direction}: {ma:.1f}% → {mb:.1f}%")

    if insights:
        return "**Destaques:** " + " | ".join(insights)
    return ""
