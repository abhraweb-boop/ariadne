/**
 * S1 — Self-improvement pane: refine loop + heals journal.
 *
 * Refine: captures current state as a ledger entry. Heals: shows recent
 * self-healing events from the watchdog.
 */

import { useCallback, useEffect, useState } from 'react'

import { get, post } from '../api'

interface HealEvent {
  id?: string
  what?: string
  when?: number
  outcome?: string
}

export function SelfImprovePane({ onClose }: { onClose: () => void }) {
  const [heals, setHeals] = useState<HealEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refineGoal, setRefineGoal] = useState('')
  const [refineMsg, setRefineMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok?: boolean; heals?: HealEvent[] }>('/api/ariadne/heals')
      setHeals(r.heals ?? [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const refine = useCallback(async () => {
    setRefineMsg('Running…')

    try {
      const r = await post<{ ok: boolean; entry?: { id?: string } }>('/api/ariadne/refine', { goal: refineGoal })

      if (r.ok) {
        setRefineMsg(`Refine recorded${r.entry?.id ? ` (${r.entry.id})` : ''}.`)
        setRefineGoal('')
      } else {
        setRefineMsg('Refine failed.')
      }
    } catch (e) {
      setRefineMsg(`Failed: ${String(e)}`)
    }
  }, [refineGoal])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>🧠 Self-Improve</span>
        <button aria-label="Close" onClick={onClose} style={{ ...ghostBtn, marginLeft: 'auto' }}>✕</button>
      </div>

      {/* Refine */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>Refine (self-improvement snapshot)</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            onChange={(e) => setRefineGoal(e.target.value)}
            placeholder="What to improve? (optional)"
            style={inputStyle}
            value={refineGoal}
          />
          <button disabled={!refineGoal.trim()} onClick={() => void refine()} style={{ ...ghostBtn, opacity: refineGoal.trim() ? 1 : 0.5 }}>
            Refine
          </button>
        </div>
        {refineMsg && <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginTop: 6 }}>{refineMsg}</div>}
      </div>

      {/* Heals journal */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)' }}>Heals journal</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
            {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
          </div>
        )}
        {!loading && !error && heals.length === 0 && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>
            No self-healing events. The agent is healthy.
          </div>
        )}
        {heals.map((h, i) => (
          <div key={h.id ?? i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: h.outcome === 'ok' ? '#9ece6a' : h.outcome === 'failed' ? '#f7768e' : '#e0af68' }} />
            <span style={{ flex: 1 }}>{h.what ?? 'Heal event'}</span>
            <span style={{ fontSize: 10, color: 'var(--muted-foreground, #888)' }}>{h.outcome}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const ghostBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--border, #2a2a2a)',
  borderRadius: 4,
  color: 'var(--foreground, #efefef)',
  cursor: 'pointer',
  fontSize: 11,
  fontFamily: 'inherit',
  padding: '2px 6px'
}

const inputStyle: React.CSSProperties = {
  padding: '4px 8px',
  background: 'transparent',
  border: '1px solid var(--border, #2a2a2a)',
  borderRadius: 4,
  color: 'inherit',
  fontSize: 12,
  fontFamily: 'inherit',
  flex: 1
}