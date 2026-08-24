# Prime Hermes v0.20.0-alpha.1 — Vibe Graph Studio core

Graph engineering for people who don't know what graph engineering is: **describe what you want in plain English, get an executable plan explained back in numbered steps, run it, watch it work.**

## What's new (Phase 8 core)

- **Vibe builder** — `ariadne_plan` gains `suggest` (goal text → ranked template matches with reasons) and `instantiate` (template → filled task specs + a human-readable step-by-step explainer). Zero DAG syntax required from the human.
- **4 starter templates** — `saas-crud-api`, `scraper-digest`, `watch-alert` (the safe "loop"), `report-mailer`. Each has slot questions with sensible defaults.
- **Gate conditions + `bypassed` state** — tasks may carry `when: {task, field, equals|not_equals}` gates. A false gate *bypasses* the node without cascading failure — this is the correct primitive for conditional/looping automations (`watch-alert` demonstrates it end-to-end).
- **Runs API** — `GET /api/ariadne/graph/runs[/id]`: poll-friendly plan/task state feeding the Flow visualization (Flow tab UI lands next release).
- **Tier surfaced everywhere** — create/run summaries now report which autonomy tier executed them; runs accept a tier override.

## A real bug fixed by the new tests

The tool-outcome interpreter was treating registry error envelopes ("Unknown tool: …") as successful results — plans could sail through with garbage as data. The vibe-flow E2E test caught it; errors now fail loudly and cascade-skip properly.

## Verification

- 117/117 tests green
- Live prime engine exercised earlier at v0.19; all LLM-calling paths mocked in unit tests (hermetic suite, ~21s)

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT. Prime engine © Mario Zechner, MIT.
