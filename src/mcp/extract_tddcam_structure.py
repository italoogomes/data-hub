"""Descobre a estrutura das tabelas TDD*."""

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.query_executor import SafeQueryExecutor


async def main():
    executor = SafeQueryExecutor()

    # Descobrir as colunas da TDDCAM consultando ela mesma
    print("[*] Colunas de TDDCAM (via dicionario)...")
    result = await executor.execute(
        "SELECT NOMECAMPO, DESCRCAMPO FROM TDDCAM WHERE NOMETAB = 'TDDCAM' ORDER BY NOMECAMPO"
    )
    if result.get("success"):
        for row in result.get("data", []):
            print(f"    {row}")
    else:
        print(f"    Erro: {result.get('error')}")

    # Testar query de campos para TGFCAB (so NOMECAMPO e DESCRCAMPO)
    print("\n[*] Campos de TGFCAB (primeiros 10)...")
    result = await executor.execute(
        "SELECT * FROM (SELECT NOMECAMPO, DESCRCAMPO FROM TDDCAM WHERE NOMETAB = 'TGFCAB' ORDER BY NOMECAMPO) WHERE ROWNUM <= 10"
    )
    if result.get("success"):
        print(f"    Total: {result.get('row_count', 0)} registros")
        for row in result.get("data", []):
            print(f"    {row}")
    else:
        print(f"    Erro: {result.get('error')}")

    # Colunas de TDDINS
    print("\n[*] Colunas de TDDINS (via dicionario)...")
    result = await executor.execute(
        "SELECT NOMECAMPO, DESCRCAMPO FROM TDDCAM WHERE NOMETAB = 'TDDINS' ORDER BY NOMECAMPO"
    )
    if result.get("success"):
        for row in result.get("data", []):
            print(f"    {row}")
    else:
        print(f"    Erro: {result.get('error')}")

    # Colunas de TDDOPC
    print("\n[*] Colunas de TDDOPC (via dicionario)...")
    result = await executor.execute(
        "SELECT NOMECAMPO, DESCRCAMPO FROM TDDCAM WHERE NOMETAB = 'TDDOPC' ORDER BY NOMECAMPO"
    )
    if result.get("success"):
        for row in result.get("data", []):
            print(f"    {row}")
    else:
        print(f"    Erro: {result.get('error')}")

    # Colunas de TDDLIG
    print("\n[*] Colunas de TDDLIG (via dicionario)...")
    result = await executor.execute(
        "SELECT NOMECAMPO, DESCRCAMPO FROM TDDCAM WHERE NOMETAB = 'TDDLIG' ORDER BY NOMECAMPO"
    )
    if result.get("success"):
        for row in result.get("data", []):
            print(f"    {row}")
    else:
        print(f"    Erro: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
