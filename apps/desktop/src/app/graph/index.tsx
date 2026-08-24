/**
 * GraphView — the Ariadne context graph as a first-class desktop page.
 *
 * One selection model, two projections (P4): the canvas and the node list
 * always agree. Deterministic layout (layout.ts). No hero copy; content
 * starts immediately (anti-slop #7). All transitions <300ms.
 */

import { useMemo, useState } from 'react'

import { getGraphRelated, getGraphStats, type GraphNode } from './api'
import { metaFor } from './colors'
import { layoutGraph } from './layout'

interface Props {
  initialQuery?: string
}

export function GraphView({ initialQuery = '' }: Props) {
  const [query, setQuery] = useState(initialQuery)

  const [data, setData] = useState<{
    nodes: GraphNode[]
    seeds: string[]
  } | null>(null)

  const [statsNodes, setStatsNodes] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)

  async function runSearch(q: string) {
    setLoading(true)
    setError('')

    try {
      const res = await getGraphRelated(q, { depth: 2, limit: 60 })

      if (!res.ok) {throw new Error('graph request failed')}
      setData({ nodes: res.nodes ?? [], seeds: res.seeds ?? [] })
      setSelectedId(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  async function loadStats() {
    try {
      const s = await getGraphStats()
      setStatsNodes(s.nodes)
    } catch {
      setStatsNodes(null)
    }
  }

  // Initial load: default subgraph for a broad seed so the page never opens empty
  // when data exists.
  const started = useMemo(() => {
    void runSearch(initialQuery || 'deploy')
    void loadStats()

    return true
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const laid = useMemo(
    () => layoutGraph(data?.nodes ?? [], []),
    [data]
  )

  const selected = data?.nodes.find((n) => n.id === selectedId) ?? null

  return (
    <div className="ariadne-graph" style={{ display: 'flex', height: '100%', minHeight: 0 }}>
      {/* Left rail: search + synchronized list (one selection model) */}
      <div
        style={{
          width: 280,
          borderRight: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0
        }}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void runSearch(query)
          }}
          style={{ padding: 10, borderBottom: '1px solid var(--border)' }}
        >
          <input
            aria-label="Search context graph"
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Seed keywords…"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              background: 'var(--background)',
              color: 'var(--foreground)',
              border: '1px solid var(--border)',
              borderRadius: 4,
              padding: '6px 8px',
              fontSize: 13
            }}
            value={query}
          />
        </form>
        <div aria-label="Graph nodes" role="listbox" style={{ overflowY: 'auto', flex: 1 }}>
          {(data?.nodes ?? []).map((n) => {
            const m = metaFor(n.type)
            const isSel = n.id === selectedId

            return (
              <button
                aria-selected={isSel}
                key={n.id}
                onClick={() => setSelectedId(n.id)}
                role="option"
                style={{
                  display: 'flex',
                  gap: 8,
                  alignItems: 'center',
                  width: '100%',
                  textAlign: 'left',
                  padding: '7px 12px',
                  background: isSel ? 'var(--accent)' : 'transparent',
                  color: isSel ? 'var(--background)' : 'var(--foreground)',
                  border: 'none',
                  borderTop: '1px solid var(--border)',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontFamily: 'inherit'
                }}
              >
                <span aria-hidden style={{ color: isSel ? 'inherit' : m.color }}>
                  {m.glyph}
                </span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {n.title || n.key}
                </span>
                <span
                  style={{
                    marginLeft: 'auto',
                    fontVariantNumeric: 'tabular-nums',
                    fontSize: 11,
                    opacity: 0.7
                  }}
                >
                  ×{n.touches}
                </span>
              </button>
            )
          })}
          {!loading && (data?.nodes.length ?? 0) === 0 && !error && (
            <p style={{ padding: 14, fontSize: 12, color: 'var(--muted-foreground)' }}>
              No nodes match this seed yet. Work in some sessions first, or try
              another keyword.
            </p>
          )}
          {error && (
            <p role="alert" style={{ padding: 14, fontSize: 12, color: '#f7768e' }}>
              {error}
            </p>
          )}
        </div>
        {statsNodes != null && (
          <div
            style={{
              padding: '8px 12px',
              borderTop: '1px solid var(--border)',
              fontSize: 11,
              color: 'var(--muted-foreground)',
              fontVariantNumeric: 'tabular-nums'
            }}
          >
            {statsNodes} nodes recorded
          </div>
        )}
      </div>

      {/* Canvas */}
      <div style={{ flex: 1, position: 'relative', overflow: 'auto', background: 'var(--background)' }}>
        {laid.nodes.length > 0 && (
          <svg
            aria-label="Context graph"
            height={laid.height}
            role="img"
            style={{ display: 'block' }}
            width={laid.width}
          >
            {/* lane separators */}
            {[...new Set(laid.nodes.map((n) => n.lane))].map((lane, i) => (
              <text
                fill="var(--muted-foreground)"
                fontSize={11}
                key={`lane-${lane}`}
                x={90 + i * 220 - 24}
                y={28}
              >
                {(data?.nodes ?? [])
                  .filter((n) => metaFor(n.type).label !== '')
                  .reduce((acc, n) => acc, '') || ''}
                {laneLabel(lane)}
              </text>
            ))}
            {laid.nodes.map((n) => {
              const m = metaFor(n.type)
              const isSel = n.id === selectedId

              return (
                <g
                  key={n.id}
                  onClick={() => setSelectedId(n.id)}
                  style={{ cursor: 'pointer' }}
                  transform={`translate(${n.x},${n.y})`}
                >
                  <rect
                    fill={isSel ? 'var(--accent)' : 'color-mix(in srgb, currentColor 8%, transparent)'}
                    height={34}
                    rx={4}
                    stroke={isSel ? 'var(--accent)' : 'var(--border)'}
                    strokeWidth={1}
                    width={150}
                    y={-17}
                  />
                  <text
                    fill={isSel ? 'var(--background)' : m.color}
                    fontSize={13}
                    x={10}
                    y={4}
                  >
                    {m.glyph}
                  </text>
                  <text
                    fill={isSel ? 'var(--background)' : 'var(--foreground)'}
                    fontSize={12}
                    x={30}
                    y={4}
                  >
                    {truncate(n.title || n.key, 16)}
                  </text>
                  <text
                    fill={isSel ? 'var(--background)' : 'var(--muted-foreground)'}
                    fontSize={10}
                    style={{ fontVariantNumeric: 'tabular-nums' }}
                    textAnchor="end"
                    x={140}
                    y={4}
                  >
                    ×{n.touches}
                  </text>
                </g>
              )
            })}
          </svg>
        )}
        {loading && (
          <p style={{ padding: 20, color: 'var(--muted-foreground)', fontSize: 13 }}>Loading…</p>
        )}
      </div>

      {/* Inspector */}
      <div
        style={{
          width: 300,
          borderLeft: '1px solid var(--border)',
          padding: 14,
          overflowY: 'auto',
          fontSize: 13
        }}
      >
        {selected ? (
            <InspectorContent node={selected} />
        ) : (
          <p style={{ color: 'var(--muted-foreground)' }}>
            Select a node to inspect it — touches, timeline, and metadata.
          </p>
        )}
      </div>
    </div>
  )
}

function InspectorContent({ node }: { node: GraphNode }) {
  const m = metaFor(node.type)

  return (
    <>
      <p style={{ margin: 0, color: m.color, fontSize: 11, letterSpacing: 0.5 }}>
        {m.label.toUpperCase()}
      </p>
      <h3 style={{ margin: '6px 0 2px', fontSize: 15 }}>{node.title || node.key}</h3>
      <code style={{ fontSize: 11, color: 'var(--muted-foreground)', wordBreak: 'break-all' }}>
        {node.id}
      </code>
      <dl style={{ marginTop: 12, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px' }}>
        <dt style={{ color: 'var(--muted-foreground)' }}>Touches</dt>
        <dd style={{ margin: 0, fontVariantNumeric: 'tabular-nums' }}>{node.touches}</dd>
        <dt style={{ color: 'var(--muted-foreground)' }}>First seen</dt>
        <dd style={{ margin: 0 }}>{fmtTime(node.first_seen)}</dd>
        <dt style={{ color: 'var(--muted-foreground)' }}>Last seen</dt>
        <dd style={{ margin: 0 }}>{fmtTime(node.last_seen)}</dd>
      </dl>
      {node.meta && node.meta !== '{}' && (
        <>
          <h4 style={{ marginBottom: 4 }}>Metadata</h4>
          <pre
            style={{
              background: 'color-mix(in srgb, var(--foreground) 5%, transparent)',
              padding: 8,
              borderRadius: 4,
              fontSize: 11,
              overflowX: 'auto'
            }}
          >
            {prettyMeta(node.meta)}
          </pre>
        </>
      )}
    </>
  )
}

function laneLabel(lane: number): string {
  const lanes: Array<[string, number]> = [
    ['session', 0],
    ['mem', 1],
    ['file', 2],
    ['cmd/url', 3],
    ['web/search', 4]
  ]

  const entry = lanes.find(([, rank]) => rank === lane)

  return entry ? entry[0] : `lane ${lane}`
}

function truncate(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s
}

function fmtTime(t: number): string {
  try {
    return new Date(t * 1000).toLocaleString()
  } catch {
    return String(t)
  }
}

function prettyMeta(meta: string): string {
  try {
    return JSON.stringify(JSON.parse(meta), null, 2)
  } catch {
    return meta
  }
}
