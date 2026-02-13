"""
MMarra Data Hub - Query Logger (Feedback Loop System)

Registra toda interacao do Smart Agent em arquivo JSONL para:
- Analytics de uso (intents, layers, filtros)
- Feedback do usuario (positivo/negativo)
- Sugestoes de perguntas populares
- Melhoria continua do scoring/prompt

Storage: data/query_log.jsonl (JSON Lines, append-only)
Rotacao: 10MB -> query_log_YYYYMM.jsonl
"""

import json
import os
import uuid
import threading
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter


PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_FILE = DATA_DIR / "query_log.jsonl"
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB


class QueryLogger:
    """Logger de queries do Smart Agent. Thread-safe, append-only JSONL."""

    def __init__(self, log_file: Path = None):
        self.log_file = log_file or LOG_FILE
        self._lock = threading.Lock()
        self._ensure_dir()

    def _ensure_dir(self):
        """Cria diretorio data/ se nao existir."""
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    # ================================================================
    # LOGGING
    # ================================================================

    def create_entry(self, question: str, user: str = "") -> dict:
        """Cria um registro novo com ID unico. Retorna o dict para ser preenchido."""
        return {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "user": (user or "").upper(),
            "question": question,
            "question_normalized": question.lower().strip().rstrip("?!."),
            "processing": {
                "layer": None,
                "intent": None,
                "score": 0,
                "entities": {},
                "filters_source": None,
                "filters_applied": {},
                "groq_raw": None,
                "groq_corrected": False,
                "view_mode": None,
                "time_ms": 0,
            },
            "result": {
                "type": None,
                "records_found": 0,
                "records_shown": 0,
                "response_preview": "",
            },
            "feedback": {
                "rating": None,
                "rated_at": None,
                "comment": None,
            },
            "auto_tags": [],
        }

    def save(self, entry: dict):
        """Salva um registro no JSONL. Thread-safe, fire-and-forget."""
        try:
            self._rotate_if_needed()
            line = json.dumps(entry, ensure_ascii=False, default=str)
            with self._lock:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            print(f"[QLOG] Erro ao salvar: {e}")

    def _rotate_if_needed(self):
        """Rotaciona arquivo se ultrapassar MAX_LOG_SIZE."""
        try:
            if self.log_file.exists() and self.log_file.stat().st_size > MAX_LOG_SIZE:
                suffix = datetime.now().strftime("%Y%m")
                rotated = self.log_file.parent / f"query_log_{suffix}.jsonl"
                # Se ja existe arquivo rotacionado do mes, append
                if rotated.exists():
                    with open(self.log_file, "r", encoding="utf-8") as src:
                        with open(rotated, "a", encoding="utf-8") as dst:
                            dst.write(src.read())
                else:
                    self.log_file.rename(rotated)
                    return
                # Limpar arquivo principal
                with self._lock:
                    with open(self.log_file, "w", encoding="utf-8") as f:
                        pass
                print(f"[QLOG] Log rotacionado -> {rotated.name}")
        except Exception as e:
            print(f"[QLOG] Erro na rotacao: {e}")

    # ================================================================
    # FEEDBACK
    # ================================================================

    def save_feedback(self, message_id: str, rating: str, comment: str = None) -> bool:
        """Atualiza o feedback de um registro existente."""
        try:
            if not self.log_file.exists():
                return False

            lines = []
            found = False
            with self._lock:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get("id") == message_id:
                                entry["feedback"] = {
                                    "rating": rating,
                                    "rated_at": datetime.now().isoformat(timespec="seconds"),
                                    "comment": comment,
                                }
                                found = True
                            lines.append(json.dumps(entry, ensure_ascii=False, default=str))
                        except json.JSONDecodeError:
                            lines.append(line)

                if found:
                    with open(self.log_file, "w", encoding="utf-8") as f:
                        f.write("\n".join(lines) + "\n")

            return found
        except Exception as e:
            print(f"[QLOG] Erro ao salvar feedback: {e}")
            return False

    def get_entry(self, message_id: str) -> dict | None:
        """Busca uma entrada pelo message_id."""
        try:
            if not self.log_file.exists():
                return None
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("id") == message_id:
                            return entry
                    except json.JSONDecodeError:
                        continue
            return None
        except Exception:
            return None

    # ================================================================
    # LEITURA (para analytics e sugestoes)
    # ================================================================

    def _load_entries(self, max_age_days: int = 30) -> list:
        """Carrega entradas dos ultimos N dias."""
        entries = []
        if not self.log_file.exists():
            return entries

        cutoff = datetime.now() - timedelta(days=max_age_days)
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp", "")
                        if ts and ts >= cutoff.isoformat(timespec="seconds"):
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[QLOG] Erro ao carregar: {e}")

        return entries

    # ================================================================
    # SUGESTOES
    # ================================================================

    def get_suggestions(self, user: str = None) -> dict:
        """Gera sugestoes de perguntas baseadas no historico."""
        entries = self._load_entries(max_age_days=30)
        if not entries:
            return {
                "popular": self._default_suggestions(),
                "recent_successful": [],
                "personalized": [],
            }

        # Popular: perguntas com feedback positivo ou sem negativo
        question_stats = {}  # {question_normalized: {count, positive, negative}}
        for e in entries:
            q = e.get("question_normalized", "")
            if not q or len(q) < 5:
                continue
            proc = e.get("processing", {})
            intent = proc.get("intent", "")
            if intent in ("saudacao", "ajuda"):
                continue

            if q not in question_stats:
                question_stats[q] = {"count": 0, "positive": 0, "negative": 0, "question": e.get("question", q)}
            question_stats[q]["count"] += 1
            rating = (e.get("feedback") or {}).get("rating")
            if rating == "positive":
                question_stats[q]["positive"] += 1
            elif rating == "negative":
                question_stats[q]["negative"] += 1

        # Top 10 populares (mais usadas, sem muitos negativos)
        popular_sorted = sorted(
            question_stats.values(),
            key=lambda x: (x["positive"] * 2 + x["count"] - x["negative"] * 5),
            reverse=True,
        )
        popular = [s["question"] for s in popular_sorted if s["negative"] < s["count"] * 0.3][:10]

        # Recent successful: ultimas 5 do usuario com feedback positivo
        recent_successful = []
        if user:
            user_upper = user.upper()
            user_entries = [e for e in entries if e.get("user", "").upper() == user_upper]
            for e in reversed(user_entries):
                rating = (e.get("feedback") or {}).get("rating")
                if rating == "positive":
                    q = e.get("question", "")
                    if q and q not in recent_successful:
                        recent_successful.append(q)
                        if len(recent_successful) >= 5:
                            break

        # Personalized: marcas/intents mais usados pelo usuario -> templates
        personalized = []
        if user:
            user_upper = user.upper()
            user_entries = [e for e in entries if e.get("user", "").upper() == user_upper]
            marca_counter = Counter()
            for e in user_entries:
                entities = (e.get("processing") or {}).get("entities") or {}
                marca = entities.get("marca")
                if marca:
                    marca_counter[marca] += 1

            # Gerar sugestoes pra marcas mais usadas
            templates = [
                "pendencias da {marca}",
                "pedidos atrasados da {marca}",
                "o que falta chegar da {marca}",
            ]
            used_marcas = [m for m, _ in marca_counter.most_common(3)]
            for marca in used_marcas:
                template = templates[len(personalized) % len(templates)]
                suggestion = template.format(marca=marca.title())
                if suggestion not in personalized:
                    personalized.append(suggestion)

        if not popular:
            popular = self._default_suggestions()

        return {
            "popular": popular,
            "recent_successful": recent_successful,
            "personalized": personalized,
        }

    def _default_suggestions(self) -> list:
        """Sugestoes padrao quando nao ha historico."""
        return [
            "O que falta chegar da Donaldson?",
            "Pedidos atrasados",
            "Vendas de hoje",
            "Estoque critico",
            "Qual pedido com maior valor pendente?",
        ]

    # ================================================================
    # ANALYTICS (admin)
    # ================================================================

    def get_analytics(self, days: int = 30) -> dict:
        """Gera analytics completo para admin."""
        entries = self._load_entries(max_age_days=days)
        total = len(entries)

        if total == 0:
            return {
                "total_queries": 0,
                "period": f"last_{days}_days",
                "feedback_summary": {"positive": 0, "negative": 0, "no_feedback": 0, "satisfaction_rate": 0},
                "by_intent": {},
                "by_layer": {},
                "problem_queries": [],
                "improvement_suggestions": [],
            }

        # Feedback summary
        positive = sum(1 for e in entries if (e.get("feedback") or {}).get("rating") == "positive")
        negative = sum(1 for e in entries if (e.get("feedback") or {}).get("rating") == "negative")
        no_feedback = total - positive - negative
        rated = positive + negative
        satisfaction = round((positive / rated * 100), 1) if rated > 0 else 0

        # By intent
        by_intent = {}
        for e in entries:
            intent = (e.get("processing") or {}).get("intent") or "unknown"
            if intent not in by_intent:
                by_intent[intent] = {"total": 0, "positive": 0, "negative": 0}
            by_intent[intent]["total"] += 1
            rating = (e.get("feedback") or {}).get("rating")
            if rating == "positive":
                by_intent[intent]["positive"] += 1
            elif rating == "negative":
                by_intent[intent]["negative"] += 1

        # By layer
        by_layer = {}
        for e in entries:
            layer = (e.get("processing") or {}).get("layer") or "unknown"
            if layer not in by_layer:
                by_layer[layer] = {"total": 0, "positive": 0, "negative": 0}
            by_layer[layer]["total"] += 1
            rating = (e.get("feedback") or {}).get("rating")
            if rating == "positive":
                by_layer[layer]["positive"] += 1
            elif rating == "negative":
                by_layer[layer]["negative"] += 1

        # Problem queries: perguntas com feedback negativo
        negative_entries = [e for e in entries if (e.get("feedback") or {}).get("rating") == "negative"]
        problem_counter = {}
        for e in negative_entries:
            q = e.get("question_normalized", e.get("question", "?"))
            if q not in problem_counter:
                problem_counter[q] = {"question": e.get("question", q), "count": 0, "negative": 0, "last_seen": e.get("timestamp", "")}
            problem_counter[q]["count"] += 1
            problem_counter[q]["negative"] += 1
            if e.get("timestamp", "") > problem_counter[q]["last_seen"]:
                problem_counter[q]["last_seen"] = e.get("timestamp", "")

        problem_queries = sorted(problem_counter.values(), key=lambda x: x["negative"], reverse=True)[:10]

        # Improvement suggestions
        improvement_suggestions = self._generate_improvements(entries)

        return {
            "total_queries": total,
            "period": f"last_{days}_days",
            "feedback_summary": {
                "positive": positive,
                "negative": negative,
                "no_feedback": no_feedback,
                "satisfaction_rate": satisfaction,
            },
            "by_intent": by_intent,
            "by_layer": by_layer,
            "problem_queries": problem_queries,
            "improvement_suggestions": improvement_suggestions,
        }

    def _generate_improvements(self, entries: list) -> list:
        """Gera sugestoes automaticas de melhoria baseadas nos padroes."""
        suggestions = []

        # 1. Groq corrections frequentes (pos-processamento corrigiu algo)
        groq_corrections = Counter()
        for e in entries:
            proc = e.get("processing") or {}
            if proc.get("groq_corrected"):
                raw = proc.get("groq_raw") or {}
                # Detectar qual campo foi corrigido
                tags = e.get("auto_tags") or []
                for tag in tags:
                    if "corrected" in tag:
                        groq_corrections[tag] += 1

        for correction, count in groq_corrections.most_common(5):
            if count >= 3:
                suggestions.append({
                    "type": "groq_correction_frequent",
                    "field": correction,
                    "count": count,
                })

        # 2. Queries que caem em fallback frequentemente
        fallback_questions = Counter()
        for e in entries:
            proc = e.get("processing") or {}
            if proc.get("layer") == "fallback":
                q = e.get("question_normalized", "")
                if q:
                    fallback_questions[q] += 1

        for q, count in fallback_questions.most_common(5):
            if count >= 3:
                suggestions.append({
                    "type": "unrecognized_pattern",
                    "question": q,
                    "count": count,
                })

        # 3. Layer 2 (LLM) muito frequente para um mesmo intent
        # Indica que scoring poderia resolver mas nao tem keywords suficientes
        llm_intents = Counter()
        for e in entries:
            proc = e.get("processing") or {}
            layer = proc.get("layer", "")
            intent = proc.get("intent", "")
            if layer in ("groq", "ollama") and intent:
                llm_intents[intent] += 1

        for intent, count in llm_intents.most_common(3):
            if count >= 10:
                suggestions.append({
                    "type": "scoring_gap",
                    "intent": intent,
                    "llm_calls": count,
                    "suggestion": f"Adicionar mais keywords no INTENT_SCORES['{intent}'] para resolver via scoring",
                })

        return suggestions


# ================================================================
# AUTO-TAG HELPERS
# ================================================================

def generate_auto_tags(entry: dict) -> list:
    """Gera tags automaticas baseadas no processamento."""
    tags = []
    proc = entry.get("processing") or {}
    filters = proc.get("filters_applied") or {}

    # Layer usada
    layer = proc.get("layer", "")
    if layer:
        tags.append(f"layer:{layer}")

    # Intent
    intent = proc.get("intent", "")
    if intent:
        tags.append(f"intent:{intent}")

    # Entidades
    entities = proc.get("entities") or {}
    for key, val in entities.items():
        if val:
            tags.append(f"{key}_filter")

    # Filtros
    if filters.get("_sort"):
        sort_field = filters["_sort"].replace("_DESC", "").replace("_ASC", "").lower()
        tags.append("sort")
        tags.append(f"sort:{sort_field}")

    if filters.get("_top"):
        tags.append(f"top{filters['_top']}")

    for key in filters:
        if key.startswith("_fn_"):
            fn = key.replace("_fn_", "")
            tags.append(f"fn:{fn}")
        elif not key.startswith("_") and key not in ("_sort", "_top"):
            tags.append(f"filter:{key}")

    # Groq correcao
    if proc.get("groq_corrected"):
        tags.append("groq_corrected")

    # View mode
    view = proc.get("view_mode")
    if view:
        tags.append(f"view:{view}")

    # Resultado
    result = entry.get("result") or {}
    rtype = result.get("type", "")
    if rtype:
        tags.append(f"result:{rtype}")

    records = result.get("records_found", 0)
    if records == 0:
        tags.append("zero_results")

    return tags
