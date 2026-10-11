"""One-time: materialize the mesh's workbench repo at TARGET_REPO_DIR.

Copies the skeleton (SPEC.md + src/) from this repo, inits git, wires the
remote, pushes main. Usage:
  .venv/bin/python scripts/setup_target_repo.py          # create/overwrite skeleton
  .venv/bin/python scripts/setup_target_repo.py --reset  # also reset src/ to skeleton
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SKELETON = ROOT / "target"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    print("  $", " ".join(args))
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


def main() -> None:
    cfg = config()
    if not cfg.target_repo_dir:
        raise SystemExit("set TARGET_REPO_DIR in .env first")
    dest = Path(cfg.target_repo_dir)
    dest.mkdir(parents=True, exist_ok=True)

    if "--reset" in sys.argv and (dest / "src").exists():
        shutil.rmtree(dest / "src")
    if not (dest / "src").exists():
        shutil.copytree(SKELETON / "src", dest / "src")
    shutil.copy(SKELETON / "SPEC.md", dest / "SPEC.md")
    readme = dest / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Procurator Workbench\n\nThis repo is written by the Procurator agent mesh "
            "(https://github.com/jp-215/Procurator).\nEach accepted ticket lands as one commit on "
            "`run/<run-id>`; the hidden-suite score is in every commit message.\n"
        )

    if not (dest / ".git").exists():
        run(["git", "init", "-b", "main"], dest)
    if cfg.target_repo_remote:
        remotes = run(["git", "remote"], dest).stdout.split()
        if "origin" not in remotes:
            run(["git", "remote", "add", "origin", cfg.target_repo_remote], dest)
        else:
            run(["git", "remote", "set-url", "origin", cfg.target_repo_remote], dest)
    run(["git", "add", "-A"], dest)
    run(["git", "commit", "-m", "skeleton: ordersvc spec + stubs (seeded by Procurator)"], dest)
    if cfg.target_repo_remote:
        p = run(["git", "push", "-u", "origin", "main"], dest)
        print(p.stdout or p.stderr)
    print(f"workbench ready at {dest}")


if __name__ == "__main__":
    main()
