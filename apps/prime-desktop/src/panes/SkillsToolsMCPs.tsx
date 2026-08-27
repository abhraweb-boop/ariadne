/**
 * H1 — Capabilities hub (formerly the combined Skills · Tools · MCPs pane).
 *
 * Re-purposed: no longer duplicates the dedicated panes. Shows live counts
 * and status, and deep-links into the dedicated panes (skills-hub / mcp /
 * tools) via onOpenPane.
 */

import { useEffect, useState } from 'react'

import { get } from '../api'

interface SkillItem { name: string; description?: string }
interface ToolItem { name: string; description?: string; toolset?: string }
interface McpItem { name: string; status?: string }

export function SkillsToolsMCPs({
  onClose,
  onOpenPane
}: {
  onClose: () => void
  onOpenPane?: (id: string) => void
}) {
  const [skills, setSkills] = useState<SkillItem[]>([])
  const [tools, setTools] = useState<ToolItem[]>([])
  const [mcps, setMcps] = useState<McpItem[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    void get<{ ok?: boolean; skills?: SkillItem[]; data?: SkillItem[] }>('/api/skills')
      .then((r) => setSkills(r.skills ?? r.data ?? []))
      .catch(() => setError('capability endpoints unavailable'))
    void get<{ ok?: boolean; tools?: ToolItem[]; data?: ToolItem[] }>('/api/tools/toolsets')
      .then((r) => setTools(r.toolsets ?? r.data ?? []))
      .catch(() => {})
    void get<{ ok?: boolean; servers?: McpItem[]; data?: McpItem[] }>('/api/mcp/servers')
      .then((r) => setMcps(r.servers ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const row = (id: string, icon: string, label: string, count: number, hint: string) => (
    <button
      aria-label={`Open ${label}`}
      key={id}
      onClick={() => onOpenPane?.(id)}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'color-mix(in srgb, var(--foreground, #efefef) 8%, transparent)' }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        width: '100%',
        padding: '10px 12px',
        background: 'transparent',
        border: 'none',
        borderBottom: '1px solid var(--border, #2a2a2a)',
        color: 'var(--foreground, #efefef)',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: 12,
        textAlign: 'left'
      }}
    >
      <span style={{ fontSize: 14 }}>{icon}</span>
      <span style={{ flex: 1 }}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        <span style={{ display: 'block', color: 'var(--muted-foreground, #888)', fontSize: 10 }}>{hint}</span>
      </span>
      <span style={{ fontSize: 16, color: 'var(--muted-foreground, #888)', fontWeight: 600 }}>{count}</span>
      <span style={{ color: 'var(--muted-foreground, #888)' }}>›</span>
    </button>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: 4, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>🧭 Capabilities</span>
        <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--muted-foreground, #888)' }}>
          tap to open
        </span>
        <button aria-label="Close" onClick={onClose} style={closeBtn}>✕</button>
      </div>

      {error && <div style={{ padding: '8px 12px', fontSize: 11, color: '#f7768e' }}>{error}</div>}

      {row('skills-hub', '📚', 'Skills Hub', skills.length, 'install, search, enable skills')}
      {row('mcp', '🔌', 'MCP Servers', mcps.length, 'add or remove model-context servers')}
      {row('tools', '🛠', 'Tools', tools.length, 'enable or disable toolsets')}

      <div style={{ padding: '10px 12px', fontSize: 11, color: 'var(--muted-foreground, #888)', lineHeight: 1.6 }}>
        Counts are live. Full management lives in the dedicated panes above.
      </div>
    </div>
  )
}

const closeBtn: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  borderRadius: 4,
  color: 'var(--muted-foreground, #888)',
  cursor: 'pointer',
  fontSize: 11,
  fontFamily: 'inherit',
  padding: '2px 6px'
}