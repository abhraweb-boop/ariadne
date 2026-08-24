#!/usr/bin/env bash
# Build vendored Prime Agent -> packages/coding-agent/dist/bundle/cli.js
set -euo pipefail
cd "$(dirname "$0")/../vendor/prime-agent"
echo "[build-prime] npm ci..."
npm ci --no-audit --no-fund 2>&1 | tail -3
echo "[build-prime] building coding-agent bundle..."
(cd packages/coding-agent && npm run build 2>&1 | tail -5)
test -f packages/coding-agent/dist/bundle/cli.js && echo "PRIME_BUILD_OK" || {
  echo "PRIME_BUILD_FAILED"; exit 1; }
