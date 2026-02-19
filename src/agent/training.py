"""
MMarra Data Hub - Treinamento Diário.
Compilação automática + revisão de aliases via scheduler.
Extraído de smart_agent.py na refatoração modular.
"""

import os
import asyncio
from datetime import datetime

TRAINING_HOUR = int(os.getenv("TRAINING_HOUR", "3"))


async def daily_training(force: bool = False) -> dict:
    """Executa compilação + review de aliases via pool_train.
    Chamado automaticamente pelo scheduler ou manualmente via CLI/endpoint."""
    from src.llm.knowledge_compiler import KnowledgeCompiler
    from src.core.groq_client import pool_train

    stats = {"compiler": {}, "aliases_reviewed": 0, "error": None}
    print(f"[TRAIN] Iniciando treinamento {'(forcado)' if force else '(scheduled)'} ...")

    # 1. Knowledge Compiler
    try:
        compiler = KnowledgeCompiler(groq_api_key=pool_train.get_key() if pool_train.available else None)
        result = await compiler.compile(full=force, dry_run=False, verbose=True)
        stats["compiler"] = result

        if result.get("processed", 0) > 0:
            from src.agent.scoring import reload_compiled
            reload_compiled()
            print(f"[TRAIN] Knowledge recarregado ({result['processed']} docs)")
    except Exception as e:
        stats["compiler"] = {"error": str(e)}
        print(f"[TRAIN] Compiler falhou: {e}")

    # 2. Alias review (aprovar sugestoes de alta confianca)
    try:
        from src.llm.alias_resolver import AliasResolver
        ar = AliasResolver()
        suggestions = ar.get_suggestions("pending")
        auto_approved = 0
        for s in suggestions:
            if s.get("confidence", 0) >= 0.85 and s.get("count", 0) >= 3:
                ar.approve_suggestion(s["apelido"], nome_real=s.get("nome_real"), codprod=s.get("codprod"))
                auto_approved += 1
                print(f"[TRAIN] Auto-aprovado alias: {s['apelido']} -> {s.get('nome_real', s.get('codprod'))}")
        stats["aliases_reviewed"] = auto_approved
    except Exception as e:
        print(f"[TRAIN] Alias review falhou: {e}")

    # 3. Elasticsearch sync incremental
    try:
        from src.elastic.search import ElasticSearchEngine
        from src.elastic.sync import ElasticSync
        es_search = ElasticSearchEngine()
        health = await es_search.health()
        if health.get("status") != "offline":
            from src.llm.query_executor import SafeQueryExecutor
            es_sync = ElasticSync(SafeQueryExecutor())
            sync_result = await es_sync.incremental_sync()
            stats["elastic_sync"] = sync_result
            print(f"[TRAIN] Elastic sync: {sync_result}")
        else:
            print(f"[TRAIN] Elastic offline, sync ignorado")
    except Exception as e:
        print(f"[TRAIN] Elastic sync falhou: {e}")

    print(f"[TRAIN] Concluido: compiler={stats['compiler'].get('processed', 0)} docs, aliases={stats['aliases_reviewed']}")
    return stats


async def _training_scheduler():
    """Loop infinito que roda daily_training() no horario configurado."""
    while True:
        now = datetime.now()
        target = now.replace(hour=TRAINING_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target = target.replace(day=target.day + 1)
        wait_seconds = (target - now).total_seconds()
        print(f"[TRAIN] Proximo treino em {wait_seconds/3600:.1f}h ({target.strftime('%d/%m %H:%M')})")
        await asyncio.sleep(wait_seconds)
        try:
            await daily_training()
        except Exception as e:
            print(f"[TRAIN] Erro no scheduler: {e}")
