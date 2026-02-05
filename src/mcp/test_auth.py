"""Script para testar autenticação do Sankhya."""
import asyncio
from server import sankhya

async def test():
    print(f"Client ID: {sankhya.client_id[:8]}...")
    print(f"X-Token: {sankhya.x_token[:8]}...")
    print("\nTestando autenticação...")

    try:
        token = await sankhya._authenticate()
        print(f"Access Token: {token[:20]}...")
        print("\nAutenticação OK!")

        # Testa uma query simples (sintaxe Oracle)
        print("\nTestando query...")
        result = await sankhya.execute_query("SELECT CODPARC, NOMEPARC FROM TGFPAR WHERE ROWNUM <= 1")
        print(f"Resultado: {result}")

    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    asyncio.run(test())
