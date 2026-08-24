# Ariadne — Architecture (Phase 2): Refine + 10× Memory

Status: Phase 2 design · Owner: Ariadne (Hermes fork) · Date: 2026-08-24
Supplements `docs/architecture-ariadne.md` (Phase 1).

## 0. Goal

Absorb Prime Agent's third capability — `/refine` self-improvement over a
persistent harness ledger — onto **a memory subsystem with 10× the storage and
capability envelope of Hermes' builtin**. Every multiplier below is quantified
against the measured baseline (`tools/memory_tool.py`):

| Dimension | Hermes builtin (1×) | Ariadne (10×) |
|---|---|---|
| Stores | 2 flat files (MEMORY.md, USER.md) | 1 SQLite ledger (+ FTS5 index) |
| Total capacity | ~3.6 KB hard cap (2200+1375 chars) | **36 MB** soft budget (configurable to GBs; SQLite scales) |
| Entries | unbounded count within caps | ≥100k entries |
| Entry size | bounded by store cap | up to 8 KB per entry |
| Versioning | none (overwrite in place) | full history per entry |
| Rollback | none | point-in-time per entry + whole-store snapshots |
| Search | substring matching for edit ops only | FTS5 keyword search at recall time |
| Injection control | frozen snapshot at session start | same cache-safe pattern + per-entry weight/pin |

Cache-safety invariant preserved exactly as upstream requires: the system-prompt
block is a frozen snapshot refreshed at session start; mid-session writes are
durable on disk but never mutate past context mid-conversation.

## 1. Source behavior absorbed from Prime (docs/rlm-runtime.md §Continual Harness State)

- Ledger of prompt notes / memories / skill descriptions / sub-agent specs /
  refinement events; not a second execution engine.
- `/refine` = dedicated review over the current trajectory applying small
  create/update/delete edits.
- Before/after snapshots recorded per edit → rollback.
- Base system prompt immutable; refinements are supplemental state.
- Session-local vs global stores.

## 2. Design decisions

### D1. Ship as an external memory provider plugin (house pattern)

`plugins/memory/ariadne/` implementing `agent.memory_provider.MemoryProvider`,
activated by `memory.provider: ariadne`. No core-file edits except the config
schema list (one line, additive). This is the sanctioned edge for memory
capability; it gives tool injection via `get_tool_schemas()` and lifecycle hooks
for free, keeps the fork rebasable, and follows "extend, don't duplicate."

### D2. Storage: one SQLite ledger, WAL mode, FTS5 virtual table

Path: `<HERMES_HOME>/ariadne/memory.db`.

Tables:
- `entries(id TEXT pk, kind TEXT, scope TEXT, title TEXT, body TEXT,
  weight REAL, pinned INTEGER, status TEXT, created_at REAL,
  updated_at REAL)` — `kind ∈ {memory,user,skill_desc,prompt_note,
  subagent_spec,event}`, `scope ∈ {global,session}`, session entries carry
  `session_id`.
- `versions(seq INTEGER pk, entry_id TEXT, op TEXT, before JSON, after JSON,
  evidence TEXT, source TEXT, created_at REAL)` — append-only history;
  `op ∈ {create,update,delete}`.
- `entries_fts` — FTS5 over (title, body), external-content table.

Budget enforcement: soft budget (default 36 MB total body bytes). When exceeded,
eviction candidates = lowest (weight, pinned=0, oldest updated_at); refine never
auto-deletes pinned or recent entries. Hard failure mode: refuse writes with an
actionable message rather than silent data loss.

### D3. Tool surface: ONE provider-injected tool `ariadne_memory`, action-dispatched

`add/update/delete/get/search/list/history/rollback/snapshot/stats` actions.
Provider tools route through MemoryManager's existing dispatch — no core-tool
footprint beyond the single name. Schema description carries usage guidance
(behavior lives in schema description, house style).

### D4. Refine engine: procedure skill + host-side apply path

- Kernel-side shim mirrors Prime: `await refine.status() / run(instructions)`.
  Scheduling semantics simplified for MVP: runs synchronously at end-of-turn
  boundary when invoked by the host; kernel-side call queues a request row that
  the next turn's host-side gate picks up (documented divergence: Prime rebuilds
  the system prompt at turn-end; we keep the frozen-snapshot rule instead).
- Host side: `skills/refine/SKILL.md` procedure — review trajectory → propose
  small edits → apply via ariadne_memory with evidence strings → every edit
  versioned automatically.
- Refine NEVER touches skills' SKILL.md files or the base prompt; it writes
  `skill_desc` / `prompt_note` entries into the ledger (supplemental state).

### D5. Config keys (all optional)

```yaml
memory:
  provider: ariadne          # activates the plugin
ariadne:
  memory:
    budget_mb: 36            # 10x the 3.6KB builtin envelope
    max_entry_chars: 8192
    prefetch_top_k: 12       # builtin injects a fixed snapshot; we rank
```

### D6. What is explicitly NOT Phase 2

Embeddings/vector recall (FTS5 first), graph node recording (Phase 3),
kernel-state revival, cross-device sync, multi-user ACLs.

## 3. Module layout

```
plugins/memory/ariadne/__init__.py     # MemoryProvider subclass + registration
plugins/memory/ariadne/ledger.py       # SQLite ledger: CRUD, versions, FTS5, budgets
tools/ariadne_memory_tool.py           # NOT needed - provider injects its own schema
skills/refine/SKILL.md                 # refine procedure (agent-facing)
ariadne_runtime/refine.py              # kernel-side client shim
tests/test_ariadne_memory_ledger.py    # ledger unit/integration
tests/test_ariadne_provider.py         # provider contract tests
```

## 4. Test strategy

- Ledger: CRUD + version chains + rollback correctness + FTS5 ranking +
  budget eviction ordering (pinned/weight/recency respected).
- Provider contract: initialize/is_available/system_prompt_block/prefetch
  shape, tool routing, cache-safe snapshot behavior across simulated turns.
- Refine: evidence-required validation, small-edit enforcement (≤N ops per run),
  rollback restores prior state byte-for-byte.
- E2E smoke: real session applies a refine edit; second session sees it.

## 5. Exit gates

1. Ledger unit/integration green (incl. rollback byte-equality, budget order).
2. Provider activates via `memory.provider: ariadne`; tools visible in a live
   session; a refine run produces versioned entries; rollback verified.
3. Live-model gate: session A refines; fresh session B's system prompt contains
   the refined note (frozen-snapshot refresh proven across sessions).
