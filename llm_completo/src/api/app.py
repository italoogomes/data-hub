"""
MMarra Data Hub - API Web
Interface web para o assistente LLM.

Uso:
    python -m src.api.app
    ou
    uvicorn src.api.app:app --reload --port 8000
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

# Import chat engine
from src.llm.chat import KnowledgeBase, GroqClient, SYSTEM_PROMPT, GROQ_MODEL

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="MMarra Data Hub",
    description="Assistente inteligente da MMarra Distribuidora Automotiva",
    version="1.0.0",
)

# Estado global
kb = KnowledgeBase()
llm = None
chat_history = []

# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():
    global llm
    kb.load()
    llm = GroqClient()
    print(f"✅ MMarra Data Hub API pronta!")
    print(f"📚 {len(kb.documents)} documentos carregados")
    print(f"🤖 Modelo: {GROQ_MODEL}")
    print(f"🌐 Acesse: http://localhost:8000")

# ============================================================
# MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    mode: str = "full"  # "full" ou "rag"

class ChatResponse(BaseModel):
    response: str
    sources: list = []
    mode: str = "full"
    tokens_used: int = 0
    time_ms: int = 0

# ============================================================
# ROUTES
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve a interface web."""
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Endpoint principal de chat."""
    global chat_history

    start = time.time()
    question = req.message.strip()

    if not question:
        return ChatResponse(response="Envie uma pergunta.", sources=[], mode=req.mode)

    # Buscar contexto
    sources = []
    if req.mode == "full":
        context = kb.get_all_content()
    else:
        results = kb.search(question, top_k=8)
        context_parts = []
        for r in results:
            context_parts.append(f"## {r['filename']} ({r['category']})\n{r['content']}")
            sources.append({
                "path": r["path"],
                "category": r["category"],
                "score": round(r["score"], 3),
            })
        context = "\n\n---\n\n".join(context_parts) if context_parts else "Nenhum documento relevante."

    # Montar mensagens
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"## Documentação disponível\n\n{context}"},
    ]

    # Histórico (últimas 6 trocas)
    for msg in chat_history[-12:]:
        messages.append(msg)

    messages.append({"role": "user", "content": question})

    # Chamar LLM
    try:
        response = llm.chat(messages)
    except Exception as e:
        return ChatResponse(
            response=f"Erro ao consultar LLM: {str(e)}",
            sources=sources,
            mode=req.mode,
        )

    # Salvar histórico
    chat_history.append({"role": "user", "content": question})
    chat_history.append({"role": "assistant", "content": response})

    elapsed = int((time.time() - start) * 1000)

    return ChatResponse(
        response=response,
        sources=sources,
        mode=req.mode,
        time_ms=elapsed,
    )


@app.post("/api/clear")
async def clear_history():
    """Limpa o histórico do chat."""
    global chat_history
    chat_history.clear()
    return {"status": "ok", "message": "Histórico limpo"}


@app.get("/api/status")
async def status():
    """Status da base de conhecimento."""
    summary = kb.get_summary()
    total_chars = sum(len(d["content"]) for d in kb.documents)
    return {
        "documents": len(kb.documents),
        "categories": summary,
        "tokens_approx": total_chars // 4,
        "model": GROQ_MODEL,
        "history_length": len(chat_history) // 2,
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
