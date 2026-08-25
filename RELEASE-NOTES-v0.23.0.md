# Prime Hermes v0.23.0-alpha.1 — Grounded Builds

Plans can now **check the real internet before writing a line of code** — the anti-hallucination primitive.

## What's new (Phase 10-D)

- **`scout` task kind** — give it `{"technologies": [...], "goal_hint": "..."}` and it produces grounding cards: official documentation URLs + top GitHub reference projects per technology, via the registry's web search.
- **Ledger-cached** — results keyed by sorted-tech-set hash; identical rebuilds fetch nothing.
- **Honest failure** — if the search backend is unreachable, the card is stamped **UNVERIFIED** with a warning; downstream nodes can gate on that instead of inventing APIs for fictional libraries.
- **Composable** — scout artifacts flow through the standard `{{task.result}}` refs, so a gate node can require verification before any build node runs.

## Example plan fragment

```json
{"id": "ground",  "kind": "scout",
 "payload": {"technologies": ["fastapi", "sqlmodel"], "goal_hint": "crud api"}},
{"id": "check",   "kind": "note", "depends_on": ["ground"],
 "payload": {"verified": true}},
{"id": "build",   "kind": "prime", "depends_on": ["check"],
 "payload": {"when": {"task": "check", "field": "verified", "equals": true},
             "prompt": "..."}}
```

## Verification

143/143 tests green; scout tests fully mocked (no network in suite).

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
