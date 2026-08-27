/**
 * C3 — MCPs pane: list servers, add, remove.
 */

import { useCallback, useEffect, useState } from 'react'

import { del, get, post } from '../api'

interface MCPServer {
  name: string
  command?: string
  args?: string[]
  enabled?: boolean
  status?: string
}

export function McpPane({ onClose }: { onClose: () => void }) {
  const [servers, setServers] = useState<MCPServer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [command, setCommand] = useState('')
  const [formMsg, setFormMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok?: boolean; servers?: MCPServer[] }>('/api/mcp/servers')
      setServers(r.servers ?? [])
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const add = useCallback(async () => {
    if (!name.trim() || !command.trim()) {return}
    setFormMsg('Adding…')

    try {
      await post('/api/mcp/servers', { name: name.trim(), command: command.trim() })
      setFormMsg('Server added.')
      setShowForm(false)
      setName(''); setCommand('')
      void load()
    } catch (e) {
      setFormMsg(`Failed: ${String(e)}`)
    }
  }, [name, command, load])

  const remove = useCallback(async (serverName: string) => {
    const prev = servers
    setServers((cur) => cur.filter((s) => s.name !== serverName))

    try {
      await del(`/api/mcp/servers/${encodeURIComponent(serverName)}`)
    } catch {
      setServers(prev)
    }
  }, [servers])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>🔌 MCP Servers</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
        <button onClick={() => { setShowForm(!showForm); setFormMsg(null) }} style={{ ...ghostBtn, marginLeft: 'auto' }}>+ Add</button>
        <button aria-label="Close" onClick={onClose} style={ghostBtn}>✕</button>
      </div>

      {showForm && (
        <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <input onChange={(e) => setName(e.target.value)} placeholder="Server name" style={inputStyle} value={name} />
          <input onChange={(e) => setCommand(e.target.value)} placeholder="Command, e.g. npx @modelcontextprotocol/server-foo" style={inputStyle} value={command} />
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button disabled={!name.trim() || !command.trim()} onClick={() => void add()} style={{ ...ghostBtn, opacity: name.trim() && command.trim() ? 1 : 0.5 }}>Add</button>
            <button onClick={() => { setShowForm(false); setFormMsg(null) }} style={ghostBtn}>Cancel</button>
            {formMsg && <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)' }}>{formMsg}</span>}
          </div>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
            {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
          </div>
        )}
        {!loading && !error && servers.length === 0 && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>No MCP servers configured. Add one to give the agent external tools.</div>
        )}
        {servers.map((s) => (
          <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: s.enabled !== false ? '#9ece6a' : '#f7768e' }} />
            <span style={{ fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.name}</span>
            <code style={{ fontSize: 10, color: 'var(--muted-foreground, #888)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 180 }}>{s.command ?? ''}</code>
            <button onClick={() => void remove(s.name)} style={{ ...ghostBtn, color: '#f7768e' }}>Remove</button>
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
  fontFamily: 'inherit'
}