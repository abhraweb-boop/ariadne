/**
 * F1 — Page loader (shown briefly on app boot while gateway connects).
 * Hermes desktop pattern: branded loading state, no spinner, honest.
 */

import { TITLEBAR_HEIGHT } from './titlebar-css'

export function PageLoader() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: `calc(100vh - ${TITLEBAR_HEIGHT}px)`,
        gap: 16,
        background: 'var(--background, #101012)',
        color: 'var(--muted-foreground, #888)',
        fontFamily: 'inherit'
      }}
    >
      <span
        style={{
          width: 24,
          height: 24,
          borderRadius: 6,
          background: 'linear-gradient(135deg, #5e6ad2, #9ece6a)',
          display: 'inline-block'
        }}
      />
      <div style={{ fontSize: 13 }}>Prime Hermes</div>
      <div style={{ fontSize: 11, opacity: 0.6 }}>Connecting to gateway…</div>
    </div>
  )
}