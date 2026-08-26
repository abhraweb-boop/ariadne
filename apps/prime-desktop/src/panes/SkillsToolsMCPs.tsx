/**
 * Skills · Tools · MCPs pane — thin renderers over existing Hermes routers.
 * List + status + detail; point-and-click only.
 */

import { useEffect, useState } from 'react'

import { get } from '../api'

interface SkillItem { id: string; name: string; description?: string }
interface ToolItem { name: string; description?: string; toolset?: string }
interface McpItem { name: string; status?: string }

export function SkillsToolsMCPs({ onClose }: { onClose: () => void }) {
  const [skills, setSkills] = useState<SkillItem[]>([])
  const [tools, setTools] = useState<ToolItem[]>([])
  const [mcps, setMcps] = useState<McpItem[]>([])
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'skills' | 'tools' | 'mcps'>('skills')

  useEffect(() => {
    void get<{ ok?: boolean; skills?: SkillItem[]; data?: SkillItem[] }>('/api/skills')
      .then((r) => setSkills(r.skills ?? r.data ?? []))
      .catch(() => setError('skills endpoint unavailable'))
    void get<{ ok?: boolean; tools?: ToolItem[]; data?: ToolItem[] }>('/api/tools')
      .then((r) => setTools(r.tools ?? r.data ?? []))
      .catch(() => {})
    void get<{ ok?: boolean; servers?: McpItem[]; data?: McpItem[] }>('/api/mcp/servers')
      .then((r) => setMcps(r.servers ?? r.data ?? []))
      .catch(() => {})
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: 4, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>📚 Capabilities</span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 4 }}>
          {(['skills', 'tools', 'mcps'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                background: tab === t ? 'var(--accent, #5e6ad2)' : 'transparent',
                border: '1px solid var(--border, #2a2a2a)',
                borderRadius: 999,
                padding: '2px 12px',
                color: tab === t ? '#fff' : 'inherit',
                cursor: 'pointer',
                fontSize: 11,
                textTransform: 'uppercase',
                letterSpacing: 0.5,
                fontFamily: 'inherit'
              }}
            >
              {t}
            </button>
          ))}
        </span>
        <button onClick={onClose} style={{ marginLeft: 4, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}>✕</button>
      </div>

      {error && <p style={{ padding: 10, color: '#f7768e', fontSize: 12 }}>{error}</p>}

      <div style={{ flex: 1, overflowY: 'auto', padding: 8 }}>
        {tab === 'skills' && (skills.length === 0
          ? <Empty label="No skills found (endpoint may need the gateway)." />
          : skills.map((s) => (
              <div key={s.id ?? s.name} style={{ border: '1px solid var(--border, #2a2a2a)', borderRadius: 8, padding: 10, marginBottom: 6 }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{s.name}</div>
                {s.description && <div style={{ fontSize: 11, opacity: 0.6, marginTop: 2 }}>{s.description.slice(0, 120)}</div>}
              </div>
            )))}
        {tab === 'tools' && (tools.length === 0
          ? <Empty label="No tools listed." />
          : tools.map((t) => (
              <div key={t.name} style={{ border: '1px solid var(--border, #2a2a2a)', borderRadius: 8, padding: 10, marginBottom: 6 }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{t.name}</div>
                {t.toolset && <div style={{ fontSize: 10, opacity: 0.5 }}>toolset: {t.toolset}</div>}
              </div>
            )))}
        {tab === 'mcps' && (mcps.length === 0
          ? <Empty label="No MCP servers." />
          : mcps.map((m) => (
              <div key={m.name} style={{ border: '1px solid var(--border, #2a2a2a)', borderRadius: 8, padding: 10, marginBottom: 6, display: 'flex', alignItems: 'center' }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{m.name}</span>
                <span style={{ marginLeft: 'auto', fontSize: 11, color: m.status === 'connected' ? '#9ece6a' : '#888' }}>{m.status ?? 'unknown'}</span>
              </div>
            )))}
      </div>
    </div>
  )
}

function Empty({ label }: { label: string }) {
  return <p style={{ padding: 16, color: 'var(--muted-foreground, #888)', fontSize: 12 }}>{label}</p>
}