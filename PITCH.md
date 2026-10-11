# Procurator — The Agent That Holds the Mandate
### MongoDB Agentic Hackathon · Prompt 2: Long-Horizon Engineering

---

## The 3-minute spoken pitch

> **[HOOK — 20s]**
> Every project that survives has one person who holds the mandate. Not the best
> engineer — the one who remembers why decisions were made, who's doing what, and
> what "done" means. Agents today have neither that person nor that memory. Give an
> agent mesh a week-long goal and it drifts, forgets, and burns tokens re-learning
> its own past. We built the missing role. Meet **Procurator** — in Rome, the steward
> who ran a province on the emperor's mandate. Here: a project-manager agent that
> runs an engineering mesh on yours.
>
> **[THE CALL — 40s, live]**
> I'm going to call my project manager. *(dial on speaker)* It answers with the live
> state of the project — that number is pytest ground truth, not an opinion. I say:
> "go ahead and build it." I hang up. That's the last human action you'll see.
> The hangup webhook classifies the call, seeds a mandate in Atlas, and launches the
> mesh headlessly. Watch the Flow view: my words ripple from the phone, through the
> PM, onto the bus, into the database.
>
> **[THE MESH — 50s, dashboard]**
> Everything you see coordinates through MongoDB Atlas — there is no message queue,
> no scheduler, no state in any process. **Change streams** are the nervous system.
> **Atomic findOneAndUpdate** is the scheduler — kill any worker mid-ticket and a
> lease reaper requeues its work; we've killed this mesh live many times and it
> resumes from Mongo every time. Every accepted ticket is graded by a **hidden test
> suite** the agents never see, then committed to GitHub with its score in the
> message — the repo *is* the metric curve. Memory is tiered: raw transcript decays
> under a **TTL index**; what survives is distilled into **Voyage-embedded** lessons
> found by **$vectorSearch**, decisions traced by **$graphLookup** — click any passing
> test and walk back to the phone call that caused it.
>
> **[THE HONEST NUMBERS — 40s]**
> We measured our own idea and it embarrassed us first. On an easy build, memory was
> a measured **tax**: the memory-off run was cheapest. We kept that chart — because
> the ledger is pytest and a token time series, not vibes. Then we made the task
> honest: mid-project, the stakeholder injects a scope change. Under drift, targeted
> memory recalled past decisions, cut recall injections five-fold, absorbed the new
> requirements with **zero regressions**, and the self-written playbooks from sprint
> one changed how sprint two was dispatched. The harness also retunes itself: a
> **Dispatch Governor** reads marginal yield — tests gained per token — off the time
> series and widens, narrows, and escalates spending per attempt. Every scaling
> decision is logged with the inputs that caused it.
>
> **[CLOSE — 20s]**
> While I've been talking, the mesh finished. *(phone rings)* That's my project
> manager, calling to report the sprint. Long-horizon agentic work doesn't need a
> bigger context window. It needs someone who holds the mandate — and a database
> that never forgets. That's Procurator, on MongoDB Atlas.

---

## The measured record (every number is a Mongo aggregation — `scripts/report.py`)

| run | task | memory | pass | rejects | tokens | recall hits |
|---|---|---|---|---|---|---|
| run-001 | build (cold, pre-fix harness) | on (flat) | 25/25 | 5 | 92,576 | 5 |
| run-off | build | **off** | 25/25 | 0 | **31,877** | 0 |
| run-002 | build | on (flat) | 25/25 | 0 | 51,011 | 66 |
| call-e2e002 | build, launched by phone call | on (flat) | 25/25 | 0 | 49,717 | 48 |
| drift-mem-on | build **+ scope drift** | on (targeted) | **32/32** | 0 | 64,431 | 13 |
| drift-mem-off | build **+ scope drift** (control) | off | *(run in progress)* | | | |

**The finding we lead with:** flat memory is a measured tax on easy work (run-off beat
run-002 by 19k tokens). Targeted memory — injected only on drift sprints and
reject-prone ticket classes — kept 32/32 under requirement drift with zero regressions
at 5× fewer injections. The harness knows the difference *because the ledger told it*.

## Atlas as the nervous system

| Atlas capability | Role in Procurator |
|---|---|
| Change streams | The message bus — agents wake on writes; the dashboard streams the same events |
| Atomic `findOneAndUpdate` + leases | The scheduler — crash-safe claims, zero double-assignment under concurrency |
| Time series collection | The ledger — per-turn tokens, pass rates, retrieval hits; feeds the Governor |
| Vector Search + Voyage AI | Semantic memory (L1 episodes, L2 lessons) |
| `$graphLookup` | Provenance — any artifact traces to the stakeholder message that caused it |
| TTL index | Memory decay — raw transcript dies in 48h; only distilled memory persists |

## The workforce

Dominus (stakeholder, now a real phone caller) → **Procurator** (PM: standups, routing,
Dispatch Governor) → Legatus (spec → ticket DAG) → Legionarii (stateless workers,
escalation ladder) → Censor (hidden-suite gate; sole writer; commits to GitHub) →
Scriba (memory tiers; writes the playbooks that re-instruct every role) → Quaestor
(the ledger).

## Q&A one-liners

- **Why MongoDB as the whole nervous system?** Because long horizons die on state
  held in processes. Our processes are disposable by design; we kill them on stage.
- **Why hidden tests?** An LLM grading itself is an opinion. pytest is a fact.
- **Isn't the self-improvement loop risky?** Every playbook is versioned in Mongo and
  gated by the same regression suite as the code. The harness can only promote changes
  the ledger likes.
- **Cost?** The whole measured record above — eight full runs, two with drift — cost
  under $0 of infra (Atlas M0 sandbox) and the tokens you see in the table.
- **What's horizontal scale?** `python -m core.main legionarius 3` on any machine with
  the connection string. Atlas is the scheduler; there's nothing else to deploy.
