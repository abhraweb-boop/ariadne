/**
 * Prime Hermes — Electron main process.
 *
 * Owns the machine facts only: window lifecycle, a typed capability bridge
 * to the renderer, gateway base-URL resolution, and — since P2 (market
 * release) — the EMBEDDED GATEWAY: if no gateway answers on the configured
 * base, we spawn the bundled runtime (`resources/runtime/hermes.exe`) as a
 * child process with a fresh session token, wait for health, and restart it
 * with backoff if it dies. Double-click-to-run: the shipped artifact needs
 * zero manual setup.
 */

import { type ChildProcess, spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { app, BrowserWindow, ipcMain } from 'electron'
import { autoUpdater } from 'electron-updater'

const __dirname = dirname(fileURLToPath(import.meta.url))

// ── Gateway discovery ────────────────────────────────────────────────────
// Rung ladder (desktop AGENTS.md: cross everything as an observable ladder):
// 1) env override, 2) install-stamp.json, 3) default localhost.
function resolveGatewayBase(): string {
  const fromEnv = process.env.PRIME_GATEWAY_BASE

  if (fromEnv) {return fromEnv.replace(/\/+$/, '')}
  const stamp = join(__dirname, '..', 'install-stamp.json')

  try {
    if (existsSync(stamp)) {
      const data = JSON.parse(readFileSync(stamp, 'utf-8'))

      if (data?.gatewayBase) {return String(data.gatewayBase).replace(/\/+$/, '')}
    }
  } catch {
    /* fall through to default */
  }

  return 'http://127.0.0.1:8000'
}

function resolveSessionToken(): string {
  // Passed from the environment by whoever launched us; empty means the
  // gateway is unauthenticated (auth_required=False) and no header is sent.
  return process.env.HERMES_DASHBOARD_SESSION_TOKEN ?? ''
}

// ── Embedded gateway (P2) ────────────────────────────────────────────────
let gatewayProc: ChildProcess | null = null
let gatewayCrashes = 0
let shuttingDown = false

/** The bundled runtime dir: resources/runtime in packaged, ../.. in dev. */
function runtimeDir(): string | null {
  const candidates = [
    join(process.resourcesPath ?? '', 'runtime'),
    join(__dirname, '..', 'resources', 'runtime'),
    join(__dirname, '..', '..', 'resources', 'runtime')
  ]

  return candidates.find((c) => existsSync(join(c, 'hermes.exe'))) ?? null
}

async function gatewayHealthy(base: string, token: string): Promise<boolean> {
  try {
    const res = await fetch(`${base}/api/health`, {
      signal: AbortSignal.timeout(1500),
      headers: token ? { 'X-Hermes-Session-Token': token } : {}
    })

    return res.ok
  } catch {
    return false
  }
}

/**
 * Spawn the embedded gateway. Returns true when the child is up.
 * Uses the runtime's own venv python via the hermes.exe shim.
 */
function spawnGateway(base: string, token: string): ChildProcess {
  const runtime = runtimeDir()
  const exe = runtime ? join(runtime, 'hermes.exe') : 'hermes'

  const env: NodeJS.ProcessEnv = {
    ...process.env,
    HERMES_DASHBOARD_SESSION_TOKEN: token
  }

  // A freshly generated token only makes sense if the gateway requires auth;
  // when it doesn't, the header is ignored server-side. We always pass one so
  // a future auth-enabled runtime works out of the box.
  const proc = spawn(exe, ['gateway'], { cwd: runtime ?? undefined, env, windowsHide: true })
  gatewayProc = proc
  gatewayCrashes += 1

  proc.on('exit', (code) => {
    gatewayProc = null

    if (shuttingDown) {return}
    // Backoff: 1s, 2s, 4s … cap at 30s; give up after 3 rapid crashes so the
    // window can show an honest "gateway failed" state instead of a busy loop.
    const delay = Math.min(1000 * 2 ** Math.min(gatewayCrashes, 5), 30_000)
    setTimeout(() => {
      if (!shuttingDown) {spawnGateway(base, token)}
    }, delay)
  })

  return proc
}

/** Bring the gateway up: probe → spawn → wait for health (bounded). */
async function ensureGateway(base: string, token: string): Promise<{ base: string; token: string; spawned: boolean }> {
  if (await gatewayHealthy(base, token)) {
    gatewayCrashes = 0

    return { base, token, spawned: false }
  }

  const runtime = runtimeDir()

  if (!runtime && process.env.PRIME_NO_EMBEDDED_GATEWAY !== '1') {
    // Dev: no bundled runtime — let the user run their own gateway; the app
    // still works (offline states) and connects once one appears.
    return { base, token, spawned: false }
  }

  spawnGateway(base, token)

  // Wait for health: up to 30s, polling every 500ms.
  const deadline = Date.now() + 30_000

  while (Date.now() < deadline) {
    if (await gatewayHealthy(base, token)) {
      gatewayCrashes = 0

      return { base, token, spawned: true }
    }

    await new Promise((r) => setTimeout(r, 500))
  }

  return { base, token, spawned: true } // child alive but not yet healthy — renderer shows connecting
}

// ── Window ───────────────────────────────────────────────────────────────
let win: BrowserWindow | null = null

function createWindow(): BrowserWindow {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 600,
    title: 'Prime Hermes',
    backgroundColor: '#101012',
    icon: join(__dirname, '..', 'assets', 'icon.ico'),
    // A1: custom titlebar — hidden native frame, renderer draws drag region
    // + window controls (min/max/close) via the bridge.
    titleBarStyle: 'hidden',
    webPreferences: {
      preload: join(__dirname, '..', 'dist', 'electron-preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  const devServer = process.env.HERMES_DESKTOP_DEV_SERVER

  if (devServer) {
    void win.loadURL(devServer)
  } else {
    void win.loadFile(join(__dirname, '..', 'dist', 'index.html'))
  }

  win.on('closed', () => { win = null })

  return win
}

app.whenReady().then(async () => {
  const gatewayBase = resolveGatewayBase()
  const sessionToken = resolveSessionToken() || `ph-${randomBytes(16).toString('hex')}`
  const gateway = await ensureGateway(gatewayBase, sessionToken)

  // Typed capability bridge: renderer asks for machine + gateway facts.
  ipcMain.handle('prime:gateway-base', () => gateway.base)
  ipcMain.handle('prime:session-token', () => gateway.token)
  ipcMain.handle('prime:platform', () => process.platform)
  ipcMain.handle('prime:versions', () => ({
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  }))
  // P2: gateway health + restart (Settings tab).
  ipcMain.handle('prime:gateway-status', async () => ({
    healthy: await gatewayHealthy(gateway.base, gateway.token),
    spawned: gatewayProc !== null,
    base: gateway.base
  }))
  ipcMain.handle('prime:gateway-restart', async () => {
    if (gatewayProc) {
      gatewayProc.kill()
      gatewayProc = null
    }

    await ensureGateway(gateway.base, gateway.token)

    return { ok: true }
  })

  // A1: window controls for the custom titlebar.
  ipcMain.handle('prime:window:minimize', () => { win?.minimize() })
  ipcMain.handle('prime:window:maximize', () => {
    if (!win) {return}

    if (win.isMaximized()) {
      win.unmaximize()
    } else {
      win.maximize()
    }
  })
  ipcMain.handle('prime:window:close', () => { win?.close() })

  // P4: auto-update (channel: GitHub Releases; publish later configured in
  // electron-builder "publish" — latest.yml is produced by the builder).
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true
  ipcMain.handle('prime:update:check', async () => {
    try {
      const result = await autoUpdater.checkForUpdates()

      return { available: !!result?.updateInfo?.version, version: result?.updateInfo?.version ?? '' }
    } catch (e) {
      return { available: false, version: '', error: String(e) }
    }
  })
  ipcMain.handle('prime:update:download', async () => {
    try {
      await autoUpdater.downloadUpdate()

      return { ok: true }
    } catch (e) {
      return { ok: false, error: String(e) }
    }
  })
  ipcMain.handle('prime:update:install', () => {
    autoUpdater.quitAndInstall()

    return { ok: true }
  })

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {createWindow()}
  })
})

app.on('before-quit', () => {
  shuttingDown = true

  if (gatewayProc) {
    gatewayProc.kill()
    gatewayProc = null
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {app.quit()}
})
