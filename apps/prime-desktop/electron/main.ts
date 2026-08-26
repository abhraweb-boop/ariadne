/**
 * Prime Hermes — Electron main process (minimal, thin).
 *
 * Owns the machine facts only: window lifecycle, a typed capability bridge
 * to the renderer, and gateway base-URL resolution. All agent capability
 * lives in the gateway backend (FastAPI), reached by the renderer over
 * fetch/EventSource through the bridge.
 */

import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { app, BrowserWindow, ipcMain } from 'electron'

const __dirname = dirname(fileURLToPath(import.meta.url))

// Gateway discovery ladder (desktop AGENTS.md: cross everything as an
// observable ladder). rung 1 = env override, 2 = install-stamp.json,
// 3 = default localhost.
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

function createWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 600,
    title: 'Prime Hermes',
    backgroundColor: '#101012',
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

  return win
}

app.whenReady().then(() => {
  const gatewayBase = resolveGatewayBase()

  // Typed capability bridge: renderer asks for machine + gateway facts.
  ipcMain.handle('prime:gateway-base', () => gatewayBase)
  ipcMain.handle('prime:platform', () => process.platform)
  ipcMain.handle('prime:versions', () => ({
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  }))

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {createWindow()}
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {app.quit()}
})
