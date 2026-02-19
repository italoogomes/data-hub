"""
MMarra Data Hub - LLM Narrator.
Explica dados retornados de forma natural usando Groq.
Inclui funcoes de build_summary para cada dominio.
"""

import re

from src.core.config import USE_LLM_NARRATOR
from src.core.utils import fmt_brl
from src.llm.groq_client import pool_narrate, groq_request


# ============================================================
# NARRATOR SYSTEM PROMPT
# ============================================================

NARRATOR_SYSTEM = """Voce e um assistente de BI da MMarra Distribuidora Automotiva.
Voce recebeu dados de uma consulta ao banco e deve explicar de forma natural e inteligente.
REGRA ABSOLUTA: Responda DIRETAMENTE em portugues brasileiro. NUNCA pense em voz alta. NUNCA comece com Okay, Let me, The user, First, I need. Va direto ao ponto.

REGRAS:
1. Fale como um colega de trabalho experiente - direto, claro, com personalidade
2. Comece respondendo a pergunta principal, depois destaque o que chama atencao
3. Aponte problemas: pedidos atrasados, estoque baixo, valores concentrados
4. Sugira acoes praticas quando fizer sentido (ex: "pode valer ligar pro fornecedor")
5. Use numeros formatados (R$ 864.800, nao 864800.82)
6. Seja conciso - 3 a 6 frases no maximo, nao faca textao
7. Use **negrito** pra destacar numeros e pontos importantes
8. NAO repita os dados em formato de tabela - isso ja foi feito
9. NAO invente dados que nao estao no resumo
10. Se nao tiver nada relevante pra analisar, seja breve"""


# ============================================================
# NARRATE
# ============================================================

async def llm_narrate(question: str, data_summary: str, fallback_response: str) -> str:
    """Pede pro Groq explicar os dados de forma natural."""
    if not USE_LLM_NARRATOR or not pool_narrate.available:
        return fallback_response

    user_msg = f"""Pergunta do usuario: "{question}"

Dados retornados do banco:
{data_summary}

Explique esses dados de forma natural e analise o que chama atencao."""

    result = await groq_request(
        pool=pool_narrate,
        messages=[
            {"role": "system", "content": NARRATOR_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.6,
        max_tokens=400,
    )

    if not result or not result.get("content"):
        print(f"[NARRATOR] Groq falhou, usando fallback")
        return fallback_response

    text = result["content"].strip()
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    if not text or len(text) < 30:
        return fallback_response

    print(f"[NARRATOR] Groq OK ({len(text)} chars)")
    return text


# ============================================================
# BUILD SUMMARIES (para o narrator)
# ============================================================

def build_pendencia_summary(kpis_data: list, detail_data: list, params: dict) -> str:
    """Monta resumo estruturado dos dados de pendencia pra LLM narrar."""
    row = kpis_data[0] if kpis_data and isinstance(kpis_data[0], dict) else {}
    qtd_ped = int(row.get("QTD_PEDIDOS", 0) or 0)
    qtd_itens = int(row.get("QTD_ITENS", 0) or 0)
    vlr = float(row.get("VLR_PENDENTE", 0) or 0)

    lines = [f"Total: {qtd_ped} pedidos, {qtd_itens} itens, R$ {vlr:,.2f}"]

    if params.get("marca"):
        lines.append(f"Filtro: marca {params['marca']}")
    if params.get("fornecedor"):
        lines.append(f"Filtro: fornecedor {params['fornecedor']}")
    if params.get("comprador"):
        lines.append(f"Filtro: comprador {params['comprador']}")

    if detail_data:
        status_count = {}
        fornecedores = {}
        total_dias = 0
        max_dias = 0
        for item in detail_data:
            if not isinstance(item, dict):
                continue
            st = item.get("STATUS_ENTREGA", "?")
            status_count[st] = status_count.get(st, 0) + 1
            forn = str(item.get("FORNECEDOR", ""))[:30]
            if forn:
                fornecedores[forn] = fornecedores.get(forn, 0) + float(item.get("VLR_PENDENTE", 0) or 0)
            dias = int(float(item.get("DIAS_ABERTO", 0) or 0))
            total_dias += dias
            max_dias = max(max_dias, dias)

        if status_count:
            status_str = ", ".join(f"{k}: {v}" for k, v in sorted(status_count.items(), key=lambda x: -x[1]))
            lines.append(f"Status: {status_str}")
        if qtd_itens > 0:
            lines.append(f"Media dias aberto: {total_dias // max(qtd_itens, 1)} dias, maximo: {max_dias} dias")
        atrasados = status_count.get("ATRASADO", 0)
        if atrasados > 0:
            pct = round(atrasados / max(qtd_itens, 1) * 100)
            lines.append(f"ATENCAO: {atrasados} itens atrasados ({pct}%)")
        sem_prev = status_count.get("SEM PREVISAO", 0)
        if sem_prev > 0:
            lines.append(f"{sem_prev} itens sem previsao de entrega")
        if fornecedores:
            top_forn = sorted(fornecedores.items(), key=lambda x: -x[1])[:3]
            forn_str = ", ".join(f"{f}: R$ {v:,.2f}" for f, v in top_forn)
            lines.append(f"Maiores fornecedores: {forn_str}")

    return "\n".join(lines)


def build_vendas_summary(kpi_row: dict, top_vendedores: list, periodo_nome: str) -> str:
    """Monta resumo de vendas pra LLM narrar."""
    qtd = int(kpi_row.get("QTD_VENDAS", 0) or 0)
    fat = float(kpi_row.get("FATURAMENTO", 0) or 0)
    ticket = float(kpi_row.get("TICKET_MEDIO", 0) or 0)
    margem = float(kpi_row.get("MARGEM_MEDIA", 0) or 0)
    comissao = float(kpi_row.get("COMISSAO_TOTAL", 0) or 0)

    lines = [
        f"Periodo: {periodo_nome}",
        f"Total: {qtd} notas de venda, faturamento R$ {fat:,.2f}, ticket medio R$ {ticket:,.2f}",
    ]
    if margem > 0:
        lines.append(f"Margem media: {margem:.1f}%")
    if comissao > 0:
        lines.append(f"Comissao total: R$ {comissao:,.2f}")

    if top_vendedores:
        top_str = ", ".join(
            f"{r.get('VENDEDOR','?')}: R$ {float(r.get('FATURAMENTO',0) or 0):,.2f} ({r.get('QTD',0)} notas)"
            for r in top_vendedores[:5] if isinstance(r, dict)
        )
        lines.append(f"Top vendedores: {top_str}")
        if len(top_vendedores) >= 2 and fat > 0:
            top1_fat = float(top_vendedores[0].get("FATURAMENTO", 0) or 0)
            pct = round(top1_fat / fat * 100)
            if pct > 40:
                lines.append(f"CONCENTRACAO: {top_vendedores[0].get('VENDEDOR','?')} responde por {pct}% do faturamento")

    return "\n".join(lines)


def build_estoque_summary(data: list, params: dict) -> str:
    """Monta resumo de estoque pra LLM narrar."""
    lines = []
    if params.get("codprod") or params.get("produto_nome"):
        if data:
            row = data[0] if isinstance(data[0], dict) else {}
            est = int(float(row.get("ESTOQUE", 0) or 0))
            est_min = int(float(row.get("ESTMIN", 0) or 0))
            lines.append(f"Produto: {row.get('CODPROD','?')} - {row.get('PRODUTO','?')} ({row.get('MARCA','')})")
            lines.append(f"Estoque: {est} unidades, minimo: {est_min}")
            if est <= est_min:
                lines.append("ALERTA: Estoque abaixo do minimo!")
            if len(data) > 1:
                for r in data:
                    if isinstance(r, dict):
                        lines.append(f"  {r.get('EMPRESA','?')}: {r.get('ESTOQUE',0)} un")
    else:
        lines.append(f"{len(data)} produtos com estoque critico (abaixo do minimo)")
        zerados = sum(1 for r in data if isinstance(r, dict) and int(float(r.get("ESTOQUE", 0) or 0)) == 0)
        if zerados:
            lines.append(f"ALERTA: {zerados} produtos com estoque ZERADO!")
        if data:
            marcas = {}
            for r in data:
                if isinstance(r, dict):
                    m = r.get("MARCA", "SEM MARCA")
                    marcas[m] = marcas.get(m, 0) + 1
            top_marcas = sorted(marcas.items(), key=lambda x: -x[1])[:5]
            lines.append(f"Marcas mais afetadas: {', '.join(f'{m}: {c}' for m, c in top_marcas)}")

    return "\n".join(lines)
