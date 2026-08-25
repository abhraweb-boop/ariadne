# Prime Hermes

**A graph-engineered build agent for vibe coders** — a fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) (formerly **Ariadne**) where you describe what you want in plain English, answer a few explained questions, and an executable task graph builds it — grounded, self-healing, and impossible to lie to you.

## What makes it different

- **The graph is the loop.** Plans are executable DAGs: kernel cells, prime workers, Gemini calls, ruflo swarms, tool invocations, and condition notes — wired by dependencies, run with parallel branches, retries, and gate conditions (`when` → bypass, not failure).
- **Prime engine inside.** Vendored [prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) over RPC as a first-class worker; autonomy tiers `governed | unleashed` (unleashed = 5 attempts, hour-long cells, auto-steer). Hard floors never move: no credential entry, no payment UI.
- **Guided Build Mode.** `ariadne_guide` walks non-coders through milestones with MCQs where every option carries its impact; say "you decide" and it chooses transparently (`/why` replays the reasoning); failures become recovery choices (retry / change approach / skip).
- **Self-modifying graphs.** `patch_plan` diffs your edits against the running plan by content hash: finished work survives untouched, only the changed branch (and its dependents) resets.
- **Grounded builds.** `scout` nodes fetch official docs + reference projects per technology before code is written; unverified tech is stamped UNVERIFIED, never invented.
- **Anti-slop scoring.** Skill candidates compete on a transparent rubric (overlaps rejected); inspiration projects are graded authority/craft/recency/fit — craft beats stars, slop is dropped.
- **Visible rebuilds.** Changes are physical: files are archived, erased, rebuilt, and proven with byte-level diff bundles. A bare "done ✓" without proof is structurally rejected; identical output reports honest `noop`.
- **Self-healing + budget leash.** Every failure is classified (transient/environmental/logical/permanent) into automatic playbooks — only true permanents reach a human. Unleashed runs carry a spending cap that warns at 50% and pauses at the limit.
- **Google SDK + ruflo inside.** In-process Gemini provider and vendored ruflo swarms as ordinary node kinds behind clean adapter seams.

## Try it

```bash
git clone https://github.com/abhraweb-boop/ariadne.git
cd ariadne
uv sync --extra dev --extra ariadne
scripts/build-prime.sh          # build the vendored prime engine

# run the dashboard server, then:
#   /api/prime-hermes/console/   ← text console (slash commands)
#   /api/ariadne/graph/flow      ← live Flow view of running plans
```

Tool surface: `ariadne_plan` (create/suggest/instantiate), `ariadne_exec` (run),
`ariadne_guide` (start/answer/decide/why), `ariadne_prime`, plus the kernel/rlm tools.

## Status

**Alpha, feature-complete against its design brief.** Windows x64 is primary;
macOS/Linux not yet packaged. CI runs the hermetic test suite on every push.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent) — see [`HERMES-README.md`](HERMES-README.md) for the underlying platform. MIT. Prime engine © Mario Zechner, MIT · ruflo © ruvnet, MIT.
