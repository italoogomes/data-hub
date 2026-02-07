"""
Extrai dicionario de dados do Sankhya (tabelas TDD*).
Salva resultados em JSON para processamento posterior.

Uso:
    python -m src.mcp.extract_data_dictionary
"""

import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.llm.query_executor import SafeQueryExecutor


TABELAS_ALVO = (
    "'TGFCAB','TGFITE','TGFPAR','TGFPRO','TGFTOP','TGFVEN',"
    "'TSIEMP','TGFEST','TGFFIN','TGFCOT','TGFPAG',"
    "'AD_TGFCUSMMA','AD_TGFPROAUXMMA'"
)

QUERIES = {
    "instancias": f"""
        SELECT INS.NUINSTANCIA, INS.NOMEINSTANCIA, INS.DESCRINSTANCIA, INS.NOMETAB
        FROM TDDINS INS
        WHERE INS.NOMETAB IN ({TABELAS_ALVO})
        ORDER BY INS.NOMETAB
    """,

    "opcoes": f"""
        SELECT CAM.NOMETAB, CAM.NOMECAMPO, CAM.DESCRCAMPO, OPC.VALOR, OPC.OPCAO
        FROM TDDOPC OPC
        JOIN TDDCAM CAM ON OPC.NUCAMPO = CAM.NUCAMPO
        WHERE CAM.NOMETAB IN ({TABELAS_ALVO})
        ORDER BY CAM.NOMETAB, CAM.NOMECAMPO, OPC.VALOR
    """,

    "relacionamentos": f"""
        SELECT
            ORIG.NOMEINSTANCIA AS ORIG_INST,
            ORIG.NOMETAB AS TAB_ORIGEM,
            DEST.NOMEINSTANCIA AS DEST_INST,
            DEST.NOMETAB AS TAB_DESTINO,
            LIG.TIPLIGACAO
        FROM TDDLIG LIG
        JOIN TDDINS ORIG ON LIG.NUINSTORIG = ORIG.NUINSTANCIA
        JOIN TDDINS DEST ON LIG.NUINSTDEST = DEST.NUINSTANCIA
        WHERE ORIG.NOMETAB IN ({TABELAS_ALVO})
           OR DEST.NOMETAB IN ({TABELAS_ALVO})
        ORDER BY ORIG.NOMETAB
    """,
}

# Tabelas para extrair campos
TABELAS_CAMPOS = [
    "TGFCAB", "TGFITE", "TGFPAR", "TGFPRO", "TGFTOP",
    "TGFVEN", "TSIEMP", "TGFEST", "TGFFIN", "TGFCOT",
    "TGFPAG", "AD_TGFCUSMMA", "AD_TGFPROAUXMMA",
]


async def main():
    executor = SafeQueryExecutor()
    output_dir = PROJECT_ROOT / "data" / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)

    all_results = {}

    # Executar queries principais
    for nome, sql in QUERIES.items():
        print(f"[*] Extraindo {nome}...")
        try:
            result = await executor.execute(sql.strip())
            if result.get("success"):
                rows = result.get("data", [])
                print(f"    [OK] {len(rows)} registros")
                all_results[nome] = rows
            else:
                print(f"    [!] Erro: {result.get('error', 'desconhecido')}")
                all_results[nome] = {"error": result.get("error")}
        except Exception as e:
            print(f"    [!] Excecao: {e}")
            all_results[nome] = {"error": str(e)}

    # Extrair campos de cada tabela
    campos_por_tabela = {}
    for tabela in TABELAS_CAMPOS:
        print(f"[*] Extraindo campos de {tabela}...")
        sql = f"""
            SELECT CAM.NOMECAMPO, CAM.DESCRCAMPO, CAM.TIPCAMPO, CAM.TAMANHO
            FROM TDDCAM CAM
            WHERE CAM.NOMETAB = '{tabela}'
            ORDER BY CAM.NOMECAMPO
        """
        try:
            result = await executor.execute(sql.strip())
            if result.get("success"):
                rows = result.get("data", [])
                print(f"    [OK] {len(rows)} campos")
                campos_por_tabela[tabela] = rows
            else:
                print(f"    [!] Erro: {result.get('error', 'desconhecido')}")
                campos_por_tabela[tabela] = {"error": result.get("error")}
        except Exception as e:
            print(f"    [!] Excecao: {e}")
            campos_por_tabela[tabela] = {"error": str(e)}

    all_results["campos"] = campos_por_tabela

    # Salvar resultado
    output_file = output_dir / "data_dictionary.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    # Resumo
    total_campos = sum(
        len(v) for v in campos_por_tabela.values()
        if isinstance(v, list)
    )
    total_opcoes = len(all_results.get("opcoes", []))
    total_rels = len(all_results.get("relacionamentos", []))

    print(f"\n{'='*50}")
    print(f"[OK] Dicionario salvo em {output_file}")
    print(f"[i] Tabelas com campos: {len([t for t, v in campos_por_tabela.items() if isinstance(v, list)])}")
    print(f"[i] Total de campos: {total_campos}")
    print(f"[i] Opcoes de dominio: {total_opcoes}")
    print(f"[i] Relacionamentos: {total_rels}")

    return all_results


if __name__ == "__main__":
    asyncio.run(main())
