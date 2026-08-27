/**
 * C4 — Webhooks pane: list, create, delete.
 */

import { useCallback, useEffect, useState } from 'react'

import { del, get, post } from '../api'

interface Webhook {
  url: string
  events?: string[]
  created?: number
}

export function WebhooksPane({ onClose }: { onClose: () => void }) {
  const [webhooks, setWebhooks] = useState<Webhook[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [url, setUrl] = useState('')
  const [formMsg, setFormMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok?: boolean; webhooks?: Webhook[] }>('/api/ariadne/webhooks')
      setWebhooks(r.webhooks ?? [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const add = useCallback(async () => {
    if (!url.trim()) {return}
    setFormMsg('Adding…')

    try {
      await post('/api/ariadne/webhooks', { url: url.trim(), events: [] })
      setFormMsg('Webhook added.')
      setUrl('')
      void load()
    } catch (e) {
      setFormMsg(`Failed: ${String(e)}`)
    }
  }, [url, load])

  const remove = useCallback(async (index: number) => {
    const prev = webhooks
    setWebhooks((cur) => cur.filter((_, i) => i !== index))

    try {
      await del(`/api/ariadne/webhooks/${index}`)
    } catch {
      setWebhooks(prev)
    }
  }, [webhooks])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>🔔 Webhooks</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
        <button aria-label="Close" onClick={onClose} style={{ ...ghostBtn, marginLeft: 'auto' }}>✕</button>
      </div>

      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', display: 'flex', gap: 6 }}>
        <input onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/hook" style={inputStyle} value={url} />
        <button disabled={!url.trim()} onClick={() => void add()} style={{ ...ghostBtn, opacity: url.trim() ? 1 : 0.5 }}>Add</button>
        {formMsg && <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)' }}>{formMsg}</span>}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
            {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
          </div>
        )}
        {!loading && !error && webhooks.length === 0 && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>No webhooks. Add one to receive agent events.</div>
        )}
        {webhooks.map((w, i) => (
          <div key={w.url} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', fontSize: 12 }}>
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{w.url}</span>
            <button onClick={() => void remove(i)} style={{ ...ghostBtn, color: '#f7768e' }}>Delete</button>
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