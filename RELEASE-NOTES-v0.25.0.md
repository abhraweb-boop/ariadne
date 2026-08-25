# Prime Hermes v0.25.0-alpha.1 — Visible Rebuilds

The fix for the oldest lie in AI coding: **"done ✓" with nothing observable happening.** Now a change is a physical event you can watch and verify.

## The cycle

```
MAP       requested change -> exact affected files
DEMOLISH  files archived to .rebuilds/gen-N/, then DELETED (the void is visible)
REBUILD   fresh implementations written into the void
PROOF     byte-diff vs archive -> per-file verdicts + counts
```

## The honesty mechanics

- **Claim gate** (`require_proof`) — any rebuild response *without* a proof bundle is rejected: `proof missing — rerun the rebuild`. A bare "success" structurally cannot pass.
- **Honest no-op** — if rebuilding produces byte-identical output, the verdict is `noop` ("nothing needed changing"), explicitly NOT counted as work.
- **Safety** — nothing outside the build directory can ever be demolished; mass rewrites (>40% of files) require explicit confirmation; archives keep 5 generations; `restore()` aborts cleanly.
- **Incomplete detection** — demolished-but-never-rebuilt files report `missing`, so an interrupted rebuild can't masquerade as done.

## Verification

166/166 tests green. Every mechanic tested: full-cycle proof, noop honesty, added-file detection, incomplete detection, outside-dir refusal, mass-confirm gate, restore, generation pruning, claim gate.

Built on [Hermes Agent](https://github.com/NousResearch/hermes-agent). MIT.
