#!/usr/bin/env node
// write-build-stamp.mjs — records install-time facts for the packaged app.
import { writeFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const stamp = {
  app: 'prime-hermes',
  gatewayBase: process.env.PRIME_GATEWAY_BASE || 'http://127.0.0.1:8000',
  builtAt: new Date().toISOString()
}
writeFileSync(resolve(root, 'dist', 'install-stamp.json'), JSON.stringify(stamp, null, 2))
