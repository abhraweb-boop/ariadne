/**
 * C1 — SkillsHub pane: list installed skills, search, install from hub.
 */

import { useCallback, useEffect, useState } from 'react'

import { get, post } from '../api'

interface Skill {
  name: string
  description?: string
  enabled?: boolean
  provenance?: string
  usage?: number
}

export function SkillsHub({ onClose }: { onClose: () => void }) {
  const [skills, setSkills] = useState<Skill[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [installName, setInstallName] = useState('')
  const [installMsg, setInstallMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok?: boolean; skills?: Skill[] } | Skill[]>('/api/skills')
      const list = Array.isArray(r) ? r : (r as any).skills ?? []
      setSkills(list)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const install = useCallback(async () => {
    const name = installName.trim()

    if (!name) {return}
    setInstallMsg('Installing…')

    try {
      await post('/api/skills/hub/install', { name, source: 'hub' })
      setInstallMsg(`Installed "${name}".`)
      setInstallName('')
      void load()
    } catch (e) {
      setInstallMsg(`Failed: ${String(e)}`)
    }
  }, [installName, load])

  const filtered = query
    ? skills.filter((s) => (s.name + ' ' + (s.description ?? '')).toLowerCase().includes(query.toLowerCase()))
    : skills

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>📚 Skills Hub</span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--muted-foreground, #888)' }}>{skills.length} installed</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
        <button aria-label="Close" onClick={onClose} style={ghostBtn}>✕</button>
      </div>

      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', display: 'flex', gap: 6 }}>
        <input
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search installed skills…"
          style={{ flex: 1, padding: '4px 8px', background: 'transparent', border: '1px solid var(--border, #2a2a2a)', borderRadius: 4, color: 'inherit', fontSize: 12, fontFamily: 'inherit' }}
          value={query}
        />
        <input
          onChange={(e) => setInstallName(e.target.value)}
          placeholder="Install from hub…"
          style={{ flex: 1, padding: '4px 8px', background: 'transparent', border: '1px solid var(--border, #2a2a2a)', borderRadius: 4, color: 'inherit', fontSize: 12, fontFamily: 'inherit' }}
          value={installName}
        />
        <button disabled={!installName.trim()} onClick={() => void install()} style={{ ...ghostBtn, opacity: installName.trim() ? 1 : 0.5 }}>Install</button>
      </div>

      {installMsg && <div style={{ padding: '4px 12px', fontSize: 11, color: 'var(--muted-foreground, #888)' }}>{installMsg}</div>}

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
            {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
          </div>
        )}
        {!loading && !error && filtered.length === 0 && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>
            {query ? 'No skills match your search.' : 'No skills installed.'}
          </div>
        )}
        {filtered.map((s) => (
          <div
            key={s.name}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', fontSize: 12 }}
          >
            <span style={{ width: 8, height: 8, borderRadius: 4, background: s.enabled !== false ? '#9ece6a' : '#f7768e' }} />
            <span style={{ fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</span>
            <span style={{ color: 'var(--muted-foreground, #888)', fontSize: 10 }}>{s.provenance}</span>
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