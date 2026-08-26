/**
 * Prime Hermes — preload bridge.
 *
 * Exposes a narrow, typed surface: machine facts, gateway base URL, and
 * window controls for the custom titlebar (A1). No Node/Electron power
 * leaks into the renderer.
 */

import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('primeHermes', {
  gatewayBase: (): Promise<string> => ipcRenderer.invoke('prime:gateway-base'),
  sessionToken: (): Promise<string> => ipcRenderer.invoke('prime:session-token'),
  platform: (): Promise<string> => ipcRenderer.invoke('prime:platform'),
  versions: (): Promise<{ electron: string; chrome: string; node: string }> =>
    ipcRenderer.invoke('prime:versions'),

  // A1: window controls
  windowMinimize: (): Promise<void> => ipcRenderer.invoke('prime:window:minimize'),
  windowMaximize: (): Promise<void> => ipcRenderer.invoke('prime:window:maximize'),
  windowClose: (): Promise<void> => ipcRenderer.invoke('prime:window:close'),
})