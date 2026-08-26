/**
 * F1 — StatusDot (port of Hermes desktop status-dot).
 * Live gateway/worker state: green connected, amber busy, red offline.
 */

export type StatusState = 'connected' | 'busy' | 'offline' | 'unknown'

const COLORS: Record<StatusState, string> = {
  connected: '#9ece6a',
  busy: '#e0af68',
  offline: '#f7768e',
  unknown: '#888'
}

export function StatusDot({ state, label }: { state: StatusState; label?: string }) {
  return (
    <span
      title={label ?? state}
      aria-label={label ?? state}
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: 4,
        background: COLORS[state],
        flexShrink: 0
      }}
    />
  )
}
