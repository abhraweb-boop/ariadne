# Prime Hermes v0.29.0-alpha.1 — Console Runs, CI, Docs That Match Reality

The closing release of the build sprint: the product is now self-serve end-to-end.

## What's new

- **Console `/exec`** — run any plan straight from the Console (`POST /api/prime-hermes/console/exec/{plan_id}`), with tier override, a budget-gate check before execution, and cost recording into the governor after.
- **CI on push** — GitHub Actions runs the hermetic Prime Hermes suite (uv sync `dev`+`ariadne`, pytest) on every push to main and every PR. LLM keys are explicitly blanked in CI so the suite can never go live.
- **README rewritten** — it finally describes what shipped: graph-as-loop, Prime inside, Guided Build, self-modifying graphs, grounding, anti-slop scoring, visible rebuilds, self-healing + budget leash, Google SDK & ruflo — with quickstart.

## Verification

190/190 tests green.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
