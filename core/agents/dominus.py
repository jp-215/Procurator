"""Dominus — the synthetic stakeholder. At a sprint boundary it injects a
calibrated scope change (target/DRIFT.md): mandate v2, amended SPEC.md in the
working tree, and a stakeholder message on the bus. The drift is fixed text so
the hidden wave-2 suite grades it exactly.
"""
from __future__ import annotations

from pathlib import Path

from core.agents.base import AgentBase, now
from core.db import MANDATE, SPRINTS, STAKEHOLDER_MSGS, coll
from core.paths import spec_path

ROOT = Path(__file__).resolve().parent.parent.parent
DRIFT = ROOT / "target" / "DRIFT.md"


class Dominus(AgentBase):
    role = "dominus"

    def inject_drift(self, sprint: int) -> None:
        self.sprint = sprint
        drift = DRIFT.read_text()
        prev = coll(MANDATE).find_one({"run_id": self.run_id}, sort=[("version", -1)])
        new_spec = prev["spec"].rstrip() + "\n\n" + drift
        spec_path().write_text(new_spec)  # workers read the file; keep it in sync
        coll(MANDATE).insert_one({
            "run_id": self.run_id, "version": prev["version"] + 1, "spec": new_spec,
            "goal": prev.get("goal", ""), "drift": True, "created_at": now(),
        })
        msg = ("Scope change: we need refund support (AC-26 through AC-32) on top of the "
               "existing lifecycle. Nothing that passes today may break.")
        coll(STAKEHOLDER_MSGS).insert_one({
            "run_id": self.run_id, "from": "dominus", "sprint": sprint,
            "text": msg, "created_at": now(),
        })
        coll(SPRINTS).insert_one({
            "run_id": self.run_id, "sprint": sprint, "status": "pending", "created_at": now(),
        })
        self.log("drift.injected", f"mandate v{prev['version'] + 1}: refunds (AC-26..32)")
