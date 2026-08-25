# Vendored: ruflo

- **Upstream:** https://github.com/ruvnet/ruflo (package `claude-flow` / CLI `ruflo`)
- **Pinned commit:** see `ruflo-PIN.txt`
- **License:** MIT — © 2024-2026 ruvnet

## Why vendored
Phase 13: swarm orchestration as a DAG node kind (`flo`). The adapter seam is
`ariadne_runtime/flo_engine.py` — all protocol specifics live there; upstream
changes only touch that file.

## Scope wall
ruflo coordinates agents UNDER a plan node. It never replaces the Prime Hermes
graph executor.

## Windows note
Primary path is the JS CLI (`bin/cli.js`, Node >= 20). The repository also ships
Rust crates, which are NOT built on Windows and are not required for the JS path.
