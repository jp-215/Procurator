"""Create collections + indexes on the Atlas sandbox. Idempotent.

Usage: .venv/bin/python scripts/bootstrap_atlas.py
Vector search indexes (atlas/indexes/*.json) are created separately — see --search.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import EPISODES, MEMORY, bootstrap, coll, db  # noqa: E402


def create_search_indexes() -> None:
    """Create the two vector-search indexes (requires Atlas, not local Mongo)."""
    from pymongo.operations import SearchIndexModel

    root = Path(__file__).resolve().parent.parent / "atlas" / "indexes"
    for fname, collection in [("search-episodes.json", EPISODES), ("search-memory.json", MEMORY)]:
        spec = json.loads((root / fname).read_text())
        existing = {ix["name"] for ix in coll(collection).list_search_indexes()}
        if spec["name"] in existing:
            print(f"  search index {spec['name']} on {collection}: exists")
            continue
        model = SearchIndexModel(definition={"fields": spec["fields"]}, name=spec["name"], type="vectorSearch")
        coll(collection).create_search_index(model)
        print(f"  search index {spec['name']} on {collection}: created (builds async)")


if __name__ == "__main__":
    created = bootstrap()
    print(f"db: {db().name}")
    print(f"collections created: {created or '(all existed)'}")
    print("standard indexes: ensured")
    if "--search" in sys.argv:
        create_search_indexes()
    else:
        print("skip vector indexes (pass --search once connected to Atlas)")
