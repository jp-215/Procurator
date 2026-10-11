"""Shared agent plumbing: event logging (L0), heartbeat registration, loop glue.

Every observable thing an agent does lands in `events` — the L0 transcript that
Scriba compacts and the dashboard streams.
"""
from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from typing import Any

from core.config import config
from core.db import AGENTS, EVENTS, coll


def now() -> datetime:
    return datetime.now(timezone.utc)


class AgentBase:
    role: str = "agent"

    def __init__(self, instance: int = 0):
        self.cfg = config()
        self.run_id = self.cfg.run_id
        self.agent_id = f"{self.role}-{instance}" if instance else self.role
        self.sprint = 0

    def register(self, **extra: Any) -> None:
        coll(AGENTS).update_one(
            {"run_id": self.run_id, "agent_id": self.agent_id},
            {"$set": {
                "role": self.role, "heartbeat_at": now(),
                "pid": os.getpid(), "host": socket.gethostname(), **extra,
            }},
            upsert=True,
        )

    def heartbeat(self, status: str = "idle", **extra: Any) -> None:
        coll(AGENTS).update_one(
            {"run_id": self.run_id, "agent_id": self.agent_id},
            {"$set": {"heartbeat_at": now(), "status": status, **extra}},
            upsert=True,
        )

    def log(self, kind: str, text: str, **data: Any) -> None:
        """L0 event. TTL'd; compacted by Scriba; streamed to the dashboard."""
        coll(EVENTS).insert_one({
            "run_id": self.run_id, "sprint": self.sprint, "agent": self.agent_id,
            "kind": kind, "text": text, "data": data, "created_at": now(),
        })
        print(f"[{self.agent_id}] {kind}: {text}", flush=True)
