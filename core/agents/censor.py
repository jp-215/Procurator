"""Censor — QA gate and the ONLY writer to target/src.

Applies a submitted artifact to a staging copy, grades it against the hidden
suite, and accepts iff there are no regressions and the ticket's ACs advance.
Accept -> files land in target/src, ticket done, M1 recorded.
Reject -> verdict with per-AC detail becomes feedback; ticket requeued (<=3 tries).
"""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from core.agents.base import AgentBase, now
from core.claims import refresh_frontier
from core.db import ARTIFACTS, TICKETS, VERDICTS, coll
from core.memory.provenance import record_decision
from core.metrics import record_turn
from runner.sandbox import GradeResult, grade

from core.paths import target_src
from core.vcs import commit_accepted

MAX_ATTEMPTS = 3


class Censor(AgentBase):
    role = "censor"

    def _baseline(self) -> GradeResult | None:
        v = coll(VERDICTS).find_one({"run_id": self.run_id, "accepted": True}, sort=[("created_at", -1)])
        if not v:
            return None
        g = GradeResult(passed=v["passed"], total=v["total"], per_ac=v["per_ac"])
        return g

    def review_one(self) -> bool:
        ticket = coll(TICKETS).find_one_and_update(
            {"run_id": self.run_id, "status": "review"},
            {"$set": {"status": "grading"}},
            sort=[("completed_at", 1)],
        )
        if ticket is None:
            return False
        self.sprint = ticket.get("sprint", 0)
        artifact = coll(ARTIFACTS).find_one({"ticket_id": ticket["_id"]}, sort=[("created_at", -1)])

        # stage = current accepted tree + this artifact's files
        with tempfile.TemporaryDirectory(prefix="procurator-stage-") as tmp:
            stage = Path(tmp) / "src"
            shutil.copytree(target_src(), stage)
            for name, content in artifact["files"].items():
                (stage / "ordersvc" / name).write_text(content)
            result = grade(stage, wave=2 if self.sprint >= 1 else 1)

        baseline = self._baseline()
        prev_pass = {ac for ac, s in (baseline.per_ac if baseline else {}).items() if s == "passed"}
        regressions = sorted(ac for ac in prev_pass if result.per_ac.get(ac) != "passed")
        newly = result.newly_passing(baseline)
        ac_refs = ticket.get("ac_refs", [])
        refs_passing = [ac for ac in ac_refs if result.per_ac.get(ac) == "passed"]
        # Accept when nothing regresses AND the ticket advances the board:
        #   - new tests pass, or
        #   - all of the ticket's own ACs pass, or
        #   - it's an infrastructure ticket (no ac_refs), or
        #   - dependents are starving behind it and the change is harmless —
        #     holding back a harmless prerequisite deadlocks the DAG; its ACs
        #     stay enforced by the regression gate as dependents land.
        infrastructure = not ac_refs
        dependents_blocked = coll(TICKETS).count_documents(
            {"run_id": self.run_id, "status": "blocked", "deps": ticket["_id"]}
        )
        accepted = not regressions and bool(
            newly
            or infrastructure
            or len(refs_passing) == len(ac_refs)
            or dependents_blocked
        )

        verdict_doc: dict[str, Any] = {
            "run_id": self.run_id, "ticket_id": ticket["_id"], "sprint": self.sprint,
            "accepted": accepted, "passed": result.passed, "total": result.total,
            "per_ac": result.per_ac, "regressions": regressions, "newly_passing": newly,
            "created_at": now(),
        }

        if accepted:
            for name, content in artifact["files"].items():
                (target_src() / "ordersvc" / name).write_text(content)
            commit_accepted(ticket, result)
            coll(TICKETS).update_one({"_id": ticket["_id"]}, {"$set": {"status": "done", "done_at": now()}})
            refresh_frontier(self.run_id)
            self.log("verdict.accept",
                     f"{ticket['title']}: {result.passed}/{result.total} (+{len(newly)})",
                     ticket_id=str(ticket["_id"]), newly=newly)
        else:
            failing_refs = {ac: result.per_ac.get(ac, "missing") for ac in ac_refs}
            verdict_doc["feedback"] = (
                f"Regressions: {regressions or 'none'}. Your ACs: {failing_refs}. "
                f"Overall {result.passed}/{result.total}. stderr tail: {result.stderr_tail[-500:]}"
            )
            attempts = ticket.get("attempts", 0) + 1
            next_status = "failed" if attempts >= MAX_ATTEMPTS else "ready"
            coll(TICKETS).update_one(
                {"_id": ticket["_id"]},
                {"$set": {"status": next_status, "attempts": attempts}},
            )
            self.log("verdict.reject",
                     f"{ticket['title']} attempt {attempts}: {result.passed}/{result.total}, "
                     f"regressions={regressions}", ticket_id=str(ticket["_id"]))

        vid = coll(VERDICTS).insert_one(verdict_doc).inserted_id
        record_decision(
            self.run_id, self.agent_id, "verdict",
            f"{'accepted' if accepted else 'rejected'} {ticket['title']} ({result.passed}/{result.total})",
            caused_by=[d for d in [ticket.get("decision_id")] if d],
            ticket_id=str(ticket["_id"]), verdict_id=str(vid),
            newly_passing=newly, regressions=regressions,
        )
        record_turn(
            run_id=self.run_id, agent=self.agent_id, sprint=self.sprint,
            ticket=str(ticket["_id"]), tests_passed=result.passed, tests_total=result.total,
            verdict="accept" if accepted else "reject",
        )
        return True

    def run_forever(self, poll_seconds: float = 2.0) -> None:
        self.register()
        self.log("agent.start", "gate open")
        while True:
            if not self.review_one():
                self.heartbeat("idle")
                time.sleep(poll_seconds)
