"""Procurator — the PM. Holds the mandate, runs the sprint loop:
reap dead leases, promote the frontier, detect sprint completion, run the
standup (a compact state summary written as an event), and close out.
Phase E adds the Dispatch Governor on top of this loop.
"""
from __future__ import annotations

import time

from core.agents.base import AgentBase, now
from core.claims import counts, reap, refresh_frontier
from core.governor import retune
from core.db import RUNS, SPRINTS, TICKETS, coll
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
        if state != getattr(self, "_last_state", None):
            self._last_state = dict(state)
            try:
                from core.llm import ask

                report = ask(
                    self.agent_id,
                    "You are Procurator writing a standup for the stakeholder. "
                    "Exactly 3 short lines: DONE, IN PROGRESS, RISKS/BUDGET. Plain text.",
                    f"State: {state}. Budget total: {self.cfg.budget_total_tokens}.",
                    sprint=self.sprint, max_tokens=150,
                )
                self.log("standup.report", report.strip())
            except Exception:
                pass
        return state

    def route(self) -> int:
        """Bump priority on tickets blocking the longest dependency chain."""
        tickets = list(coll(TICKETS).find(
            {"run_id": self.run_id, "status": {"$nin": ["done", "failed"]}},
            {"deps": 1, "priority": 1, "title": 1}))
        if not tickets:
            return 0
        by_id = {t["_id"]: t for t in tickets}
        depth: dict = {}

        def chain(tid) -> int:
            if tid in depth:
                return depth[tid]
            t = by_id.get(tid)
            depth[tid] = 1 + max((chain(d) for d in (t or {}).get("deps", []) if d in by_id), default=0) if t else 0
            return depth[tid]

        # dependents count: how many open tickets sit behind each ticket
        blocking: dict = {}
        for t in tickets:
            for d in t.get("deps", []):
                blocking[d] = blocking.get(d, 0) + 1
        bumped = 0
        for tid, n in blocking.items():
            t = by_id.get(tid)
            if t and n >= 2 and t.get("priority", 1) < 1 + n:
                coll(TICKETS).update_one({"_id": tid}, {"$set": {"priority": 1 + n}})
                self.log("route.bump", f"{t.get('title', tid)} -> priority {1 + n} ({n} dependents)")
                bumped += 1
        return bumped

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
            self.route()
            retune(self.run_id, sprint)
            if tick % standup_every == 0:
                self.standup()
            if self.sprint_done():
                break
            tick += 1
            time.sleep(poll_seconds)

        if self.cfg.memory_enabled:
            from core.memory.scriba import Scriba

            scriba = Scriba()
            scriba.compact(sprint)
            scriba.distill(sprint)
            scriba.retro(sprint)

        final = self.standup()
        coll(SPRINTS).update_one(
            {"run_id": self.run_id, "sprint": sprint},
            {"$set": {"ended_at": now(), "status": "done", "summary": final}},
        )
        coll(RUNS).update_one({"run_id": self.run_id}, {"$set": {"status": "done", "summary": final}})
        self.log("sprint.done", f"sprint {sprint} closed", **final)
        try:
            from core.llm import ask
            from server.voice import _briefing, call_stakeholder

            report = ask(
                self.agent_id,
                "You are Procurator phoning the stakeholder after a sprint. Compose the "
                "spoken report: 4-6 sentences. Cover: what the project is, which features "
                "shipped this sprint, WHY each matters to the product goal, the verified "
                "test score, and what happens next. Spoken register, numbers in words, "
                "no lists. Ground everything in the briefing.",
                f"Sprint {sprint} just closed.\n{_briefing(self.run_id)}",
                sprint=sprint, max_tokens=350,
            )
            if call_stakeholder(" ".join(report.split())):
                self.log("voice.outbound", "called the stakeholder with the sprint report")
        except Exception:
            pass
        return final
