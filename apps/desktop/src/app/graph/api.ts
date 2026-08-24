import type { ProfileScope } from '@/api/client'
import { profileScoped } from '@/api/client'

export interface GraphNode {
  id: string
  type: string
  key: string
  title: string
  meta: string
  first_seen: number
  last_seen: number
  touches: number
}

export interface GraphEdge {
  src: string
  rel: string
  dst: string
  weight: number
  last_seen: number
}

export interface GraphSubgraph {
  ok: boolean
  seeds?: string[]
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphStats {
  ok: boolean
  nodes: number
  edges: number
  by_type: Record<string, number>
  db_path: string
}

export interface GraphTimelineEvent {
  src: string
  rel: string
  dst: string
  weight: number
  last_seen: number
}

function base(profile?: ProfileScope) {
  return { ...profileScoped() }
}

export async function getGraphRelated(
  query: string,
  opts?: { depth?: number; limit?: number; node?: string },
  profile?: ProfileScope,
): Promise<GraphSubgraph> {
  const params = new URLSearchParams({ query, ...(opts?.node ? { node: opts.node } : {}) })

  if (opts?.depth != null) {params.set('depth', String(opts.depth))}

  if (opts?.limit != null) {params.set('limit', String(opts.limit))}

  return window.hermesDesktop.api<GraphSubgraph>({
    ...base(profile),
    path: `/api/ariadne/graph/related?${params.toString()}`
  })
}

export async function getGraphStats(profile?: ProfileScope): Promise<GraphStats> {
  return window.hermesDesktop.api<GraphStats>({
    ...base(profile),
    path: '/api/ariadne/graph/stats'
  })
}

export async function getGraphTimeline(
  node: string,
  limit = 20,
  profile?: ProfileScope,
): Promise<{ ok: boolean; node: string; events: GraphTimelineEvent[] }> {
  return window.hermesDesktop.api({
    ...base(profile),
    path: `/api/ariadne/graph/timeline?node=${encodeURIComponent(node)}&limit=${limit}`
  })
}

export async function pruneGraph(
  olderThanDays: number,
  profile?: ProfileScope,
): Promise<{ ok: boolean; nodes: number; edges: number }> {
  return window.hermesDesktop.api({
    ...base(profile),
    path: '/api/ariadne/graph/prune',
    method: 'POST',
    body: { older_than_days: olderThanDays }
  })
}
