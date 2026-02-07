"""
Extrai campos das tabelas TGFMAR e TGFVAR do dicionario Sankhya.

Uso:
    python -m src.mcp.extract_tgfmar_tgfvar
"""

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.query_executor import SafeQueryExecutor


async def main():
    executor = SafeQueryExecutor()

    # 1. Campos da TGFMAR
    print("=" * 60)
    print("TGFMAR - Marcas de Produtos")
    print("=" * 60)

    result = await executor.execute("""
        SELECT CAM.NOMECAMPO, CAM.DESCRCAMPO, CAM.TIPCAMPO
        FROM TDDCAM CAM
        WHERE CAM.NOMETAB = 'TGFMAR'
        ORDER BY CAM.NOMECAMPO
    """)
    if result["success"]:
        for row in result["data"]:
            print(f"  {row}")
    else:
        print(f"  ERRO: {result.get('error')}")

    # 1b. Contagem TGFMAR
    print("\nContagem TGFMAR:")
    result = await executor.execute("SELECT COUNT(*) AS TOTAL FROM TGFMAR")
    if result["success"]:
        print(f"  {result['data']}")

    # 1c. Opcoes de dominio TGFMAR
    print("\nOpcoes de dominio TGFMAR:")
    result = await executor.execute("""
        SELECT CAM.NOMECAMPO, CAM.DESCRCAMPO, OPC.VALOR, OPC.OPCAO
        FROM TDDOPC OPC
        JOIN TDDCAM CAM ON OPC.NUCAMPO = CAM.NUCAMPO
        WHERE CAM.NOMETAB = 'TGFMAR'
        ORDER BY CAM.NOMECAMPO, OPC.VALOR
    """)
    if result["success"]:
        for row in result["data"]:
            print(f"  {row}")
    else:
        print(f"  ERRO: {result.get('error')}")

    # 1d. Relacionamentos TGFMAR
    print("\nRelacionamentos TGFMAR:")
    result = await executor.execute("""
        SELECT
            ORIG.NOMEINSTANCIA AS ORIG_INST,
            ORIG.NOMETAB AS TAB_ORIGEM,
            DEST.NOMEINSTANCIA AS DEST_INST,
            DEST.NOMETAB AS TAB_DESTINO,
            LIG.TIPLIGACAO
        FROM TDDLIG LIG
        JOIN TDDINS ORIG ON LIG.NUINSTORIG = ORIG.NUINSTANCIA
        JOIN TDDINS DEST ON LIG.NUINSTDEST = DEST.NUINSTANCIA
        WHERE ORIG.NOMETAB = 'TGFMAR' OR DEST.NOMETAB = 'TGFMAR'
        ORDER BY ORIG.NOMETAB
    """)
    if result["success"]:
        for row in result["data"]:
            print(f"  {row}")
    else:
        print(f"  ERRO: {result.get('error')}")

    # 2. Campos da TGFVAR
    print("\n" + "=" * 60)
    print("TGFVAR - Variacoes/Atendimentos de Pedido")
    print("=" * 60)

    result = await executor.execute("""
        SELECT CAM.NOMECAMPO, CAM.DESCRCAMPO, CAM.TIPCAMPO
        FROM TDDCAM CAM
        WHERE CAM.NOMETAB = 'TGFVAR'
        ORDER BY CAM.NOMECAMPO
    """)
    if result["success"]:
        for row in result["data"]:
            print(f"  {row}")
    else:
        print(f"  ERRO: {result.get('error')}")

    # 2b. Contagem TGFVAR
    print("\nContagem TGFVAR:")
    result = await executor.execute("SELECT COUNT(*) AS TOTAL FROM TGFVAR")
    if result["success"]:
        print(f"  {result['data']}")

    # 2c. Opcoes de dominio TGFVAR
    print("\nOpcoes de dominio TGFVAR:")
    result = await executor.execute("""
        SELECT CAM.NOMECAMPO, CAM.DESCRCAMPO, OPC.VALOR, OPC.OPCAO
        FROM TDDOPC OPC
        JOIN TDDCAM CAM ON OPC.NUCAMPO = CAM.NUCAMPO
        WHERE CAM.NOMETAB = 'TGFVAR'
        ORDER BY CAM.NOMECAMPO, OPC.VALOR
    """)
    if result["success"]:
        for row in result["data"]:
            print(f"  {row}")
    else:
        print(f"  ERRO: {result.get('error')}")

    # 2d. Relacionamentos TGFVAR
    print("\nRelacionamentos TGFVAR:")
    result = await executor.execute("""
        SELECT
            ORIG.NOMEINSTANCIA AS ORIG_INST,
            ORIG.NOMETAB AS TAB_ORIGEM,
            DEST.NOMEINSTANCIA AS DEST_INST,
            DEST.NOMETAB AS TAB_DESTINO,
            LIG.TIPLIGACAO
        FROM TDDLIG LIG
        JOIN TDDINS ORIG ON LIG.NUINSTORIG = ORIG.NUINSTANCIA
        JOIN TDDINS DEST ON LIG.NUINSTDEST = DEST.NUINSTANCIA
        WHERE ORIG.NOMETAB = 'TGFVAR' OR DEST.NOMETAB = 'TGFVAR'
        ORDER BY ORIG.NOMETAB
    """)
    if result["success"]:
        for row in result["data"]:
            print(f"  {row}")
    else:
        print(f"  ERRO: {result.get('error')}")

    # 3. Verificar campo CODMARCA em TGFPRO
    print("\n" + "=" * 60)
    print("Verificacao: CODMARCA em TGFPRO")
    print("=" * 60)
    result = await executor.execute("""
        SELECT CAM.NOMECAMPO, CAM.DESCRCAMPO, CAM.TIPCAMPO
        FROM TDDCAM CAM
        WHERE CAM.NOMETAB = 'TGFPRO' AND CAM.NOMECAMPO = 'CODMARCA'
    """)
    if result["success"]:
        for row in result["data"]:
            print(f"  {row}")

    # 4. Amostra TGFMAR
    print("\nAmostra TGFMAR (10 primeiros):")
    result = await executor.execute("""
        SELECT M.CODIGO, M.DESCRICAO, M.AD_CODVEND
        FROM TGFMAR M
        WHERE ROWNUM <= 10
        ORDER BY M.CODIGO
    """)
    if result["success"]:
        for row in result["data"]:
            print(f"  {row}")
    else:
        print(f"  ERRO: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(main())
