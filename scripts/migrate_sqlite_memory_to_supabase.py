#!/usr/bin/env python3
"""One-time import of the former SQLite memory file into Supabase Postgres."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from packages.config.env import load_dotenv
from packages.memory.postgres import SupabaseMemoryService
from packages.memory.service import MemoryService, SourceEvent


def counts(memory: MemoryService) -> dict[str, int]:
    return {
        "items": len(memory._items),
        "revisions": sum(len(items) for items in memory._revisions.values()),
        "proposals": len(memory._proposals),
        "source_events": len(memory._source_events),
        "claims": len(memory._claims),
        "directives": len(memory._behavioral_directives),
        "audit_events": len(memory._audit_events),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, default=Path("data/memory.sqlite3"))
    parser.add_argument("--allow-merge", action="store_true", help="upsert into a non-empty Siduri dataset")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(Path(".env"))
    if not args.sqlite.is_file():
        raise SystemExit(f"SQLite source does not exist: {args.sqlite}")

    source = MemoryService(args.sqlite)
    source_counts = counts(source)
    print("SQLite source:", source_counts, flush=True)
    if args.dry_run:
        return

    dsn = os.getenv("SIDURI_SUPABASE_DATABASE_URL", "").strip()
    if not dsn:
        raise SystemExit("Set SIDURI_SUPABASE_DATABASE_URL first.")

    target = SupabaseMemoryService.connect(dsn)
    if any(counts(target).values()) and not args.allow_merge:
        raise SystemExit("Supabase memory is not empty; use --allow-merge to upsert intentionally.")

    for event in source._source_events.values():
        target.add_source_event(event)
    for item in source._items.values():
        target._items[item.memory_id] = item
        target._persist_item(item)
    for revisions in source._revisions.values():
        for revision in revisions:
            target._revisions.setdefault(revision.memory_id, []).append(revision)
            target._persist_revision(revision)
    for proposal in source._proposals.values():
        target._proposals[proposal.proposal_id] = proposal
        target._persist_proposal(proposal)
    for claim in sorted(source._claims.values(), key=lambda item: item.asserted_at):
        target._claims[claim.claim_id] = claim
        target._persist_claim(claim)
    for directive in sorted(source._behavioral_directives.values(), key=lambda item: item.created_at):
        if directive.source_event_id not in target._source_events:
            target.add_source_event(SourceEvent(
                event_id=directive.source_event_id,
                source_type=directive.source_type,
                occurred_at=directive.created_at,
                payload={"migrated_directive_id": directive.directive_id},
            ))
        target.add_behavioral_directive(directive)
    target._persist_audit_events(tuple(
        (f"legacy_sqlite_audit_{index:08d}", event)
        for index, event in enumerate(source._audit_events, start=1)
    ))

    reloaded = SupabaseMemoryService.connect(dsn)
    target_counts = counts(reloaded)
    print("Supabase target:", target_counts, flush=True)
    mismatches = {
        key: (source_counts[key], target_counts[key])
        for key in source_counts
        if source_counts[key] != target_counts[key]
    }
    if mismatches:
        raise SystemExit(f"Migration count verification failed: {mismatches}")
    print("Migration verified.", flush=True)


if __name__ == "__main__":
    main()
