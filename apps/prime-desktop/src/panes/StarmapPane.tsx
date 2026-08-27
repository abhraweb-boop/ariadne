/**
 * C5 — Starmap pane: graph stats + recent runs (project context map).
 */

import { useCallback, useEffect, useState } from 'react'

import { get } from '../api'

interface Run {
  plan_id?: string
  goal?: string
  state?: string
  started?: number
}

export function StarmapPane({ onClose }: { onClose: () => void }) {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const s = await get<{ ok?: boolean; stats?: Record<string, unknown> }>('/api/ariadne/graph/stats')
      setStats(s.stats ?? s)
      const r = await get<{ ok?: boolean; runs?: Run[] }>('/api/ariadne/graph/runs')
      setRuns(r.runs ?? [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const statRows = stats ? Object.entries(stats).slice(0, 8) : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>🗺 Starmap</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
        <button aria-label="Close" onClick={onClose} style={{ ...ghostBtn, marginLeft: 'auto' }}>✕</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
            {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
          </div>
        )}

        {!loading && !error && (
          <>
            <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
              <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>Graph stats</div>
              {statRows.length === 0 && <div style={{ fontSize: 12 }}>No stats yet — run a plan to populate the graph.</div>}
              {statRows.map(([k, v]) => (
                <div key={k} style={{ display: 'flex', fontSize: 12, padding: '2px 0' }}>
                  <span style={{ color: 'var(--muted-foreground, #888)', width: 120 }}>{k}</span>
                  <span>{String(v)}</span>
                </div>
              ))}
            </div>

            <div style={{ padding: '10px 12px' }}>
              <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>Recent runs</div>
              {runs.length === 0 && <div style={{ fontSize: 12 }}>No runs recorded.</div>}
              {runs.map((run) => (
                <div key={run.plan_id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, padding: '4px 0' }}>
                  <span style={{ width: 8, height: 8, borderRadius: 4, background: run.state === 'done' ? '#9ece6a' : run.state === 'failed' ? '#f7768e' : '#e0af68' }} />
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{run.goal ?? run.plan_id}</span>
                  <span style={{ fontSize: 10, color: 'var(--muted-foreground, #888)' }}>{run.state}</span>
                </div>
              ))}
            </div>
          </>
        )}
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