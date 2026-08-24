# Prime Hermes v0.22.0-alpha.1 — Self-Modifying Graphs

The plan is no longer a one-shot artifact: **the graph edits itself when you change your mind**, and a whole build compiles into one master DAG.

## What's new (Phase 10 core)

- **Master-DAG compiler** (`ariadne_runtime/compile.py`) — guide milestones → single executable plan: `m1-`, `m2-` prefixes, checkpoint nodes chaining milestones, slot context injected from your answers.
- **`patch_plan()`** — the self-modification primitive. Diff by kind+payload hash:
  - unchanged + done → **kept** (never re-executed)
  - changed → reset (+ every dependent invalidated transitively)
  - new ids → inserted; removed ids → skipped
  - title-only diffs → renamed in place (a rename is not a rebuild)
- **Store primitives** — `insert_task` (validated insert into an existing plan) and `rename_task`.

## Why it matters

Combined with v0.20's gates and the executor's resume semantics: start a build, change your mind halfway ("use Postgres instead"), patch — done work survives, only the affected branch rebuilds, then execution resumes.

## Verification

138/138 tests green. Patch semantics covered: leaf-change isolation, root-change cascade invalidation, insert/drop, duplicate rejection, checkpoint chaining (transitive reach), slot injection.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
