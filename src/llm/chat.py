"""
MMarra Data Hub - Chat LLM
Assistente inteligente que responde perguntas sobre o negócio usando a base de conhecimento.

Uso:
    python -m src.llm.chat
    python -m src.llm.chat "qual o fluxo de compras?"
"""

import os
import sys
import glob
import re
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.theme import Theme

# Adicionar raiz do projeto ao path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

# ============================================================
# CONFIGURACAO
# ============================================================

# Importar cliente LLM unificado
from src.llm.llm_client import LLMClient, LLM_MODEL, LLM_PROVIDER

KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
QUERIES_DIR = PROJECT_ROOT / "queries"

# Rich console
theme = Theme({
    "user": "bold cyan",
    "assistant": "bold green",
    "system": "bold yellow",
    "error": "bold red",
})
console = Console(theme=theme)

# ============================================================
# BASE DE CONHECIMENTO
# ============================================================

class KnowledgeBase:
    """Carrega e busca na base de conhecimento do projeto."""

    def __init__(self):
        self.documents = []  # Lista de {"path": str, "content": str, "category": str}
        self.tfidf_matrix = None
        self.vectorizer = None

    def load(self):
        """Carrega todos os .md e .sql da base de conhecimento."""
        patterns = [
            (KNOWLEDGE_DIR / "**" / "*.md", self._categorize_knowledge),
            (QUERIES_DIR / "**" / "*.sql", lambda p: "query"),
        ]

        for pattern, categorizer in patterns:
            for filepath in glob.glob(str(pattern), recursive=True):
                path = Path(filepath)
                content = path.read_text(encoding="utf-8", errors="ignore").strip()
                if content and content != "":
                    rel_path = path.relative_to(PROJECT_ROOT)
                    self.documents.append({
                        "path": str(rel_path),
                        "content": content,
                        "category": categorizer(rel_path) if callable(categorizer) else categorizer,
                        "filename": path.stem,
                    })

        console.print(f"[system][OK] Base carregada: {len(self.documents)} documentos[/]")
        self._build_index()

    def _categorize_knowledge(self, path):
        """Categoriza documento pelo caminho."""
        parts = path.parts
        if "tabelas" in parts:
            return "tabela"
        elif "processos" in parts:
            return "processo"
        elif "glossario" in parts:
            return "glossario"
        elif "regras" in parts:
            return "regra"
        elif "erros" in parts:
            return "erro"
        elif "sankhya" in parts:
            return "api"
        return "outro"

    def _build_index(self):
        """Constrói índice TF-IDF para busca."""
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            corpus = []
            for doc in self.documents:
                # Combinar nome do arquivo + conteúdo para melhor busca
                text = f"{doc['filename']} {doc['category']} {doc['content']}"
                corpus.append(text)

            self.vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words=None,  # Manter termos técnicos
                min_df=1,
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
            console.print("[system][OK] Indice de busca criado (TF-IDF)[/]")

        except ImportError:
            console.print("[system][!] scikit-learn nao instalado. Usando busca por keywords.[/]")
            self.vectorizer = None

    def search(self, query, top_k=5):
        """Busca documentos relevantes para a query."""
        if self.vectorizer and self.tfidf_matrix is not None:
            return self._search_tfidf(query, top_k)
        return self._search_keywords(query, top_k)

    def _search_tfidf(self, query, top_k):
        """Busca usando TF-IDF + cosine similarity."""
        from sklearn.metrics.pairwise import cosine_similarity

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        # Top K resultados com score > 0
        top_indices = similarities.argsort()[::-1][:top_k]
        results = []
        for idx in top_indices:
            if similarities[idx] > 0.01:
                results.append({
                    **self.documents[idx],
                    "score": float(similarities[idx]),
                })
        return results

    def _search_keywords(self, query, top_k):
        """Busca simples por keywords (fallback)."""
        keywords = query.lower().split()
        scored = []
        for doc in self.documents:
            text = (doc["content"] + " " + doc["filename"]).lower()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scored.append({**doc, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def get_all_content(self):
        """Retorna todo o conteúdo formatado (para contexto completo)."""
        sections = {
            "tabela": "## Tabelas do Sankhya\n\n",
            "processo": "## Processos de Negócio\n\n",
            "regra": "## Regras de Negócio\n\n",
            "glossario": "## Glossário\n\n",
            "erro": "## Erros Conhecidos\n\n",
            "api": "## API Sankhya\n\n",
            "query": "## Queries SQL\n\n",
            "outro": "## Outros\n\n",
        }

        for doc in self.documents:
            cat = doc["category"]
            if cat in sections:
                sections[cat] += f"### {doc['filename']}\n{doc['content']}\n\n---\n\n"

        return "\n".join(sections.values())

    def get_summary(self):
        """Retorna resumo da base para status."""
        categories = {}
        for doc in self.documents:
            cat = doc["category"]
            categories[cat] = categories.get(cat, 0) + 1
        return categories


# ============================================================
# LLM CLIENT (usa LLMClient de llm_client.py)
# ============================================================
# Classe LLMClient importada de src.llm.llm_client


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """Você é o assistente de dados da MMarra Distribuidora Automotiva, uma distribuidora de autopeças para veículos pesados (caminhões, ônibus) com sede em Ribeirão Preto/SP e 9 filiais pelo Brasil.

## Seu papel
- Responder perguntas sobre o negócio, processos, dados e sistema Sankhya ERP
- Explicar fluxos de compra, venda, estoque, financeiro, WMS
- Ajudar a entender tabelas, campos e relacionamentos do banco de dados
- Sugerir queries SQL quando necessário (banco Oracle)
- Explicar regras de negócio específicas da MMarra

## Contexto técnico
- ERP: Sankhya (banco Oracle)
- Tabelas principais: TGFCAB (notas), TGFITE (itens), TGFPAR (parceiros), TGFPRO (produtos), TGFTOP (operações), TSIEMP (empresas), TGFVEN (vendedores), TGFEST (estoque), TGFFIN (financeiro)
- Tabelas customizadas: Prefixo AD_* (MMarra personalizou bastante)
- API: OAuth2 via api.sankhya.com.br

## Números chave
- 10 empresas (Ribeirão Preto é a maior: R$ 343M)
- 394k produtos (Cummins 44k, MWM 15k, ZF 14k SKUs)
- 57k parceiros
- 343k notas
- 1.1M itens
- 20 compradores, 86 vendedores

## Regras importantes da MMarra
- NÃO usa workflow de aprovação padrão (TGFLIB vazia)
- Solicitação de compra usa TGFCAB com TIPMOV='J' (não TGFSOL)
- Cotação usa TGFCOT, apenas preço importa (PESOPRECO=1)
- Custos em tabela customizada AD_TGFCUSMMA (709k registros, 5 anos)
- Códigos auxiliares em AD_TGFPROAUXMMA (1.1M registros, 18 por produto)

## Instruções
- Responda em português brasileiro
- Use os documentos fornecidos como fonte principal
- Se não souber, diga que precisa investigar no banco
- Quando sugerir queries, use sintaxe Oracle (ROWNUM, SYSDATE, etc)
- Seja direto e prático
- Se a pergunta envolver dados em tempo real, explique que precisa acessar o banco via MCP
"""


# ============================================================
# CHAT ENGINE
# ============================================================

class ChatEngine:
    """Motor de chat com RAG."""

    def __init__(self):
        self.kb = KnowledgeBase()
        self.llm = None
        self.history = []
        self.mode = "rag"  # "rag" ou "full"

    def initialize(self):
        """Inicializa base de conhecimento e LLM."""
        console.print(Panel(
            "[bold]MMarra Data Hub - Assistente LLM[/]\n"
            "Seu assistente inteligente sobre o negocio MMarra",
            border_style="cyan",
        ))

        # Carregar base
        self.kb.load()
        summary = self.kb.get_summary()
        for cat, count in sorted(summary.items()):
            console.print(f"  - {cat}: {count} documentos")

        # Verificar LLM (Ollama)
        try:
            self.llm = LLMClient()
            health = self.llm.check_health()

            if health["status"] != "ok":
                console.print(f"[error][X] LLM nao disponivel: {health.get('error', 'Erro desconhecido')}[/]")
                console.print("[error]   Verifique se o Ollama esta rodando[/]")
                sys.exit(1)

            if not health["model_available"]:
                console.print(f"[error][X] Modelo {self.llm.model} nao encontrado[/]")
                console.print(f"[error]   Modelos disponiveis: {health['models']}[/]")
                sys.exit(1)

            console.print(f"[system][OK] LLM conectado ({LLM_PROVIDER}/{LLM_MODEL})[/]")

        except Exception as e:
            console.print(f"[error][X] Erro ao conectar LLM: {e}[/]")
            sys.exit(1)

        # Calcular tamanho da base
        total_chars = sum(len(d["content"]) for d in self.kb.documents)
        total_tokens_aprox = total_chars // 4
        console.print(f"[system][i] Base total: ~{total_tokens_aprox:,} tokens[/]")

        # Ollama local - sem limite de tokens! Pode usar modo full
        if total_tokens_aprox < 60000:
            self.mode = "full"
            console.print("[system][i] Modo: contexto completo (base cabe no context window)[/]")
        else:
            self.mode = "rag"
            console.print("[system][i] Modo: RAG (busca documentos relevantes por pergunta)[/]")

        console.print()
        console.print("[system]Comandos: 'sair' para sair | 'status' para ver base | 'modo' para alternar RAG/full[/]")
        console.print()

    def ask(self, question):
        """Processa uma pergunta e retorna resposta."""
        # Buscar contexto
        if self.mode == "full":
            context = self.kb.get_all_content()
            sources_info = "Contexto: base completa"
        else:
            results = self.kb.search(question, top_k=8)
            if results:
                context_parts = []
                sources = []
                for r in results:
                    context_parts.append(f"## {r['filename']} ({r['category']})\n{r['content']}")
                    sources.append(f"  > {r['path']} (score: {r['score']:.2f})")
                context = "\n\n---\n\n".join(context_parts)
                sources_info = "\n".join(sources)
            else:
                context = "Nenhum documento relevante encontrado na base."
                sources_info = "Sem fontes"

        # Montar mensagens
        messages = [
            {"role": "system", "content": "/no_think\n" + SYSTEM_PROMPT},
            {
                "role": "system",
                "content": f"## Documentação disponível\n\n{context}",
            },
        ]

        # Adicionar histórico (últimas 6 trocas)
        for msg in self.history[-12:]:
            messages.append(msg)

        messages.append({"role": "user", "content": question})

        # Chamar LLM
        try:
            response = self.llm.chat(messages)
        except Exception as e:
            return f"[X] Erro na LLM: {e}", sources_info

        # Salvar no histórico
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": response})

        return response, sources_info

    def run_interactive(self):
        """Roda chat interativo no terminal."""
        self.initialize()

        while True:
            try:
                question = Prompt.ask("[user]Você[/]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[system]Ate mais![/]")
                break

            question = question.strip()
            if not question:
                continue

            if question.lower() in ("sair", "exit", "quit", "q"):
                console.print("[system]Ate mais![/]")
                break

            if question.lower() == "status":
                summary = self.kb.get_summary()
                console.print(Panel(
                    f"Documentos: {len(self.kb.documents)}\n"
                    f"Modo: {self.mode}\n"
                    f"Historico: {len(self.history) // 2} trocas\n"
                    + " | ".join(f"{k}: {v}" for k, v in summary.items()),
                    title="Status",
                    border_style="yellow",
                ))
                continue

            if question.lower() == "modo":
                self.mode = "full" if self.mode == "rag" else "rag"
                console.print(f"[system]Modo alterado para: {self.mode}[/]")
                continue

            if question.lower() == "limpar":
                self.history.clear()
                console.print("[system]Historico limpo![/]")
                continue

            # Processar pergunta
            with console.status("[bold green]Pensando...[/]"):
                response, sources = self.ask(question)

            # Mostrar fontes (modo RAG)
            if self.mode == "rag" and ">" in sources:
                console.print(f"[dim]{sources}[/]")

            # Mostrar resposta
            console.print()
            try:
                console.print(Markdown(response))
            except Exception:
                console.print(response)
            console.print()

    def ask_single(self, question):
        """Responde uma única pergunta e sai."""
        self.initialize()
        console.print(f"\n[user]Pergunta:[/] {question}\n")

        with console.status("[bold green]Pensando...[/]"):
            response, sources = self.ask(question)

        if self.mode == "rag" and ">" in sources:
            console.print(f"[dim]{sources}[/]")

        console.print()
        try:
            console.print(Markdown(response))
        except Exception:
            console.print(response)


# ============================================================
# MAIN
# ============================================================

def main():
    engine = ChatEngine()

    # Se passou pergunta como argumento
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        engine.ask_single(question)
    else:
        engine.run_interactive()


if __name__ == "__main__":
    main()
