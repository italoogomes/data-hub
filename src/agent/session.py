"""
MMarra Data Hub - Session Memory.

Memória de sessão melhorada que mantém histórico de mensagens por usuário.
Permite ao agente:
- Lembrar o que foi perguntado antes na mesma sessão
- Resolver pronomes ("e de uberlândia?" → sabe que o contexto era pendências da MANN)
- Acumular filtros progressivos ("pendências MANN" → "só os atrasados" → "exporta pra Excel")
- Manter parâmetros entre turnos para follow-up natural

Integra com ConversationContext existente + adiciona histórico de mensagens.
"""

import time
from typing import Optional
from dataclasses import dataclass, field

from src.agent.context import ConversationContext


@dataclass
class Message:
    """Uma mensagem na sessão."""
    role: str           # "user" ou "assistant"
    content: str        # Texto da mensagem
    tool_used: str = "" # Tool que foi usada (se assistant)
    params: dict = field(default_factory=dict)  # Parâmetros da tool call
    timestamp: float = field(default_factory=time.time)


class SessionMemory:
    """
    Memória de sessão por usuário.
    Combina ConversationContext (estado atual) com histórico de mensagens.
    
    Usage:
        sessions = {}  # ou cache com TTL
        
        session = sessions.get(user_id) or SessionMemory(user_id)
        session.add_user_message(question)
        # ... processar ...
        session.add_assistant_message(response_text, tool_name, params)
        sessions[user_id] = session
    """

    MAX_HISTORY = 20  # Máximo de mensagens por sessão
    SESSION_TTL = 3600  # 1 hora de inatividade = sessão expira

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.ctx = ConversationContext(user_id)
        self.messages: list[Message] = []
        self.created_at = time.time()
        self.last_active = time.time()

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.last_active) > self.SESSION_TTL

    @property
    def turn_count(self) -> int:
        return len([m for m in self.messages if m.role == "user"])

    def add_user_message(self, content: str):
        """Registra mensagem do usuário."""
        self.messages.append(Message(role="user", content=content))
        self.last_active = time.time()
        self._trim()

    def add_assistant_message(self, content: str, tool_used: str = "",
                               params: dict = None):
        """Registra resposta do assistente com a tool usada."""
        self.messages.append(Message(
            role="assistant",
            content=content[:500],  # Truncar respostas longas
            tool_used=tool_used,
            params=params or {}
        ))
        self.last_active = time.time()
        self._trim()

    def get_history_for_llm(self, max_messages: int = 6) -> list[dict]:
        """
        Retorna histórico formatado para enviar ao LLM como contexto.
        Inclui só as últimas N mensagens para não estourar tokens.
        """
        recent = self.messages[-max_messages:]
        history = []
        for msg in recent:
            if msg.role == "user":
                history.append({"role": "user", "content": msg.content})
            else:
                # Resumo compacto da resposta do assistente
                summary = f"[Usou: {msg.tool_used}]"
                if msg.params:
                    param_str = ", ".join(f"{k}={v}" for k, v in msg.params.items() if v)
                    if param_str:
                        summary += f" ({param_str})"
                history.append({"role": "assistant", "content": summary})
        return history

    def get_context_summary(self) -> str:
        """
        Resumo do contexto da sessão para o router/classificador.
        Mais rico que build_context_hint do ConversationContext.
        """
        if not self.messages:
            return ""

        parts = []

        # Última tool usada
        last_assistant = None
        for msg in reversed(self.messages):
            if msg.role == "assistant" and msg.tool_used:
                last_assistant = msg
                break

        if last_assistant:
            parts.append(f"Última consulta: {last_assistant.tool_used}")
            if last_assistant.params:
                param_str = ", ".join(f"{k}={v}" for k, v in last_assistant.params.items() if v)
                if param_str:
                    parts.append(f"Parâmetros: {param_str}")

        # Dados disponíveis no contexto
        if self.ctx.has_data():
            data = self.ctx.get_data()
            parts.append(f"Dados em memória: {len(data)} registros")

        # Entidades acumuladas na sessão
        accumulated = self._get_accumulated_entities()
        if accumulated:
            parts.append(f"Entidades da sessão: {accumulated}")

        return " | ".join(parts) if parts else ""

    def _get_accumulated_entities(self) -> dict:
        """Coleta todas as entidades mencionadas na sessão."""
        entities = {}
        for msg in self.messages:
            if msg.role == "assistant" and msg.params:
                for key in ("marca", "empresa", "comprador", "fornecedor", "periodo"):
                    val = msg.params.get(key)
                    if val:
                        entities[key] = val  # Último valor mencionado prevalece
        return entities

    def _trim(self):
        """Remove mensagens antigas se exceder MAX_HISTORY."""
        if len(self.messages) > self.MAX_HISTORY:
            self.messages = self.messages[-self.MAX_HISTORY:]

    def __repr__(self):
        return (f"<Session user={self.user_id} turns={self.turn_count} "
                f"last_tool={self.ctx.intent} expired={self.is_expired}>")


# ============================================================
# SESSION STORE (in-memory, com cleanup automático)
# ============================================================

class SessionStore:
    """
    Store global de sessões. Thread-safe para uso com FastAPI.
    Limpa sessões expiradas automaticamente.
    """

    def __init__(self):
        self._sessions: dict[str, SessionMemory] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutos

    def get(self, user_id: str) -> SessionMemory:
        """Retorna sessão existente ou cria nova."""
        self._maybe_cleanup()

        session = self._sessions.get(user_id)
        if session and not session.is_expired:
            return session

        # Nova sessão
        session = SessionMemory(user_id)
        self._sessions[user_id] = session
        return session

    def get_context(self, user_id: str) -> ConversationContext:
        """Atalho: retorna o ConversationContext da sessão."""
        return self.get(user_id).ctx

    def _maybe_cleanup(self):
        """Remove sessões expiradas periodicamente."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        expired = [uid for uid, s in self._sessions.items() if s.is_expired]
        for uid in expired:
            del self._sessions[uid]

        if expired:
            print(f"[SESSION] Cleanup: {len(expired)} sessões expiradas removidas, "
                  f"{len(self._sessions)} ativas")
        self._last_cleanup = now

    @property
    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if not s.is_expired)

    def stats(self) -> dict:
        return {
            "total_sessions": len(self._sessions),
            "active_sessions": self.active_count,
            "sessions": {
                uid: {
                    "turns": s.turn_count,
                    "last_tool": s.ctx.intent,
                    "last_active_ago": f"{time.time() - s.last_active:.0f}s",
                }
                for uid, s in self._sessions.items()
                if not s.is_expired
            }
        }


# Instância global
session_store = SessionStore()
