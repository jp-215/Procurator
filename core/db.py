"""Mongo client factory + collection handles + idempotent bootstrap.

All coordination state lives in these collections; processes hold nothing.
See atlas/collections.md for the full map.
"""
from __future__ import annotations

from functools import lru_cache

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import CollectionInvalid

from core.config import config

# Control plane
MANDATE = "mandate"
SPRINTS = "sprints"
TICKETS = "tickets"
AGENTS = "agents"
DISPATCH_LOG = "dispatch_log"
STAKEHOLDER_MSGS = "stakeholder_msgs"
RUNS = "runs"

# Memory tiers
EVENTS = "events"          # L0 raw transcript (TTL)
EPISODES = "episodes"      # L1 compacted summaries (hybrid search)
MEMORY = "memory"          # L2 semantic facts (vector search)
DECISIONS = "decisions"    # L3 provenance graph
PLAYBOOKS = "playbooks"    # L4 learned procedure

# Signal plane
METRICS = "metrics"        # time series
ARTIFACTS = "artifacts"
VERDICTS = "verdicts"

ALL_COLLECTIONS = [
    MANDATE, SPRINTS, TICKETS, AGENTS, DISPATCH_LOG, STAKEHOLDER_MSGS, RUNS,
    EVENTS, EPISODES, MEMORY, DECISIONS, PLAYBOOKS,
    METRICS, ARTIFACTS, VERDICTS,
]


@lru_cache(maxsize=1)
def client() -> MongoClient:
    return MongoClient(config().mongodb_uri, appname="procurator")


def db() -> Database:
    return client()[config().mongodb_db]


def coll(name: str) -> Collection:
    return db()[name]


def bootstrap() -> list[str]:
    """Create collections + indexes. Idempotent; safe to re-run."""
    d = db()
    created: list[str] = []
    existing = set(d.list_collection_names())

    # metrics must be a time series collection
    if METRICS not in existing:
        try:
            d.create_collection(
                METRICS,
                timeseries={"timeField": "ts", "metaField": "meta", "granularity": "seconds"},
            )
            created.append(METRICS)
        except CollectionInvalid:
            pass

    for name in ALL_COLLECTIONS:
        if name not in existing and name != METRICS:
            try:
                d.create_collection(name)
                created.append(name)
            except CollectionInvalid:
                pass

    # L0 decay: 48h TTL
    d[EVENTS].create_index([("created_at", ASCENDING)], expireAfterSeconds=172_800)
    d[EVENTS].create_index([("run_id", ASCENDING), ("sprint", ASCENDING), ("created_at", DESCENDING)])

    # Claim scan + reaper + frontier
    d[TICKETS].create_index([("run_id", ASCENDING), ("status", ASCENDING), ("priority", DESCENDING), ("created_at", ASCENDING)])
    d[TICKETS].create_index([("lease_until", ASCENDING)], sparse=True)
    d[TICKETS].create_index([("deps", ASCENDING)])

    d[AGENTS].create_index([("heartbeat_at", ASCENDING)])
    d[DECISIONS].create_index([("caused_by", ASCENDING)])
    d[PLAYBOOKS].create_index([("ticket_class", ASCENDING), ("version", DESCENDING)])
    d[ARTIFACTS].create_index([("ticket_id", ASCENDING)])
    d[VERDICTS].create_index([("ticket_id", ASCENDING), ("created_at", DESCENDING)])
    d[EPISODES].create_index([("run_id", ASCENDING), ("sprint", ASCENDING)])
    d[MEMORY].create_index([("run_id", ASCENDING), ("kind", ASCENDING)])

    return created
