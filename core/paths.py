"""Single source of truth for where the mesh's working tree lives.

Default: ./target inside this repo (legacy). Set TARGET_REPO_DIR to point the
mesh at a separate clone so this repo is never written by agents.
"""
from __future__ import annotations

from pathlib import Path

from core.config import config

ROOT = Path(__file__).resolve().parent.parent


def target_dir() -> Path:
    cfg = config()
    return Path(cfg.target_repo_dir) if cfg.target_repo_dir else ROOT / "target"


def target_src() -> Path:
    return target_dir() / "src"


def spec_path() -> Path:
    return target_dir() / "SPEC.md"
