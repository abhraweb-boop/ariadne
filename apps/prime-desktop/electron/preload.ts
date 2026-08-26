/**
 * Prime Hermes — preload bridge.
 *
 * Exposes a narrow, typed surface: machine facts + the gateway base URL so
 * the renderer can talk to the FastAPI gateway with fetch/EventSource.
 * No Node/Electron power leaks into the renderer.
 */

import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('primeHermes', {
  gatewayBase: (): Promise<string> => ipcRenderer.invoke('prime:gateway-base'),
  platform: (): Promise<string> => ipcRenderer.invoke('prime:platform'),
  versions: (): Promise<{ electron: string; chrome: string; node: string }> =>
    ipcRenderer.invoke('prime:versions')
})
