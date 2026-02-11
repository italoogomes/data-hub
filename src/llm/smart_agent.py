"""
MMarra Data Hub - Smart Agent v3 (Scoring + LLM Classifier)

3 camadas:
- Layer 1: Scoring por palavras-chave (0ms) - resolve 90%+ dos casos
- Layer 2: LLM Classifier (1-3s) - so quando scoring e ambiguo
- Layer 3: Fallback - sugestoes uteis

Entidades (marcas, empresas, compradores) carregadas do banco automaticamente.

Fluxo:
    Pergunta -> Score (0ms) -> [se ambiguo: LLM classifica (1-3s)] -> SQL template -> Sankhya -> Python formata -> Resposta
"""

import re
import os
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from src.llm.query_executor import SafeQueryExecutor

# Config
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", os.getenv("LLM_MODEL", "qwen3:8b"))
USE_LLM_CLASSIFIER = os.getenv("USE_LLM_CLASSIFIER", "true").lower() in ("true", "1", "yes")
LLM_CLASSIFIER_TIMEOUT = int(os.getenv("LLM_CLASSIFIER_TIMEOUT", "8"))


# ============================================================
# SCORING SYSTEM - Palavras-chave e seus pesos por intent
# ============================================================

# Cada palavra/stem ganha pontos pro intent correspondente
# Score >= THRESHOLD = intent detectado

INTENT_SCORES = {
    "pendencia_compras": {
        # Palavras fortes (qualquer uma quase garante o intent)
        "pendencia": 10, "pendencias": 10, "pendente": 10, "pendentes": 10,
        "pend": 8,
        # Contexto compras
        "compra": 6, "compras": 6, "pedido": 5, "pedidos": 5,
        "aberto": 5, "abertos": 5, "atraso": 5, "atrasado": 5, "atrasados": 5,
        # Entidades (reforco)
        "marca": 3, "fornecedor": 3, "comprador": 3, "empresa": 3, "filial": 3,
        # Interrogativos
        "quantos": 2, "quais": 2, "qual": 2, "quanto": 2,
        "tem": 1, "temos": 1, "total": 2, "valor": 2,
        # Verbos
        "falta": 4, "faltam": 4, "faltando": 4, "chegar": 3, "chegando": 3,
        "entrega": 3, "entregar": 3, "previsao": 3,
    },
    "estoque": {
        "estoque": 10, "saldo": 8, "disponivel": 6,
        "produto": 3, "peca": 3, "pecas": 3, "item": 2,
        "critico": 5, "baixo": 4, "zerado": 5, "minimo": 4,
        "acabando": 5, "faltando": 4,
        "quantos": 2, "quanto": 2, "quais": 2,
        "codigo": 2, "cod": 2,
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
}

# Thresholds por intent
INTENT_THRESHOLDS = {
    "pendencia_compras": 8,
    "estoque": 8,
    "vendas": 8,
    "gerar_excel": 8,
    "saudacao": 8,
    "ajuda": 8,
}

# Palavras de confirmacao (para follow-up/excel)
CONFIRM_WORDS = {"sim", "quero", "pode", "claro", "isso", "ok", "beleza", "bora", "vamos", "manda", "faz", "gera", "gere"}

# Score pra decidir se mostra ITENS ou PEDIDOS
VIEW_ITEM_WORDS = {"itens", "item", "produtos", "produto", "detalhe", "detalhes", "detalhado", "lista", "listagem", "peca", "pecas"}
VIEW_ORDER_WORDS = {"pedidos", "pedido", "resumo", "agrupado", "consolidado"}


def normalize(text: str) -> str:
    """Remove acentos e normaliza texto."""
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u',
        'ç': 'c',
    }
    t = text.lower().strip()
    for old, new in replacements.items():
        t = t.replace(old, new)
    return t


def tokenize(text: str) -> list:
    """Extrai palavras normalizadas."""
    return re.findall(r'[a-z0-9]+', normalize(text))


def score_intent(tokens: list) -> dict:
    """Calcula score de cada intent baseado nos tokens."""
    scores = {}
    for intent_id, keywords in INTENT_SCORES.items():
        s = 0
        for token in tokens:
            if token in keywords:
                s += keywords[token]
        scores[intent_id] = s
    return scores


def detect_view_mode(tokens: list) -> str:
    """Decide se mostra itens ou pedidos."""
    item_score = sum(1 for t in tokens if t in VIEW_ITEM_WORDS)
    order_score = sum(1 for t in tokens if t in VIEW_ORDER_WORDS)
    if item_score > order_score:
        return "itens"
    return "pedidos"


# ============================================================
# LLM CLASSIFIER (Layer 2 - so quando scoring e ambiguo)
# ============================================================

LLM_CLASSIFIER_PROMPT = """Voce e um classificador de perguntas para um sistema ERP de distribuidora de autopecas.
Analise a pergunta e retorne APENAS um JSON (sem markdown, sem explicacao).

Intents possiveis:
- pendencia_compras: perguntas sobre pedidos de compra pendentes, o que falta chegar, entregas atrasadas
- estoque: perguntas sobre quantidade em estoque, estoque critico, saldo de produtos
- vendas: perguntas sobre vendas, faturamento, notas fiscais de venda
- saudacao: oi, bom dia, ola
- ajuda: o que voce faz, como funciona, help
- desconhecido: nao se encaixa em nenhum

Campos do JSON:
- intent: um dos intents acima
- marca: nome da marca mencionada ou null
- fornecedor: nome do fornecedor ou null
- empresa: nome da empresa/filial ou null
- comprador: nome do comprador ou null
- periodo: hoje|ontem|semana|mes|ano ou null
- view: "itens" se quer ver produtos individuais, "pedidos" se quer ver agrupado por pedido

Exemplos:
Pergunta: "o que falta chegar da mann?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos"}

Pergunta: "quais produtos estao pendentes da tome?"
{"intent":"pendencia_compras","marca":"TOME","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"itens"}

Pergunta: "quanto vendemos hoje?"
{"intent":"vendas","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":"hoje","view":"pedidos"}

Pergunta: "tem saldo do produto 133346?"
{"intent":"estoque","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"itens"}

Agora classifique:
Pergunta: "{question}"
"""


async def llm_classify(question: str) -> Optional[dict]:
    """Chama LLM local (Ollama) para classificar intent. Timeout curto, fallback-safe."""
    if not USE_LLM_CLASSIFIER:
        return None

    try:
        import httpx
    except ImportError:
        print("[LLM-CLS] httpx nao instalado, pulando classificador")
        return None

    prompt = LLM_CLASSIFIER_PROMPT.replace("{question}", question.replace('"', '\\"'))

    try:
        t0 = time.time()
        async with httpx.AsyncClient(timeout=LLM_CLASSIFIER_TIMEOUT) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": LLM_CLASSIFIER_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0,
                        "num_predict": 150,  # Resposta curta
                        "top_p": 0.1,
                    },
                },
            )

        elapsed = time.time() - t0

        if resp.status_code != 200:
            print(f"[LLM-CLS] Erro HTTP {resp.status_code} ({elapsed:.1f}s)")
            return None

        data = resp.json()
        raw = data.get("response", "").strip()

        # Extrair JSON da resposta (pode vir com markdown)
        json_match = re.search(r'\{[^}]+\}', raw)
        if not json_match:
            print(f"[LLM-CLS] JSON nao encontrado na resposta ({elapsed:.1f}s): {raw[:100]}")
            return None

        result = json.loads(json_match.group())
        print(f"[LLM-CLS] OK ({elapsed:.1f}s): {result}")

        # Normalizar
        if result.get("marca"):
            result["marca"] = result["marca"].upper().strip()
        if result.get("fornecedor"):
            result["fornecedor"] = result["fornecedor"].upper().strip()
        if result.get("empresa"):
            result["empresa"] = result["empresa"].upper().strip()
        if result.get("comprador"):
            result["comprador"] = result["comprador"].upper().strip()

        return result

    except httpx.TimeoutException:
        print(f"[LLM-CLS] Timeout ({LLM_CLASSIFIER_TIMEOUT}s) - pulando")
        return None
    except json.JSONDecodeError as e:
        print(f"[LLM-CLS] JSON invalido: {e}")
        return None
    except httpx.ConnectError:
        print(f"[LLM-CLS] Ollama nao acessivel em {OLLAMA_URL}")
        return None
    except Exception as e:
        print(f"[LLM-CLS] Erro inesperado: {e}")
        return None


# ============================================================
# ENTITY EXTRACTION (scoring-based, not regex-dependent)
# ============================================================

def extract_entities(question: str, known_marcas: set = None, known_empresas: set = None, known_compradores: set = None) -> dict:
    """Extrai entidades da pergunta usando matching com banco."""
    params = {}
    q_upper = question.upper().strip()
    q_norm = normalize(question)
    tokens = tokenize(question)

    # ---- MARCA ----
    # Estrategia 1: "marca X" ou "da X"
    m = re.search(r'(?:MARCA\s+)([A-Z][A-Z0-9\s\.\-&]{1,35}?)(?:\s*[?,!.]|\s+(?:QUE|TEM|TEMOS|EU|TENHO)|\s*$)', q_upper)
    if m:
        params["marca"] = m.group(1).strip()

    if "marca" not in params:
        m = re.search(r'(?:D[AEO])\s+([A-Z][A-Z0-9\s\.\-&]{1,30}?)(?:\s*[?,!.]|\s*$)', q_upper)
        if m:
            candidate = m.group(1).strip()
            noise = {"COMPRA", "COMPRAS", "VENDA", "VENDAS", "EMPRESA", "FORNECEDOR",
                     "MARCA", "PRODUTO", "ESTOQUE", "PEDIDO", "PEDIDOS", "MES",
                     "SEMANA", "ANO", "HOJE", "ONTEM", "PERIODO", "SISTEMA",
                     "TODAS", "TODOS", "TUDO", "GERAL", "MINHA", "MINHAS"}
            if candidate not in noise and len(candidate) > 1:
                params["marca"] = candidate

    # Estrategia 2: Matching com marcas do banco
    if "marca" not in params and known_marcas:
        # Cada token (e combinacoes de 2) vs banco
        for i, token in enumerate(tokens):
            t_upper = token.upper()
            if len(t_upper) < 2:
                continue
            # Match exato
            if t_upper in known_marcas:
                params["marca"] = t_upper
                break
            # Match parcial (token dentro de marca ou marca dentro de token)
            for m in known_marcas:
                m_norm = normalize(m)
                if t_upper in m and len(t_upper) >= 3:
                    params["marca"] = m
                    break
                if m in q_upper and len(m) >= 3:
                    params["marca"] = m
                    break
            if "marca" in params:
                break

    # ---- FORNECEDOR ----
    m = re.search(r'FORNECEDOR\s+([A-Z][A-Z\s\.\-&]{2,40}?)(?:\s*[?,!.]|\s*$)', q_upper)
    if m:
        params["fornecedor"] = m.group(1).strip()

    # ---- EMPRESA ----
    m = re.search(r'(?:EMPRESA|FILIAL|UNIDADE|LOJA)\s+([A-Z][A-Z\s\-]{2,30}?)(?:\s*[?,!.]|\s*$)', q_upper)
    if m:
        params["empresa"] = m.group(1).strip()

    if "empresa" not in params and known_empresas:
        for emp in known_empresas:
            if emp in q_upper and len(emp) >= 3:
                params["empresa"] = emp
                break

    # Cidades conhecidas como filiais
    cidades = {"ARACATUBA": "ARACAT", "RIBEIRAO": "RIBEIR", "UBERLANDIA": "UBERL",
               "ITUMBIARA": "ITUMBI", "RIO VERDE": "RIO VERDE"}
    if "empresa" not in params:
        for k, v in cidades.items():
            if k in q_upper or k in normalize(question).upper():
                params["empresa"] = v
                break

    # ---- COMPRADOR ----
    m = re.search(r'COMPRADOR[A]?\s+([A-Z][A-Z\s]{2,25}?)(?:\s*[?,!.]|\s*$)', q_upper)
    if m:
        params["comprador"] = m.group(1).strip()

    if "comprador" not in params and known_compradores:
        for comp in known_compradores:
            if comp in q_upper and len(comp) >= 3:
                params["comprador"] = comp
                break

    # ---- NUMERO PEDIDO ----
    m = re.search(r'(?:PEDIDO|NOTA|NUNOTA)\s*(?:N(?:UMERO)?\.?)?\s*(\d{4,10})', q_upper)
    if m:
        params["nunota"] = int(m.group(1))

    # ---- CODIGO PRODUTO ----
    m = re.search(r'(?:CODIGO|COD|CODPROD|PRODUTO)\s*(\d{3,8})', q_upper)
    if m:
        params["codprod"] = int(m.group(1))

    # ---- NOME PRODUTO ----
    m = re.search(r'(?:PRODUTO|PECA|ITEM)\s+([A-Z][A-Z0-9\s\-/]{3,40}?)(?:\s*[?,!.]|\s*$)', q_upper)
    if m and "codprod" not in params:
        candidate = m.group(1).strip()
        noise_prod = {"TEM", "TEMOS", "NO", "ESTOQUE", "PENDENTE", "EM", "ABERTO"}
        if candidate not in noise_prod:
            params["produto_nome"] = candidate

    # ---- PERIODO ----
    q_lower = question.lower()
    if "hoje" in q_lower:
        params["periodo"] = "hoje"
    elif "ontem" in q_lower:
        params["periodo"] = "ontem"
    elif re.search(r'(essa|esta|nessa|nesta)\s*semana', q_lower):
        params["periodo"] = "semana"
    elif re.search(r'(esse|este|nesse|neste)\s*mes', q_norm):
        params["periodo"] = "mes"
    elif re.search(r'mes\s+(passado|anterior)', q_norm):
        params["periodo"] = "mes_passado"
    elif re.search(r'semana\s+(passada|anterior)', q_norm):
        params["periodo"] = "semana_passada"

    return params


# ============================================================
# SQL TEMPLATES
# ============================================================

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


def _build_where_extra(params, user_context=None):
    w = ""
    if params.get("marca"):
        w += f" AND UPPER(MAR.DESCRICAO) LIKE UPPER('%{params['marca']}%')"
    if params.get("fornecedor"):
        w += f" AND UPPER(PAR.NOMEPARC) LIKE UPPER('%{params['fornecedor']}%')"
    if params.get("empresa"):
        w += f" AND UPPER(EMP.NOMEFANTASIA) LIKE UPPER('%{params['empresa']}%')"
    if params.get("comprador"):
        w += f" AND UPPER(VEN.APELIDO) LIKE UPPER('%{params['comprador']}%')"
    if params.get("nunota"):
        w += f" AND CAB.NUNOTA = {params['nunota']}"
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
    if params.get("empresa"): filtro_desc.append(f"empresa **{params['empresa']}**")
    if params.get("comprador"): filtro_desc.append(f"comprador **{params['comprador']}**")
    if params.get("nunota"): filtro_desc.append(f"pedido **{params['nunota']}**")
    desc = "pendencia de compras"
    if filtro_desc: desc += " da " + ", ".join(filtro_desc)
    return sql_kpis, sql_detail, desc


def _build_periodo_filter(params, date_col="C.DTNEG"):
    p = params.get("periodo", "mes")
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


# ============================================================
# FORMATACAO
# ============================================================

def fmt_brl(valor):
    try:
        v = float(valor or 0)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

def fmt_num(valor):
    try:
        return f"{int(float(valor or 0)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def format_pendencia_response(kpis_data, detail_data, description, params, view_mode="pedidos"):
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
            lines.append("**Itens pendentes:**\n")
            lines.append("| Pedido | CodProd | Produto | Marca | Qtd Pend. | Valor | Status |")
            lines.append("|--------|---------|---------|-------|-----------|-------|--------|")
            for item in detail_data[:12]:
                if isinstance(item, dict):
                    lines.append(f"| {item.get('PEDIDO','?')} | {item.get('CODPROD','?')} | {str(item.get('PRODUTO',''))[:30]} | {str(item.get('MARCA',''))[:15]} | {item.get('QTD_PENDENTE',0)} | {fmt_brl(item.get('VLR_PENDENTE',0))} | {item.get('STATUS_ENTREGA','?')} |")
            if len(detail_data) > 12:
                lines.append(f"\n*...e mais {len(detail_data) - 12} itens.*\n")
        else:
            pedidos = {}
            for item in detail_data:
                if not isinstance(item, dict):
                    continue
                ped = item.get("PEDIDO", "?")
                if ped not in pedidos:
                    pedidos[ped] = {"pedido": ped, "fornecedor": str(item.get("FORNECEDOR",""))[:30], "dt_pedido": item.get("DT_PEDIDO",""), "status": item.get("STATUS_ENTREGA","?"), "itens": 0, "valor": 0.0}
                pedidos[ped]["itens"] += 1
                pedidos[ped]["valor"] += float(item.get("VLR_PENDENTE", 0) or 0)

            lines.append("**Pedidos:**\n")
            lines.append("| Pedido | Fornecedor | Data | Itens | Valor Pendente | Status |")
            lines.append("|--------|------------|------|-------|----------------|--------|")
            for pd in list(pedidos.values())[:10]:
                lines.append(f"| {pd['pedido']} | {pd['fornecedor']} | {pd['dt_pedido']} | {pd['itens']} | {fmt_brl(pd['valor'])} | {pd['status']} |")
            if len(pedidos) > 10:
                lines.append(f"\n*...e mais {len(pedidos) - 10} pedidos.*\n")

    lines.append(f"\n\U0001f4e5 **Quer que eu gere um arquivo Excel com todos os {fmt_num(qtd_itens)} itens?**")
    return "\n".join(lines)


def format_vendas_response(kpis_data, periodo_nome):
    qtd = int(kpis_data.get("QTD_VENDAS", 0) or 0)
    fat = float(kpis_data.get("FATURAMENTO", 0) or 0)
    ticket = float(kpis_data.get("TICKET_MEDIO", 0) or 0)
    if qtd == 0:
        return f"Nao encontrei vendas para o periodo **{periodo_nome}**."
    lines = [f"\U0001f4ca **Vendas - {periodo_nome.title()}**\n",
             f"**{fmt_num(qtd)}** notas de venda com faturamento total de **{fmt_brl(fat)}**.",
             f"Ticket medio: **{fmt_brl(ticket)}**.\n"]
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
# EXCEL GENERATION
# ============================================================

def generate_excel(data, columns, filename, title=""):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return generate_csv(data, columns, filename)

    wb = Workbook()
    ws = wb.active
    ws.title = "Dados"
    hfill = PatternFill(start_color="0E75B9", end_color="0E75B9", fill_type="solid")
    hfont = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    dfont = Font(name="Arial", size=9)
    brd = Border(bottom=Side(style="thin", color="E0E0E0"))
    sr = 1
    if title:
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
        ws.cell(row=1, column=1, value=title).font = Font(name="Arial", size=12, bold=True, color="0E75B9")
        ws.cell(row=2, column=1, value=f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}").font = Font(name="Arial", size=8, color="888888")
        sr = 4
    for ci, cn in enumerate(columns, 1):
        c = ws.cell(row=sr, column=ci, value=cn); c.font = hfont; c.fill = hfill; c.alignment = Alignment(horizontal="center", vertical="center")
    ccols = {"VLR_UNITARIO","VLR_PENDENTE","VLR_TOTAL_PENDENTE","VALOR","FATURAMENTO","TICKET_MEDIO"}
    ncols = {"QTD_PEDIDA","QTD_ATENDIDA","QTD_PENDENTE","DIAS_ABERTO","CODPROD","PEDIDO","ESTOQUE","ESTMIN","QTD"}
    for ri, rd in enumerate(data, sr + 1):
        for ci, cn in enumerate(columns, 1):
            val = rd.get(cn, "") if isinstance(rd, dict) else (rd[ci-1] if ci <= len(rd) else "")
            cell = ws.cell(row=ri, column=ci, value=val); cell.font = dfont; cell.border = brd
            if cn in ccols:
                try: cell.value = float(val or 0); cell.number_format = '#,##0.00'; cell.alignment = Alignment(horizontal="right")
                except: pass
            elif cn in ncols:
                try: cell.value = int(float(val or 0)); cell.alignment = Alignment(horizontal="right")
                except: pass
    for ci, cn in enumerate(columns, 1):
        ml = len(str(cn))
        for ri in range(sr+1, min(sr+50, len(data)+sr+1)):
            cv = ws.cell(row=ri, column=ci).value
            if cv: ml = max(ml, min(len(str(cv)), 40))
        ws.column_dimensions[get_column_letter(ci)].width = ml + 3
    ws.auto_filter.ref = f"A{sr}:{get_column_letter(len(columns))}{sr + len(data)}"
    ws.freeze_panes = ws.cell(row=sr + 1, column=1)
    static_dir = Path(__file__).parent.parent / "api" / "static" / "exports"
    static_dir.mkdir(parents=True, exist_ok=True)
    fp = static_dir / filename; wb.save(str(fp)); return str(fp)


def generate_csv(data, columns, filename):
    static_dir = Path(__file__).parent.parent / "api" / "static" / "exports"
    static_dir.mkdir(parents=True, exist_ok=True)
    fp = static_dir / filename.replace(".xlsx", ".csv")
    with open(fp, "w", encoding="utf-8-sig") as f:
        f.write(";".join(columns) + "\n")
        for row in data:
            vals = [str(row.get(c,"")).replace(";",",") for c in columns] if isinstance(row, dict) else [str(v).replace(";",",") for v in row]
            f.write(";".join(vals) + "\n")
    return str(fp)


# ============================================================
# SMART AGENT v2
# ============================================================

class SmartAgent:
    def __init__(self):
        self.executor = SafeQueryExecutor()
        self.last_result = {}
        self._known_marcas = set()
        self._known_empresas = set()
        self._known_compradores = set()
        self._entities_loaded = False

    async def _load_entities(self):
        """Carrega entidades do banco (1x, depois cache)."""
        if self._entities_loaded:
            return
        try:
            # Marcas
            r = await self.executor.execute("SELECT UPPER(TRIM(DESCRICAO)) AS M FROM TGFMAR WHERE DESCRICAO IS NOT NULL")
            if r.get("success"):
                for row in r.get("data", []):
                    v = row.get("M", row[0] if isinstance(row, (list, tuple)) else "") if isinstance(row, dict) else (str(row[0]) if isinstance(row, (list, tuple)) and row else "")
                    if v and len(v) > 1: self._known_marcas.add(v.strip())
            # Empresas
            r = await self.executor.execute("SELECT UPPER(TRIM(NOMEFANTASIA)) AS E FROM TSIEMP WHERE NOMEFANTASIA IS NOT NULL")
            if r.get("success"):
                for row in r.get("data", []):
                    v = row.get("E", row[0] if isinstance(row, (list, tuple)) else "") if isinstance(row, dict) else (str(row[0]) if isinstance(row, (list, tuple)) and row else "")
                    if v and len(v) > 1: self._known_empresas.add(v.strip())
            # Compradores (via marcas)
            r = await self.executor.execute("SELECT DISTINCT UPPER(TRIM(V.APELIDO)) AS C FROM TGFVEN V JOIN TGFMAR M ON M.AD_CODVEND = V.CODVEND WHERE V.APELIDO IS NOT NULL")
            if r.get("success"):
                for row in r.get("data", []):
                    v = row.get("C", row[0] if isinstance(row, (list, tuple)) else "") if isinstance(row, dict) else (str(row[0]) if isinstance(row, (list, tuple)) and row else "")
                    if v and len(v) > 1: self._known_compradores.add(v.strip())
            print(f"[SMART] Entidades: {len(self._known_marcas)} marcas, {len(self._known_empresas)} empresas, {len(self._known_compradores)} compradores")
        except Exception as e:
            print(f"[SMART] Erro ao carregar entidades: {e}")
        self._entities_loaded = True

    async def ask(self, question: str, user_context: dict = None) -> Optional[dict]:
        await self._load_entities()
        t0 = time.time()
        tokens = tokenize(question)

        # Score de cada intent
        scores = score_intent(tokens)
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # ========== CONFIRMACAO CURTA (follow-up) ==========
        if len(tokens) <= 3 and any(t in CONFIRM_WORDS for t in tokens) and self.last_result:
            print(f"[SMART] Follow-up: gerar_excel")
            return await self._handle_excel_followup(user_context)

        # Excel explicito
        if scores.get("gerar_excel", 0) >= INTENT_THRESHOLDS["gerar_excel"]:
            if self.last_result:
                return await self._handle_excel_followup(user_context)

        # Saudacao (so se for curta e score alto)
        if scores.get("saudacao", 0) >= INTENT_THRESHOLDS["saudacao"] and len(tokens) <= 5:
            return self._handle_saudacao(user_context)

        # Ajuda
        if scores.get("ajuda", 0) >= INTENT_THRESHOLDS["ajuda"]:
            return self._handle_ajuda()

        # ========== LAYER 1: SCORING (0ms) ==========
        print(f"[SMART] Scores: pend={scores.get('pendencia_compras',0)} est={scores.get('estoque',0)} vend={scores.get('vendas',0)} | best={best_intent}({best_score})")

        if best_score >= INTENT_THRESHOLDS.get(best_intent, 8):
            # Score alto = confianca alta, executa direto
            print(f"[SMART] Layer 1 (scoring): {best_intent} (score={best_score})")
            return await self._dispatch(best_intent, question, user_context, t0, tokens)

        # ========== LAYER 1.5: ENTITY DETECTION ==========
        params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        has_entity = params.get("marca") or params.get("fornecedor") or params.get("comprador") or params.get("empresa")

        if has_entity and best_score >= 3:
            # Tem entidade + algum score = provavelmente pendencia
            print(f"[SMART] Layer 1.5 (entidade + score): pendencia | params={params}")
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode)

        # ========== LAYER 2: LLM CLASSIFIER (1-3s) ==========
        if USE_LLM_CLASSIFIER:
            print(f"[SMART] Layer 2 (LLM classifier): score ambiguo ({best_score}), consultando LLM...")
            llm_result = await llm_classify(question)

            if llm_result and llm_result.get("intent") not in (None, "desconhecido", ""):
                intent = llm_result["intent"]
                print(f"[SMART] LLM classificou: {intent}")

                # Usar entidades da LLM se nao extraiu pelo scoring
                if llm_result.get("marca") and not params.get("marca"):
                    params["marca"] = llm_result["marca"]
                if llm_result.get("fornecedor") and not params.get("fornecedor"):
                    params["fornecedor"] = llm_result["fornecedor"]
                if llm_result.get("empresa") and not params.get("empresa"):
                    params["empresa"] = llm_result["empresa"]
                if llm_result.get("comprador") and not params.get("comprador"):
                    params["comprador"] = llm_result["comprador"]
                if llm_result.get("periodo") and not params.get("periodo"):
                    params["periodo"] = llm_result["periodo"]

                view_mode = llm_result.get("view", detect_view_mode(tokens))

                if intent == "pendencia_compras":
                    return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode)
                elif intent == "estoque":
                    return await self._handle_estoque(question, user_context, t0)
                elif intent == "vendas":
                    return await self._handle_vendas(question, user_context, t0)
                elif intent == "saudacao":
                    return self._handle_saudacao(user_context)
                elif intent == "ajuda":
                    return self._handle_ajuda()

        # ========== LAYER 3: FALLBACK ==========
        # Ultima tentativa: se tem entidade, assume pendencia
        if has_entity:
            print(f"[SMART] Layer 3 (fallback c/ entidade): {params}")
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode)

        return self._handle_fallback(question)

    async def _dispatch(self, intent: str, question: str, user_context: dict, t0: float, tokens: list):
        """Despacha para o handler correto baseado no intent."""
        if intent == "pendencia_compras":
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, None, view_mode)
        elif intent == "estoque":
            return await self._handle_estoque(question, user_context, t0)
        elif intent == "vendas":
            return await self._handle_vendas(question, user_context, t0)
        elif intent == "saudacao":
            return self._handle_saudacao(user_context)
        elif intent == "ajuda":
            return self._handle_ajuda()
        return self._handle_fallback(question)

    # ---- SAUDACAO ----
    def _handle_saudacao(self, user_context=None):
        nome = (user_context or {}).get("user", "")
        hora = datetime.now().hour
        saud = "Bom dia" if hora < 12 else ("Boa tarde" if hora < 18 else "Boa noite")
        r = f"{saud}{', ' + nome if nome else ''}! \U0001f44b\n\n"
        r += "Como posso ajudar? Posso consultar:\n\n"
        r += "\U0001f4e6 **Pendencia de compras** - *\"pendencia da marca Donaldson\"*\n"
        r += "\U0001f4ca **Vendas e faturamento** - *\"vendas de hoje\"*\n"
        r += "\U0001f4cb **Estoque** - *\"estoque do produto 133346\"*\n\nE so perguntar!"
        return {"response": r, "tipo": "info", "query_executed": None, "query_results": None}

    def _handle_ajuda(self):
        r = "\U0001f916 **O que posso fazer:**\n\n"
        r += "**\U0001f4e6 Pendencia de Compras**\n- *\"Pendencia da marca Donaldson\"*\n- *\"Itens pendentes da Tome\"*\n- *\"Pedidos em aberto do comprador Juliano\"*\n\n"
        r += "**\U0001f4ca Vendas**\n- *\"Vendas de hoje\"* / *\"Faturamento do mes\"*\n\n"
        r += "**\U0001f4cb Estoque**\n- *\"Estoque do produto 133346\"*\n- *\"Estoque critico\"*\n\n"
        r += "**\U0001f4e5 Excel**\n- Apos qualquer consulta, diga *\"sim\"* ou *\"gera excel\"*\n\n"
        r += "\U0001f4a1 Tambem temos **Relatorios** completos no menu lateral!"
        return {"response": r, "tipo": "info", "query_executed": None, "query_results": None}

    def _handle_fallback(self, question):
        r = "\U0001f914 Nao entendi a pergunta.\n\nTente algo como:\n- *\"Pendencia da marca Donaldson\"*\n- *\"Vendas de hoje\"*\n- *\"Estoque do produto 133346\"*\n\nOu digite **ajuda** para ver tudo que posso fazer."
        return {"response": r, "tipo": "info", "query_executed": None, "query_results": None}

    # ---- PENDENCIA ----
    async def _handle_pendencia_compras(self, question, user_context, t0, params=None, view_mode="pedidos"):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        print(f"[SMART] Pendencia params: {params} | view: {view_mode}")

        sql_kpis, sql_detail, description = sql_pendencia_compras(params, user_context)
        kpis_result = await self.executor.execute(sql_kpis)
        if not kpis_result.get("success"):
            return {"response": f"Erro ao consultar: {kpis_result.get('error','?')}", "tipo": "consulta_banco", "query_executed": sql_kpis[:200], "query_results": 0}

        kpis_data = kpis_result.get("data", [])
        if kpis_data and isinstance(kpis_data[0], (list, tuple)):
            cols = kpis_result.get("columns") or ["QTD_PEDIDOS", "QTD_ITENS", "VLR_PENDENTE"]
            kpis_data = [dict(zip(cols, row)) for row in kpis_data]

        qtd = int((kpis_data[0] if kpis_data else {}).get("QTD_PEDIDOS", 0) or 0)
        detail_data = []
        detail_columns = ["EMPRESA","PEDIDO","TIPO_COMPRA","COMPRADOR","DT_PEDIDO","PREVISAO_ENTREGA","CONFIRMADO","FORNECEDOR","CODPROD","PRODUTO","MARCA","UNIDADE","QTD_PEDIDA","QTD_ATENDIDA","QTD_PENDENTE","VLR_UNITARIO","VLR_PENDENTE","DIAS_ABERTO","STATUS_ENTREGA"]

        if qtd > 0:
            dr = await self.executor.execute(sql_detail)
            if dr.get("success"):
                detail_data = dr.get("data", [])
                if detail_data and isinstance(detail_data[0], (list, tuple)):
                    rc = dr.get("columns") or detail_columns
                    if rc and len(rc) == len(detail_data[0]):
                        detail_data = [dict(zip(rc, row)) for row in detail_data]
                    else:
                        detail_data = [dict(zip(detail_columns, row)) for row in detail_data]

        self.last_result = {"detail_data": detail_data, "columns": detail_columns, "description": description, "params": params, "intent": "pendencia_compras"}
        response = format_pendencia_response(kpis_data, detail_data, description, params, view_mode)
        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": qtd, "time_ms": elapsed}

    # ---- ESTOQUE ----
    async def _handle_estoque(self, question, user_context, t0):
        params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        print(f"[SMART] Estoque params: {params}")
        q_norm = normalize(question)
        is_critico = any(w in q_norm for w in ["critico", "baixo", "zerado", "minimo", "acabando", "faltando"])

        if params.get("codprod"):
            sql = f"SELECT EMP.NOMEFANTASIA AS EMPRESA, E.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA, NVL(E.ESTOQUE,0) AS ESTOQUE, NVL(E.ESTMIN,0) AS ESTMIN FROM TGFEST E JOIN TGFPRO PRO ON PRO.CODPROD=E.CODPROD LEFT JOIN TGFMAR MAR ON MAR.CODIGO=PRO.CODMARCA LEFT JOIN TSIEMP EMP ON EMP.CODEMP=E.CODEMP WHERE E.CODPROD={params['codprod']} AND E.CODLOCAL=0 AND NVL(E.ATIVO,'S')='S' ORDER BY EMP.NOMEFANTASIA"
            dcols = ["EMPRESA","CODPROD","PRODUTO","MARCA","ESTOQUE","ESTMIN"]
        elif params.get("produto_nome"):
            sql = f"SELECT EMP.NOMEFANTASIA AS EMPRESA, E.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA, NVL(E.ESTOQUE,0) AS ESTOQUE, NVL(E.ESTMIN,0) AS ESTMIN FROM TGFEST E JOIN TGFPRO PRO ON PRO.CODPROD=E.CODPROD LEFT JOIN TGFMAR MAR ON MAR.CODIGO=PRO.CODMARCA LEFT JOIN TSIEMP EMP ON EMP.CODEMP=E.CODEMP WHERE UPPER(PRO.DESCRPROD) LIKE UPPER('%{params['produto_nome']}%') AND E.CODLOCAL=0 AND NVL(E.ATIVO,'S')='S' AND NVL(E.ESTOQUE,0)>0 ORDER BY E.ESTOQUE DESC"
            dcols = ["EMPRESA","CODPROD","PRODUTO","MARCA","ESTOQUE","ESTMIN"]
        elif is_critico or params.get("marca"):
            we = f"AND UPPER(MAR.DESCRICAO) LIKE UPPER('%{params['marca']}%')" if params.get("marca") else ""
            sql = f"SELECT E.CODPROD, PRO.DESCRPROD AS PRODUTO, NVL(MAR.DESCRICAO,'') AS MARCA, SUM(NVL(E.ESTOQUE,0)) AS ESTOQUE, MAX(NVL(E.ESTMIN,0)) AS ESTMIN FROM TGFEST E JOIN TGFPRO PRO ON PRO.CODPROD=E.CODPROD LEFT JOIN TGFMAR MAR ON MAR.CODIGO=PRO.CODMARCA WHERE E.CODLOCAL=0 AND NVL(E.ATIVO,'S')='S' AND NVL(E.ESTMIN,0)>0 {we} GROUP BY E.CODPROD, PRO.DESCRPROD, MAR.DESCRICAO HAVING SUM(NVL(E.ESTOQUE,0))<=MAX(NVL(E.ESTMIN,0)) ORDER BY SUM(NVL(E.ESTOQUE,0))"
            dcols = ["CODPROD","PRODUTO","MARCA","ESTOQUE","ESTMIN"]
        else:
            return {"response": "\U0001f4cb Para consultar estoque, me diga:\n\n- O **codigo** do produto: *\"estoque do produto 133346\"*\n- O **nome** da peca: *\"estoque da correia ventilador\"*\n- **Estoque critico**: *\"produtos com estoque critico\"*", "tipo": "info", "query_executed": None, "query_results": None}

        result = await self.executor.execute(sql)
        if not result.get("success"):
            return {"response": f"Erro ao consultar estoque: {result.get('error','?')}", "tipo": "consulta_banco", "query_executed": sql[:200], "query_results": 0}
        data = result.get("data", [])
        if data and isinstance(data[0], (list, tuple)):
            rc = result.get("columns") or dcols
            data = [dict(zip(rc if rc and len(rc)==len(data[0]) else dcols, row)) for row in data]

        self.last_result = {"detail_data": data, "columns": dcols, "description": "estoque", "params": params, "intent": "estoque"}
        response = format_estoque_response(data, params)
        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql[:200] + "...", "query_results": len(data), "time_ms": elapsed}

    # ---- VENDAS ----
    async def _handle_vendas(self, question, user_context, t0):
        params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        print(f"[SMART] Vendas params: {params}")
        periodo = params.get("periodo", "mes")
        periodo_nome = PERIODO_NOMES.get(periodo, "este mes")
        pf = _build_periodo_filter(params)
        rbac = ""
        if user_context:
            role = user_context.get("role", "vendedor")
            if role in ("admin", "diretor", "ti"):
                pass
            elif role == "gerente":
                team = user_context.get("team_codvends", [])
                if team: rbac = f" AND C.CODVEND IN ({','.join(str(c) for c in team)})"
            elif role == "vendedor":
                codvend = user_context.get("codvend", 0)
                if codvend: rbac = f" AND C.CODVEND = {codvend}"
        emp_f = f" AND UPPER(EMP.NOMEFANTASIA) LIKE UPPER('%{params['empresa']}%')" if params.get("empresa") else ""

        sql_kpis = f"SELECT COUNT(*) AS QTD_VENDAS, NVL(SUM(C.VLRNOTA),0) AS FATURAMENTO, NVL(ROUND(AVG(C.VLRNOTA),2),0) AS TICKET_MEDIO FROM TGFCAB C LEFT JOIN TSIEMP EMP ON EMP.CODEMP=C.CODEMP WHERE C.TIPMOV='V' AND C.CODTIPOPER IN (1100,1101) AND C.STATUSNOTA<>'C' {pf} {rbac} {emp_f}"
        sql_top = f"SELECT NVL(V.APELIDO,'SEM VENDEDOR') AS VENDEDOR, COUNT(*) AS QTD, NVL(SUM(C.VLRNOTA),0) AS FATURAMENTO FROM TGFCAB C LEFT JOIN TGFVEN V ON V.CODVEND=C.CODVEND LEFT JOIN TSIEMP EMP ON EMP.CODEMP=C.CODEMP WHERE C.TIPMOV='V' AND C.CODTIPOPER IN (1100,1101) AND C.STATUSNOTA<>'C' {pf} {rbac} {emp_f} GROUP BY V.APELIDO ORDER BY SUM(C.VLRNOTA) DESC"

        kr = await self.executor.execute(sql_kpis)
        if not kr.get("success"):
            return {"response": f"Erro ao consultar vendas: {kr.get('error','?')}", "tipo": "consulta_banco", "query_executed": sql_kpis[:200], "query_results": 0}
        kd = kr.get("data", [])
        if kd and isinstance(kd[0], (list, tuple)):
            cols = kr.get("columns") or ["QTD_VENDAS","FATURAMENTO","TICKET_MEDIO"]
            kd = [dict(zip(cols, row)) for row in kd]
        kpi_row = kd[0] if kd else {}

        tr = await self.executor.execute(sql_top)
        td = []
        if tr.get("success"):
            td = tr.get("data", [])
            if td and isinstance(td[0], (list, tuple)):
                tc = tr.get("columns") or ["VENDEDOR","QTD","FATURAMENTO"]
                td = [dict(zip(tc, row)) for row in td]

        response = format_vendas_response(kpi_row, periodo_nome)
        if td:
            response += "\n**Top vendedores:**\n| Vendedor | Notas | Faturamento |\n|----------|-------|-------------|\n"
            for row in td[:5]:
                if isinstance(row, dict):
                    response += f"| {str(row.get('VENDEDOR','?'))[:20]} | {fmt_num(row.get('QTD',0))} | {fmt_brl(row.get('FATURAMENTO',0))} |\n"

        self.last_result = {"detail_data": td, "columns": ["VENDEDOR","QTD","FATURAMENTO"], "description": f"vendas - {periodo_nome}", "params": params, "intent": "vendas"}
        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": int(kpi_row.get("QTD_VENDAS",0) or 0), "time_ms": elapsed}

    # ---- EXCEL ----
    async def _handle_excel_followup(self, user_context):
        if not self.last_result or not self.last_result.get("detail_data"):
            return {"response": "Nao tenho dados para gerar o arquivo. Faca uma consulta primeiro.", "tipo": "info", "query_executed": None, "query_results": None}
        data = self.last_result["detail_data"]
        columns = self.last_result["columns"]
        description = self.last_result["description"]
        params = self.last_result.get("params", {})
        intent = self.last_result.get("intent", "dados")
        fn = params.get("marca") or params.get("fornecedor") or params.get("empresa") or params.get("periodo", "geral")
        fn = re.sub(r'[^\w\s-]', '', str(fn)).strip().replace(' ', '_')
        filename = f"{intent}_{fn}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        try:
            fp = generate_excel(data=data, columns=columns, filename=filename, title=description.title())
            rp = Path(fp).name
            url = f"/static/exports/{rp}"
            s = "s" if len(data) > 1 else ""
            r = f"\U0001f4ca **Arquivo gerado com sucesso!**\n\n**{len(data)} registro{s}** exportado{s}.\n\n\U0001f4e5 **[Clique aqui para baixar]({url})**\n\n*Arquivo: {rp}*"
            return {"response": r, "tipo": "arquivo", "query_executed": None, "query_results": len(data), "download_url": url}
        except Exception as e:
            return {"response": f"Erro ao gerar arquivo: {str(e)}", "tipo": "erro", "query_executed": None, "query_results": None}

    def clear(self):
        self.last_result = {}