"""
MMarra Data Hub - Módulo de Produto.
Detecção de queries de produto, resolução de código fabricante, busca de similares.
Extraído de smart_agent.py na refatoração modular.
"""

import re
from src.core.utils import safe_sql


SIMILAR_WORDS = {"similar", "similares", "equivalente", "equivalentes",
                 "alternativ", "substitut", "cross", "crossref",
                 "auxiliar", "auxiliares", "outras marcas", "outra marca",
                 "quais marcas", "que marcas"}


def is_product_code(text: str) -> bool:
    """
    Detecta se o texto parece um código de produto/fabricante.
    Ex: P618689, W950, 0986B02486, 133346, HU727/1X

    Retorna True se a query inteira (ou o token dominante) parece código.
    NÃO detecta queries mistas como "filtro mann w950" — isso vai pro multi_match.
    """
    t = text.strip()
    if not t or len(t) < 3 or len(t) > 30:
        return False

    # Query com múltiplos espaços provavelmente é texto, não código
    words = t.split()
    if len(words) > 3:
        return False

    # Se é exatamente 1 token alfanumérico (com possíveis -, /, .)
    if len(words) == 1:
        # Código alfanumérico com pelo menos 1 dígito (P618689, W950, 0986B02486)
        if re.match(r'^[A-Za-z0-9\-\.\/]{3,25}$', t) and re.search(r'\d', t):
            return True
        # Código numérico puro com 5+ dígitos (CODPROD)
        if re.match(r'^\d{5,}$', t):
            return True

    # 2 tokens onde pelo menos 1 parece código: "HU727 1X" ou "W 950"
    if len(words) == 2:
        for w in words:
            if re.match(r'^[A-Za-z0-9\-\.\/]{2,20}$', w) and re.search(r'\d', w):
                return True

    return False


def _trunc(text, max_len=40):
    """Trunca texto para caber em tabelas."""
    if not text:
        return ""
    s = str(text).strip()
    return s[:max_len] + "..." if len(s) > max_len else s


def _sanitize_code(code: str) -> str:
    """Remove espacos, tracos e barras para comparacao flexivel de codigos."""
    return re.sub(r'[\s\-/\.]', '', code).upper()


async def resolve_manufacturer_code(code_input: str, executor) -> dict:
    """Busca produto pelo codigo do fabricante em TGFPRO.

    Busca nos campos: REFERENCIA, AD_NUMFABRICANTE, AD_NUMFABRICANTE2, AD_NUMORIGINAL, REFFORN.
    Normaliza: remove espacos, tracos, barras antes de comparar.

    Returns:
        {"found": bool, "products": [...], "code_searched": str}
    """
    safe_code = safe_sql(code_input)
    clean = _sanitize_code(safe_code)

    sql = f"""SELECT DISTINCT PRO.CODPROD, PRO.DESCRPROD AS PRODUTO,
        NVL(MAR.DESCRICAO, '') AS MARCA,
        PRO.REFERENCIA, PRO.REFFORN,
        PRO.AD_NUMFABRICANTE, PRO.AD_NUMFABRICANTE2, PRO.AD_NUMORIGINAL,
        NVL(PRO.CARACTERISTICAS, '') AS APLICACAO
    FROM TGFPRO PRO
    LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
    WHERE PRO.ATIVO = 'S'
      AND (
        UPPER(REPLACE(REPLACE(REPLACE(PRO.REFERENCIA,' ',''),'-',''),'/',''))
            LIKE '%{clean}%'
        OR UPPER(REPLACE(REPLACE(PRO.AD_NUMFABRICANTE,' ',''),'-',''))
            LIKE '%{clean}%'
        OR UPPER(REPLACE(REPLACE(PRO.AD_NUMFABRICANTE2,' ',''),'-',''))
            LIKE '%{clean}%'
        OR UPPER(REPLACE(REPLACE(PRO.AD_NUMORIGINAL,' ',''),'-',''))
            LIKE '%{clean}%'
        OR UPPER(REPLACE(REPLACE(PRO.REFFORN,' ',''),'-',''))
            LIKE '%{clean}%'
      )
    AND ROWNUM <= 10"""

    result = await executor.execute(sql)
    cols = ["CODPROD", "PRODUTO", "MARCA", "REFERENCIA", "REFFORN",
            "AD_NUMFABRICANTE", "AD_NUMFABRICANTE2", "AD_NUMORIGINAL", "APLICACAO"]

    products = []
    if result.get("success"):
        data = result.get("data", [])
        if data and isinstance(data[0], (list, tuple)):
            rc = result.get("columns") or cols
            data = [dict(zip(rc if rc and len(rc) == len(data[0]) else cols, row)) for row in data]
        for row in data:
            if isinstance(row, dict):
                # Identificar qual campo matchou
                campo_match = "?"
                for campo in ["REFERENCIA", "AD_NUMFABRICANTE", "AD_NUMFABRICANTE2", "AD_NUMORIGINAL", "REFFORN"]:
                    val = str(row.get(campo, "") or "")
                    if clean in _sanitize_code(val):
                        campo_match = campo
                        break
                products.append({
                    "codprod": int(row.get("CODPROD", 0) or 0),
                    "produto": str(row.get("PRODUTO", "")),
                    "marca": str(row.get("MARCA", "")),
                    "referencia": str(row.get("REFERENCIA", "") or ""),
                    "aplicacao": str(row.get("APLICACAO", "") or ""),
                    "campo_match": campo_match,
                })

    print(f"[PRODUTO] resolve_manufacturer_code('{code_input}'): {len(products)} resultado(s)")
    return {"found": len(products) > 0, "products": products, "code_searched": code_input}


async def buscar_similares(codprod: int, executor) -> dict:
    """Busca codigos auxiliares/similares de um produto em AD_TGFPROAUXMMA.

    Returns:
        {"found": bool, "codprod": int, "produto": str, "marca": str,
         "auxiliares": [{"codigo": str, "marca": str, "observacao": str, "origem": str}]}
    """
    # Dados do produto
    sql_prod = f"""SELECT PRO.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA,
        PRO.REFERENCIA, PRO.AD_NUMFABRICANTE, NVL(PRO.CARACTERISTICAS,'') AS APLICACAO
    FROM TGFPRO PRO LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
    WHERE PRO.CODPROD = {codprod}"""

    sql_aux = f"""SELECT AUX.NUMAUX AS CODIGO, NVL(MAR.DESCRICAO, 'SEM MARCA') AS MARCA,
        NVL(AUX.OBSERVACAO, '') AS OBSERVACAO, NVL(AUX.ORIGEM, '') AS ORIGEM
    FROM AD_TGFPROAUXMMA AUX
    LEFT JOIN TGFMAR MAR ON MAR.CODIGO = AUX.CODIGO
    WHERE AUX.CODPROD = {codprod}
    ORDER BY MAR.DESCRICAO, AUX.NUMAUX"""

    prod_result = await executor.execute(sql_prod)
    aux_result = await executor.execute(sql_aux)

    produto_info = {"codprod": codprod, "produto": "?", "marca": "", "referencia": "", "aplicacao": ""}
    if prod_result.get("success") and prod_result.get("data"):
        pdata = prod_result["data"]
        if pdata and isinstance(pdata[0], (list, tuple)):
            cols = prod_result.get("columns") or ["CODPROD", "PRODUTO", "MARCA", "REFERENCIA", "AD_NUMFABRICANTE", "APLICACAO"]
            pdata = [dict(zip(cols, row)) for row in pdata]
        if pdata and isinstance(pdata[0], dict):
            produto_info["produto"] = str(pdata[0].get("PRODUTO", "?"))
            produto_info["marca"] = str(pdata[0].get("MARCA", ""))
            produto_info["referencia"] = str(pdata[0].get("REFERENCIA", "") or "")
            produto_info["aplicacao"] = str(pdata[0].get("APLICACAO", "") or "")

    auxiliares = []
    if aux_result.get("success") and aux_result.get("data"):
        adata = aux_result["data"]
        if adata and isinstance(adata[0], (list, tuple)):
            cols = aux_result.get("columns") or ["CODIGO", "MARCA", "OBSERVACAO", "ORIGEM"]
            adata = [dict(zip(cols, row)) for row in adata]
        for row in adata:
            if isinstance(row, dict):
                auxiliares.append({
                    "codigo": str(row.get("CODIGO", "")),
                    "marca": str(row.get("MARCA", "")),
                    "observacao": str(row.get("OBSERVACAO", "")),
                    "origem": str(row.get("ORIGEM", "")),
                })

    print(f"[PRODUTO] buscar_similares({codprod}): {len(auxiliares)} codigo(s) auxiliar(es)")
    return {"found": len(auxiliares) > 0, **produto_info, "auxiliares": auxiliares}


async def buscar_similares_por_codigo(code_input: str, executor) -> dict:
    """Dado um codigo auxiliar, encontra o produto e lista todos os similares."""
    safe_code = safe_sql(code_input)
    clean = _sanitize_code(safe_code)

    sql = f"""SELECT DISTINCT AUX.CODPROD
    FROM AD_TGFPROAUXMMA AUX
    WHERE UPPER(REPLACE(REPLACE(AUX.NUMAUX, ' ', ''), '-', ''))
          LIKE '%{clean}%'
    AND ROWNUM <= 5"""

    result = await executor.execute(sql)
    codprods = []
    if result.get("success") and result.get("data"):
        for row in result["data"]:
            if isinstance(row, dict):
                codprods.append(int(row.get("CODPROD", 0) or 0))
            elif isinstance(row, (list, tuple)):
                codprods.append(int(row[0] or 0))

    if not codprods:
        return {"found": False, "code_searched": code_input, "products": []}

    # Se 1 resultado, listar similares completos
    if len(codprods) == 1:
        return await buscar_similares(codprods[0], executor)

    # Se multiplos, listar os produtos encontrados
    products = []
    for cp in codprods[:5]:
        sql_p = f"SELECT PRO.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA, NVL(PRO.CARACTERISTICAS,'') AS APLICACAO FROM TGFPRO PRO LEFT JOIN TGFMAR MAR ON MAR.CODIGO=PRO.CODMARCA WHERE PRO.CODPROD={cp}"
        pr = await executor.execute(sql_p)
        if pr.get("success") and pr.get("data"):
            pdata = pr["data"]
            if pdata and isinstance(pdata[0], (list, tuple)):
                cols = pr.get("columns") or ["CODPROD", "PRODUTO", "MARCA", "APLICACAO"]
                pdata = [dict(zip(cols, row)) for row in pdata]
            if pdata and isinstance(pdata[0], dict):
                products.append({"codprod": cp, "produto": str(pdata[0].get("PRODUTO", "")), "marca": str(pdata[0].get("MARCA", "")), "aplicacao": str(pdata[0].get("APLICACAO", "") or "")})

    return {"found": True, "code_searched": code_input, "products": products, "multiple": True}


def detect_product_query(q_norm: str, params: dict) -> str | None:
    """Detecta se a pergunta e centrada em produto e qual tipo de consulta.

    Returns:
        "produto_360" - visao completa (estoque + pendencia + info)
        "busca_fabricante" - resolver codigo fabricante pra CODPROD
        "similares" - buscar cross-reference/similares
        "busca_aplicacao" - buscar por veiculo/aplicacao
        None - nao e query centrada em produto
    """
    # Busca por aplicacao: tem aplicacao mas nao codprod/codigo_fabricante
    if params.get("aplicacao") and not params.get("codprod") and not params.get("codigo_fabricante"):
        return "busca_aplicacao"

    has_product = params.get("codprod") or params.get("produto_nome") or params.get("codigo_fabricante")
    if not has_product:
        return None

    q = q_norm.lower()

    # Similares / cross-reference
    if any(w in q for w in SIMILAR_WORDS):
        return "similares"

    # Se tem codigo fabricante, precisa resolver primeiro
    if params.get("codigo_fabricante") and not params.get("codprod"):
        return "busca_fabricante"

    # Visao 360: "tudo sobre", "situacao do", "me fala tudo"
    full_view_patterns = ["tudo sobre", "situacao do", "como esta o", "me fala", "resumo do",
                          "informac", "detalhe do produto", "visao geral"]
    if any(p in q for p in full_view_patterns):
        return "produto_360"

    # Cross-intent: menciona estoque E pendencia juntos
    pend_words = {"pendente", "pendencia", "falta chegar", "pedido aberto", "compra"}
    est_words = {"estoque", "saldo", "disponivel"}
    has_pend = any(w in q for w in pend_words)
    has_est = any(w in q for w in est_words)
    if has_pend and has_est:
        return "produto_360"

    return None


def format_produto_360(prod_info: dict, estoque_data: list, pendencia_data: dict, vendas_info: dict = None) -> str:
    """Formata a visao 360 de um produto."""
    codprod = prod_info.get("codprod", "?")
    produto = prod_info.get("produto", "?")
    marca = prod_info.get("marca", "")
    ref = prod_info.get("referencia", "")

    aplicacao = prod_info.get("aplicacao", "")
    complemento = prod_info.get("complemento", "")
    num_original = prod_info.get("num_original", "")
    ref_forn = prod_info.get("ref_fornecedor", "")

    lines = []
    header = f"\U0001f4e6 **Produto {codprod} - {produto}**"
    if marca:
        header += f" ({marca})"
    lines.append(header)
    if aplicacao:
        lines.append(f"Aplicacao: {aplicacao}")
    refs = []
    if ref:
        refs.append(f"Ref: {ref}")
    if num_original and num_original != ref:
        refs.append(f"Nro. Original: {num_original}")
    if ref_forn and ref_forn != ref:
        refs.append(f"Ref. Forn: {ref_forn}")
    if refs:
        lines.append(" | ".join(refs))
    if complemento:
        lines.append(f"Complemento: {complemento}")
    lines.append("")

    # ESTOQUE
    if estoque_data:
        total_est = sum(int(float(r.get("ESTOQUE", 0) or 0)) for r in estoque_data if isinstance(r, dict))
        lines.append(f"\U0001f4ca **Estoque:** {fmt_num(total_est)} unidades\n")
        if len(estoque_data) > 1:
            lines.append("| Empresa | Estoque | Est. Min. |")
            lines.append("|---------|---------|-----------|")
            for r in estoque_data[:8]:
                if isinstance(r, dict):
                    est = fmt_num(r.get("ESTOQUE", 0))
                    estmin = fmt_num(r.get("ESTMIN", 0))
                    emp = str(r.get("EMPRESA", "?"))[:25]
                    lines.append(f"| {emp} | {est} | {estmin} |")
            lines.append("")
    else:
        lines.append("\U0001f4ca **Estoque:** sem dados\n")

    # PENDENCIA
    if pendencia_data and pendencia_data.get("detail_data"):
        detail = pendencia_data["detail_data"]
        qtd_ped = len(set(str(r.get("PEDIDO", "")) for r in detail if isinstance(r, dict)))
        vlr_total = sum(float(r.get("VLR_PENDENTE", 0) or 0) for r in detail if isinstance(r, dict))
        qtd_pend = sum(int(r.get("QTD_PENDENTE", 0) or 0) for r in detail if isinstance(r, dict))

        lines.append(f"\U0001f69a **Compras Pendentes:** {fmt_num(qtd_ped)} pedido(s), {fmt_num(qtd_pend)} un., {fmt_brl(vlr_total)}\n")
        lines.append("| Pedido | Tipo | Fornecedor | Qtd Pend. | Valor | Status |")
        lines.append("|--------|------|-----------|-----------|-------|--------|")
        shown_pedidos = set()
        for r in detail[:8]:
            if isinstance(r, dict):
                ped = str(r.get("PEDIDO", "?"))
                if ped in shown_pedidos:
                    continue
                shown_pedidos.add(ped)
                tipo = str(r.get("TIPO_COMPRA", ""))
                forn = str(r.get("FORNECEDOR", "?"))[:25]
                qtd = fmt_num(r.get("QTD_PENDENTE", 0))
                vlr = fmt_brl(r.get("VLR_PENDENTE", 0))
                status = str(r.get("STATUS_ENTREGA", "?"))
                lines.append(f"| {ped} | {tipo} | {forn} | {qtd} | {vlr} | {status} |")
        lines.append("")
    else:
        lines.append("\U0001f69a **Compras Pendentes:** nenhuma\n")

    # VENDAS
    if vendas_info and int(vendas_info.get("QTD_VENDAS", 0) or 0) > 0:
        qv = fmt_num(vendas_info.get("QTD_VENDAS", 0))
        qtdv = fmt_num(vendas_info.get("QTD_VENDIDA", 0))
        vlrv = fmt_brl(vendas_info.get("VLR_TOTAL", 0))
        lines.append(f"\U0001f4c8 **Vendas (3 meses):** {qv} notas, {qtdv} un., {vlrv}\n")

    return "\n".join(lines)


def format_busca_fabricante(resolved: dict) -> str:
    """Formata resultado da busca por codigo fabricante."""
    code = resolved.get("code_searched", "?")
    products = resolved.get("products", [])

    if not products:
        return f"\U0001f50d Nenhum produto encontrado com o codigo **{code}**.\n\nTente buscar por similares: *\"similares do {code}\"*"

    if len(products) == 1:
        p = products[0]
        response = f"\U0001f50d O codigo **{code}** corresponde ao produto:\n\n"
        response += f"| Campo | Valor |\n|---|---|\n"
        response += f"| **Codigo** | {p['codprod']} |\n"
        response += f"| **Produto** | {p['produto']} |\n"
        if p.get("marca"):
            response += f"| **Marca** | {p['marca']} |\n"
        if p.get("aplicacao"):
            response += f"| **Aplicacao** | {p['aplicacao']} |\n"
        if p.get("referencia"):
            response += f"| **Referencia** | {p['referencia']} |\n"
        response += f"| **Campo encontrado** | {p['campo_match']} |\n"
        response += f"\nQuer ver a visao completa? Pergunte: *\"tudo sobre o produto {p['codprod']}\"*"
        return response

    response = f"\U0001f50d Encontrei **{len(products)} produtos** com o codigo **{code}**:\n\n"
    response += "| CodProd | Produto | Marca | Aplicacao | Campo |\n|---------|---------|-------|-----------|-------|\n"
    for p in products:
        aplic = _trunc(p.get('aplicacao',''), 40)
        response += f"| {p['codprod']} | {str(p['produto'])[:35]} | {p.get('marca','')} | {aplic} | {p['campo_match']} |\n"
    response += f"\nEspecifique o produto pelo codigo. Ex: *\"tudo sobre o produto {products[0]['codprod']}\"*"
    return response


def format_similares(sim_data: dict) -> str:
    """Formata resultado da busca de similares/cross-reference."""
    if not sim_data.get("found"):
        code = sim_data.get("code_searched", sim_data.get("codprod", "?"))
        return f"Nao encontrei codigos auxiliares/similares para **{code}**."

    # Se veio de busca por codigo texto com multiplos produtos
    if sim_data.get("multiple"):
        products = sim_data.get("products", [])
        response = f"\U0001f504 O codigo **{sim_data.get('code_searched', '?')}** aparece em {len(products)} produtos:\n\n"
        response += "| CodProd | Produto | Marca |\n|---------|---------|-------|\n"
        for p in products:
            response += f"| {p['codprod']} | {str(p['produto'])[:40]} | {p.get('marca','')} |\n"
        response += f"\nPara ver similares de um produto especifico: *\"similares do produto {products[0]['codprod']}\"*"
        return response

    codprod = sim_data.get("codprod", "?")
    produto = sim_data.get("produto", "?")
    marca = sim_data.get("marca", "")
    aplicacao = sim_data.get("aplicacao", "")
    auxiliares = sim_data.get("auxiliares", [])

    response = f"\U0001f504 **Similares do produto {codprod} - {produto}**"
    if marca:
        response += f" ({marca})"
    if aplicacao:
        response += f"\nAplicacao: {aplicacao}"
    response += f"\n\nEncontrei **{len(auxiliares)}** codigo(s) auxiliar(es):\n\n"

    # Agrupar por marca
    from collections import defaultdict
    por_marca = defaultdict(list)
    for aux in auxiliares:
        por_marca[aux.get("marca", "?")].append(aux)

    response += "| Codigo | Marca | Obs. |\n|--------|-------|------|\n"
    count = 0
    for m_name in sorted(por_marca.keys()):
        for aux in por_marca[m_name][:5]:
            obs = str(aux.get("observacao", ""))[:20]
            response += f"| {aux['codigo']} | {m_name} | {obs} |\n"
            count += 1
            if count >= 30:
                break
        if count >= 30:
            break

    if len(auxiliares) > 30:
        response += f"\n*...e mais {len(auxiliares) - 30} codigo(s).*"

    response += f"\n\n{len(por_marca)} marca(s) diferente(s)."
    return response

