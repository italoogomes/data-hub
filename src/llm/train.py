"""
CLI para treino manual do Smart Agent.

Uso:
    python -m src.llm.train          # Incremental (so novos/alterados)
    python -m src.llm.train --full   # Reprocessa tudo
    python -m src.llm.train --pools  # Mostra status dos pools Groq
"""

import asyncio
import os
import sys
from pathlib import Path

# Setup paths
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

# Carregar .env
env_path = _ROOT / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Smart Agent - Treinamento manual")
    parser.add_argument("--full", action="store_true", help="Reprocessar tudo (ignora cache)")
    parser.add_argument("--pools", action="store_true", help="Mostrar status dos pools Groq")
    args = parser.parse_args()

    if args.pools:
        from src.llm.smart_agent_v3_backup import pool_classify, pool_narrate, pool_train
        print("\n=== GROQ POOLS STATUS ===\n")
        for name, pool in [("classify", pool_classify), ("narrate", pool_narrate), ("train", pool_train)]:
            s = pool.stats()
            print(f"  {name} ({s['keys']} keys, {s['in_cooldown']} em cooldown):")
            print(f"    uso total:  {s['usage_total']}")
            print(f"    uso hoje:   {s['usage_today']}")
            if s['errors']:
                print(f"    erros:      {s['errors']}")
            print()
        return

    from src.llm.smart_agent_v3_backup import daily_training
    stats = await daily_training(force=args.full)
    print(f"\nResultado: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
