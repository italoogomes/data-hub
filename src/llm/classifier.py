"""
MMarra Data Hub - LLM Classifier.
Classificacao de intents via Groq API e Ollama (fallback).
Prompt de classificacao + funcoes de chamada.
"""

import re
import json
import time
from typing import Optional

import requests as req_sync

from src.core.config import (
    OLLAMA_URL, LLM_CLASSIFIER_MODEL, USE_LLM_CLASSIFIER,
    LLM_CLASSIFIER_TIMEOUT, GROQ_MODEL, GROQ_MODEL_CLASSIFY,
)
from src.llm.groq_client import pool_classify, groq_request


# ============================================================
# CLASSIFIER PROMPT
# ============================================================

LLM_CLASSIFIER_PROMPT = """Voce e o interpretador de perguntas do sistema ERP da MMarra Distribuidora Automotiva.
Analise a pergunta do usuario e retorne APENAS um JSON (sem markdown, sem explicacao, sem texto antes ou depois).

# INTENTS POSSIVEIS
- pendencia_compras: pedidos de compra pendentes, o que falta chegar, entregas, previsoes
- estoque: quantidade em estoque, saldo, estoque critico, disponibilidade
- vendas: vendas, faturamento, notas fiscais de venda, receita
- produto: busca por produto especifico, codigo fabricante (HU711/51, WK950/21), similares, cross-reference, visao 360
- busca_produto: usuario quer ENCONTRAR/PROCURAR um produto por nome, codigo, referencia, aplicacao. Palavras-chave: "tem", "busca", "procura", "encontra", "acha", "existe", "onde tem". Diferente de pendencia (pedidos) e estoque (saldo).
- busca_cliente: usuario quer encontrar um CLIENTE por nome, CNPJ, cidade. Ex: "dados do cliente auto pecas", "clientes de uberlandia"
- busca_fornecedor: usuario quer encontrar um FORNECEDOR por nome, contato. Ex: "contato do fornecedor nakata", "telefone da mann filter"
- rastreio_pedido: o usuario quer RASTREAR um pedido de venda especifico por NUNOTA. Quer saber status, conferencia, separacao, se as pecas foram compradas, se chegou. Palavras-chave: "status do pedido", "como esta o pedido", "meu pedido", "pedido X", "conferencia", "separacao", "ja comprou", "ja chegou". IMPORTANTE: diferente de pendencia_compras (que e sobre pedidos de COMPRA pendentes). rastreio_pedido e sobre um pedido de VENDA especifico.
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
- tipo_compra: "casada"|"estoque" ou null (tipo de compra mencionado - casada=empenho/vinculada, estoque=reposicao/entrega futura)
- aplicacao: veiculo/motor/maquina mencionado para busca por aplicacao ou null (ex: "SCANIA R450", "MERCEDES ACTROS", "MOTOR DC13")
- texto_busca: texto livre que o usuario quer buscar (nome do produto, nome do cliente, etc.) ou null. Usado com busca_produto/busca_cliente/busca_fornecedor.
- nunota: numero unico da nota/pedido (NUNOTA) quando o usuario menciona um numero de pedido de venda. Extrair o numero da pergunta. Ex: "pedido 1199868" -> nunota=1199868. Usado com rastreio_pedido.
- extra_columns: lista de colunas extras que o usuario quer ver no relatorio, ou null
  Colunas possiveis: "EMPRESA", "TIPO_COMPRA", "COMPRADOR", "PREVISAO_ENTREGA", "CONFIRMADO",
  "FORNECEDOR", "UNIDADE", "QTD_PEDIDA", "QTD_ATENDIDA", "VLR_UNITARIO", "DIAS_ABERTO",
  "NUM_FABRICANTE", "NUM_ORIGINAL", "REFERENCIA", "APLICACAO"
  Detecte quando o usuario pede para ADICIONAR/VER campos com frases como:
  "contendo X", "com o campo X", "incluindo X", "mostrando X",
  "precisa ter X", "quero ver X tambem", "adiciona X"
  Mapeamentos importantes:
  "codigo fabricante"/"numero fabricante"/"ref fabricante"/"fabricante" = "NUM_FABRICANTE"
  "numero original"/"original" = "NUM_ORIGINAL"
  "referencia"/"ref interna" = "REFERENCIA"
  "previsao"/"previsao de entrega"/"quando chega" = "PREVISAO_ENTREGA"
  "tipo de compra"/"casada ou estoque" = "TIPO_COMPRA"
  "dias"/"dias aberto"/"dias pendente" = "DIAS_ABERTO"
  "comprador"/"quem compra" = "COMPRADOR"
  "empresa"/"filial" = "EMPRESA"
  Se o usuario NAO pediu colunas extras, retorne null.

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
- FORNECEDOR, CODPROD, PRODUTO, MARCA, QTD_PEDIDA, VLR_UNITARIO, EMPRESA, COMPRADOR
- TIPO_COMPRA: tipo do pedido de compra ("Casada" = empenho/vinculada a venda, "Estoque" = reposicao geral)
- NUM_FABRICANTE: codigo que o fabricante da a peca (AD_NUMFABRICANTE)
- NUM_ORIGINAL: numero original da peca (AD_NUMORIGINAL)
- REFERENCIA: referencia interna do cadastro (PRO.REFERENCIA)

IMPORTANTE - Diferencie corretamente:
- "data de entrega" / "previsao de entrega" / "quando vai chegar" = PREVISAO_ENTREGA (NAO e DT_PEDIDO!)
- "data do pedido" / "quando foi pedido" / "quando comprou" = DT_PEDIDO
- "mais atrasado" / "mais tempo aberto" = DIAS_ABERTO_DESC
- "mais caro" / "maior valor" = VLR_PENDENTE_DESC

Campos para estoque: CODPROD, PRODUTO, MARCA, ESTOQUE_TOTAL, ESTOQUE_MINIMO, CUSTO_MEDIO
Campos para vendas: NUNOTA, CLIENTE, PRODUTO, QTD, VLR_TOTAL, DT_VENDA

# CONTEXTO DE CONVERSA
Se houver contexto da conversa anterior (adicionado ao final do prompt), use-o para interpretar a pergunta corretamente.
Exemplos de referencias ao contexto:
- "me passa os atrasados" = filtrar STATUS_ENTREGA="ATRASADO" dos dados anteriores
- "e os de estoque?" = manter marca/empresa anterior, filtrar TIPO_COMPRA="Estoque"
- "agora por itens" = mesma consulta anterior mas view="itens"
- "os 41 atrasados" = 41 e a QUANTIDADE de itens atrasados mencionada antes, filtrar STATUS_ENTREGA="ATRASADO"
- "qual o mais caro?" = referencia aos dados anteriores, ordenar VLR_PENDENTE_DESC + top 1
IMPORTANTE: Quando o usuario menciona um NUMERO que coincide com dados da conversa anterior
(ex: "41 atrasados" quando havia exatamente 41 itens com STATUS=ATRASADO), trate como
filtro de STATUS, NAO como filtro de DIAS_ABERTO ou outro campo numerico.

# EXEMPLOS
Pergunta: "o que falta chegar da mann?"
{"intent":"pendencia_compras","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "qual pedido esta sem previsao de entrega da tome?"
{"intent":"pendencia_compras","marca":"TOME","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"PREVISAO_ENTREGA","operador":"vazio","valor":null},"ordenar":null,"top":1,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "pedidos atrasados da Donaldson"
{"intent":"pendencia_compras","marca":"DONALDSON","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":"pedidos","filtro":{"campo":"STATUS_ENTREGA","operador":"igual","valor":"ATRASADO"},"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "vendas de hoje"
{"intent":"vendas","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":"hoje","view":"pedidos","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "como funciona a compra casada?"
{"intent":"conhecimento","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "HU711/51"
{"intent":"produto","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":null}

Pergunta: "tem filtro de ar da mann pra scania?"
{"intent":"busca_produto","marca":"MANN","fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":"SCANIA","texto_busca":"filtro de ar","nunota":null,"extra_columns":null}

Pergunta: "status do pedido 1199868"
{"intent":"rastreio_pedido","marca":null,"fornecedor":null,"empresa":null,"comprador":null,"periodo":null,"view":null,"filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":1199868,"extra_columns":null}

Pergunta: "pendencias da nakata por ribeirao contendo codigo do fabricante"
{"intent":"pendencia_compras","marca":"NAKATA","fornecedor":null,"empresa":"RIBEIR","comprador":null,"periodo":null,"view":"itens","filtro":null,"ordenar":null,"top":null,"tipo_compra":null,"aplicacao":null,"texto_busca":null,"nunota":null,"extra_columns":["NUM_FABRICANTE"]}
"""


# ============================================================
# GROQ CLASSIFY
# ============================================================

async def groq_classify(question: str, context_hint: str = "", model: str = None) -> Optional[dict]:
    """Classifica intent via Groq API. Retorna dict com campos do JSON ou None."""
    _model = model or GROQ_MODEL_CLASSIFY

    user_msg = question
    if context_hint:
        user_msg += f"\n\n# CONTEXTO DA CONVERSA ANTERIOR\n{context_hint}"

    result = await groq_request(
        pool=pool_classify,
        messages=[
            {"role": "system", "content": LLM_CLASSIFIER_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
        max_tokens=400,
        model=_model,
    )

    if not result or not result.get("content"):
        return None

    raw = result["content"].strip()

    try:
        # Limpar markdown fences
        raw = re.sub(r'```json\s*', '', raw)
        raw = re.sub(r'```\s*', '', raw)
        raw = raw.strip()

        # Extrair JSON
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', raw)
        if not json_match:
            print(f"[GROQ-CLS] JSON nao encontrado: {raw[:100]}")
            return None

        parsed = json.loads(json_match.group())

        # Normalizar entidades para UPPER
        for key in ["marca", "fornecedor", "empresa", "comprador"]:
            if parsed.get(key):
                parsed[key] = parsed[key].upper().strip()

        return parsed

    except json.JSONDecodeError as e:
        print(f"[GROQ-CLS] JSON invalido: {e} | raw: {raw[:200]}")
        return None
    except Exception as e:
        print(f"[GROQ-CLS] Erro: {type(e).__name__}: {e}")
        return None


# ============================================================
# OLLAMA CLASSIFY (fallback local)
# ============================================================

async def ollama_classify(question: str, context_hint: str = "") -> Optional[dict]:
    """Classifica intent via Ollama local. Sincrono (roda em thread)."""
    import asyncio

    def _sync_classify():
        user_msg = question
        if context_hint:
            user_msg += f"\n\n# CONTEXTO DA CONVERSA ANTERIOR\n{context_hint}"

        t0 = time.time()
        try:
            r = req_sync.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": LLM_CLASSIFIER_MODEL,
                    "messages": [
                        {"role": "system", "content": LLM_CLASSIFIER_PROMPT + "\n\nIMPORTANTE: /no_think"},
                        {"role": "user", "content": user_msg},
                    ],
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 400},
                },
                timeout=LLM_CLASSIFIER_TIMEOUT,
            )
            elapsed = time.time() - t0
            raw = r.json().get("message", {}).get("content", "").strip()

            # Limpar thinking leak
            raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()

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

    return await asyncio.get_event_loop().run_in_executor(None, _sync_classify)


# ============================================================
# UNIFIED CLASSIFY
# ============================================================

async def llm_classify(question: str, context_hint: str = "") -> Optional[dict]:
    """Classificador inteligente: Groq 70b (forte) -> Groq 8b (rapido) -> Ollama (local) -> None."""
    if not USE_LLM_CLASSIFIER:
        return None

    if pool_classify.available:
        # 1) Tentar modelo forte (70b)
        if GROQ_MODEL_CLASSIFY != GROQ_MODEL:
            result = await groq_classify(question, context_hint, model=GROQ_MODEL_CLASSIFY)
            if result:
                return result
            print(f"[LLM-CLS] {GROQ_MODEL_CLASSIFY} falhou, tentando {GROQ_MODEL}...")

        # 2) Fallback: modelo rapido (8b)
        result = await groq_classify(question, context_hint, model=GROQ_MODEL)
        if result:
            return result
        print("[LLM-CLS] Groq falhou, tentando Ollama...")

    # 3) Fallback: Ollama local
    result = await ollama_classify(question, context_hint)
    return result
