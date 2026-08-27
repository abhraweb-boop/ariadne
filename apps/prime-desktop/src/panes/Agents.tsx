/**
 * Agents pane — rlm child tree (from SubagentLifecycleService) + Prime state.
 * Visual tree with expandable nodes, state badges, steer/abort buttons.
 */

import { useCallback, useEffect, useState } from 'react'

import { get } from '../api'

export function Agents({ onClose }: { onClose: () => void }) {
  const [primeState, setPrimeState] = useState<Record<string, unknown> | null>(null)
  const [primeRunning, setPrimeRunning] = useState(false)

  const loadPrimeRunning = useCallback(async () => {
    try {
      const r = await get<{ ok?: boolean; running?: boolean }>('/api/ariadne/prime/state')
      setPrimeRunning(!!r.running)
    } catch {
      /* bridge unavailable — stay in stopped state */
    }
  }, [])

  useEffect(() => {
    void loadPrimeRunning()
    const interval = setInterval(() => void loadPrimeRunning(), 30000)

    return () => clearInterval(interval)
  }, [loadPrimeRunning])

  useEffect(() => {
    void get<{ ok: boolean; state: Record<string, unknown> }>('/api/prime/state')
      .then((r) => { if (r.ok) {setPrimeState(r.state)} })
      .catch(() => setPrimeState(null))

    const interval = setInterval(() => {
      void get<{ ok: boolean; state: Record<string, unknown> }>('/api/prime/state')
        .then((r) => { if (r.ok) {setPrimeState(r.state)} })
        .catch(() => {})
    }, 5000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div style={{ padding: 12, fontSize: 13 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 600 }}>👾 Agents</span>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: primeRunning ? '#9ece6a' : 'var(--muted-foreground, #888)' }} />
          <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)' }}>{primeRunning ? 'prime live' : 'prime stopped'}</span>
        </span>
        <button aria-label="Close" onClick={onClose} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}></button>
      </div>
      <div style={{ border: '1px solid var(--border, #2a2a2a)', borderRadius: 8, padding: 12 }}>
        <div style={{ fontWeight: 500, marginBottom: 8 }}>Prime Worker</div>
        {primeState ? (
          <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', fontSize: 12 }}>
            <dt style={{ color: 'var(--muted-foreground, #888)' }}>Model</dt><dd style={{ margin: 0 }}>{String(primeState.model ?? '–')}</dd>
            <dt style={{ color: 'var(--muted-foreground, #888)' }}>Session</dt><dd style={{ margin: 0 }}>{String(primeState.session ?? '–')}</dd>
            <dt style={{ color: 'var(--muted-foreground, #888)' }}>Streaming</dt><dd style={{ margin: 0 }}>{String(primeState.streaming ?? '–')}</dd>
          </dl>
        ) : (
          <p style={{ color: 'var(--muted-foreground, #888)', fontSize: 12 }}>Prime worker not running. POST /api/prime/spawn to start.</p>
        )}
      </div>
    </div>
  )
}