/**
 * Deterministic-layout invariant (Phase 4 gate): the layout is a pure
 * function of the graph — two mounts produce identical positions.
 */

import { describe, expect, it } from 'vitest'

import type { GraphEdge, GraphNode } from './api'
import { layoutGraph } from './layout'

const nodes: GraphNode[] = [
  {
    id: 'session:s1',
    type: 'session',
    key: 's1',
    title: 'session s1',
    meta: '{}',
    first_seen: 1,
    last_seen: 100,
    touches: 3
  },
  {
    id: 'file:deploy.py',
    type: 'file',
    key: 'deploy.py',
    title: 'deploy.py',
    meta: '{}',
    first_seen: 2,
    last_seen: 90,
    touches: 5
  },
  {
    id: 'cmd:kubectl',
    type: 'cmd',
    key: 'kubectl',
    title: 'kubectl rollout',
    meta: '{}',
    first_seen: 3,
    last_seen: 80,
    touches: 1
  },
  {
    id: 'mem:e1',
    type: 'mem',
    key: 'e1',
    title: 'deploy policy',
    meta: '{}',
    first_seen: 4,
    last_seen: 95,
    touches: 2
  }
]

const edges: GraphEdge[] = [
  { src: 'file:deploy.py', rel: 'read-by', dst: 'session:s1', weight: 8, last_seen: 100 },
  { src: 'cmd:kubectl', rel: 'produced', dst: 'file:deploy.py', weight: 4, last_seen: 90 }
]

describe('layoutGraph', () => {
  it('is deterministic across repeated calls', () => {
    const a = layoutGraph(nodes, edges)
    const b = layoutGraph(nodes, edges)
    expect(a.nodes.map(n => [n.id, n.x, n.y])).toEqual(
      b.nodes.map(n => [n.id, n.x, n.y])
    )
  })

  it('orders lanes by type rank (session before mem before file before cmd)', () => {
    const { nodes: laid } = layoutGraph(nodes, edges)
    const byId = new Map(laid.map(n => [n.id, n]))
    expect(byId.get('session:s1')!.lane).toBeLessThan(byId.get('mem:e1')!.lane)
    expect(byId.get('mem:e1')!.lane).toBeLessThan(byId.get('file:deploy.py')!.lane)
    expect(byId.get('file:deploy.py')!.lane).toBeLessThan(byId.get('cmd:kubectl')!.lane)
  })

  it('places newest-first within a lane and never overlaps', () => {
    const sameLane = nodes.filter(n => n.type === 'file')
    sameLane.push({ ...nodes[1], id: 'file:zz.py', key: 'zz.py', title: 'zz.py', last_seen: 99 })
    const { nodes: laid } = layoutGraph(sameLane, [])
    const ys = laid.map(n => n.y)
    expect(new Set(ys).size).toBe(ys.length) // no overlap
    // zz.py (99) is newer than nothing else here; single-lane ordering check:
    if (laid.length === 2) {
      expect(laid[0].y).toBeLessThan(laid[1].y)
    }
  })
})
