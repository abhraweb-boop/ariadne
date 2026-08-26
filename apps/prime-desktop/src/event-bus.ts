/**
 * Prime Hermes — EventBus (S1: one SSE spine with replay).
 *
 * A single EventSource subscribes to the gateway's unified event stream.
 * On reconnect it sends `Last-Event-ID` so missed transitions are replayed —
 * panes never show stale state after a wake/blip. Panes subscribe by type.
 */

import { gatewayBase } from './api'

export interface BusEvent {
  id: string
  type: string
  payload: Record<string, unknown>
  ts: number
}

type Listener = (ev: BusEvent) => void

const listeners = new Map<string, Set<Listener>>()
let source: EventSource | null = null
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
    if (source) source.close()
    source = new EventSource(
      `${base}/api/prime/events${lastEventId ? `?after_id=${encodeURIComponent(lastEventId)}` : ''}`
    )
    source.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data) as BusEvent
        lastEventId = ev.id
        reconnectDelay = 1000
        dispatch(ev)
      } catch {
        /* malformed frame — ignore */
      }
    }
    source.onerror = () => {
      // EventSource auto-reconnects; we just track replay position.
      if (source) source.close()
      setTimeout(() => void connect(), reconnectDelay)
      reconnectDelay = Math.min(reconnectDelay * 2, 30_000)
    }
  } catch {
    setTimeout(() => void connect(), reconnectDelay)
  }
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
