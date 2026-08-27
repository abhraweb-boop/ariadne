/**
 * P1/P2 — Bundle the gateway runtime into resources/runtime/.
 *
 * Copies the venv hermes runtime (hermes.exe + venv site-packages + the
 * hermes_cli package) so the packaged app can spawn the gateway embedded.
 *
 * Usage: node scripts/bundle-runtime.mjs [--src <repo-root>]
 *
 * The source is the hermes-core repo root (where .venv/Scripts/hermes.exe
 * lives). Output: apps/prime-desktop/resources/runtime/
 */

import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const APP = resolve(HERE, '..')
const REPO = process.argv.includes('--src')
  ? resolve(process.argv[process.argv.indexOf('--src') + 1])
  : resolve(APP, '..', '..') // hermes-core
const OUT = join(APP, 'resources', 'runtime')

const VENV = join(REPO, '.venv')

if (!existsSync(join(VENV, 'Scripts', 'hermes.exe'))) {
  console.error(`hermes.exe not found under ${VENV}\\Scripts — run the repo bootstrap first.`)
  process.exit(1)
}

console.log(`Bundling runtime from ${REPO}`)
rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })

// 1. hermes.exe + the Scripts shims it needs (activate, DLLs are in venv root)
cpSync(join(VENV, 'Scripts', 'hermes.exe'), join(OUT, 'hermes.exe'))
for (const f of ['python.exe', 'pythonw.exe']) {
  const src = join(VENV, 'Scripts', f)
  if (existsSync(src)) cpSync(src, join(OUT, f))
}

// 2. The venv library (site-packages + stdlib) — this is the bulk (~100-200MB)
cpSync(join(VENV, 'Lib'), join(OUT, 'Lib'), { recursive: true })

// 3. The hermes_cli package + plugins + skills (source, imported by the venv python)
cpSync(join(REPO, 'hermes_cli'), join(OUT, 'hermes_cli'), { recursive: true })
if (existsSync(join(REPO, 'plugins'))) {
  cpSync(join(REPO, 'plugins'), join(OUT, 'plugins'), { recursive: true })
}
if (existsSync(join(REPO, 'skills'))) {
  cpSync(join(REPO, 'skills'), join(OUT, 'skills'), { recursive: true })
}

// 4. A tiny launcher script the app calls instead of hermes.exe directly
//    (hermes.exe needs its DLLs beside it; python.exe shims handle that).
import { writeFileSync } from 'node:fs'
writeFileSync(
  join(OUT, 'launch-gateway.cmd'),
  [
    '@echo off',
    'setlocal',
    `set "PH_RUNTIME=%~dp0"`,
    `"%PH_RUNTIME%hermes.exe" %*`,
    'endlocal'
  ].join('\r\n'),
  'utf-8'
)

// Size estimate
import { statSync, readdirSync } from 'node:fs'
function dirSize(p) {
  let total = 0
  for (const e of readdirSync(p, { withFileTypes: true })) {
    const full = join(p, e.name)
    total += e.isDirectory() ? dirSize(full) : statSync(full).size
  }
  return total
}
const mb = (dirSize(OUT) / 1024 / 1024).toFixed(0)
console.log(`runtime bundled -> ${OUT} (${mb} MB)`)
