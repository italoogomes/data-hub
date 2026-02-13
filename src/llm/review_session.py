"""
MMarra Data Hub - Review Session (Auditoria de Queries)

CLI que analisa o query_log.jsonl, roda validacao offline e gera:
- Relatorio markdown (data/review_YYYYMMDD_HHMM.md)
- Fixes JSON (data/fixes_YYYYMMDD_HHMM.json)
- Resumo no console

Uso:
    python -m src.llm.review_session                # analisa ultimas 24h
    python -m src.llm.review_session --days 7       # ultimos 7 dias
    python -m src.llm.review_session --auto-fix     # aplica correcoes automaticas
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_FILE = DATA_DIR / "query_log.jsonl"

from src.llm.result_validator import ResultValidator


def load_entries(log_file: Path, days: int = 1) -> list:
    """Carrega entradas do JSONL dos ultimos N dias."""
    entries = []
    if not log_file.exists():
        print(f"[REVIEW] Arquivo nao encontrado: {log_file}")
        return entries

    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")

    with open(log_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                if ts >= cutoff:
                    entries.append(entry)
            except json.JSONDecodeError:
                print(f"[REVIEW] Linha {line_num} invalida, pulando")
                continue

    return entries


def run_review(entries: list, validator: ResultValidator) -> dict:
    """Roda validacao em todas as entradas e retorna estatisticas."""
    stats = {
        "total": len(entries),
        "validated": 0,
        "passed": 0,
        "failed": 0,
        "by_severity": Counter(),
        "by_check": Counter(),
        "by_intent": Counter(),
        "by_layer": Counter(),
        "feedback_positive": 0,
        "feedback_negative": 0,
        "feedback_none": 0,
        "problems": [],          # entries com falha
        "groq_corrections": 0,
        "zero_results": 0,
    }

    for entry in entries:
        proc = entry.get("processing") or {}
        intent = proc.get("intent") or "unknown"
        layer = proc.get("layer") or "unknown"
        stats["by_intent"][intent] += 1
        stats["by_layer"][layer] += 1

        # Feedback
        feedback = entry.get("feedback") or {}
        rating = feedback.get("rating")
        if rating == "positive":
            stats["feedback_positive"] += 1
        elif rating == "negative":
            stats["feedback_negative"] += 1
        else:
            stats["feedback_none"] += 1

        # Zero results
        result = entry.get("result") or {}
        if result.get("records_found", 0) == 0 and intent in ("pendencia_compras", "estoque", "vendas"):
            stats["zero_results"] += 1

        # Groq corrections
        if proc.get("groq_corrected"):
            stats["groq_corrections"] += 1

        # Validacao (usa validation salvo no log OU re-valida)
        existing_validation = entry.get("validation")
        if existing_validation:
            validation = existing_validation
        else:
            # Re-validar offline (sem result_data, usa summary)
            validation = validator.validate(entry, result_data=None)

        stats["validated"] += 1

        if validation.get("passed"):
            stats["passed"] += 1
        else:
            stats["failed"] += 1
            severity = validation.get("severity") or "low"
            stats["by_severity"][severity] += 1

            # Registrar checks que falharam
            for check in validation.get("checks", []):
                if not check.get("passed"):
                    stats["by_check"][check.get("check", "?")] += 1

            stats["problems"].append({
                "id": entry.get("id", "?"),
                "timestamp": entry.get("timestamp", "?"),
                "question": entry.get("question", "?"),
                "intent": intent,
                "layer": layer,
                "severity": severity,
                "checks_failed": [
                    {"check": c.get("check"), "detail": c.get("detail")}
                    for c in validation.get("checks", [])
                    if not c.get("passed")
                ],
                "suggested_fix": validation.get("suggested_fix"),
                "feedback_rating": rating,
            })

    return stats


def generate_markdown(stats: dict, days: int) -> str:
    """Gera relatorio markdown."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = [
        f"# Review Session - {now}",
        f"",
        f"> Periodo: ultimos {days} dia(s) | Total: {stats['total']} queries",
        f"",
        f"---",
        f"",
        f"## Resumo",
        f"",
        f"| Metrica | Valor |",
        f"|---------|-------|",
        f"| Total de queries | {stats['total']} |",
        f"| Validadas | {stats['validated']} |",
        f"| Passaram | {stats['passed']} |",
        f"| Falharam | {stats['failed']} |",
        f"| Taxa de acerto | {_pct(stats['passed'], stats['validated'])} |",
        f"| Feedback positivo | {stats['feedback_positive']} |",
        f"| Feedback negativo | {stats['feedback_negative']} |",
        f"| Sem feedback | {stats['feedback_none']} |",
        f"| Correcoes Groq | {stats['groq_corrections']} |",
        f"| Zero resultados | {stats['zero_results']} |",
        f"",
    ]

    # Severity breakdown
    if stats["by_severity"]:
        lines += [
            f"## Falhas por Severidade",
            f"",
            f"| Severidade | Qtd |",
            f"|------------|-----|",
        ]
        for sev in ("high", "medium", "low"):
            count = stats["by_severity"].get(sev, 0)
            if count:
                emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "")
                lines.append(f"| {emoji} {sev} | {count} |")
        lines.append("")

    # Check failures
    if stats["by_check"]:
        lines += [
            f"## Checks que Falharam",
            f"",
            f"| Check | Qtd |",
            f"|-------|-----|",
        ]
        for check, count in stats["by_check"].most_common():
            lines.append(f"| {check} | {count} |")
        lines.append("")

    # Intent distribution
    if stats["by_intent"]:
        lines += [
            f"## Distribuicao por Intent",
            f"",
            f"| Intent | Qtd |",
            f"|--------|-----|",
        ]
        for intent, count in stats["by_intent"].most_common():
            lines.append(f"| {intent} | {count} |")
        lines.append("")

    # Layer distribution
    if stats["by_layer"]:
        lines += [
            f"## Distribuicao por Layer",
            f"",
            f"| Layer | Qtd |",
            f"|-------|-----|",
        ]
        for layer, count in stats["by_layer"].most_common():
            lines.append(f"| {layer} | {count} |")
        lines.append("")

    # Problems (top 20)
    problems = stats.get("problems", [])
    if problems:
        # Ordenar por severity (high primeiro)
        severity_order = {"high": 0, "medium": 1, "low": 2}
        problems.sort(key=lambda p: severity_order.get(p.get("severity", "low"), 3))

        lines += [
            f"## Problemas Detectados ({len(problems)} total)",
            f"",
        ]
        for i, p in enumerate(problems[:20], 1):
            sev = p.get("severity", "low")
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(sev, "")
            lines += [
                f"### {i}. {emoji} {p.get('question', '?')}",
                f"",
                f"- **ID:** `{p.get('id', '?')}`",
                f"- **Timestamp:** {p.get('timestamp', '?')}",
                f"- **Intent:** {p.get('intent', '?')} | **Layer:** {p.get('layer', '?')}",
                f"- **Severity:** {sev}",
                f"- **Feedback:** {p.get('feedback_rating') or 'nenhum'}",
                f"",
            ]
            for check in p.get("checks_failed", []):
                lines.append(f"  - ❌ **{check.get('check', '?')}**: {check.get('detail', '?')}")
            lines.append("")
            if p.get("suggested_fix"):
                lines.append(f"  - 💡 **Fix:** {p['suggested_fix']}")
                lines.append("")

        if len(problems) > 20:
            lines.append(f"*...e mais {len(problems) - 20} problemas (ver fixes JSON)*")
            lines.append("")

    # Footer
    lines += [
        f"---",
        f"",
        f"*Gerado por review_session.py em {now}*",
    ]

    return "\n".join(lines)


def generate_fixes_json(stats: dict) -> list:
    """Gera lista de fixes para aplicacao automatica."""
    fixes = []
    for p in stats.get("problems", []):
        fix_entry = {
            "id": p.get("id"),
            "question": p.get("question"),
            "intent": p.get("intent"),
            "severity": p.get("severity"),
            "checks_failed": [c.get("check") for c in p.get("checks_failed", [])],
            "suggested_fix": p.get("suggested_fix"),
            "auto_fixable": _is_auto_fixable(p),
            "fix_actions": _generate_fix_actions(p),
        }
        fixes.append(fix_entry)
    return fixes


def _is_auto_fixable(problem: dict) -> bool:
    """Determina se um problema pode ser corrigido automaticamente."""
    checks = [c.get("check") for c in problem.get("checks_failed", [])]
    # Auto-fixable: groq_correction_pattern (melhorar prompt)
    # Auto-fixable: not_empty_unexpected (adicionar sinonimo)
    auto_fixable_checks = {"groq_correction_pattern"}
    return any(c in auto_fixable_checks for c in checks)


def _generate_fix_actions(problem: dict) -> list:
    """Gera acoes de fix especificas para cada problema."""
    actions = []
    for check in problem.get("checks_failed", []):
        name = check.get("check", "")

        if name == "sort_correct":
            actions.append({
                "type": "investigate",
                "target": "smart_agent.py:apply_filters",
                "description": f"Verificar ordenacao para o campo mencionado",
            })

        elif name == "entity_in_results":
            actions.append({
                "type": "investigate",
                "target": "smart_agent.py:extract_entities",
                "description": "Verificar se o filtro de marca esta sendo aplicado na SQL",
            })

        elif name == "not_empty_unexpected":
            actions.append({
                "type": "add_synonym",
                "target": "knowledge/glossario/sinonimos.md",
                "description": f"Verificar se o nome '{problem.get('question', '')}' tem sinonimo nao mapeado",
            })

        elif name == "groq_correction_pattern":
            actions.append({
                "type": "improve_prompt",
                "target": "smart_agent.py:LLM_CLASSIFIER_PROMPT",
                "description": "Adicionar mais exemplos no prompt para evitar confusao de campos",
            })

        elif name == "key_fields_not_null":
            actions.append({
                "type": "investigate",
                "target": "smart_agent.py:sql_pendencia_compras",
                "description": "Verificar se a query SQL retorna o campo necessario preenchido",
            })

        elif name == "plausible_values":
            actions.append({
                "type": "investigate",
                "target": "queries/",
                "description": "Verificar dados retornados pela query - valores suspeitos",
            })

    return actions


def _pct(num: int, total: int) -> str:
    """Calcula porcentagem formatada."""
    if total == 0:
        return "0%"
    return f"{round(num / total * 100, 1)}%"


def print_summary(stats: dict):
    """Imprime resumo colorido no console."""
    total = stats["total"]
    passed = stats["passed"]
    failed = stats["failed"]
    rate = f"{round(passed / stats['validated'] * 100, 1)}%" if stats["validated"] > 0 else "N/A"

    print()
    print("=" * 60)
    print("  REVIEW SESSION - Resumo")
    print("=" * 60)
    print(f"  Total de queries:    {total}")
    print(f"  Passaram validacao:  {passed}")
    print(f"  Falharam:            {failed}")
    print(f"  Taxa de acerto:      {rate}")
    print(f"  Feedback (+/-/0):    {stats['feedback_positive']}/{stats['feedback_negative']}/{stats['feedback_none']}")
    print(f"  Correcoes Groq:      {stats['groq_corrections']}")
    print(f"  Zero resultados:     {stats['zero_results']}")
    print()

    if stats["by_severity"]:
        print("  Falhas por severidade:")
        for sev in ("high", "medium", "low"):
            count = stats["by_severity"].get(sev, 0)
            if count:
                marker = {"high": "!!!", "medium": " ! ", "low": " . "}.get(sev, "   ")
                print(f"    [{marker}] {sev}: {count}")
        print()

    # Top 5 problems
    problems = stats.get("problems", [])
    if problems:
        severity_order = {"high": 0, "medium": 1, "low": 2}
        problems.sort(key=lambda p: severity_order.get(p.get("severity", "low"), 3))
        print(f"  Top problemas ({min(5, len(problems))} de {len(problems)}):")
        for p in problems[:5]:
            sev = p.get("severity", "low")
            marker = {"high": "!!!", "medium": " ! ", "low": " . "}.get(sev, "   ")
            q = p.get("question", "?")[:50]
            checks = ", ".join(c.get("check", "?") for c in p.get("checks_failed", []))
            print(f"    [{marker}] {q} -> {checks}")
        print()

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="MMarra Data Hub - Review Session")
    parser.add_argument("--days", type=int, default=1, help="Analisar ultimos N dias (default: 1)")
    parser.add_argument("--log-file", type=str, default=None, help="Caminho do arquivo de log")
    parser.add_argument("--auto-fix", action="store_true", help="Aplicar correcoes automaticas")
    parser.add_argument("--no-report", action="store_true", help="Nao gerar relatorio markdown")
    args = parser.parse_args()

    log_file = Path(args.log_file) if args.log_file else LOG_FILE

    print(f"[REVIEW] Carregando entradas dos ultimos {args.days} dia(s)...")
    entries = load_entries(log_file, days=args.days)

    if not entries:
        print("[REVIEW] Nenhuma entrada encontrada no periodo.")
        sys.exit(0)

    print(f"[REVIEW] {len(entries)} entradas carregadas. Rodando validacao...")
    validator = ResultValidator()
    stats = run_review(entries, validator)

    # Console summary
    print_summary(stats)

    # Markdown report
    if not args.no_report:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        md_file = DATA_DIR / f"review_{timestamp}.md"
        md_content = generate_markdown(stats, args.days)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"[REVIEW] Relatorio: {md_file}")

    # Fixes JSON
    fixes = generate_fixes_json(stats)
    if fixes:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        fixes_file = DATA_DIR / f"fixes_{timestamp}.json"
        with open(fixes_file, "w", encoding="utf-8") as f:
            json.dump(fixes, f, ensure_ascii=False, indent=2)
        print(f"[REVIEW] Fixes: {fixes_file} ({len(fixes)} problemas)")

    # Auto-fix
    if args.auto_fix:
        auto_fixable = [f for f in fixes if f.get("auto_fixable")]
        if auto_fixable:
            print(f"\n[AUTO-FIX] {len(auto_fixable)} correcoes auto-aplicaveis encontradas.")
            apply_auto_fixes(auto_fixable)
        else:
            print(f"\n[AUTO-FIX] Nenhuma correcao auto-aplicavel encontrada.")

    print("[REVIEW] Concluido.")


def apply_auto_fixes(fixes: list):
    """Aplica correcoes automaticas."""
    for fix in fixes:
        actions = fix.get("fix_actions", [])
        for action in actions:
            action_type = action.get("type", "")

            if action_type == "improve_prompt":
                # Registrar padroes de correcao do Groq para melhoria do prompt
                print(f"  [FIX] Registrando padrao de correcao Groq para: {fix.get('question', '?')[:40]}")
                _log_groq_pattern(fix)

            elif action_type == "add_synonym":
                print(f"  [FIX] Sugestao de sinonimo: {fix.get('question', '?')[:40]}")
                # Nao altera automaticamente - apenas registra sugestao

            else:
                print(f"  [FIX] Acao '{action_type}' requer intervencao manual: {action.get('description', '?')}")


def _log_groq_pattern(fix: dict):
    """Registra padrao de correcao do Groq em arquivo para revisao."""
    patterns_file = DATA_DIR / "groq_correction_patterns.jsonl"
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        pattern = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "question": fix.get("question", ""),
            "intent": fix.get("intent", ""),
            "checks_failed": fix.get("checks_failed", []),
        }
        with open(patterns_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(pattern, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"  [FIX] Erro ao registrar padrao: {e}")


if __name__ == "__main__":
    main()
