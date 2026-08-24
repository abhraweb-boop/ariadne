# Prime Hermes v0.19.0-alpha.1 — the Prime engine lives inside

The headline: **Prime Agent is now an internal organ.** Vendored, pinned, built, and verified end-to-end: the desktop/web server spawned the real `prime-agent --mode rpc` subprocess and a live model answered through it during this release's dogfood run.

## What's new (Phase 7 core)

- **Vendored Prime engine** — [prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) @ `a9b5d88b` (MIT) under `vendor/prime-agent`, built by `scripts/build-prime.sh`, provenance in `vendor/PRIME-NOTICE.md`.
- **`PrimeEngine`** (`ariadne/prime_engine.py`) — JSONL RPC driver speaking prime-agent's *real* wire format (`{id, type:<command>}`, payloads in `data`, async prompt ACK + agent events until `agent_end`, final text via `get_last_assistant_text`). CRLF-tolerant, stderr tail surfaced on failures, Windows-safe teardown.
- **`prime` DAG kind** — graph-executor plans can now delegate nodes to the prime worker; artifacts flow downstream via `{{task.result}}`.
- **`ariadne_prime` tool** — direct surface: run / status / new_session / steer, with teaching errors for disabled/bundle-missing/no-key states.
- **Autonomy policy tiers** (`ariadne_runtime/policy.py`) — `governed` (2 attempts, 5-min cells, per-node reporting) vs `unleashed` (5 attempts, hour-long cells, auto-steer, 200k iterations). Hard floors constant: no credentials entry, no payment UI, no destructive OS ops.
- **Prime Hermes Console** (`/api/prime-hermes/console/`) — standalone text surface over HTTP: status badges (model · tier · engine pid), slash commands (`/status`, `/session`, `/steer <text>`, `/help`), prompts stream through the engine. No Electron changes required; wraps natively later.
- **Brand** — product name is now **Prime Hermes** (formerly Ariadne).

## Verification performed before tagging

- 99/99 tests green (`tests/ariadne/`)
- Live dogfood: server → Console API → prime-engine prompt round-trip returned a real model reply ("PRIME HERMES ONLINE", 11 events)

## Known limitations

- Console auth uses the dashboard session token (same as all web APIs).
- Engine model follows ambient provider env; explicit `ariadne.prime.provider/model` config lands with Phase 8.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT licensed. Prime engine © Mario Zechner, MIT.
