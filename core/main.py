"""Process launcher.

  python -m core.main procurator            # PM loop (reaper, frontier, standups)
  python -m core.main legatus               # one-shot decomposition
  python -m core.main legionarius 3         # three worker threads
  python -m core.main censor                # QA gate
  python -m core.main all                   # whole mesh in one process (demo mode)

Scale horizontally by running more `legionarius` processes — any machine with
the same MONGODB_URI joins the mesh; Atlas is the scheduler.
"""
from __future__ import annotations

import sys
import threading


def run_workers(n: int) -> list[threading.Thread]:
    from core.agents.legionarius import Legionarius

    threads = []
    for i in range(1, n + 1):
        t = threading.Thread(target=Legionarius(instance=i).run_forever, daemon=True)
        t.start()
        threads.append(t)
    return threads


def main() -> None:
    role = sys.argv[1] if len(sys.argv) > 1 else "all"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    if role == "legatus":
        from core.agents.legatus import Legatus

        Legatus().decompose()
    elif role == "legionarius":
        threads = run_workers(n)
        for t in threads:
            t.join()
    elif role == "censor":
        from core.agents.censor import Censor

        Censor().run_forever()
    elif role == "procurator":
        from core.agents.procurator import Procurator

        Procurator().run_sprint(sprint=0)
    elif role == "all":
        import os

        from core.agents.censor import Censor
        from core.agents.legatus import Legatus
        from core.agents.procurator import Procurator

        Legatus().decompose(sprint=0)
        threading.Thread(target=Censor().run_forever, daemon=True).start()
        run_workers(n)
        Procurator().run_sprint(sprint=0)
        if os.environ.get("DRIFT", "").lower() in {"1", "true", "yes"}:
            from core.agents.dominus import Dominus

            Dominus().inject_drift(sprint=1)
            Legatus().decompose(sprint=1)
            Procurator().run_sprint(sprint=1)
    else:
        raise SystemExit(f"unknown role: {role}")


if __name__ == "__main__":
    main()
