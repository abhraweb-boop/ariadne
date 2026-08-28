/**
 * A2 — Statusbar with context menu (port of Hermes desktop statusbar-controls).
 *
 * Hermes pattern: model badge (click → dropdown), gateway status dot,
 * approval-mode toggle, context usage. Prime additions: kernel state,
 * DAG plan count, worker state (added by G2). Always visible, clickable.
 */

import { useEffect, useRef, useState } from 'react'

import { get } from '../api'

export interface StatusbarItem {
  id: string
  label: string
  icon?: string
  badge?: { color: string; label: string }
  onClick?: () => void
}

export function Statusbar({
  onOpenPane,
  widgets
}: {
  onOpenPane?: (id: string) => void
  /** G2: live widgets rendered in the right cluster. */
  widgets?: React.ReactNode
}) {
  const [model, setModel] = useState('gpt-4o-mini')
  const [menuOpen, setMenuOpen] = useState<string | null>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) {return}

    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(null)
      }
    }

    document.addEventListener('mousedown', handler)

    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  // Poll model from prime state
  useEffect(() => {
    const poll = () => {
      void get<{ ok: boolean; state: { model?: string } }>('/api/prime/state')
        .then((r) => { if (r.ok && r.state?.model) {setModel(r.state.model)} })
        .catch(() => {})
    }

    poll()
    const interval = setInterval(poll, 30_000)

    return () => clearInterval(interval)
  }, [])

  const items: StatusbarItem[] = [
    { id: 'model', label: model, icon: '🧠' },
    { id: 'gateway', label: 'Gateway', icon: '⚡', badge: { color: '#9ece6a', label: 'connected' } },
    { id: 'approval', label: 'Approval', icon: '🛡️', badge: { color: '#e0af68', label: 'auto' } },
    { id: 'context', label: 'Context', icon: '📄', badge: { color: 'var(--muted-foreground, #888)', label: '3.2K' } },
  ]

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        padding: '2px 8px',
        borderTop: '1px solid var(--border, #2a2a2a)',
        fontSize: 11,
        color: 'var(--muted-foreground, #888)',
        fontVariantNumeric: 'tabular-nums',
        minHeight: 22,
        background: 'var(--background, #101012)'
      }}
    >
      {/* Left cluster: statusbar items */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
        {items.map((item) => (
          <div
            key={item.id}
            ref={item.id === menuOpen ? menuRef : undefined}
            style={{ position: 'relative' }}
          >
            <button
              aria-label={item.label}
              onClick={() => {
                if (item.id === 'model') {
                  setMenuOpen(menuOpen === item.id ? null : item.id)
                } else {
                  item.onClick?.()
                }
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'color-mix(in srgb, var(--foreground, #efefef) 8%, transparent)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent' }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                height: '100%',
                padding: '2px 8px',
                background: 'transparent',
                border: 'none',
                borderRadius: 3,
                color: 'var(--muted-foreground, #888)',
                cursor: 'pointer',
                fontSize: 11,
                fontFamily: 'inherit',
                lineHeight: 1
              }}
            >
              {item.icon && <span>{item.icon}</span>}
              <span>{item.label}</span>
              {item.badge && (
                <span
                  style={{
                    color: item.badge.color,
                    fontSize: 10,
                    marginLeft: 2
                  }}
                >
                  · {item.badge.label}
                </span>
              )}
            </button>
            {/* Model dropdown menu */}
            {item.id === 'model' && menuOpen === 'model' && (
              <div
                style={{
                  position: 'absolute',
                  bottom: '100%',
                  left: 0,
                  marginBottom: 4,
                  background: 'var(--theme-mix-card, #1a1a1a)',
                  border: '1px solid var(--border, #2a2a2a)',
                  borderRadius: 6,
                  padding: '4px 0',
                  minWidth: 180,
                  boxShadow: 'var(--shadow-nous, 0 4px 12px rgba(0,0,0,0.4))',
                  zIndex: 100
                }}
              >
                <div style={{ padding: '4px 10px', fontSize: 10, fontWeight: 600, letterSpacing: 0.6, textTransform: 'uppercase', color: 'var(--muted-foreground, #888)', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
                  Active model
                </div>
                <div style={{ padding: '6px 10px', fontSize: 12, color: 'var(--foreground, #efefef)' }}>
                  {model}
                </div>
                <div style={{ padding: '4px 10px', fontSize: 10, color: 'var(--muted-foreground, #888)' }}>
                  Set via settings or env
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Right cluster: version + prime-specific widgets */}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 4 }}>
        {widgets}
        <span style={{ fontSize: 10, opacity: 0.5 }}>Prime Hermes v0.1.1</span>
      </div>
    </div>
  )
}