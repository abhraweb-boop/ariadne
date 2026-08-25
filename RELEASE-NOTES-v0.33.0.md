# Prime Hermes v0.33.0-alpha.1 — Git-Backed Builds & Guided Tour

Phase 14 (self-healing hardening) is now **complete to the last planned item**: builds leave a git trail you can walk back on, and new users get a guided first minute.

## What's new

- **Git-backed builds** (`ariadne_runtime/build_snapshots.py`)
  - `snapshot(dir, label)` — commit current worktree state, get a SHA
  - `record_run(...)` / `load_run(...)` — machine-readable run records at `<dir>/.prime-runs/<plan_id>.json` with before/after SHAs + final state
  - `revert_to(dir, sha)` — restores the worktree as a **new commit**; history is never rewritten
  - Silent degradation outside repos or without git — can never break a run
- **Console `/exec` integration** — pass `{"snapshot_dir": "..."}` in the body: before/after checkpoints per run, SHAs echoed back in the exec summary (`summary.snapshot`).
- **`/tour` Console command** — five-step guided walkthrough (engine · badges · flow · heals · snapshots), staggered output so it reads like a human guide.

## Verification

224/224 tests green — snapshot tests run against **real temporary git repos** (init → snapshot → mutate → revert-as-new-commit → assert file contents and history).

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
