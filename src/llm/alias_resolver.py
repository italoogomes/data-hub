"""
AliasResolver - Sistema de apelidos de produto para o Smart Agent.

Mapeia termos informais usados pelos usuarios para nomes reais de produtos
ou CODPRODs do sistema Sankhya.

Ex: "boneca" -> "PINO DO CABECALHO"
    "kit embreagem" -> CODPROD 145678
"""

import json
import os
import unicodedata
from datetime import datetime
from typing import Optional


# Caminho padrao do JSON de apelidos
_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "knowledge", "glossario", "apelidos_produto.json"
)


class AliasResolver:
    """Resolve apelidos de produto para nomes/codigos reais."""

    def __init__(self, json_path: str = None):
        self.json_path = json_path or _DEFAULT_PATH
        self._aliases = {}       # normalizado -> dict
        self._suggestions = []   # lista de sugestoes pendentes
        self._load()

    def _load(self):
        """Carrega apelidos do JSON."""
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("aliases", {})
            self._aliases = {}
            for key, val in raw.items():
                norm_key = self._normalize(key)
                self._aliases[norm_key] = val
            self._suggestions = data.get("suggestions", [])
            print(f"[ALIAS] Carregados {len(self._aliases)} apelido(s) de {self.json_path}")
        except FileNotFoundError:
            print(f"[ALIAS] Arquivo nao encontrado: {self.json_path} (iniciando vazio)")
            self._aliases = {}
            self._suggestions = []
        except (json.JSONDecodeError, Exception) as e:
            print(f"[ALIAS] Erro ao carregar: {e}")
            self._aliases = {}
            self._suggestions = []

    def _save(self):
        """Persiste apelidos no JSON."""
        data = {
            "_meta": {
                "descricao": "Apelidos de produto usados pelos usuarios da MMarra.",
                "formato": "chave = apelido normalizado, valor = objeto com nome_real, codprod, confidence, hits, criado_em, origem",
                "versao": "1.0",
                "atualizado_em": datetime.now().strftime("%Y-%m-%d")
            },
            "aliases": self._aliases,
            "suggestions": self._suggestions[-100:]  # manter ultimas 100
        }
        try:
            os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[ALIAS] Erro ao salvar: {e}")

    @staticmethod
    def _normalize(text: str) -> str:
        """Normaliza texto: minusculo, sem acentos, trim."""
        if not text:
            return ""
        s = text.lower().strip()
        # Remover acentos
        s = unicodedata.normalize("NFKD", s)
        s = "".join(c for c in s if not unicodedata.combining(c))
        return s

    def resolve(self, term: str) -> Optional[dict]:
        """Busca apelido e retorna info do produto real.

        Returns:
            dict com {nome_real, codprod, confidence} ou None se nao encontrou.
        """
        norm = self._normalize(term)
        if not norm:
            return None

        alias = self._aliases.get(norm)
        if alias and alias.get("confidence", 0) >= 0.5:
            self._increment_hits(norm)
            return {
                "nome_real": alias.get("nome_real"),
                "codprod": alias.get("codprod"),
                "confidence": alias.get("confidence", 0),
            }
        return None

    def _increment_hits(self, norm_key: str):
        """Incrementa contador de uso de um apelido."""
        if norm_key in self._aliases:
            self._aliases[norm_key]["hits"] = self._aliases[norm_key].get("hits", 0) + 1
            self._save()

    def add_alias(self, apelido: str, nome_real: str = None, codprod: int = None,
                  confidence: float = 0.90, origem: str = "manual") -> bool:
        """Adiciona ou atualiza um apelido.

        Args:
            apelido: Termo informal usado pelo usuario.
            nome_real: Nome real do produto no sistema (DESCRPROD).
            codprod: Codigo do produto no sistema.
            confidence: Grau de confianca (0.0 a 1.0).
            origem: "manual", "feedback", "sequencia", "admin".

        Returns:
            True se adicionado com sucesso.
        """
        norm = self._normalize(apelido)
        if not norm:
            return False
        if not nome_real and not codprod:
            return False

        self._aliases[norm] = {
            "nome_real": nome_real,
            "codprod": codprod,
            "confidence": confidence,
            "hits": 0,
            "criado_em": datetime.now().strftime("%Y-%m-%d"),
            "origem": origem,
        }
        self._save()
        print(f"[ALIAS] Adicionado: '{apelido}' -> {nome_real or codprod} (conf={confidence}, origem={origem})")
        return True

    def remove_alias(self, apelido: str) -> bool:
        """Remove um apelido."""
        norm = self._normalize(apelido)
        if norm in self._aliases:
            del self._aliases[norm]
            self._save()
            print(f"[ALIAS] Removido: '{apelido}'")
            return True
        return False

    def suggest_alias(self, term: str, context: str = "", user: str = ""):
        """Registra uma sugestao de apelido para review.

        Chamado quando um termo nao e encontrado no banco e pode ser apelido.
        """
        norm = self._normalize(term)
        if not norm or len(norm) < 2:
            return

        # Verificar se ja existe sugestao igual
        for s in self._suggestions:
            if s.get("term_norm") == norm:
                s["count"] = s.get("count", 1) + 1
                s["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                if context and context not in s.get("contexts", []):
                    s.setdefault("contexts", []).append(context[:100])
                self._save()
                return

        self._suggestions.append({
            "term": term,
            "term_norm": norm,
            "count": 1,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "contexts": [context[:100]] if context else [],
            "user": user,
            "status": "pending",  # pending, approved, rejected
        })
        self._save()
        print(f"[ALIAS] Sugestao registrada: '{term}' (contexto: {context[:50]})")

    def get_all_aliases(self) -> dict:
        """Retorna todos os apelidos (para admin)."""
        return dict(self._aliases)

    def get_suggestions(self, status: str = "pending") -> list:
        """Retorna sugestoes filtradas por status."""
        return [s for s in self._suggestions if s.get("status") == status]

    def approve_suggestion(self, term: str, nome_real: str = None, codprod: int = None) -> bool:
        """Aprova uma sugestao e a transforma em apelido."""
        norm = self._normalize(term)
        for s in self._suggestions:
            if s.get("term_norm") == norm:
                s["status"] = "approved"
                return self.add_alias(term, nome_real=nome_real, codprod=codprod,
                                      confidence=0.85, origem="feedback")
        return False

    def reject_suggestion(self, term: str) -> bool:
        """Rejeita uma sugestao."""
        norm = self._normalize(term)
        for s in self._suggestions:
            if s.get("term_norm") == norm:
                s["status"] = "rejected"
                self._save()
                return True
        return False

    # ---- B3: Aprendizado via feedback ----
    def detect_alias_from_feedback(self, log_entry: dict, rating: str, comment: str = ""):
        """Analisa feedback negativo para detectar possivel apelido.

        Se o usuario deu feedback negativo e a query tinha produto_nome que nao encontrou
        resultados, registra como sugestao com confidence boost.
        """
        if rating != "negative":
            return

        proc = log_entry.get("processing", {})
        entities = proc.get("entities", {})
        produto_nome = entities.get("produto_nome", "")
        records = log_entry.get("result", {}).get("records_found", 0)

        if produto_nome and records == 0:
            # Ja existe sugestao? Incrementar confidence
            norm = self._normalize(produto_nome)
            for s in self._suggestions:
                if s.get("term_norm") == norm:
                    s["count"] = s.get("count", 1) + 2  # feedback pesa mais
                    s["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    s.setdefault("feedback_negative", 0)
                    s["feedback_negative"] = s.get("feedback_negative", 0) + 1
                    if comment:
                        s.setdefault("contexts", []).append(f"[FEEDBACK] {comment[:100]}")
                    self._save()
                    print(f"[ALIAS] Feedback negativo reforca sugestao: '{produto_nome}'")
                    return

            # Nova sugestao via feedback
            self.suggest_alias(
                produto_nome,
                context=f"[FEEDBACK NEGATIVO] {comment[:100]}" if comment else "[FEEDBACK NEGATIVO]",
                user=log_entry.get("user", "")
            )

    # ---- B4: Aprendizado via sequencia ----
    def detect_alias_from_sequence(self, failed_term: str, success_term: str, codprod: int = None):
        """Detecta alias quando usuario falha com termo A e sucede com termo B.

        Ex: "boneca" (0 results) -> "pino do cabecalho" (encontrou) = boneca e alias
        """
        if not failed_term or not success_term:
            return

        norm_failed = self._normalize(failed_term)
        norm_success = self._normalize(success_term)

        if norm_failed == norm_success:
            return  # mesmo termo, nao e alias

        # Verificar se ja tem alias
        if norm_failed in self._aliases:
            return  # ja resolvido

        # Registrar ou reforcar sugestao
        for s in self._suggestions:
            if s.get("term_norm") == norm_failed:
                s["count"] = s.get("count", 1) + 1
                s.setdefault("possible_target", success_term.upper())
                s.setdefault("possible_codprod", codprod)
                s["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                self._save()
                print(f"[ALIAS] Sequencia reforca: '{failed_term}' -> '{success_term}'")

                # Auto-promote se count alto
                if s.get("count", 0) >= 3:
                    self.add_alias(
                        failed_term,
                        nome_real=success_term.upper(),
                        codprod=codprod,
                        confidence=0.75,
                        origem="sequencia"
                    )
                return

        # Nova sugestao
        self._suggestions.append({
            "term": failed_term,
            "term_norm": norm_failed,
            "count": 1,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "contexts": [f"[SEQ] apos falha, usuario buscou '{success_term}'"],
            "possible_target": success_term.upper(),
            "possible_codprod": codprod,
            "user": "",
            "status": "pending",
        })
        self._save()
        print(f"[ALIAS] Sequencia detectada: '{failed_term}' -> '{success_term}'")

    # ---- B5: Auto-promote sugestoes com alta confianca ----
    def auto_promote_suggestions(self, min_count: int = 5) -> list:
        """Promove automaticamente sugestoes com count alto e target definido.

        Returns:
            Lista de apelidos promovidos.
        """
        promoted = []
        for s in self._suggestions:
            if s.get("status") != "pending":
                continue
            if s.get("count", 0) < min_count:
                continue
            target = s.get("possible_target")
            codprod = s.get("possible_codprod")
            if not target and not codprod:
                continue

            term = s.get("term", "")
            ok = self.add_alias(
                term,
                nome_real=target,
                codprod=codprod,
                confidence=0.80,
                origem="auto"
            )
            if ok:
                s["status"] = "approved"
                promoted.append({"term": term, "target": target, "codprod": codprod})

        if promoted:
            self._save()
            print(f"[ALIAS] Auto-promovidos: {len(promoted)} apelido(s)")
        return promoted

    def stats(self) -> dict:
        """Retorna estatisticas do sistema de apelidos."""
        total_aliases = len(self._aliases)
        total_suggestions = len(self._suggestions)
        pending = sum(1 for s in self._suggestions if s.get("status") == "pending")
        approved = sum(1 for s in self._suggestions if s.get("status") == "approved")
        rejected = sum(1 for s in self._suggestions if s.get("status") == "rejected")
        total_hits = sum(a.get("hits", 0) for a in self._aliases.values())
        return {
            "total_aliases": total_aliases,
            "total_suggestions": total_suggestions,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total_hits": total_hits,
        }
