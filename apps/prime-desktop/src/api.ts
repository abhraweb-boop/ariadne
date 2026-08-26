/**
 * Prime Hermes — typed gateway client.
 *
 * Resolves the gateway base URL through the preload bridge once, then talks
 * to the FastAPI gateway with fetch + EventSource. Renderer never reaches for
 * Node/Electron directly (desktop AGENTS.md: keep the seams clean).
 */

declare global {
  interface Window {
    primeHermes?: {
      gatewayBase: () => Promise<string>
      sessionToken: () => Promise<string>
      platform: () => Promise<string>
      versions: () => Promise<{ electron: string; chrome: string; node: string }>
      // A1: window controls
      windowMinimize?: () => Promise<void>
      windowMaximize?: () => Promise<void>
      windowClose?: () => Promise<void>
    }
  }
}

let cachedBase: string | null = null
let cachedToken: string | null = null

export async function sessionToken(): Promise<string> {
  if (cachedToken !== null) return cachedToken
  if (window.primeHermes) {
    cachedToken = await window.primeHermes.sessionToken()
  } else {
    cachedToken = ''
  }
  return cachedToken
}

export async function gatewayBase(): Promise<string> {
  if (cachedBase) {return cachedBase}

  if (window.primeHermes) {
    cachedBase = await window.primeHermes.gatewayBase()
  } else {
    // Browser dev fallback (vite without electron): assume local gateway.
    cachedBase = 'http://127.0.0.1:8000'
  }

  return cachedBase
}

export interface ApiOptions {
  method?: string
  body?: unknown
  headers?: Record<string, string>
  timeoutMs?: number
}

export async function api<T = unknown>(
  path: string,
  opts: ApiOptions = {}
): Promise<T> {
  const base = await gatewayBase()
  const token = await sessionToken()
  const controller = new AbortController()

  const timeout = setTimeout(
    () => controller.abort(),
    opts.timeoutMs ?? 60_000
  )

  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...opts.headers
    }
    if (token) {
      headers['X-Hermes-Session-Token'] = token
    }
    const res = await fetch(`${base}${path}`, {
      method: opts.method ?? 'GET',
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: controller.signal
    })

    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`API ${opts.method ?? 'GET'} ${path} -> ${res.status}: ${text.slice(0, 300)}`)
    }

    return (await res.json()) as T
  } finally {
    clearTimeout(timeout)
  }
}

/** POST convenience. */
export function post<T = unknown>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: 'POST', body })
}

/** GET convenience. */
export function get<T = unknown>(path: string): Promise<T> {
  return api<T>(path)
}
