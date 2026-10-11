"""Retrieval: pack relevant memory into a worker's context.

Phase C stub honors the ablation switch and returns nothing; Phase D adds
$vectorSearch over episodes/memory and playbook injection.
"""
from __future__ import annotations

from typing import Any

from core.config import config


def recall_for_ticket(run_id: str, ticket: dict[str, Any]) -> tuple[str, int]:
    """Returns (context_block, hit_count)."""
    if not config().memory_enabled:
        return "", 0
    return "", 0  # Phase D fills this in
