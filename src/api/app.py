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
from collections import defaultdict
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
from src.llm.smart_agent import SmartAgent
from src.llm.llm_client import LLMClient, LLM_MODEL, LLM_PROVIDER

# Import reports
from src.api.reports import router as reports_router

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

# Reports router
app.include_router(reports_router)

# Estado global
agent = DataHubAgent()
smart_agent = SmartAgent()

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


# ============================================================
# RATE LIMITER (in-memory, sem dependencias externas)
# ============================================================

class SimpleRateLimiter:
    """Rate limiter simples por usuario. 30 requests/minuto por padrao."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        # Limpar requests fora da janela
        self._requests[user_id] = [
            t for t in self._requests[user_id] if now - t < self.window
        ]
        if len(self._requests[user_id]) >= self.max_requests:
            return False
        self._requests[user_id].append(now)
        return True

    def remaining(self, user_id: str) -> int:
        now = time.time()
        recent = [t for t in self._requests.get(user_id, []) if now - t < self.window]
        return max(0, self.max_requests - len(recent))


rate_limiter = SimpleRateLimiter(max_requests=30, window_seconds=60)


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
    # Criar pasta de exports se nao existir
    exports_dir = Path(__file__).parent / "static" / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Pasta exports: {exports_dir}")

    # Smart Agent - sempre disponivel (sem LLM)
    print(f"[OK] Smart Agent pronto (templates SQL, zero LLM)")

    # Verificar se LLM esta disponivel (para fallback)
    llm_client = LLMClient()
    health = llm_client.check_health()

    if health["status"] != "ok":
        print(f"[!] LLM nao disponivel: {health.get('error', 'Erro desconhecido')}")
        print(f"[!] Smart Agent funciona normalmente. LLM so e necessario para perguntas complexas.")
    else:
        print(f"[OK] LLM conectado ({LLM_PROVIDER}/{LLM_MODEL})")

    try:
        agent.initialize()
        print(f"[OK] LLM Agent inicializado ({len(agent.kb.documents)} docs)")
    except Exception as e:
        print(f"[!] LLM Agent nao inicializou: {e}")
        print(f"[!] Smart Agent continua funcionando normalmente.")

    # Knowledge Compiler - compilacao incremental em background
    try:
        from src.llm.knowledge_compiler import KnowledgeCompiler
        compiler = KnowledgeCompiler()
        stats = await compiler.compile(full=False, dry_run=False, verbose=False)
        if stats.get("processed", 0) > 0:
            print(f"[OK] Knowledge Compiler: {stats['processed']} docs processados ({stats.get('groq_calls', 0)} Groq calls)")
            # Recarregar no SmartAgent
            from src.llm.smart_agent import _load_compiled_knowledge, _COMPILED_LOADED
            import src.llm.smart_agent as _sa
            _sa._COMPILED_LOADED = False  # forcar recarga
            _load_compiled_knowledge()
        else:
            print(f"[OK] Knowledge Compiler: up-to-date ({stats.get('total_files', 0)} docs)")
    except Exception as e:
        print(f"[!] Knowledge Compiler falhou (nao critico): {e}")

    # Training scheduler (roda de madrugada)
    try:
        from src.llm.smart_agent import _training_scheduler
        import asyncio
        asyncio.create_task(_training_scheduler())
        from src.llm.smart_agent import TRAINING_HOUR
        print(f"[OK] Training scheduler ativo (todo dia as {TRAINING_HOUR}h)")
    except Exception as e:
        print(f"[!] Training scheduler falhou: {e}")

    # Elasticsearch: verificar e sincronizar se indice vazio
    try:
        from src.elastic.search import ElasticSearchEngine
        from src.elastic.sync import ElasticSync
        _es_search = ElasticSearchEngine()
        health = await _es_search.health()
        if health.get("status") != "offline":
            print(f"[OK] Elasticsearch: {health.get('status')}")
            products_count = health.get("indices", {}).get("idx_produtos", {}).get("docs", "0")
            partners_count = health.get("indices", {}).get("idx_parceiros", {}).get("docs", "0")
            if int(products_count or 0) == 0:
                print("[ELASTIC] Indice vazio — iniciando full sync em background...")
                _es_sync = ElasticSync(smart_agent.executor)
                asyncio.create_task(_es_sync.full_sync())
            else:
                print(f"[OK] Elastic: {products_count} produtos, {partners_count} parceiros indexados")
        else:
            print(f"[!] Elasticsearch offline: {health.get('error', '?')}")
    except Exception as e:
        print(f"[!] Elasticsearch nao disponivel (nao critico): {e}")

    print(f"[OK] MMarra Data Hub API pronta!")
    print(f"[i] Acesse: http://localhost:8000")

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
    tipo: str = "documentacao"  # "documentacao", "consulta_banco", "arquivo", "erro"
    query_executed: Optional[str] = None
    query_results: Optional[int] = None
    download_url: Optional[str] = None
    time_ms: int = 0
    message_id: Optional[str] = None
    table_data: Optional[dict] = None  # {columns, rows, visible_columns} para toggle frontend

class FeedbackRequest(BaseModel):
    message_id: str
    rating: str  # "positive" | "negative"
    comment: Optional[str] = None

class AliasRequest(BaseModel):
    action: str  # "add" | "approve" | "reject" | "remove"
    apelido: str
    nome_real: Optional[str] = None
    codprod: Optional[int] = None

# ============================================================
# ROUTES
# ============================================================

# Garantir que pasta exports exista antes do mount
Path(__file__).parent.joinpath("static", "exports").mkdir(parents=True, exist_ok=True)

# Montar pasta static para servir imagens, CSS, JS
app.mount("/imagens", StaticFiles(directory=str(Path(__file__).parent / "static" / "imagens")), name="imagens")
app.mount("/static/exports", StaticFiles(directory=str(Path(__file__).parent / "static" / "exports")), name="exports")
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
        smart_agent.query_logger.log_security_event(
            req.username, "login_failed",
            f"status={status}, msg={msg[:100] if msg else 'N/A'}"
        )
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
        session = sessions.pop(token, {})
        user = session.get("user", "?")
        # Limpar contexto de conversa do usuario
        smart_agent.clear_user(user)
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
    """Endpoint principal de chat com agente.

    Fluxo:
    1. SmartAgent tenta responder (regex + SQL templates, instantaneo)
    2. Se nao matchou, cai no LLM Agent (Ollama, pode demorar)
    """
    session = get_current_user(authorization)
    user = session.get("user", "anonymous")
    start = time.time()
    question = req.message.strip()

    if not question:
        return ChatResponse(
            response="Envie uma pergunta.",
            sources=[],
            mode=req.mode,
            tipo="erro",
        )

    # Rate limiting
    if not rate_limiter.is_allowed(user):
        print(f"[SECURITY] Rate limit exceeded: {user}")
        smart_agent.query_logger.log_security_event(
            user, "rate_limit",
            f"Exceeded {rate_limiter.max_requests} req/{rate_limiter.window}s"
        )
        return ChatResponse(
            response="Muitas consultas em sequencia. Aguarde alguns segundos e tente novamente.",
            sources=[],
            mode=req.mode,
            tipo="rate_limit",
            time_ms=int((time.time() - start) * 1000),
        )

    user_context = {
        "user": session["user"],
        "role": session.get("role", "vendedor"),
        "codvend": session.get("codvend", 0),
        "tipvend": session.get("tipvend", ""),
        "team_codvends": session.get("team_codvends", []),
    }

    # ---- SMART AGENT (instantaneo, sem LLM) ----
    try:
        smart_result = await smart_agent.ask(question, user_context=user_context)
        if smart_result:
            elapsed = int((time.time() - start) * 1000)

            # Extrair table_data para toggle de colunas no frontend
            _td = None
            _detail = smart_result.pop("_detail_data", None)
            _vis_cols = smart_result.pop("_visible_columns", None)
            if _detail and isinstance(_detail, list) and len(_detail) > 0:
                _all_cols = list(_detail[0].keys()) if isinstance(_detail[0], dict) else []
                _td = {
                    "columns": _all_cols,
                    "rows": _detail[:200],  # limitar payload
                    "visible_columns": _vis_cols or [],
                }

            return ChatResponse(
                response=smart_result.get("response", "Sem resposta"),
                sources=[],
                mode="smart",
                tipo=smart_result.get("tipo", "consulta_banco"),
                query_executed=smart_result.get("query_executed"),
                query_results=smart_result.get("query_results"),
                download_url=smart_result.get("download_url"),
                time_ms=elapsed,
                message_id=smart_result.get("message_id"),
                table_data=_td,
            )
    except Exception as e:
        print(f"[SMART] Erro: {e}")

    # ---- LLM AGENT (fallback - desabilitado se SMART_ONLY=true) ----
    smart_only = os.getenv("SMART_ONLY", "true").lower() in ("true", "1", "yes")
    if smart_only:
        elapsed = int((time.time() - start) * 1000)
        return ChatResponse(
            response="🤔 Não entendi a pergunta.\n\nTente algo como:\n- *\"Pendência da marca Donaldson\"*\n- *\"Vendas de hoje\"*\n- *\"Estoque do produto 133346\"*\n\nOu digite **ajuda** para ver tudo que posso fazer.",
            sources=[],
            mode="smart",
            tipo="info",
            time_ms=elapsed,
        )

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


@app.post("/api/feedback")
async def feedback(req: FeedbackRequest, authorization: Optional[str] = Header(None)):
    """Registra feedback do usuario sobre uma resposta."""
    get_current_user(authorization)
    if req.rating not in ("positive", "negative"):
        raise HTTPException(status_code=400, detail="Rating deve ser 'positive' ou 'negative'")
    found = smart_agent.query_logger.save_feedback(req.message_id, req.rating, req.comment)

    # B3: Detectar alias via feedback negativo
    if req.rating == "negative" and found:
        log_entry = smart_agent.query_logger.get_entry(req.message_id)
        if log_entry:
            smart_agent.alias_resolver.detect_alias_from_feedback(log_entry, req.rating, req.comment or "")

    return {"ok": found}


@app.get("/api/suggestions")
async def suggestions(authorization: Optional[str] = Header(None)):
    """Retorna sugestoes de perguntas baseadas no historico."""
    session = get_current_user(authorization)
    user = session.get("user", "")
    return smart_agent.query_logger.get_suggestions(user=user)


@app.get("/api/analytics")
async def analytics(authorization: Optional[str] = Header(None)):
    """Analytics de uso (admin only)."""
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return smart_agent.query_logger.get_analytics(days=30)


@app.get("/api/aliases")
async def get_aliases(authorization: Optional[str] = Header(None)):
    """Retorna todos os apelidos e sugestoes (admin only)."""
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return {
        "aliases": smart_agent.alias_resolver.get_all_aliases(),
        "suggestions": smart_agent.alias_resolver.get_suggestions("pending"),
        "stats": smart_agent.alias_resolver.stats(),
    }


@app.post("/api/aliases")
async def manage_aliases(req: AliasRequest, authorization: Optional[str] = Header(None)):
    """Gerencia apelidos (admin only). Actions: add, approve, reject, remove."""
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")

    if req.action == "add":
        if not req.nome_real and not req.codprod:
            raise HTTPException(status_code=400, detail="Informe nome_real ou codprod")
        ok = smart_agent.alias_resolver.add_alias(
            req.apelido, nome_real=req.nome_real, codprod=req.codprod,
            confidence=0.95, origem="admin"
        )
        return {"ok": ok, "action": "add"}

    elif req.action == "approve":
        ok = smart_agent.alias_resolver.approve_suggestion(
            req.apelido, nome_real=req.nome_real, codprod=req.codprod
        )
        return {"ok": ok, "action": "approve"}

    elif req.action == "reject":
        ok = smart_agent.alias_resolver.reject_suggestion(req.apelido)
        return {"ok": ok, "action": "reject"}

    elif req.action == "remove":
        ok = smart_agent.alias_resolver.remove_alias(req.apelido)
        return {"ok": ok, "action": "remove"}

    else:
        raise HTTPException(status_code=400, detail="Action invalida. Use: add, approve, reject, remove")


@app.get("/api/admin/pools")
async def admin_pools(authorization: Optional[str] = Header(None)):
    """Status dos pools Groq (admin only)."""
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    from src.llm.smart_agent import pool_classify, pool_narrate, pool_train
    return {
        "classify": pool_classify.stats(),
        "narrate": pool_narrate.stats(),
        "train": pool_train.stats(),
    }


@app.post("/api/admin/train")
async def admin_train(authorization: Optional[str] = Header(None)):
    """Dispara treinamento manual (admin only)."""
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    from src.llm.smart_agent import daily_training
    stats = await daily_training(force=True)
    return stats


@app.get("/api/admin/elastic/health")
async def elastic_health(authorization: Optional[str] = Header(None)):
    """Status do Elasticsearch (admin only)."""
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    from src.elastic.search import ElasticSearchEngine
    es = ElasticSearchEngine()
    return await es.health()


@app.post("/api/admin/elastic/sync")
async def elastic_sync_endpoint(full: bool = False, authorization: Optional[str] = Header(None)):
    """Sincroniza Elasticsearch (admin only). ?full=true para sync completo."""
    session = get_current_user(authorization)
    if session.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    from src.elastic.sync import ElasticSync
    es_sync = ElasticSync(smart_agent.executor)
    if full:
        result = await es_sync.full_sync()
    else:
        result = await es_sync.incremental_sync()
    return result


@app.post("/api/clear")
async def clear_history(authorization: Optional[str] = Header(None)):
    """Limpa o historico do chat."""
    session = get_current_user(authorization)
    user = session.get("user", "")
    agent.clear_history()
    smart_agent.clear_user(user)
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
        port=8000,
        reload=True,
    )