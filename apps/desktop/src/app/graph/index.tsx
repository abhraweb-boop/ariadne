/**
 * GraphView — the Ariadne context graph as a first-class desktop page.
 *
 * Polish spec (docs/architecture-ariadne-phase4.md + plan doc):
 * ① GitLens-style sticky time-bucket pills in the node list
 * ② Figma hover-preview across views (hover locates, click commits)
 * ③ Keyboard parity: ↑/↓ traverse, Enter inspects, Esc clears
 * ④ Type-filter chips ("filtering beats physics")
 * ⑤ Contrast-audited tokens (colors.test.ts) + prune action w/ confirm
 *
 * One selection model, two synchronized projections. No simulation.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { getGraphRelated, getGraphStats, type GraphNode, pruneGraph } from './api'
import { metaFor } from './colors'
import { layoutGraph } from './layout'

interface Props {
  initialQuery?: string
}

const TYPE_ORDER = ['session', 'mem', 'file', 'cmd', 'url', 'web', 'search'] as const

function timeBucket(unixSeconds: number): string {
  const ageMs = Date.now() - unixSeconds * 1000
  const mins = ageMs / 60000

  if (mins < 60) {return 'Last hour'}
  const hours = mins / 60

  if (hours < 24) {return 'Today'}
  const days = hours / 24

  if (days < 7) {return 'This week'}

  return 'Older'
}

const BUCKET_ORDER = ['Last hour', 'Today', 'This week', 'Older']

export function GraphView({ initialQuery = '' }: Props) {
  const [query, setQuery] = useState(initialQuery)
  const [data, setData] = useState<{ nodes: GraphNode[]; seeds: string[] } | null>(null)
  const [statsNodes, setStatsNodes] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set())
  const [confirmingPrune, setConfirmingPrune] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  const runSearch = useCallback(async (q: string) => {
    setLoading(true)
    setError('')

    try {
      const res = await getGraphRelated(q, { depth: 2, limit: 80 })

      if (!res.ok) {throw new Error('graph request failed')}
      setData({ nodes: res.nodes ?? [], seeds: res.seeds ?? [] })
      setSelectedId(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void runSearch(initialQuery || 'deploy')
    void getGraphStats()
      .then((s) => setStatsNodes(s.nodes))
      .catch(() => setStatsNodes(null))
      // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load only
  }, [])

  // ④ type filter applied AFTER fetch — filtering beats re-querying
  const filteredNodes = useMemo(() => {
    const all = data?.nodes ?? []

    return typeFilter.size === 0 ? all : all.filter((n) => !typeFilter.has(n.type))
  }, [data, typeFilter])

  const laid = useMemo(() => layoutGraph(filteredNodes, []), [filteredNodes])

  // ① grouped for the list: time buckets within type-lane order
  const listGroups = useMemo(() => {
    const groups = new Map<string, GraphNode[]>()

    for (const n of filteredNodes) {
      const b = timeBucket(n.last_seen)
      const arr = groups.get(b)

      if (arr) {arr.push(n)}
      else {groups.set(b, [n])}
    }

    return BUCKET_ORDER.filter((b) => groups.has(b)).map((b) => ({
      bucket: b,
      nodes: groups.get(b)!
    }))
  }, [filteredNodes])

  const selected = data?.nodes.find((n) => n.id === selectedId) ?? null

  // ③ keyboard parity on the list container
  const orderedIds = useMemo(
    () => listGroups.flatMap((g) => g.nodes.map((n) => n.id)),
    [listGroups]
  )

  function moveSelection(delta: number) {
    if (orderedIds.length === 0) {return}
    const idx = selectedId ? orderedIds.indexOf(selectedId) : -1
    const next = orderedIds[Math.min(orderedIds.length - 1, Math.max(0, idx + delta))]

    if (next && next !== selectedId) {setSelectedId(next)}
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      moveSelection(1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      moveSelection(-1)
    } else if (e.key === 'Escape') {
      setSelectedId(null)
      setConfirmingPrune(false)
    }
  }

  async function doPrune() {
    try {
      await pruneGraph(30)
      setConfirmingPrune(false)
      await runSearch(query)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const presentTypes = useMemo(() => {
    const s = new Set((data?.nodes ?? []).map((n) => n.type))

    return TYPE_ORDER.filter((t) => s.has(t))
  }, [data])

  return (
    <div onKeyDown={onKeyDown} style={{ display: 'flex', height: '100%', minHeight: 0 }}>
      {/* Left rail */}
      <div
        ref={listRef}
        style={{
          width: 300,
          borderRight: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          outline: 'none'
        }}
        tabIndex={0}
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

        {/* ④ type-filter chips */}
        <div
          aria-label="Filter by node type"
          role="group"
          style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '8px 10px', borderBottom: '1px solid var(--border)' }}
        >
          {presentTypes.map((t) => {
            const m = metaFor(t)
            const off = typeFilter.has(t)

            return (
              <button
                aria-pressed={!off}
                key={t}
                onClick={() =>
                  setTypeFilter((prev) => {
                    const next = new Set(prev)

                    if (next.has(t)) {next.delete(t)}
                    else {next.add(t)}

                    return next
                  })
                }
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '2px 8px',
                  fontSize: 11,
                  borderRadius: 10,
                  border: `1px solid ${off ? 'var(--border)' : m.color}`,
                  background: 'transparent',
                  color: off ? 'var(--muted-foreground)' : m.color,
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  opacity: off ? 0.55 : 1,
                  transition: 'opacity 150ms ease'
                }}
                title={off ? `Show ${m.label}` : `Hide ${m.label}`}
              >
                <span aria-hidden>{m.glyph}</span>
                {m.label}
              </button>
            )
          })}
        </div>

        {/* ① time-bucketed node list with ② hover-preview and ③ keyboard nav */}
        <div aria-label="Graph nodes" role="listbox" style={{ overflowY: 'auto', flex: 1 }}>
          {listGroups.map((g) => (
            <div key={g.bucket}>
              <div
                aria-hidden
                style={{
                  position: 'sticky',
                  top: 0,
                  zIndex: 1,
                  padding: '3px 12px',
                  fontSize: 10,
                  letterSpacing: 0.8,
                  textTransform: 'uppercase',
                  color: 'var(--muted-foreground)',
                  background: 'var(--background)',
                  borderBottom: '1px solid var(--border)'
                }}
              >
                {g.bucket}
              </div>
              {g.nodes.map((n) => {
                const m = metaFor(n.type)
                const isSel = n.id === selectedId
                const isHover = n.id === hoveredId

                return (
                  <button
                    aria-selected={isSel}
                    key={n.id}
                    onBlur={() => setHoveredId((h) => (h === n.id ? null : h))}
                    onClick={() => setSelectedId(n.id)}
                    onFocus={() => setHoveredId(n.id)}
                    onMouseEnter={() => setHoveredId(n.id)}
                    onMouseLeave={() => setHoveredId((h) => (h === n.id ? null : h))}
                    role="option"
                    style={{
                      display: 'flex',
                      gap: 8,
                      alignItems: 'center',
                      width: '100%',
                      textAlign: 'left',
                      padding: '7px 12px',
                      background: isSel
                        ? 'var(--accent)'
                        : isHover
                          ? 'color-mix(in srgb, var(--foreground) 6%, transparent)'
                          : 'transparent',
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
            </div>
          ))}
          {!loading && (data?.nodes.length ?? 0) === 0 && !error && (
            <p style={{ padding: 14, fontSize: 12, color: 'var(--muted-foreground)' }}>
              No nodes match this seed yet. Work in some sessions first, or try
              another keyword{typeFilter.size > 0 && ' (or clear a type filter)'}.
            </p>
          )}
          {error && (
            <p role="alert" style={{ padding: 14, fontSize: 12, color: '#f7768e' }}>
              {error}
            </p>
          )}
        </div>

        {/* footer: count + prune (two-step confirm, P8) */}
        <div
          style={{
            padding: '8px 12px',
            borderTop: '1px solid var(--border)',
            fontSize: 11,
            color: 'var(--muted-foreground)',
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}
        >
          <span style={{ fontVariantNumeric: 'tabular-nums' }}>
            {statsNodes != null ? `${statsNodes} nodes` : ''}
          </span>
          <span style={{ marginLeft: 'auto' }}>
            {confirmingPrune ? (
              <>
                Prune stale (&gt;30d)?
                <button
                  onClick={() => void doPrune()}
                  style={{
                    marginLeft: 6,
                    background: 'transparent',
                    border: '1px solid #f7768e',
                    color: '#f7768e',
                    borderRadius: 4,
                    padding: '1px 8px',
                    fontSize: 11,
                    cursor: 'pointer',
                    fontFamily: 'inherit'
                  }}
                >
                  Confirm
                </button>
                <button
                  onClick={() => setConfirmingPrune(false)}
                  style={{
                    marginLeft: 4,
                    background: 'transparent',
                    border: '1px solid var(--border)',
                    color: 'var(--muted-foreground)',
                    borderRadius: 4,
                    padding: '1px 8px',
                    fontSize: 11,
                    cursor: 'pointer',
                    fontFamily: 'inherit'
                  }}
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                onClick={() => setConfirmingPrune(true)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--muted-foreground)',
                  fontSize: 11,
                  cursor: 'pointer',
                  textDecoration: 'underline dotted',
                  fontFamily: 'inherit'
                }}
              >
                prune stale
              </button>
            )}
          </span>
        </div>
      </div>

      {/* Canvas */}
      <div
        style={{ flex: 1, position: 'relative', overflow: 'auto', background: 'var(--background)' }}
      >
        {laid.nodes.length > 0 && (
          <svg
            aria-label="Context graph"
            height={laid.height}
            role="img"
            style={{ display: 'block' }}
            width={laid.width}
          >
            {[...new Set(laid.nodes.map((n) => n.lane))].map((lane, i) => (
              <text
                fill="var(--muted-foreground)"
                fontSize={11}
                key={`lane-${lane}`}
                x={90 + i * 220 - 24}
                y={28}
              >
                {laneLabel(lane)}
              </text>
            ))}
            {laid.nodes.map((n) => {
              const m = metaFor(n.type)
              const isSel = n.id === selectedId
              // ② hover-preview: ghost outline on the counterpart view
              const isHover = n.id === hoveredId && !isSel

              return (
                <g
                  key={n.id}
                  onClick={() => setSelectedId(n.id)}
                  onMouseEnter={() => setHoveredId(n.id)}
                  onMouseLeave={() => setHoveredId((h) => (h === n.id ? null : h))}
                  style={{ cursor: 'pointer' }}
                  transform={`translate(${n.x},${n.y})`}
                >
                  <rect
                    fill={
                      isSel
                        ? 'var(--accent)'
                        : 'color-mix(in srgb, currentColor 8%, transparent)'
                    }
                    height={34}
                    opacity={hoveredId && !isSel && !isHover ? 0.45 : 1}
                    rx={4}
                    stroke={
                      isSel ? 'var(--accent)' : isHover ? 'var(--foreground)' : 'var(--border)'
                    }
                    strokeDasharray={isHover ? '3 2' : undefined}
                    strokeWidth={isHover ? 1.5 : 1}
                    width={150}
                    y={-17}
                  />
                  <text fill={isSel ? 'var(--background)' : m.color} fontSize={13} x={10} y={4}>
                    {m.glyph}
                  </text>
                  <text
                    fill={isSel ? 'var(--background)' : 'var(--foreground)'}
                    fontSize={12}
                    opacity={hoveredId && !isSel && !isHover ? 0.6 : 1}
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
            <br />
            <br />
            <kbd>↑</kbd>/<kbd>↓</kbd> move · <kbd>Esc</kbd> clears
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
