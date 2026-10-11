# Procurator

**The agent that holds the mandate.** A PM-led multi-agent mesh for long-horizon
engineering, built on MongoDB Atlas for the MongoDB agentic hackathon (prompt 2).

In Rome, a *procurator* stewarded a province on the emperor's mandate: managed the staff,
kept the books, reported upward. Here, Procurator is a project-manager agent that owns the
communication and memory layer for a mesh of worker agents — the single point of contact
for the stakeholder, running standups, routing context budgets, and relentlessly steering
toward a long-term goal it can measure.

## The thesis
Long-horizon agentic work fails on memory and drift, not on capability. Procurator fixes
both by making **MongoDB Atlas the entire nervous system**: scheduler, message bus, memory,
and scoreboard. Processes are stateless and disposable — kill any agent mid-task and the
mesh resumes from Mongo.

## The workforce
| Agent | Role |
|---|---|
| **Dominus** | Synthetic stakeholder — issues the mandate, injects scope changes |
| **Procurator** | PM — sole stakeholder contact, standups, Dispatch Governor |
| **Scriba** | Memory — compacts transcripts into tiered memory, writes playbooks |
| **Legatus** | Eng lead — decomposes the spec into a ticket DAG |
| **Legionarius ×N** | Workers — claim tickets atomically, submit artifacts |
| **Censor** | QA gate — grades against a hidden acceptance suite; only merge point |
| **Quaestor** | Metrics — token ledger, pass rates, marginal yield |

## How Atlas is used
- **Change streams** — the message bus; agents wake on writes, never poll hot loops
- **Atomic `findOneAndUpdate`** — the scheduler; leases + reaper give crash-safe claims
- **Time series collection** — per-turn metrics (tokens, pass rate, retrieval hits)
- **Vector Search + Voyage AI** — semantic memory tiers (L1 episodes, L2 facts)
- **`$graphLookup`** — provenance: trace any passing test back to the stakeholder message
- **TTL indexes** — raw transcript (L0) decays; only distilled memory persists

## Hard metrics
- **M1** — pass rate on a hidden acceptance suite (pytest ground truth, 25 ACs)
- **M2** — marginal yield (Δ tests / Δ tokens), drives width/depth/redundancy scaling
- **M3** — ablation: same mandate with memory on vs off; the proof the memory layer earns its keep

## Running everything, end to end

**0. One-time setup**
```bash
python3 -m venv .venv && .venv/bin/pip install -e .
cd dashboard && npm install && cd ..
cp .env.example .env            # fill in MONGODB_URI, ANTHROPIC_API_KEY, VOYAGE_API_KEY
.venv/bin/python scripts/bootstrap_atlas.py --search   # collections + vector indexes
```

**1. Seed a run** (pick a RUN_ID; it namespaces everything in Atlas)
```bash
export RUN_ID=run-002
.venv/bin/python scripts/seed.py --fresh   # mandate + sprint 0 (wipes only this RUN_ID)
git checkout -- target/src                 # start from the skeleton
```

**2. Terminal A — telemetry server** (SSE bridge, port 8787)
```bash
RUN_ID=run-002 .venv/bin/uvicorn server.app:app --port 8787
```

**3. Terminal B — dashboard** (Vite dev server, port 5173, proxies /api -> 8787)
```bash
cd dashboard && npm run dev
```
Open **http://localhost:5173** (or `?run=run-002` to pin a run). Explorer left,
document tabs center, provenance inspector right, Events/Metrics/Problems bottom.

**4. Terminal C — the mesh**
```bash
RUN_ID=run-002 .venv/bin/python -m core.main all 2        # decompose + 2 workers + censor + PM
# crashed or interrupted? resume without re-decomposing:
RUN_ID=run-002 .venv/bin/python scripts/resume.py 2
# scale horizontally from any machine with the same MONGODB_URI:
RUN_ID=run-002 .venv/bin/python -m core.main legionarius 3
```

**5. Watch.** Tickets flow blocked -> ready -> claimed -> review -> done in the
explorer; verdicts and standups stream into Events; the Metrics tab plots M1
(tests passing) and token burn live; click a done ticket to see its code and its
`$graphLookup` provenance chain back to the stakeholder message.

**Ablation (M3)**: run once with `MEMORY_ENABLED=false RUN_ID=run-off`, once with
`MEMORY_ENABLED=true RUN_ID=run-on`, same budget; compare the two curves.

**Grade the tree yourself at any time**
```bash
.venv/bin/python runner/sandbox.py        # hidden-suite score of target/src
```

## Layout
```
core/        agents, claims/leases, change-stream bus, metrics, memory
target/      the seeded repo the mesh works on (SPEC.md = the mandate)
hidden_tests/  grading oracle — agents never see it (enforced by runner/sandbox.py)
runner/      Censor's grading sandbox
atlas/       collection map + search index definitions
scripts/     bootstrap, seed, ablation
server/      SSE bridge for the dashboard (Phase F)
dashboard/   read-only editor-UI telemetry (Phase F)
```

See `CLAUDE.md` for contributor/agent rules and `atlas/collections.md` for the schema.
