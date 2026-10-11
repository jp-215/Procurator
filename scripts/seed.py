"""Seed the mandate from target/SPEC.md and open sprint 0.

Usage: .venv/bin/python scripts/seed.py [--fresh]
--fresh wipes all documents for the current RUN_ID first (not other runs).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import config  # noqa: E402
from core.db import ALL_COLLECTIONS, MANDATE, SPRINTS, STAKEHOLDER_MSGS, coll  # noqa: E402

from core.paths import spec_path  # noqa: E402


def main() -> None:
    cfg = config()
    now = datetime.now(timezone.utc)

    if "--fresh" in sys.argv:
        for name in ALL_COLLECTIONS:
            coll(name).delete_many({"run_id": cfg.run_id})
            coll(name).delete_many({"meta.run_id": cfg.run_id})  # metrics ts
        print(f"wiped run_id={cfg.run_id}")

    spec = spec_path().read_text()
    coll(MANDATE).insert_one({
        "run_id": cfg.run_id, "version": 1, "spec": spec,
        "goal": "Implement ordersvc to satisfy all 25 acceptance criteria",
        "invariants": ["never rename spec-named symbols", "no regressions pass the gate"],
        "created_at": now,
    })
    coll(STAKEHOLDER_MSGS).insert_one({
        "run_id": cfg.run_id, "from": "dominus", "sprint": 0,
        "text": "Mandate issued: implement the orders service per SPEC.md. "
                "Budget is fixed; the hidden suite is the judge.",
        "created_at": now,
    })
    coll(SPRINTS).insert_one({
        "run_id": cfg.run_id, "sprint": 0, "status": "pending", "created_at": now,
    })
    print(f"mandate v1 seeded for run_id={cfg.run_id} ({len(spec)} chars of spec)")


if __name__ == "__main__":
    main()
