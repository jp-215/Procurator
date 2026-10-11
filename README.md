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

## Quickstart
```bash
cp .env.example .env            # fill in MONGODB_URI, ANTHROPIC_API_KEY, VOYAGE_API_KEY
.venv/bin/python scripts/bootstrap_atlas.py --search
.venv/bin/python scripts/seed.py --fresh
.venv/bin/python -m core.main all
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
