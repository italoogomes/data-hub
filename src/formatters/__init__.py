"""
MMarra Data Hub - Formatadores de Resposta.
Formata dados de pendência, vendas, estoque em Markdown/tabelas.
Extraído de smart_agent.py na refatoração modular.
"""

import re
import os
from pathlib import Path
from src.core.utils import fmt_brl, fmt_num, trunc
from src.agent.scoring import COLUMN_LABELS, COLUMN_MAX_WIDTH


def detect_aggregation_view(question_norm: str) -> str | None:
    """Detecta se a pergunta pede uma visao agregada em vez de listagem.

    Returns:
        "comprador_marca" - quem compra marca X
        "fornecedor_marca" - quem fornece marca X
        None - pergunta normal (listagem)
    """
    q = question_norm.lower()

    # "quem compra/e o comprador/e responsavel pela marca X"
    if re.search(r'quem\s+(compra|e\s+o?\s*comprador|e\s+responsavel)', q):
        return "comprador_marca"
    if re.search(r'comprador(es?)?\s+(da|de|do)\s+', q):
        return "comprador_marca"
    if re.search(r'responsavel\s+(pela|pela\s+marca|pelas?\s+compras?\s+d)', q):
        return "comprador_marca"

    # "quem fornece/e o fornecedor da marca X"
    if re.search(r'quem\s+(fornece|e\s+o?\s*fornecedor|vende|entrega)', q):
        return "fornecedor_marca"
    if re.search(r'fornecedor(es?)?\s+(da|de|do)\s+marca', q):
        return "fornecedor_marca"

    # "fornecedor da SABO" sem "pedido/pendencia" = quem fornece
    if re.search(r'fornecedor(es?)?\s+(da|de|do)\s+\w+', q) and not re.search(r'(pedido|pendencia|pend)', q):
        return "fornecedor_marca"

    return None


def format_comprador_marca(detail_data: list, marca: str) -> str:
    """Formata resposta 'quem compra marca X' agrupando por COMPRADOR."""
    from collections import defaultdict
    compradores = defaultdict(lambda: {"pedidos": set(), "itens": 0, "valor": 0.0})

    for r in detail_data:
        if not isinstance(r, dict):
            continue
        comp = r.get("COMPRADOR") or "SEM COMPRADOR"
        compradores[comp]["pedidos"].add(str(r.get("PEDIDO", "")))
        compradores[comp]["itens"] += 1
        compradores[comp]["valor"] += float(r.get("VLR_PENDENTE", 0) or 0)

    if not compradores:
        return f"Nao encontrei pedidos pendentes da marca {marca}."

    sorted_comp = sorted(compradores.items(), key=lambda x: -x[1]["valor"])

    response = f"\U0001f3f7\ufe0f **Comprador(es) da marca {marca}:**\n\n"
    response += "| Comprador | Pedidos | Itens | Valor Pendente |\n|---|---|---|---|\n"
    for comp, data in sorted_comp:
        response += f"| {comp} | {len(data['pedidos'])} | {data['itens']} | R$ {fmt_num(data['valor'])} |\n"

    if len(sorted_comp) == 1:
        response += f"\n**{sorted_comp[0][0]}** e o comprador responsavel pela marca {marca}."

    return response


def format_fornecedor_marca(detail_data: list, marca: str) -> str:
    """Formata resposta 'quem fornece marca X' agrupando por FORNECEDOR."""
    from collections import defaultdict
    fornecedores = defaultdict(lambda: {"pedidos": set(), "itens": 0, "valor": 0.0})

    for r in detail_data:
        if not isinstance(r, dict):
            continue
        forn = r.get("FORNECEDOR") or "?"
        fornecedores[forn]["pedidos"].add(str(r.get("PEDIDO", "")))
        fornecedores[forn]["itens"] += 1
        fornecedores[forn]["valor"] += float(r.get("VLR_PENDENTE", 0) or 0)

    if not fornecedores:
        return f"Nao encontrei fornecedores com pedidos pendentes da marca {marca}."

    sorted_forn = sorted(fornecedores.items(), key=lambda x: -x[1]["valor"])

    response = f"\U0001f3ed **Fornecedor(es) da marca {marca}:**\n\n"
    response += "| Fornecedor | Pedidos | Itens | Valor Pendente |\n|---|---|---|---|\n"
    for forn, data in sorted_forn:
        response += f"| {forn} | {len(data['pedidos'])} | {data['itens']} | R$ {fmt_num(data['valor'])} |\n"

    return response


def format_pendencia_response(kpis_data, detail_data, description, params, view_mode="pedidos", extra_columns=None):
    if not kpis_data:
        filtro = params.get("marca") or params.get("fornecedor") or params.get("empresa") or ""
        return f"Nao encontrei pedidos pendentes{' para ' + filtro if filtro else ''}. Verifique se o nome esta correto."

    row = kpis_data[0] if isinstance(kpis_data[0], dict) else {}
    qtd_ped = int(row.get("QTD_PEDIDOS", 0) or 0)
    qtd_itens = int(row.get("QTD_ITENS", 0) or 0)
    vlr = float(row.get("VLR_PENDENTE", 0) or 0)

    if qtd_ped == 0:
        filtro = params.get("marca") or params.get("fornecedor") or ""
        return f"Nao encontrei pedidos pendentes{' para ' + filtro if filtro else ''}."

    lines = []
    lines.append(f"\U0001f4e6 **{description.title()}**\n")
    s_ped = "s" if qtd_ped > 1 else ""
    s_it = "ns" if qtd_itens > 1 else "m"
    lines.append(f"Voce tem **{fmt_num(qtd_ped)} pedido{s_ped}** pendente{s_ped}, com **{fmt_num(qtd_itens)} ite{s_it}** e valor total de **{fmt_brl(vlr)}**.\n")

    if detail_data:
        if view_mode == "itens":
            # Colunas base
            has_aplic = any(item.get("APLICACAO") for item in detail_data[:12] if isinstance(item, dict))
            base_cols = ["PEDIDO", "CODPROD", "PRODUTO"]
            base_cols.append("APLICACAO" if has_aplic else "MARCA")

            # Inserir extras ANTES das colunas numericas
            if extra_columns:
                for ec in extra_columns:
                    if ec not in base_cols:
                        base_cols.append(ec)

            base_cols.extend(["QTD_PENDENTE", "VLR_PENDENTE", "STATUS_ENTREGA"])
            visible_cols = base_cols

            # Mensagem de colunas extras
            if extra_columns:
                added_labels = [COLUMN_LABELS.get(c, c) for c in extra_columns]
                lines.append(f"\u2705 Coluna{'s' if len(added_labels)>1 else ''} extra{'s' if len(added_labels)>1 else ''}: **{', '.join(added_labels)}**\n")

            # Header
            headers = [COLUMN_LABELS.get(c, c) for c in visible_cols]
            lines.append("**Itens pendentes:**\n")
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---" for _ in visible_cols]) + "|")

            # Rows
            for item in detail_data[:12]:
                if not isinstance(item, dict):
                    continue
                cells = []
                for c in visible_cols:
                    val = item.get(c, "")
                    if val is None: val = ""
                    val = str(val)
                    max_w = COLUMN_MAX_WIDTH.get(c, 40)
                    if len(val) > max_w:
                        val = val[:max_w-1] + "\u2026"
                    if "VLR" in c:
                        try: val = fmt_brl(float(val))
                        except: pass
                    elif c in ("QTD_PENDENTE", "QTD_PEDIDA", "QTD_ATENDIDA", "DIAS_ABERTO"):
                        try: val = str(int(float(val or 0)))
                        except: pass
                    cells.append(val)
                lines.append("| " + " | ".join(cells) + " |")

            if len(detail_data) > 12:
                lines.append(f"\n*...e mais {len(detail_data) - 12} itens.*\n")
        else:
            pedidos = {}
            for item in detail_data:
                if not isinstance(item, dict): continue
                ped = item.get("PEDIDO", "?")
                if ped not in pedidos:
                    pedidos[ped] = {
                        "PEDIDO": ped,
                        "FORNECEDOR": str(item.get("FORNECEDOR",""))[:30],
                        "DT_PEDIDO": item.get("DT_PEDIDO",""),
                        "STATUS_ENTREGA": item.get("STATUS_ENTREGA","?"),
                        "_itens": 0, "_valor": 0.0
                    }
                    if extra_columns:
                        for ec in extra_columns:
                            pedidos[ped][ec] = str(item.get(ec, "") or "")
                pedidos[ped]["_itens"] += 1
                pedidos[ped]["_valor"] += float(item.get("VLR_PENDENTE", 0) or 0)

            # Colunas base
            base_cols = ["PEDIDO", "FORNECEDOR", "DT_PEDIDO"]
            if extra_columns:
                for ec in extra_columns:
                    if ec not in base_cols:
                        base_cols.append(ec)
            base_cols.extend(["_itens", "_valor", "STATUS_ENTREGA"])

            label_override = {"_itens": "Itens", "_valor": "Valor Pendente"}
            headers = [label_override.get(c, COLUMN_LABELS.get(c, c)) for c in base_cols]

            if extra_columns:
                added_labels = [COLUMN_LABELS.get(c, c) for c in extra_columns]
                lines.append(f"\u2705 Coluna{'s' if len(added_labels)>1 else ''} extra{'s' if len(added_labels)>1 else ''}: **{', '.join(added_labels)}**\n")

            lines.append("**Pedidos:**\n")
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join(["---" for _ in base_cols]) + "|")

            for pd in list(pedidos.values())[:10]:
                cells = []
                for c in base_cols:
                    if c == "_valor": cells.append(fmt_brl(pd["_valor"]))
                    elif c == "_itens": cells.append(str(pd["_itens"]))
                    else:
                        val = str(pd.get(c, ""))
                        max_w = COLUMN_MAX_WIDTH.get(c, 40)
                        if len(val) > max_w: val = val[:max_w-1] + "\u2026"
                        cells.append(val)
                lines.append("| " + " | ".join(cells) + " |")

            if len(pedidos) > 10:
                lines.append(f"\n*...e mais {len(pedidos) - 10} pedidos.*\n")

    lines.append(f"\n\U0001f4e5 **Quer que eu gere um arquivo Excel com todos os {fmt_num(qtd_itens)} itens?**")
    return "\n".join(lines)


def format_vendas_response(kpis_data, periodo_nome):
    qtd = int(kpis_data.get("QTD_VENDAS", 0) or 0)
    fat = float(kpis_data.get("FATURAMENTO", 0) or 0)
    vlr_vendas = float(kpis_data.get("VLR_VENDAS", 0) or 0)
    vlr_dev = float(kpis_data.get("VLR_DEVOLUCAO", 0) or 0)
    ticket = float(kpis_data.get("TICKET_MEDIO", 0) or 0)
    margem = float(kpis_data.get("MARGEM_MEDIA", 0) or 0)
    comissao = float(kpis_data.get("COMISSAO_TOTAL", 0) or 0)
    if qtd == 0 and vlr_vendas == 0:
        return f"Nao encontrei vendas para o periodo **{periodo_nome}**."
    lines = [
        f"\U0001f4ca **Vendas - {periodo_nome.title()}**\n",
    ]
    if vlr_dev > 0:
        lines.append(f"**{fmt_num(qtd)}** notas | Vendas brutas **{fmt_brl(vlr_vendas)}** | Devoluções **{fmt_brl(vlr_dev)}** | Líquido **{fmt_brl(fat)}**")
    else:
        lines.append(f"**{fmt_num(qtd)}** notas | **{fmt_brl(fat)}** faturamento | Ticket medio **{fmt_brl(ticket)}**")
    if margem > 0:
        lines.append(f"Margem media: **{margem:.1f}%** | Comissao total: **{fmt_brl(comissao)}**")
    lines.append("")
    return "\n".join(lines)


def format_estoque_response(data, params):
    if not data:
        filtro = params.get("codprod") or params.get("produto_nome") or params.get("marca") or ""
        return f"Nao encontrei informacoes de estoque{' para ' + str(filtro) if filtro else ''}."
    lines = []
    if params.get("codprod") or params.get("produto_nome"):
        row = data[0] if isinstance(data[0], dict) else {}
        lines.append(f"\U0001f4e6 **Estoque do produto {row.get('CODPROD','?')}**\n")
        lines.append(f"**{row.get('PRODUTO','?')}**" + (f" ({row.get('MARCA','')})" if row.get('MARCA') else ""))
        if row.get('APLICACAO'):
            lines.append(f"Aplicacao: {row.get('APLICACAO','')}")
        lines.append(f"Estoque atual: **{fmt_num(row.get('ESTOQUE',0))}** unidades")
        if row.get('ESTMIN'):
            lines.append(f"Estoque minimo: **{fmt_num(row.get('ESTMIN',0))}**")
            if int(float(row.get('ESTOQUE',0) or 0)) <= int(float(row.get('ESTMIN',0) or 0)):
                lines.append("\u26a0\ufe0f **Abaixo do estoque minimo!**")
        if len(data) > 1:
            lines.append("\n**Por empresa:**\n| Empresa | Estoque | Est. Minimo |\n|---------|---------|-------------|")
            for r in data[:10]:
                if isinstance(r, dict):
                    lines.append(f"| {str(r.get('EMPRESA','?'))[:25]} | {fmt_num(r.get('ESTOQUE',0))} | {fmt_num(r.get('ESTMIN',0))} |")
    else:
        lines.append(f"\u26a0\ufe0f **Estoque Critico** - {len(data)} produto{'s' if len(data)>1 else ''}\n")
        lines.append("| CodProd | Produto | Marca | Estoque | Est. Min. |\n|---------|---------|-------|---------|-----------|")
        for r in data[:15]:
            if isinstance(r, dict):
                lines.append(f"| {r.get('CODPROD','?')} | {str(r.get('PRODUTO',''))[:30]} | {str(r.get('MARCA',''))[:15]} | {fmt_num(r.get('ESTOQUE',0))} | {fmt_num(r.get('ESTMIN',0))} |")
        if len(data) > 15:
            lines.append(f"\n*...e mais {len(data)-15} produtos.*")
    return "\n".join(lines)


# ============================================================
# FINANCEIRO
# ============================================================

def format_financeiro_response(kpis, detail_data, tipo, description, params):
    """Formata resposta de contas a pagar/receber/fluxo."""
    if not kpis:
        return f"Nao encontrei dados financeiros para o periodo solicitado."

    row = kpis if isinstance(kpis, dict) else (kpis[0] if kpis else {})
    qtd = int(row.get("QTD_TITULOS", 0) or 0)
    vlr_total = float(row.get("VLR_TOTAL", 0) or 0)
    vlr_vencido = float(row.get("VLR_VENCIDO", 0) or 0)
    vlr_a_vencer = float(row.get("VLR_A_VENCER", 0) or 0)

    lines = []

    if tipo == "fluxo":
        entradas = float(row.get("ENTRADAS", 0) or 0)
        saidas = float(row.get("SAIDAS", 0) or 0)
        saldo = float(row.get("SALDO", 0) or 0)
        lines.append(f"\U0001f4b0 **Fluxo de Caixa - {description}**\n")
        lines.append(f"\u2b06\ufe0f Entradas: **{fmt_brl(entradas)}**")
        lines.append(f"\u2b07\ufe0f Saidas: **{fmt_brl(saidas)}**")
        emoji_saldo = "\u2705" if saldo >= 0 else "\U0001f534"
        lines.append(f"{emoji_saldo} Saldo: **{fmt_brl(saldo)}**\n")

        if detail_data:
            lines.append("| Parceiro | Tipo | Vencimento | Valor |\n|----------|------|------------|-------|")
            for r in detail_data[:15]:
                if not isinstance(r, dict):
                    continue
                parc = trunc(str(r.get("PARCEIRO", "?")), 25)
                tp = "Receber" if str(r.get("RECDESP", "")) == "1" else "Pagar"
                venc = r.get("DTVENC", "?")
                vlr = fmt_brl(float(r.get("VLRDESDOB", 0) or 0))
                lines.append(f"| {parc} | {tp} | {venc} | {vlr} |")
            if len(detail_data) > 15:
                lines.append(f"\n*...e mais {len(detail_data) - 15} titulos.*")
    else:
        tipo_label = "Contas a Pagar" if tipo == "pagar" else "Contas a Receber"
        emoji = "\U0001f4c9" if tipo == "pagar" else "\U0001f4c8"
        lines.append(f"{emoji} **{tipo_label} - {description}**\n")
        s = "s" if qtd > 1 else ""
        lines.append(f"**{fmt_num(qtd)}** titulo{s} | Total: **{fmt_brl(vlr_total)}**")
        if vlr_vencido > 0:
            lines.append(f"\U0001f534 Vencido: **{fmt_brl(vlr_vencido)}** | \u2705 A vencer: **{fmt_brl(vlr_a_vencer)}**")
        lines.append("")

        if detail_data:
            lines.append("| Parceiro | Vencimento | Valor | Dias | Status |\n|----------|------------|-------|------|--------|")
            for r in detail_data[:15]:
                if not isinstance(r, dict):
                    continue
                parc = trunc(str(r.get("PARCEIRO", "?")), 25)
                venc = r.get("DTVENC", "?")
                vlr = fmt_brl(float(r.get("VLRDESDOB", 0) or 0))
                dias = int(r.get("DIAS_VENCIDO", 0) or 0)
                dias_str = f"{dias}d atraso" if dias > 0 else (f"{abs(dias)}d" if dias < 0 else "hoje")
                status = r.get("STATUS", "?")
                lines.append(f"| {parc} | {venc} | {vlr} | {dias_str} | {status} |")
            if len(detail_data) > 15:
                lines.append(f"\n*...e mais {len(detail_data) - 15} titulos.*")

    lines.append(f"\n\U0001f4e5 **Quer que eu gere um arquivo Excel com todos os {fmt_num(qtd)} titulos?**")
    return "\n".join(lines)


def format_inadimplencia_response(kpis, detail_data, description, params):
    """Formata resposta de inadimplência (clientes devedores)."""
    if not kpis:
        return "Nao encontrei clientes inadimplentes para o filtro solicitado."

    row = kpis if isinstance(kpis, dict) else (kpis[0] if kpis else {})
    qtd_clientes = int(row.get("QTD_CLIENTES", 0) or 0)
    vlr_total = float(row.get("VLR_INADIMPLENTE", 0) or 0)
    dias_medio = int(row.get("DIAS_MEDIO_ATRASO", 0) or 0)

    if qtd_clientes == 0:
        return f"Nenhum cliente inadimplente encontrado. \u2705"

    lines = []
    lines.append(f"\u26a0\ufe0f **Inadimplencia - {description}**\n")
    s = "s" if qtd_clientes > 1 else ""
    lines.append(f"**{fmt_num(qtd_clientes)}** cliente{s} inadimplente{s} | Total: **{fmt_brl(vlr_total)}** | Atraso medio: **{dias_medio} dias**\n")

    if detail_data:
        lines.append("| Cliente | Titulos | Valor Devido | Maior Atraso |\n|---------|---------|-------------|-------------|")
        for r in detail_data[:15]:
            if not isinstance(r, dict):
                continue
            parc = trunc(str(r.get("PARCEIRO", "?")), 30)
            qtd_t = int(r.get("QTD_TITULOS", 0) or 0)
            vlr = fmt_brl(float(r.get("VLR_INADIMPLENTE", 0) or 0))
            dias = int(r.get("MAIOR_ATRASO", 0) or 0)
            lines.append(f"| {parc} | {qtd_t} | {vlr} | {dias} dias |")
        if len(detail_data) > 15:
            lines.append(f"\n*...e mais {len(detail_data) - 15} clientes.*")

    lines.append(f"\n\U0001f4e5 **Quer que eu gere um arquivo Excel com o detalhe completo?**")
    return "\n".join(lines)


# ============================================================
# COMISSAO
# ============================================================

def format_comissao_response(kpis, detail_data, view, description, params, por_empresa=False):
    """Formata resposta de comissão de vendedores (VLRNOTA p/ faturado, AD_VLRBASECOMINT p/ base comissao)."""
    if not kpis:
        return "Nao encontrei dados de comissao para o periodo solicitado."

    row = kpis if isinstance(kpis, dict) else (kpis[0] if kpis else {})
    qtd_notas = int(row.get("QTD_NOTAS", 0) or 0)
    vlr_faturado = float(row.get("VLR_FATURADO", 0) or 0)
    vlr_devolucao = float(row.get("VLR_DEVOLUCAO", 0) or 0)
    vlr_liquido = float(row.get("VLR_LIQUIDO", 0) or 0)
    base_comissao = float(row.get("BASE_COMISSAO", 0) or 0)
    com_vendas = float(row.get("COM_VENDAS", 0) or 0)
    com_devolucao = float(row.get("COM_DEVOLUCAO", 0) or 0)
    com_liquida = float(row.get("COM_LIQUIDA", 0) or 0)
    margem_media = float(row.get("MARGEM_MEDIA", 0) or 0)

    if qtd_notas == 0:
        filtro = params.get("vendedor") or params.get("empresa") or ""
        return f"Nao encontrei vendas com comissao{' para ' + filtro if filtro else ''} no periodo."

    lines = []
    lines.append(f"\U0001f4b5 **Comissao - {description}**\n")
    s = "s" if qtd_notas > 1 else ""
    lines.append(f"**{fmt_num(qtd_notas)}** nota{s} | Faturado: **{fmt_brl(vlr_faturado)}**")
    if vlr_devolucao > 0:
        lines.append(f"\U0001f534 Devoluções: **{fmt_brl(vlr_devolucao)}** | Liquido: **{fmt_brl(vlr_liquido)}**")
    lines.append(f"Base comissao: **{fmt_brl(base_comissao)}**")
    lines.append(f"Comissao: **{fmt_brl(com_vendas)}**" + (f" - Devol: **{fmt_brl(com_devolucao)}** = Liquida: **{fmt_brl(com_liquida)}**" if com_devolucao > 0 else ""))
    lines.append(f"Margem media: **{margem_media:.1f}%**\n")

    if detail_data:
        if view == "ranking":
            if por_empresa:
                lines.append("| Vendedor | Empresa | Notas | Faturado | Devol. | Liquido | Base Com. | Com. Liq. | Margem | Aliq. |\n|----------|---------|-------|----------|--------|---------|-----------|-----------|--------|-------|")
            else:
                lines.append("| Vendedor | Notas | Faturado | Devol. | Liquido | Base Com. | Com. Liq. | Margem | Aliq. |\n|----------|-------|----------|--------|---------|-----------|-----------|--------|-------|")
            for r in detail_data[:20]:
                if not isinstance(r, dict):
                    continue
                vend = trunc(str(r.get("VENDEDOR", "?")), 18)
                notas = int(r.get("QTD_NOTAS", 0) or 0)
                faturado = fmt_brl(float(r.get("VLR_FATURADO", 0) or 0))
                devol = fmt_brl(float(r.get("VLR_DEVOLUCAO", 0) or 0))
                liq = fmt_brl(float(r.get("VLR_LIQUIDO", 0) or 0))
                base_com = fmt_brl(float(r.get("BASE_COMISSAO", 0) or 0))
                com_liq = fmt_brl(float(r.get("COM_LIQUIDA", 0) or 0))
                mg = float(r.get("MARGEM_MEDIA", 0) or 0)
                aliq = float(r.get("ALIQ_MEDIA", 0) or 0)
                if por_empresa:
                    emp = trunc(str(r.get("EMPRESA", "?")), 18)
                    lines.append(f"| {vend} | {emp} | {notas} | {faturado} | {devol} | {liq} | {base_com} | {com_liq} | {mg:.1f}% | {aliq:.1f}% |")
                else:
                    lines.append(f"| {vend} | {notas} | {faturado} | {devol} | {liq} | {base_com} | {com_liq} | {mg:.1f}% | {aliq:.1f}% |")
            if len(detail_data) > 20:
                lines.append(f"\n*...e mais {len(detail_data) - 20} {'linhas' if por_empresa else 'vendedores'}.*")
        else:
            lines.append("| Nota | Tipo | Vendedor | Data | Faturado | Base Com. | Margem | Aliq. | Comissao |\n|------|------|----------|------|----------|-----------|--------|-------|----------|")
            for r in detail_data[:15]:
                if not isinstance(r, dict):
                    continue
                nota = r.get("NUNOTA", "?")
                tipmov = r.get("TIPMOV", "V")
                tipo_label = "Dev" if tipmov == "D" else "Vda"
                vend = trunc(str(r.get("VENDEDOR", "?")), 15)
                data = r.get("DT_NEG", "?")
                faturado = fmt_brl(float(r.get("VLR_FATURADO", 0) or 0))
                base = fmt_brl(float(r.get("BASE_COMISSAO", 0) or 0))
                mg = float(r.get("MARGEM", 0) or 0)
                aliq = float(r.get("ALIQUOTA", 0) or 0)
                com = fmt_brl(float(r.get("VLR_COMISSAO", 0) or 0))
                lines.append(f"| {nota} | {tipo_label} | {vend} | {data} | {faturado} | {base} | {mg:.1f}% | {aliq:.1f}% | {com} |")
            if len(detail_data) > 15:
                lines.append(f"\n*...e mais {len(detail_data) - 15} notas.*")

    lines.append(f"\n\U0001f4e5 **Quer que eu gere um arquivo Excel com o detalhe completo?**")
    return "\n".join(lines)