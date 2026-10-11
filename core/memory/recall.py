"""Retrieval: pack relevant memory into a worker's context.

Three sources, all cross-run (memory accumulates over the whole horizon):
  L4 playbooks  — exact match on ticket_class/module, latest version
  L2 facts      — $vectorSearch over `memory` (Voyage embeddings)
  L1 episodes   — $vectorSearch over `episodes`

Honors the ablation switch: MEMORY_ENABLED=false -> empty context, zero hits.
"""
from __future__ import annotations

from typing import Any

from core.config import config
from core.db import EPISODES, MEMORY, PLAYBOOKS, coll
from core.embeddings import embed_one


def _vector_hits(collection: str, index: str, qvec: list[float], k: int, field: str) -> list[str]:
    try:
        rows = coll(collection).aggregate([
            {"$vectorSearch": {
                "index": index, "path": "embedding", "queryVector": qvec,
                "numCandidates": k * 10, "limit": k,
            }},
            {"$project": {field: 1, "score": {"$meta": "vectorSearchScore"}}},
        ])
        return [r[field] for r in rows if r.get(field) and r.get("score", 0) > 0.5]
    except Exception:
        return []  # index still building, or M0 hiccup — recall degrades, never crashes


def recall_for_ticket(run_id: str, ticket: dict[str, Any]) -> tuple[str, int]:
    """Returns (context_block, hit_count)."""
    if not config().memory_enabled:
        return "", 0

    parts: list[str] = []
    hits = 0

    # L4: procedure for this class of work (exact, no embedding needed)
    pb = coll(PLAYBOOKS).find_one(
        {"ticket_class": {"$in": [ticket.get("ticket_class"), ticket.get("module")]}},
        sort=[("version", -1)],
    )
    if pb:
        parts.append(f"PLAYBOOK ({pb['ticket_class']} v{pb['version']}):\n{pb['text']}")
        hits += 1

    # L2 + L1: semantic recall on the ticket's own description
    query = f"{ticket.get('title', '')} {ticket.get('module', '')} {ticket.get('description', '')[:300]}"
    qvec = embed_one(query, input_type="query")
    if qvec:
        lessons = _vector_hits(MEMORY, "memory_semantic", qvec, 4, "text")
        episodes = _vector_hits(EPISODES, "episodes_hybrid", qvec, 2, "summary")
        if lessons:
            parts.append("LESSONS LEARNED:\n" + "\n".join(f"- {x}" for x in lessons))
            hits += len(lessons)
        if episodes:
            parts.append("RELEVANT PAST EPISODES:\n" + "\n".join(f"- {x}" for x in episodes))
            hits += len(episodes)

    if not parts:
        return "", 0
    return "\n\nMEMORY (from past work — follow playbooks, heed lessons):\n" + "\n\n".join(parts), hits
