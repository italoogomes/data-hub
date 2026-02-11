"""
MMarra Data Hub - Modulo de Relatorios
Endpoints e handlers para relatorios parametrizados.

Cada relatorio e uma funcao que:
1. Recebe parametros + contexto RBAC
2. Monta SQL (baseada nas queries validadas)
3. Executa via SafeQueryExecutor
4. Retorna JSON estruturado (KPIs + tabela + dados de grafico)

Cache: resultados ficam em memoria por CACHE_TTL segundos.
Mesma combinacao (relatorio + parametros + perfil) retorna do cache sem bater no Sankhya.
"""

import time
import hashlib
import json
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from src.llm.query_executor import SafeQueryExecutor


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Executor compartilhado
_executor = SafeQueryExecutor()


# ============================================================
# CACHE
# ============================================================

CACHE_TTL = 180  # 3 minutos (segundos)

class ReportCache:
    """Cache em memoria com TTL por chave.

    Chave = hash de (report_id + params + role + codvend).
    Mesma pessoa com mesmos filtros pega do cache.
    Pessoas com roles diferentes geram caches separados (dados RBAC diferentes).
    """

    def __init__(self):
        self._store = {}  # {key: {"data": ..., "expires": timestamp}}
        self._hits = 0
        self._misses = 0

    def _make_key(self, report_id: str, params: dict, user_context: dict) -> str:
        """Gera chave unica para a combinacao relatorio+filtros+usuario."""
        key_parts = {
            "report": report_id,
            "params": params,
            "role": user_context.get("role", ""),
            "codvend": user_context.get("codvend", 0),
            "team": sorted(user_context.get("team_codvends", [])),
        }
        raw = json.dumps(key_parts, sort_keys=True, default=str)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, report_id: str, params: dict, user_context: dict):
        """Retorna dados do cache se existir e nao expirou."""
        self._cleanup()
        key = self._make_key(report_id, params, user_context)
        entry = self._store.get(key)
        if entry and time.time() < entry["expires"]:
            self._hits += 1
            print(f"[CACHE] HIT {report_id} (key={key[:8]}..., hits={self._hits})")
            return entry["data"]
        self._misses += 1
        return None

    def set(self, report_id: str, params: dict, user_context: dict, data):
        """Armazena resultado no cache."""
        key = self._make_key(report_id, params, user_context)
        self._store[key] = {
            "data": data,
            "expires": time.time() + CACHE_TTL,
            "report_id": report_id,
            "created": time.time(),
        }
        print(f"[CACHE] SET {report_id} (key={key[:8]}..., ttl={CACHE_TTL}s, total={len(self._store)})")

    def invalidate(self, report_id: str = None):
        """Limpa cache. Se report_id, limpa so daquele relatorio."""
        if report_id:
            keys_to_del = [k for k, v in self._store.items() if v.get("report_id") == report_id]
            for k in keys_to_del:
                del self._store[k]
            print(f"[CACHE] INVALIDATE {report_id} ({len(keys_to_del)} entradas removidas)")
        else:
            count = len(self._store)
            self._store.clear()
            self._hits = 0
            self._misses = 0
            print(f"[CACHE] CLEAR ALL ({count} entradas removidas)")

    def _cleanup(self):
        """Remove entradas expiradas."""
        now = time.time()
        expired = [k for k, v in self._store.items() if now >= v["expires"]]
        for k in expired:
            del self._store[k]

    def stats(self) -> dict:
        """Retorna estatisticas do cache."""
        self._cleanup()
        total = self._hits + self._misses
        return {
            "entries": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "N/A",
            "ttl_seconds": CACHE_TTL,
        }


# Cache global
_cache = ReportCache()


# ============================================================
# MODELS
# ============================================================

class ReportRequest(BaseModel):
    data_ini: Optional[str] = None   # DD/MM/YYYY
    data_fim: Optional[str] = None   # DD/MM/YYYY
    codemp: Optional[int] = None
    codvend: Optional[int] = None
    codparc: Optional[int] = None
    codmarca: Optional[int] = None
    categoria: Optional[str] = None  # todos|atrasados|15dias|sem_previsao|programados|transito
    solicitante: Optional[str] = None
    no_cache: Optional[bool] = False  # Forcar bypass do cache


class ReportResponse(BaseModel):
    report_id: str
    nome: str
    kpis: list = []
    categorias: list = []            # 6 abas com contagem/valor
    table_columns: list = []
    table_data: list = []
    chart_data: dict = {}
    charts: list = []                # Multiplos graficos
    filtros_aplicados: dict = {}
    filtros_disponiveis: dict = {}   # Opcoes para dropdowns (empresas, compradores, etc)
    time_ms: int = 0
    row_count: int = 0
    from_cache: bool = False


# ============================================================
# HELPERS
# ============================================================

def _parse_date(dt_str: str, default: str = None) -> str:
    """Converte DD/MM/YYYY pra TO_DATE Oracle."""
    if not dt_str:
        return default
    try:
        parsed = datetime.strptime(dt_str, "%d/%m/%Y")
        return f"TO_DATE('{parsed.strftime('%d/%m/%Y')}','DD/MM/YYYY')"
    except ValueError:
        return default


def _apply_rbac_filter(sql: str, user_context: dict, alias: str = "C") -> str:
    """Aplica filtro RBAC na query conforme perfil do usuario."""
    role = user_context.get("role", "vendedor")

    if role == "admin":
        return sql

    if role == "gerente":
        team = user_context.get("team_codvends", [])
        if team:
            codvends = ",".join(str(c) for c in team)
            return sql + f" AND {alias}.CODVEND IN ({codvends})"
        return sql

    if role in ("vendedor", "comprador"):
        codvend = user_context.get("codvend", 0)
        if codvend:
            return sql + f" AND {alias}.CODVEND = {codvend}"

    return sql


def _build_date_filter(alias: str, data_ini: str, data_fim: str) -> str:
    """Constroi filtro de data."""
    parts = []
    if data_ini:
        parts.append(f"{alias}.DTNEG >= {_parse_date(data_ini)}")
    if data_fim:
        parts.append(f"{alias}.DTNEG <= {_parse_date(data_fim)} + 0.99999")
    return " AND ".join(parts) if parts else ""


async def _run_query(sql: str) -> dict:
    """Executa query e retorna resultado normalizado (sempre list of dicts)."""
    try:
        result = await _executor.execute(sql)

        # Normalizar: se rows vieram como listas, converter pra dicts
        if result.get("success") and result.get("data"):
            data = result["data"]
            if data and isinstance(data[0], (list, tuple)):
                # Rows sao listas - extrair aliases do SQL pra usar como keys
                aliases = _extract_sql_aliases(sql)
                if aliases and len(aliases) == len(data[0]):
                    result["data"] = [dict(zip(aliases, row)) for row in data]
                    result["columns"] = aliases
                elif result.get("columns") and len(result["columns"]) == len(data[0]):
                    result["data"] = [dict(zip(result["columns"], row)) for row in data]
                else:
                    # Fallback: usar indices como keys (COL_0, COL_1...)
                    n_cols = len(data[0])
                    keys = [f"COL_{i}" for i in range(n_cols)]
                    result["data"] = [dict(zip(keys, row)) for row in data]
                    result["columns"] = keys
                    print(f"[WARN] _run_query: rows como lista sem aliases. SQL: {sql[:80]}...")

        return result
    except Exception as e:
        return {"success": False, "error": str(e), "data": [], "columns": []}


def _extract_sql_aliases(sql: str) -> list:
    """Extrai aliases das colunas do SELECT pra mapear rows-lista em dicts."""
    import re as _re

    # Pegar tudo entre SELECT e FROM
    match = _re.search(r'SELECT\s+(.*?)\s+FROM\b', sql, _re.IGNORECASE | _re.DOTALL)
    if not match:
        return []

    select_clause = match.group(1)

    # Separar por virgula respeitando parenteses
    parts = []
    depth = 0
    current = ""
    for char in select_clause:
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current.strip())

    # Extrair alias de cada parte
    aliases = []
    for part in parts:
        # "expressao AS ALIAS"
        as_match = _re.search(r'\bAS\s+(\w+)\s*$', part, _re.IGNORECASE)
        if as_match:
            aliases.append(as_match.group(1).upper())
        else:
            # "TABELA.COLUNA" -> pega COLUNA | "COLUNA" -> pega COLUNA
            words = _re.findall(r'[\w]+', part)
            if words:
                aliases.append(words[-1].upper())

    return aliases


# ============================================================
# RELATORIO: PENDENCIA DE COMPRAS (Power BI Parity)
# ============================================================

def _fmt_brl(valor: float) -> str:
    """Formata valor como R$ X.XXX,XX"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def report_pendencia_compras(params: ReportRequest, user_context: dict) -> ReportResponse:
    """
    Pendencia de Compras - Replica do dashboard Power BI.
    Query base fornecida pelo usuario (validada no Sankhya).

    Categorias: Todos, Atrasado, Próximo (7d), Sem Previsão, No Prazo, Trânsito
    Tabela: nivel item (TGFITE) com produto, marca, qtd pedida/atendida/pendente
    Graficos: por empresa, comprador, marca, curva ABC
    Filtros: empresa, comprador, marca + data
    """
    start = time.time()
    filtros = {}

    # ========================================
    # JOINS e WHERE BASE (query real do Power BI)
    # ========================================
    # Comprador vem pela MARCA (TGFMAR.AD_CODVEND), nao pelo cabecalho
    joins = """
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

    where_base = """CAB.CODTIPOPER IN (1301, 1313)
       AND CAB.STATUSNOTA <> 'C'
       AND CAB.PENDENTE = 'S'
       AND ITE.PENDENTE = 'S'
       AND (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) > 0"""

    # Filtros opcionais
    if params.data_ini:
        where_base += f" AND CAB.DTNEG >= {_parse_date(params.data_ini)}"
        filtros["data_ini"] = params.data_ini
    if params.data_fim:
        where_base += f" AND CAB.DTNEG <= {_parse_date(params.data_fim)} + 0.99999"
        filtros["data_fim"] = params.data_fim
    if params.codemp:
        where_base += f" AND ITE.CODEMP = {params.codemp}"
        filtros["codemp"] = params.codemp
    if params.codparc:
        where_base += f" AND CAB.CODPARC = {params.codparc}"
        filtros["codparc"] = params.codparc
    if params.codmarca:
        where_base += f" AND PRO.CODMARCA = {params.codmarca}"
        filtros["codmarca"] = params.codmarca
    if params.codvend:
        where_base += f" AND MAR.AD_CODVEND = {params.codvend}"
        filtros["codvend"] = params.codvend
    if params.solicitante:
        where_base += f" AND UPPER(VEN.APELIDO) LIKE UPPER('%{params.solicitante}%')"
        filtros["solicitante"] = params.solicitante

# RBAC (comprador pela marca)
    role = user_context.get("role", "vendedor")
    if role in ("admin", "diretor", "ti"):
        pass  # Ve tudo
    elif role == "gerente":
        team = user_context.get("team_codvends", [])
        if team:
            where_base += f" AND MAR.AD_CODVEND IN ({','.join(str(c) for c in team)})"
    elif role in ("vendedor", "comprador"):
        codvend = user_context.get("codvend", 0)
        if codvend:
            where_base += f" AND MAR.AD_CODVEND = {codvend}"

    # ========================================
    # 1) CATEGORIAS (6 abas)
    # ========================================
    # Categorias baseadas no STATUS_ENTREGA da query real:
    # - ATRASADO: DTPREVENT < SYSDATE
    # - PROXIMO: DTPREVENT entre SYSDATE e SYSDATE+7
    # - SEM PREVISAO: DTPREVENT IS NULL
    # - NO PRAZO: DTPREVENT >= SYSDATE+7
    # - TRANSITO: tem atendimento parcial (V_AGG.TOTAL_ATENDIDO > 0 mas < QTDNEG)

    cat_filters = {
        "todos": "",
        "atrasados": " AND CAB.DTPREVENT IS NOT NULL AND CAB.DTPREVENT < TRUNC(SYSDATE)",
        "proximo": " AND CAB.DTPREVENT IS NOT NULL AND CAB.DTPREVENT >= TRUNC(SYSDATE) AND CAB.DTPREVENT < TRUNC(SYSDATE) + 7",
        "sem_previsao": " AND CAB.DTPREVENT IS NULL",
        "no_prazo": " AND CAB.DTPREVENT IS NOT NULL AND CAB.DTPREVENT >= TRUNC(SYSDATE) + 7",
        "transito": " AND NVL(V_AGG.TOTAL_ATENDIDO, 0) > 0 AND NVL(V_AGG.TOTAL_ATENDIDO, 0) < ITE.QTDNEG",
    }

    cat_names = {
        "todos": "Pedidos em Aberto",
        "atrasados": "Atrasados",
        "proximo": "Próximo (7 dias)",
        "sem_previsao": "Sem Previsão",
        "no_prazo": "No Prazo",
        "transito": "Trânsito",
    }

    # Query de contagem por categoria (UNION ALL)
    union_parts = []
    for cat_id, cat_where in cat_filters.items():
        union_parts.append(f"""
            SELECT
                '{cat_id}' AS CAT,
                COUNT(DISTINCT CAB.NUNOTA) AS QTD_PEDIDOS,
                COUNT(*) AS QTD_PRODUTOS,
                NVL(SUM(ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2)), 0) AS VLR_TOTAL
            {joins}
            WHERE {where_base}
              {cat_where}
        """)

    sql_categorias = " UNION ALL ".join(union_parts)
    cat_result = await _run_query(sql_categorias)

    categorias = []
    kpis = []
    if cat_result.get("success"):
        for row in cat_result.get("data", []):
            cat_id = str(row.get("CAT", ""))
            qtd_ped = int(row.get("QTD_PEDIDOS", 0) or 0)
            qtd_prod = int(row.get("QTD_PRODUTOS", 0) or 0)
            vlr = float(row.get("VLR_TOTAL", 0) or 0)
            categorias.append({
                "id": cat_id,
                "nome": cat_names.get(cat_id, cat_id),
                "qtd_pedidos": qtd_ped,
                "qtd_produtos": qtd_prod,
                "valor_total": vlr,
                "valor_fmt": _fmt_brl(vlr),
            })

            # KPIs = categoria ativa (ou 'todos')
            cat_filtro = params.categoria or "todos"
            if cat_id == cat_filtro:
                kpis = [
                    {"label": "Valor Total Pendente", "value": _fmt_brl(vlr), "icon": "💰"},
                    {"label": "Pedidos", "value": str(qtd_ped), "icon": "📦"},
                    {"label": "Itens", "value": str(qtd_prod), "icon": "📋"},
                ]

    # ========================================
    # 2) TABELA DETALHADA (query real do usuario)
    # ========================================
    cat_filtro = params.categoria or "todos"
    cat_filter = cat_filters.get(cat_filtro, "")
    if cat_filtro != "todos":
        filtros["categoria"] = cat_filtro

    sql_table = f"""
        SELECT
            ITE.CODEMP AS COD_EMPRESA,
            EMP.NOMEFANTASIA AS EMPRESA,
            CAB.NUNOTA AS PEDIDO,
            CASE
                WHEN CAB.CODTIPOPER = 1313 THEN 'Casada'
                WHEN CAB.CODTIPOPER = 1301 THEN 'Estoque'
            END AS TIPO_COMPRA,
            TO_CHAR(CAB.DTNEG, 'DD/MM/YY') AS DT_PEDIDO,
            NVL(TO_CHAR(CAB.DTPREVENT, 'DD/MM/YY'), '') AS PREVISAO_ENTREGA,
            CASE
                WHEN CAB.STATUSNOTA = 'L' THEN 'Sim'
                ELSE 'Não'
            END AS CONFIRMADO,
            NVL(VEN.APELIDO, 'SEM COMPRADOR') AS COMPRADOR,
            PRO.CODPROD,
            SUBSTR(PRO.DESCRPROD, 1, 50) AS PRODUTO,
            NVL(MAR.DESCRICAO, '') AS MARCA,
            PAR.NOMEPARC AS FORNECEDOR,
            ITE.CODVOL AS UNIDADE,
            ITE.QTDNEG AS QTD_PEDIDA,
            NVL(V_AGG.TOTAL_ATENDIDO, 0) AS QTD_ATENDIDA,
            (ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) AS QTD_PENDENTE,
            ITE.VLRUNIT AS VLR_UNITARIO,
            ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2) AS VLR_TOTAL_PENDENTE,
            TRUNC(SYSDATE) - TRUNC(CAB.DTNEG) AS DIAS_ABERTO,
            CASE
                WHEN CAB.DTPREVENT IS NULL THEN 'SEM PREVISÃO'
                WHEN CAB.DTPREVENT < SYSDATE THEN 'ATRASADO'
                WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 'PRÓXIMO'
                ELSE 'NO PRAZO'
            END AS STATUS_ENTREGA
        {joins}
        WHERE {where_base}
          {cat_filter}
        ORDER BY
            CASE
                WHEN CAB.DTPREVENT IS NULL THEN 1
                WHEN CAB.DTPREVENT < SYSDATE THEN 0
                WHEN CAB.DTPREVENT < SYSDATE + 7 THEN 2
                ELSE 3
            END,
            MAR.DESCRICAO,
            PRO.DESCRPROD
    """

    table_result = await _run_query(sql_table)
    table_columns = [
        {"key": "EMPRESA", "label": "Empresa", "type": "text"},
        {"key": "PEDIDO", "label": "Pedido", "type": "number"},
        {"key": "TIPO_COMPRA", "label": "Tipo Compra", "type": "text"},
        {"key": "COMPRADOR", "label": "Comprador", "type": "text"},
        {"key": "DT_PEDIDO", "label": "Data Pedido", "type": "text"},
        {"key": "PREVISAO_ENTREGA", "label": "Previsão", "type": "text"},
        {"key": "CONFIRMADO", "label": "Confirmado", "type": "text"},
        {"key": "DIAS_ABERTO", "label": "Dias Aberto", "type": "number"},
        {"key": "STATUS_ENTREGA", "label": "Status", "type": "text"},
        {"key": "CODPROD", "label": "CodProduto", "type": "number"},
        {"key": "PRODUTO", "label": "Produto", "type": "text"},
        {"key": "MARCA", "label": "Marca", "type": "text"},
        {"key": "FORNECEDOR", "label": "Fornecedor", "type": "text"},
        {"key": "UNIDADE", "label": "Un.", "type": "text"},
        {"key": "QTD_PEDIDA", "label": "Qtd Pedida", "type": "number"},
        {"key": "QTD_ATENDIDA", "label": "Qtd Atendida", "type": "number"},
        {"key": "QTD_PENDENTE", "label": "Qtd Pendente", "type": "number"},
        {"key": "VLR_UNITARIO", "label": "Vlr Unit.", "type": "currency"},
        {"key": "VLR_TOTAL_PENDENTE", "label": "Vlr Pendente", "type": "currency"},
    ]

    table_data = table_result.get("data", []) if table_result.get("success") else []

    # ========================================
    # 3) 4 GRAFICOS (agrupamentos como Power BI)
    # ========================================
    # Valor = VLR_TOTAL_PENDENTE (pendente, nao pedido total)

    sql_chart_empresa = f"""
        SELECT NVL(EMP.NOMEFANTASIA, 'N/I') AS LABEL,
               NVL(SUM(ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2)), 0) AS VALOR
        {joins}
        WHERE {where_base} {cat_filter}
        GROUP BY EMP.NOMEFANTASIA
        ORDER BY VALOR DESC
    """

    sql_chart_comprador = f"""
        SELECT NVL(VEN.APELIDO, 'SEM COMPRADOR') AS LABEL,
               NVL(SUM(ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2)), 0) AS VALOR
        {joins}
        WHERE {where_base} {cat_filter}
        GROUP BY VEN.APELIDO
        ORDER BY VALOR DESC
    """

    sql_chart_marca = f"""
        SELECT NVL(MAR.DESCRICAO, 'SEM MARCA') AS LABEL,
               NVL(SUM(ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2)), 0) AS VALOR
        {joins}
        WHERE {where_base} {cat_filter}
        GROUP BY MAR.DESCRICAO
        ORDER BY VALOR DESC
    """

    sql_chart_abc = f"""
        SELECT NVL(PRO.AD_LINHA, 'N/I') AS LABEL,
               NVL(SUM(ROUND((ITE.QTDNEG - NVL(V_AGG.TOTAL_ATENDIDO, 0)) * ITE.VLRUNIT, 2)), 0) AS VALOR
        {joins}
        WHERE {where_base} {cat_filter}
        GROUP BY PRO.AD_LINHA
        ORDER BY VALOR DESC
    """

    r_emp = await _run_query(sql_chart_empresa)
    r_comp = await _run_query(sql_chart_comprador)
    r_marca = await _run_query(sql_chart_marca)
    r_abc = await _run_query(sql_chart_abc)

    def _build_chart(result, title, filter_key, max_items=10):
        chart = {"type": "bar_h", "labels": [], "values": [], "title": title, "filter_key": filter_key}
        if result.get("success"):
            for row in result.get("data", [])[:max_items]:
                lab = str(row.get("LABEL", "?"))
                chart["labels"].append(lab[:25] if len(lab) > 25 else lab)
                chart["values"].append(float(row.get("VALOR", 0) or 0))
        return chart

    charts = [
        _build_chart(r_emp, "Total por empresa", "EMPRESA"),
        _build_chart(r_comp, "Total por comprador", "COMPRADOR"),
        _build_chart(r_marca, "Total por marca", "MARCA", max_items=15),
        _build_chart(r_abc, "Total por curva ABC", "LABEL", max_items=8),
    ]

    chart_data = charts[0] if charts else {}

    # ========================================
    # 4) FILTROS DISPONIVEIS (para dropdowns)
    # ========================================
    sql_filtros_emp = f"SELECT DISTINCT ITE.CODEMP AS CODEMP, NVL(EMP.NOMEFANTASIA, 'N/I') AS NOME {joins} WHERE {where_base} ORDER BY NOME"
    sql_filtros_comp = f"SELECT DISTINCT MAR.AD_CODVEND AS CODVEND, NVL(VEN.APELIDO, 'N/I') AS NOME {joins} WHERE {where_base} AND MAR.AD_CODVEND IS NOT NULL ORDER BY NOME"
    sql_filtros_marca = f"SELECT DISTINCT PRO.CODMARCA AS CODMARCA, NVL(MAR.DESCRICAO, 'N/I') AS NOME {joins} WHERE {where_base} AND PRO.CODMARCA IS NOT NULL ORDER BY NOME"

    r_f_emp = await _run_query(sql_filtros_emp)
    r_f_comp = await _run_query(sql_filtros_comp)
    r_f_marca = await _run_query(sql_filtros_marca)

    def _build_options(result, code_key, name_key):
        opts = []
        seen = set()
        if result.get("success"):
            for row in result.get("data", []):
                code = row.get(code_key)
                name = row.get(name_key, "?")
                if code and code not in seen:
                    opts.append({"value": code, "label": str(name)})
                    seen.add(code)
        return opts

    filtros_disponiveis = {
        "empresas": _build_options(r_f_emp, "CODEMP", "NOME"),
        "compradores": _build_options(r_f_comp, "CODVEND", "NOME"),
        "marcas": _build_options(r_f_marca, "CODMARCA", "NOME"),
    }

    elapsed = int((time.time() - start) * 1000)

    return ReportResponse(
        report_id="pendencia_compras",
        nome="Pendência de Compras",
        kpis=kpis,
        categorias=categorias,
        table_columns=table_columns,
        table_data=table_data,
        chart_data=chart_data,
        charts=charts,
        filtros_aplicados=filtros,
        filtros_disponiveis=filtros_disponiveis,
        time_ms=elapsed,
        row_count=len(table_data),
    )


# ============================================================
# RELATORIO: VENDAS POR PERIODO
# ============================================================

async def report_vendas_periodo(params: ReportRequest, user_context: dict) -> ReportResponse:
    """
    Vendas por Periodo.
    KPIs: total notas, faturamento, ticket medio, comparativo mes anterior
    Tabela: vendas por dia
    Grafico: faturamento diario (linha)
    """
    start = time.time()
    filtros = {}

    # --- Defaults: mes atual ---
    if params.data_ini:
        date_ini_sql = _parse_date(params.data_ini)
        filtros["data_ini"] = params.data_ini
    else:
        date_ini_sql = "TRUNC(SYSDATE, 'MM')"

    if params.data_fim:
        date_fim_sql = _parse_date(params.data_fim) + " + 0.99999"
        filtros["data_fim"] = params.data_fim
    else:
        date_fim_sql = "SYSDATE"

    where_base = f"C.TIPMOV = 'V' AND C.CODTIPOPER IN (1100, 1101) AND C.STATUSNOTA <> 'C' AND C.DTNEG >= {date_ini_sql} AND C.DTNEG <= {date_fim_sql}"

    if params.codemp:
        where_base += f" AND C.CODEMP = {params.codemp}"
        filtros["codemp"] = params.codemp

    # RBAC
    where_rbac = where_base
    role = user_context.get("role", "vendedor")
    if role == "gerente":
        team = user_context.get("team_codvends", [])
        if team:
            where_rbac += f" AND C.CODVEND IN ({','.join(str(c) for c in team)})"
    elif role == "vendedor":
        codvend = user_context.get("codvend", 0)
        if codvend:
            where_rbac += f" AND C.CODVEND = {codvend}"

    # --- KPIs ---
    sql_kpis = f"""
        SELECT
            COUNT(*) AS QTD_VENDAS,
            NVL(SUM(C.VLRNOTA), 0) AS FATURAMENTO,
            NVL(ROUND(AVG(C.VLRNOTA), 2), 0) AS TICKET_MEDIO
        FROM TGFCAB C
        WHERE {where_rbac}
    """

    # KPI comparativo: mes anterior
    sql_mes_ant = f"""
        SELECT
            NVL(SUM(C.VLRNOTA), 0) AS FAT_ANTERIOR
        FROM TGFCAB C
        WHERE C.TIPMOV = 'V'
          AND C.CODTIPOPER IN (1100, 1101)
          AND C.STATUSNOTA <> 'C'
          AND C.DTNEG >= ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -1)
          AND C.DTNEG < TRUNC(SYSDATE, 'MM')
    """

    kpis_result = await _run_query(sql_kpis)
    ant_result = await _run_query(sql_mes_ant)

    kpis = []
    if kpis_result.get("success") and kpis_result.get("data"):
        row = kpis_result["data"][0]
        qtd = int(row.get("QTD_VENDAS", 0))
        fat = float(row.get("FATURAMENTO", 0))
        ticket = float(row.get("TICKET_MEDIO", 0))

        fat_ant = 0
        if ant_result.get("success") and ant_result.get("data"):
            fat_ant = float(ant_result["data"][0].get("FAT_ANTERIOR", 0))

        variacao = ""
        if fat_ant > 0:
            pct = ((fat - fat_ant) / fat_ant) * 100
            sinal = "+" if pct >= 0 else ""
            variacao = f" ({sinal}{pct:.1f}%)"

        kpis = [
            {"label": "Notas de Venda", "value": str(qtd), "icon": "🧾"},
            {"label": "Faturamento", "value": f"R$ {fat:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "icon": "💰"},
            {"label": "Ticket Médio", "value": f"R$ {ticket:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "icon": "📊"},
            {"label": "vs. Mês Anterior", "value": variacao.strip() if variacao.strip() else "N/A", "icon": "📈",
             "alert": variacao and "-" in variacao},
        ]

    # --- Tabela: vendas por dia ---
    sql_table = f"""
        SELECT
            TO_CHAR(TRUNC(C.DTNEG), 'DD/MM/YYYY') AS DATA,
            COUNT(*) AS QTD_VENDAS,
            SUM(C.VLRNOTA) AS FATURAMENTO,
            ROUND(AVG(C.VLRNOTA), 2) AS TICKET_MEDIO
        FROM TGFCAB C
        WHERE {where_rbac}
        GROUP BY TRUNC(C.DTNEG)
        ORDER BY TRUNC(C.DTNEG)
    """

    table_result = await _run_query(sql_table)
    table_columns = [
        {"key": "DATA", "label": "Data", "type": "text"},
        {"key": "QTD_VENDAS", "label": "Qtd Vendas", "type": "number"},
        {"key": "FATURAMENTO", "label": "Faturamento", "type": "currency"},
        {"key": "TICKET_MEDIO", "label": "Ticket Médio", "type": "currency"},
    ]

    table_data = table_result.get("data", []) if table_result.get("success") else []

    # --- Grafico: faturamento por dia (linha) ---
    chart_data = {"type": "line", "labels": [], "values": [], "title": "Faturamento Diário", "filter_key": "DATA"}
    for row in table_data:
        chart_data["labels"].append(row.get("DATA", ""))
        chart_data["values"].append(float(row.get("FATURAMENTO", 0)))

    elapsed = int((time.time() - start) * 1000)

    return ReportResponse(
        report_id="vendas_periodo",
        nome="Vendas por Período",
        kpis=kpis,
        table_columns=table_columns,
        table_data=table_data,
        chart_data=chart_data,
        filtros_aplicados=filtros,
        time_ms=elapsed,
        row_count=len(table_data),
    )


# ============================================================
# RELATORIO: ESTOQUE CRITICO
# ============================================================

async def report_estoque_critico(params: ReportRequest, user_context: dict) -> ReportResponse:
    """
    Estoque Critico - Produtos com estoque <= minimo.
    KPIs: total produtos criticos, valor parado, produtos zerados
    Tabela: produtos com estoque abaixo do minimo
    Grafico: top 10 marcas com mais itens criticos
    """
    start = time.time()
    filtros = {}

    where_base = "E.QTDATUAL <= NVL(E.QTDMIN, 0) AND E.ATIVO = 'S' AND P.ATIVO = 'S'"

    if params.codemp:
        where_base += f" AND E.CODEMP = {params.codemp}"
        filtros["codemp"] = params.codemp

    # --- KPIs ---
    sql_kpis = f"""
        SELECT
            COUNT(*) AS QTD_CRITICOS,
            SUM(CASE WHEN E.QTDATUAL = 0 THEN 1 ELSE 0 END) AS QTD_ZERADOS,
            NVL(SUM(E.QTDATUAL * P.VLRVENDA), 0) AS VLR_PARADO
        FROM TGFEST E
        JOIN TGFPRO P ON E.CODPROD = P.CODPROD
        WHERE {where_base}
          AND NVL(E.QTDMIN, 0) > 0
    """

    kpis_result = await _run_query(sql_kpis)
    kpis = []
    if kpis_result.get("success") and kpis_result.get("data"):
        row = kpis_result["data"][0]
        crit = int(row.get("QTD_CRITICOS", 0))
        zer = int(row.get("QTD_ZERADOS", 0))
        vlr = float(row.get("VLR_PARADO", 0))
        kpis = [
            {"label": "Produtos Críticos", "value": str(crit), "icon": "⚠️", "alert": True},
            {"label": "Estoque Zerado", "value": str(zer), "icon": "🚫", "alert": zer > 0},
            {"label": "Valor Parado", "value": f"R$ {vlr:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "icon": "💰"},
        ]

    # --- Tabela ---
    sql_table = f"""
        SELECT
            P.CODPROD,
            P.DESCRPROD AS PRODUTO,
            M.DESCRICAO AS MARCA,
            E.QTDATUAL AS ESTOQUE_ATUAL,
            NVL(E.QTDMIN, 0) AS ESTOQUE_MIN,
            NVL(E.QTDMIN, 0) - E.QTDATUAL AS FALTA,
            E.CODEMP
        FROM TGFEST E
        JOIN TGFPRO P ON E.CODPROD = P.CODPROD
        LEFT JOIN TGFMAR M ON P.CODMARCA = M.CODMARCA
        WHERE {where_base}
          AND NVL(E.QTDMIN, 0) > 0
        ORDER BY (NVL(E.QTDMIN, 0) - E.QTDATUAL) DESC
    """

    table_result = await _run_query(sql_table)
    table_columns = [
        {"key": "CODPROD", "label": "Código", "type": "number"},
        {"key": "PRODUTO", "label": "Produto", "type": "text"},
        {"key": "MARCA", "label": "Marca", "type": "text"},
        {"key": "ESTOQUE_ATUAL", "label": "Estoque", "type": "number"},
        {"key": "ESTOQUE_MIN", "label": "Mínimo", "type": "number"},
        {"key": "FALTA", "label": "Falta", "type": "number"},
    ]

    table_data = table_result.get("data", []) if table_result.get("success") else []

    # --- Grafico: top 10 marcas criticas ---
    sql_chart = f"""
        SELECT
            NVL(M.DESCRICAO, 'SEM MARCA') AS MARCA,
            COUNT(*) AS QTD
        FROM TGFEST E
        JOIN TGFPRO P ON E.CODPROD = P.CODPROD
        LEFT JOIN TGFMAR M ON P.CODMARCA = M.CODMARCA
        WHERE {where_base}
          AND NVL(E.QTDMIN, 0) > 0
        GROUP BY NVL(M.DESCRICAO, 'SEM MARCA')
        ORDER BY COUNT(*) DESC
    """

    chart_result = await _run_query(sql_chart)
    chart_data = {"type": "bar", "labels": [], "values": [], "title": "Marcas com Mais Itens Críticos", "filter_key": "MARCA"}
    if chart_result.get("success"):
        for row in chart_result.get("data", [])[:10]:
            chart_data["labels"].append(row.get("MARCA", "?"))
            chart_data["values"].append(int(row.get("QTD", 0)))

    elapsed = int((time.time() - start) * 1000)

    return ReportResponse(
        report_id="estoque_critico",
        nome="Estoque Crítico",
        kpis=kpis,
        table_columns=table_columns,
        table_data=table_data,
        chart_data=chart_data,
        filtros_aplicados=filtros,
        time_ms=elapsed,
        row_count=len(table_data),
    )


# ============================================================
# REGISTRO DE RELATORIOS
# ============================================================

REPORT_REGISTRY = {
    "pendencia_compras": {
        "nome": "Pendência de Compras",
        "modulo": "compras",
        "handler": report_pendencia_compras,
        "params": ["data_ini", "data_fim", "codemp"],
    },
    "vendas_periodo": {
        "nome": "Vendas por Período",
        "modulo": "vendas",
        "handler": report_vendas_periodo,
        "params": ["data_ini", "data_fim", "codemp", "codvend"],
    },
    "estoque_critico": {
        "nome": "Estoque Crítico",
        "modulo": "vendas",
        "handler": report_estoque_critico,
        "params": ["codemp"],
    },
}


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/list")
async def list_reports():
    """Lista todos os relatorios disponiveis."""
    reports = []
    for rid, info in REPORT_REGISTRY.items():
        reports.append({
            "id": rid,
            "nome": info["nome"],
            "modulo": info["modulo"],
            "params": info["params"],
        })
    return {"reports": reports}


@router.post("/{report_id}")
async def execute_report(report_id: str, params: ReportRequest, authorization: Optional[str] = Header(None)):
    """Executa um relatorio parametrizado (com cache)."""
    from src.api.app import get_current_user

    session = get_current_user(authorization)

    if report_id not in REPORT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Relatorio '{report_id}' nao encontrado")

    report_info = REPORT_REGISTRY[report_id]

    # Verificar permissao de modulo
    modulo = report_info["modulo"]
    modules = session.get("modules", {})
    if modulo == "compras" and modules.get("reports_compras") is False:
        raise HTTPException(status_code=403, detail="Sem permissao para relatorios de compras")
    if modulo == "vendas" and modules.get("reports_vendas") is False:
        raise HTTPException(status_code=403, detail="Sem permissao para relatorios de vendas")

    # Montar contexto RBAC
    user_context = {
        "user": session["user"],
        "role": session.get("role", "vendedor"),
        "codvend": session.get("codvend", 0),
        "tipvend": session.get("tipvend", ""),
        "team_codvends": session.get("team_codvends", []),
    }

    # Parametros para cache key (sem no_cache)
    params_dict = params.dict(exclude={"no_cache"}, exclude_none=True)

    # Tentar cache (se nao pediu bypass)
    if not params.no_cache:
        cached = _cache.get(report_id, params_dict, user_context)
        if cached is not None:
            cached["from_cache"] = True
            return cached

    # Executar handler (miss no cache ou bypass)
    try:
        result = await report_info["handler"](params, user_context)
        result_dict = result.dict() if hasattr(result, 'dict') else result.__dict__

        # Salvar no cache
        result_dict["from_cache"] = False
        _cache.set(report_id, params_dict, user_context, result_dict)

        return result_dict
    except Exception as e:
        print(f"[REPORT] Erro em {report_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro ao gerar relatorio: {str(e)}")


@router.get("/cache/stats")
async def cache_stats(authorization: Optional[str] = Header(None)):
    """Retorna estatisticas do cache de relatorios."""
    from src.api.app import get_current_user
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin pode ver stats do cache")
    return _cache.stats()


@router.post("/cache/clear")
async def cache_clear(authorization: Optional[str] = Header(None)):
    """Limpa todo o cache de relatorios."""
    from src.api.app import get_current_user
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Apenas admin pode limpar cache")
    _cache.invalidate()
    return {"status": "ok", "message": "Cache limpo"}
