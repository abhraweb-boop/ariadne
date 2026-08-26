/**
 * Prime Hermes — EventBus (S1: one SSE spine with replay).
 *
 * A single fetch-based SSE stream subscribes to the gateway's unified event
 * stream. fetch (not EventSource) so we can attach the session token header.
 * On reconnect it sends `after_id` so missed transitions are replayed —
 * panes never show stale state after a wake/blip. Panes subscribe by type.
 */

import { gatewayBase, sessionToken } from './api'

export interface BusEvent {
  id: string
  type: string
  payload: Record<string, unknown>
  ts: number
}

type Listener = (ev: BusEvent) => void

const listeners = new Map<string, Set<Listener>>()
let controller: AbortController | null = null
let lastEventId: string | null = null
let reconnectDelay = 1000
let started = false

export function startEventBus(): void {
  if (started) return
  started = true
  void connect()
}

async function connect(): Promise<void> {
  try {
    const base = await gatewayBase()
    const token = await sessionToken()
    if (controller) controller.abort()
    controller = new AbortController()
    const headers: Record<string, string> = {}
    if (token) headers['X-Hermes-Session-Token'] = token

    const res = await fetch(
      `${base}/api/ariadne/events${lastEventId ? `?after_id=${encodeURIComponent(lastEventId)}` : ''}`,
      { headers, signal: controller.signal }
    )
    if (!res.ok || !res.body) throw new Error(`events ${res.status}`)

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        const line = frame.replace(/^data: /, '').trim()
        if (!line) continue
        try {
          const ev = JSON.parse(line) as BusEvent
          if (ev.id && ev.id !== '_eof') lastEventId = ev.id
          reconnectDelay = 1000
          dispatch(ev)
        } catch {
          /* malformed frame — ignore */
        }
      }
    }
    // Stream ended cleanly (heartbeat eof) — reconnect.
    scheduleReconnect()
  } catch {
    scheduleReconnect()
  }
}

function scheduleReconnect(): void {
  setTimeout(() => void connect(), reconnectDelay)
  reconnectDelay = Math.min(reconnectDelay * 2, 30_000)
}

function dispatch(ev: BusEvent): void {
  const set = listeners.get(ev.type)
  if (set) for (const fn of [...set]) fn(ev)
  const all = listeners.get('*')
  if (all) for (const fn of [...all]) fn(ev)
}

export function onEvent(
  type: string,
  fn: Listener
): () => void {
  let set = listeners.get(type)
  if (!set) {
    set = new Set()
    listeners.set(type, set)
  }
  set.add(fn)
  return () => {
    set!.delete(fn)
  }
}

/** Reconnect now (e.g. after settings change). */
export function resetEventBus(): void {
  lastEventId = null
  void connect()
}
