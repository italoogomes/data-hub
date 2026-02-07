"""
MMarra Data Hub - API Web
Interface web para o agente LLM com capacidade de consulta ao banco.

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
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

# Import agent
from src.llm.agent import DataHubAgent
from src.llm.llm_client import LLMClient, LLM_MODEL, LLM_PROVIDER

# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="MMarra Data Hub",
    description="Assistente inteligente da MMarra Distribuidora Automotiva",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado global
agent = DataHubAgent()

# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():
    # Verificar se LLM esta disponivel
    llm_client = LLMClient()
    health = llm_client.check_health()

    if health["status"] != "ok":
        print(f"[ERRO] LLM nao disponivel: {health.get('error', 'Erro desconhecido')}")
        print(f"[ERRO] Verifique se o Ollama esta rodando")
    else:
        print(f"[OK] LLM conectado ({LLM_PROVIDER}/{LLM_MODEL})")

    agent.initialize()
    print(f"[OK] MMarra Data Hub API pronta!")
    print(f"[i] {len(agent.kb.documents)} documentos carregados")
    print(f"[i] Modelo: {LLM_PROVIDER}/{LLM_MODEL}")
    print(f"[i] Modo: Agente com consulta ao banco")
    print(f"[i] Acesse: http://localhost:8000")

# ============================================================
# MODELS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    mode: str = "agent"  # "agent" (novo) ou "rag" (compatibilidade)

class ChatResponse(BaseModel):
    response: str
    sources: list = []
    mode: str = "agent"
    tipo: str = "documentacao"  # "documentacao" ou "consulta_banco"
    query_executed: Optional[str] = None
    query_results: Optional[int] = None
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
    """Endpoint principal de chat com agente."""
    start = time.time()
    question = req.message.strip()

    if not question:
        return ChatResponse(
            response="Envie uma pergunta.",
            sources=[],
            mode=req.mode,
            tipo="erro",
        )

    # Usar o agente
    try:
        result = await agent.ask(question)
    except Exception as e:
        return ChatResponse(
            response=f"Erro ao processar: {str(e)}",
            sources=[],
            mode=req.mode,
            tipo="erro",
        )

    elapsed = int((time.time() - start) * 1000)

    return ChatResponse(
        response=result.get("response", "Sem resposta"),
        sources=[],
        mode=req.mode,
        tipo=result.get("tipo", "documentacao"),
        query_executed=result.get("query_executed"),
        query_results=result.get("query_results"),
        time_ms=elapsed,
    )


@app.post("/api/clear")
async def clear_history():
    """Limpa o historico do chat."""
    agent.clear_history()
    return {"status": "ok", "message": "Historico limpo"}


@app.get("/api/status")
async def status():
    """Status da base de conhecimento e agente."""
    model_info = f"{LLM_PROVIDER}/{LLM_MODEL}"

    if not agent.initialized:
        return {
            "documents": 0,
            "categories": {},
            "tokens_approx": 0,
            "model": model_info,
            "provider": LLM_PROVIDER,
            "history_length": 0,
            "mode": "agent",
        }

    summary = agent.kb.get_summary()
    total_chars = sum(len(d["content"]) for d in agent.kb.documents)
    return {
        "documents": len(agent.kb.documents),
        "categories": summary,
        "tokens_approx": total_chars // 4,
        "model": model_info,
        "provider": LLM_PROVIDER,
        "history_length": len(agent.history) // 2,
        "mode": "agent",
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
