/**
 * G3 — Cost breakdown pane.
 *
 * Per-session/agent token usage + estimated cost from event-bus accounting.
 * Tabular numerics, collapsed groups, honest empty state.
 */

import { useEffect, useState } from 'react'

import { type BusEvent, onEvent } from '../event-bus'

interface ScopeStat {
  id: string
  label: string
  tokens: number
}

export function CostBreakdown({ onClose }: { onClose: () => void }) {
  const [bySession, setBySession] = useState<ScopeStat[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const unsub = onEvent('prime.*', (ev: BusEvent) => {
      const payload = (ev.payload ?? {}) as Record<string, unknown>
      const tokens = Number(payload.tokens ?? (payload.usage as Record<string, unknown> | undefined)?.total_tokens ?? 0)

      if (tokens > 0) {
        const sessionId = String(payload.session_id ?? payload.sessionId ?? 'unknown')
        setBySession((prev) => {
          const existing = prev.find((s) => s.id === sessionId)
          if (existing) {
            return prev.map((s) => (s.id === sessionId ? { ...s, tokens: s.tokens + tokens } : s))
          }
          return [...prev, { id: sessionId, label: sessionId.slice(0, 20), tokens }]
        })
        setTotal((t) => t + tokens)
      }
    })
    setLoading(false)
    return unsub
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>💸 Cost & tokens</span>
        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--muted-foreground, #888)', fontVariantNumeric: 'tabular-nums' }}>
          total: {total.toLocaleString()}
        </span>
        <button onClick={onClose} style={ghostBtn}>✕</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {!loading && bySession.length === 0 && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>
            No token data collected yet. Run a session or plan and costs will appear here.
          </div>
        )}
        {bySession.map((s) => (
          <div
            key={s.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '8px 12px',
              borderBottom: '1px solid var(--border, #2a2a2a)',
              fontSize: 12
            }}
          >
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {s.label}
            </span>
            <span style={{ color: 'var(--muted-foreground, #888)', fontVariantNumeric: 'tabular-nums' }}>
              {s.tokens.toLocaleString()} tok
            </span>
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
