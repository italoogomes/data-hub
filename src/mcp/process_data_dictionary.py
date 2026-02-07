"""
Processa o dicionario de dados extraido e gera/atualiza documentacao.

Uso:
    python -m src.mcp.process_data_dictionary
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Tipo de campo do Sankhya
TIPO_CAMPO = {
    "S": "Texto",
    "I": "Inteiro",
    "F": "Decimal",
    "D": "Data",
    "H": "Data/Hora",
    "B": "Binario",
    "T": "Texto Longo",
}

# Tabelas e suas descricoes curtas
TABELA_DESC = {
    "TGFCAB": "Cabecalho de Notas/Pedidos",
    "TGFITE": "Itens das Notas/Pedidos",
    "TGFPAR": "Parceiros (Clientes/Fornecedores)",
    "TGFPRO": "Produtos",
    "TGFTOP": "Tipos de Operacao (TOPs)",
    "TGFVEN": "Vendedores/Compradores",
    "TSIEMP": "Empresas/Filiais",
    "TGFEST": "Posicao de Estoque",
    "TGFFIN": "Titulos Financeiros",
    "TGFCOT": "Cotacoes de Compra",
    "TGFPAG": "Pagamentos",
    "AD_TGFCUSMMA": "Historico de Custos (MMarra)",
    "AD_TGFPROAUXMMA": "Numeros Auxiliares de Produtos (MMarra)",
}


def load_data():
    data_file = PROJECT_ROOT / "data" / "raw" / "data_dictionary.json"
    with open(data_file, "r", encoding="utf-8") as f:
        return json.load(f)


def process_campos(data):
    """Organiza campos por tabela."""
    campos = {}
    for tabela, rows in data.get("campos", {}).items():
        if isinstance(rows, list):
            campos[tabela] = []
            for row in rows:
                # [NOMECAMPO, DESCRCAMPO, TIPCAMPO, TAMANHO]
                nome = row[0] if len(row) > 0 else ""
                descr = row[1] if len(row) > 1 else ""
                tipo = row[2] if len(row) > 2 else ""
                tam = row[3] if len(row) > 3 else ""
                campos[tabela].append({
                    "nome": nome,
                    "descricao": descr or "",
                    "tipo": TIPO_CAMPO.get(tipo, tipo or ""),
                    "tamanho": tam or "",
                })
    return campos


def process_opcoes(data):
    """Organiza opcoes de dominio por tabela.campo."""
    opcoes = defaultdict(lambda: defaultdict(list))
    for row in data.get("opcoes", []):
        # [NOMETAB, NOMECAMPO, DESCRCAMPO, VALOR, OPCAO]
        tab = row[0] if len(row) > 0 else ""
        campo = row[1] if len(row) > 1 else ""
        descr_campo = row[2] if len(row) > 2 else ""
        valor = row[3] if len(row) > 3 else ""
        opcao = row[4] if len(row) > 4 else ""
        opcoes[tab][campo].append({
            "valor": valor,
            "opcao": opcao,
            "descr_campo": descr_campo,
        })
    return opcoes


def process_relacionamentos(data):
    """Organiza relacionamentos por tabela de origem."""
    rels = defaultdict(list)
    for row in data.get("relacionamentos", []):
        # [ORIG_INST, TAB_ORIGEM, DEST_INST, TAB_DESTINO, TIPLIGACAO]
        orig_inst = row[0] if len(row) > 0 else ""
        tab_orig = row[1] if len(row) > 1 else ""
        dest_inst = row[2] if len(row) > 2 else ""
        tab_dest = row[3] if len(row) > 3 else ""
        tipo = row[4] if len(row) > 4 else ""
        rels[tab_orig].append({
            "orig_inst": orig_inst,
            "tab_destino": tab_dest,
            "dest_inst": dest_inst,
            "tipo": tipo,
        })
    return rels


def generate_table_doc(tabela, campos, opcoes, rels):
    """Gera documentacao markdown para uma tabela."""
    desc = TABELA_DESC.get(tabela, tabela)

    lines = [
        f"# {tabela}",
        "",
        f"**Descricao:** {desc}",
        f"**Total de campos no dicionario:** {len(campos)}",
        "",
    ]

    # Campos principais (filtrar os mais relevantes - nao AD_ e nao campos de sistema muito internos)
    lines.append("## Campos Principais")
    lines.append("")
    lines.append("| Campo | Tipo | Descricao |")
    lines.append("|-------|------|-----------|")

    # Separar campos normais e AD_
    campos_normais = [c for c in campos if not c["nome"].startswith("AD_")]
    campos_ad = [c for c in campos if c["nome"].startswith("AD_")]

    for c in campos_normais:
        tipo_str = c["tipo"]
        if c["tamanho"]:
            tipo_str += f"({c['tamanho']})"
        descr = c["descricao"].replace("|", "/").replace("\n", " ")
        lines.append(f"| {c['nome']} | {tipo_str} | {descr} |")

    if campos_ad:
        lines.append("")
        lines.append(f"## Campos Customizados (AD_) - {len(campos_ad)} campos")
        lines.append("")
        lines.append("| Campo | Tipo | Descricao |")
        lines.append("|-------|------|-----------|")
        for c in campos_ad:
            tipo_str = c["tipo"]
            if c["tamanho"]:
                tipo_str += f"({c['tamanho']})"
            descr = c["descricao"].replace("|", "/").replace("\n", " ")
            lines.append(f"| {c['nome']} | {tipo_str} | {descr} |")

    # Opcoes de dominio
    tab_opcoes = opcoes.get(tabela, {})
    if tab_opcoes:
        lines.append("")
        lines.append("## Valores de Dominio")
        lines.append("")
        for campo, opts in sorted(tab_opcoes.items()):
            descr_campo = opts[0].get("descr_campo", campo) if opts else campo
            lines.append(f"### {campo} ({descr_campo})")
            lines.append("")
            lines.append("| Valor | Significado |")
            lines.append("|-------|-------------|")
            for o in opts:
                opcao_text = o["opcao"].replace("|", "/").replace("\n", " ")
                lines.append(f"| {o['valor']} | {opcao_text} |")
            lines.append("")

    # Relacionamentos
    tab_rels = rels.get(tabela, [])
    if tab_rels:
        lines.append("")
        lines.append("## Relacionamentos (via TDDLIG)")
        lines.append("")
        # Deduplicar
        seen = set()
        for r in tab_rels:
            key = f"{r['tab_destino']}-{r['dest_inst']}"
            if key not in seen:
                seen.add(key)
                lines.append(f"- {r['orig_inst']} -> {r['dest_inst']} ({r['tab_destino']}) [{r['tipo']}]")

    lines.append("")
    return "\n".join(lines)


def main():
    print("[*] Carregando dicionario...")
    data = load_data()

    campos = process_campos(data)
    opcoes = process_opcoes(data)
    rels = process_relacionamentos(data)

    tabelas_dir = PROJECT_ROOT / "knowledge" / "sankhya" / "tabelas"
    tabelas_dir.mkdir(parents=True, exist_ok=True)

    # Gerar documentacao por tabela
    for tabela in TABELA_DESC:
        if tabela in campos:
            print(f"[*] Gerando {tabela}.md ({len(campos[tabela])} campos)...")
            doc = generate_table_doc(tabela, campos[tabela], opcoes, rels)
            output_file = tabelas_dir / f"{tabela}.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(doc)
            print(f"    [OK] Salvo em {output_file.relative_to(PROJECT_ROOT)}")

    # Gerar resumo das opcoes de dominio para sinonimos
    print("\n[*] Gerando resumo de opcoes de dominio...")
    opcoes_resumo = []
    for tab, campos_opts in sorted(opcoes.items()):
        for campo, opts in sorted(campos_opts.items()):
            for o in opts:
                opcoes_resumo.append(f"{tab}.{campo} = '{o['valor']}' -> {o['opcao']}")

    opcoes_file = PROJECT_ROOT / "data" / "raw" / "opcoes_dominio.txt"
    with open(opcoes_file, "w", encoding="utf-8") as f:
        f.write("\n".join(opcoes_resumo))
    print(f"    [OK] {len(opcoes_resumo)} opcoes salvas em {opcoes_file.relative_to(PROJECT_ROOT)}")

    # Resumo
    print(f"\n{'='*50}")
    print(f"[OK] Documentacao gerada!")
    print(f"[i] Tabelas documentadas: {len([t for t in TABELA_DESC if t in campos])}")
    print(f"[i] Total de opcoes de dominio: {len(opcoes_resumo)}")


if __name__ == "__main__":
    main()
