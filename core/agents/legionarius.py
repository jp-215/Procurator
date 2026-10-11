"""Legionarius — stateless worker. Claims a ticket atomically, writes code as an
artifact (never touches target/ directly — Censor is the single merge point),
hands it to review. Kill it any time; the lease reaper requeues its work.
"""
from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any

from core.agents.base import AgentBase, now
from core.claims import claim_next, complete, renew_lease
from core.db import ARTIFACTS, VERDICTS, coll
from core.llm import BudgetExhausted, ask
from core.memory.recall import recall_for_ticket

from core.paths import spec_path, target_src

SYSTEM = """You are Legionarius, an implementation agent. You receive one ticket:
a module to implement against a spec excerpt, plus the current content of the
files in scope and any reviewer feedback from failed attempts.

Output format — one block per file you are writing (NO JSON, no markdown fences):

===FILE: <filename>===
<complete new file content>
===END===
NOTES: <one-line summary of your approach>

Rules:
- Return COMPLETE file contents, not diffs. Only files inside the ordersvc package.
- Implement exactly what the spec excerpt demands; honor exact signatures,
  exception types, and semantics. Do not rename anything the spec names.
- You may read-depend on sibling modules (they exist per the spec) but only
  rewrite files for YOUR ticket unless feedback demands otherwise."""

FILE_RE = re.compile(r"===FILE:\s*(\S+?)\s*===\n(.*?)\n===END===", re.DOTALL)
NOTES_RE = re.compile(r"^NOTES:\s*(.*)$", re.MULTILINE)


def parse_files(text: str) -> tuple[dict[str, str], str]:
    files = {m.group(1): m.group(2) for m in FILE_RE.finditer(text)}
    notes = NOTES_RE.search(text)
    return files, (notes.group(1) if notes else "")


class Legionarius(AgentBase):
    role = "legionarius"

    def _context_for(self, ticket: dict[str, Any]) -> tuple[str, int]:
        spec = spec_path().read_text()
        module = ticket["module"]
        current = ""
        for f in sorted((target_src() / "ordersvc").glob("*.py")):
            marker = " (YOUR TICKET)" if f.name == module else ""
            current += f"\n--- {f.name}{marker} ---\n{f.read_text()}"
        feedback = ""
        v = coll(VERDICTS).find_one({"ticket_id": ticket["_id"], "accepted": False}, sort=[("created_at", -1)])
        if v:
            feedback = f"\n\nPREVIOUS ATTEMPT REJECTED:\n{v.get('feedback', '')}"
        memory, hits = recall_for_ticket(self.run_id, ticket)
        return (
            f"TICKET: {ticket['title']}\nModule: {module}\nACs: {', '.join(ticket['ac_refs'])}\n"
            f"Description: {ticket['description']}\n\nSPEC:\n{spec}\n\nCURRENT FILES:{current}"
            f"{feedback}{memory}"
        ), hits

    def work_one(self) -> bool:
        """Claim and work one ticket. Returns False when nothing was ready."""
        ticket = claim_next(self.run_id, self.agent_id)
        if ticket is None:
            return False
        self.sprint = ticket.get("sprint", 0)
        self.heartbeat("working", ticket=str(ticket["_id"]))
        self.log("ticket.claimed", ticket["title"], ticket_id=str(ticket["_id"]))

        stop = threading.Event()  # lease heartbeat while the LLM thinks
        def _renew():
            while not stop.wait(self.cfg.heartbeat_seconds):
                renew_lease(ticket["_id"], self.agent_id)
        threading.Thread(target=_renew, daemon=True).start()

        try:
            prompt, hits = self._context_for(ticket)
            text = ask(
                self.agent_id, SYSTEM, prompt,
                sprint=self.sprint, ticket=str(ticket["_id"]),
                retrieval_hits=hits, max_tokens=8192,
            )
            raw_files, notes = parse_files(text)
            files = {
                name: content for name, content in raw_files.items()
                if name.endswith(".py") and "/" not in name and "\\" not in name and ".." not in name
            }
            if not files:
                raise ValueError("worker returned no usable files")
            coll(ARTIFACTS).insert_one({
                "run_id": self.run_id, "ticket_id": ticket["_id"], "sprint": self.sprint,
                "worker_id": self.agent_id, "files": files,
                "notes": notes, "created_at": now(),
            })
            complete(ticket["_id"], self.agent_id, status="review")
            self.log("ticket.submitted", f"{ticket['title']} -> review",
                     ticket_id=str(ticket["_id"]), files=list(files))
        except BudgetExhausted:
            complete(ticket["_id"], self.agent_id, status="ready")  # hand back untouched
            raise
        except Exception as e:
            self.log("ticket.error", f"{ticket['title']}: {e}", ticket_id=str(ticket["_id"]))
            complete(ticket["_id"], self.agent_id, status="ready")
        finally:
            stop.set()
            self.heartbeat("idle")
        return True

    def run_forever(self, poll_seconds: float = 3.0) -> None:
        self.register()
        self.log("agent.start", "reporting for duty")
        while True:
            try:
                if not self.work_one():
                    self.heartbeat("idle")
                    time.sleep(poll_seconds)
            except BudgetExhausted:
                self.log("agent.halt", "budget exhausted")
                return
