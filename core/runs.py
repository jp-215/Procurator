"""Run lifecycle: registry + headless seeding/launch.

A 'run' is one end-to-end attempt at the mandate. The registry makes the live
run discoverable by the voice layer and dashboard regardless of process env.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.config import config
from core.db import ALL_COLLECTIONS, MANDATE, RUNS, SPRINTS, STAKEHOLDER_MSGS, coll
from core.paths import spec_path, target_src

ROOT = Path(__file__).resolve().parent.parent


def _now() -> datetime:
    return datetime.now(timezone.utc)


def current_run_id() -> str:
    """Latest registered run, falling back to the process env."""
    r = coll(RUNS).find_one(sort=[("created_at", -1)])
    return r["run_id"] if r else config().run_id


def seed_run(run_id: str, directive: str = "", fresh: bool = True) -> None:
    if fresh:
        for name in ALL_COLLECTIONS:
            coll(name).delete_many({"run_id": run_id})
            coll(name).delete_many({"meta.run_id": run_id})
    spec = spec_path().read_text()
    coll(MANDATE).insert_one({
        "run_id": run_id, "version": 1, "spec": spec,
        "goal": "Implement ordersvc to satisfy all acceptance criteria",
        "directive": directive, "created_at": _now(),
    })
    coll(STAKEHOLDER_MSGS).insert_one({
        "run_id": run_id, "from": "dominus", "sprint": 0,
        "text": directive or "Mandate issued: implement the orders service per SPEC.md.",
        "created_at": _now(),
    })
    coll(SPRINTS).insert_one({"run_id": run_id, "sprint": 0, "status": "pending", "created_at": _now()})
    coll(RUNS).update_one(
        {"run_id": run_id},
        {"$set": {"status": "seeded", "directive": directive, "created_at": _now()}},
        upsert=True,
    )


def reset_workbench() -> None:
    """Restore the mesh working tree to the skeleton before a fresh run."""
    import shutil

    skeleton = ROOT / "target" / "src"
    dst = target_src()
    if dst.resolve() == skeleton.resolve():
        return  # legacy in-repo mode; CI calibration protects the skeleton
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(skeleton, dst)


def launch_headless(run_id: str, workers: int = 2, log_dir: Path | None = None) -> int:
    """Detach a full mesh run; returns the PID. Survives the caller's exit."""
    import os

    logs = log_dir or (ROOT / ".runs")
    logs.mkdir(exist_ok=True)
    out = open(logs / f"{run_id}.log", "a")
    env = {**os.environ, "RUN_ID": run_id}
    proc = subprocess.Popen(
        [sys.executable, "-m", "core.main", "all", str(workers)],
        cwd=ROOT, env=env, stdout=out, stderr=out, start_new_session=True,
    )
    coll(RUNS).update_one(
        {"run_id": run_id},
        {"$set": {"status": "running", "pid": proc.pid, "launched_at": _now()}},
    )
    return proc.pid
