"""
Teste de diagnostico da API Groq - verifica rate limits
"""
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

# Carregar .env do projeto
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv('GROQ_API_KEY')
print(f"API Key: {api_key[:20]}...{api_key[-10:]}" if api_key else "API Key NAO ENCONTRADA!")

response = httpx.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": "Diga apenas: OK"}],
        "max_tokens": 10,
    },
    timeout=30,
)

print(f"\n=== RESULTADO ===")
print(f"Status: {response.status_code}")

print(f"\n=== HEADERS DE RATE LIMIT ===")
rate_limit_headers = [
    "x-ratelimit-limit-requests",
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-requests",
    "x-ratelimit-reset-tokens",
    "retry-after",
]

for header in rate_limit_headers:
    value = response.headers.get(header, "N/A")
    print(f"  {header}: {value}")

print(f"\n=== BODY ===")
print(response.text[:500])
