"""Script para explorar a tabela TGFPAR (parceiros/clientes)."""
import asyncio
import json
from server import sankhya

async def explore():
    results = {}

    # 1. Estrutura
    sql_estrutura = """
        SELECT
            c.COLUMN_NAME as campo,
            c.DATA_TYPE as tipo,
            c.DATA_LENGTH as tamanho,
            c.NULLABLE as permite_nulo,
            NVL(cc.COMMENTS, ' ') as comentario
        FROM USER_TAB_COLUMNS c
        LEFT JOIN USER_COL_COMMENTS cc
            ON c.TABLE_NAME = cc.TABLE_NAME
            AND c.COLUMN_NAME = cc.COLUMN_NAME
        WHERE c.TABLE_NAME = 'TGFPAR'
        ORDER BY c.COLUMN_ID
    """
    results["estrutura"] = await sankhya.execute_query(sql_estrutura)

    # 2. Chaves
    sql_chaves = """
        SELECT
            CASE uc.CONSTRAINT_TYPE
                WHEN 'P' THEN 'PK'
                WHEN 'R' THEN 'FK'
            END as tipo_chave,
            ucc.COLUMN_NAME as campo,
            uc.CONSTRAINT_NAME as nome_constraint,
            r_uc.TABLE_NAME as tabela_ref,
            r_ucc.COLUMN_NAME as campo_ref
        FROM USER_CONSTRAINTS uc
        JOIN USER_CONS_COLUMNS ucc
            ON uc.CONSTRAINT_NAME = ucc.CONSTRAINT_NAME
        LEFT JOIN USER_CONSTRAINTS r_uc
            ON uc.R_CONSTRAINT_NAME = r_uc.CONSTRAINT_NAME
        LEFT JOIN USER_CONS_COLUMNS r_ucc
            ON r_uc.CONSTRAINT_NAME = r_ucc.CONSTRAINT_NAME
        WHERE uc.TABLE_NAME = 'TGFPAR'
            AND uc.CONSTRAINT_TYPE IN ('P', 'R')
        ORDER BY tipo_chave, campo
    """
    results["chaves"] = await sankhya.execute_query(sql_chaves)

    # 3. Domínios
    campos_dominio = ['TIPPESSOA', 'CLIENTE', 'FORNECEDOR', 'VENDEDOR', 'TRANSPORTADORA', 'ATIVO']
    results["dominios"] = {}

    for campo in campos_dominio:
        sql = f"""
            SELECT * FROM (
                SELECT {campo} as valor, COUNT(*) as qtd
                FROM TGFPAR
                WHERE {campo} IS NOT NULL
                GROUP BY {campo}
                ORDER BY qtd DESC
            ) WHERE ROWNUM <= 20
        """
        results["dominios"][campo] = await sankhya.execute_query(sql)

    # 4. Sample
    sql_sample = """
        SELECT CODPARC, NOMEPARC, RAZAOSOCIAL, CGC_CPF, TIPPESSOA, CLIENTE, FORNECEDOR, ATIVO, CODCID, CODVEND
        FROM TGFPAR
        WHERE ROWNUM <= 10
    """
    results["sample"] = await sankhya.execute_query(sql_sample)

    # 5. Contagem
    results["contagem"] = await sankhya.execute_query("SELECT COUNT(*) as total FROM TGFPAR")

    # Salva em JSON
    with open("tgfpar_data.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("Dados salvos em tgfpar_data.json")

if __name__ == "__main__":
    asyncio.run(explore())
