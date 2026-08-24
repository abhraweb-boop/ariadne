# Vendored: Prime Agent

- **Upstream:** https://github.com/PrimeIntellect-ai/prime-agent
- **Pinned commit:** see `prime-agent-PIN.txt` (shallow clone of that SHA)
- **License:** MIT — © 2025 Mario Zechner / Prime Intellect contributors
- **Modifications:** none. Source vendored as-is; built artifacts produced by `scripts/build-prime.sh`.

## Why vendored

Prime Hermes embeds Prime Agent as an internal execution engine (`--mode rpc`
JSONL subprocess). There is no npm package for it upstream, so a pinned source
clone is the only reproducible supply path.

## Upgrade procedure

1. `cd vendor/prime-agent && git fetch --unshallow && git checkout <new-sha>`
2. Update `prime-agent-PIN.txt`.
3. Re-run `scripts/build-prime.sh` → must print `PRIME_BUILD_OK`.
4. Re-run protocol fixture tests: `pytest tests/ariadne/test_prime_engine.py`.
5. Commit both the submodule-style bump and refreshed fixtures together.
