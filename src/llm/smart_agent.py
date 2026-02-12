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
import requests as req_sync
from pathlib import Path
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

from src.llm.query_executor import SafeQueryExecutor
from src.llm.knowledge_base import KnowledgeBase, score_knowledge

# Config
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_CLASSIFIER_MODEL = os.getenv("LLM_CLASSIFIER_MODEL", os.getenv("LLM_MODEL", "qwen3:4b"))
USE_LLM_CLASSIFIER = os.getenv("USE_LLM_CLASSIFIER", "true").lower() in ("true", "1", "yes")
LLM_CLASSIFIER_TIMEOUT = int(os.getenv("LLM_CLASSIFIER_TIMEOUT", "60"))
USE_LLM_NARRATOR = os.getenv("USE_LLM_NARRATOR", "true").lower() in ("true", "1", "yes")
LLM_NARRATOR_TIMEOUT = int(os.getenv("LLM_NARRATOR_TIMEOUT", "60"))
LLM_NARRATOR_MODEL = os.getenv("LLM_NARRATOR_MODEL", os.getenv("LLM_MODEL", "qwen3:4b"))

# Groq API (classifier principal - rapido e gratis)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "10"))
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


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

LLM_CLASSIFIER_PROMPT = """Voce e o interpretador de perguntas do sistema ERP da MMarra Distribuidora Automotiva.
Analise a pergunta do usuario e retorne APENAS um JSON (sem markdown, sem explicacao, sem texto antes ou depois).

# INTENTS POSSIVEIS
- pendencia_compras: pedidos de compra pendentes, o que falta chegar, entregas, previsoes
- estoque: quantidade em estoque, saldo, estoque critico, disponibilidade
- vendas: vendas, faturamento, notas fiscais de venda, receita
- conhecimento: como funcionam processos, regras, politicas, explicacoes do ERP
- saudacao: oi, bom dia, ola
- ajuda: o que voce faz, como funciona, help
- desconhecido: nao se encaixa em nenhum

# CAMPOS DO JSON
- intent: um dos intents acima
- marca: nome da marca mencionada (MAIUSCULO) ou null
- fornecedor: nome do fornecedor ou null
- empresa: nome da empresa/filial ou null
- comprador: nome do comprador ou null
- periodo: "hoje"|"ontem"|"semana"|"mes"|"ano" ou null
- view: "pedidos" (agrupado por pedido - padrao para "qual pedido") ou "itens" (produtos individuais - para "qual item/produto")
- filtro: objeto com instrucoes de filtragem ou null (ver abaixo)
- ordenar: campo para ordenar + _DESC ou _ASC (ver campos abaixo)
- top: numero de resultados desejados ou null (ex: 1 para "qual o...", 5 para "top 5")

# FILTRO - como interpretar pedidos de filtragem
O campo "filtro" permite filtrar os dados retornados. Formato: {"campo": "NOME_DO_CAMPO", "operador": "tipo", "valor": "X"}

Operadores:
- "igual": campo == valor (ex: STATUS_ENTREGA == "ATRASADO")
- "vazio": campo esta vazio/nulo (ex: PREVISAO_ENTREGA sem data)
- "nao_vazio": campo tem valor preenchido
- "maior": campo > valor (numerico)
- "menor": campo < valor (numerico)
- "contem": campo contem texto

# CAMPOS DISPONIVEIS (pendencia_compras) - ATENCAO AOS NOMES:
- PEDIDO: numero do pedido de compra
- DT_PEDIDO: data em que o pedido foi feito (quando compramos)
- PREVISAO_ENTREGA: data prevista para o fornecedor entregar (quando vai chegar)
- CONFIRMADO: se o fornecedor confirmou (S/N)
- STATUS_ENTREGA: situacao da entrega (ATRASADO/NO PRAZO/PROXIMO/SEM PREVISAO)
- DIAS_ABERTO: quantos dias o pedido esta em aberto sem receber
- VLR_PENDENTE: valor em reais do que falta receber
- QTD_PENDENTE: quantidade de pecas que falta receber
- FORNECEDOR, CODPROD, PRODUTO, MARCA, QTD_PEDIDA, VLR_UNITARIO, EMPRESA, COMPRADOR, TIPO_COMPRA

IMPORTANTE - Diferencie corretamente:
- "data de entrega" / "previsao de entrega" / "quando vai chegar" = PREVISAO_ENTREGA (NAO e DT_PEDIDO!)
- "data do pedido" / "quando foi pedido" / "quando comprou" = DT_PEDIDO
- "mais atrasado" / "mais tempo aberto" = DIAS_ABERTO_DESC
- "mais caro" / "maior valor" = VLR_PENDENTE_DESC

Campos para estoque: CODPROD, PRODUTO, MARCA, ESTOQUE_TOTAL, ESTOQUE_MINIMO, CUSTO_MEDIO
Campos para vendas: NUNOTA, CLIENTE, PRODUTO, QTD, VLR_TOTAL, DT_VENDA

# EXEMPLOS
Pergunta: "o que falta chegar da mann?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":null,"top":null}

Pergunta: "qual pedido esta sem previsao de entrega da tome?"
{"intent":"pendencia_compras","marca":"TOME","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"PREVISAO_ENTREGA","operador":"vazio","valor":null},"ordenar":null,"top":1}

Pergunta: "pedidos atrasados da Donaldson"
{"intent":"pendencia_compras","marca":"DONALDSON","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"STATUS_ENTREGA","operador":"igual","valor":"ATRASADO"},"ordenar":null,"top":null}

Pergunta: "qual pedido da sabo tem a maior previsao de entrega?"
{"intent":"pendencia_compras","marca":"SABO","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":"PREVISAO_ENTREGA_DESC","top":1}

Pergunta: "qual pedido da mann foi feito mais recentemente?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":"DT_PEDIDO_DESC","top":1}

Pergunta: "qual o pedido mais caro da Mann?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":"VLR_PENDENTE_DESC","top":1}

Pergunta: "quais pedidos estao confirmados?"
{"intent":"pendencia_compras","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"CONFIRMADO","operador":"igual","valor":"S"},"ordenar":null,"top":null}

Pergunta: "qual item com maior quantidade pendente da Tome?"
{"intent":"pendencia_compras","marca":"TOME","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"itens","filtro":null,"ordenar":"QTD_PENDENTE_DESC","top":1}

Pergunta: "tem algum pedido acima de 50 mil reais?"
{"intent":"pendencia_compras","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"VLR_PENDENTE","operador":"maior","valor":"50000"},"ordenar":null,"top":null}

Pergunta: "vendas de hoje"
{"intent":"vendas","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":"hoje","view":"pedidos","filtro":null,"ordenar":null,"top":null}

Pergunta: "como funciona a compra casada?"
{"intent":"conhecimento","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null}

Agora classifique:
Pergunta: "{question}"
"""


async def groq_classify(question: str) -> Optional[dict]:
    """Chama Groq API para classificar/interpretar a pergunta. Rapido (~0.5s)."""
    if not GROQ_API_KEY:
        return None

    prompt = LLM_CLASSIFIER_PROMPT.replace("{question}", question.replace('"', '\\"'))

    def _call():
        return req_sync.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": 200,
                "top_p": 0.1,
            },
            timeout=GROQ_TIMEOUT,
        )

    try:
        t0 = time.time()
        resp = await asyncio.to_thread(_call)
        elapsed = time.time() - t0

        if resp.status_code == 429:
            print(f"[GROQ] Rate limit atingido ({elapsed:.1f}s) - fallback para Ollama")
            return None

        if resp.status_code != 200:
            print(f"[GROQ] Erro HTTP {resp.status_code} ({elapsed:.1f}s): {resp.text[:200]}")
            return None

        data = resp.json()
        raw = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        # Extrair JSON da resposta
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', raw)
        if not json_match:
            print(f"[GROQ] JSON nao encontrado ({elapsed:.1f}s): {raw[:150]}")
            return None

        result = json.loads(json_match.group())
        print(f"[GROQ] OK ({elapsed:.1f}s): {result}")

        # Normalizar entidades para MAIUSCULO
        for key in ["marca", "fornecedor", "empresa", "comprador"]:
            if result.get(key):
                result[key] = result[key].upper().strip()

        return result

    except req_sync.exceptions.Timeout:
        print(f"[GROQ] Timeout ({GROQ_TIMEOUT}s)")
        return None
    except req_sync.exceptions.ConnectionError:
        print(f"[GROQ] Sem conexao com api.groq.com")
        return None
    except json.JSONDecodeError as e:
        print(f"[GROQ] JSON invalido: {e}")
        return None
    except Exception as e:
        print(f"[GROQ] Erro: {type(e).__name__}: {e}")
        return None


async def ollama_classify(question: str) -> Optional[dict]:
    """Fallback: Ollama local para classificar. Mais lento mas funciona offline."""
    prompt = LLM_CLASSIFIER_PROMPT.replace("{question}", question.replace('"', '\\"'))

    def _call():
        return req_sync.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": LLM_CLASSIFIER_MODEL,
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "{"},
                ],
                "stream": False,
                "options": {"temperature": 0, "num_predict": 200, "top_p": 0.1},
            },
            timeout=LLM_CLASSIFIER_TIMEOUT,
        )

    try:
        t0 = time.time()
        resp = await asyncio.to_thread(_call)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            print(f"[OLLAMA-CLS] Erro HTTP {resp.status_code} ({elapsed:.1f}s)")
            return None

        data = resp.json()
        raw = data.get("message", {}).get("content", "").strip()
        raw = "{" + raw  # Prefixo assistant era "{"

        # Limpar thinking leak
        raw = clean_thinking_leak(raw) if callable(clean_thinking_leak) else raw

        # Extrair JSON
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', raw)
        if not json_match:
            print(f"[OLLAMA-CLS] JSON nao encontrado ({elapsed:.1f}s): {raw[:100]}")
            return None

        result = json.loads(json_match.group())
        print(f"[OLLAMA-CLS] OK ({elapsed:.1f}s): {result}")

        for key in ["marca", "fornecedor", "empresa", "comprador"]:
            if result.get(key):
                result[key] = result[key].upper().strip()

        return result

    except req_sync.exceptions.Timeout:
        print(f"[OLLAMA-CLS] Timeout ({LLM_CLASSIFIER_TIMEOUT}s)")
        return None
    except req_sync.exceptions.ConnectionError:
        print(f"[OLLAMA-CLS] Ollama nao acessivel em {OLLAMA_URL}")
        return None
    except json.JSONDecodeError as e:
        print(f"[OLLAMA-CLS] JSON invalido: {e}")
        return None
    except Exception as e:
        print(f"[OLLAMA-CLS] Erro: {type(e).__name__}: {e}")
        return None


async def llm_classify(question: str) -> Optional[dict]:
    """Classificador inteligente: Groq (rapido) -> Ollama (fallback) -> None."""
    if not USE_LLM_CLASSIFIER:
        return None

    # Tentar Groq primeiro (rapido, ~0.5s)
    if GROQ_API_KEY:
        result = await groq_classify(question)
        if result:
            return result
        print("[LLM-CLS] Groq falhou, tentando Ollama...")

    # Fallback: Ollama local
    result = await ollama_classify(question)
    return result


# ============================================================
# LLM NARRATOR - Explica dados de forma natural
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


def clean_thinking_leak(text: str) -> str:
    """Remove 'thinking in english' que vaza do qwen3 quando think:false nao funciona."""
    if not text:
        return text

    # Limpar tags <think>
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    # Detectar onde comeca o thinking em ingles
    # Patterns comuns: "Hmm,", "Okay,", "Let me", "The user", "I need", "First,", "Wait,"
    leak_patterns = [
        r'\n\s*(Hmm|Okay|Let me|The user|I need|I should|First,|Wait,|Now,|So,|Alright)',
        r'\n\s*(Hmm|Okay|Let me|The user|I need|I should|First,|Wait,)',
    ]
    for pattern in leak_patterns:
        match = re.search(pattern, text)
        if match:
            # Cortar tudo a partir do thinking
            text = text[:match.start()].strip()
            break

    # Se sobrou muito pouco, retorna vazio
    if len(text) < 15:
        return ""

    return text.strip()


async def llm_narrate(question: str, data_summary: str, fallback_response: str) -> str:
    """Pede pra LLM explicar os dados de forma natural. Retorna fallback se falhar."""
    if not USE_LLM_NARRATOR:
        return fallback_response

    user_msg = f"""Pergunta do usuario: "{question}"

Dados retornados do banco:
{data_summary}

Explique esses dados de forma natural e analise o que chama atencao."""

    # Prefixo assistant forca resposta em portugues
    assistant_prefix = "Analisando os dados: "

    def _call():
        return req_sync.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": LLM_NARRATOR_MODEL,
                "messages": [
                    {"role": "system", "content": NARRATOR_SYSTEM},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": assistant_prefix},
                ],
                "stream": False,
                "options": {"temperature": 0.6, "num_predict": 400, "top_p": 0.85},
            },
            timeout=LLM_NARRATOR_TIMEOUT,
        )

    try:
        t0 = time.time()
        resp = await asyncio.to_thread(_call)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            print(f"[NARRATOR] Erro HTTP {resp.status_code} ({elapsed:.1f}s)")
            return fallback_response

        data = resp.json()
        text = data.get("message", {}).get("content", "").strip()
        text = clean_thinking_leak(text)

        # Juntar prefixo + continuacao
        if text:
            text = assistant_prefix + text

        if not text or len(text) < 30:
            print(f"[NARRATOR] Resposta vazia ({elapsed:.1f}s)")
            return fallback_response

        print(f"[NARRATOR] OK ({elapsed:.1f}s, {len(text)} chars)")
        return text

    except req_sync.exceptions.Timeout:
        print(f"[NARRATOR] Timeout ({LLM_NARRATOR_TIMEOUT}s)")
        return fallback_response
    except Exception as e:
        print(f"[NARRATOR] Erro: {type(e).__name__}: {e}")
        return fallback_response


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
        # Status
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

        # Top fornecedores
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

    lines = [
        f"Periodo: {periodo_nome}",
        f"Total: {qtd} notas de venda, faturamento R$ {fat:,.2f}, ticket medio R$ {ticket:,.2f}",
    ]

    if top_vendedores:
        top_str = ", ".join(
            f"{r.get('VENDEDOR','?')}: R$ {float(r.get('FATURAMENTO',0) or 0):,.2f} ({r.get('QTD',0)} notas)"
            for r in top_vendedores[:5] if isinstance(r, dict)
        )
        lines.append(f"Top vendedores: {top_str}")

        # Concentracao
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
        # DA/DE/DO (standalone) + captura ate verbo/preposicao/pontuacao/fim
        stop_after = r'(?:\s+(?:QUE|TEM|TEMOS|COM|SEM|ESTA|ESTAO|FOI|NAO|PARA|POR|EM|NO|NA|NOS|COMO|ONDE|QUAL|QUAIS|ENTRE|ACIMA|ABAIXO)|\s*[?,!.]|\s*$)'
        m = re.search(r'\b(?:DA|DE|DO)\s+([A-Z][A-Z0-9\s\.\-&]{1,30}?)' + stop_after, q_upper)
        if m:
            candidate = m.group(1).strip()
            noise = {"COMPRA", "COMPRAS", "VENDA", "VENDAS", "EMPRESA", "FORNECEDOR",
                     "MARCA", "PRODUTO", "PRODUTOS", "ESTOQUE", "PEDIDO", "PEDIDOS", "MES",
                     "SEMANA", "ANO", "HOJE", "ONTEM", "PERIODO", "SISTEMA",
                     "TODAS", "TODOS", "TUDO", "GERAL", "MINHA", "MINHAS",
                     "ENTREGA", "PREVISAO", "DATA", "CONFIRMACAO", "COMPRADOR",
                     "VALOR", "QUANTIDADE", "STATUS", "PRAZO", "ATRASO",
                     "ESTA", "ESTAO", "ESSE", "ESSA", "ISSO", "AQUI", "ONDE"}
            first_word = candidate.split()[0] if candidate else ""
            if first_word in noise:
                # Buscar ultimo DA/DO (provavelmente antes do nome real)
                last_da = re.search(r'.*\b(?:DA|DO)\s+([A-Z][A-Z0-9\s\.\-&]{1,30}?)' + stop_after, q_upper)
                if last_da:
                    candidate = last_da.group(1).strip()
                    first_word = candidate.split()[0] if candidate else ""
            if candidate not in noise and first_word not in noise and len(candidate) > 1:
                params["marca"] = candidate

    # Estrategia 2: Matching com marcas do banco
    if "marca" not in params and known_marcas:
        # Palavras comuns que NAO devem matchear com marcas
        stop_words = {"DOS", "DAS", "DEL", "UMA", "UNS", "COM", "POR", "QUE",
                       "NAO", "SIM", "MAS", "SEM", "SOB", "TEM", "SAO", "ERA",
                       "FOI", "SER", "TER", "VER", "DAR", "FAZ", "DIZ",
                       "MEU", "SEU", "TEU", "NOS", "VOS", "ELA", "ELE",
                       "PARA", "MAIS", "COMO", "ESSE", "ESSA", "ESTE", "ESTA",
                       "AQUI", "ONDE", "QUAL", "QUEM", "AGORA", "ALEM",
                       "ITENS", "ITEM", "CADA", "DOIS", "TRES", "QUATRO",
                       "PRECISO", "QUERO", "GERAR", "GERA", "TOTAL"}
        # Cada token (e combinacoes de 2) vs banco
        for i, token in enumerate(tokens):
            t_upper = token.upper()
            if len(t_upper) < 3 or t_upper in stop_words:
                continue
            # Match exato
            if t_upper in known_marcas:
                params["marca"] = t_upper
                break
            # Match parcial (token dentro de marca) - minimo 4 chars pra evitar falso positivo
            for m in known_marcas:
                if t_upper in m and len(t_upper) >= 4:
                    params["marca"] = m
                    break
                if m in q_upper and len(m) >= 4:
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
# CONVERSATION CONTEXT - Memoria por usuario
# ============================================================

# Palavras que indicam referencia ao contexto anterior
FOLLOWUP_WORDS = {
    "desses", "destes", "daqueles", "delas", "deles",
    "esses", "estes", "aqueles", "essas", "estas", "aquelas",
    "neles", "nelas", "nisso", "nesse", "nessa", "neste", "nesta",
    "mesma", "mesmo", "mesmos", "mesmas",
    "tambem", "alem", "ainda", "mais",
    "agora", "entao",
}

# Patterns que indicam follow-up (referencia a dados anteriores)
FOLLOWUP_PATTERNS = [
    r'\b(desse[s]?|deste[s]?|daquela?[s]?|dela[s]?|dele[s]?)\b',
    r'\b(esse[s]?|este[s]?|aquele[s]?|essa[s]?|esta[s]?|aquela[s]?)\b',
    r'\b(nele[s]?|nela[s]?|nisso|nesse[s]?|nessa[s]?)\b',
    r'\be (os|as|a|o) (itens|pedidos|pendentes|atrasados)\b',
    r'^e\s+(os|as|quais|quantos|quantas|qual|quanto)\b',
    r'^e\s+(da|do|de|das|dos)\s+',
    r'^(quais|quantos|quantas|qual|quanto)\s+(sao|estao|tem)\s+(os|as|atrasad)',
]

# Patterns que indicam filtro sobre dados anteriores
# Regras de filtro/ordenacao sobre dados anteriores
# ORDEM IMPORTA: patterns mais longos/especificos primeiro
FILTER_RULES = [
    # === PREVISAO DE ENTREGA (mais especificos primeiro!) ===
    {"match": ["maior data de entrega", "maior previsao de entrega", "maior previsao entrega"],
     "sort": "PREVISAO_ENTREGA_DESC", "top": 1},
    {"match": ["menor data de entrega", "menor previsao de entrega", "menor previsao entrega"],
     "sort": "PREVISAO_ENTREGA_ASC", "top": 1},
    {"match": ["data de entrega mais distante", "previsao mais distante", "entrega mais longe"],
     "sort": "PREVISAO_ENTREGA_DESC", "top": 1},
    {"match": ["data de entrega mais proxima", "previsao mais proxima", "proxima entrega"],
     "sort": "PREVISAO_ENTREGA_ASC", "top": 1},
    # === SUPERLATIVOS (sort + top N) ===
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
    # === FILTROS por CAMPO (mais especificos primeiro) ===
    {"match": ["sem previsao de entrega", "sem data de entrega", "sem previsao entrega"],
     "filter_fn": "empty", "filter_field": "PREVISAO_ENTREGA"},
    {"match": ["sem confirmacao", "nao confirmado", "nao confirmados"],
     "filter": {"CONFIRMADO": "N"}},
    {"match": ["confirmado", "confirmados"],           "filter": {"CONFIRMADO": "S"}},
    # === FILTROS por STATUS_ENTREGA ===
    {"match": ["sem previsao"],                        "filter": {"STATUS_ENTREGA": "SEM PREVISAO"}},
    {"match": ["no prazo", "dentro do prazo"],         "filter": {"STATUS_ENTREGA": "NO PRAZO"}},
    {"match": ["atrasado", "atrasados"],               "filter": {"STATUS_ENTREGA": "ATRASADO"}},
    {"match": ["proximo", "proximos"],                 "filter": {"STATUS_ENTREGA": "PROXIMO"}},
]


def _is_complex_query(q_norm: str, tokens: list, pattern_filters: dict) -> bool:
    """Detecta se a query tem complexidade alem de intent+entidade simples.
    Se sim, vale chamar Groq pra interpretar mesmo quando scoring resolveu o intent."""
    # Se pattern ja resolveu filtros, nao precisa Groq
    if pattern_filters:
        return False

    # Palavras que indicam query complexa (filtros, ordenacao, comparacao)
    complexity_words = {
        "maior", "menor", "mais", "menos", "primeiro", "ultimo", "ultima",
        "acima", "abaixo", "entre", "superior", "inferior",
        "sem", "com",
        "previsao", "entrega", "confirmado", "confirmacao",
        "prazo", "atraso", "atrasado", "atrasados",
        "caro", "barato", "urgente", "critico",
        "valor", "quantidade", "data",
        "diferente", "igual", "mesmo", "vazio",
    }
    found = [t for t in tokens if t in complexity_words]
    if len(found) >= 2:
        return True

    # Patterns explicitos de complexidade
    complex_patterns = [
        r'(?:maior|menor|mais|menos)\s+(?:data|valor|quantidade|previsao|prazo|dias)',
        r'(?:sem|com)\s+(?:previsao|confirmacao|data|entrega)',
        r'(?:acima|abaixo)\s+de\s+\d',
        r'(?:entre)\s+\d.*e\s+\d',
        r'(?:data|previsao)\s+de\s+entrega',
    ]
    for p in complex_patterns:
        if re.search(p, q_norm):
            return True

    return False


def _llm_to_filters(llm_result: dict, question: str = "") -> dict:
    """Converte o resultado da LLM (filtro/ordenar/top) no formato de apply_filters.
    Inclui pos-processamento pra corrigir confusoes comuns da LLM."""
    filters = {}

    # Filtro estruturado da LLM
    filtro = llm_result.get("filtro")
    if filtro and isinstance(filtro, dict):
        campo = filtro.get("campo", "")
        operador = filtro.get("operador", "")
        valor = filtro.get("valor")

        if operador == "igual" and campo and valor:
            filters[campo] = str(valor).upper()
        elif operador == "vazio" and campo:
            filters[f"_fn_empty"] = campo
        elif operador == "nao_vazio" and campo:
            filters[f"_fn_not_empty"] = campo
        elif operador == "maior" and campo and valor:
            filters[f"_fn_maior"] = f"{campo}:{valor}"
        elif operador == "menor" and campo and valor:
            filters[f"_fn_menor"] = f"{campo}:{valor}"
        elif operador == "contem" and campo and valor:
            filters[f"_fn_contem"] = f"{campo}:{valor}"

    # Ordenacao
    ordenar = llm_result.get("ordenar")
    if ordenar and isinstance(ordenar, str):
        filters["_sort"] = ordenar.upper()

    # Top N
    top = llm_result.get("top")
    if top and isinstance(top, (int, float)):
        filters["_top"] = int(top)
    elif top and isinstance(top, str) and top.isdigit():
        filters["_top"] = int(top)

    # === POS-PROCESSAMENTO: corrigir confusoes comuns da LLM ===
    if question:
        q_lower = question.lower()
        sort_key = filters.get("_sort", "")

        # Confusao #1: "data de entrega" / "previsao de entrega" → LLM retorna DT_PEDIDO
        entrega_words = ["entrega", "previsao", "chegar", "chegada", "previsão"]
        pedido_words = ["data do pedido", "quando pediu", "quando comprou", "data da compra"]
        mentions_entrega = any(w in q_lower for w in entrega_words)
        mentions_pedido = any(w in q_lower for w in pedido_words)

        if mentions_entrega and not mentions_pedido:
            if "DT_PEDIDO" in sort_key:
                old_sort = sort_key
                filters["_sort"] = sort_key.replace("DT_PEDIDO", "PREVISAO_ENTREGA")
                print(f"[LLM-FIX] Sort corrigido: {old_sort} -> {filters['_sort']} (query menciona entrega)")

    return filters


def detect_followup(tokens: list, question_norm: str) -> bool:
    """Detecta se a pergunta e um follow-up referenciando dados anteriores."""
    # Check tokens (pronomes, advs de continuidade)
    if any(t in FOLLOWUP_WORDS for t in tokens):
        return True
    # Check regex patterns
    for pattern in FOLLOWUP_PATTERNS:
        if re.search(pattern, question_norm):
            return True
    # Pergunta curta com palavras de follow-up implicito
    # Ex: "quantos atrasados?", "qual o mais caro?"
    # Mas NAO pra queries completas como "pedidos pendentes da Donaldson"
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


def detect_filter_request(question_norm: str, tokens: list) -> dict:
    """Detecta se o usuario quer filtrar/ordenar dados anteriores. FILTER_RULES por prioridade."""
    result = {}

    for rule in FILTER_RULES:
        matched = any(m in question_norm for m in rule["match"])
        if not matched:
            continue

        if "filter" in rule:
            result.update(rule["filter"])
        if "filter_fn" in rule:
            # Filtro especial (ex: campo vazio)
            result[f"_fn_{rule['filter_fn']}"] = rule["filter_field"]
        if "sort" in rule:
            result["_sort"] = rule["sort"]
        if "top" in rule:
            result["_top"] = rule["top"]

        # Primeiro match ganha (mais especifico primeiro)
        break

    # Detectar numero explicito na pergunta: "5 mais caros", "top 10", "3 primeiros"
    num_match = re.search(r'\b(\d{1,3})\s+(?:mais|primeiro|primeiros|maior|menor|ultim)', question_norm)
    if not num_match:
        num_match = re.search(r'(?:top|os)\s+(\d{1,3})\b', question_norm)
    if num_match:
        result["_top"] = int(num_match.group(1))

    # "qual" (singular) sem _top = top 1
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

    # Filtros especiais (funcoes)
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
        elif fn_name == "contem" and ":" in str(field_spec):
            campo, texto = str(field_spec).split(":", 1)
            result = [r for r in result if isinstance(r, dict) and texto.upper() in str(r.get(campo, "")).upper()]

    # Filtrar por campo=valor
    for field, value in filters.items():
        if field.startswith("_"):
            continue
        result = [r for r in result if isinstance(r, dict) and str(r.get(field, "")).upper() == value.upper()]

    # Ordenar
    if sort_key and result:
        field, direction = sort_key.rsplit("_", 1)
        reverse = direction == "DESC"
        try:
            # Tentar sort numerico primeiro
            result = sorted(result, key=lambda r: float(r.get(field, 0) or 0), reverse=reverse)
        except (ValueError, TypeError):
            try:
                # Fallback: sort por string (funciona pra datas dd/mm/yyyy invertendo pra yyyy-mm-dd)
                def _sort_key(r):
                    v = str(r.get(field, "") or "")
                    # Converter dd/mm/yyyy pra yyyy-mm-dd pra sort correto
                    if re.match(r'\d{2}/\d{2}/\d{4}', v):
                        parts = v.split("/")
                        return f"{parts[2]}-{parts[1]}-{parts[0]}"
                    return v
                result = sorted(result, key=_sort_key, reverse=reverse)
            except Exception:
                pass

    # Limitar quantidade (top N)
    if top_n and result:
        result = result[:top_n]

    return result


class ConversationContext:
    """Contexto de conversa de um usuario. Guarda parametros e dados anteriores."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.intent = None          # ultimo intent resolvido
        self.params = {}            # {marca, fornecedor, empresa, comprador, periodo}
        self.last_result = {}       # ultimo resultado (detail_data, columns, etc)
        self.last_question = ""     # ultima pergunta
        self.last_view_mode = "pedidos"
        self.turn_count = 0         # quantas perguntas ja fez

    def merge_params(self, new_params: dict) -> dict:
        """Mescla parametros novos com contexto anterior.
        Regra: parametro novo sobrescreve, ausente herda do contexto.
        """
        merged = {}
        param_keys = ["marca", "fornecedor", "empresa", "comprador", "periodo",
                       "codprod", "produto_nome", "pedido"]

        for key in param_keys:
            new_val = new_params.get(key)
            old_val = self.params.get(key)

            if new_val:
                merged[key] = new_val  # Novo sobrescreve
            elif old_val:
                merged[key] = old_val  # Herda do contexto

        return merged

    def update(self, intent: str, params: dict, result: dict, question: str, view_mode: str = "pedidos"):
        """Atualiza contexto apos uma resposta bem-sucedida."""
        self.intent = intent
        # Atualiza params (nao apaga os antigos, so sobrescreve os que vieram)
        for k, v in params.items():
            if v:
                self.params[k] = v
        self.last_result = result
        self.last_question = question
        self.last_view_mode = view_mode
        self.turn_count += 1

    def has_data(self) -> bool:
        """Tem dados anteriores disponíveis para filtrar?"""
        return bool(self.last_result and self.last_result.get("detail_data"))

    def get_data(self) -> list:
        """Retorna dados anteriores."""
        return self.last_result.get("detail_data", [])

    def get_description(self) -> str:
        """Retorna descrição do ultimo resultado."""
        return self.last_result.get("description", "")

    def __repr__(self):
        return f"<Ctx user={self.user_id} intent={self.intent} params={self.params} turns={self.turn_count}>"


# ============================================================
# SMART AGENT v3
# ============================================================

class SmartAgent:
    def __init__(self):
        self.executor = SafeQueryExecutor()
        self._known_marcas = set()
        self._known_empresas = set()
        self._known_compradores = set()
        self._entities_loaded = False
        self.kb = KnowledgeBase()  # Knowledge Base para perguntas sobre processos
        # Contexto POR USUARIO
        self._user_contexts = {}  # {user_id: ConversationContext}

    def _get_context(self, user_id: str) -> 'ConversationContext':
        """Retorna (ou cria) contexto do usuario."""
        if not user_id:
            user_id = "__default__"
        if user_id not in self._user_contexts:
            self._user_contexts[user_id] = ConversationContext(user_id)
        return self._user_contexts[user_id]

    def clear_user(self, user_id: str):
        """Limpa contexto de um usuario especifico (logout)."""
        if user_id in self._user_contexts:
            del self._user_contexts[user_id]
            print(f"[CTX] Contexto limpo: {user_id}")

    def clear(self):
        """Limpa todos os contextos (compatibilidade)."""
        self._user_contexts.clear()
        print(f"[CTX] Todos os contextos limpos")

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
        q_norm = normalize(question)
        user_id = (user_context or {}).get("user", "__default__")
        ctx = self._get_context(user_id)

        # Score de cada intent
        scores = score_intent(tokens)
        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        # ========== CONFIRMACAO CURTA (follow-up excel) ==========
        if len(tokens) <= 3 and any(t in CONFIRM_WORDS for t in tokens) and ctx.has_data():
            print(f"[SMART] Follow-up: gerar_excel")
            return await self._handle_excel_followup(user_context, ctx)

        # Excel explicito
        if scores.get("gerar_excel", 0) >= INTENT_THRESHOLDS["gerar_excel"]:
            if ctx.has_data():
                return await self._handle_excel_followup(user_context, ctx)

        # Saudacao (so se for curta e score alto)
        if scores.get("saudacao", 0) >= INTENT_THRESHOLDS["saudacao"] and len(tokens) <= 5:
            return self._handle_saudacao(user_context)

        # Ajuda
        if scores.get("ajuda", 0) >= INTENT_THRESHOLDS["ajuda"]:
            return self._handle_ajuda()

        # ========== DETECTAR FOLLOW-UP (referencia a dados anteriores) ==========
        is_followup = detect_followup(tokens, q_norm)
        filters = detect_filter_request(q_norm, tokens) if is_followup else {}

        if is_followup and ctx.has_data() and filters:
            # Filtrar dados anteriores
            print(f"[CTX] Follow-up com filtro: {filters} | ctx={ctx}")
            result = self._handle_filter_followup(ctx, filters, question, t0)
            if result:
                return result

        # ========== EXTRAIR PARAMETROS + MERGE COM CONTEXTO ==========
        params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        has_entity = params.get("marca") or params.get("fornecedor") or params.get("comprador") or params.get("empresa")

        # Se e follow-up sem entidade nova, herda do contexto
        if is_followup and not has_entity and ctx.params:
            merged = ctx.merge_params(params)
            if merged != params:
                print(f"[CTX] Herdando contexto: {params} -> {merged}")
                params = merged
                has_entity = params.get("marca") or params.get("fornecedor") or params.get("comprador") or params.get("empresa")

        # Se score baixo mas tem contexto e a pergunta parece continuacao
        if best_score < INTENT_THRESHOLDS.get(best_intent, 8) and is_followup and ctx.intent:
            # Herdar intent anterior se nenhum novo foi detectado forte
            if best_score <= 3:
                best_intent = ctx.intent
                best_score = INTENT_THRESHOLDS.get(best_intent, 8)  # Forca threshold
                print(f"[CTX] Herdando intent: {best_intent} (follow-up sem score)")

        # ========== LAYER 1: SCORING (0ms) ==========
        print(f"[SMART] Scores: pend={scores.get('pendencia_compras',0)} est={scores.get('estoque',0)} vend={scores.get('vendas',0)} | best={best_intent}({best_score}) | followup={is_followup}")

        # Checar knowledge score antes pra decidir rota
        kb_score = score_knowledge(question)

        # Se KB score alto E data score nao e dominante, vai pra knowledge
        if kb_score >= 8 and (best_score < kb_score or best_score < 12):
            print(f"[SMART] Layer 1.2 (knowledge): kb={kb_score} vs data={best_score}")
            kb_result = await self.kb.answer(question)
            if kb_result:
                kb_result["time_ms"] = int((time.time() - t0) * 1000)
                return kb_result

        if best_score >= INTENT_THRESHOLDS.get(best_intent, 8):
            # Score alto = confianca alta no INTENT, mas query pode ter filtros complexos
            print(f"[SMART] Layer 1 (scoring): {best_intent} (score={best_score})")

            # Detectar se query e complexa (filtros/ordenacao que o pattern nao pegou)
            pattern_filters = detect_filter_request(q_norm, tokens)
            is_complex = _is_complex_query(q_norm, tokens, pattern_filters)

            if is_complex and best_intent in ("pendencia_compras", "estoque", "vendas") and GROQ_API_KEY:
                # Query complexa: usar Groq pra interpretar filtros (scoring ja resolveu intent)
                print(f"[SMART] Layer 1+ (Groq filtro): query complexa, consultando Groq...")
                llm_result = await groq_classify(question)
                if llm_result:
                    llm_filters = _llm_to_filters(llm_result, question)
                    # Usar entidades da LLM se scoring nao extraiu direito
                    for key in ["marca", "fornecedor", "empresa", "comprador", "periodo"]:
                        if llm_result.get(key) and not params.get(key):
                            params[key] = llm_result[key]
                        elif llm_result.get(key) and params.get(key):
                            # Se LLM extraiu diferente e parece mais correto (esta nas known_marcas)
                            llm_val = llm_result[key].upper()
                            cur_val = params[key].upper()
                            if key == "marca" and self._known_marcas:
                                # Preferir valor que esta no banco
                                if llm_val in self._known_marcas and cur_val not in self._known_marcas:
                                    print(f"[SMART] LLM corrigiu {key}: {cur_val} -> {llm_val}")
                                    params[key] = llm_val
                    view_mode = llm_result.get("view") or detect_view_mode(tokens)
                    if llm_filters:
                        print(f"[SMART] LLM filters: {llm_filters}")
                    if best_intent == "pendencia_compras":
                        return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx, llm_filters=llm_filters)
                    elif best_intent == "estoque":
                        return await self._handle_estoque(question, user_context, t0, params, ctx)
                    elif best_intent == "vendas":
                        return await self._handle_vendas(question, user_context, t0, params, ctx)

            return await self._dispatch(best_intent, question, user_context, t0, tokens, params, ctx)

        # ========== LAYER 1.5: ENTITY DETECTION ==========
        if has_entity and best_score >= 3:
            # Tem entidade + algum score = provavelmente pendencia
            print(f"[SMART] Layer 1.5 (entidade + score): pendencia | params={params}")
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx)

        # ========== LAYER 2: LLM CLASSIFIER (Groq ~0.5s / Ollama ~10s) ==========
        if USE_LLM_CLASSIFIER:
            print(f"[SMART] Layer 2 (LLM): score ambiguo ({best_score}), consultando LLM...")
            llm_result = await llm_classify(question)

            if llm_result and llm_result.get("intent") not in (None, "desconhecido", ""):
                intent = llm_result["intent"]
                print(f"[SMART] LLM classificou: {intent} | filtro={llm_result.get('filtro')} | ordenar={llm_result.get('ordenar')} | top={llm_result.get('top')}")

                # Se LLM classificou como conhecimento
                if intent == "conhecimento":
                    kb_result = await self.kb.answer(question)
                    if kb_result:
                        kb_result["time_ms"] = int((time.time() - t0) * 1000)
                        return kb_result

                # Usar entidades da LLM se nao extraiu pelo scoring
                for key in ["marca", "fornecedor", "empresa", "comprador", "periodo"]:
                    if llm_result.get(key) and not params.get(key):
                        params[key] = llm_result[key]

                view_mode = llm_result.get("view") or detect_view_mode(tokens)

                # Converter filtro/ordenar/top da LLM em dict de filtros
                llm_filters = _llm_to_filters(llm_result, question)
                if llm_filters:
                    print(f"[SMART] LLM filters convertidos: {llm_filters}")

                if intent == "pendencia_compras":
                    return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx, llm_filters=llm_filters)
                elif intent == "estoque":
                    return await self._handle_estoque(question, user_context, t0, params, ctx)
                elif intent == "vendas":
                    return await self._handle_vendas(question, user_context, t0, params, ctx)
                elif intent == "saudacao":
                    return self._handle_saudacao(user_context)
                elif intent == "ajuda":
                    return self._handle_ajuda()

        # ========== LAYER 3: FALLBACK ==========
        # Ultima tentativa: se tem entidade, assume pendencia
        if has_entity:
            print(f"[SMART] Layer 3 (fallback c/ entidade): {params}")
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx)

        # Ultima tentativa: se tem algum score de knowledge, tenta KB
        if kb_score >= 4:
            print(f"[SMART] Layer 3 (fallback knowledge): kb_score={kb_score}")
            kb_result = await self.kb.answer(question)
            if kb_result:
                kb_result["time_ms"] = int((time.time() - t0) * 1000)
                return kb_result

        return self._handle_fallback(question)

    async def _dispatch(self, intent: str, question: str, user_context: dict, t0: float, tokens: list, params: dict = None, ctx: ConversationContext = None):
        """Despacha para o handler correto baseado no intent."""
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        if intent == "pendencia_compras":
            view_mode = detect_view_mode(tokens)
            return await self._handle_pendencia_compras(question, user_context, t0, params, view_mode, ctx)
        elif intent == "estoque":
            return await self._handle_estoque(question, user_context, t0, params, ctx)
        elif intent == "vendas":
            return await self._handle_vendas(question, user_context, t0, params, ctx)
        elif intent == "saudacao":
            return self._handle_saudacao(user_context)
        elif intent == "ajuda":
            return self._handle_ajuda()
        return self._handle_fallback(question)

    # ---- FILTRO FOLLOW-UP (dados anteriores) ----
    def _handle_filter_followup(self, ctx: ConversationContext, filters: dict, question: str, t0: float):
        """Filtra dados anteriores baseado na pergunta do usuario."""
        data = ctx.get_data()
        if not data:
            return None

        # Guardar meta antes de apply_filters (que faz pop)
        has_sort = "_sort" in filters
        has_top = "_top" in filters
        top_n = filters.get("_top", 0)
        sort_key = filters.get("_sort", "")
        filter_fields = {k: v for k, v in filters.items() if not k.startswith("_")}
        fn_fields = {k: v for k, v in filters.items() if k.startswith("_fn_")}

        filtered = apply_filters(list(data), dict(filters))

        if not filtered:
            desc = ctx.get_description()
            return {
                "response": f"\U0001f914 Nenhum resultado encontrado com esse filtro nos dados de **{desc}**.\n\nTente outra pergunta ou faca uma nova consulta.",
                "tipo": "consulta_banco",
                "query_executed": f"Filtro: {filters}",
                "query_results": 0,
                "time_ms": int((time.time() - t0) * 1000),
            }

        desc = ctx.get_description()
        prev_intent = ctx.intent or "pendencia_compras"

        # Construir descricao do filtro para o titulo
        filter_parts = []
        if filter_fields:
            filter_parts.append(", ".join(f"{v}" for v in filter_fields.values()))
        for fn_key, fn_field in fn_fields.items():
            fn_name = fn_key.replace("_fn_", "")
            if fn_name == "empty":
                filter_parts.append(f"sem {fn_field.lower().replace('_', ' ')}")
        if has_sort and sort_key:
            sort_names = {
                "DIAS_ABERTO_DESC": "mais atrasado", "DIAS_ABERTO_ASC": "mais recente",
                "VLR_PENDENTE_DESC": "maior valor", "VLR_PENDENTE_ASC": "menor valor",
                "DT_PEDIDO_DESC": "mais recente", "QTD_PENDENTE_DESC": "maior quantidade",
            }
            filter_parts.append(sort_names.get(sort_key, sort_key))

        filter_label = " | ".join(filter_parts) if filter_parts else "filtrado"

        if prev_intent == "pendencia_compras":
            # Resposta especial para top 1 (resposta direta)
            if top_n == 1 and len(filtered) == 1:
                r = filtered[0]
                pedido = r.get("PEDIDO", "?")
                produto = r.get("PRODUTO", "?")
                marca = r.get("MARCA", "")
                vlr = float(r.get("VLR_PENDENTE", 0) or 0)
                dias = int(r.get("DIAS_ABERTO", 0) or 0)
                qtd = int(r.get("QTD_PENDENTE", 0) or 0)
                status = r.get("STATUS_ENTREGA", "?")
                fornecedor = r.get("FORNECEDOR", "")

                response = f"\U0001f50d **{filter_label.title()}** de **{desc.title()}**:\n\n"
                response += f"| Campo | Valor |\n|---|---|\n"
                response += f"| **Pedido** | {pedido} |\n"
                if fornecedor: response += f"| **Fornecedor** | {fornecedor} |\n"
                response += f"| **Produto** | {produto} |\n"
                if marca: response += f"| **Marca** | {marca} |\n"
                response += f"| **Qtd. Pendente** | {fmt_num(qtd)} |\n"
                response += f"| **Valor Pendente** | R$ {fmt_num(vlr)} |\n"
                response += f"| **Dias em Aberto** | {dias} dias |\n"
                response += f"| **Status** | {status} |\n"
            else:
                # Tabela normal com KPIs
                view_mode = "itens"
                kpis_data = [{
                    "QTD_PEDIDOS": len(set(str(r.get("PEDIDO", "")) for r in filtered if isinstance(r, dict))),
                    "QTD_ITENS": len(filtered),
                    "VLR_PENDENTE": sum(float(r.get("VLR_PENDENTE", 0) or 0) for r in filtered if isinstance(r, dict)),
                }]
                response = format_pendencia_response(kpis_data, filtered, f"{desc} ({filter_label})", ctx.params, view_mode)
        elif prev_intent == "estoque":
            response = format_estoque_response(filtered, ctx.params)
        elif prev_intent == "vendas":
            kpi_row = {
                "QTD_VENDAS": len(filtered),
                "FATURAMENTO": sum(float(r.get("FATURAMENTO", 0) or 0) for r in filtered if isinstance(r, dict)),
                "TICKET_MEDIO": 0,
            }
            if kpi_row["QTD_VENDAS"]:
                kpi_row["TICKET_MEDIO"] = kpi_row["FATURAMENTO"] / kpi_row["QTD_VENDAS"]
            response = format_vendas_response(kpi_row, f"{desc} ({filter_label})")
        else:
            response = f"Encontrei **{len(filtered)}** registros com o filtro aplicado."

        elapsed = int((time.time() - t0) * 1000)
        return {
            "response": response,
            "tipo": "consulta_banco",
            "query_executed": f"Filtro: {filter_label}",
            "query_results": len(filtered),
            "time_ms": elapsed,
        }

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
        r += "**\U0001f4da Processos e Regras**\n- *\"Como funciona o fluxo de compras?\"*\n- *\"O que e compra casada?\"*\n- *\"Qual a diferenca entre TOP 1301 e 1313?\"*\n\n"
        r += "**\U0001f4e5 Excel**\n- Apos qualquer consulta, diga *\"sim\"* ou *\"gera excel\"*\n\n"
        r += "\U0001f4a1 Tambem temos **Relatorios** completos no menu lateral!"
        return {"response": r, "tipo": "info", "query_executed": None, "query_results": None}

    def _handle_fallback(self, question):
        r = "\U0001f914 Nao entendi a pergunta.\n\nTente algo como:\n- *\"Pendencia da marca Donaldson\"*\n- *\"Vendas de hoje\"*\n- *\"Estoque do produto 133346\"*\n\nOu digite **ajuda** para ver tudo que posso fazer."
        return {"response": r, "tipo": "info", "query_executed": None, "query_results": None}

    # ---- PENDENCIA ----
    async def _handle_pendencia_compras(self, question, user_context, t0, params=None, view_mode="pedidos", ctx=None, llm_filters=None):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        # Merge com contexto se disponivel
        if ctx and not (params.get("marca") or params.get("fornecedor") or params.get("comprador")):
            params = ctx.merge_params(params)
            print(f"[CTX] Params merged: {params}")
        print(f"[SMART] Pendencia params: {params} | view: {view_mode} | llm_filters: {llm_filters}")

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

        result_data = {"detail_data": detail_data, "columns": detail_columns, "description": description, "params": params, "intent": "pendencia_compras"}
        if ctx:
            ctx.update("pendencia_compras", params, result_data, question, view_mode)
            print(f"[CTX] Atualizado: {ctx}")

        # ========== FILTROS (LLM ou pattern-based) ==========
        # Prioridade: LLM filters > inline pattern filters
        active_filters = llm_filters if llm_filters else detect_filter_request(normalize(question), tokenize(question))
        filter_source = "LLM" if llm_filters else "pattern"

        if active_filters and detail_data:
            # Guardar meta antes de apply_filters
            has_top = "_top" in active_filters
            top_n = active_filters.get("_top", 0)
            sort_key = active_filters.get("_sort", "")
            filter_fields = {k: v for k, v in active_filters.items() if not k.startswith("_")}
            fn_fields = {k: v for k, v in active_filters.items() if k.startswith("_fn_")}

            filtered = apply_filters(list(detail_data), dict(active_filters))
            if filtered:
                print(f"[SMART] Filtro ({filter_source}): {active_filters} -> {len(filtered)}/{len(detail_data)} registros")

                # Construir label do filtro
                filter_parts = []
                if filter_fields:
                    filter_parts.append(", ".join(str(v) for v in filter_fields.values()))
                for fn_key, fn_field in fn_fields.items():
                    fn_name = fn_key.replace("_fn_", "")
                    if fn_name == "empty":
                        filter_parts.append(f"sem {fn_field.lower().replace('_', ' ')}")
                    elif fn_name == "not_empty":
                        filter_parts.append(f"com {fn_field.lower().replace('_', ' ')}")
                    elif fn_name in ("maior", "menor") and ":" in str(fn_field):
                        campo, val = str(fn_field).split(":", 1)
                        op = "acima de" if fn_name == "maior" else "abaixo de"
                        filter_parts.append(f"{campo.lower().replace('_', ' ')} {op} {val}")
                if sort_key:
                    sort_names = {"DIAS_ABERTO_DESC": "mais atrasado", "VLR_PENDENTE_DESC": "maior valor",
                                  "VLR_PENDENTE_ASC": "menor valor", "DT_PEDIDO_DESC": "pedido mais recente",
                                  "DT_PEDIDO_ASC": "pedido mais antigo",
                                  "PREVISAO_ENTREGA_DESC": "maior previsao de entrega",
                                  "PREVISAO_ENTREGA_ASC": "menor previsao de entrega",
                                  "QTD_PENDENTE_DESC": "maior quantidade"}
                    filter_parts.append(sort_names.get(sort_key, sort_key.lower().replace("_", " ")))
                filter_label = " | ".join(p for p in filter_parts if p)

                # Se view=pedidos e tem sort/top, agrupar por PEDIDO antes de aplicar top
                if view_mode == "pedidos" and top_n and sort_key:
                    # Pegar o pedido do primeiro item (ja esta ordenado)
                    top_pedido = str(filtered[0].get("PEDIDO", ""))
                    # Buscar TODOS os itens desse pedido nos dados originais
                    pedido_items = [r for r in detail_data if isinstance(r, dict) and str(r.get("PEDIDO", "")) == top_pedido]
                    if pedido_items:
                        filtered = pedido_items
                        print(f"[SMART] Pedido view: pedido {top_pedido} tem {len(pedido_items)} itens")

                # Top 1 + view pedidos = mostrar o PEDIDO completo
                if top_n == 1 and view_mode == "pedidos" and len(filtered) >= 1:
                    pedido_num = str(filtered[0].get("PEDIDO", "?"))
                    fornecedor = filtered[0].get("FORNECEDOR", "?")
                    dt_pedido = filtered[0].get("DT_PEDIDO", "?")
                    previsao = filtered[0].get("PREVISAO_ENTREGA", "?")
                    confirmado = filtered[0].get("CONFIRMADO", "?")
                    status = filtered[0].get("STATUS_ENTREGA", "?")
                    dias = int(filtered[0].get("DIAS_ABERTO", 0) or 0)

                    total_vlr = sum(float(r.get("VLR_PENDENTE", 0) or 0) for r in filtered)
                    total_itens = len(filtered)
                    total_qtd = sum(int(r.get("QTD_PENDENTE", 0) or 0) for r in filtered)

                    response = f"\U0001f50d **{filter_label.title() if filter_label else 'Resultado'}** de **{description.title()}**:\n\n"
                    response += f"| Campo | Valor |\n|---|---|\n"
                    response += f"| **Pedido** | {pedido_num} |\n"
                    response += f"| **Fornecedor** | {fornecedor} |\n"
                    response += f"| **Data Pedido** | {dt_pedido} |\n"
                    response += f"| **Previsao Entrega** | {previsao} |\n"
                    response += f"| **Confirmado** | {confirmado} |\n"
                    response += f"| **Status** | {status} |\n"
                    response += f"| **Dias em Aberto** | {dias} dias |\n"
                    response += f"| **Itens** | {total_itens} |\n"
                    response += f"| **Qtd. Pendente** | {fmt_num(total_qtd)} |\n"
                    response += f"| **Valor Pendente** | R$ {fmt_num(total_vlr)} |\n\n"

                    # Listar itens do pedido
                    if total_itens > 1:
                        response += f"**Itens do pedido {pedido_num}:**\n\n"
                        response += "| Produto | Marca | Qtd | Valor |\n|---|---|---|---|\n"
                        for r in filtered:
                            prod = str(r.get("PRODUTO", "?"))[:40]
                            marca_i = r.get("MARCA", "")
                            qtd_i = int(r.get("QTD_PENDENTE", 0) or 0)
                            vlr_i = float(r.get("VLR_PENDENTE", 0) or 0)
                            response += f"| {prod} | {marca_i} | {fmt_num(qtd_i)} | R$ {fmt_num(vlr_i)} |\n"

                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": total_itens, "time_ms": elapsed}

                # Top 1 + view itens = mostrar 1 item (tabela vertical)
                elif top_n == 1 and len(filtered) == 1:
                    r = filtered[0]
                    response = f"\U0001f50d **{filter_label.title() if filter_label else 'Resultado'}** de **{description.title()}**:\n\n"
                    response += f"| Campo | Valor |\n|---|---|\n"
                    response += f"| **Pedido** | {r.get('PEDIDO', '?')} |\n"
                    if r.get("FORNECEDOR"): response += f"| **Fornecedor** | {r.get('FORNECEDOR')} |\n"
                    response += f"| **Produto** | {r.get('PRODUTO', '?')} |\n"
                    if r.get("MARCA"): response += f"| **Marca** | {r.get('MARCA')} |\n"
                    response += f"| **Qtd. Pendente** | {fmt_num(int(r.get('QTD_PENDENTE', 0) or 0))} |\n"
                    response += f"| **Valor Pendente** | R$ {fmt_num(float(r.get('VLR_PENDENTE', 0) or 0))} |\n"
                    response += f"| **Dias em Aberto** | {int(r.get('DIAS_ABERTO', 0) or 0)} dias |\n"
                    response += f"| **Status** | {r.get('STATUS_ENTREGA', '?')} |\n"
                    if r.get("PREVISAO_ENTREGA"): response += f"| **Previsao Entrega** | {r.get('PREVISAO_ENTREGA')} |\n"
                    if r.get("CONFIRMADO"): response += f"| **Confirmado** | {r.get('CONFIRMADO')} |\n"
                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": 1, "time_ms": elapsed}
                else:
                    # Recalcular KPIs com dados filtrados
                    kpis_data = [{
                        "QTD_PEDIDOS": len(set(str(r.get("PEDIDO", "")) for r in filtered if isinstance(r, dict))),
                        "QTD_ITENS": len(filtered),
                        "VLR_PENDENTE": sum(float(r.get("VLR_PENDENTE", 0) or 0) for r in filtered if isinstance(r, dict)),
                    }]
                    detail_data = filtered
                    desc_filtered = f"{description} ({filter_label})" if filter_label else description
                    fallback_response = format_pendencia_response(kpis_data, detail_data, desc_filtered, params, "itens")
                    elapsed = int((time.time() - t0) * 1000)
                    return {"response": fallback_response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": len(filtered), "time_ms": elapsed}
            else:
                # Filtro retornou 0 resultados - avisar usuario
                print(f"[SMART] Filtro ({filter_source}): 0 resultados")
                filter_parts = []
                for k, v in filter_fields.items():
                    filter_parts.append(str(v))
                for fn_key, fn_field in fn_fields.items():
                    fn_name = fn_key.replace("_fn_", "")
                    if fn_name == "empty":
                        filter_parts.append(f"{fn_field} vazio")
                    elif fn_name in ("maior", "menor") and ":" in str(fn_field):
                        campo, val = str(fn_field).split(":", 1)
                        op = "acima de" if fn_name == "maior" else "abaixo de"
                        filter_parts.append(f"{campo} {op} {val}")
                filter_label = ", ".join(filter_parts) if filter_parts else "filtro aplicado"
                response = f"\U0001f4cb **{description.title()}**\n\n"
                response += f"\U0001f914 Nenhum item encontrado com **{filter_label}**.\n\n"
                response += f"Os {len(detail_data)} itens disponiveis tem os seguintes status: "
                statuses = set(str(r.get("STATUS_ENTREGA", "?")) for r in detail_data if isinstance(r, dict))
                response += ", ".join(f"**{s}**" for s in sorted(statuses)) + "."
                elapsed = int((time.time() - t0) * 1000)
                return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": 0, "time_ms": elapsed}

        fallback_response = format_pendencia_response(kpis_data, detail_data, description, params, view_mode)

        # Narrator: LLM explica os dados naturalmente
        if USE_LLM_NARRATOR and qtd > 0:
            summary = build_pendencia_summary(kpis_data, detail_data, params)
            narration = await llm_narrate(question, summary, "")
            if narration:
                # Monta resposta: analise da LLM + tabela resumida + oferta Excel
                parts = [f"\U0001f4e6 **{description.title()}**\n"]
                parts.append(narration)
                # Adicionar tabela resumida (sem KPIs, a LLM ja falou)
                table_lines = fallback_response.split("\n")
                table_start = next((i for i, l in enumerate(table_lines) if l.startswith("|")), None)
                if table_start is not None:
                    table_section = "\n".join(table_lines[table_start:])
                    parts.append(f"\n{table_section}")
                parts.append(f"\n\U0001f4e5 **Quer que eu gere um arquivo Excel com todos os {fmt_num(int((kpis_data[0] if kpis_data else {}).get('QTD_ITENS', 0) or 0))} itens?**")
                response = "\n".join(parts)
            else:
                response = fallback_response
        else:
            response = fallback_response

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": qtd, "time_ms": elapsed}

    # ---- ESTOQUE ----
    async def _handle_estoque(self, question, user_context, t0, params=None, ctx=None):
        if params is None:
            params = extract_entities(question, self._known_marcas, self._known_empresas, self._known_compradores)
        # Merge com contexto se disponivel
        if ctx and not (params.get("codprod") or params.get("produto_nome") or params.get("marca")):
            params = ctx.merge_params(params)
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

        result_data = {"detail_data": data, "columns": dcols, "description": "estoque", "params": params, "intent": "estoque"}
        if ctx:
            ctx.update("estoque", params, result_data, question)
        fallback_response = format_estoque_response(data, params)

        if USE_LLM_NARRATOR and data:
            summary = build_estoque_summary(data, params)
            narration = await llm_narrate(question, summary, "")
            if narration:
                table_lines = fallback_response.split("\n")
                table_start = next((i for i, l in enumerate(table_lines) if l.startswith("|")), None)
                parts = [narration]
                if table_start is not None:
                    parts.append(f"\n{''.join(table_lines[table_start:])}")
                response = "\n".join(parts)
            else:
                response = fallback_response
        else:
            response = fallback_response

        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql[:200] + "...", "query_results": len(data), "time_ms": elapsed}

    # ---- VENDAS ----
    async def _handle_vendas(self, question, user_context, t0, params=None, ctx=None):
        if params is None:
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

        fallback_response = format_vendas_response(kpi_row, periodo_nome)
        if td:
            fallback_response += "\n**Top vendedores:**\n| Vendedor | Notas | Faturamento |\n|----------|-------|-------------|\n"
            for row in td[:5]:
                if isinstance(row, dict):
                    fallback_response += f"| {str(row.get('VENDEDOR','?'))[:20]} | {fmt_num(row.get('QTD',0))} | {fmt_brl(row.get('FATURAMENTO',0))} |\n"

        if USE_LLM_NARRATOR and int(kpi_row.get("QTD_VENDAS", 0) or 0) > 0:
            summary = build_vendas_summary(kpi_row, td, periodo_nome)
            narration = await llm_narrate(question, summary, "")
            if narration:
                parts = [f"\U0001f4ca **Vendas - {periodo_nome.title()}**\n"]
                parts.append(narration)
                if td:
                    parts.append(f"\n**Top vendedores:**\n| Vendedor | Notas | Faturamento |\n|----------|-------|-------------|")
                    for row in td[:5]:
                        if isinstance(row, dict):
                            parts.append(f"| {str(row.get('VENDEDOR','?'))[:20]} | {fmt_num(row.get('QTD',0))} | {fmt_brl(row.get('FATURAMENTO',0))} |")
                response = "\n".join(parts)
            else:
                response = fallback_response
        else:
            response = fallback_response

        result_data = {"detail_data": td, "columns": ["VENDEDOR","QTD","FATURAMENTO"], "description": f"vendas - {periodo_nome}", "params": params, "intent": "vendas"}
        if ctx:
            ctx.update("vendas", params, result_data, question)
        elapsed = int((time.time() - t0) * 1000)
        return {"response": response, "tipo": "consulta_banco", "query_executed": sql_kpis[:200] + "...", "query_results": int(kpi_row.get("QTD_VENDAS",0) or 0), "time_ms": elapsed}

    # ---- EXCEL ----
    async def _handle_excel_followup(self, user_context, ctx=None):
        last_result = ctx.last_result if ctx else {}
        if not last_result or not last_result.get("detail_data"):
            return {"response": "Nao tenho dados para gerar o arquivo. Faca uma consulta primeiro.", "tipo": "info", "query_executed": None, "query_results": None}
        data = last_result["detail_data"]
        columns = last_result["columns"]
        description = last_result["description"]
        params = last_result.get("params", {})
        intent = last_result.get("intent", "dados")
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
