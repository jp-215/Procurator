"""Mesh output versioning: every accepted artifact becomes a commit in the
target repo (TARGET_REPO_DIR), pushed to TARGET_REPO_REMOTE on branch run/<RUN_ID>.

Best-effort by design: a git/network failure must never block the gate —
Atlas `artifacts` remains the source of truth; the repo is the human-facing mirror.
"""
from __future__ import annotations

import subprocess
from typing import Any

from core.config import config
from core.paths import target_dir


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=target_dir(), capture_output=True, text=True, timeout=60,
    )


def _is_repo() -> bool:
    return (target_dir() / ".git").exists()


def commit_accepted(ticket: dict[str, Any], result: Any) -> str | None:
    """Commit the accepted state; push if a remote is configured. Returns sha or None."""
    cfg = config()
    if not cfg.target_repo_dir or not _is_repo():
        return None  # legacy in-repo target: never auto-commit inside Procurator itself
    try:
        branch = f"run/{cfg.run_id}"
        _git("checkout", "-B", branch)
        _git("add", "-A")
        msg = (
            f"{ticket.get('module', '?')}: {ticket.get('title', '')}\n\n"
            f"ticket: {ticket['_id']}\nhidden suite: {result.passed}/{result.total}\n"
            f"newly passing: {', '.join(result.newly_passing(None)) or '-'}\n\n"
            f"Committed by Censor (Procurator mesh)"
        )
        c = _git("commit", "-m", msg)
        if c.returncode != 0:
            return None  # nothing to commit
        sha = _git("rev-parse", "--short", "HEAD").stdout.strip()
        if cfg.target_repo_remote:
            _git("push", "-u", "origin", branch)  # best-effort
        return sha
    except Exception:
        return None
