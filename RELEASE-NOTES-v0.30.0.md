# Prime Hermes v0.30.0-alpha.1 — Dogfood-Verified, CI Clean

The release where the product proves itself through its own front door.

## What's new

- **Full HTTP dogfood passed** — plan seeded → server booted → `POST /api/prime-hermes/console/exec/{plan_id}` ran it → Runs API flipped `draft → done` (2/2 tasks) → Flow view served the live data. Every surface exercised over real HTTP with the dashboard token.
- **CI hygiene** — removed 6 inherited upstream workflows (deploy-site/Vercel hook, docker hub, docs site, install-e2e ×2, contributor-check) that failed noisily on every release for infrastructure this fork doesn't have. What remains: our `tests.yml` plus upstream CI relevant to the core. Verified zero remaining `release:` triggers.

## Verification

- Live exec round-trip: `{"ok":true,...,"final_state":"done","states":{"done":2}}`
- Flow endpoint serves; Runs API reflects post-exec state
- Local suite: 190/190 · GitHub Actions: green on Linux

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
