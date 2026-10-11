"""Quaestor's write path: one metrics doc per agent turn, plus aggregations.

metrics is a time series collection: {ts, meta:{run_id, sprint, agent, ticket},
tokens_in, tokens_out, retrieval_hits, tests_passed, tests_total, verdict}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.db import METRICS, coll


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_turn(
    *, run_id: str, agent: str, sprint: int = 0, ticket: str | None = None,
    tokens_in: int = 0, tokens_out: int = 0, retrieval_hits: int = 0,
    tests_passed: int | None = None, tests_total: int | None = None,
    verdict: str | None = None,
) -> None:
    doc: dict[str, Any] = {
        "ts": _now(),
        "meta": {"run_id": run_id, "sprint": sprint, "agent": agent, "ticket": ticket},
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "retrieval_hits": retrieval_hits,
    }
    if tests_passed is not None:
        doc["tests_passed"] = tests_passed
        doc["tests_total"] = tests_total
    if verdict:
        doc["verdict"] = verdict
    coll(METRICS).insert_one(doc)


def tokens_spent(run_id: str, sprint: int | None = None) -> int:
    match: dict[str, Any] = {"meta.run_id": run_id}
    if sprint is not None:
        match["meta.sprint"] = sprint
    rows = list(coll(METRICS).aggregate([
        {"$match": match},
        {"$group": {"_id": None, "t": {"$sum": {"$add": ["$tokens_in", "$tokens_out"]}}}},
    ]))
    return rows[0]["t"] if rows else 0


def latest_pass_rate(run_id: str) -> tuple[int, int]:
    row = coll(METRICS).find_one(
        {"meta.run_id": run_id, "tests_total": {"$gt": 0}},
        sort=[("ts", -1)],
    )
    return (row["tests_passed"], row["tests_total"]) if row else (0, 0)


def marginal_yield(run_id: str, sprint: int) -> float | None:
    """M2: newly passing tests this sprint / tokens spent this sprint."""
    spent = tokens_spent(run_id, sprint)
    if spent == 0:
        return None
    rows = list(coll(METRICS).find(
        {"meta.run_id": run_id, "meta.sprint": sprint, "tests_total": {"$gt": 0}},
        sort=[("ts", 1)],
    ))
    if not rows:
        return None
    delta = rows[-1]["tests_passed"] - rows[0]["tests_passed"]
    return max(delta, 0) / spent
