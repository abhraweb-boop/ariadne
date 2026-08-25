# Prime Hermes v0.32.0-alpha.1 — Heals Journal & Secret-Scan Gate

Completes Phase 14 (self-healing hardening): the doctor now has a **public memory** and the executor has a **credential tripwire**.

## What's new

- **`/heals` journal** — every autonomous fix is now recorded and visible:
  - `GET /api/prime-hermes/console/heals` + `/heals` Console command
  - Fed by ErrorDoctor playbooks (pip installs, port kills, retries) *and* the P15 drift sentinel
  - Process-wide, capped at 200 entries, newest-first
- **Secret-scan gate** (`ariadne_runtime/secret_scan.py`) — task payloads are scanned for credential shapes before execution: OpenAI/Anthropic/Google/GitHub/AWS/Slack keys, bearer headers, private-key blocks, assigned secrets.
  - **Advisory by default** (findings logged, execution proceeds)
  - **Strict mode**: `store.set_plan_context(pid, {"secret_scan": "strict"})` → findings become task failures with a fix hint (*"move secrets to env references"*)
  - Env-var *references* (`process.env.X`, `os.environ[...]`) and placeholder values (`your-api-key`, `${VAR}`) are exempt — only literals trip it
- **`plan_context` table** — per-plan execution context storage on TaskStore.

## Verification

219/219 tests green (11 new).

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
