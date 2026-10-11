"""L3 decision graph: every consequential choice is a node with caused_by edges.
$graphLookup walks any artifact/AC back to the stakeholder message that caused it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.db import DECISIONS, coll


def record_decision(
    run_id: str, agent: str, kind: str, text: str,
    caused_by: list[Any] | None = None, **data: Any,
) -> Any:
    doc = {
        "run_id": run_id, "agent": agent, "kind": kind, "text": text,
        "caused_by": caused_by or [], "data": data,
        "created_at": datetime.now(timezone.utc),
    }
    return coll(DECISIONS).insert_one(doc).inserted_id


def provenance_chain(decision_id: Any) -> list[dict[str, Any]]:
    """Walk caused_by edges from a decision back to its roots."""
    rows = list(coll(DECISIONS).aggregate([
        {"$match": {"_id": decision_id}},
        {"$graphLookup": {
            "from": DECISIONS, "startWith": "$caused_by",
            "connectFromField": "caused_by", "connectToField": "_id",
            "as": "chain", "depthField": "depth",
        }},
    ]))
    if not rows:
        return []
    root = rows[0]
    chain = sorted(root.pop("chain"), key=lambda d: d["depth"])
    return [root] + chain
