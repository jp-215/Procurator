"""Read-only telemetry bridge: REST snapshots + one SSE stream over change streams.

The dashboard is a pure observer — no endpoint here mutates anything.
Run: .venv/bin/uvicorn server.app:app --port 8787
"""
from __future__ import annotations

import json
import queue
import threading
from typing import Any

from bson import ObjectId
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from core.config import config
from core.db import (
    AGENTS, ARTIFACTS, DECISIONS, EPISODES, EVENTS, MANDATE, MEMORY, METRICS,
    PLAYBOOKS, SPRINTS, STAKEHOLDER_MSGS, TICKETS, VERDICTS, coll,
)
from core.memory.provenance import provenance_chain
from core.metrics import latest_pass_rate, tokens_spent

app = FastAPI(title="Procurator Telemetry")

from server.voice import router as voice_router  # noqa: E402

app.include_router(voice_router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


def clean(doc: Any) -> Any:
    """BSON -> JSON-safe."""
    if isinstance(doc, list):
        return [clean(d) for d in doc]
    if isinstance(doc, dict):
        return {k: clean(v) for k, v in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    if hasattr(doc, "isoformat"):
        return doc.isoformat()
    return doc


def rid(run: str | None) -> str:
    from core.runs import current_run_id

    return run or current_run_id()


@app.get("/api/state")
def state(run: str | None = None):
    r = rid(run)
    passed, total = latest_pass_rate(r)
    tickets = clean(list(coll(TICKETS).find({"run_id": r}).sort("created_at", 1)))
    return {
        "run_id": r,
        "mandate": clean(coll(MANDATE).find_one({"run_id": r}, sort=[("version", -1)])),
        "sprints": clean(list(coll(SPRINTS).find({"run_id": r}).sort("sprint", 1))),
        "tickets": tickets,
        "agents": clean(list(coll(AGENTS).find({"run_id": r}))),
        "stakeholder_msgs": clean(list(coll(STAKEHOLDER_MSGS).find({"run_id": r}).sort("created_at", 1))),
        "pass": {"passed": passed, "total": total},
        "tokens": tokens_spent(r),
        "memory_enabled": config().memory_enabled,
    }


@app.get("/api/ticket/{tid}")
def ticket(tid: str, run: str | None = None):
    t = coll(TICKETS).find_one({"_id": ObjectId(tid)})
    arts = list(coll(ARTIFACTS).find({"ticket_id": ObjectId(tid)}).sort("created_at", -1))
    verds = list(coll(VERDICTS).find({"ticket_id": ObjectId(tid)}).sort("created_at", -1))
    return clean({"ticket": t, "artifacts": arts, "verdicts": verds})


@app.get("/api/memory")
def memory(run: str | None = None):
    return clean({
        "episodes": list(coll(EPISODES).find({}, {"embedding": 0}).sort("created_at", -1).limit(30)),
        "lessons": list(coll(MEMORY).find({}, {"embedding": 0}).sort("created_at", -1).limit(30)),
        "playbooks": list(coll(PLAYBOOKS).find().sort([("ticket_class", 1), ("version", -1)]).limit(30)),
    })


@app.get("/api/events")
def events(run: str | None = None, limit: int = 100):
    return clean(list(coll(EVENTS).find({"run_id": rid(run)}).sort("created_at", -1).limit(limit))[::-1])


@app.get("/api/decisions")
def decisions(run: str | None = None):
    return clean(list(coll(DECISIONS).find({"run_id": rid(run)}).sort("created_at", 1)))


@app.get("/api/provenance/{decision_id}")
def provenance(decision_id: str):
    chain = provenance_chain(ObjectId(decision_id))
    # stakeholder messages can be roots of the chain; resolve any leftover ids
    return clean(chain)


@app.get("/api/metrics/series")
def metrics_series(run: str | None = None):
    r = rid(run)
    rows = list(coll(METRICS).find({"meta.run_id": r}).sort("ts", 1))
    series, cum = [], 0
    for m in rows:
        cum += m.get("tokens_in", 0) + m.get("tokens_out", 0)
        point: dict[str, Any] = {"ts": m["ts"].isoformat(), "tokens_cum": cum, "agent": m["meta"].get("agent")}
        if m.get("tests_total"):
            point["passed"] = m["tests_passed"]
            point["total"] = m["tests_total"]
        series.append(point)
    return series


@app.get("/api/stream")
def stream(run: str | None = None):
    r = rid(run)
    q: queue.Queue[str] = queue.Queue(maxsize=1000)

    def watcher(collection: str, label: str):
        from core.bus import watch

        for ch in watch(collection):
            doc = ch.get("fullDocument") or {}
            if doc.get("run_id") not in (r, None):
                continue
            try:
                q.put_nowait(json.dumps({"type": label, "op": ch["operationType"], "doc": clean(doc)}))
            except queue.Full:
                pass

    for c, label in [(EVENTS, "event"), (TICKETS, "ticket"), (VERDICTS, "verdict"),
                     (AGENTS, "agent"), (STAKEHOLDER_MSGS, "stakeholder")]:
        threading.Thread(target=watcher, args=(c, label), daemon=True).start()

    def gen():
        yield "retry: 3000\n\n"
        while True:
            try:
                item = q.get(timeout=25)
                yield f"data: {item}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
