/**
 * A1 — Custom titlebar (port of Hermes desktop's titlebar behavior).
 *
 * Frameless window: this bar is the drag region; buttons are no-drag.
 * Brand mark left, window controls (min/max/close) right, matching Hermes
 * desktop's 34px height and control affordances.
 *
 * Window bridge types live in api.ts (single global declaration).
 */

import { useCallback } from 'react'

import { DRAG_CLASS, NO_DRAG_CLASS, TITLEBAR_HEIGHT } from './titlebar-css'

export function Titlebar() {
  const minimize = useCallback(() => void window.primeHermes?.windowMinimize?.(), [])
  const maximize = useCallback(() => void window.primeHermes?.windowMaximize?.(), [])
  const close = useCallback(() => void window.primeHermes?.windowClose?.(), [])

  return (
    <header
      className={DRAG_CLASS}
      style={{
        height: TITLEBAR_HEIGHT,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '0 8px 0 14px',
        borderBottom: '1px solid var(--border, #2a2a2a)',
        background: 'var(--background, #101012)',
        userSelect: 'none',
        flexShrink: 0
      }}
    >
      {/* Brand mark (A1) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, minWidth: 0 }}>
        <span
          aria-hidden
          style={{
            width: 16,
            height: 16,
            borderRadius: 4,
            background: 'linear-gradient(135deg, #5e6ad2, #9ece6a)',
            display: 'inline-block',
            flexShrink: 0
          }}
        />
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: 'var(--foreground, #efefef)',
            letterSpacing: 0.3,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis'
          }}
        >
          Prime Hermes
        </span>
      </div>

      {/* Window controls (A1) — no-drag */}
      <div
        className={NO_DRAG_CLASS}
        style={{
          marginLeft: 'auto',
          display: 'flex',
          alignItems: 'center',
          gap: 2
        }}
      >
        {[
          { label: 'Minimize', glyph: '—', onClick: minimize },
          { label: 'Maximize', glyph: '▢', onClick: maximize },
          { label: 'Close', glyph: '✕', onClick: close, danger: true }
        ].map((btn) => (
          <button
            aria-label={btn.label}
            key={btn.label}
            onClick={btn.onClick}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = btn.danger
                ? 'color-mix(in srgb, #f7768e 20%, transparent)'
                : 'color-mix(in srgb, var(--foreground, #efefef) 10%, transparent)'

              if (btn.danger) {e.currentTarget.style.color = '#f7768e'}
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = 'var(--muted-foreground, #888)'
            }}
            style={{
              width: 40,
              height: 28,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'transparent',
              border: 'none',
              borderRadius: 4,
              color: btn.danger ? 'var(--muted-foreground, #888)' : 'var(--muted-foreground, #888)',
              cursor: 'pointer',
              fontSize: 12,
              fontFamily: 'inherit',
              lineHeight: 1
            }}
            type="button"
          >
            {btn.glyph}
          </button>
        ))}
      </div>
    </header>
  )
}
