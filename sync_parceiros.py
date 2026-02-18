"""Sync parceiros direto (sem API auth)."""
import asyncio
from src.elastic.sync import ElasticSync
from src.llm.query_executor import SafeQueryExecutor

async def run():
    executor = SafeQueryExecutor()
    sync = ElasticSync(executor)
    result = await sync.sync_partners(full=True)
    print(result)

asyncio.run(run())