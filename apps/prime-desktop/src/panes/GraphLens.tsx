/**
 * Graph Lens (full-pane) — reuses ui-graph layout/colors, serves from
 * ariadne_graph REST. Re-minimap and focused search.
 */

import { type GraphNode, layoutGraph, metaFor } from '@ariadne/ui-graph'
import { useEffect, useMemo, useState } from 'react'

import { get } from '../api'

export function GraphLens({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [loading, setLoading] = useState(false)

  async function search(q: string) {
    setLoading(true)

    try {
      const r = await get<{ ok: boolean; nodes: typeof nodes }>(`/api/ariadne/graph/related?query=${encodeURIComponent(q)}&depth=2&limit=40`)

      if (r.ok) {setNodes(r.nodes ?? [])}
    } catch { setNodes([]) }

    setLoading(false)
  }

  useEffect(() => { if (query) {void search(query)} }, [query])

  const laid = useMemo(() => layoutGraph(nodes, []), [nodes])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>🕸 Graph Lens</span>
        <input onChange={(e) => setQuery(e.target.value)} placeholder="Search nodes…" style={{ flex: 1, background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)', border: '1px solid var(--border, #2a2a2a)', borderRadius: 4, padding: '4px 8px', color: 'inherit', fontSize: 12, fontFamily: 'inherit' }} value={query} />
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}>✕</button>
      </div>
      <div style={{ flex: 1, overflow: 'auto', position: 'relative' }}>
        {loading && <p style={{ padding: 20, color: 'var(--muted-foreground, #888)' }}>Loading…</p>}
        {!loading && laid.nodes.length > 0 && (
          <svg aria-label="Context graph" height={laid.height} role="img" style={{ display: 'block' }} width={laid.width}>
            {laid.nodes.map((n) => {
              const m = metaFor(n.type)

              return (
                <g key={n.id} style={{ cursor: 'pointer' }} transform={`translate(${n.x},${n.y})`}>
                  <rect fill="color-mix(in srgb, currentColor 8%, transparent)" height={30} rx={4} stroke="var(--border, #2a2a2a)" strokeWidth={1} width={150} y={-15} />
                  <text fill={m.color} fontSize={12} x={10} y={4}>{m.glyph}</text>
                  <text fill="var(--foreground, #efefef)" fontSize={11} x={28} y={4}>{n.title?.slice(0, 16) || n.key?.slice(0, 16)}</text>
                </g>
              )
            })}
          </svg>
        )}
        {!loading && laid.nodes.length === 0 && query && <p style={{ padding: 20, color: 'var(--muted-foreground, #888)' }}>No nodes found.</p>}
      </div>
    </div>
  )
}