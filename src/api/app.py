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
import secrets
import requests as http_requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Header
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
# AUTH - Sessoes em memoria
# ============================================================

sessions = {}  # {token: {user, role, codvend, tipvend, ...}}
SESSION_TIMEOUT = timedelta(hours=8)

# Sankhya API
SANKHYA_BASE_URL = "https://api.sankhya.com.br"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_X_TOKEN", "")
ADMIN_USERS = [u.strip().upper() for u in os.getenv("ADMIN_USERS", "").split(",") if u.strip()]
_oauth_token = {"token": None, "expires_at": 0}


def get_sankhya_oauth_token() -> str:
    """Obtem token OAuth do Sankhya (com cache)."""
    if _oauth_token["token"] and time.time() < (_oauth_token["expires_at"] - 30):
        return _oauth_token["token"]

    if not all([SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET, SANKHYA_X_TOKEN]):
        raise Exception("Credenciais OAuth nao configuradas no .env (SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET, SANKHYA_X_TOKEN)")

    print(f"[AUTH] Obtendo OAuth token... (client_id={SANKHYA_CLIENT_ID[:8]}...)")
    resp = http_requests.post(
        f"{SANKHYA_BASE_URL}/authenticate",
        headers={
            "X-Token": SANKHYA_X_TOKEN,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "client_id": SANKHYA_CLIENT_ID,
            "client_secret": SANKHYA_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=30,
        verify=False
    )

    raw = resp.text
    print(f"[AUTH] OAuth response: HTTP {resp.status_code}, body={raw[:500]}")

    if resp.status_code != 200 or not raw.strip():
        raise Exception(f"OAuth HTTP {resp.status_code} - resposta: '{raw[:300]}'")

    try:
        result = resp.json()
    except Exception:
        raise Exception(f"OAuth resposta nao-JSON (HTTP {resp.status_code}): '{raw[:300]}'")

    if "access_token" not in result:
        raise Exception(f"OAuth sem access_token: {result}")

    _oauth_token["token"] = result["access_token"]
    _oauth_token["expires_at"] = time.time() + result.get("expires_in", 300)
    print(f"[AUTH] OAuth token obtido (expira em {result.get('expires_in', 300)}s)")
    return _oauth_token["token"]


def _execute_sankhya_query(sql: str) -> list:
    """Executa query SQL no Sankhya via DbExplorerSP (sincrono)."""
    oauth_token = get_sankhya_oauth_token()
    resp = http_requests.post(
        f"{SANKHYA_BASE_URL}/gateway/v1/mge/service.sbr",
        params={"serviceName": "DbExplorerSP.executeQuery", "outputType": "json"},
        headers={
            "Authorization": f"Bearer {oauth_token}",
            "Content-Type": "application/json",
        },
        json={"requestBody": {"sql": sql}},
        timeout=30,
        verify=False
    )
    data = resp.json()
    if str(data.get("status")) != "1":
        print(f"[RBAC] Query falhou: {data}")
        return []
    try:
        rows = data["responseBody"]["rows"]
        return rows if isinstance(rows, list) else []
    except (KeyError, TypeError):
        return []


def fetch_user_profile(username: str) -> dict:
    """Busca perfil do usuario na TGFVEN pelo APELIDO."""
    sql = (
        f"SELECT CODVEND, APELIDO, TIPVEND, CODGER, ATIVO, CODEMP "
        f"FROM TGFVEN "
        f"WHERE UPPER(APELIDO) = UPPER('{username}') AND ATIVO = 'S' "
        f"AND ROWNUM <= 1"
    )
    rows = _execute_sankhya_query(sql)
    if not rows:
        return None
    row = rows[0]
    return {
        "codvend": int(row.get("CODVEND", 0)),
        "apelido": row.get("APELIDO", ""),
        "tipvend": row.get("TIPVEND", ""),
        "codger": int(row.get("CODGER", 0)) if row.get("CODGER") else 0,
        "codemp": int(row.get("CODEMP", 0)) if row.get("CODEMP") else 0,
    }


def fetch_team_codvends(codvend: int) -> list:
    """Busca CODVENDs dos subordinados de um gerente."""
    sql = (
        f"SELECT CODVEND FROM TGFVEN "
        f"WHERE CODGER = {codvend} AND ATIVO = 'S'"
    )
    rows = _execute_sankhya_query(sql)
    team = [int(r.get("CODVEND", 0)) for r in rows if r.get("CODVEND")]
    if codvend not in team:
        team.append(codvend)
    return team


def determine_role(username: str, profile: dict) -> str:
    """Determina o perfil RBAC do usuario."""
    if username.upper() in ADMIN_USERS:
        return "admin"
    if not profile:
        return "admin" if username.upper() in ADMIN_USERS else None
    # Verificar se tem subordinados (gerente)
    sql = (
        f"SELECT COUNT(*) AS QTD FROM TGFVEN "
        f"WHERE CODGER = {profile['codvend']} AND ATIVO = 'S' "
        f"AND CODVEND != {profile['codvend']}"
    )
    rows = _execute_sankhya_query(sql)
    if rows and int(rows[0].get("QTD", 0)) > 0:
        return "gerente"
    tipvend = (profile.get("tipvend") or "").upper()
    if tipvend == "V":
        return "vendedor"
    if tipvend == "C":
        return "comprador"
    return "vendedor"


def get_visible_modules(role: str) -> dict:
    """Retorna modulos visiveis por perfil."""
    if role == "vendedor":
        return {"chat": True, "reports_vendas": True, "reports_compras": False}
    if role == "comprador":
        return {"chat": True, "reports_vendas": False, "reports_compras": True}
    return {"chat": True, "reports_vendas": True, "reports_compras": True}


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Valida token e retorna sessao completa do usuario."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token nao fornecido")

    token = authorization.replace("Bearer ", "")
    session = sessions.get(token)

    if not session:
        raise HTTPException(status_code=401, detail="Sessao invalida")

    if datetime.now() - session["last_activity"] > SESSION_TIMEOUT:
        del sessions[token]
        raise HTTPException(status_code=401, detail="Sessao expirada")

    session["last_activity"] = datetime.now()
    return session

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
    print(f"[i] Acesse: http://localhost:8080")

# ============================================================
# MODELS
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str

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

# Montar pasta static para servir imagens, CSS, JS
app.mount("/imagens", StaticFiles(directory=str(Path(__file__).parent / "static" / "imagens")), name="imagens")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


# ============================================================
# AUTH ROUTES
# ============================================================

@app.post("/api/login")
async def login(req: LoginRequest):
    """Autentica usuario via Sankhya MobileLogin (com OAuth no gateway)."""
    try:
        # 1. Obter token OAuth do gateway
        oauth_token = get_sankhya_oauth_token()

        # 2. Chamar MobileLogin com o token OAuth
        resp = http_requests.post(
            f"{SANKHYA_BASE_URL}/gateway/v1/mge/service.sbr",
            params={
                "serviceName": "MobileLoginSP.login",
                "outputType": "json",
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {oauth_token}",
            },
            json={
                "requestBody": {
                    "NOMUSU": {"$": req.username},
                    "INTERNO": {"$": req.password},
                    "KEEPCONNECTED": {"$": "S"}
                }
            },
            timeout=30,
            verify=False
        )
        raw_login = resp.text
        print(f"[AUTH] MobileLogin HTTP {resp.status_code}: {raw_login[:500]}")

        if not raw_login.strip():
            raise Exception(f"MobileLogin retornou resposta vazia (HTTP {resp.status_code})")

        try:
            data = resp.json()
        except Exception:
            raise Exception(f"MobileLogin resposta nao-JSON (HTTP {resp.status_code}): '{raw_login[:300]}'")

    except Exception as e:
        print(f"[AUTH] Erro: {e}")
        raise HTTPException(status_code=503, detail=str(e))

    # Sankhya retorna status como string "1" ou int 1
    status = data.get("status")
    if str(status) != "1":
        msg = data.get("statusMessage", data.get("message", ""))
        print(f"[AUTH] Login falhou para '{req.username}': status={status}, full={data}")
        detail = msg if msg else f"Sankhya retornou: {data}"
        raise HTTPException(status_code=401, detail=detail)

    # Buscar perfil RBAC na TGFVEN
    profile = None
    role = "admin" if req.username.upper() in ADMIN_USERS else None
    codvend = 0
    team_codvends = []

    try:
        profile = fetch_user_profile(req.username)
        if profile:
            role = determine_role(req.username, profile)
            codvend = profile["codvend"]
            if role == "gerente":
                team_codvends = fetch_team_codvends(codvend)
            print(f"[RBAC] {req.username}: role={role}, codvend={codvend}, tipvend={profile.get('tipvend')}")
        elif not role:
            print(f"[RBAC] {req.username}: nao encontrado na TGFVEN, negando acesso")
            raise HTTPException(status_code=403, detail="Usuario nao tem perfil cadastrado na TGFVEN")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[RBAC] Erro ao buscar perfil: {e}")
        if not role:
            role = "vendedor"

    modules = get_visible_modules(role)

    # Criar sessao local enriquecida
    token = secrets.token_hex(32)
    sessions[token] = {
        "user": req.username,
        "role": role,
        "codvend": codvend,
        "tipvend": profile.get("tipvend", "") if profile else "",
        "codger": profile.get("codger", 0) if profile else 0,
        "codemp": profile.get("codemp", 0) if profile else 0,
        "team_codvends": team_codvends,
        "modules": modules,
        "login_time": datetime.now(),
        "last_activity": datetime.now()
    }

    print(f"[AUTH] Login: {req.username} (role={role}, {len(sessions)} sessoes ativas)")
    return {"token": token, "user": req.username, "role": role, "modules": modules}


@app.post("/api/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """Encerra sessao do usuario."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        user = sessions.pop(token, {}).get("user", "?")
        print(f"[AUTH] Logout: {user} ({len(sessions)} sessoes ativas)")
    return {"status": "ok"}


@app.get("/api/me")
async def me(authorization: Optional[str] = Header(None)):
    """Retorna info do usuario logado com perfil RBAC."""
    session = get_current_user(authorization)
    return {
        "user": session["user"],
        "role": session.get("role", "vendedor"),
        "codvend": session.get("codvend", 0),
        "modules": session.get("modules", get_visible_modules("vendedor")),
    }

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve a interface web."""
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, authorization: Optional[str] = Header(None)):
    """Endpoint principal de chat com agente."""
    session = get_current_user(authorization)
    start = time.time()
    question = req.message.strip()

    if not question:
        return ChatResponse(
            response="Envie uma pergunta.",
            sources=[],
            mode=req.mode,
            tipo="erro",
        )

    # Usar o agente com contexto RBAC
    user_context = {
        "user": session["user"],
        "role": session.get("role", "vendedor"),
        "codvend": session.get("codvend", 0),
        "tipvend": session.get("tipvend", ""),
        "team_codvends": session.get("team_codvends", []),
    }
    try:
        result = await agent.ask(question, user_context=user_context)
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
async def clear_history(authorization: Optional[str] = Header(None)):
    """Limpa o historico do chat."""
    get_current_user(authorization)
    agent.clear_history()
    return {"status": "ok", "message": "Historico limpo"}


@app.get("/api/status")
async def status(authorization: Optional[str] = Header(None)):
    """Status da base de conhecimento e agente."""
    get_current_user(authorization)
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
        port=8080,
        reload=True,
    )
