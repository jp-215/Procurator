"""Cursor pagination — see SPEC.md AC-16..AC-19."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Page:
    items: list[Any] = field(default_factory=list)
    next_cursor: str | None = None


def paginate(items: list[Any], limit: int, cursor: str | None = None) -> Page:
    raise NotImplementedError  # TODO: AC-16..AC-19
