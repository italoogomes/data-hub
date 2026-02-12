"""
MMarra Data Hub - Knowledge Base
Carrega documentacao de processos e regras, seleciona docs relevantes por topico,
e usa LLM para explicar de forma natural.
"""

import os
import re
import json
import time
import asyncio
import requests as req_sync
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:4b")
LLM_KNOWLEDGE_TIMEOUT = int(os.getenv("LLM_KNOWLEDGE_TIMEOUT", "90"))

# ============================================================
# KNOWLEDGE CATEGORIES - mapeia cada arquivo a topicos
# ============================================================

DOC_CATEGORIES = {
    # Compras
    "processos/compras/fluxo_compra.md": ["compras", "pedido", "recebimento", "solicitacao", "cotacao", "fluxo"],
    "processos/compras/rotina_comprador.md": ["compras", "comprador", "rotina", "dia-a-dia", "perguntas"],
    "regras/cotacao_compra.md": ["compras", "cotacao", "fornecedor", "preco"],
    "regras/solicitacao_compra.md": ["compras", "solicitacao", "requisicao"],
    "regras/aprovacao_compras.md": ["compras", "aprovacao", "liberacao", "limite"],
    # Vendas
    "processos/vendas/fluxo_venda.md": ["vendas", "faturamento", "nota", "venda", "fluxo"],
    # Estoque
    "processos/estoque/transferencia.md": ["estoque", "transferencia", "filial"],
    "processos/estoque/devolucao.md": ["estoque", "devolucao", "troca"],
    # Regras gerais
    "regras/custos_produto.md": ["custo", "preco", "margem", "markup"],
    "regras/codigos_auxiliares.md": ["codigo", "top", "tipmov", "operacao"],
    # Glossario
    "glossario/sinonimos.md": ["glossario", "termo", "significado", "tipmov", "top"],
    # Tabelas principais (resumos curtos, nao o arquivo inteiro)
    "sankhya/relacionamentos.md": ["tabela", "relacionamento", "join", "estrutura"],
    "sankhya/tabelas/TGFCAB.md": ["nota", "cabecalho", "pedido", "status", "tipmov"],
    "sankhya/tabelas/TGFITE.md": ["item", "produto", "quantidade"],
    "sankhya/tabelas/TGFCOT.md": ["cotacao"],
    "sankhya/tabelas/TGFMAR.md": ["marca", "comprador"],
    "sankhya/tabelas/TGFEST.md": ["estoque", "saldo"],
    "sankhya/tabelas/TGFFIN.md": ["financeiro", "titulo", "pagar", "receber"],
    "sankhya/tabelas/TGFVEN.md": ["vendedor", "comprador", "representante"],
    "sankhya/tabelas/TGFPRO.md": ["produto", "cadastro"],
    "sankhya/tabelas/TGFPAR.md": ["parceiro", "fornecedor", "cliente"],
    "sankhya/tabelas/TGFTOP.md": ["top", "operacao", "tipo"],
    "sankhya/tabelas/TGFVAR.md": ["variacao", "atendimento", "parcial"],
    "sankhya/tabelas/TGFLIB.md": ["aprovacao", "liberacao"],
}

# Palavras-chave que indicam pergunta sobre conhecimento (nao sobre dados)
KNOWLEDGE_KEYWORDS = {
    # Perguntas sobre processo
    "como": 5, "funciona": 5, "processo": 5, "fluxo": 5,
    "explica": 6, "explique": 6, "explicar": 6,
    "porque": 4, "por que": 4, "pra que": 4, "para que": 4,
    "quando": 3, "onde": 3,
    "diferenca": 5, "significa": 5, "significado": 5,
    "etapa": 4, "etapas": 4, "passo": 4, "passos": 4,
    "regra": 5, "regras": 5, "politica": 4,
    # Especificos do dominio
    "casada": 5, "empenho": 5, "solicitacao": 5, "cotacao": 5,
    "aprovacao": 5, "liberacao": 5, "devolucao": 4,
    "transferencia": 4, "recebimento": 4,
    "top": 3, "tipmov": 4, "statusnota": 4,
    "tabela": 3, "campo": 3,
    # Verbos de aprendizado/curiosidade
    "ensina": 5, "ensine": 5, "me diz": 4, "me fala": 4,
    "quero saber": 5, "quero entender": 5,
    "aprova": 4, "aprovam": 4, "aprovar": 4,
    "quem": 3, "qual": 2,
    "serve": 4, "servem": 4,
    "tipo": 3, "tipos": 3,
}


def normalize_kb(text: str) -> str:
    """Remove acentos."""
    r = {'á':'a','à':'a','ã':'a','â':'a','é':'e','è':'e','ê':'e','í':'i','ó':'o','õ':'o','ô':'o','ú':'u','ç':'c'}
    t = text.lower().strip()
    for o, n in r.items():
        t = t.replace(o, n)
    return t


def _clean_thinking_leak(text: str) -> str:
    """Remove 'thinking in english' que vaza do qwen3."""
    if not text:
        return text
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    leak_patterns = [
        r'\n\s*(Hmm|Okay|Let me|The user|I need|I should|First,|Wait,|Now,|So,|Alright)',
    ]
    for pattern in leak_patterns:
        match = re.search(pattern, text)
        if match:
            text = text[:match.start()].strip()
            break
    if len(text) < 15:
        return ""
    return text.strip()


def score_knowledge(question: str) -> int:
    """Retorna score indicando se a pergunta e sobre conhecimento/processo."""
    q = normalize_kb(question)
    words = re.findall(r'[a-z]+', q)
    score = 0
    for w in words:
        if w in KNOWLEDGE_KEYWORDS:
            score += KNOWLEDGE_KEYWORDS[w]
    # Bonus pra perguntas que comecam com "como", "o que e", "por que"
    if q.startswith("como "):
        score += 3
    if q.startswith("o que ") or "o que e " in q or "o que sao " in q:
        score += 4
    if q.startswith("por que ") or q.startswith("porque "):
        score += 3
    if q.startswith("qual a diferenca") or q.startswith("qual diferenca"):
        score += 4
    if "quem " in q and ("aprova" in q or "libera" in q or "responsavel" in q):
        score += 4
    if "pra que serve" in q or "para que serve" in q:
        score += 5
    if "etapas" in q or "passo a passo" in q:
        score += 3
    return score


class KnowledgeBase:
    def __init__(self, knowledge_dir: str = None):
        if knowledge_dir is None:
            knowledge_dir = str(PROJECT_ROOT / "knowledge")
        self.knowledge_dir = Path(knowledge_dir)
        self._docs = {}  # {relative_path: content}
        self._loaded = False

    def load(self):
        """Carrega todos os .md da pasta knowledge."""
        if self._loaded:
            return
        if not self.knowledge_dir.exists():
            print(f"[KB] Pasta knowledge nao encontrada: {self.knowledge_dir}")
            self._loaded = True
            return
        count = 0
        for md_file in self.knowledge_dir.rglob("*.md"):
            rel_path = str(md_file.relative_to(self.knowledge_dir))
            # Normalizar path separators
            rel_path = rel_path.replace("\\", "/")
            try:
                content = md_file.read_text(encoding="utf-8")
                self._docs[rel_path] = content
                count += 1
            except Exception as e:
                print(f"[KB] Erro ao ler {rel_path}: {e}")
        print(f"[KB] {count} documentos carregados ({sum(len(v) for v in self._docs.values())} bytes)")
        self._loaded = True

    def select_docs(self, question: str, max_chars: int = 12000) -> list:
        """Seleciona documentos relevantes pra pergunta, respeitando limite de tamanho."""
        self.load()
        q = normalize_kb(question)
        q_words = set(re.findall(r'[a-z]+', q))

        # Scorear cada doc por relevancia
        doc_scores = []
        for rel_path, content in self._docs.items():
            score = 0
            # Score por categoria
            for cat_path, tags in DOC_CATEGORIES.items():
                if rel_path.endswith(cat_path):
                    for tag in tags:
                        tag_norm = normalize_kb(tag)
                        if tag_norm in q:
                            score += 5
                        for w in q_words:
                            if w == tag_norm or tag_norm.startswith(w) or w.startswith(tag_norm):
                                score += 3
                    break

            # Score por conteudo (primeiras 500 chars)
            preview = normalize_kb(content[:500])
            for w in q_words:
                if len(w) >= 3 and w in preview:
                    score += 1

            if score > 0:
                doc_scores.append((rel_path, score, content))

        # Ordenar por score desc
        doc_scores.sort(key=lambda x: x[1], reverse=True)

        # Pegar docs ate o limite de chars
        selected = []
        total_chars = 0
        for rel_path, score, content in doc_scores:
            # Pra docs muito grandes (tabelas), pegar so primeiras 150 linhas
            if "/tabelas/" in rel_path and len(content) > 4000:
                lines = content.split("\n")[:150]
                content = "\n".join(lines) + "\n\n[... documento completo disponivel ...]"

            if total_chars + len(content) > max_chars:
                # Ainda cabe um resumo?
                if total_chars + 2000 <= max_chars:
                    lines = content.split("\n")[:60]
                    content = "\n".join(lines) + "\n\n[... resumido ...]"
                else:
                    break

            selected.append({"path": rel_path, "score": score, "content": content})
            total_chars += len(content)

        return selected

    async def answer(self, question: str) -> Optional[dict]:
        """Busca docs relevantes e usa LLM pra explicar."""
        t0 = time.time()
        docs = self.select_docs(question)

        if not docs:
            return None

        print(f"[KB] {len(docs)} docs selecionados: {[d['path'].split('/')[-1] for d in docs]}")

        # Montar contexto
        context_parts = []
        for doc in docs:
            context_parts.append(f"--- {doc['path']} ---\n{doc['content']}")
        context = "\n\n".join(context_parts)

        # System prompt que faz a LLM explicar naturalmente
        system_prompt = """Voce e um analista experiente da MMarra Distribuidora Automotiva que conhece profundamente todos os processos, regras e sistemas da empresa.
REGRA ABSOLUTA: Responda DIRETAMENTE em portugues brasileiro. NUNCA pense em voz alta. NUNCA comece com Okay, Let me, The user, First, I need. Va direto ao ponto.

REGRAS:
1. Explique de forma SIMPLES e DIRETA, como se estivesse conversando com um colega de trabalho
2. Use exemplos praticos do dia a dia da empresa quando possivel
3. NUNCA copie a documentacao literalmente - reformule com suas proprias palavras
4. Se a pergunta for sobre um processo, explique o passo-a-passo de forma clara
5. Se a pergunta for sobre uma regra, explique o POR QUE ela existe e como impacta o trabalho
6. Use formatacao markdown (negrito, listas) para organizar a resposta
7. Seja conciso - foque no que foi perguntado
8. NAO invente informacao que nao esta na documentacao"""

        user_prompt = f"""Documentacao de referencia:

{context}

---

Pergunta do usuario: {question}

Responda de forma natural e explicativa, como um colega experiente explicaria."""

        assistant_prefix = "Sobre isso: "

        def _call():
            return req_sync.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": assistant_prefix},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.5,
                        "num_predict": 400,
                        "top_p": 0.85,
                    },
                },
                timeout=LLM_KNOWLEDGE_TIMEOUT,
            )

        try:
            import asyncio
            resp = await asyncio.to_thread(_call)
            elapsed = time.time() - t0

            if resp.status_code != 200:
                print(f"[KB] Erro HTTP {resp.status_code} ({elapsed:.1f}s)")
                return self._format_docs_fallback(question, docs, t0)

            data = resp.json()
            answer_text = data.get("message", {}).get("content", "").strip()

            # Limpar thinking leak do qwen3
            answer_text = _clean_thinking_leak(answer_text)

            # Juntar prefixo + continuacao
            if answer_text:
                answer_text = assistant_prefix + answer_text

            if not answer_text or len(answer_text) < 30:
                print(f"[KB] Resposta vazia/curta ({elapsed:.1f}s)")
                return self._format_docs_fallback(question, docs, t0)

            print(f"[KB] Resposta LLM ({elapsed:.1f}s, {len(answer_text)} chars)")

            # Adicionar footer com fontes
            sources = ", ".join(d["path"].split("/")[-1].replace(".md", "") for d in docs[:5])
            answer_text += f"\n\n---\n*\U0001f4da Fontes: {sources}*"

            return {
                "response": answer_text,
                "tipo": "conhecimento",
                "query_executed": None,
                "query_results": len(docs),
                "time_ms": int(elapsed * 1000),
            }

        except req_sync.exceptions.Timeout:
            elapsed = time.time() - t0
            print(f"[KB] Timeout ({elapsed:.0f}s)")
            return self._format_docs_fallback(question, docs, t0)
        except Exception as e:
            print(f"[KB] Erro LLM: {type(e).__name__}: {e}")
            return self._format_docs_fallback(question, docs, t0)

    def _format_docs_fallback(self, question: str, docs: list, t0: float):
        """Fallback se LLM nao disponivel - mostra resumo dos docs."""
        lines = ["\U0001f4da **Encontrei estas informacoes relevantes:**\n"]
        for doc in docs[:3]:
            name = doc["path"].split("/")[-1].replace(".md", "").replace("_", " ").title()
            # Pegar primeiras linhas uteis
            content_lines = [l.strip() for l in doc["content"].split("\n") if l.strip() and not l.startswith("#")]
            preview = " ".join(content_lines[:3])[:200]
            lines.append(f"**{name}:** {preview}...\n")

        lines.append("\n*\u26a0\ufe0f LLM nao disponivel. Mostrando resumo da documentacao.*")
        elapsed = int((time.time() - t0) * 1000)
        return {
            "response": "\n".join(lines),
            "tipo": "conhecimento",
            "query_executed": None,
            "query_results": len(docs),
            "time_ms": elapsed,
        }