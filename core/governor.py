"""Dispatch Governor — the credit harness.

One `governor` doc per run holds the dials; Procurator writes them each loop
tick from hard signals, workers read them before claiming and dispatching:

  width        how many tickets may be claimed concurrently
  depth_tokens max_tokens granted to an attempt-0 worker call

Every change is logged to `dispatch_log` with the inputs that caused it, so
scaling is auditable evidence, not vibes. The escalation ladder (attempt ->
model/depth/memory) lives in the worker; its levels come from here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.config import config
from core.db import DISPATCH_LOG, TICKETS, coll

GOVERNOR = "governor"

DEFAULTS = {"width": 2, "depth_tokens": 4096}

# escalation ladder: per-attempt dispatch policy (worker consumes this)
LADDER = [
    {"model": "worker", "depth_mult": 1, "memory": "targeted"},   # attempt 0: lean
    {"model": "worker", "depth_mult": 2, "memory": "full"},       # attempt 1: insured
    {"model": "procurator", "depth_mult": 2, "memory": "full"},   # attempt 2: heavy
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def read(run_id: str) -> dict[str, Any]:
    doc = coll(GOVERNOR).find_one({"run_id": run_id})
    return {**DEFAULTS, **(doc or {})}


def ladder_rung(attempts: int) -> dict[str, Any]:
    return LADDER[min(attempts, len(LADDER) - 1)]


def retune(run_id: str, sprint: int) -> dict[str, Any]:
    """Recompute dials from frontier, budget, and marginal yield. PM-only."""
    from core.metrics import marginal_yield, tokens_spent

    cfg = config()
    cur = read(run_id)
    frontier = coll(TICKETS).count_documents({"run_id": run_id, "status": "ready"})
    in_flight = coll(TICKETS).count_documents({"run_id": run_id, "status": {"$in": ["claimed", "grading", "review"]}})
    spent = tokens_spent(run_id)
    remaining_frac = max(0.0, 1 - spent / cfg.budget_total_tokens)
    yield_now = marginal_yield(run_id, sprint)

    # width: enough to drain the frontier, capped by budget posture
    width = min(cfg.width_max, max(1, frontier + in_flight))
    reason = f"frontier={frontier} in_flight={in_flight}"
    if remaining_frac < 0.2:
        width = 1
        reason += f" | budget guard ({remaining_frac:.0%} left)"
    elif yield_now is not None and yield_now <= 0 and spent > 20_000:
        width = max(1, width - 1)
        reason += f" | yield flat ({yield_now:.2e})"
    else:
        reason += f" | yield={'n/a' if yield_now is None else f'{yield_now:.2e}'}"

    depth = int(DEFAULTS["depth_tokens"] * (2 if remaining_frac > 0.5 else 1))

    if width != cur.get("width") or depth != cur.get("depth_tokens"):
        coll(GOVERNOR).update_one(
            {"run_id": run_id},
            {"$set": {"width": width, "depth_tokens": depth, "reason": reason, "updated_at": _now()}},
            upsert=True,
        )
        coll(DISPATCH_LOG).insert_one({
            "run_id": run_id, "sprint": sprint, "width": width, "depth_tokens": depth,
            "inputs": {"frontier": frontier, "in_flight": in_flight, "tokens_spent": spent,
                       "remaining_frac": round(remaining_frac, 3),
                       "marginal_yield": yield_now},
            "reason": reason, "created_at": _now(),
        })
    return {"width": width, "depth_tokens": depth, "reason": reason}
