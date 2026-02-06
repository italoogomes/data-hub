"""
MMarra Data Hub - Cliente LLM Unificado
Suporta Ollama (local) como provider.

Uso:
    from src.llm.llm_client import LLMClient

    client = LLMClient()
    response = client.chat([{"role": "user", "content": "Ola"}])
"""

import os
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Carregar .env
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Configuracoes
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


class LLMClient:
    """
    Cliente LLM unificado para Ollama.

    Ollama roda localmente sem rate limits e sem custos.
    Os dados nao saem da rede interna.
    """

    def __init__(self, model: str = None):
        self.provider = LLM_PROVIDER
        self.model = model or LLM_MODEL
        self.base_url = OLLAMA_URL
        self.timeout = 120  # segundos (modelos locais podem demorar)

    def chat(self, messages: list, temperature: float = 0.3) -> str:
        """
        Envia mensagens para o LLM e retorna a resposta.

        Args:
            messages: Lista de mensagens no formato OpenAI
                      [{"role": "user", "content": "texto"}, ...]
            temperature: Criatividade (0 = deterministico, 1 = criativo)

        Returns:
            Texto da resposta do LLM
        """
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")

        except httpx.TimeoutException:
            raise Exception(f"Timeout ao chamar Ollama ({self.timeout}s). O modelo pode estar carregando.")

        except httpx.HTTPStatusError as e:
            raise Exception(f"Erro HTTP do Ollama: {e.response.status_code} - {e.response.text}")

        except httpx.ConnectError:
            raise Exception(
                f"Nao foi possivel conectar ao Ollama em {self.base_url}. "
                "Verifique se o Ollama esta rodando."
            )

        except Exception as e:
            raise Exception(f"Erro ao chamar Ollama: {str(e)}")

    def check_health(self) -> dict:
        """
        Verifica se o Ollama esta rodando e se o modelo esta disponivel.

        Returns:
            dict com status, models (lista de modelos disponiveis)
        """
        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()

                models = [m["name"] for m in data.get("models", [])]
                model_available = self.model in models or any(self.model in m for m in models)

                return {
                    "status": "ok",
                    "provider": self.provider,
                    "base_url": self.base_url,
                    "model": self.model,
                    "model_available": model_available,
                    "models": models,
                }

        except httpx.ConnectError:
            return {
                "status": "error",
                "provider": self.provider,
                "base_url": self.base_url,
                "model": self.model,
                "model_available": False,
                "error": "Ollama nao esta rodando",
            }

        except Exception as e:
            return {
                "status": "error",
                "provider": self.provider,
                "base_url": self.base_url,
                "model": self.model,
                "model_available": False,
                "error": str(e),
            }

    def __repr__(self):
        return f"LLMClient(provider={self.provider}, model={self.model})"


# ============================================================
# TESTE
# ============================================================

if __name__ == "__main__":
    print("=== Teste do LLMClient ===\n")

    client = LLMClient()
    print(f"Provider: {client.provider}")
    print(f"Model: {client.model}")
    print(f"URL: {client.base_url}")

    print("\n--- Health Check ---")
    health = client.check_health()
    for k, v in health.items():
        print(f"  {k}: {v}")

    if health["status"] == "ok":
        print("\n--- Teste de Chat ---")
        response = client.chat([
            {"role": "user", "content": "Diga apenas: OK"}
        ], temperature=0)
        print(f"Resposta: {response}")
    else:
        print("\n[ERRO] Ollama nao esta disponivel")
