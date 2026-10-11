"""Voyage AI embeddings (MongoDB-owned). No-op when MEMORY_ENABLED=false —
that switch is the ablation arm for metric M3.

Free-tier Voyage (no payment method) allows 3 RPM / 10K TPM, so calls are
paced and rate-limit errors retried with backoff. Memory writes are not
latency-sensitive; recall degrades to zero hits rather than crashing.
"""
from __future__ import annotations

import threading
import time
from functools import lru_cache

from core.config import config

_lock = threading.Lock()
_last_call = 0.0
_MIN_INTERVAL = 21.0  # 3 RPM with headroom


@lru_cache(maxsize=1)
def _client():
    import voyageai

    return voyageai.Client(api_key=config().voyage_api_key, max_retries=0)


def _pace() -> None:
    global _last_call
    with _lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def embed(texts: list[str], input_type: str = "document") -> list[list[float]] | None:
    cfg = config()
    if not cfg.memory_enabled or not cfg.voyage_api_key:
        return None
    import voyageai.error as verr

    for attempt in range(5):
        _pace()
        try:
            result = _client().embed(texts, model=cfg.voyage_model, input_type=input_type)
            return result.embeddings
        except verr.RateLimitError:
            time.sleep(21 * (attempt + 1))
        except Exception:
            return None  # embedding is best-effort; memory degrades, never crashes
    return None


def embed_one(text: str, input_type: str = "document") -> list[float] | None:
    vecs = embed([text], input_type=input_type)
    return vecs[0] if vecs else None
