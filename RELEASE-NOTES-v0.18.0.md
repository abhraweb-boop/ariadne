# Ariadne v0.18.0-alpha.1 — graph execution engine (Phase 6)

The headline: **the graph is now the loop.** Phase 5's context graph recorded and recalled Ariadne's work; execution was still a classic agent while-loop. Phase 6 promotes the graph to control flow — plans are executable task DAGs, and running them *is* the agent loop.

## What's new

- **Executable task DAGs** — `ariadne_plan` creates validated, acyclic plans; every node is a `kernel` cell (persistent IPython), an `rlm` recursive child, any registered Hermes `tool`, or a `note`.
- **Topological executor** (`ariadne_runtime/graph_exec.py`) — independent branches run concurrently in a bounded thread pool; artifacts travel along edges via `{{task.result}}` references that resolve at run time.
- **Local failure routing** — per-task retries (`max_attempts` up to 5), then transitive cascade-skip of only the dead branch. Sibling branches finish; the summary reports node-level states so a repair plan can target exactly what failed.
- **Resume + crash recovery** — interrupted runs restart from completed nodes; stale `running` rows reset automatically.
- **Plan-scoped ids** — model-written short ids (`scan`) become `plan-<id>-scan` internally; `{{scan.result}}` refs are rewritten to match. No cross-plan collisions.
- **/graph integration** — tasks mirror into the shared context graph as `task:` nodes with `blocks` edges; the desktop panel renders plans for free.

## Try it

```
ariadne_plan {"action":"create","goal":"migrate config",
  "tasks":[
    {"id":"scan","kind":"tool","payload":{"tool":"search_files","args":{"pattern":"*.yaml"}},"max_attempts":2},
    {"id":"analyze","kind":"kernel","depends_on":["scan"],"payload":{"code":"import yaml; ..."}}]}
ariadne_exec {"action":"run","plan_id":"<returned id>"}
```

## Notes

- Code-only release: no new installer binary (desktop app unchanged since v0.17.0).
- Test suite: **69/69 green** (26 new tests covering topo order, parallelism, failure routing, retries, resume, artifacts).
- Design contract: [`docs/architecture-ariadne-phase6.md`](docs/architecture-ariadne-phase6.md).

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT licensed.
