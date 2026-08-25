# Prime Hermes v0.26.0-alpha.1 — Self-Healing Core

**"It runs until done" now has an immune system.**

## What's new (Phase 14 core)

- **ErrorDoctor** — every task failure passes through one classifier with four classes, each with its own automatic playbook:

| Class | Example | Automatic playbook |
|---|---|---|
| `transient` | connection reset, 429, timeout | backoff + retry |
| `environmental` | missing package, busy port, missing dir | install dep / rebind / recreate, then retry |
| `logical` | assertion failures, tracebacks | hand to prime worker for a code patch, re-run |
| `permanent` | invalid API key | **the only class that escalates to a human** |

- **Heal journal** — every autonomous fix is recorded; the human sees outcomes plus "what it fixed while you were away", never the noise.
- **Budget governor** — unleashed builds get a spending leash: soft warning at 50% of cap, hard pause at cap (with resume). The doctor checks the gate before every attempt.
- Conservative by design: anything unclassifiable is treated as permanent rather than retried into oblivion.

## Verification

180/180 tests green. Classifier ordering (env-beats-logic), playbook execution, exhaustion escalation, immediate permanent bubbling, and budget gating all covered — including two regex bugs the tests caught before you ever would have.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
