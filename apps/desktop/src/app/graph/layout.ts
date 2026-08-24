/**
 * Deterministic layered layout for the context graph (P2/P3/P5).
 *
 * No simulation. Nodes are assigned to type-rank lanes (session -> mem ->
 * file -> cmd/web/url/search), ordered by last_seen within each lane, and
 * spread on a fixed grid. Two mounts over the same data produce identical
 * positions — the layout is a pure function of the graph.
 */

import type { GraphEdge, GraphNode } from './api'

export interface LaidOutNode extends GraphNode {
  x: number
  y: number
  lane: number
}

const TYPE_RANK: Record<string, number> = {
  session: 0,
  mem: 1,
  file: 2,
  cmd: 3,
  url: 3,
  web: 4,
  search: 4
}

const LANE_GAP_X = 220
const NODE_GAP_Y = 74
const ORIGIN = { x: 90, y: 60 }

function rankOf(type: string): number {
  return TYPE_RANK[type] ?? 5
}

export function layoutGraph(
  nodes: GraphNode[],
  _edges: GraphEdge[]
): { nodes: LaidOutNode[]; width: number; height: number } {
  const sorted = [...nodes].sort((a, b) => {
    const r = rankOf(a.type) - rankOf(b.type)

    if (r !== 0) {return r}

    return b.last_seen - a.last_seen // newest first within lane
  })

  const perLane = new Map<number, GraphNode[]>()

  for (const n of sorted) {
    const lane = rankOf(n.type)
    const bucket = perLane.get(lane)

    if (bucket) {bucket.push(n)}
    else {perLane.set(lane, [n])}
  }

  const lanes = [...perLane.keys()].sort((a, b) => a - b)
  let maxRows = 0
  const laid: LaidOutNode[] = []

  for (const lane of lanes) {
    maxRows = Math.max(maxRows, perLane.get(lane)!.length)
  }

  for (const lane of lanes) {
    const bucket = perLane.get(lane)!
    const laneX = ORIGIN.x + lanes.indexOf(lane) * LANE_GAP_X
    const columnHeight = bucket.length * NODE_GAP_Y

    const yOffset =
      ORIGIN.y + Math.max(0, (maxRows * NODE_GAP_Y - columnHeight) / 2)

    bucket.forEach((n, i) => {
      laid.push({ ...n, x: laneX, y: yOffset + i * NODE_GAP_Y + 20, lane })
    })
  }

  const width = ORIGIN.x * 2 + Math.max(1, lanes.length) * LANE_GAP_X
  const height = ORIGIN.y * 2 + maxRows * NODE_GAP_Y

  return { nodes: laid, width, height }
}
