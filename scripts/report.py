"""Pitch numbers, straight from the ledger. Every figure is a Mongo aggregation.

Usage: .venv/bin/python scripts/report.py [run ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import DISPATCH_LOG, METRICS, PLAYBOOKS, RUNS, VERDICTS, coll  # noqa: E402
from core.metrics import latest_pass_rate, tokens_spent  # noqa: E402


def row(run: str) -> dict:
    p, t = latest_pass_rate(run)
    v = list(coll(VERDICTS).find({"run_id": run}))
    rej = sum(1 for x in v if not x["accepted"])
    scriba = next(iter(coll(METRICS).aggregate([
        {"$match": {"meta.run_id": run, "meta.agent": {"$regex": "^scriba"}}},
        {"$group": {"_id": None, "t": {"$sum": {"$add": ["$tokens_in", "$tokens_out"]}}}}])), {}).get("t", 0)
    hits = next(iter(coll(METRICS).aggregate([
        {"$match": {"meta.run_id": run}},
        {"$group": {"_id": None, "h": {"$sum": "$retrieval_hits"}}}])), {}).get("h", 0)
    sprints = sorted(coll(METRICS).distinct("meta.sprint", {"meta.run_id": run}))
    return {"run": run, "pass": f"{p}/{t}", "verdicts": len(v), "rejects": rej,
            "tokens": tokens_spent(run), "scriba": scriba, "hits": hits,
            "sprints": len(sprints), "dispatch_changes": coll(DISPATCH_LOG).count_documents({"run_id": run})}


def main() -> None:
    runs = sys.argv[1:] or [d["run_id"] for d in coll(RUNS).find().sort("created_at", 1)]
    print(f"{'run':16} {'pass':8} {'verd':5} {'rej':4} {'tokens':>9} {'scriba':>8} {'hits':>5} {'spr':>4} {'gov':>4}")
    for r in runs:
        d = row(r)
        print(f"{d['run']:16} {d['pass']:8} {d['verdicts']:<5} {d['rejects']:<4} "
              f"{d['tokens']:>9,} {d['scriba']:>8,} {d['hits']:>5} {d['sprints']:>4} {d['dispatch_changes']:>4}")
    print(f"\nplaybooks on file: {coll(PLAYBOOKS).count_documents({})} "
          f"(roles: {coll(PLAYBOOKS).count_documents({'ticket_class': {'$regex': '^role:'}})})")


if __name__ == "__main__":
    main()
