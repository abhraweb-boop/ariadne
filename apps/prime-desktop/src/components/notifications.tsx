/**
 * A5 — Notification stack.
 *
 * Fed by the event bus (G1 wires terminal events like plan.completed /
 * plan.failed / kernel crash). Toasts appear top-right, auto-dismiss after
 * 6s, click to dismiss. Honest states only — real events, never fake data.
 */

import { useEffect, useState } from 'react'

import { type BusEvent, onEvent } from '../event-bus'

export interface Notification {
  id: string
  title: string
  body?: string
  tone: 'info' | 'success' | 'error'
}

let nid = 0

export function toneFor(type: string): Notification['tone'] {
  if (type.endsWith('.failed') || type.endsWith('.error') || type.endsWith('.crash')) {return 'error'}

  if (type.endsWith('.completed') || type.endsWith('.done')) {return 'success'}

  return 'info'
}

export function titleFor(type: string, payload: Record<string, unknown>): { title: string; body?: string } {
  if (type === 'plan.completed') {return { title: 'Plan completed', body: (payload.goal as string | undefined)?.slice(0, 80) }}

  if (type === 'plan.failed') {return { title: 'Plan failed', body: (payload.goal as string | undefined)?.slice(0, 80) }}

  if (type === 'plan.cancelled') {return { title: 'Plan cancelled' }}

  if (type === 'kernel.crash') {return { title: 'Kernel crashed', body: String(payload.error ?? '') }}

  if (type === 'prime.agent_end') {return { title: 'Agent finished' }}

  if (type === 'prime.agent_error') {return { title: 'Agent error', body: String(payload.error ?? '') }}

  return { title: type }
}

export function Notifications() {
  const [items, setItems] = useState<Notification[]>([])

  useEffect(() => {
    const unsub = onEvent('*', (ev: BusEvent) => {
      // Skip heartbeats and internal markers — never toast them.
      if (ev.type === '_heartbeat' || ev.type === '_hb' || ev.id === '_hb') {return}
      const payload = (ev.payload ?? {}) as Record<string, unknown>
      const { title, body } = titleFor(ev.type, payload)

      const notif: Notification = {
        id: `n-${nid++}`,
        title,
        body,
        tone: toneFor(ev.type)
      }

      setItems((prev) => [...prev.slice(-4), notif])
      setTimeout(() => {
        setItems((prev) => prev.filter((n) => n.id !== notif.id))
      }, 6000)
    })

    return unsub
  }, [])

  if (items.length === 0) {return null}

  const toneColor = { info: '#5e6ad2', success: '#9ece6a', error: '#f7768e' }

  return (
    <div
      style={{
        position: 'fixed',
        top: 44,
        right: 12,
        zIndex: 300,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        pointerEvents: 'none'
      }}
    >
      {items.map((n) => (
        <button
          key={n.id}
          onClick={() => setItems((prev) => prev.filter((x) => x.id !== n.id))}
          style={{
            pointerEvents: 'auto',
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            maxWidth: 320,
            padding: '10px 12px',
            textAlign: 'left',
            background: '#1a1a1a',
            border: `1px solid ${toneColor[n.tone]}`,
            borderRadius: 8,
            color: 'var(--foreground, #efefef)',
            cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
            fontFamily: 'inherit'
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 4,
              background: toneColor[n.tone],
              marginTop: 4,
              flexShrink: 0
            }}
          />
          <span style={{ fontSize: 12 }}>
            <span style={{ fontWeight: 600, display: 'block' }}>{n.title}</span>
            {n.body && (
              <span style={{ color: 'var(--muted-foreground, #888)', fontSize: 11, display: 'block' }}>
                {n.body}
              </span>
            )}
          </span>
        </button>
      ))}
    </div>
  )
}
