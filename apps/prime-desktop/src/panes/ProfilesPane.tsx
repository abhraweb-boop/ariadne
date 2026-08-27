/**
 * C4 — Profiles pane: list profiles, create, activate, open terminal.
 */

import { useCallback, useEffect, useState } from 'react'

import { get, post } from '../api'

interface Profile {
  name: string
  active?: boolean
}

export function ProfilesPane({ onClose }: { onClose: () => void }) {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [newName, setNewName] = useState('')
  const [formMsg, setFormMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok?: boolean; profiles?: Profile[] }>('/api/profiles')
      setProfiles(r.profiles ?? [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const create = useCallback(async () => {
    if (!newName.trim()) {return}
    setFormMsg('Creating…')

    try {
      await post('/api/profiles', { name: newName.trim() })
      setFormMsg('Profile created.')
      setNewName('')
      void load()
    } catch (e) {
      setFormMsg(`Failed: ${String(e)}`)
    }
  }, [newName, load])

  const activate = useCallback(async (name: string) => {
    const prev = profiles
    setProfiles((cur) => cur.map((p) => ({ ...p, active: p.name === name })))

    try {
      await post('/api/profiles/active', { name })
    } catch {
      setProfiles(prev)
    }
  }, [profiles])

  const openTerminal = useCallback(async (name: string) => {
    try {
      await post(`/api/profiles/${encodeURIComponent(name)}/open-terminal`, {})
    } catch { /* external app; ignore */ }
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>👤 Profiles</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
        <button aria-label="Close" onClick={onClose} style={{ ...ghostBtn, marginLeft: 'auto' }}>✕</button>
      </div>

      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', display: 'flex', gap: 6 }}>
        <input onChange={(e) => setNewName(e.target.value)} placeholder="New profile name…" style={inputStyle} value={newName} />
        <button disabled={!newName.trim()} onClick={() => void create()} style={{ ...ghostBtn, opacity: newName.trim() ? 1 : 0.5 }}>Create</button>
        {formMsg && <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)' }}>{formMsg}</span>}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
            {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
          </div>
        )}
        {!loading && !error && profiles.length === 0 && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>No profiles found.</div>
        )}
        {profiles.map((p) => (
          <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: p.active ? '#9ece6a' : 'var(--border, #2a2a2a)' }} />
            <span style={{ fontWeight: 600, flex: 1 }}>{p.name}</span>
            {!p.active && <button onClick={() => void activate(p.name)} style={ghostBtn}>Activate</button>}
            <button onClick={() => void openTerminal(p.name)} style={ghostBtn}>Terminal</button>
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