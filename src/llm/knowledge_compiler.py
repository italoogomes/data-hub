"""
Knowledge Compiler - Le documentacao e auto-gera inteligencia pro Smart Agent.

Le TODA a knowledge base, envia pro Groq pra extrair keywords/filtros/exemplos,
e gera `data/compiled_knowledge.json` que o SmartAgent carrega no startup.

Uso:
    python -m src.llm.knowledge_compiler --full      # Processa TUDO
    python -m src.llm.knowledge_compiler              # So novos/alterados (incremental)
    python -m src.llm.knowledge_compiler --dry-run    # Mostra sem alterar
    python -m src.llm.knowledge_compiler --report     # Relatorio do compilado
    python -m src.llm.knowledge_compiler --verbose    # Output detalhado
"""

import argparse
import ast
import asyncio
import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


# Caminhos relativos ao root do projeto
_ROOT = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_DIR = _ROOT / "knowledge"
DATA_DIR = _ROOT / "data"
MANIFEST_PATH = DATA_DIR / "knowledge_manifest.json"
COMPILED_PATH = DATA_DIR / "compiled_knowledge.json"

MAX_CONTENT_CHARS = 6000   # ~1500 tokens
MAX_REQUESTS_PER_RUN = 50  # Rate limit Groq free tier
CONFIDENCE_BY_TYPE = {
    "tabela": 0.90,
    "glossario": 0.95,
    "processo": 0.80,
    "regra": 0.85,
    "referencia": 0.75,
}

# Groq config
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_CLASSIFIER_MODEL", "llama-3.1-8b-instant")


# ============================================================
# PROMPTS POR TIPO DE DOCUMENTO
# ============================================================

PROMPT_TABELA = """Voce e um especialista em ERP Sankhya. Analise esta documentacao de tabela e extraia informacoes que ajudem um chatbot a entender perguntas dos usuarios.

CONTEXTO: O chatbot atende funcionarios de uma distribuidora de autopecas. Eles perguntam coisas como "quanto temos a pagar?", "pedidos pendentes da MANN", "estoque do produto 133346".

INTENTS JA EXISTENTES: pendencia_compras, estoque, vendas, gerar_excel, saudacao, ajuda

EXTRAIA:

1. KEYWORDS: Palavras que um usuario usaria ao perguntar sobre dados desta tabela. Para cada keyword, indique qual intent existente faz sentido OU sugira um novo intent se nenhum se encaixa.
   Formato: {{"word": "pagar", "intent": "financeiro", "weight": 10}}
   Weight: 10=garante intent, 5-8=forte indicacao, 2-4=reforco

2. FILTER_RULES: Patterns de pergunta -> acao. Baseado nos campos da tabela.
   Formato: {{"match": ["titulos vencidos", "contas vencidas"], "description": "DTVENC < SYSDATE AND DHBAIXA IS NULL"}}

3. GROQ_EXAMPLES: 2-3 exemplos de perguntas reais com JSON de resposta esperada.
   Formato: {{"question": "quanto temos a pagar este mes?", "response": {{"intent": "financeiro", "periodo": "mes_atual"}}}}

4. SYNONYMS: Termos populares -> campos tecnicos desta tabela.
   Formato: {{"term": "boleto", "field": "TGFFIN.VLRDESDOB", "meaning": "titulo financeiro"}}

Responda APENAS com JSON valido (sem markdown, sem backticks, sem explicacao):
{{"keywords":[], "filter_rules":[], "groq_examples":[], "synonyms":[]}}

DOCUMENTO:
{content}"""

PROMPT_PROCESSO = """Voce e um especialista em processos de negocio. Analise esta documentacao de processo e extraia informacoes para um chatbot de distribuidora de autopecas.

FOCO: Como o USUARIO perguntaria no dia a dia. Nao termos tecnicos, mas linguagem natural.
Ex: "quanto gastei" (nao "SELECT SUM(VLRDESDOB)"), "quem aprovou" (nao "TGFLIB.CODUSU")

INTENTS JA EXISTENTES: pendencia_compras, estoque, vendas, gerar_excel, saudacao, ajuda

EXTRAIA:

1. KEYWORDS: Vocabulario do time que usa este processo.
   Formato: {{"word": "cotacao", "intent": "pendencia_compras", "weight": 5}}

2. FILTER_RULES: Perguntas comuns -> como filtrar dados.
   Formato: {{"match": ["pedidos aprovados"], "description": "STATUS = 'APROVADO'"}}

3. GROQ_EXAMPLES: 3-4 perguntas reais sobre este processo.
   Formato: {{"question": "quais pedidos estao aguardando aprovacao?", "response": {{"intent": "pendencia_compras"}}}}

4. SYNONYMS: Termos do processo -> termos tecnicos.
   Formato: {{"term": "aprovar", "field": "TGFLIB", "meaning": "liberacao de pedido"}}

Responda APENAS com JSON valido (sem markdown):
{{"keywords":[], "filter_rules":[], "groq_examples":[], "synonyms":[]}}

DOCUMENTO:
{content}"""

PROMPT_REGRA = """Analise esta regra de negocio de uma distribuidora de autopecas e extraia:

INTENTS JA EXISTENTES: pendencia_compras, estoque, vendas, gerar_excel, saudacao, ajuda

1. KEYWORDS: Termos que indicam perguntas sobre esta regra.
   Formato: {{"word": "aprovacao", "intent": "pendencia_compras", "weight": 5}}

2. FILTER_RULES: Condicoes descritas -> filtros/acoes.
   Formato: {{"match": ["pedidos sem aprovacao"], "description": "STATUSNOTA = 'P'"}}

3. GROQ_EXAMPLES: Perguntas sobre esta regra.
   Formato: {{"question": "quais pedidos precisam de aprovacao?", "response": {{"intent": "pendencia_compras"}}}}

4. SYNONYMS: Termos -> campos tecnicos.
   Formato: {{"term": "liberar", "field": "TGFLIB", "meaning": "aprovar pedido"}}

5. BUSINESS_RULES: Regras de desambiguacao que o sistema deve saber.
   Formato: {{"rule": "pendencia sem especificar = pendencia de COMPRA (nao financeira)"}}

Responda APENAS com JSON valido:
{{"keywords":[], "filter_rules":[], "groq_examples":[], "synonyms":[], "business_rules":[]}}

DOCUMENTO:
{content}"""

PROMPT_GLOSSARIO = """Analise este glossario de termos de uma distribuidora de autopecas e extraia mapeamentos:

INTENTS JA EXISTENTES: pendencia_compras, estoque, vendas, gerar_excel, saudacao, ajuda

1. KEYWORDS: Termos que indicam intents especificos.
   Formato: {{"word": "empenho", "intent": "pendencia_compras", "weight": 6}}

2. SYNONYMS: Cada termo do usuario -> significado tecnico/campo SQL.
   Formato: {{"term": "empenho", "field": "TGFCAB.CODTIPOPER", "meaning": "compra casada 1313"}}

3. FILTER_RULES: Mapeamentos diretos de texto -> filtro.
   Formato: {{"match": ["compra casada"], "description": "CODTIPOPER = 1313"}}

Responda APENAS com JSON valido:
{{"keywords":[], "filter_rules":[], "synonyms":[]}}

DOCUMENTO:
{content}"""

PROMPT_REFERENCIA = """Analise esta referencia tecnica do ERP Sankhya e extraia:

INTENTS JA EXISTENTES: pendencia_compras, estoque, vendas, gerar_excel, saudacao, ajuda

1. KEYWORDS: Termos tecnicos que indicam intents.
   Formato: {{"word": "nota", "intent": "vendas", "weight": 3}}

2. SYNONYMS: Mapeamentos de termos.
   Formato: {{"term": "nota fiscal", "field": "TGFCAB.NUMNOTA", "meaning": "numero da nota"}}

3. BUSINESS_RULES: Regras/cuidados que o sistema deve seguir.
   Formato: {{"rule": "NUNCA juntar TGFITE com TGFFIN sem subquery"}}

Responda APENAS com JSON valido:
{{"keywords":[], "synonyms":[], "business_rules":[]}}

DOCUMENTO:
{content}"""


PROMPTS = {
    "tabela": PROMPT_TABELA,
    "processo": PROMPT_PROCESSO,
    "regra": PROMPT_REGRA,
    "glossario": PROMPT_GLOSSARIO,
    "referencia": PROMPT_REFERENCIA,
}


# ============================================================
# KNOWLEDGE COMPILER
# ============================================================

class KnowledgeCompiler:

    def __init__(self, groq_api_key: str = None):
        self.groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self.manifest = self._load_manifest()
        self.verbose = False
        self._groq_calls = 0

    # ============================================================
    # CORE
    # ============================================================

    async def compile(self, full: bool = False, dry_run: bool = False, verbose: bool = False) -> dict:
        """Compila knowledge base. Retorna stats."""
        self.verbose = verbose
        t0 = time.time()

        # Garantir pasta data/
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # 1. Scan
        files = self._scan_files()
        to_process = [f for f in files if self._needs_processing(f["path"], f["hash"], full)]

        print(f"[COMPILER] Scan: {len(files)} arquivos, {len(to_process)} para processar" +
              (" (full)" if full else " (incremental)"))

        if dry_run:
            self._print_dry_run(files, to_process)
            return {"total_files": len(files), "to_process": len(to_process), "processed": 0, "dry_run": True}

        if not to_process:
            print("[COMPILER] Nenhum arquivo novo/alterado.")
            return {"total_files": len(files), "to_process": 0, "processed": 0}

        # 2. Processar
        results = []
        processed = 0
        errors = 0

        for f in to_process:
            if self._groq_calls >= MAX_REQUESTS_PER_RUN:
                print(f"[COMPILER] Rate limit: {MAX_REQUESTS_PER_RUN} requests atingido, parando.")
                break

            try:
                content = Path(f["path"]).read_text(encoding="utf-8")
                prepared = self._prepare_content(content, f["doc_type"])

                if self.groq_key:
                    result = await self._analyze_document(f["path"], prepared, f["doc_type"])
                else:
                    result = self._analyze_local(content, f["doc_type"])

                result["_source"] = f["relative"]
                result["_doc_type"] = f["doc_type"]
                results.append(result)

                # Atualizar manifesto
                self.manifest["files"][f["relative"]] = {
                    "hash": f["hash"],
                    "size_lines": f["lines"],
                    "doc_type": f["doc_type"],
                    "processed_at": datetime.now().isoformat(timespec="seconds"),
                    "generated": {
                        "keywords": len(result.get("keywords", [])),
                        "filter_rules": len(result.get("filter_rules", [])),
                        "groq_examples": len(result.get("groq_examples", [])),
                        "synonyms": len(result.get("synonyms", [])),
                    }
                }
                processed += 1

                if verbose:
                    kw = len(result.get("keywords", []))
                    fr = len(result.get("filter_rules", []))
                    ge = len(result.get("groq_examples", []))
                    sy = len(result.get("synonyms", []))
                    print(f"  [OK] {f['relative']} -> kw={kw} fr={fr} ex={ge} syn={sy}")

            except Exception as e:
                errors += 1
                print(f"  [ERRO] {f['relative']}: {type(e).__name__}: {e}")

        # 3. Consolidar
        if results:
            # Carregar compilado existente (para merge incremental)
            existing = self._load_compiled()
            compiled = self._merge_all_results(results, existing if not full else None)
            compiled = self._deduplicate_against_manual(compiled)
            compiled["potential_intents"] = self._detect_potential_intents(compiled)

            compiled["_meta"] = {
                "compiled_at": datetime.now().isoformat(timespec="seconds"),
                "compiler_version": "1.0",
                "source_files": len(files),
                "processed_files": processed,
                "groq_model": GROQ_MODEL if self.groq_key else "local_regex",
                "groq_calls": self._groq_calls,
            }

            self._save_compiled(compiled)
            print(f"[COMPILER] Compilado salvo: {COMPILED_PATH}")

        # 4. Salvar manifesto
        self.manifest["last_incremental" if not full else "last_full_compile"] = datetime.now().isoformat(timespec="seconds")
        self.manifest["stats"] = self._compute_manifest_stats()
        self._save_manifest()

        elapsed = time.time() - t0
        stats = {
            "total_files": len(files),
            "to_process": len(to_process),
            "processed": processed,
            "errors": errors,
            "groq_calls": self._groq_calls,
            "elapsed_s": round(elapsed, 1),
        }
        print(f"[COMPILER] Concluido: {processed}/{len(to_process)} processados, "
              f"{errors} erros, {self._groq_calls} chamadas Groq, {elapsed:.1f}s")
        return stats

    def report(self):
        """Imprime relatorio do que esta compilado."""
        compiled = self._load_compiled()
        if not compiled:
            print("[COMPILER] Nenhum arquivo compilado encontrado.")
            print(f"  Execute: python -m src.llm.knowledge_compiler --full")
            return

        meta = compiled.get("_meta", {})
        print(f"\n{'='*60}")
        print(f"  KNOWLEDGE COMPILER - RELATORIO")
        print(f"{'='*60}")
        print(f"  Compilado em: {meta.get('compiled_at', '?')}")
        print(f"  Modelo:       {meta.get('groq_model', '?')}")
        print(f"  Arquivos:     {meta.get('source_files', '?')} total, {meta.get('processed_files', '?')} processados")
        print(f"  Groq calls:   {meta.get('groq_calls', '?')}")

        # Keywords por intent
        kw = compiled.get("intent_keywords", {})
        print(f"\n--- KEYWORDS ({sum(len(v) for v in kw.values())} total) ---")
        for intent, words in sorted(kw.items()):
            top = sorted(words, key=lambda x: -x.get("weight", 0))[:5]
            top_str = ", ".join(f"{w['word']}({w.get('weight',0)})" for w in top)
            print(f"  {intent}: {len(words)} keywords | top: {top_str}")

        # Filter rules
        fr = compiled.get("filter_rules", [])
        print(f"\n--- FILTER RULES ({len(fr)}) ---")
        for r in fr[:10]:
            matches = ", ".join(r.get("match", [])[:3])
            print(f"  [{matches}] -> {r.get('description', '?')[:60]}")
        if len(fr) > 10:
            print(f"  ...e mais {len(fr)-10} regras.")

        # Groq examples
        ge = compiled.get("groq_examples", [])
        print(f"\n--- GROQ EXAMPLES ({len(ge)}) ---")
        for e in ge[:5]:
            print(f"  \"{e.get('question', '?')[:60]}\" -> intent={e.get('response', {}).get('intent', '?')}")
        if len(ge) > 5:
            print(f"  ...e mais {len(ge)-5} exemplos.")

        # Synonyms
        sy = compiled.get("synonyms", [])
        print(f"\n--- SYNONYMS ({len(sy)}) ---")
        for s in sy[:8]:
            print(f"  \"{s.get('term', '?')}\" -> {s.get('field', '?')} ({s.get('meaning', '')[:40]})")
        if len(sy) > 8:
            print(f"  ...e mais {len(sy)-8} sinonimos.")

        # Business rules
        br = compiled.get("business_rules", [])
        if br:
            print(f"\n--- BUSINESS RULES ({len(br)}) ---")
            for r in br[:5]:
                print(f"  * {r.get('rule', '?')[:80]}")

        # Potential intents
        pi = compiled.get("potential_intents", [])
        if pi:
            print(f"\n--- INTENTS POTENCIAIS ({len(pi)}) ---")
            for p in pi:
                print(f"  ** {p['name']} ** ({p['keywords_count']} keywords)")
                print(f"     Top: {', '.join(p.get('top_keywords', [])[:5])}")
                print(f"     Nota: {p.get('note', '')}")

        print(f"\n{'='*60}\n")

    # ============================================================
    # SCAN & CLASSIFY
    # ============================================================

    def _scan_files(self) -> list:
        """Retorna [{path, relative, hash, lines, doc_type, needs_processing}]"""
        files = []
        if not KNOWLEDGE_DIR.exists():
            print(f"[COMPILER] AVISO: Diretorio {KNOWLEDGE_DIR} nao encontrado.")
            return files

        for filepath in sorted(KNOWLEDGE_DIR.rglob("*")):
            if not filepath.is_file():
                continue
            # Skip: .gitkeep, .json (apelidos), imagens
            if filepath.name == ".gitkeep":
                continue
            if filepath.suffix == ".json":
                continue
            if filepath.suffix not in (".md", ".txt"):
                continue

            relative = str(filepath.relative_to(_ROOT)).replace("\\", "/")
            doc_type = self._classify_doc(relative)
            if doc_type == "skip":
                continue

            file_hash = self._file_hash(filepath)
            lines = sum(1 for _ in filepath.open(encoding="utf-8", errors="ignore"))

            files.append({
                "path": str(filepath),
                "relative": relative,
                "hash": file_hash,
                "lines": lines,
                "doc_type": doc_type,
            })

        return files

    def _classify_doc(self, filepath: str) -> str:
        """Classifica por pasta."""
        fp = filepath.lower().replace("\\", "/")
        if "/tabelas/" in fp:
            return "tabela"
        if "/processos/" in fp:
            return "processo"
        if "/regras/" in fp:
            return "regra"
        if "/glossario/" in fp:
            if fp.endswith(".json"):
                return "skip"
            return "glossario"
        if fp.endswith(".json"):
            return "skip"
        # api.md, erros_sql.md, exemplos_sql.md, relacionamentos.md
        return "referencia"

    def _file_hash(self, filepath: Path) -> str:
        """SHA-256 do conteudo."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return f"sha256:{h.hexdigest()[:16]}"

    def _needs_processing(self, filepath: str, file_hash: str, full: bool) -> bool:
        """True se full=True OU hash mudou OU arquivo novo."""
        if full:
            return True
        relative = str(Path(filepath).relative_to(_ROOT)).replace("\\", "/")
        entry = self.manifest.get("files", {}).get(relative)
        if not entry:
            return True  # arquivo novo
        return entry.get("hash") != file_hash  # hash diferente

    # ============================================================
    # CONTENT PREPARATION
    # ============================================================

    def _prepare_content(self, content: str, doc_type: str) -> str:
        """Trunca docs grandes de forma inteligente."""
        if len(content) <= MAX_CONTENT_CHARS:
            return content

        if doc_type == "tabela":
            lines = content.split("\n")
            header = lines[:10]
            important_keywords = [
                "CODPROD", "DESCRPROD", "CODPARC", "NOMEPARC", "VLRNOTA", "VLRDESDOB",
                "DTNEG", "DTVENC", "DHBAIXA", "PENDENTE", "TIPMOV", "ESTOQUE", "ESTMIN",
                "CODMARCA", "CARACTERISTICAS", "REFERENCIA", "AD_", "CODVEND", "APELIDO",
                "STATUSNOTA", "CODTIPOPER", "NUNOTA", "NUMNOTA", "VLRUNIT", "QTDNEG",
                "CODVOL", "NCM", "ATIVO", "CODTIPVENDA", "CODTIPOPER",
            ]
            important = [l for l in lines if any(k in l.upper() for k in important_keywords)]
            result = "\n".join(header + ["...(campos relevantes)..."] + important[:80])
            return result[:MAX_CONTENT_CHARS]

        if doc_type == "referencia":
            # Para erros_sql/exemplos_sql: pegar inicio + exemplos mais recentes
            lines = content.split("\n")
            if len(lines) > 100:
                return "\n".join(lines[:30] + ["...(truncado)..."] + lines[-70:])

        # Default: inicio + fim
        half = MAX_CONTENT_CHARS // 2
        return content[:half] + "\n\n...(truncado)...\n\n" + content[-half:]

    # ============================================================
    # ANALISE VIA GROQ
    # ============================================================

    async def _analyze_document(self, filepath: str, content: str, doc_type: str) -> dict:
        """Envia pro Groq e retorna resultado parseado."""
        prompt = self._build_prompt(content, doc_type)
        result = await self._call_groq(prompt)
        if not result:
            # Fallback local se Groq falhar
            return self._analyze_local(content, doc_type)

        # Atribuir confidence e source
        confidence = CONFIDENCE_BY_TYPE.get(doc_type, 0.75)
        relative = str(Path(filepath).relative_to(_ROOT)).replace("\\", "/")

        for kw in result.get("keywords", []):
            kw.setdefault("confidence", confidence)
            kw["source"] = relative
        for fr in result.get("filter_rules", []):
            fr.setdefault("confidence", confidence)
            fr["source"] = relative
        for ge in result.get("groq_examples", []):
            ge.setdefault("confidence", confidence)
            ge["source"] = relative
        for sy in result.get("synonyms", []):
            sy["source"] = relative
        for br in result.get("business_rules", []):
            br["source"] = relative

        return result

    def _build_prompt(self, content: str, doc_type: str) -> str:
        """Monta prompt baseado no tipo."""
        template = PROMPTS.get(doc_type, PROMPT_REFERENCIA)
        return template.replace("{content}", content)

    async def _call_groq(self, prompt: str) -> Optional[dict]:
        """Chama Groq API e retorna JSON parseado."""
        if not self.groq_key:
            return None

        import requests as req_sync

        def _do_call():
            return req_sync.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "response_format": {"type": "json_object"},
                },
                timeout=30,
            )

        try:
            self._groq_calls += 1
            resp = await asyncio.to_thread(_do_call)

            if resp.status_code == 429:
                wait_s = int(resp.headers.get("retry-after", "2"))
                print(f"[COMPILER] Groq rate limit, aguardando {wait_s}s...")
                await asyncio.sleep(wait_s)
                # Retry uma vez
                resp = await asyncio.to_thread(_do_call)
                if resp.status_code == 429:
                    print(f"[COMPILER] Groq rate limit persistente, parando.")
                    self._groq_calls = MAX_REQUESTS_PER_RUN
                    return None

            if resp.status_code != 200:
                print(f"[COMPILER] Groq erro HTTP {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            # Limpar backticks, ```json, etc
            content = self._clean_json_response(content)

            # Tentar JSON primeiro, depois ast.literal_eval (single quotes)
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass

            try:
                obj = ast.literal_eval(content)
                if isinstance(obj, dict):
                    return obj
            except (ValueError, SyntaxError):
                pass

            print(f"[COMPILER] Groq resposta nao parseavel ({len(content)} chars)")
            return None

        except json.JSONDecodeError as e:
            print(f"[COMPILER] Groq JSON invalido: {e}")
            return None
        except Exception as e:
            print(f"[COMPILER] Groq erro: {type(e).__name__}: {e}")
            return None

    def _clean_json_response(self, content: str) -> str:
        """Limpa resposta do Groq removendo markdown/backticks."""
        content = content.strip()
        # Remover ```json ... ``` ou ``` ... ```
        if content.startswith("```"):
            first_nl = content.find("\n")
            if first_nl > 0:
                content = content[first_nl + 1:]
            else:
                content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Tentar extrair JSON se tem texto antes/depois
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            candidate = json_match.group()
            # Tentar parsear para validar
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        # Tentar corrigir single quotes -> double quotes (comum em LLMs)
        try:
            fixed = content.replace("'", '"')
            json.loads(fixed)
            return fixed
        except (json.JSONDecodeError, Exception):
            pass

        return content

    # ============================================================
    # FALLBACK LOCAL (sem Groq)
    # ============================================================

    def _analyze_local(self, content: str, doc_type: str) -> dict:
        """Analise basica por regex, sem LLM."""
        result = {"keywords": [], "filter_rules": [], "groq_examples": [], "synonyms": [], "business_rules": []}

        lines = content.split("\n")
        content_upper = content.upper()

        # Inferir intent do documento pelo conteudo
        intent_hints = {
            "pendencia_compras": ["PENDENCIA", "COMPRA", "PEDIDO", "FORNECEDOR", "CASADA", "EMPENHO",
                                  "CODTIPOPER", "TGFCAB", "PREVISAO", "COTACAO", "SOLICITACAO"],
            "estoque": ["ESTOQUE", "SALDO", "TGFEST", "TGFPRO", "ESTMIN", "CODPROD", "PRODUTO",
                        "SIMILAR", "FABRICANTE", "REFERENCIA", "APLICACAO"],
            "vendas": ["VENDA", "FATURAMENTO", "NOTA FISCAL", "TGFITE", "VLRNOTA", "VENDEDOR",
                       "FATURAD", "TIPMOV = 'V'"],
        }
        doc_intent = "unknown"
        best_count = 0
        for intent, hints in intent_hints.items():
            count = sum(1 for h in hints if h in content_upper)
            if count > best_count:
                best_count = count
                doc_intent = intent
        if best_count < 2:
            doc_intent = "unknown"

        # 1. Extrair palavras de headers markdown
        stopwords = {"para", "como", "entre", "sobre", "campos", "tabela", "campo",
                     "descricao", "tipo", "valor", "exemplo", "quando", "onde", "qual",
                     "quais", "relacionamentos", "observacoes", "importante", "nota",
                     "fluxo", "processo", "regra", "modulo"}
        for line in lines:
            if line.startswith("#"):
                words = re.findall(r'[A-Za-z\u00C0-\u00FF]{4,}', line.lower())
                for w in words:
                    if w not in stopwords:
                        result["keywords"].append({
                            "word": w, "intent": doc_intent, "weight": 3,
                            "confidence": 0.50
                        })

        # 2. Extrair de tabelas markdown (| termo | significado |)
        for line in lines:
            if "|" in line and not line.strip().startswith("|--") and not line.strip().startswith("| -"):
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if len(cells) >= 2 and len(cells[0]) > 1 and not cells[0].startswith("-"):
                    result["synonyms"].append({
                        "term": cells[0].lower()[:50],
                        "meaning": cells[1][:100],
                        "field": "",
                    })

        # 3. Extrair patterns "X = Y" ou "X -> Y"
        for line in lines:
            m = re.search(r'["\'](.{3,40}?)["\']\s*(?:=|->|\u2192)+\s*(.{3,80})', line)
            if m:
                result["synonyms"].append({
                    "term": m.group(1).lower().strip(),
                    "meaning": m.group(2).strip(),
                    "field": "",
                })

        # Dedup keywords
        seen = set()
        unique_kw = []
        for kw in result["keywords"]:
            if kw["word"] not in seen:
                seen.add(kw["word"])
                unique_kw.append(kw)
        result["keywords"] = unique_kw[:30]  # max 30 por doc
        result["synonyms"] = result["synonyms"][:20]  # max 20

        return result

    # ============================================================
    # CONSOLIDACAO
    # ============================================================

    def _merge_all_results(self, results: list, existing: dict = None) -> dict:
        """Junta resultados de todos os docs."""
        compiled = existing or {
            "intent_keywords": {},
            "filter_rules": [],
            "groq_examples": [],
            "synonyms": [],
            "business_rules": [],
        }

        for r in results:
            source = r.get("_source", "?")

            # Keywords -> agrupados por intent
            for kw in r.get("keywords", []):
                intent = kw.get("intent", "unknown")
                word = kw.get("word", "").lower().strip()
                if not word or len(word) < 2:
                    continue
                if intent not in compiled["intent_keywords"]:
                    compiled["intent_keywords"][intent] = []

                # Dedup por word dentro do intent
                existing_words = {w["word"] for w in compiled["intent_keywords"][intent]}
                if word not in existing_words:
                    compiled["intent_keywords"][intent].append({
                        "word": word,
                        "weight": kw.get("weight", 3),
                        "confidence": kw.get("confidence", 0.75),
                        "source": kw.get("source", source),
                    })

            # Filter rules
            for fr in r.get("filter_rules", []):
                if fr.get("match"):
                    fr.setdefault("source", source)
                    compiled["filter_rules"].append(fr)

            # Groq examples
            for ge in r.get("groq_examples", []):
                if ge.get("question"):
                    ge.setdefault("source", source)
                    compiled["groq_examples"].append(ge)

            # Synonyms
            for sy in r.get("synonyms", []):
                if sy.get("term"):
                    sy.setdefault("source", source)
                    compiled["synonyms"].append(sy)

            # Business rules
            for br in r.get("business_rules", []):
                if br.get("rule"):
                    br.setdefault("source", source)
                    compiled["business_rules"].append(br)

        return compiled

    def _deduplicate_against_manual(self, compiled: dict) -> dict:
        """Remove keywords/rules que ja existem no INTENT_SCORES/FILTER_RULES manual."""
        try:
            from src.llm.smart_agent_v3_backup import INTENT_SCORES, FILTER_RULES
        except ImportError:
            print("[COMPILER] AVISO: nao conseguiu importar smart_agent para dedup.")
            return compiled

        # Dedup keywords
        for intent, words in compiled.get("intent_keywords", {}).items():
            if intent in INTENT_SCORES:
                manual_words = set(INTENT_SCORES[intent].keys())
                compiled["intent_keywords"][intent] = [
                    w for w in words if w["word"] not in manual_words
                ]

        # Dedup filter rules
        existing_matches = set()
        for rule in FILTER_RULES:
            for m in rule.get("match", []):
                existing_matches.add(m.lower())

        compiled["filter_rules"] = [
            fr for fr in compiled.get("filter_rules", [])
            if not all(m.lower() in existing_matches for m in fr.get("match", []))
        ]

        return compiled

    def _detect_potential_intents(self, compiled: dict) -> list:
        """Detecta intents sugeridos que nao existem no codigo."""
        try:
            from src.llm.smart_agent_v3_backup import INTENT_SCORES
            existing = set(INTENT_SCORES.keys())
        except ImportError:
            existing = {"pendencia_compras", "estoque", "vendas", "gerar_excel", "saudacao", "ajuda"}

        potential = []
        for intent, keywords in compiled.get("intent_keywords", {}).items():
            if intent not in existing and intent != "unknown" and len(keywords) >= 3:
                potential.append({
                    "name": intent,
                    "keywords_count": len(keywords),
                    "top_keywords": [k["word"] for k in sorted(keywords, key=lambda x: -x.get("weight", 0))[:5]],
                    "source_files": list(set(k.get("source", "") for k in keywords)),
                    "note": f"Considerar criar _handle_{intent}()"
                })

        return sorted(potential, key=lambda x: -x["keywords_count"])

    # ============================================================
    # PERSISTENCIA
    # ============================================================

    def _load_manifest(self) -> dict:
        """Carrega manifesto."""
        try:
            if MANIFEST_PATH.exists():
                with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"version": "1.0", "files": {}, "stats": {}}

    def _save_manifest(self):
        """Salva manifesto."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
                json.dump(self.manifest, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[COMPILER] Erro ao salvar manifesto: {e}")

    def _load_compiled(self) -> dict:
        """Carrega compilado existente."""
        try:
            if COMPILED_PATH.exists():
                with open(COMPILED_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_compiled(self, compiled: dict):
        """Salva compilado."""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(COMPILED_PATH, "w", encoding="utf-8") as f:
                json.dump(compiled, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[COMPILER] Erro ao salvar compilado: {e}")

    def _compute_manifest_stats(self) -> dict:
        """Computa stats do manifesto."""
        total_kw = sum(f.get("generated", {}).get("keywords", 0) for f in self.manifest.get("files", {}).values())
        total_fr = sum(f.get("generated", {}).get("filter_rules", 0) for f in self.manifest.get("files", {}).values())
        total_ge = sum(f.get("generated", {}).get("groq_examples", 0) for f in self.manifest.get("files", {}).values())
        total_sy = sum(f.get("generated", {}).get("synonyms", 0) for f in self.manifest.get("files", {}).values())
        return {
            "total_files": len(self.manifest.get("files", {})),
            "total_keywords": total_kw,
            "total_filter_rules": total_fr,
            "total_groq_examples": total_ge,
            "total_synonyms": total_sy,
        }

    # ============================================================
    # DISPLAY
    # ============================================================

    def _print_dry_run(self, all_files: list, to_process: list):
        """Mostra o que seria processado."""
        print(f"\n[DRY RUN] {len(to_process)}/{len(all_files)} arquivos seriam processados:\n")

        by_type = {}
        for f in to_process:
            by_type.setdefault(f["doc_type"], []).append(f)

        for dtype, files in sorted(by_type.items()):
            print(f"  {dtype} ({len(files)}):")
            for f in files:
                status = "NOVO" if f["relative"] not in self.manifest.get("files", {}) else "ALTERADO"
                print(f"    [{status}] {f['relative']} ({f['lines']} linhas)")

        already = len(all_files) - len(to_process)
        if already > 0:
            print(f"\n  {already} arquivo(s) ja processados (hash igual).")

        if not self.groq_key:
            print(f"\n  AVISO: GROQ_API_KEY nao configurado — usaria fallback local (regex).")
        else:
            print(f"\n  Modelo: {GROQ_MODEL} | Max requests: {MAX_REQUESTS_PER_RUN}")


# ============================================================
# CLI
# ============================================================

async def main():
    parser = argparse.ArgumentParser(description="Knowledge Compiler - auto-gera inteligencia para o Smart Agent")
    parser.add_argument("--full", action="store_true", help="Processa TODOS os arquivos (ignora cache)")
    parser.add_argument("--dry-run", action="store_true", help="Mostra o que faria sem alterar nada")
    parser.add_argument("--verbose", action="store_true", help="Output detalhado")
    parser.add_argument("--report", action="store_true", help="Relatorio do compilado existente")
    args = parser.parse_args()

    # Carregar .env
    env_path = _ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    compiler = KnowledgeCompiler()

    if args.report:
        compiler.report()
        return

    stats = await compiler.compile(full=args.full, dry_run=args.dry_run, verbose=args.verbose)

    if not args.dry_run and stats.get("processed", 0) > 0:
        print(f"\nPara ver o relatorio: python -m src.llm.knowledge_compiler --report")


if __name__ == "__main__":
    asyncio.run(main())
