# Ariadne

**A persistent-memory research agent** — a fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) that gives a coding/research agent an evolving memory of its own work.

Where stock Hermes treats every session as fresh context, Ariadne layers a research loop on top:

- **Persistent IPython kernel** — long-lived kernel sessions managed via `ariadne/kernel_manager.py`, so exploration survives across turns instead of dying with each tool call.
- **Recursive `rlm()`** — subagent lifecycle service (`ariadne/service.py`) for spawning scoped child workers whose results flow back into the parent thread.
- **`/refine` memory ledger** — `ariadne_runtime/refine.py` writes every refinement into a SQLite ledger at 10× retention granularity; conclusions compound instead of evaporating.
- **Context graph + waterfall loader** — `plugins/context_graph/` builds a live graph of session entities/artifacts and loads relevant context waterfall-style (nearest-first), surfaced in the desktop app's `/graph` panel.
- **Graph execution (Phase 6)** — plans are executable task DAGs (`ariadne_plan` / `ariadne_exec`): the executor walks topological order with parallel branches, `{{task.result}}` artifact passing, per-task retries, and cascade-skip failure routing — the graph *is* the loop, not just its memory. See [`docs/architecture-ariadne-phase6.md`](docs/architecture-ariadne-phase6.md).
- **Packaged desktop app** — rebranded Electron build (`Ariadne`) with installers under `apps/desktop/release/`.

## Status

**Alpha.** Windows x64 installer is provided; macOS/Linux builds are not yet produced. Expect rough edges — this is a research line, not a stable product.

## Install (Windows)

Download `Ariadne-0.17.0-win-x64.exe` from [Releases](../../releases) and run it.

## Running from source

```bash
git clone https://github.com/abhraweb-boop/ariadne.git
cd ariadne
uv sync                      # Python deps
cd apps/desktop && npm ci && npm run dev   # desktop shell
```

The agent core, CLI, skills, and plugin system are unchanged from upstream — see [`HERMES-README.md`](HERMES-README.md) for full documentation of the underlying platform, including `hermes setup`, providers, gateway platforms, and plugin authoring.

## Layout (Ariadne-specific)

```
ariadne/                  kernel manager + rlm() subagent service
ariadne_runtime/          bridge + /refine ledger runtime
plugins/context_graph/    context-graph store + waterfall loader
plugins/memory/ariadne/   ledger persistence hooks
apps/desktop/             Electron app (rebranded "Ariadne")
```

## License

MIT — inherited from Hermes Agent, © Nous Research (see [`LICENSE`](LICENSE)). Ariadne-specific changes © their authors.
