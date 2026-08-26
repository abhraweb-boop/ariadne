/**
 * G2 — Statusbar live widgets.
 *
 * Kernel busy/idle dot, running-plan count, prime worker state, ledger
 * usage. Polled / event-bus driven; each opens its pane on click.
 */

import { useEffect, useState } from 'react'

import { get } from '../api'
import { type BusEvent, onEvent } from '../event-bus'
import { StatusDot, type StatusState } from './status-dot'

/** Kernel busy/idle dot (polls /api/ariadne/kernel/status). */
export function KernelWidget({ onOpen }: { onOpen?: () => void }) {
  const [state, setState] = useState<StatusState>('unknown')

  useEffect(() => {
    const poll = () => {
      void get<{ ok: boolean; running: boolean }>('/api/ariadne/kernel/status')
        .then((r) => setState(r.ok ? (r.running ? 'busy' : 'connected') : 'offline'))
        .catch(() => setState('offline'))
    }
    poll()
    const interval = setInterval(poll, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <button onClick={onOpen} style={widgetBtnStyle} aria-label="Kernel status">
      <StatusDot state={state} label={`kernel ${state}`} />
      <span>kernel</span>
    </button>
  )
}

/** Running-plan count (polls /api/ariadne/plans). */
export function PlanCountWidget({ onOpen }: { onOpen?: () => void }) {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    const poll = () => {
      void get<{ ok: boolean; plans: Array<{ state: string }> }>('/api/ariadne/plans')
        .then((r) => {
          if (r.ok) {
            setCount(r.plans.filter((p) => !['done', 'cancelled', 'failed'].includes(p.state)).length)
          }
        })
        .catch(() => {})
    }
    poll()
    const interval = setInterval(poll, 10000)
    return () => clearInterval(interval)
  }, [])

  return (
    <button onClick={onOpen} style={widgetBtnStyle} aria-label="Running plans">
      <StatusDot state={count && count > 0 ? 'busy' : 'connected'} label={count ? `${count} running` : 'no plans'} />
      <span style={{ fontVariantNumeric: 'tabular-nums' }}>plans {count ?? '–'}</span>
    </button>
  )
}

/** Prime worker state (event-bus driven). */
export function WorkerWidget({ onOpen }: { onOpen?: () => void }) {
  const [state, setState] = useState<StatusState>('unknown')

  useEffect(() => {
    const unsub = onEvent('prime.*', (ev: BusEvent) => {
      if (ev.type === 'prime.spawned') {setState('busy')}
      if (ev.type === 'prime.agent_end' || ev.type === 'prime.stopped') {setState('connected')}
      if (ev.type === 'prime.agent_error') {setState('offline')}
    })
    return unsub
  }, [])

  return (
    <button onClick={onOpen} style={widgetBtnStyle} aria-label="Worker status">
      <StatusDot state={state} label={`worker ${state}`} />
      <span>worker</span>
    </button>
  )
}

/** Ledger entry count (polls /api/ariadne/ledger/entries). */
export function MemoryWidget({ onOpen }: { onOpen?: () => void }) {
  const [count, setCount] = useState<number | null>(null)

  useEffect(() => {
    const poll = () => {
      void get<{ ok: boolean; entries: unknown[] }>('/api/ariadne/ledger/entries')
        .then((r) => { if (r.ok) {setCount(r.entries.length)} })
        .catch(() => {})
    }
    poll()
    const interval = setInterval(poll, 15000)
    return () => clearInterval(interval)
  }, [])

  return (
    <button onClick={onOpen} style={widgetBtnStyle} aria-label="Ledger memory">
      <StatusDot state={count && count > 0 ? 'connected' : 'unknown'} label={count ? `${count} entries` : 'empty ledger'} />
      <span style={{ fontVariantNumeric: 'tabular-nums' }}>mem {count ?? '–'}</span>
    </button>
  )
}

const widgetBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  padding: '2px 8px',
  background: 'transparent',
  border: 'none',
  borderRadius: 3,
  color: 'var(--muted-foreground, #888)',
  cursor: 'pointer',
  fontSize: 11,
  fontFamily: 'inherit',
  lineHeight: 1
}
