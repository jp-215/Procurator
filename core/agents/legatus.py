"""Legatus — engineering lead. Decomposes the mandate's spec into a ticket DAG."""
from __future__ import annotations

from pathlib import Path

from core.agents.base import AgentBase, now
from core.db import MANDATE, STAKEHOLDER_MSGS, TICKETS, coll
from core.llm import ask_json
from core.memory.provenance import record_decision

SYSTEM = """You are Legatus, the engineering lead of an agent mesh. Decompose a
software spec into implementation tickets forming a dependency DAG.

Rules:
- One ticket per cohesive unit of work (usually one module). 4-8 tickets total.
- Each ticket: {"title": str, "module": str (filename, e.g. "retry.py"),
  "ac_refs": ["AC-20", ...], "description": str (what to implement, crisp),
  "deps": [int, ...] (indices into this same list, tickets that must land first),
  "priority": int (higher = sooner), "ticket_class": str (short category)}
- deps must be acyclic and minimal: only true build-order dependencies
  (e.g. orders.py uses store.py and auth.py).
- Cover EVERY AC in the spec across the tickets' ac_refs.
- ac_refs must list ONLY ACs this ticket alone can make pass. Shared scaffolding
  (exception types, base models) gets ac_refs: [] — its correctness is proven by
  the tickets that use it, never by itself."""


class Legatus(AgentBase):
    role = "legatus"

    def decompose(self, sprint: int = 0) -> int:
        self.sprint = sprint
        mandate = coll(MANDATE).find_one({"run_id": self.run_id}, sort=[("version", -1)])
        spec = mandate["spec"]
        self.log("decompose.start", f"mandate v{mandate['version']}")

        delta_note = ""
        if sprint > 0:
            delta_note = ("\nIMPORTANT: this is a SCOPE CHANGE sprint. The codebase already "
                          "satisfies every AC from earlier spec sections. Create tickets ONLY "
                          "for the newest scope-change section; 1-3 tickets, each touching the "
                          "minimum set of modules. Preserving existing behavior is part of done.")
        tickets = ask_json(
            self.agent_id, SYSTEM + delta_note + self.role_guidance(), f"Spec:\n\n{spec}",
            model=self.cfg.procurator_model, sprint=self.sprint, max_tokens=4096,
        )
        if isinstance(tickets, dict):  # model wrapped the list in an object
            tickets = next((v for v in tickets.values() if isinstance(v, list)), [])
        if not tickets:
            raise ValueError("Legatus produced no tickets")
        docs = []
        for i, t in enumerate(tickets):
            docs.append({
                "run_id": self.run_id, "sprint": self.sprint,
                "title": t["title"], "module": t["module"],
                "ac_refs": t.get("ac_refs", []), "description": t["description"],
                "ticket_class": t.get("ticket_class", t["module"]),
                "priority": t.get("priority", 1), "deps_idx": t.get("deps", []),
                "status": "pending", "attempts": 0, "created_at": now(),
            })
        ids = coll(TICKETS).insert_many(docs).inserted_ids
        # resolve index-deps to ObjectIds, mark roots ready
        for i, (tid, t) in enumerate(zip(ids, docs)):
            deps = [ids[j] for j in t["deps_idx"] if 0 <= j < len(ids) and j != i]
            coll(TICKETS).update_one(
                {"_id": tid},
                {"$set": {"deps": deps, "status": "ready" if not deps else "blocked"},
                 "$unset": {"deps_idx": ""}},
            )
        msg = coll(STAKEHOLDER_MSGS).find_one({"run_id": self.run_id}, sort=[("created_at", -1)])
        dec = record_decision(
            self.run_id, self.agent_id, "decomposition",
            f"split mandate v{mandate['version']} into {len(ids)} tickets",
            caused_by=[msg["_id"]] if msg else [],
            ticket_ids=[str(i) for i in ids], mandate_version=mandate["version"],
        )
        coll(TICKETS).update_many({"_id": {"$in": ids}}, {"$set": {"decision_id": dec}})
        self.log("decompose.done", f"{len(ids)} tickets", ticket_ids=[str(i) for i in ids])
        return len(ids)
