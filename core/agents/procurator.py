"""Procurator — the PM. Holds the mandate, runs the sprint loop:
reap dead leases, promote the frontier, detect sprint completion, run the
standup (a compact state summary written as an event), and close out.
Phase E adds the Dispatch Governor on top of this loop.
"""
from __future__ import annotations

import time

from core.agents.base import AgentBase, now
from core.claims import counts, reap, refresh_frontier
from core.db import SPRINTS, TICKETS, coll
from core.metrics import latest_pass_rate, tokens_spent

TERMINAL = {"done", "failed"}


class Procurator(AgentBase):
    role = "procurator"

    def standup(self) -> dict:
        c = counts(self.run_id)
        passed, total = latest_pass_rate(self.run_id)
        spent = tokens_spent(self.run_id)
        state = {"tickets": c, "pass": f"{passed}/{total}", "tokens": spent}
        self.log("standup", f"pass {passed}/{total} | tickets {c} | {spent} tok", **state)
        return state

    def sprint_done(self) -> bool:
        c = counts(self.run_id)
        active = sum(v for k, v in c.items() if k not in TERMINAL)
        return active == 0 and sum(c.values()) > 0

    def run_sprint(self, sprint: int, poll_seconds: float = 5.0, standup_every: int = 6) -> dict:
        self.sprint = sprint
        self.register()
        coll(SPRINTS).update_one(
            {"run_id": self.run_id, "sprint": sprint},
            {"$set": {"started_at": now(), "status": "running"}},
            upsert=True,
        )
        tick = 0
        while True:
            reaped = reap(self.run_id)
            if reaped:
                self.log("reaper", f"requeued {reaped} expired lease(s)")
            refresh_frontier(self.run_id)
            if tick % standup_every == 0:
                self.standup()
            if self.sprint_done():
                break
            tick += 1
            time.sleep(poll_seconds)

        final = self.standup()
        coll(SPRINTS).update_one(
            {"run_id": self.run_id, "sprint": sprint},
            {"$set": {"ended_at": now(), "status": "done", "summary": final}},
        )
        self.log("sprint.done", f"sprint {sprint} closed", **final)
        return final
