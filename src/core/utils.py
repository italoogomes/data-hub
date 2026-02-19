"""
MMarra Data Hub - Funcoes utilitarias compartilhadas.
Normalizacao de texto, formatacao, seguranca SQL.
"""

import re


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize(text: str) -> str:
    """Remove acentos e normaliza texto para minusculo."""
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u',
        'ç': 'c',
    }
    t = text.lower().strip()
    for old, new in replacements.items():
        t = t.replace(old, new)
    return t


def tokenize(text: str) -> list:
    """Extrai palavras normalizadas (alfanumericas)."""
    return re.findall(r'[a-z0-9]+', normalize(text))


# ============================================================
# FORMATTING (BRL / numeros)
# ============================================================

def fmt_brl(valor) -> str:
    """Formata valor para R$ brasileiro."""
    try:
        v = float(valor or 0)
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"


def fmt_num(valor) -> str:
    """Formata numero inteiro com separador de milhar."""
    try:
        return f"{int(float(valor or 0)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def trunc(text, max_len=40) -> str:
    """Trunca texto para caber em tabelas."""
    if not text:
        return ""
    s = str(text).strip()
    return s[:max_len] + "..." if len(s) > max_len else s


# ============================================================
# SQL SAFETY
# ============================================================

def safe_sql(value: str) -> str:
    """Sanitiza valor para uso em SQL: remove chars perigosos, escapa aspas."""
    if not value:
        return ""
    s = str(value).strip()
    # Remover chars perigosos de SQL injection
    s = re.sub(r'[;\-\-\/\*\\\x00]', '', s)
    # Escapar aspas simples (Oracle-style)
    s = s.replace("'", "''")
    return s


def sanitize_code(code: str) -> str:
    """Remove espacos, tracos e barras para comparacao flexivel de codigos."""
    return re.sub(r'[\s\-/\.]', '', code).upper()
