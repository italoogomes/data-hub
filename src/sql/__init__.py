"""
MMarra Data Hub - Templates SQL.
Queries para pendência de compras, vendas, estoque.
Extraído de smart_agent.py na refatoração modular.
"""

import re
from src.core.utils import safe_sql
from src.agent.entities import EMPRESA_DISPLAY


JOINS_PENDENCIA = """
    FROM TGFITE ITE
    JOIN TGFCAB CAB ON CAB.NUNOTA = ITE.NUNOTA
    JOIN TSIEMP EMP ON EMP.CODEMP = ITE.CODEMP
    JOIN TGFPRO PRO ON PRO.CODPROD = ITE.CODPROD
    LEFT JOIN TGFPAR PAR ON PAR.CODPARC = CAB.CODPARC
    LEFT JOIN TGFMAR MAR ON MAR.CODIGO = PRO.CODMARCA
    LEFT JOIN TGFVEN VEN ON VEN.CODVEND = MAR.AD_CODVEND
    LEFT JOIN (
        SELECT V.NUNOTAORIG, V.SEQUENCIAORIG,
               SUM(V.QTDATENDIDA) AS TOTAL_ATENDIDO
        FROM TGFVAR V
        JOIN TGFCAB C ON C.NUNOTA = V.NUNOTA
        WHERE C.STATUSNOTA <> 'C'
        GROUP BY V.NUNOTAORIG, V.SEQUENCIAORIG
    ) V_AGG ON V_AGG.NUNOTAORIG = ITE.NUNOTA
           AND V_AGG.SEQUENCIAORIG = ITE.SEQUENCIA
"""

WHERE_PENDENCIA = """CAB.CODTIPOPER IN (1301, 1313)
      AND CAB.STATUSNOTA <> 'C'
      AND CAB.PENDENTE = 'S'
      AND ITE.PENDENTE = 'S'
      AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0"""


def safe_sql(value: str) -> str:
    """Sanitiza valor para uso em SQL: remove chars perigosos, escapa aspas."""
    if not value:
        return ""
    s = str(value).strip()
    # Remover chars perigosos de SQL injection
    s = re.sub(r'[;\-\-\/\*\\\x00]', '', s)
    # Escapar aspas simples (Oracle-style)
    s = s.replace("'", "''")
    return s


def _build_where_extra(params, user_context=None):
    w = ""
    if params.get("marca"):
        w += f" AND UPPER(MAR.DESCRICAO) LIKE UPPER('%{safe_sql(params['marca'])}%')"
    if params.get("fornecedor"):
        w += f" AND UPPER(PAR.NOMEPARC) LIKE UPPER('%{safe_sql(params['fornecedor'])}%')"
    if params.get("empresa"):
        w += f" AND UPPER(EMP.NOMEFANTASIA) LIKE UPPER('%{safe_sql(params['empresa'])}%')"
    if params.get("comprador"):
        w += f" AND UPPER(VEN.APELIDO) LIKE UPPER('%{safe_sql(params['comprador'])}%')"
    if params.get("nunota"):
        w += f" AND CAB.NUNOTA = {int(params['nunota'])}"
    if params.get("codprod"):
        w += f" AND PRO.CODPROD = {int(params['codprod'])}"
    if params.get("produto_nome") and not params.get("codprod"):
        w += f" AND UPPER(PRO.DESCRPROD) LIKE UPPER('%{safe_sql(params['produto_nome'])}%')"
    if params.get("aplicacao"):
        w += f" AND UPPER(PRO.CARACTERISTICAS) LIKE UPPER('%{safe_sql(params['aplicacao'])}%')"
    # Tipo de compra (casada/estoque) via CODTIPOPER (mais eficiente que filtrar pos-query)
    tc = (params.get("tipo_compra") or "").upper()
    if tc in ("CASADA", "EMPENHO", "VINCULADA"):
        w += " AND CAB.CODTIPOPER = 1313"
    elif tc in ("ESTOQUE", "FUTURA", "REPOSICAO"):
        w += " AND CAB.CODTIPOPER = 1301"
    if user_context:
        role = user_context.get("role", "vendedor")
        if role in ("admin", "diretor", "ti"):
            pass
        elif role == "gerente":
            team = user_context.get("team_codvends", [])
            if team:
                w += f" AND MAR.AD_CODVEND IN ({','.join(str(c) for c in team)})"
        elif role in ("vendedor", "comprador"):
            codvend = user_context.get("codvend", 0)
            if codvend:
                w += f" AND MAR.AD_CODVEND = {codvend}"
    return w


def sql_pendencia_compras(params, user_context=None):
    we = _build_where_extra(params, user_context)
    sql_kpis = f"""
        SELECT
            COUNT(DISTINCT CAB.NUNOTA) AS QTD_PEDIDOS,
            COUNT(*) AS QTD_ITENS,
            NVL(SUM(ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2)), 0) AS VLR_PENDENTE
        {JOINS_PENDENCIA}
        WHERE {WHERE_PENDENCIA} {we}
    """
    sql_detail = f"""
        SELECT
            EMP.NOMEFANTASIA AS EMPRESA,
            CAB.NUNOTA AS PEDIDO,
            CASE WHEN CAB.CODTIPOPER = 1313 THEN 'Casada' WHEN CAB.CODTIPOPER = 1301 THEN 'Estoque' END AS TIPO_COMPRA,
            NVL(VEN.APELIDO, 'SEM COMPRADOR') AS COMPRADOR,
            TO_CHAR(CAB.DTNEG, 'DD/MM/YYYY') AS DT_PEDIDO,
            NVL(TO_CHAR(CAB.DTPREVENT, 'DD/MM/YYYY'), 'Sem previsao') AS PREVISAO_ENTREGA,
            CASE WHEN CAB.STATUSNOTA = 'L' THEN 'Sim' ELSE 'Nao' END AS CONFIRMADO,
            PAR.NOMEPARC AS FORNECEDOR,
            PRO.CODPROD,
            PRO.DESCRPROD AS PRODUTO,
            NVL(MAR.DESCRICAO, '') AS MARCA,
            NVL(PRO.CARACTERISTICAS, '') AS APLICACAO,
            NVL(PRO.AD_NUMFABRICANTE, '') AS NUM_FABRICANTE,
            ITE.CODVOL AS UNIDADE,
            ITE.QTDNEG AS QTD_PEDIDA,
            NVL(V_AGG.TOTAL_ATENDIDO, 0) AS QTD_ATENDIDA,
            (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) AS QTD_PENDENTE,
            ITE.VLRUNIT AS VLR_UNITARIO,
            ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2) AS VLR_PENDENTE,
            TRUNC(SYSDATE) - TRUNC(CAB.DTNEG) AS DIAS_ABERTO,
            CASE
                WHEN CAB.DTPREVENT IS NULL THEN 'SEM PREVISAO'
                WHEN CAB.DTPREVENT < SYSDATE THEN 'ATRASADO'
                WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 'PROXIMO'
                ELSE 'NO PRAZO'
            END AS STATUS_ENTREGA
        {JOINS_PENDENCIA}
        WHERE {WHERE_PENDENCIA} {we}
        ORDER BY
            CASE WHEN CAB.DTPREVENT IS NULL THEN 1 WHEN CAB.DTPREVENT < SYSDATE THEN 0 WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 2 ELSE 3 END,
            MAR.DESCRICAO, PRO.DESCRPROD
    """
    filtro_desc = []
    if params.get("marca"): filtro_desc.append(f"marca **{params['marca']}**")
    if params.get("fornecedor"): filtro_desc.append(f"fornecedor **{params['fornecedor']}**")
    if params.get("empresa"):
        emp_display = EMPRESA_DISPLAY.get(params['empresa'].upper(), params['empresa'])
        filtro_desc.append(f"empresa **{emp_display}**")
    if params.get("comprador"): filtro_desc.append(f"comprador **{params['comprador']}**")
    if params.get("nunota"): filtro_desc.append(f"pedido **{params['nunota']}**")
    if params.get("codprod"): filtro_desc.append(f"produto **{params['codprod']}**")
    if params.get("produto_nome") and not params.get("codprod"): filtro_desc.append(f"produto **{params['produto_nome']}**")
    desc = "pendencia de compras"
    if filtro_desc: desc += " da " + ", ".join(filtro_desc)
    return sql_kpis, sql_detail, desc


def _build_periodo_filter(params, date_col="C.DTNEG"):
    p = params.get("periodo", "mes")

    # Custom: data_inicio e data_fim explícitas (usado por multi-step comparisons)
    # Formato esperado: YYYY-MM-DD (convertido para YYYYMMDD no SQL)
    if p == "custom":
        di = params.get("data_inicio")
        df = params.get("data_fim")
        if di and df:
            di_clean = re.sub(r'[^0-9]', '', str(di))[:8]
            df_clean = re.sub(r'[^0-9]', '', str(df))[:8]
            return f"AND {date_col} >= TO_DATE('{di_clean}', 'YYYYMMDD') AND {date_col} < TO_DATE('{df_clean}', 'YYYYMMDD') + 1"

    m = {
        "hoje": f"AND {date_col} >= TRUNC(SYSDATE) AND {date_col} < TRUNC(SYSDATE) + 1",
        "ontem": f"AND {date_col} >= TRUNC(SYSDATE) - 1 AND {date_col} < TRUNC(SYSDATE)",
        "semana": f"AND {date_col} >= TRUNC(SYSDATE, 'IW') AND {date_col} < TRUNC(SYSDATE) + 1",
        "semana_passada": f"AND {date_col} >= TRUNC(SYSDATE, 'IW') - 7 AND {date_col} < TRUNC(SYSDATE, 'IW')",
        "mes": f"AND {date_col} >= TRUNC(SYSDATE, 'MM') AND {date_col} < TRUNC(SYSDATE) + 1",
        "mes_passado": f"AND {date_col} >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1) AND {date_col} < TRUNC(SYSDATE, 'MM')",
        "ano": f"AND {date_col} >= TRUNC(SYSDATE, 'YYYY') AND {date_col} < TRUNC(SYSDATE) + 1",
    }
    return m.get(p, m["mes"])


PERIODO_NOMES = {
    "hoje": "hoje", "ontem": "ontem", "semana": "esta semana",
    "semana_passada": "semana passada", "mes": "este mes",
    "mes_passado": "mes passado", "ano": "este ano",
}


def _build_vendas_where(params, user_context=None):
    """WHERE clause para queries de vendas. RBAC via CAB.CODVEND (vendedor da nota)."""
    w = ""
    if params.get("marca"):
        w += f" AND UPPER(MAR.DESCRICAO) LIKE UPPER('%{safe_sql(params['marca'])}%')"
    if params.get("empresa"):
        w += f" AND UPPER(EMP.NOMEFANTASIA) LIKE UPPER('%{safe_sql(params['empresa'])}%')"
    if params.get("cliente"):
        w += f" AND UPPER(PAR.NOMEPARC) LIKE UPPER('%{safe_sql(params['cliente'])}%')"
    vendedor = params.get("vendedor") or params.get("vendedor_nome")
    if vendedor:
        w += f" AND UPPER(VEN.APELIDO) LIKE UPPER('%{safe_sql(vendedor)}%')"
    # RBAC - vendas usa C.CODVEND (vendedor da nota), NAO MAR.AD_CODVEND
    if user_context:
        role = user_context.get("role", "vendedor")
        if role in ("admin", "diretor", "ti"):
            pass
        elif role == "gerente":
            team = user_context.get("team_codvends", [])
            if team:
                w += f" AND C.CODVEND IN ({','.join(str(int(c)) for c in team)})"
        elif role in ("vendedor",):
            codvend = user_context.get("codvend", 0)
            if codvend:
                w += f" AND C.CODVEND = {int(codvend)}"
    return w

