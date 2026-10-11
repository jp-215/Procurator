"""Atomic ticket claiming, leases, heartbeats, and the reaper.

The whole scheduler is these four functions + Mongo's atomicity:
  claim_next()  -- one atomic findOneAndUpdate; no lock server, no double-claims
  renew_lease() -- worker heartbeat extends its lease while it works
  reap()        -- requeue tickets whose lease expired (worker died)
  frontier()    -- tickets whose deps are all done (the ready set)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pymongo import ReturnDocument

from core.config import config
from core.db import TICKETS, coll


def now() -> datetime:
    return datetime.now(timezone.utc)


def refresh_frontier(run_id: str) -> int:
    """Promote blocked tickets whose deps are all done to status=ready."""
    tickets = coll(TICKETS)
    done_ids = {t["_id"] for t in tickets.find({"run_id": run_id, "status": "done"}, {"_id": 1})}
    blocked = tickets.find({"run_id": run_id, "status": "blocked"}, {"_id": 1, "deps": 1})
    promoted = 0
    for t in blocked:
        if set(t.get("deps", [])) <= done_ids:
            r = tickets.update_one({"_id": t["_id"], "status": "blocked"}, {"$set": {"status": "ready"}})
            promoted += r.modified_count
    return promoted


def claim_next(run_id: str, worker_id: str) -> dict[str, Any] | None:
    """Atomically claim the highest-priority ready ticket. None if none ready."""
    lease = now() + timedelta(seconds=config().lease_seconds)
    return coll(TICKETS).find_one_and_update(
        {"run_id": run_id, "status": "ready"},
        {"$set": {"status": "claimed", "worker_id": worker_id, "lease_until": lease, "claimed_at": now()}},
        sort=[("priority", -1), ("created_at", 1)],
        return_document=ReturnDocument.AFTER,
    )


def renew_lease(ticket_id: Any, worker_id: str) -> bool:
    lease = now() + timedelta(seconds=config().lease_seconds)
    r = coll(TICKETS).update_one(
        {"_id": ticket_id, "worker_id": worker_id, "status": "claimed"},
        {"$set": {"lease_until": lease}},
    )
    return r.modified_count == 1


def complete(ticket_id: Any, worker_id: str, status: str = "review") -> bool:
    """Worker hands the ticket to Censor (status=review) or marks failure."""
    r = coll(TICKETS).update_one(
        {"_id": ticket_id, "worker_id": worker_id, "status": "claimed"},
        {"$set": {"status": status, "completed_at": now()}, "$unset": {"lease_until": ""}},
    )
    return r.modified_count == 1


def reap(run_id: str) -> int:
    """Requeue tickets whose worker's lease expired. Run by Procurator's loop."""
    r = coll(TICKETS).update_many(
        {"run_id": run_id, "status": "claimed", "lease_until": {"$lt": now()}},
        {
            "$set": {"status": "ready"},
            "$unset": {"worker_id": "", "lease_until": ""},
            "$inc": {"reap_count": 1},
        },
    )
    return r.modified_count


def counts(run_id: str) -> dict[str, int]:
    pipeline = [
        {"$match": {"run_id": run_id}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]
    return {row["_id"]: row["n"] for row in coll(TICKETS).aggregate(pipeline)}
