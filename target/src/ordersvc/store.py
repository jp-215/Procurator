"""In-memory KV store — see SPEC.md AC-24..AC-25."""
from __future__ import annotations

from typing import Any


class MemoryStore:
    def put(self, key: str, value: Any) -> None:
        raise NotImplementedError  # TODO: AC-24

    def get(self, key: str) -> Any:
        raise NotImplementedError  # TODO: AC-24

    def delete(self, key: str) -> None:
        raise NotImplementedError  # TODO: AC-25
