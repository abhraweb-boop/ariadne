# Prime Hermes v0.21.0-alpha.1 — Guided Build Mode

**"I want to build a web app but I don't know how"** now has an answer that walks you through it.

## What's new (Phase 9)

- **Build sessions** — `ariadne_guide action=start {"goal": "..."}` opens a guided build; progress persists in SQLite, so sessions survive restarts.
- **Every step explained, every option weighed** — MCQs where each option carries *what it is* and *what it will cost/change* ("The public → real logins and hosting costs; ~2 extra steps at the end").
- **"You decide"** — say the word (action=decide) and the guide picks the recommended path, logging its rationale and impact so `/why` can always reconstruct why your app is the way it is.
- **Too many options? Guide decides.** Milestones marked `auto` (like stack choice) resolve transparently with stated impact.
- **Recovery dialogue** — a failed build step becomes a choice, not a dead end: Retry / Change approach / Skip this part — each with its consequence spelled out.
- **web-app archetype v1** — idea-clarify → stack auto-choice → scaffold (with live-URL payoff moment) → data model → polish.

## Try it

```
ariadne_guide {"action":"start","goal":"a habit tracker for me"}
ariadne_guide {"action":"answer","build_id":"bld-x","question_id":"audience","option_id":"just-me"}
ariadne_guide {"action":"decide","build_id":"bld-x"}     # "you decide"
ariadne_guide {"action":"why","build_id":"bld-x"}
```

## Verification

130/130 tests green. Tool-surface roundtrip covered: start → answer → why → abandon.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
