"""Resume a run mid-sprint without re-decomposing. Crash-and-resume entrypoint.

Usage: RUN_ID=run-001 .venv/bin/python scripts/resume.py [n_workers]
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agents.censor import Censor  # noqa: E402
from core.agents.procurator import Procurator  # noqa: E402
from core.main import run_workers  # noqa: E402

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    threading.Thread(target=Censor().run_forever, daemon=True).start()
    run_workers(n)
    Procurator().run_sprint(sprint=0)
