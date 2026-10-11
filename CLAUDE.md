# Procurator — agent guidance

Before doing anything in this repo, read `README.md`, then `atlas/collections.md` and
`target/SPEC.md`. They are the source of truth for architecture, schema, and the mandate —
do not re-derive any of it from code.

## What this is
A PM-led multi-agent mesh for the MongoDB agentic hackathon (prompt 2: Long-Horizon
Engineering). All coordination state lives in MongoDB Atlas — processes are stateless and
disposable. The PM agent (Procurator) is the sole stakeholder contact; Atlas change
streams are the message bus; atomic `findOneAndUpdate` claims are the scheduler.

## Hard rules
- **Never read, edit, or reference `hidden_tests/`** from agent/worker code paths. Only
  `runner/sandbox.py` may touch it. The hidden suite is the grading oracle; leaking it
  invalidates metric M1 and the entire project thesis.
- **Censor is the only writer to `target/src/`.** Workers produce artifacts in Mongo,
  never file edits.
- Every LLM call goes through `core/llm.py` (budget guard + token metrics). Never call
  the Anthropic SDK directly from an agent.
- All timestamps UTC (`datetime.now(timezone.utc)`); every document carries `run_id`.
- Respect the ablation switch: memory code must no-op cleanly when `MEMORY_ENABLED=false`.
- M0 sandbox limits: max 2 Atlas search indexes (episodes, memory). Do not add more.

## Environment
- Python venv at `.venv/` — run everything as `.venv/bin/python` / `.venv/bin/pytest`.
- Secrets live in `.env` (gitignored). `.env.example` is the template. Never commit keys.
- `scripts/bootstrap_atlas.py` is idempotent; `--search` adds the two vector indexes.
- `scripts/seed.py --fresh` wipes and reseeds the current `RUN_ID` only.

## Key commands
```bash
.venv/bin/python scripts/bootstrap_atlas.py        # create collections + indexes
.venv/bin/python scripts/seed.py --fresh           # seed mandate + sprint 0
.venv/bin/python -m core.main all                  # run the whole mesh (demo mode)
.venv/bin/python -m core.main legionarius 3        # add 3 workers (any machine)
.venv/bin/python runner/sandbox.py                 # grade target/src right now
.venv/bin/pytest tests/ -v                         # claims-layer integration tests
```

## Metrics (the project thesis — keep them honest)
- **M1** pass rate on the hidden suite (machine truth, from pytest).
- **M2** marginal yield = Δ tests passing / Δ tokens — drives the Dispatch Governor.
- **M3** ablation delta: memory-on vs memory-off runs, same budget. The demo chart.
Anything that would let an LLM opinion substitute for these numbers is a bug.

## Build state
Phases A–D done + dashboard (A: spine; B: target+hidden suite 0/25→25/25; C: minimal
mesh, verified live — run-001 hit 25/25 at 81k tokens; D: Scriba tiers, $vectorSearch
recall, $graphLookup provenance; F-partial: SSE server (server/app.py, port 8787) +
Vite editor-UI (dashboard/, port 5173)). Remaining: Phase E (Dispatch Governor +
Dominus scope injection) and the ablation script/chart. Voyage free tier is 3 RPM —
embeddings are paced in core/embeddings.py; don't call Voyage directly.
