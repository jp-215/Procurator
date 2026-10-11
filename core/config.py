"""Environment-driven configuration. Every process reads the same .env."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    mongodb_uri: str = field(default_factory=lambda: os.environ.get("MONGODB_URI", ""))
    mongodb_db: str = field(default_factory=lambda: os.environ.get("MONGODB_DB", "procurator"))

    voyage_api_key: str = field(default_factory=lambda: os.environ.get("VOYAGE_API_KEY", ""))
    voyage_model: str = field(default_factory=lambda: os.environ.get("VOYAGE_MODEL", "voyage-3.5"))
    voyage_dims: int = field(default_factory=lambda: _int("VOYAGE_DIMS", 1024))

    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    procurator_model: str = field(default_factory=lambda: os.environ.get("PROCURATOR_MODEL", "claude-opus-5"))
    worker_model: str = field(default_factory=lambda: os.environ.get("WORKER_MODEL", "claude-sonnet-5"))

    budget_total_tokens: int = field(default_factory=lambda: _int("BUDGET_TOTAL_TOKENS", 1_000_000))
    width_max: int = field(default_factory=lambda: _int("WIDTH_MAX", 8))
    lease_seconds: int = field(default_factory=lambda: _int("LEASE_SECONDS", 300))
    heartbeat_seconds: int = field(default_factory=lambda: _int("HEARTBEAT_SECONDS", 30))

    memory_enabled: bool = field(default_factory=lambda: _bool("MEMORY_ENABLED", True))

    # Identifies an end-to-end run; ablation gives each arm its own run_id.
    run_id: str = field(default_factory=lambda: os.environ.get("RUN_ID", "dev"))


@lru_cache(maxsize=1)
def config() -> Config:
    cfg = Config()
    if not cfg.mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set — copy .env.example to .env and fill it in")
    return cfg
