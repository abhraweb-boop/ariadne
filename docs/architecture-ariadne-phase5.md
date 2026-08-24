# Ariadne — Architecture (Phase 5): Packaging & Distribution

Status: Phase 5 design · Owner: Ariadne · Date: 2026-08-24

## 0. Goal

Make Ariadne installable by someone who has never heard of Hermes: one command
per platform, branded artifacts, MIT license intact.

## 1. What upstream provides (inherited, not rebuilt)

The fork inherits complete packaging machinery:

- **Desktop**: electron-builder fully configured (`apps/desktop/package.json`
  `build` block) with per-platform targets — mac dmg+zip (notarize hook),
  win nsis+msi, linux AppImage+deb+rpm. Scripts: `npm run dist` /
  `dist:win[:msi|nsis]` / `dist:mac[...]` / `dist:linux`.
- **Agent core**: `scripts/install.sh|ps1|cmd` — uv-based installer that
  clones the repo, syncs the venv, runs setup.

## 2. Ariadne deltas

### D1. Branding pass (small, mechanical)

- `apps/desktop/package.json`: name/productName/description/appId suffix →
  "Ariadne" (`com.ariadne.agent`), artifactName prefix `Ariadne-`.
- Protocol scheme stays `hermes` for v0 (deep-link compat with the gateway
  pairing flow); revisit in a later release.
- Root `pyproject.toml`: description mentions Ariadne; version bumped to
  `0.21.0-a1` (fork epoch). Package name stays `hermes-agent` (import paths,
  console scripts, and the plugin ecosystem depend on it — renaming is a v2
  breaking change, not packaging).

### D2. Build verification on this machine (Windows)

- Renderer + electron-main build via `npm run build` (vite + bundlers).
- Installer artifact: `npm run dist:win` → NSIS exe under apps/desktop/release/.
- Smoke: installer exists, size sane; launch installed app is manual/user step.

### D3. Distribution channels (documented; execution needs repos/secrets)

- GitHub Releases on the Ariadne repo: attach per-platform desktop artifacts
  (built in CI — GH runners for mac/linux; windows-latest for NSIS).
- Agent core installs from the git URL directly:
  `curl ... | bash -s -- --repo <ariadne-repo-url>` once the installer's repo
  vars are parameterized (one-line change, kept pointing at upstream until
  the Ariadne repo is public).
- Code signing/notarization: out of scope for v0 alpha (unsigned artifacts +
  SmartScreen/Gatekeeper warnings documented in README).

### D4. License

MIT upstream license files are inherited untouched; Ariadne additions remain
MIT. No new license surface.

## 3. Gates

1. `npm run build` succeeds on Windows (renderer + main + native staging).
2. `npm run dist:win` produces an NSIS installer artifact.
3. Version/branding consistent across pyproject + desktop package.
4. Plan/README updated with install instructions.
