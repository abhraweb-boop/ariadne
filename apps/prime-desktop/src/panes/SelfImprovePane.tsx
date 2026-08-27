/**
 * S1 — Self-improvement pane: refine loop + heals journal.
 *
 * Refine: drives the live Prime worker over the ariadne prime RPC bridge
 * (persistent kernel, rlm() subagents). Heals: shows recent self-healing
 * events from the watchdog.
 */

import { useCallback, useEffect, useState } from 'react'

import { get, post } from '../api'
import { usePrimeState } from '../hooks/use-prime-state'

interface HealEvent {
  id?: string
  what?: string
  when?: number
  outcome?: string
}

interface PrimeState {
  model?: string
  session?: string
  kernel?: string
}

export function SelfImprovePane({ onClose }: { onClose: () => void }) {
  const [heals, setHeals] = useState<HealEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refineGoal, setRefineGoal] = useState('')
  const [refineMsg, setRefineMsg] = useState<string | null>(null)

  const loadHeals = useCallback(async () => {
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

  const { running, state: primeState, refresh } = usePrimeState(30000)

  useEffect(() => {
    void loadHeals()
    void refresh()
  }, [loadHeals, refresh])

  const refine = useCallback(async () => {
    if (!refineGoal.trim()) {return}
    setRefineMsg('Running refine against the live Prime worker…')

    try {
      const r = await post<{ ok: boolean; response?: string }>('/api/ariadne/prime/prompt', { goal: refineGoal })

      if (r.ok) {
        const text = r.response ?? ''
        setRefineMsg(`Prime worker responded: ${text.slice(0, 400)}${text.length > 400 ? '…' : ''}`)
        setRefineGoal('')
      } else {
        setRefineMsg('Refine failed.')
      }
    } catch (e) {
      setRefineMsg(`Failed: ${String(e)}`)
    } finally {
      void refresh()
    }
  }, [refineGoal, refresh])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>🧠 Self-Improve</span>
        <span style={{ width: 8, height: 8, borderRadius: 4, background: running ? '#9ece6a' : 'var(--muted-foreground, #888)' }} />
        <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)' }}>
          {running ? `Prime worker live${primeState?.model ? ` · ${primeState.model}` : ''}` : 'Prime worker stopped'}
        </span>
        <button aria-label="Close" onClick={onClose} style={{ ...ghostBtn, marginLeft: 'auto' }}>✕</button>
      </div>

      {/* Refine */}
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>Refine (drive the live Prime worker)</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            onChange={(e) => setRefineGoal(e.target.value)}
            placeholder="What to improve? (sent to Prime RPC)"
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
        <button onClick={() => void loadHeals()} style={ghostBtn}>↻</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
            {error} <button onClick={() => void loadHeals()} style={ghostBtn}>Retry</button>
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