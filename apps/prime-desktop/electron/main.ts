/**
 * Prime Hermes — Electron main process.
 *
 * Owns the machine facts only: window lifecycle, a typed capability bridge
 * to the renderer, and gateway base-URL resolution. All agent capability
 * lives in the gateway backend (FastAPI), reached by the renderer over
 * fetch/EventSource through the bridge.
 */

import { app, BrowserWindow, ipcMain } from 'electron'
import { existsSync, readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

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

function resolveSessionToken(): string {
  // Passed from the environment by whoever launched us; empty means the
  // gateway is unauthenticated (auth_required=False) and no header is sent.
  return process.env.HERMES_DASHBOARD_SESSION_TOKEN ?? ''
}

let win: BrowserWindow | null = null

function createWindow(): BrowserWindow {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 600,
    title: 'Prime Hermes',
    backgroundColor: '#101012',
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

app.whenReady().then(() => {
  const gatewayBase = resolveGatewayBase()
  const sessionToken = resolveSessionToken()

  // Typed capability bridge: renderer asks for machine + gateway facts.
  ipcMain.handle('prime:gateway-base', () => gatewayBase)
  ipcMain.handle('prime:session-token', () => sessionToken)
  ipcMain.handle('prime:platform', () => process.platform)
  ipcMain.handle('prime:versions', () => ({
    electron: process.versions.electron,
    chrome: process.versions.chrome,
    node: process.versions.node
  }))

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

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {createWindow()}
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {app.quit()}
})
