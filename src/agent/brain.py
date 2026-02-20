"""
MMarra Data Hub - Cerebro Analitico.

Detecta perguntas analiticas e escala pro modelo 70b.
Intercepta no roteamento (com contexto de sessao) ou na narracao (sem contexto).

Fluxo:
  1. is_analytical_query() detecta se a pergunta exige raciocinio
  2. Se tem contexto de sessao → brain_analyze() responde direto com 70b
  3. Se nao tem contexto → routing normal busca dados, narrator usa 70b
"""

import re
import time
from typing import Optional


# ============================================================
# ANALYTICAL KEYWORDS & PATTERNS
# ============================================================

# Palavras/frases que indicam pergunta analitica (requer raciocinio)
# NOTA: Para patterns com variacoes (eu/posso/oq), usar _ANALYTICAL_PATTERNS (regex)
_ANALYTICAL_KEYWORDS = [
    # Causa (simples)
    "qual o motivo", "qual motivo", "qual a causa", "qual a razao",
    "qual a razão", "o que causou", "o que causa", "o que levou a",
    "motivo de", "razao de", "razão de",
    # Sugestao / recomendacao
    "sugira", "sugestao", "sugestão", "sugestoes", "sugestões",
    "recomenda", "recomende", "recomendacao", "recomendação",
    # Decisao
    "vale a pena", "compensa", "deveria", "devemos",
    "seria melhor", "faz sentido", "é viável", "e viavel",
    # Avaliacao
    "avalie", "avaliação", "avaliacao",
    # Analise / tendencia
    "analise", "análise", "analisar", "tendencia", "tendência",
    "previsao", "previsão", "projecao", "projeção",
    "perspectiva", "cenario", "cenário",
    # Interpretacao
    "o que isso significa", "o que significa", "o que isso quer dizer",
    "como interpretar",
    # Comparacao analitica (nao temporal — temporal e multi-step)
    "qual é melhor", "qual e melhor", "qual rende mais",
    "diferenca entre", "diferença entre",
    "qual a melhor opcao", "qual a melhor opção", "qual a melhor escolha",
    "qual o melhor jeito", "qual a melhor forma",
    # Impacto / consequencia
    "impacto", "consequencia", "consequência",
    "o que acontece se", "o que aconteceria",
    # Investigacao
    "investigue", "investigar", "aprofunde", "detalhe mais",
    "explique melhor", "entender melhor",
    # Estrategia
    "estrategia", "estratégia", "plano de acao", "plano de ação",
    "proximo passo", "próximo passo", "proximos passos", "próximos passos",
]

# Patterns regex para perguntas analiticas
# Regex cobre variacoes de linguagem natural (eu, oq, pq, tá, dá, etc.)
_ANALYTICAL_PATTERNS = [
    # ---- CONSULTIVOS (pedem acao/conselho) ----
    r"\bo\s*q(?:ue)?\s+(?:eu\s+)?posso\s+fazer\b",   # "o que (eu) posso fazer", "oq posso fazer"
    r"\bo\s*q(?:ue)?\s+fazer\b",                       # "o que fazer pra...", "oq fazer"
    r"\bcomo\s+(?:eu\s+)?(?:posso\s+)?(?:melhorar|resolver|reduzir|aumentar|evitar|solucionar)\b",
    r"\btem\s+como\s+(?:melhorar|resolver|reduzir|aumentar)\b",  # "tem como melhorar"
    r"\bd[aá]\s+pra\s+(?:melhorar|resolver|reduzir|aumentar)\b", # "dá pra melhorar"
    r"\bme\s+(?:d[aáeê]|passa)\s+sugest",             # "me dá sugestões", "me dê sugestões"
    r"\bme\s+(?:explica|recomend[ae])\b",              # "me explica", "me recomende"

    # ---- CAUSAIS (pedem explicacao) ----
    r"\bpor\s*qu[eê]\b",                              # "por que caiu?", "por quê?"
    r"\bporque\s+(?:que\s+)?(?:o|a|os|as)\b",         # "porque que os pedidos..."
    r"\bpq\b",                                         # "pq caiu?" (informal)
    r"\bqual\s+(?:o\s+)?(?:motivo|razao|razão|causa)\b",
    r"\bo\s+que\s+(?:aconteceu|houve)\b",             # "o que aconteceu com..."

    # ---- DECISORIOS (pedem opiniao) ----
    r"\bdevo\s+\w",                                    # "devo focar em...", "devo trocar"
    r"\b[eé]\s+melhor\b",                             # "é melhor trocar?"

    # ---- AVALIATIVOS (pedem analise) ----
    r"\bcomo\s+(?:estamos|est[aá])\b",                # "como estamos?", "como está?"
    r"\bt[aá]\s+(?:bom|ruim|bem|mal)\b",              # "tá bom?", "tá ruim?"
    r"\best[aá]\s+(?:bom|ruim|bem|mal)\b",            # "está bom?", "está ruim?"
    r"\bqual\s+(?:a\s+)?(?:tendencia|tendência|previsao|previsão)\b",

    # ---- FOLLOW-UP ANALITICO ----
    r"^e\s+a(?:gora|[ií])\s*\?",                     # "e agora?", "e aí?"
    r"\bo\s+que\s+(?:eu\s+)?(?:posso|devo)\s+fazer\s+com\s+isso\b",
]

# Palavras que DESQUALIFICAM como analitica (perguntas fatuais simples)
_FACTUAL_OVERRIDES = [
    "quanto", "quantos", "quantas", "qual o valor", "qual valor",
    "qual o total", "qual total", "qual o estoque", "qual estoque",
    "lista", "listar", "mostra", "mostrar",
    "ajuda", "oi ", "bom dia", "boa tarde", "boa noite",
    "quero um relatorio", "quero um relatório", "gera relatorio", "gera relatório",
]


# ============================================================
# DETECTION
# ============================================================

def is_analytical_query(question: str) -> bool:
    """Detecta se a pergunta exige raciocinio analitico (70b) ou e fatual simples (8b).

    Preferimos falsos negativos (nao detectar analitica) a falsos positivos
    (classificar fatual como analitica e desperdicar tokens 70b).

    Returns:
        True se a pergunta e analitica (escalar pro 70b).
        False se e fatual/simples (manter no 8b).
    """
    q = question.lower().strip()

    if not q or len(q) < 10:
        return False

    # Check factual overrides first — perguntas que comecam com "quanto/qual valor"
    # sao fatuais mesmo que contenham keywords analiticas
    for kw in _FACTUAL_OVERRIDES:
        if q.startswith(kw):
            return False

    # Check keywords
    for kw in _ANALYTICAL_KEYWORDS:
        if kw in q:
            return True

    # Check regex patterns
    for pat in _ANALYTICAL_PATTERNS:
        if re.search(pat, q):
            return True

    return False


# ============================================================
# ANALYTICAL SYSTEM PROMPT
# ============================================================

ANALYTICAL_SYSTEM = """Voce e o analista de dados senior da MMarra Distribuidora Automotiva.
Seu trabalho e analisar dados do ERP e fornecer insights acionaveis para a equipe.

REGRA ABSOLUTA: Responda DIRETAMENTE em portugues brasileiro. NUNCA pense em voz alta. NUNCA comece com Okay, Let me, The user, First, I need. Va direto ao ponto.

REGRAS OBRIGATORIAS:
1. USE APENAS os dados fornecidos no contexto. NUNCA invente numeros — se nao tem, diga "nao tenho essa informacao"
2. Cite valores EXATOS do resumo (R$, quantidades, percentuais). Copie os numeros, nao recalcule
3. O "Resumo da consulta anterior" tem os totais corretos — USE-OS como fonte primaria
4. Organize em: Situacao → Pontos de atencao → Recomendacoes
5. Seja direto e pratico — os usuarios sao funcionarios operacionais, nao analistas
6. Use numeros formatados (R$ 29.401, nao 29401.19)
7. Use **negrito** pra destacar insights e numeros-chave
8. Limite a 3-5 paragrafos. Sem enrolacao
9. NAO repita dados em tabela — isso ja foi feito
10. Sugira acoes PRATICAS e ESPECIFICAS (ex: "ligar pro fornecedor X sobre o pedido Y")

FORMATO:
- Comece com a situacao geral (numeros do resumo)
- Aponte problemas/riscos identificados nos dados
- Termine com recomendacoes numeradas e acionaveis"""


# ============================================================
# SESSION CONTEXT COLLECTOR
# ============================================================

def collect_session_context(ctx) -> Optional[dict]:
    """Coleta dados relevantes da sessao para o brain analisar.

    Args:
        ctx: ConversationContext da sessao atual

    Returns:
        dict com dados da sessao, ou None se nao tem contexto relevante.
    """
    if not ctx or not ctx.intent:
        print(f"[BRAIN] collect_context: sem ctx ou intent (ctx={ctx is not None}, "
              f"intent={getattr(ctx, 'intent', 'N/A')})")
        return None

    if not ctx.has_data():
        # Log detalhado pra debug: quais chaves existem no last_result?
        _keys = list((ctx.last_result or {}).keys()) if ctx.last_result else []
        print(f"[BRAIN] collect_context: has_data=False (intent={ctx.intent}, "
              f"last_result keys={_keys})")
        return None

    data = ctx.get_data()
    if not data:
        print(f"[BRAIN] collect_context: get_data vazio (intent={ctx.intent})")
        return None

    # Pegar texto da resposta anterior (ja formatado com numeros)
    response_text = ctx.last_result.get("response", "") if ctx.last_result else ""

    result = {
        "intent": ctx.intent,
        "params": ctx.params or {},
        "description": ctx.get_description(),
        "last_question": ctx.last_question,
        "data": data[:30],  # Max 30 rows pro prompt nao estourar
        "total_rows": len(data),
        "response_text": response_text[:1500],  # Texto formatado (compacto)
    }
    print(f"[BRAIN] collect_context: OK (intent={ctx.intent}, "
          f"rows={len(data)}, response_len={len(response_text)})")
    return result


_MAX_CONTEXT_CHARS = 6000  # ~1500 tokens — cabe no 70b sem estourar


def _format_context_for_llm(context_data: dict) -> str:
    """Formata contexto da sessao para o prompt do 70b.

    Prioridade: narracao anterior > resumo calculado > amostra de dados.
    A narracao ja tem os totais corretos — e a fonte primaria.
    """
    parts = []

    # 1. Metadata
    parts.append(f"Consulta anterior: \"{context_data['last_question']}\"")
    parts.append(f"Dominio: {context_data['intent']}")
    if context_data["params"]:
        params_str = ", ".join(f"{k}={v}" for k, v in context_data["params"].items() if v)
        if params_str:
            parts.append(f"Filtros: {params_str}")
    parts.append(f"Total de registros: {context_data['total_rows']}")

    # 2. Narracao anterior (PRIORIDADE — ja tem KPIs, totais, percentuais)
    response_text = context_data.get("response_text", "")
    if response_text:
        # Limpar markdown pesado e emojis pra economizar tokens
        clean = _clean_response_for_context(response_text)
        parts.append(f"\n--- RESUMO DA CONSULTA ANTERIOR ---\n{clean}")

    # 3. Resumo calculado dos dados brutos (complementa a narracao)
    data = context_data.get("data", [])
    intent = context_data.get("intent", "")
    if data:
        summary = _summarize_data(data, intent)
        if summary:
            parts.append(f"\n--- DADOS CALCULADOS ---\n{summary}")

    # 4. Amostra de dados (so se sobrar espaco)
    result = "\n".join(parts)
    remaining = _MAX_CONTEXT_CHARS - len(result)
    if remaining > 500 and data:
        sample_size = min(5, len(data))
        sample_lines = [f"\n--- AMOSTRA ({sample_size} de {len(data)} registros) ---"]
        for row in data[:sample_size]:
            compact = _format_row_compact(row)
            if len("\n".join(sample_lines)) + len(compact) + 2 < remaining:
                sample_lines.append(compact)
        result += "\n".join(sample_lines)

    # Truncar se necessario
    if len(result) > _MAX_CONTEXT_CHARS:
        result = result[:_MAX_CONTEXT_CHARS] + "\n[...truncado]"

    return result


def _clean_response_for_context(text: str) -> str:
    """Limpa narracao anterior pra economizar tokens no contexto."""
    # Remover emojis unicode (manter texto)
    clean = re.sub(r'[\U0001f300-\U0001f9ff]', '', text)
    # Remover markdown headers ##
    clean = re.sub(r'^#{1,3}\s*', '', clean, flags=re.MULTILINE)
    # Remover linhas de tabela markdown (separadores |---|)
    clean = re.sub(r'\|[-:]+\|[-:| ]+\|', '', clean)
    # Compactar multiplas quebras de linha
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    return clean.strip()[:2000]


def _summarize_data(rows: list, intent: str) -> str:
    """Calcula resumo estatistico dos dados baseado no dominio."""
    if not rows or not isinstance(rows[0], dict):
        return ""

    summaries = []

    if "pendencia" in intent:
        _summarize_pendencia(rows, summaries)
    elif "venda" in intent:
        _summarize_vendas(rows, summaries)
    elif "comiss" in intent:
        _summarize_comissao(rows, summaries)
    elif "financ" in intent:
        _summarize_financeiro(rows, summaries)
    elif "inadimpl" in intent:
        _summarize_inadimplencia(rows, summaries)
    elif "estoque" in intent:
        _summarize_estoque(rows, summaries)
    else:
        # Generico: tentar detectar colunas de valor
        _summarize_generic(rows, summaries)

    return "\n".join(summaries) if summaries else ""


def _summarize_pendencia(rows: list, out: list):
    """Resumo para pendencias de compra."""
    valores = [float(r.get("VLR_PENDENTE", 0) or 0) for r in rows]
    if valores:
        out.append(f"Valor total pendente: R$ {sum(valores):,.2f}")
        out.append(f"Valor medio por item: R$ {sum(valores)/len(valores):,.2f}")
        if max(valores) > 0:
            out.append(f"Maior valor: R$ {max(valores):,.2f}")

    # Status breakdown
    status_count = {}
    for r in rows:
        s = str(r.get("STATUS_ENTREGA", "DESCONHECIDO") or "DESCONHECIDO")
        status_count[s] = status_count.get(s, 0) + 1
    if status_count:
        parts = [f"{s}: {n}" for s, n in sorted(status_count.items(), key=lambda x: -x[1])]
        out.append(f"Por status: {', '.join(parts)}")

    # Pedidos distintos
    pedidos = set(str(r.get("PEDIDO", "")) for r in rows if r.get("PEDIDO"))
    if pedidos:
        out.append(f"Pedidos distintos: {len(pedidos)}")

    # Fornecedores / marcas
    _add_breakdown(rows, "MARCA", "Por marca", out, top=5)
    _add_breakdown(rows, "FORNECEDOR", "Por fornecedor", out, top=5)


def _summarize_vendas(rows: list, out: list):
    """Resumo para vendas."""
    valores = [float(r.get("VALOR", 0) or 0) for r in rows]
    if valores:
        out.append(f"Valor total: R$ {sum(valores):,.2f}")
        out.append(f"Ticket medio: R$ {sum(valores)/len(valores):,.2f}")
    margens = [float(r.get("MARGEM", 0) or 0) for r in rows if r.get("MARGEM")]
    if margens:
        out.append(f"Margem media: {sum(margens)/len(margens):.1f}%")
    _add_breakdown(rows, "VENDEDOR", "Por vendedor", out, top=5)


def _summarize_comissao(rows: list, out: list):
    """Resumo para comissoes."""
    for col in ("COM_LIQUIDA", "VLR_COMISSAO", "COMISSAO"):
        valores = [float(r.get(col, 0) or 0) for r in rows if r.get(col) is not None]
        if valores:
            out.append(f"Comissao total: R$ {sum(valores):,.2f}")
            break
    for col in ("VLR_FATURADO", "VLR_LIQUIDO"):
        valores = [float(r.get(col, 0) or 0) for r in rows if r.get(col) is not None]
        if valores:
            out.append(f"Faturamento: R$ {sum(valores):,.2f}")
            break
    _add_breakdown(rows, "VENDEDOR", "Por vendedor", out, top=5)


def _summarize_financeiro(rows: list, out: list):
    """Resumo para financeiro."""
    valores = [float(r.get("VLRDESDOB", 0) or 0) for r in rows]
    if valores:
        out.append(f"Valor total: R$ {sum(valores):,.2f}")
    # Vencidos vs a vencer
    vencidos = [r for r in rows if str(r.get("STATUS", "")).upper() in ("VENCIDO", "EM ATRASO")]
    if vencidos:
        vlr_vencido = sum(float(r.get("VLRDESDOB", 0) or 0) for r in vencidos)
        out.append(f"Vencido: R$ {vlr_vencido:,.2f} ({len(vencidos)} titulos)")
    _add_breakdown(rows, "PARCEIRO", "Por parceiro", out, top=5)


def _summarize_inadimplencia(rows: list, out: list):
    """Resumo para inadimplencia."""
    valores = [float(r.get("VLR_INADIMPLENTE", 0) or 0) for r in rows]
    if valores:
        out.append(f"Inadimplencia total: R$ {sum(valores):,.2f}")
        out.append(f"Clientes inadimplentes: {len(valores)}")
    atrasos = [float(r.get("MAIOR_ATRASO", 0) or 0) for r in rows if r.get("MAIOR_ATRASO")]
    if atrasos:
        out.append(f"Maior atraso: {int(max(atrasos))} dias")
        out.append(f"Atraso medio: {int(sum(atrasos)/len(atrasos))} dias")


def _summarize_estoque(rows: list, out: list):
    """Resumo para estoque."""
    estoques = [float(r.get("ESTOQUE", 0) or 0) for r in rows]
    if estoques:
        out.append(f"Itens consultados: {len(estoques)}")
        out.append(f"Estoque total: {sum(estoques):,.0f} unidades")
    # Abaixo do minimo
    abaixo = [r for r in rows if float(r.get("ESTOQUE", 0) or 0) < float(r.get("ESTMIN", 0) or 0)]
    if abaixo:
        out.append(f"Abaixo do minimo: {len(abaixo)} itens")
    _add_breakdown(rows, "MARCA", "Por marca", out, top=5)


def _summarize_generic(rows: list, out: list):
    """Resumo generico — tenta detectar colunas de valor."""
    for col in ("VLR_TOTAL", "VALOR", "VLRNOTA", "VLRDESDOB", "VLR_PENDENTE"):
        valores = [float(r.get(col, 0) or 0) for r in rows if r.get(col) is not None]
        if valores:
            out.append(f"Total ({col}): R$ {sum(valores):,.2f}")
            out.append(f"Registros: {len(valores)}")
            break


def _add_breakdown(rows: list, field: str, label: str, out: list, top: int = 5):
    """Adiciona breakdown por campo (ex: por marca, por vendedor)."""
    counts = {}
    for r in rows:
        val = str(r.get(field, "") or "").strip()
        if val:
            counts[val] = counts.get(val, 0) + 1
    if counts and len(counts) > 1:
        sorted_items = sorted(counts.items(), key=lambda x: -x[1])[:top]
        parts = [f"{k}: {v}" for k, v in sorted_items]
        out.append(f"{label}: {', '.join(parts)}")


def _format_row_compact(row: dict) -> str:
    """Formata um registro de forma compacta pro LLM."""
    _SKIP = {"CODPARC", "CODEMP", "SEQUENCIA", "UNIDADE", "NUM_FABRICANTE"}
    relevant = {}
    for k, v in row.items():
        if k in _SKIP or v is None or str(v).strip() == "":
            continue
        if isinstance(v, float):
            if any(x in k.upper() for x in ("VLR", "VALOR", "COMISS", "FATUR")):
                relevant[k] = f"R${v:,.2f}"
            else:
                relevant[k] = f"{v:.1f}"
        else:
            relevant[k] = str(v)[:40]
    return str(relevant)


# ============================================================
# BRAIN ANALYZE (70b com contexto)
# ============================================================

async def brain_analyze(question: str, context_data: dict) -> Optional[dict]:
    """Envia query analitica + contexto pro 70b para analise profunda.

    Args:
        question: pergunta do usuario
        context_data: dados coletados por collect_session_context()

    Returns:
        dict compativel com handler result, ou None se falhar.
    """
    from src.core.groq_client import pool_classify, pool_narrate, groq_request
    from src.core.config import GROQ_MODEL_CLASSIFY

    ctx_text = _format_context_for_llm(context_data)
    print(f"[BRAIN] Contexto formatado: {len(ctx_text)} chars")

    user_msg = f"""Pergunta do usuario: "{question}"

{ctx_text}

Com base nesses dados, responda a pergunta do usuario.
Use os numeros do resumo — NAO recalcule. Sugira acoes praticas."""

    # ---- Tentar 70b (pool_classify) ----
    if pool_classify.available:
        print(f"[BRAIN] Enviando pro 70b (pool_classify)...")
        t_start = time.time()

        result = await groq_request(
            pool=pool_classify,
            messages=[
                {"role": "system", "content": ANALYTICAL_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            model=GROQ_MODEL_CLASSIFY,
            temperature=0.7,
            max_tokens=800,
            timeout=15,
        )

        text = _clean_brain_response(result)
        if text:
            elapsed_llm = time.time() - t_start
            print(f"[BRAIN] 70b OK ({len(text)} chars, {elapsed_llm:.1f}s)")
            return _build_result(text, model="70b")

        print(f"[BRAIN] 70b falhou, tentando 8b...")

    # ---- Fallback: 8b (pool_narrate) com prompt analitico ----
    if pool_narrate.available:
        result = await groq_request(
            pool=pool_narrate,
            messages=[
                {"role": "system", "content": ANALYTICAL_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=600,
        )

        text = _clean_brain_response(result)
        if text:
            print(f"[BRAIN] 8b-fallback OK ({len(text)} chars)")
            return _build_result(text, model="8b-fallback")

    print(f"[BRAIN] Ambos falharam, fallback pro routing normal")
    return None


# ============================================================
# HELPERS
# ============================================================

def _clean_brain_response(result: dict | None) -> str | None:
    """Limpa resposta do Groq. Retorna None se invalida."""
    if not result or not result.get("content"):
        return None

    text = result["content"].strip()
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    if not text or len(text) < 30:
        return None

    return text


def _build_result(text: str, model: str = "70b") -> dict:
    """Monta dict de resultado compativel com formato dos handlers."""
    return {
        "response": f"\U0001f9e0 **Análise**\n\n{text}",
        "tipo": "brain_analysis",
        "query_executed": None,
        "query_results": None,
        "time_ms": None,  # Setado pelo caller
        "_brain_model": model,
    }
