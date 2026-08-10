#!/usr/bin/env python3
"""Apply and verify Siduri's Supabase memory schema."""
from __future__ import annotations

import os
from pathlib import Path
from packages.config.env import load_dotenv
from packages.memory.postgres import SupabaseMemoryService, normalize_supabase_dsn


def main() -> None:
    load_dotenv(Path(".env"))
    dsn = os.getenv("SIDURI_SUPABASE_DATABASE_URL", "").strip()
    if not dsn:
        raise SystemExit("Set SIDURI_SUPABASE_DATABASE_URL first.")

    try:
        import psycopg
    except ImportError as error:
        raise SystemExit("Install dependencies with .venv/bin/pip install -e '.[platforms]'.") from error

    migration = Path("migrations/002_memory.sql").read_text(encoding="utf-8")
    connection = psycopg.connect(normalize_supabase_dsn(dsn))
    try:
        with connection.cursor() as cursor:
            cursor.execute(migration)
        connection.commit()
    finally:
        connection.close()

    memory = SupabaseMemoryService.connect(dsn)
    try:
        print("Supabase memory schema is ready.")
        print(
            "Siduri dataset:",
            {
                "items": len(memory._items),
                "proposals": len(memory._proposals),
                "claims": len(memory._claims),
                "directives": len(memory._behavioral_directives),
            },
        )
    finally:
        memory.close()


if __name__ == "__main__":
    main()
