"""Change-stream bus: agents wake on document writes, never poll hot loops.

watch() yields change events and survives transient cursor drops by resuming
from the last resume token. Used by agent loops and the SSE bridge alike.
"""
from __future__ import annotations

import time
from typing import Any, Iterator

from pymongo.errors import PyMongoError

from core.db import coll


def watch(
    collection: str,
    pipeline: list[dict[str, Any]] | None = None,
    full_document: str = "updateLookup",
) -> Iterator[dict[str, Any]]:
    """Yield change events forever, resuming across transient errors."""
    resume_token: Any = None
    while True:
        try:
            kwargs: dict[str, Any] = {"full_document": full_document}
            if resume_token is not None:
                kwargs["resume_after"] = resume_token
            with coll(collection).watch(pipeline or [], **kwargs) as stream:
                for change in stream:
                    resume_token = change["_id"]
                    yield change
        except PyMongoError:
            time.sleep(1.0)  # transient drop; resume from token
