"""Token auth — see SPEC.md AC-01..AC-04."""
from __future__ import annotations


def issue_token(user_id: str, ttl_seconds: int = 3600, *, now: float | None = None) -> str:
    raise NotImplementedError  # TODO: AC-01


def verify_token(token: str, *, now: float | None = None) -> str:
    raise NotImplementedError  # TODO: AC-02, AC-03, AC-04


def revoke_token(token: str) -> None:
    raise NotImplementedError  # TODO: AC-04
