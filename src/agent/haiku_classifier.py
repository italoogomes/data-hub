"""
MMarra Data Hub - Classificador Inteligente (Claude Haiku).

Substitui o scoring por keywords por um LLM que entende contexto.
Classifica intent + extrai parâmetros numa chamada só.

Fallback: Groq 8b FC → Scoring keywords
"""

import os
import json
import time
import re
import httpx
from typing import Optional

from src.agent.tools import ToolCall


# Config
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HAIKU_MODEL = os.getenv("HAIKU_MODEL", "claude-haiku-4-5-20251001")
HAIKU_TIMEOUT = int(os.getenv("HAIKU_TIMEOUT", "8"))  # segundos
HAIKU_MAX_TOKENS = 300  # Resposta é JSON curto
HAIKU_API_URL = "https://api.anthropic.com/v1/messages"
USE_HAIKU_CLASSIFIER = os.getenv("USE_HAIKU_CLASSIFIER", "false").lower() in ("true", "1", "yes")


# ============================================================
# SYSTEM PROMPT — O "Manual do Funcionário" da MMarra
# ============================================================

CLASSIFIER_SYSTEM = """Você é o classificador inteligente do Data Hub da MMarra Distribuidora Automotiva, uma distribuidora de autopeças pesadas (caminhões, ônibus, máquinas) com ~200 funcionários e 4 filiais: Ribeirão Preto (RIBEIR), Uberlândia (UBERL), Araçatuba (ARACAT) e Itumbiara (ITUMBI).

Sua ÚNICA função é classificar a pergunta do usuário e retornar um JSON com a ferramenta correta e parâmetros extraídos.

## FERRAMENTAS DISPONÍVEIS

### 1. consultar_pendencias
Pedidos de compra pendentes, entregas, previsões, o que falta chegar.
- **Quando usar:** pendências, pedidos de compra, entregas, previsão de chegada, o que falta, fornecedor vai entregar, pedidos atrasados, compras abertas, casada/empenho, quem compra/fornece uma marca
- **Exemplos:** "pendências da MANN", "o que falta chegar?", "pedidos atrasados", "qual a próxima entrega do item P618689?", "compras casadas", "quem fornece WEGA?", "pedidos do comprador João"
- **Parâmetros:** marca (MAIÚSCULO), fornecedor, empresa (prefixo), comprador, tipo_compra (casada/estoque), apenas_atrasados (bool), valor_minimo, valor_maximo, dias_minimo, top, ordenar, view (pedidos/itens)

### 2. consultar_vendas
Vendas, faturamento, notas fiscais de venda, receita.
- **Quando usar:** vendas, faturamento, quanto vendeu, notas emitidas, ticket médio, ranking de vendedores por faturamento
- **Exemplos:** "vendas do mês", "faturamento de ontem", "quanto a filial de Uberlândia vendeu?", "ranking de vendedores", "vendas da marca MANN"
- **Parâmetros:** periodo (hoje/ontem/semana/semana_passada/mes/mes_passado/ano), marca (MAIÚSCULO), empresa (prefixo)

### 3. consultar_estoque
Saldo em estoque, disponibilidade, estoque crítico/zerado.
- **Quando usar:** estoque de um produto, saldo disponível, estoque crítico, estoque baixo/zerado, quanto tem em estoque
- **Exemplos:** "estoque do produto 133346", "estoque de filtro de óleo", "produtos com estoque crítico", "saldo da MANN em Uberlândia"
- **Parâmetros:** codprod (int), produto_nome, marca (MAIÚSCULO), empresa (prefixo)

### 4. buscar_produto
Busca no catálogo de produtos (Elasticsearch). Para ENCONTRAR/PROCURAR um produto.
- **Quando usar:** buscar produto por nome/código/referência, listar produtos de uma marca, verificar se existe no catálogo, buscar por código do fabricante
- **Exemplos:** "busca filtro de óleo MANN", "tem correia para Scania R450?", "produtos da marca DONALDSON", "código HU711/51"
- **Parâmetros:** texto_busca, marca (MAIÚSCULO), aplicacao (veículo/motor)
- **IMPORTANTE:** Não confundir com consultar_estoque. "buscar produto" = catálogo. "estoque do produto" = saldo.

### 5. buscar_parceiro
Busca cliente ou fornecedor por nome, CNPJ, cidade.
- **Quando usar:** dados de contato de cliente/fornecedor, telefone, endereço, CNPJ
- **Exemplos:** "dados do cliente Auto Peças Silva", "telefone do fornecedor MANN", "CNPJ do cliente 12345"
- **Parâmetros:** texto_busca, tipo (cliente/fornecedor)

### 6. consultar_financeiro
Contas a pagar, contas a receber, boletos, duplicatas, títulos, fluxo de caixa.
- **Quando usar:** boletos, duplicatas, títulos vencidos, contas a pagar/receber, fluxo de caixa, pagamentos, cobranças
- **Exemplos:** "boletos vencidos", "contas a pagar do mês", "títulos a receber", "fluxo de caixa", "boletos do cliente X"
- **Parâmetros:** tipo (pagar/receber/fluxo), status (vencido/a_vencer/pago), periodo, empresa (prefixo), parceiro, valor_minimo

### 7. consultar_inadimplencia
Clientes inadimplentes, devedores, quem deve.
- **Quando usar:** inadimplência, clientes que devem, devedores, cobrança, calote
- **Exemplos:** "clientes inadimplentes", "quem tá devendo?", "maiores devedores", "inadimplência de Uberlândia"
- **Parâmetros:** empresa (prefixo), parceiro, dias_atraso_minimo

### 8. consultar_comissao
Comissão de vendedores, margem, alíquota, ranking.
- **Quando usar:** comissão, quanto o vendedor ganha, margem de venda, alíquota, ranking por comissão, PMV
- **Exemplos:** "comissão do Rafael", "ranking de comissão do mês", "margem do vendedor João", "comissão de janeiro"
- **Parâmetros:** vendedor, empresa (prefixo), periodo (mes/mes_passado/ano), view (ranking/detalhe), marca (MAIÚSCULO), top

### 9. rastrear_pedido
Rastreamento de pedido de venda (conferência, separação, WMS, expedição).
- **Quando usar:** rastrear pedido, status do pedido, conferência, separação, WMS, expedição, cadê meu pedido
- **Exemplos:** "rastreia pedido 45678", "status do pedido 12345", "cadê o pedido do cliente X?"
- **Parâmetros:** nunota (número do pedido)

### 10. consultar_conhecimento
Processos, regras, políticas da empresa. NÃO é para dados.
- **Quando usar:** "como funciona...", "o que é...", "qual a diferença entre...", "qual a política de..."
- **Exemplos:** "como funciona compra casada?", "o que é empenho?", "qual o processo de devolução?"
- **Parâmetros:** pergunta

### 11. saudacao
Cumprimentos.
- **Quando usar:** APENAS para "oi", "bom dia", "olá", "hey"
- **Parâmetros:** nenhum

### 12. ajuda
Menu de ajuda.
- **Quando usar:** "ajuda", "help", "o que você faz?", "comandos"
- **Parâmetros:** nenhum

## REGRAS DE CLASSIFICAÇÃO

1. **Marcas são SEMPRE MAIÚSCULAS:** MANN, SABO, DONALDSON, WEGA, FLEETGUARD, EATON, ZF, NAKATA, MAHLE, FRAS-LE, RIOSULENSE, KNORR, CONTINENTAL, HENGST
2. **Empresas → prefixo:** Ribeirão Preto=RIBEIR, Uberlândia=UBERL, Araçatuba=ARACAT, Itumbiara=ITUMBI
3. **"mil" = x1000:** "50 mil" = 50000, "100 mil" = 100000
4. **"próxima entrega" ou "quando chega" = pendencia_compras** (NÃO estoque)
5. **"buscar/procurar produto" = buscar_produto** | **"estoque do produto" = consultar_estoque**
6. **Códigos alfanuméricos (P618689, HU711/51, W950) = buscar_produto** (busca no catálogo por código)
7. **Vendedores conhecidos da MMarra:** LICIANE, LUIZ FERNANDO LUCIND, MIRÃO SILVA, ALVARO SANTOS, CLEVERTON, VALÉRIO, MARCOS TORRES, RAFAEL CANDIDO, MATHEUS SILVA, RENALDO MIRANDA
8. **Compradores conhecidos:** (serão carregados dinamicamente)
9. **Se a pergunta é analítica** ("por que caiu?", "como melhorar?", "o que fazer?") → retorne `"intent": "brain_analyze"` com parâmetros vazios. O brain lida com isso.

## FORMATO DE RESPOSTA

Retorne APENAS um JSON válido, sem markdown, sem explicação:

{"tool": "nome_da_ferramenta", "params": {"param1": "valor1"}, "confidence": 0.95}

Se não conseguir classificar com confiança:
{"tool": "ajuda", "params": {}, "confidence": 0.1}

NUNCA retorne texto fora do JSON. NUNCA explique. APENAS o JSON."""


# ============================================================
# HAIKU CLASSIFY
# ============================================================

async def haiku_classify(question: str, known_marcas: set = None,
                         known_empresas: set = None,
                         known_compradores: set = None,
                         ctx=None, history: list = None) -> Optional[ToolCall]:
    """
    Classifica a pergunta usando Claude Haiku.

    Returns:
        ToolCall com intent + params, ou None se falhar.
    """
    if not ANTHROPIC_API_KEY or not USE_HAIKU_CLASSIFIER:
        return None

    t0 = time.time()

    # Montar mensagem do usuário com contexto
    user_msg = _build_user_message(question, ctx, history)

    try:
        async with httpx.AsyncClient(timeout=HAIKU_TIMEOUT) as client:
            response = await client.post(
                HAIKU_API_URL,
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": HAIKU_MODEL,
                    "max_tokens": HAIKU_MAX_TOKENS,
                    "system": CLASSIFIER_SYSTEM,
                    "messages": [{"role": "user", "content": user_msg}],
                    "temperature": 0.0,  # Determinístico para classificação
                },
            )

        elapsed = time.time() - t0

        if response.status_code != 200:
            print(f"[HAIKU] HTTP {response.status_code}: {response.text[:200]} ({elapsed:.1f}s)")
            return None

        data = response.json()
        text = data.get("content", [{}])[0].get("text", "").strip()

        # Parse JSON
        result = _parse_haiku_response(text)
        if not result:
            print(f"[HAIKU] Resposta inválida ({elapsed:.1f}s): {text[:100]}")
            return None

        tool_name = result.get("tool", "")
        params = result.get("params", {})
        confidence = result.get("confidence", 0.5)

        # Tokens usados (para monitoramento de custo)
        usage = data.get("usage", {})
        in_tokens = usage.get("input_tokens", 0)
        out_tokens = usage.get("output_tokens", 0)

        print(f"[HAIKU] {tool_name}({params}) conf={confidence:.0%} | "
              f"{elapsed:.1f}s | {in_tokens}+{out_tokens} tokens")

        return ToolCall(
            name=tool_name,
            params=params,
            source="haiku",
            confidence=confidence,
        )

    except httpx.TimeoutException:
        elapsed = time.time() - t0
        print(f"[HAIKU] Timeout ({elapsed:.1f}s)")
        return None
    except Exception as e:
        elapsed = time.time() - t0
        print(f"[HAIKU] Erro ({elapsed:.1f}s): {e}")
        return None


def _build_user_message(question: str, ctx=None, history: list = None) -> str:
    """Monta a mensagem do usuário com contexto da sessão."""
    parts = [f'Classifique: "{question}"']

    # Contexto da sessão (último intent e parâmetros)
    if ctx and ctx.intent:
        parts.append(f"\nContexto da sessão: último intent={ctx.intent}, params={ctx.params}")
        if ctx.last_question:
            parts.append(f'Pergunta anterior: "{ctx.last_question}"')

    return "\n".join(parts)


def _parse_haiku_response(text: str) -> Optional[dict]:
    """Parse da resposta JSON do Haiku."""
    # Limpar possíveis markdown wrappers
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]  # Remove primeira linha
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        result = json.loads(text)
        if "tool" in result:
            return result
    except json.JSONDecodeError:
        pass

    # Tentar encontrar JSON dentro do texto (suporta {} aninhados)
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        candidate = json.loads(text[start:i + 1])
                        if "tool" in candidate:
                            return candidate
                    except json.JSONDecodeError:
                        pass
                    break

    return None
