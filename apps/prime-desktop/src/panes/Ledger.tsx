/**
 * Ledger pane — /refine memory ledger viewer with version history + rollback.
 */

import { useEffect, useState } from 'react'

import { get, post } from '../api'

interface LedgerEntry {
  id: string
  kind: string
  title?: string
  body: string
  status: string
  touches?: number
  updated_at?: number
}

export function Ledger({ onClose }: { onClose: () => void }) {
  const [entries, setEntries] = useState<LedgerEntry[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [history, setHistory] = useState<Array<Record<string, unknown>>>([])

  useEffect(() => {
    void refresh()
  }, [])

  async function refresh() {
    try {
      const r = await get<{ ok: boolean; entries: LedgerEntry[] }>('/api/ariadne/ledger/entries')

      if (r.ok) {setEntries(r.entries ?? [])}
    } catch {
      setEntries([])
    }
  }

  async function selectEntry(id: string) {
    setSelectedId(id)

    try {
      const r = await get<{ ok: boolean; history: Array<Record<string, unknown>> }>(`/api/ariadne/ledger/${id}`)

      if (r.ok) {setHistory(r.history ?? [])}
    } catch {
      setHistory([])
    }
  }

  async function rollback() {
    if (!selectedId) {return}
    await post(`/api/ariadne/ledger/${selectedId}/rollback`, {})
    await selectEntry(selectedId)
    await refresh()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>📓 Refine Ledger</span>
        <button onClick={() => void refresh()} style={{ marginLeft: 8, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 12, opacity: 0.7, fontFamily: 'inherit' }}>↻</button>
        <span style={{ marginLeft: 'auto', fontSize: 11, opacity: 0.5, fontVariantNumeric: 'tabular-nums' }}>{entries.length} entries</span>
        <button aria-label="Close" onClick={onClose} style={{ marginLeft: 8, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}></button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        {entries.length === 0 && <p style={{ padding: 16, color: 'var(--muted-foreground, #888)', fontSize: 12 }}>Ledger empty — memory writes will appear here.</p>}
        {entries.map((e) => (
          <button
            key={e.id}
            onClick={() => void selectEntry(e.id)}
            style={{
              display: 'block',
              width: '100%',
              textAlign: 'left',
              marginBottom: 6,
              padding: 10,
              borderRadius: 8,
              border: selectedId === e.id ? '1.5px solid var(--accent, #5e6ad2)' : '1px solid var(--border, #2a2a2a)',
              background: 'transparent',
              color: 'inherit',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: 12
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontWeight: 600 }}>{e.title || e.body.slice(0, 50)}</span>
              <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--muted-foreground, #888)' }}>{e.kind}</span>
            </div>
            <div style={{ fontSize: 11, opacity: 0.6, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {e.body.slice(0, 100)}
            </div>
          </button>
        ))}
      </div>
      {selectedId && (
        <div style={{ borderTop: '1px solid var(--border, #2a2a2a)', padding: 10, fontSize: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
            <strong>Version history</strong>
            <button onClick={() => void rollback()} style={{ marginLeft: 'auto', background: 'none', border: '1px solid var(--accent, #e0af68)', borderRadius: 4, padding: '2px 10px', color: 'var(--accent, #e0af68)', cursor: 'pointer', fontSize: 11, fontFamily: 'inherit' }}>
              Rollback
            </button>
          </div>
          <div style={{ maxHeight: 120, overflowY: 'auto' }}>
            {history.map((h, i) => (
              <div key={i} style={{ fontSize: 11, padding: '2px 0', opacity: 0.7 }}>
                v{i + 1} · {String(h.body ?? '').slice(0, 60)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}