# Procurator — Operator Runbook (every CLI command)

All commands run from `~/Procurator` unless noted. Secrets live in `.env`.

## 0. One-time setup
```bash
git clone https://github.com/jp-215/Procurator.git && cd Procurator
python3 -m venv .venv && .venv/bin/pip install -e .
cd dashboard && npm install && cd ..
cp .env.example .env                              # fill in every key
.venv/bin/python scripts/bootstrap_atlas.py --search   # collections + vector indexes (idempotent)
.venv/bin/python scripts/setup_target_repo.py          # seed the workbench repo (once)
.venv/bin/pytest tests/ -v                             # health check (6 tests)
```

## 1. Bring the stack up (3 terminals, this order)
```bash
# T1 — tunnel (keep open; URL changes each restart)
/opt/homebrew/opt/cloudflared/bin/cloudflared tunnel --url http://localhost:8787 --no-autoupdate 2> /tmp/procurator-tunnel.log

# T2 — voice + telemetry server
.venv/bin/uvicorn server.app:app --port 8787

# T3 — sync tunnel -> .env + Twilio webhooks (run once per tunnel restart),
#      then RESTART T2 so it picks up the new PUBLIC_BASE_URL
.venv/bin/python scripts/go_live.py

# T4 — dashboard  ->  http://localhost:5173  (Editor/Flow toggle top-left)
cd dashboard && npm run dev
```

## 2. The headless loop (no terminals needed after step 1)
Call **the Twilio number** from your verified phone → tell the PM to build → hang up.
The mesh seeds, builds, gates, commits to the workbench repo, and calls you back.

## 3. Manual runs
```bash
# single-sprint build
.venv/bin/python -c "from core.runs import reset_workbench, seed_run; reset_workbench(); seed_run('my-run')"
RUN_ID=my-run .venv/bin/python -m core.main all 2

# two-sprint drift run (build, then Dominus injects the refund scope change)
.venv/bin/python -c "from core.runs import reset_workbench, seed_run; reset_workbench(); seed_run('my-drift')"
RUN_ID=my-drift MEMORY_ENABLED=true DRIFT=1 .venv/bin/python -m core.main all 2

# ablation control (same thing, memory off)
RUN_ID=my-drift-off MEMORY_ENABLED=false DRIFT=1 .venv/bin/python -m core.main all 2

# crash recovery (resume mid-sprint, no re-decomposition)
RUN_ID=my-run .venv/bin/python scripts/resume.py 2

# scale horizontally from ANY machine with the same MONGODB_URI
RUN_ID=my-run .venv/bin/python -m core.main legionarius 3
```

## 4. Inspect
```bash
.venv/bin/python runner/sandbox.py        # grade the workbench tree right now
.venv/bin/python scripts/report.py        # the pitch table (all runs, from Mongo)
.venv/bin/python scripts/report.py showcase drift-mem-on drift-mem-off   # specific runs
tail -f .runs/<run-id>.log                # live mesh log for a headless run
git -C ~/procurator-workbench log --oneline --all   # the mesh's commits per run
```

## 5. Reset / teardown
```bash
RUN_ID=my-run .venv/bin/python scripts/seed.py --fresh   # wipe ONE run's docs, reseed
git checkout -- target/src                               # restore repo skeleton (CI gate)
pkill -f "uvicorn server.app"; pkill -f cloudflared; pkill -f "npm run dev"; pkill -f core.main
```

## 6. Demo-day sequence (the pitch, PITCH.md)
```bash
# before going on stage:
#   T1 tunnel up  ->  T3 go_live.py  ->  restart T2  ->  T4 dashboard on the Flow view
# on stage:
#   1. call the number on speaker; ask "how is the project?"  (live status from memory)
#   2. say "go ahead and build it"; hang up                   (mesh launches headlessly)
#   3. narrate the Flow view pulses + GitHub commits appearing
#   4. kill a worker live if asked about reliability:  pkill -f legionarius  (reaper recovers)
#   5. your phone rings — the PM reports the sprint. Take the call on speaker.
```

## Gotchas learned the hard way
- Never `kill $(lsof -ti tcp:8787)` — cloudflared holds a client socket on 8787 and
  dies too. Use `pkill -f "uvicorn server.app"`.
- Tunnel restarted → URL changed → **run `scripts/go_live.py` again**, then restart the server.
- Twilio trial only connects calls with your verified number; the trial preamble
  wants a keypress before the PM picks up.
- One run at a time: the workbench is single-tenant (the launcher enforces it).
- ElevenLabs key must carry the Text-to-Speech permission or calls use robot voice.
