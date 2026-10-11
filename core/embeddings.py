"""Voyage AI embeddings (MongoDB-owned). No-op when MEMORY_ENABLED=false —
that switch is the ablation arm for metric M3.
"""
from __future__ import annotations

from functools import lru_cache

from core.config import config


@lru_cache(maxsize=1)
def _client():
    import voyageai

    return voyageai.Client(api_key=config().voyage_api_key)


def embed(texts: list[str], input_type: str = "document") -> list[list[float]] | None:
    cfg = config()
    if not cfg.memory_enabled or not cfg.voyage_api_key:
        return None
    result = _client().embed(texts, model=cfg.voyage_model, input_type=input_type)
    return result.embeddings


def embed_one(text: str, input_type: str = "document") -> list[float] | None:
    vecs = embed([text], input_type=input_type)
    return vecs[0] if vecs else None
