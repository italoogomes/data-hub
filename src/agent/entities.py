"""
MMarra Data Hub - Extração de Entidades.
Identifica marcas, empresas, compradores, produtos, períodos e cidades nas perguntas.
Extraído de smart_agent.py na refatoração modular.
"""

import re
from src.core.utils import normalize, tokenize


# Mapa de prefixo empresa -> nome legível para exibição
EMPRESA_DISPLAY = {
    "ARACAT": "Aracatuba",
    "RIBEIR": "Ribeirao Preto",
    "UBERL": "Uberlandia",
    "ITUMBI": "Itumbiara",
    "RIO VERDE": "Rio Verde",
    "GOIAN": "Goiania",
    "SAO JOSE": "Sao Jose do Rio Preto",
}

# Cidades -> prefixo padrão de empresa
_CIDADES_EMPRESA = {
    "ARACATUBA": "ARACAT", "ARAÇATUBA": "ARACAT", "ARACAT": "ARACAT",
    "RIBEIRAO PRETO": "RIBEIR", "RIBEIRÃO PRETO": "RIBEIR",
    "RIBEIRAO": "RIBEIR", "RIBEIRÃO": "RIBEIR", "RIBEIR": "RIBEIR",
    "UBERLANDIA": "UBERL", "UBERLÂNDIA": "UBERL", "UBERL": "UBERL",
    "ITUMBIARA": "ITUMBI", "ITUMBI": "ITUMBI",
    "RIO VERDE": "RIO VERDE",
    "GOIANIA": "GOIAN", "GOIÂNIA": "GOIAN", "GOIAN": "GOIAN",
    "SAO JOSE": "SAO JOSE", "SÃO JOSÉ": "SAO JOSE",
}
_CIDADES_SET = {c.split()[0] for c in _CIDADES_EMPRESA.keys()}

# Período nomes para exibição
PERIODO_NOMES = {
    "hoje": "hoje", "ontem": "ontem", "semana": "esta semana",
    "semana_passada": "semana passada", "mes": "este mês",
    "mes_passado": "mês passado", "ano": "este ano",
}


def _resolve_cidade(name):
    """Resolve nome/prefixo para prefixo padrão de empresa."""
    for cidade, prefixo in _CIDADES_EMPRESA.items():
        if cidade in name or name in cidade:
            return prefixo
    return name


def extract_entities(question: str, known_marcas: set = None,
                     known_empresas: set = None, known_compradores: set = None) -> dict:
    """Extrai entidades da pergunta usando matching com banco.

    Entidades extraídas: marca, fornecedor, empresa, comprador, codprod,
    codigo_fabricante, produto_nome, aplicacao, periodo, nunota.
    """
    params = {}
    q_upper = question.upper().strip()
    q_norm = normalize(question)
    tokens = tokenize(question)

    # ---- VENDEDOR ----
    # "vendedor X", "do vendedor X", "da vendedora X"
    m_vend = re.search(
        r'(?:DO\s+|DA\s+)?VENDEDOR[A]?\s+([A-ZÀ-Ú][A-ZÀ-Ú\s]{2,40}?)(?:\s*[?,!.]|\s+(?:QUE|TEM|TEMOS|NO|NA|DO|DA|EM|ESTE|ESSE|DESTE|DESSE|NESTE|NESSE)|\s*$)',
        q_upper
    )
    if m_vend:
        candidate_vend = m_vend.group(1).strip()
        # Limpar palavras de período que podem grudar no final
        candidate_vend = re.sub(r'\s+(?:HOJE|ONTEM|MES|SEMANA|ANO|PERIODO)$', '', candidate_vend).strip()
        if candidate_vend and len(candidate_vend) >= 2:
            params["vendedor"] = candidate_vend

    # ---- MARCA ----
    # Estratégia 1: "marca X" ou "da X"
    m = re.search(r'(?:MARCA\s+)([A-Z][A-Z0-9\s\.\-&]{1,35}?)(?:\s*[?,!.]|\s+(?:QUE|TEM|TEMOS|EU|TENHO)|\s*$)', q_upper)
    if m:
        params["marca"] = m.group(1).strip()

    if "marca" not in params:
        stop_after = r'(?:\s+(?:QUE|TEM|TEMOS|COM|SEM|ESTA|ESTAO|FOI|NAO|PARA|POR|EM|NO|NA|NOS|COMO|ONDE|QUAL|QUAIS|ENTRE|ACIMA|ABAIXO)|\s*[?,!.]|\s*$)'
        m = re.search(r'\b(?:DA|DE|DO|PELA|PELO|PELAS|PELOS)\s+([A-Z][A-Z0-9\s\.\-&]{1,30}?)' + stop_after, q_upper)
        if m:
            candidate = m.group(1).strip()
            noise = {"COMPRA", "COMPRAS", "VENDA", "VENDAS", "EMPRESA", "FORNECEDOR",
                     "MARCA", "PRODUTO", "PRODUTOS", "ESTOQUE", "PEDIDO", "PEDIDOS", "MES",
                     "SEMANA", "ANO", "HOJE", "ONTEM", "PERIODO", "SISTEMA",
                     "TODAS", "TODOS", "TUDO", "GERAL", "MINHA", "MINHAS",
                     "ENTREGA", "PREVISAO", "DATA", "CONFIRMACAO", "COMPRADOR",
                     "VALOR", "QUANTIDADE", "STATUS", "PRAZO", "ATRASO",
                     "ESTA", "ESTAO", "ESSE", "ESSA", "ISSO", "AQUI", "ONDE",
                     "QUEM", "RESPONSAVEL", "FORNECEDORES", "COMPRADORES",
                     "VENDEDOR", "VENDEDORA", "VENDEDORES",
                     "CASADA", "CASADAS", "CASADO", "CASADOS", "EMPENHO",
                     "FUTURA", "REPOSICAO",
                     "FILIAL", "UNIDADE", "LOJA",
                     "FILTRO", "FILTROS", "CORREIA", "CORREIAS", "DISCO", "DISCOS",
                     "PASTILHA", "PASTILHAS", "ABRACADEIRA", "ROLAMENTO",
                     "PECA", "PECAS", "AR", "OLEO", "COMBUSTIVEL", "CABINE",
                     "CADASTRADO", "CADASTRADA", "CADASTRADOS", "CADASTRADAS",
                     "CODIGO", "REFERENCIA", "COMISSAO", "COMISSOES"}
            first_word = candidate.split()[0] if candidate else ""
            if first_word in noise:
                last_da = re.search(r'.*\b(?:DA|DO)\s+([A-Z][A-Z0-9\s\.\-&]{1,30}?)' + stop_after, q_upper)
                if last_da:
                    candidate = last_da.group(1).strip()
                    first_word = candidate.split()[0] if candidate else ""
            if candidate not in noise and first_word not in noise and len(candidate) > 1:
                params["marca"] = candidate

    # Estratégia 2: Matching com marcas do banco
    if "marca" not in params and known_marcas:
        stop_words = {"DOS", "DAS", "DEL", "UMA", "UNS", "COM", "POR", "QUE",
                       "NAO", "SIM", "MAS", "SEM", "SOB", "TEM", "SAO", "ERA",
                       "FOI", "SER", "TER", "VER", "DAR", "FAZ", "DIZ",
                       "MEU", "SEU", "TEU", "NOS", "VOS", "ELA", "ELE",
                       "PARA", "MAIS", "COMO", "ESSE", "ESSA", "ESTE", "ESTA",
                       "AQUI", "ONDE", "QUAL", "QUEM", "AGORA", "ALEM",
                       "ITENS", "ITEM", "CADA", "DOIS", "TRES", "QUATRO",
                       "PRECISO", "QUERO", "GERAR", "GERA", "TOTAL"}
        for i, token in enumerate(tokens):
            t_upper = token.upper()
            if len(t_upper) < 3 or t_upper in stop_words:
                continue
            if t_upper in known_marcas:
                params["marca"] = t_upper
                break
            for m in known_marcas:
                if t_upper in m and len(t_upper) >= 4:
                    params["marca"] = m
                    break
                if m in q_upper and len(m) >= 4:
                    params["marca"] = m
                    break
            if "marca" in params:
                break

    # ---- FORNECEDOR ----
    m = re.search(r'FORNECEDOR\s+([A-Z][A-Z\s\.\-&]{2,40}?)(?:\s*[?,!.]|\s*$)', q_upper)
    if m:
        candidate_forn = m.group(1).strip()
        if not re.match(r'^D[AEOI]\s', candidate_forn):
            params["fornecedor"] = candidate_forn

    # ---- EMPRESA ----
    q_upper_norm = normalize(question).upper()

    # 1. Prefixo explícito
    m = re.search(r'(?:EMPRESA|FILIAL|UNIDADE|LOJA)\s+(?:DE\s+|DA\s+|DO\s+)?([A-Z][A-ZÀ-Ú\s\-]{2,30}?)(?:\s*[?,!.]|\s*$)', q_upper)
    if m:
        params["empresa"] = _resolve_cidade(m.group(1).strip())

    # 2. Preposição + cidade
    if "empresa" not in params:
        m_prep = re.search(r'\b(?:POR|EM|PARA|PRA)\s+([A-Z][A-ZÀ-Ú\s]{2,25})', q_upper)
        if m_prep:
            candidate_city = m_prep.group(1).strip()
            resolved = _resolve_cidade(candidate_city)
            if resolved != candidate_city:
                params["empresa"] = resolved

    # 3. Cidade solta no texto
    if "empresa" not in params:
        for cidade, prefixo in _CIDADES_EMPRESA.items():
            if cidade in q_upper or cidade in q_upper_norm:
                params["empresa"] = prefixo
                break

    # 4. Match com empresas do banco
    if "empresa" not in params and known_empresas:
        m_prep2 = re.search(r'\b(?:POR|EM|PARA|PRA)\s+([A-Z][A-Z\s\-]{2,30})', q_upper)
        if m_prep2:
            candidate_emp = m_prep2.group(1).strip()
            for emp in known_empresas:
                if candidate_emp in emp or emp in candidate_emp:
                    params["empresa"] = emp
                    break
        if "empresa" not in params:
            for emp in known_empresas:
                if emp in q_upper and len(emp) >= 3:
                    params["empresa"] = emp
                    break

    # Limpar marca se pegou cidade por engano
    if params.get("marca") and params.get("empresa"):
        marca = params["marca"]
        for cidade_word in _CIDADES_SET:
            if marca.endswith(" " + cidade_word) or marca.endswith(" " + cidade_word + " PRETO"):
                params["marca"] = marca[:marca.rfind(" " + cidade_word)].strip()
                break

    # Limpar marca se pegou vendedor por engano
    # Ex: "DO VENDEDOR ROGERIO FERNANDES" → marca="VENDEDOR ROGERIO FERNANDES"
    if params.get("marca"):
        marca_up = params["marca"]
        # Se marca começa com "VENDEDOR", extrair como vendedor e limpar marca
        m_vend_in_marca = re.match(r'^VENDEDOR[A]?\s+(.+)', marca_up)
        if m_vend_in_marca:
            if "vendedor" not in params:
                params["vendedor"] = m_vend_in_marca.group(1).strip()
            del params["marca"]
        # Se vendedor já extraído e marca é igual ou contém o nome do vendedor → duplicata
        # Ex: "agora do rafael candido" → vendedor=RAFAEL CANDIDO + marca=RAFAEL CANDIDO
        elif params.get("vendedor") and (
            marca_up == params["vendedor"]
            or params["vendedor"] in marca_up
            or marca_up in params["vendedor"]
        ):
            del params["marca"]

    # Limpar marca vazia
    if params.get("marca") and not params["marca"].strip():
        del params["marca"]

    # ---- COMPRADOR ----
    m = re.search(r'COMPRADOR[A]?\s+([A-Z][A-Z\s]{2,25}?)(?:\s*[?,!.]|\s*$)', q_upper)
    if m:
        candidate_comp = m.group(1).strip()
        if not re.match(r'^D[AEOI]\s', candidate_comp):
            params["comprador"] = candidate_comp

    if "comprador" not in params and known_compradores:
        for comp in known_compradores:
            if comp in q_upper and len(comp) >= 3:
                params["comprador"] = comp
                break

    # ---- NUMERO PEDIDO ----
    m = re.search(r'(?:PEDIDO|NOTA|NUNOTA)\s*(?:N(?:UMERO)?\.?)?\s*(\d{4,10})', q_upper)
    if m:
        params["nunota"] = int(m.group(1))

    # ---- CODIGO PRODUTO ----
    m = re.search(r'(?:CODIGO|COD|CODPROD|PRODUTO)\s*(\d{3,8})', q_upper)
    if m:
        params["codprod"] = int(m.group(1))

    # ---- CODIGO FABRICANTE (alfanumerico) ----
    if "codprod" not in params:
        m = re.search(r'(?:REFERENCIA|FABRICANTE|NUM(?:ERO)?\s*(?:DO\s+)?FAB(?:RICANTE)?|COD(?:IGO)?\s*FAB(?:RICANTE)?|ORIGINAL)\s+([A-Z0-9][A-Z0-9\s\-/\.]{2,30})', q_upper)
        if m:
            params["codigo_fabricante"] = m.group(1).strip()
        if "codigo_fabricante" not in params:
            m = re.search(r'\b([A-Z]{1,5}\d{2,}[A-Z0-9/\-\.]*)\\b', q_upper)
            if m:
                candidate_fab = m.group(1).strip()
                if len(candidate_fab) >= 4 and not (known_marcas and candidate_fab in known_marcas):
                    params["codigo_fabricante"] = candidate_fab
        if "codigo_fabricante" not in params:
            m = re.search(r'\b(\d{7,15}[A-Z]?)\b', q_upper)
            if m:
                params["codigo_fabricante"] = m.group(1)

    # ---- NOME PRODUTO ----
    m = re.search(r'(?:PRODUTO|PECA|ITEM)\s+([A-Z][A-Z0-9\s\-/]{3,40}?)(?:\s*[?,!.]|\s*$)', q_upper)
    if m and "codprod" not in params and "codigo_fabricante" not in params:
        candidate = m.group(1).strip()
        noise_prod = {"TEM", "TEMOS", "NO", "ESTOQUE", "PENDENTE", "EM", "ABERTO", "SIMILAR", "SIMILARES", "EQUIVALENTE"}
        if candidate not in noise_prod:
            params["produto_nome"] = candidate

    # ---- APLICACAO / VEICULO ----
    if "codprod" not in params and "codigo_fabricante" not in params:
        aplic_match = re.search(
            r'(?:SERVE|APLICA|COMPATIVEL|ENCAIXA|CABE)\s+(?:NO|NA|NOS|NAS|PRA|PARA|COM|EM)\s+([A-Z][A-Z0-9\s\-/]{2,30})',
            q_upper
        )
        if not aplic_match:
            aplic_match = re.search(
                r'(?:PECAS?|PRODUTOS?|FILTROS?)\s+(?:DO|DA|PRO|PRA|PARA|P/)\s+([A-Z][A-Z0-9\s\-/]{2,30})',
                q_upper
            )
        if not aplic_match:
            aplic_match = re.search(
                r'(?:MOTOR|VEICULO|CAMINHAO|ONIBUS|CARRO|MAQUINA)\s+([A-Z][A-Z0-9\s\-/]{2,30})',
                q_upper
            )
        if aplic_match:
            candidate_aplic = aplic_match.group(1).strip()
            noise_aplic = {"ESTOQUE", "PENDENTE", "PENDENCIA", "COMPRA", "COMPRAS",
                           "VENDA", "VENDAS", "MARCA", "EMPRESA", "PRODUTO", "PRODUTOS"}
            first_w = candidate_aplic.split()[0] if candidate_aplic else ""
            if first_w not in noise_aplic and candidate_aplic not in noise_aplic:
                params["aplicacao"] = candidate_aplic

    # ---- PERIODO ----
    # ORDEM: mais específicos primeiro (passado/anterior ANTES dos genéricos)
    q_lower = question.lower()
    if "hoje" in q_lower:
        params["periodo"] = "hoje"
    elif "ontem" in q_lower:
        params["periodo"] = "ontem"
    elif re.search(r'semana\s+(passada|anterior)', q_norm):
        params["periodo"] = "semana_passada"
    elif re.search(r'mes\s+(passado|anterior)', q_norm):
        params["periodo"] = "mes_passado"
    elif re.search(r'(essa|esta|nessa|nesta|da|na)\s+semana', q_norm):
        params["periodo"] = "semana"
    elif re.search(r'(esse|este|nesse|neste|do|no|desse|deste)\s+mes', q_norm):
        params["periodo"] = "mes"
    elif re.search(r'mes\s+atual', q_norm):
        params["periodo"] = "mes"
    elif re.search(r'(esse|este|nesse|neste|do|no|desse|deste)\s+ano', q_norm):
        params["periodo"] = "ano"
    elif re.search(r'ano\s+atual', q_norm):
        params["periodo"] = "ano"

    return params
