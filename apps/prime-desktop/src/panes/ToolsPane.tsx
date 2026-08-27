/**
 * C3 — Tools pane: toolset catalog with enable/disable.
 */

import { useCallback, useEffect, useState } from 'react'

import { get, put } from '../api'

interface Toolset {
  name: string
  enabled?: boolean
  description?: string
  tools?: string[]
}

export function ToolsPane({ onClose }: { onClose: () => void }) {
  const [toolsets, setToolsets] = useState<Toolset[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok?: boolean; toolsets?: Toolset[] }>('/api/tools/toolsets')
      setToolsets(r.toolsets ?? [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const toggle = useCallback(async (name: string, enabled: boolean) => {
    const prev = toolsets
    setToolsets((cur) => cur.map((t) => (t.name === name ? { ...t, enabled } : t)))

    try {
      await put(`/api/tools/toolsets/${encodeURIComponent(name)}`, { enabled })
    } catch {
      setToolsets(prev)
    }
  }, [toolsets])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>🛠 Tools</span>
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
        {!loading && !error && toolsets.length === 0 && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>No toolsets found.</div>
        )}
        {toolsets.map((t) => (
          <div key={t.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: t.enabled !== false ? '#9ece6a' : '#f7768e' }} />
            <span style={{ fontWeight: 600, flex: 1 }}>{t.name}</span>
            <button onClick={() => void toggle(t.name, t.enabled === false)} style={ghostBtn}>{t.enabled === false ? 'Enable' : 'Disable'}</button>
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