# Procurator — Atlas collection map

Every piece of coordination state lives here. Processes hold nothing.

## Control plane
| Collection | Purpose | Notes |
|---|---|---|
| `mandate` | The long-term goal: criteria[], invariants[], version | Versioned; Dominus edits create new versions, never mutate |
| `sprints` | Sprint envelope: window, budget, criteria in scope | |
| `tickets` | Work DAG. `deps[]`, `status`, `worker_id`, `lease_until` | Atomic claim target; change-stream source |
| `agents` | Registry: role, capabilities, context_policy, `heartbeat_at` | Reaper reads this |
| `dispatch_log` | Every Governor decision + its inputs | Makes scaling auditable |
| `stakeholder_msgs` | Dominus → Procurator traffic | Perturbation source |

## Memory tiers
| Collection | Tier | Mechanism |
|---|---|---|
| `events` | L0 raw transcript | TTL index (48h). Never retrieved directly |
| `episodes` | L1 compacted summaries | Atlas Search + Vector Search (hybrid) |
| `memory` | L2 semantic facts/decisions | Vector Search |
| `decisions` | L3 structured provenance nodes | `$graphLookup` edges |
| `playbooks` | L4 learned procedure | Versioned; written by retros, read at dispatch |

## Signal plane
| Collection | Purpose |
|---|---|
| `metrics` | **Time series.** One doc per agent turn |
| `artifacts` | Diffs/files produced, linked to tickets |
| `verdicts` | Censor gate results, test pass/fail detail |

## M0 budget note
Free tier caps search indexes. We index **only** `episodes` (hybrid) and `memory` (vector)
— two indexes. L0 is TTL'd and unindexed; L3/L4 use ordinary B-tree indexes. The tiering is
a design requirement, not a nicety.
