# Ariadne — Architecture (Phase 6): Graph Execution

Status: implemented · Owner: Ariadne (Hermes fork) · Date: 2026-08-25
Supplements `docs/architecture-ariadne-phase3.md`.

## 0. Goal

Promote the context graph from *memory* to *control flow*. Phases 1–5 gave
Ariadne a graph that **records and recalls**; execution remained stock
Hermes' while-loop (LLM call → tool call → observe → repeat). Phase 6 makes
the graph **the loop**: a plan is a task DAG, and execution is a topological
walk over that DAG — independent branches run concurrently, artifacts flow
along edges, failures re-route locally instead of unwinding a turn.

## 1. Source behavior (Prime parity where it exists)

Prime's `rlm()` spawns children from a linear thread; there is no DAG
executor. We keep Prime's governing rules anyway:

- supplemental state only — task rows never mutate past conversation context;
- everything derived is versioned/inspectable in SQLite, nothing silently
  overwritten (every transition is an UPDATE with timestamps).

## 2. Design decisions

### D1. Plans live in the same DB family (`graph.db`)

`plugins/context_graph/tasks.py::TaskStore` adds `plans(id, goal, state,
created_at, updated_at)` + `tasks(id, plan_id, kind, title, payload JSON,
depends_on JSON, state, attempts, max_attempts, result, error,
created/started/finished)` beside the existing nodes/edges tables — one WAL
database, one backup story. Every task also mirrors into the shared context
graph as a `task:<id>` node with `blocks` edges, so the desktop /graph panel
renders plans for free.

### D2. Task kinds map onto the Phase-1/2 machinery

| kind | executes via | notes |
|---|---|---|
| `kernel` | `ariadne.service.execute_cell` | persistent IPython; state carries across nodes |
| `rlm` | `svc._handle_host_request("rlm.run", …)` | requires live parent session (same rule as direct tool) |
| `tool` | `tools.registry.dispatch(name, args)` | any registered Hermes tool, incl. plugin tools |
| `note` | none | annotation/artifact node |

### D3. State machine + failure routing

```
pending -> ready -> running -> done
                   running -> failed   (attempts < max_attempts -> ready)
dep failed/skipped -> skipped        (transitive cascade)
```

Failure is *local*: retry per-task (`max_attempts` 1–5), then cascade-skip
only descendants; sibling branches finish normally. A plan that ends with
failures reports `final_state: failed` with per-node states — the model
plans a repair DAG against real node-level errors instead of guessing.

### D4. Artifacts travel along edges

Payload values may reference upstream outputs: `"{{build.result}}"` (whole)
or embedded `"...{{build.result}}..."` (JSON-encoded interpolation). The
resolver substitutes only from tasks listed in `depends_on` whose state is
`done`; unresolved refs fail that task with a precise error.

### D5. Executor semantics (`ariadne_runtime/graph_exec.py`)

One `ThreadPoolExecutor(max_workers)`. Loop: cascade-skip → collect ready →
submit up to max_workers → wait(FIRST_COMPLETED) → apply outcomes. Exit when
nothing is in flight and nothing is ready. `run(resume=True)` resets stale
`running` rows (crash recovery), skips `done` nodes — interrupted runs
continue from completed work. Bounded by `max_iterations` (10k) so a store
bug can never hot-loop.

### D6. Model surface: two tools, zero core edits

`ariadne_plan` (create/get/list/delete/reset_task) and `ariadne_exec`
(run/status) register through the same plugin `ctx.register_tool` gate as
`ariadne_graph` — no core-file changes, same registration pattern as every
prior phase. Tool descriptions teach the loop shift: emit a DAG first, run
it, inspect node states, patch and re-run.

### D7. Security posture unchanged

The executor runs as the user (same trust level as the agent's own tools).
`tool` dispatch goes through the registry's normal check_fn gates. rlm
children remain admission-scoped to a live parent turn. Plans are data:
deleting a plan deletes its tasks; nothing executes from history without an
explicit `ariadne_exec action=run`.
