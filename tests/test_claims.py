"""Claims-layer integration test against the Atlas sandbox.

Asserts: no double-claims under concurrency, full drain, and reaper requeue
after a simulated worker death. Run: .venv/bin/pytest tests/test_claims.py -v
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import timedelta

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("MONGODB_URI"), reason="MONGODB_URI not set")


@pytest.fixture()
def run_id():
    from core.db import TICKETS, coll

    rid = f"test-{uuid.uuid4().hex[:8]}"
    yield rid
    coll(TICKETS).delete_many({"run_id": rid})


def seed_tickets(run_id: str, n: int):
    from core.claims import now
    from core.db import TICKETS, coll

    coll(TICKETS).insert_many(
        {
            "run_id": run_id,
            "title": f"fake-{i}",
            "status": "ready",
            "priority": 1,
            "deps": [],
            "created_at": now(),
        }
        for i in range(n)
    )


def test_no_double_claims_and_full_drain(run_id):
    from core.claims import claim_next, complete

    seed_tickets(run_id, 10)
    claimed: list[tuple[str, str]] = []
    lock = threading.Lock()

    def worker(wid: str):
        while True:
            t = claim_next(run_id, wid)
            if t is None:
                return
            with lock:
                claimed.append((str(t["_id"]), wid))
            complete(t["_id"], wid, status="done")

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    ids = [c[0] for c in claimed]
    assert len(ids) == 10, f"expected 10 claims, got {len(ids)}"
    assert len(set(ids)) == 10, "double-claim detected"


def test_reaper_requeues_dead_worker(run_id):
    from core.claims import claim_next, now, reap
    from core.db import TICKETS, coll

    seed_tickets(run_id, 1)
    t = claim_next(run_id, "doomed-worker")
    assert t is not None

    # Simulate death: backdate the lease past expiry
    coll(TICKETS).update_one({"_id": t["_id"]}, {"$set": {"lease_until": now() - timedelta(seconds=5)}})

    assert reap(run_id) == 1
    fresh = coll(TICKETS).find_one({"_id": t["_id"]})
    assert fresh["status"] == "ready"
    assert "worker_id" not in fresh
    assert fresh["reap_count"] == 1


def test_frontier_promotion(run_id):
    from core.claims import now, refresh_frontier
    from core.db import TICKETS, coll

    tickets = coll(TICKETS)
    a = tickets.insert_one({"run_id": run_id, "title": "a", "status": "done", "deps": [], "priority": 1, "created_at": now()}).inserted_id
    b = tickets.insert_one({"run_id": run_id, "title": "b", "status": "blocked", "deps": [a], "priority": 1, "created_at": now()}).inserted_id
    c = tickets.insert_one({"run_id": run_id, "title": "c", "status": "blocked", "deps": [a, b], "priority": 1, "created_at": now()}).inserted_id

    assert refresh_frontier(run_id) == 1  # only b (its dep a is done)
    assert tickets.find_one({"_id": b})["status"] == "ready"
    assert tickets.find_one({"_id": c})["status"] == "blocked"
