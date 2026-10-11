"""Retry with exponential backoff — see SPEC.md AC-20..AC-23."""
from __future__ import annotations

import time
from typing import Any, Callable


def retry_with_backoff(
    fn: Callable[[], Any],
    max_attempts: int = 3,
    base_delay: float = 0.1,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    raise NotImplementedError  # TODO: AC-20..AC-23
