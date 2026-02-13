"""
MMarra Data Hub - Result Validator (Auto-Auditoria)

Valida automaticamente se a resposta do Smart Agent esta correta.
Roda 6 checks independentes sobre cada interacao e retorna severity + fix sugerido.

Usado por:
- smart_agent.py (validacao em tempo real, antes de retornar)
- review_session.py (auditoria batch em historico)
"""

import re
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).parent.parent.parent
KNOWLEDGE_PATH = PROJECT_ROOT / "knowledge"


class ResultValidator:
    """Valida automaticamente se a resposta do Smart Agent esta correta."""

    def __init__(self, knowledge_path: Path = None):
        self._kp = knowledge_path or KNOWLEDGE_PATH

    def validate(self, log_entry: dict, result_data: list = None) -> dict:
        """
        Valida um registro do query_log + dados completos do resultado.

        Args:
            log_entry: registro do query_log.jsonl (ou dict em memoria)
            result_data: lista de dicts com TODOS os registros retornados
                         (antes de aplicar filtros/top). Pode ser None se
                         validando a partir do log (usa result_data_summary).
        """
        checks = []

        checks.append(self._check_sort_correct(log_entry, result_data))
        checks.append(self._check_entity_in_results(log_entry, result_data))
        checks.append(self._check_not_empty_unexpected(log_entry, result_data))
        checks.append(self._check_key_fields_not_null(log_entry, result_data))
        checks.append(self._check_plausible_values(log_entry, result_data))
        checks.append(self._check_groq_correction_pattern(log_entry))

        checks = [c for c in checks if c is not None]
        failed = [c for c in checks if not c.get("passed")]

        return {
            "passed": len(failed) == 0,
            "checks_run": len(checks),
            "checks_failed": len(failed),
            "checks": checks,
            "severity": self._calc_severity(failed),
            "suggested_fix": self._generate_fix(failed) if failed else None,
        }

    # ================================================================
    # CHECK 1: Sort correto
    # ================================================================

    def _check_sort_correct(self, log_entry: dict, result_data: list = None) -> dict | None:
        """Verifica se o sort retornou o resultado correto."""
        proc = log_entry.get("processing") or {}
        filters = proc.get("filters_applied") or {}
        sort_key = str(filters.get("_sort", ""))
        if not sort_key:
            return None

        field = sort_key.replace("_DESC", "").replace("_ASC", "")
        is_desc = "DESC" in sort_key

        # Fonte de dados: result_data em memoria OU summary do log
        summary = log_entry.get("result_data_summary") or {}

        if result_data:
            values = [r.get(field, "") for r in result_data if isinstance(r, dict) and r.get(field)]
            if not values:
                return None
            sorted_values = _smart_sort(values, descending=is_desc)
            # Pegar o valor mostrado (primeiro do resultado filtrado)
            shown = log_entry.get("result_data_summary", {}).get("shown_record", {})
            shown_value = shown.get(field, "") if shown else ""
            if not shown_value and result_data:
                shown_value = str(result_data[0].get(field, ""))
            expected_value = str(sorted_values[0]) if sorted_values else ""
        elif summary.get("sort_field_top5"):
            # Validar a partir do summary salvo no log
            top5 = summary["sort_field_top5"]
            shown = summary.get("shown_record") or {}
            shown_value = str(shown.get(field, ""))
            expected_value = str(top5[0]) if top5 else ""
            sorted_values = top5
        else:
            return None

        if not shown_value or not expected_value:
            return None

        passed = _normalize_compare(shown_value) == _normalize_compare(expected_value)

        return {
            "check": "sort_correct",
            "passed": passed,
            "detail": (
                f"Sort {sort_key}: OK ({shown_value})" if passed
                else f"Sort {sort_key}: mostrou '{shown_value}', esperado '{expected_value}'"
            ),
            "field": field,
            "shown": shown_value,
            "expected": expected_value,
            "all_top5": [str(v) for v in sorted_values[:5]] if sorted_values else [],
        }

    # ================================================================
    # CHECK 2: Entidade presente nos resultados
    # ================================================================

    def _check_entity_in_results(self, log_entry: dict, result_data: list = None) -> dict | None:
        """Verifica se a entidade filtrada aparece nos resultados."""
        proc = log_entry.get("processing") or {}
        entities = proc.get("entities") or {}
        marca = entities.get("marca")
        if not marca:
            return None

        summary = log_entry.get("result_data_summary") or {}

        if result_data:
            found = any(
                str(r.get("MARCA", "")).upper() == marca.upper()
                for r in result_data if isinstance(r, dict)
            )
            total = len(result_data)
        elif summary.get("entity_values_unique"):
            found = marca.upper() in [v.upper() for v in summary["entity_values_unique"]]
            total = summary.get("total_records", 0)
        else:
            return None

        return {
            "check": "entity_in_results",
            "passed": found,
            "detail": (
                f"Marca '{marca}' encontrada nos resultados ({total} registros)" if found
                else f"Marca '{marca}' NAO encontrada nos {total} resultados"
            ),
        }

    # ================================================================
    # CHECK 3: Zero resultados inesperado
    # ================================================================

    def _check_not_empty_unexpected(self, log_entry: dict, result_data: list = None) -> dict | None:
        """Se tinha entidade mas retornou 0 registros, algo pode estar errado."""
        proc = log_entry.get("processing") or {}
        entities = proc.get("entities") or {}
        intent = proc.get("intent", "")
        result = log_entry.get("result") or {}

        if intent not in ("pendencia_compras", "estoque", "vendas"):
            return None

        has_entity = entities.get("marca") or entities.get("fornecedor") or entities.get("comprador")
        if not has_entity:
            return None

        records = result.get("records_found", 0)
        if records is None:
            records = 0

        if records > 0:
            return {"check": "not_empty_unexpected", "passed": True, "detail": f"{records} registros encontrados"}

        entity_name = entities.get("marca") or entities.get("fornecedor") or entities.get("comprador") or "?"
        return {
            "check": "not_empty_unexpected",
            "passed": False,
            "detail": f"0 registros para entidade '{entity_name}' (intent={intent}) - pode ser nome errado ou sem dados",
        }

    # ================================================================
    # CHECK 4: Campos-chave nao nulos
    # ================================================================

    def _check_key_fields_not_null(self, log_entry: dict, result_data: list = None) -> dict | None:
        """Se usou sort/filter num campo, o resultado mostrado deve ter esse campo preenchido."""
        proc = log_entry.get("processing") or {}
        filters = proc.get("filters_applied") or {}
        sort_key = str(filters.get("_sort", ""))
        if not sort_key:
            return None

        field = sort_key.replace("_DESC", "").replace("_ASC", "")

        summary = log_entry.get("result_data_summary") or {}
        shown = summary.get("shown_record") or {}

        if result_data and len(result_data) > 0:
            shown_value = result_data[0].get(field, "")
        elif shown:
            shown_value = shown.get(field, "")
        else:
            return None

        passed = bool(shown_value) and str(shown_value).strip() not in ("", "None", "null")

        return {
            "check": "key_fields_not_null",
            "passed": passed,
            "detail": (
                f"Campo '{field}' preenchido no resultado mostrado" if passed
                else f"Campo '{field}' VAZIO no resultado mostrado (sort por este campo)"
            ),
            "field": field,
            "value": str(shown_value) if shown_value else None,
        }

    # ================================================================
    # CHECK 5: Valores plausiveis
    # ================================================================

    def _check_plausible_values(self, log_entry: dict, result_data: list = None) -> dict | None:
        """Detecta valores absurdos nos resultados."""
        if not result_data:
            return None

        issues = []
        for i, r in enumerate(result_data[:50]):  # checar ate 50 registros
            if not isinstance(r, dict):
                continue

            # VLR_PENDENTE negativo
            vlr = r.get("VLR_PENDENTE")
            if vlr is not None:
                try:
                    v = float(vlr)
                    if v < 0:
                        issues.append(f"VLR_PENDENTE negativo ({v}) no registro {i}")
                    elif v > 50_000_000:
                        issues.append(f"VLR_PENDENTE absurdo ({v}) no registro {i}")
                except (ValueError, TypeError):
                    pass

            # QTD_PENDENTE > 100000
            qtd = r.get("QTD_PENDENTE")
            if qtd is not None:
                try:
                    q = int(float(str(qtd)))
                    if q > 100_000:
                        issues.append(f"QTD_PENDENTE absurdo ({q}) no registro {i}")
                except (ValueError, TypeError):
                    pass

            # Datas fora de range
            for date_field in ("DT_PEDIDO", "PREVISAO_ENTREGA"):
                dt_val = r.get(date_field, "")
                if dt_val and isinstance(dt_val, str):
                    parsed = _parse_date_br(dt_val)
                    if parsed:
                        year = parsed.year
                        if year < 2020 or year > 2030:
                            issues.append(f"{date_field}={dt_val} fora de range no registro {i}")

        if not issues:
            return {"check": "plausible_values", "passed": True, "detail": "Valores dentro do esperado"}

        return {
            "check": "plausible_values",
            "passed": False,
            "detail": f"{len(issues)} valor(es) suspeito(s): {'; '.join(issues[:3])}",
            "issues": issues[:10],
        }

    # ================================================================
    # CHECK 6: Padrao de correcao do Groq
    # ================================================================

    def _check_groq_correction_pattern(self, log_entry: dict) -> dict | None:
        """Registra se o pos-processamento corrigiu o Groq."""
        proc = log_entry.get("processing") or {}
        if not proc.get("groq_corrected"):
            return None

        groq_raw = proc.get("groq_raw") or {}
        ordenar_raw = groq_raw.get("ordenar", "")

        detail = "Groq corrigido pelo pos-processamento"
        if ordenar_raw and "DT_PEDIDO" in str(ordenar_raw):
            detail = f"Groq retornou '{ordenar_raw}' mas foi corrigido (provavelmente para PREVISAO_ENTREGA)"

        return {
            "check": "groq_correction_pattern",
            "passed": False,  # Correcao = sinal de que o prompt precisa melhorar
            "detail": detail,
            "severity_override": "low",
        }

    # ================================================================
    # SEVERITY & FIX
    # ================================================================

    def _calc_severity(self, failed: list) -> str | None:
        if not failed:
            return None

        severities = []
        for check in failed:
            name = check.get("check", "")
            override = check.get("severity_override")
            if override:
                severities.append(override)
            elif name in ("sort_correct", "entity_in_results"):
                severities.append("high")
            elif name in ("not_empty_unexpected", "key_fields_not_null"):
                severities.append("medium")
            elif name in ("plausible_values",):
                severities.append("high")
            else:
                severities.append("low")

        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        return "low"

    def _generate_fix(self, failed: list) -> str | None:
        if not failed:
            return None

        fixes = []
        for check in failed:
            name = check.get("check", "")
            if name == "sort_correct":
                fixes.append(f"Verificar _smart_sort em apply_filters() para campo {check.get('field', '?')}")
            elif name == "entity_in_results":
                fixes.append("Verificar SQL WHERE clause - filtro de marca pode nao estar sendo aplicado")
            elif name == "not_empty_unexpected":
                fixes.append("Verificar se o nome da entidade esta correto no banco (maiusculas, abreviacoes)")
            elif name == "key_fields_not_null":
                fixes.append(f"Campo '{check.get('field', '?')}' vazio no top result - considerar filtrar registros sem este campo")
            elif name == "plausible_values":
                fixes.append("Verificar dados retornados pela query SQL - valores fora do range esperado")
            elif name == "groq_correction_pattern":
                fixes.append("Adicionar mais exemplos no LLM_CLASSIFIER_PROMPT para evitar confusao de campos")

        return "; ".join(fixes) if fixes else None


# ================================================================
# HELPERS
# ================================================================

def _parse_date_br(val: str) -> datetime | None:
    """Tenta converter dd/mm/yyyy para datetime."""
    if not val or not isinstance(val, str):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(val.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def _smart_sort(values: list, descending: bool = True) -> list:
    """Ordena valores de forma inteligente (numeros, datas BR, strings)."""
    if not values:
        return values

    # Filtrar vazios
    non_empty = [v for v in values if v and str(v).strip() not in ("", "None", "null")]
    if not non_empty:
        return []

    # Tentar como numeros
    try:
        numeric = [(float(str(v).replace(",", ".")), v) for v in non_empty]
        numeric.sort(key=lambda x: x[0], reverse=descending)
        return [v for _, v in numeric]
    except (ValueError, TypeError):
        pass

    # Tentar como datas BR (dd/mm/yyyy)
    parsed = []
    for v in non_empty:
        dt = _parse_date_br(str(v))
        if dt:
            parsed.append((dt, v))

    if len(parsed) == len(non_empty):
        parsed.sort(key=lambda x: x[0], reverse=descending)
        return [v for _, v in parsed]

    # Fallback: string sort
    non_empty.sort(reverse=descending)
    return non_empty


def _normalize_compare(val: str) -> str:
    """Normaliza valor para comparacao (remove espacos, converte data)."""
    val = str(val).strip()
    dt = _parse_date_br(val)
    if dt:
        return dt.strftime("%Y-%m-%d")
    try:
        return str(float(val.replace(",", ".")))
    except (ValueError, TypeError):
        return val.upper()


def build_result_data_summary(result_data: list, log_entry: dict) -> dict:
    """Constroi o summary dos dados para salvar no log (compacto)."""
    if not result_data:
        return {}

    proc = log_entry.get("processing") or {}
    filters = proc.get("filters_applied") or {}
    entities = proc.get("entities") or {}

    sort_key = str(filters.get("_sort", ""))
    sort_field = sort_key.replace("_DESC", "").replace("_ASC", "") if sort_key else ""
    is_desc = "DESC" in sort_key if sort_key else True

    summary = {
        "total_records": len(result_data),
    }

    # Sort field top5/bottom5
    if sort_field:
        values = [r.get(sort_field, "") for r in result_data if isinstance(r, dict) and r.get(sort_field)]
        if values:
            sorted_vals = _smart_sort(values, descending=is_desc)
            sorted_asc = _smart_sort(values, descending=not is_desc)
            summary["sort_field"] = sort_field
            summary["sort_field_top5"] = [str(v) for v in sorted_vals[:5]]
            summary["sort_field_bottom5"] = [str(v) for v in sorted_asc[:5]]

    # Shown record (primeiro da lista filtrada - sera preenchido pelo caller)
    if result_data and isinstance(result_data[0], dict):
        shown = {}
        for key in ("PEDIDO", "FORNECEDOR", "PRODUTO", "MARCA", "VLR_PENDENTE",
                     "QTD_PENDENTE", "DIAS_ABERTO", "STATUS_ENTREGA",
                     "DT_PEDIDO", "PREVISAO_ENTREGA", "CONFIRMADO"):
            if key in result_data[0]:
                shown[key] = str(result_data[0][key]) if result_data[0][key] is not None else ""
        summary["shown_record"] = shown

    # Entity values unique
    marca = entities.get("marca")
    if marca:
        summary["entity_field"] = "MARCA"
        unique = set()
        for r in result_data:
            if isinstance(r, dict) and r.get("MARCA"):
                unique.add(str(r["MARCA"]).upper())
        summary["entity_values_unique"] = sorted(unique)

    # Null counts for key fields
    null_counts = {}
    for field in ("PREVISAO_ENTREGA", "CONFIRMADO", "VLR_PENDENTE", "STATUS_ENTREGA"):
        count = sum(
            1 for r in result_data
            if isinstance(r, dict) and (not r.get(field) or str(r.get(field, "")).strip() in ("", "None"))
        )
        if count > 0:
            null_counts[field] = count
    if null_counts:
        summary["null_counts"] = null_counts

    return summary
