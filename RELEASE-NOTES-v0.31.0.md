# Prime Hermes v0.31.0-alpha.1 — Goal Anchoring (Anti-Drift)

The fix for the oldest agent failure mode: **long builds that forget what they're building and wander off.** In Prime Hermes, drifting is now a detectable, correctable event — not silent behavior.

## Three structural layers

1. **Goal anchoring** — every prompt sent to prime/gemini/flo nodes now opens with:
   ```
   [GOAL] <the plan's goal>
   [MILESTONE] <this node's title>
   [SCOPE] Do ONLY this milestone's job. No unrelated refactors. Stop when done.
   ```
   The objective is the first thing every model call sees, every time.

2. **Context-pack discipline** — upstream artifacts injected via `{{task.result}}` are head+tail capped at ~2 KB. Long dependency chains can no longer drown the goal in accumulated noise (the mechanism behind classic context-drift). Small structured values stay native.

3. **Drift sentinel** — after prime/gemini nodes run, a cheap Gemini-Flash judge scores *did this output serve the node's intent?* An explicit `DRIFT` verdict becomes a retryable failure whose retry carries `[REFOCUS] Previous attempt drifted: <reason>` before the anchored prompt.

## Safety properties

- Judge is **conservative**: only an explicit `DRIFT:` verdict fails; anything ambiguous passes.
- Silent no-op when Google isn't configured — never blocks execution.
- Per-node opt-out: `"judge": false` in the payload.
- Deterministic nodes (tool/kernel/rlm/scout/flo/note) are never judged.
- Drift failures are classified as retryable *before* the ErrorDoctor's conservative permanent-default.
- Judge tokens flow through the budget governor's cost accounting.

## Verification

208/208 tests green (18 new). The drift→refocus→recover cycle is tested end-to-end with a fake engine: first attempt wanders ("a blog engine about cooking"), judge flags it, retry arrives with `[REFOCUS]`, second attempt succeeds on-goal.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
