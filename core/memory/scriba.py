"""Scriba — the memory agent. Turns raw transcript into durable, retrievable tiers.

L0 events --compact()--> L1 episodes (embedded summaries)
verdicts/feedback --distill()--> L2 facts (embedded lessons)
sprint stats --retro()--> L4 playbooks (procedure for next time)

Every LLM call here goes through core.llm.ask, so memory PAYS for itself in the
token ledger — the M3 ablation compares honest totals.
"""
from __future__ import annotations

from typing import Any

from core.agents.base import AgentBase, now
from core.config import config
from core.db import EPISODES, EVENTS, MEMORY, PLAYBOOKS, TICKETS, VERDICTS, coll
from core.embeddings import embed_one
from core.llm import ask

SUMMARIZE = """You are Scriba, the record-keeper of an agent mesh. Compress this
raw event transcript into a dense episode summary (<=120 words): what was
attempted, what happened, what state changed. Facts only, no filler."""

DISTILL = """You are Scriba. From this verdict history, extract 1-3 reusable
lessons for future implementation work on this codebase. Each lesson is ONE
sentence, concrete and actionable (e.g. 'AC-23 requires delays [0.1,0.2,0.4] via
the injectable sleep, not real sleeping'). One lesson per line, nothing else."""

PLAYBOOK = """You are Scriba writing a playbook entry for ticket class '{klass}'.
Given the stats and lessons below, write <=80 words of procedure a future worker
should follow for this class of ticket. Imperative voice, concrete."""


class Scriba(AgentBase):
    role = "scriba"

    def compact(self, sprint: int) -> int:
        """L0 -> L1: one episode per (agent, sprint) slice of uncompacted events."""
        if not self.cfg.memory_enabled:
            return 0
        self.sprint = sprint
        q = {"run_id": self.run_id, "sprint": sprint, "compacted": {"$ne": True}}
        agents = coll(EVENTS).distinct("agent", q)
        made = 0
        for agent in agents:
            evs = list(coll(EVENTS).find({**q, "agent": agent}).sort("created_at", 1))
            if len(evs) < 3:
                continue
            transcript = "\n".join(f"[{e['kind']}] {e['text']}" for e in evs)[:8000]
            summary = ask(self.agent_id, SUMMARIZE, transcript, sprint=sprint, max_tokens=300)
            coll(EPISODES).insert_one({
                "run_id": self.run_id, "sprint": sprint, "agent": agent,
                "summary": summary.strip(), "n_events": len(evs),
                "embedding": embed_one(summary), "created_at": now(),
            })
            coll(EVENTS).update_many({**q, "agent": agent}, {"$set": {"compacted": True}})
            made += 1
        self.log("compact.done", f"{made} episodes from sprint {sprint}")
        return made

    def distill(self, sprint: int) -> int:
        """verdicts -> L2 facts: lessons from what the gate accepted/rejected."""
        if not self.cfg.memory_enabled:
            return 0
        self.sprint = sprint
        verdicts = list(coll(VERDICTS).find({"run_id": self.run_id, "sprint": sprint}).sort("created_at", 1))
        if not verdicts:
            return 0
        history = []
        for v in verdicts:
            t = coll(TICKETS).find_one({"_id": v["ticket_id"]}, {"title": 1, "module": 1, "ticket_class": 1})
            history.append(
                f"{'ACCEPT' if v['accepted'] else 'REJECT'} {t.get('module')} ({t.get('title')}): "
                f"{v['passed']}/{v['total']}, newly={v.get('newly_passing')}, "
                f"regressions={v.get('regressions')}, feedback={v.get('feedback', '')[:300]}"
            )
        lessons = ask(self.agent_id, DISTILL, "\n".join(history)[:8000], sprint=sprint, max_tokens=400)
        made = 0
        for line in lessons.strip().splitlines():
            line = line.strip().lstrip("-•* ")
            if len(line) < 15:
                continue
            coll(MEMORY).insert_one({
                "run_id": self.run_id, "sprint": sprint, "kind": "lesson",
                "text": line, "confidence": 0.8,
                "embedding": embed_one(line), "created_at": now(),
            })
            made += 1
        self.log("distill.done", f"{made} lessons from {len(verdicts)} verdicts")
        return made

    def retro(self, sprint: int) -> int:
        """metrics + verdicts -> L4 playbooks, one per ticket_class seen this sprint."""
        if not self.cfg.memory_enabled:
            return 0
        self.sprint = sprint
        made = 0
        for klass in coll(TICKETS).distinct("ticket_class", {"run_id": self.run_id, "sprint": sprint}):
            tks = list(coll(TICKETS).find({"run_id": self.run_id, "sprint": sprint, "ticket_class": klass}))
            tids = [t["_id"] for t in tks]
            vs = list(coll(VERDICTS).find({"ticket_id": {"$in": tids}}))
            rejects = [v for v in vs if not v["accepted"]]
            stats = (
                f"tickets={len(tks)}, verdicts={len(vs)}, rejects={len(rejects)}, "
                f"reaps={sum(t.get('reap_count', 0) for t in tks)}, "
                f"reject_feedback={[v.get('feedback', '')[:200] for v in rejects]}"
            )
            lessons = [m["text"] for m in coll(MEMORY).find(
                {"kind": "lesson", "sprint": sprint, "run_id": self.run_id}).limit(5)]
            text = ask(
                self.agent_id, PLAYBOOK.format(klass=klass),
                f"Stats: {stats}\nLessons:\n" + "\n".join(lessons), sprint=sprint, max_tokens=250,
            )
            prev = coll(PLAYBOOKS).find_one({"ticket_class": klass}, sort=[("version", -1)])
            coll(PLAYBOOKS).insert_one({
                "run_id": self.run_id, "ticket_class": klass,
                "version": (prev["version"] + 1 if prev else 1),
                "text": text.strip(), "stats": stats, "created_at": now(),
            })
            made += 1
        made += self._role_retro(sprint)
        self.log("retro.done", f"{made} playbooks updated")
        return made

    ROLE_SIGNALS = {
        "legatus": "tickets that advanced zero tests (over-decomposition), reject rates, dep structure",
        "legionarius": "parse failures (ticket.error events), attempts needed per ticket",
        "censor": "rejects later overturned on retry, feedback usefulness",
    }

    ROLE_PROMPT = """You are Scriba reviewing the {role} agent's own performance this
sprint from hard signals. Write <=60 words of guidance that agent should follow next
sprint to waste fewer tokens and fewer attempts. Imperative voice. If performance was
clean, reinforce what worked. Signals to consider: {signals}"""

    def _role_retro(self, sprint: int) -> int:
        from core.db import EVENTS, TICKETS

        made = 0
        for role, signals in self.ROLE_SIGNALS.items():
            tks = list(coll(TICKETS).find({"run_id": self.run_id, "sprint": sprint}))
            errors = coll(EVENTS).count_documents(
                {"run_id": self.run_id, "sprint": sprint, "kind": "ticket.error"})
            vs = list(coll(VERDICTS).find({"run_id": self.run_id, "sprint": sprint}))
            zero_gain = sum(1 for v in vs if v["accepted"] and not v.get("newly_passing"))
            stats = (f"tickets={len(tks)}, verdicts={len(vs)}, "
                     f"rejects={sum(1 for v in vs if not v['accepted'])}, "
                     f"zero_gain_accepts={zero_gain}, worker_errors={errors}, "
                     f"attempts={[t.get('attempts', 0) for t in tks]}")
            text = ask(self.agent_id, self.ROLE_PROMPT.format(role=role, signals=signals),
                       f"Sprint stats: {stats}", sprint=sprint, max_tokens=150)
            klass = f"role:{role}"
            prev = coll(PLAYBOOKS).find_one({"ticket_class": klass}, sort=[("version", -1)])
            coll(PLAYBOOKS).insert_one({
                "run_id": self.run_id, "ticket_class": klass,
                "version": (prev["version"] + 1 if prev else 1),
                "text": text.strip(), "stats": stats, "created_at": now(),
            })
            made += 1
        return made
