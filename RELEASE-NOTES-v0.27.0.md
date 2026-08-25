# Prime Hermes v0.27.0-alpha.1 — Google SDK & ruflo Inside

Two new engines join the harness, both behind the same disciplined adapter seams.

## What's new (Phase 13)

- **Google SDK, in-process** — `ariadne_runtime/google_provider.py` wraps `google-genai` (Gemini). New `gemini` DAG node kind calls it directly — no subprocess, no extra runtime installs. Every unconfigured state is a *teaching message* (`no_key` with the exact env var and where to get a key; `not_installed` with the pip line), never a traceback.
- **ruflo vendored & pinned** — MIT, pinned at `e21aa352`, flattened into `vendor/ruflo` (5,607 files) so clones get real source. The JS CLI path is primary on Windows; Rust crates deliberately not built there.
- **`flo` DAG kind** — swarm orchestration as an ordinary plan node via `FloEngine`, with a hard scope wall: ruflo coordinates agents *under* a plan node; it never replaces the graph executor.
- **Provenance** — `vendor/RUFLO-NOTICE.md` + `ruflo-PIN.txt`, mirroring the Prime vendoring discipline.

## Verification

189/189 tests green; all provider/engine paths mocked in-suite (deterministic, no network, no node spawn).

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT. ruflo © ruvnet, MIT.
