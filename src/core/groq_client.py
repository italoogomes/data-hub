"""
MMarra Data Hub - Cliente Groq API.
Key pool com rotação round-robin e cooldown automático.
Extraído de smart_agent.py na refatoração modular.
"""

import os
import time
import httpx
from typing import Optional


# Config
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_MODEL_CLASSIFY = os.getenv("GROQ_MODEL_CLASSIFY", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "10"))
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqKeyPool:
    """Pool de chaves Groq com rotação round-robin e cooldown automático."""

    def __init__(self, keys: list, name: str = "default"):
        self._keys = [k.strip() for k in keys if k.strip()]
        self._name = name
        self._index = 0
        self._cooldown = {}
        self._usage = {k: 0 for k in self._keys}
        self._daily_usage = {k: 0 for k in self._keys}
        self._last_reset = time.time()
        self._errors = {k: 0 for k in self._keys}
        if self._keys:
            print(f"[GROQ:{name}] Pool inicializado com {len(self._keys)} chave(s)")
        else:
            print(f"[GROQ:{name}] Pool VAZIO - sem chaves configuradas")

    @property
    def available(self) -> bool:
        return len(self._keys) > 0

    def get_key(self) -> str | None:
        """Retorna próxima chave disponível (round-robin, pula chaves em cooldown)."""
        if not self._keys:
            return None
        self._maybe_reset_daily()
        now = time.time()
        for _ in range(len(self._keys)):
            key = self._keys[self._index % len(self._keys)]
            self._index += 1
            if self._cooldown.get(key, 0) > now:
                continue
            self._usage[key] += 1
            self._daily_usage[key] += 1
            return key
        earliest = min(self._cooldown, key=self._cooldown.get)
        print(f"[GROQ:{self._name}] Todas as chaves em cooldown. Usando ...{earliest[-6:]}")
        return earliest

    def mark_rate_limited(self, key: str, retry_after: int = 60):
        self._cooldown[key] = time.time() + retry_after
        self._errors[key] = self._errors.get(key, 0) + 1
        print(f"[GROQ:{self._name}] ...{key[-6:]} rate-limited, cooldown {retry_after}s")

    def mark_error(self, key: str):
        self._errors[key] = self._errors.get(key, 0) + 1

    def _maybe_reset_daily(self):
        now = time.time()
        if now - self._last_reset > 86400:
            self._daily_usage = {k: 0 for k in self._keys}
            self._cooldown = {}
            self._last_reset = now
            print(f"[GROQ:{self._name}] Contadores diários resetados")

    def stats(self) -> dict:
        return {
            "pool": self._name,
            "keys": len(self._keys),
            "usage_total": {f"...{k[-6:]}": v for k, v in self._usage.items()},
            "usage_today": {f"...{k[-6:]}": v for k, v in self._daily_usage.items()},
            "errors": {f"...{k[-6:]}": v for k, v in self._errors.items() if v > 0},
            "in_cooldown": sum(1 for t in self._cooldown.values() if t > time.time()),
        }


def _make_pool(env_var: str, name: str) -> GroqKeyPool:
    """Cria pool a partir de variável de ambiente (vírgula-separada)."""
    raw = os.getenv(env_var, "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    return GroqKeyPool(keys, name)


# ============================================================
# POOLS GLOBAIS
# ============================================================

pool_classify = _make_pool("GROQ_POOL_CLASSIFY", "classify")
pool_narrate = _make_pool("GROQ_POOL_NARRATE", "narrate")
pool_train = _make_pool("GROQ_POOL_TRAIN", "train")

# Fallback: chave legada
if not pool_classify.available:
    _legacy = os.getenv("GROQ_API_KEY", "")
    if _legacy:
        pool_classify = GroqKeyPool([_legacy], "classify-legacy")
        pool_narrate = GroqKeyPool([_legacy], "narrate-legacy")
        pool_train = GroqKeyPool([_legacy], "train-legacy")
        print("[GROQ] Usando chave legado GROQ_API_KEY para todos os pools")

print(f"[GROQ] Modelos: classify={GROQ_MODEL_CLASSIFY} | geral={GROQ_MODEL}")


# ============================================================
# GROQ REQUEST
# ============================================================

async def groq_request(pool: GroqKeyPool, messages: list, temperature: float = 0.0,
                       max_tokens: int = 400, timeout: int = None, model: str = None,
                       tools: list = None, tool_choice: str = None) -> dict | None:
    """Faz request ao Groq usando chave do pool, com retry automático.
    
    Args:
        tools: Lista de tool definitions (OpenAI format) para Function Calling.
        tool_choice: "auto", "required", "none", ou {"type":"function","function":{"name":"X"}}.
    """
    key = pool.get_key()
    if not key:
        return None

    _timeout = timeout or GROQ_TIMEOUT
    _model = model or GROQ_MODEL

    payload = {
        "model": _model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
    if tool_choice:
        payload["tool_choice"] = tool_choice

    try:
        async with httpx.AsyncClient(timeout=_timeout) as client:
            r = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload
            )

            if r.status_code == 429:
                retry_after = int(r.headers.get("retry-after", "60"))
                pool.mark_rate_limited(key, retry_after)
                fallback_key = pool.get_key()
                if fallback_key and fallback_key != key:
                    print(f"[GROQ:{pool._name}] Retry com chave alternativa")
                    r = await client.post(
                        GROQ_API_URL,
                        headers={"Authorization": f"Bearer {fallback_key}", "Content-Type": "application/json"},
                        json={"model": _model, "messages": messages,
                              "temperature": temperature, "max_tokens": max_tokens}
                    )
                    if r.status_code == 429:
                        pool.mark_rate_limited(fallback_key, int(r.headers.get("retry-after", "60")))
                        return None
                else:
                    return None

            r.raise_for_status()
            data = r.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", None)
            result = {"content": content, "usage": data.get("usage", {})}
            if tool_calls:
                result["tool_calls"] = tool_calls
            return result

    except httpx.TimeoutException:
        print(f"[GROQ:{pool._name}] Timeout ({_timeout}s)")
        pool.mark_error(key)
        return None
    except Exception as e:
        print(f"[GROQ:{pool._name}] Erro: {e}")
        pool.mark_error(key)
        return None
