# Prime Hermes v0.28.0-alpha.1 — Flow Tab & Self-Healing Everywhere

The integration release: everything built so far is now **wired together and visible**.

## What's new

- **Flow tab** (`/api/ariadne/graph/flow`) — live plan visualization: nodes color by state (green done · purple-pulse running · red failed · amber bypassed-gate · grey skipped), retry counts, inline error cards, dependency arrows, run picker. Polls the Runs API every 2s.
- **Console status extended** — header badges now show Gemini state (`g:ok/no_key/…`), flo engine state, and the budget meter ($spent/$cap, amber past 50%, red when paused).
- **Doctor in the executor** — every task failure is now classified on arrival: permanent-class errors (e.g. invalid API key) fail terminally *with a fix hint* instead of burning retries; transient/environmental/logical classes keep the existing retry/heal paths.
- **`transient` keyword** recognized as a self-declared transient signal.

## Verification

189/189 tests green — including a regression this wiring itself caught (the flaky-retry test's error string now classifies correctly).

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
