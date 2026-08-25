# Prime Hermes v0.24.0-alpha.1 — Capability Acquisition & Inspiration Scoring

The harness now **chooses its own tools honestly** and **grades its teachers**.

## What's new (Phase 11)

- **Capability manifest** — reads a compiled master DAG and derives exactly which capabilities a build needs (technologies × domains).
- **Best-only skill selection, overlap-free by construction** — candidates scored on a transparent rubric (relevance 50 · completeness 30 · specificity 20 − slop), selected greedily best-first; anything whose coverage adds nothing new is rejected as `skipped_overlap`. A generic "do anything" skill structurally cannot outrank one that matches your stack.
- **Inspiration scoring — professional vs slop, quantified** — every scouted reference project gets 0–100: authority 25 · craft 30 (tests/CI/license/typing) · recency 15 · fit-to-plan 20, minus slop penalties capped at −40 (hype adjectives, emoji spam).
- **Stars can't buy tier** — full craft substitutes for popularity: a 50k-star testless hype repo scores below an unglamorous typed+tested+CI'd template. Tiers: gold ≥80 (citable) · silver ≥60 (citable) · bronze ≥40 (flagged) · below that it's dropped as slop entirely.

## Verification

154/154 tests green. The guarantees are tested, not aspirational: specific-beats-generic, overlap rejection, slop penalization, craft-beats-stars, tier boundaries, recency/fit sensitivity.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
