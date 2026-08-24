# Ariadne v0.17.0 — first public alpha

Ariadne is a persistent-memory research agent: a fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) with a research loop layered on top — conclusions compound instead of evaporating between sessions.

## What's in this release

- **Persistent IPython kernel** (`ariadne/kernel_manager.py`) — long-lived kernel sessions that survive across turns; clean atexit shutdown on parent exit.
- **Recursive `rlm()`** (`ariadne/service.py`) — subagent lifecycle service for scoped child workers whose results flow back into the parent thread.
- **`/refine` + 10× memory ledger** (`ariadne_runtime/refine.py`, `plugins/memory/ariadne/`) — every refinement is written to a SQLite ledger at 10× retention granularity.
- **Context graph + waterfall loader** (`plugins/context_graph/`) — live graph of session entities/artifacts, nearest-first waterfall loading, surfaced in the desktop app's `/graph` panel.
- **Rebranded desktop app** — Electron shell packaged as **Ariadne** (window title, product name).

## Downloads

| File | Platform |
|---|---|
| `Ariadne-0.17.0-win-x64.exe` | Windows 10/11 x64 |

> ⚠️ The installer is **not code-signed**, so SmartScreen may warn on first run ("More info" → "Run anyway"). macOS/Linux builds are planned but not yet produced.

## Known limitations (alpha)

- Windows-only packaging.
- No auto-update channel yet.
- Rough edges expected — this is a research line, not a stable product.

## Credits & license

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent) by Nous Research. MIT licensed — upstream © Nous Research; Ariadne-specific changes © their authors.
