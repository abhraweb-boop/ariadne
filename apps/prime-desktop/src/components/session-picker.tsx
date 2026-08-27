/**
 * C2 — Session picker overlay (port of Hermes desktop session-picker-overlay).
 *
 * Opens on Ctrl+P: type-to-filter sessions, ↑↓ navigate, Enter select,
 * Esc close. Keyboard-first, no mouse needed.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { listSessions, type SessionInfo } from '../sessions'

export function SessionPicker({
  onSelect,
  onClose
}: {
  onSelect: (id: string) => void
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    void listSessions().then(setSessions)
    inputRef.current?.focus()
  }, [])

  const filtered = useMemo(() => {
    const q = query.toLowerCase()

    if (!q) {return sessions}

    return sessions.filter((s) => (s.title || s.id).toLowerCase().includes(q))
  }, [sessions, query])

  useEffect(() => {
    const el = listRef.current?.children[selected] as HTMLElement | undefined
    el?.scrollIntoView?.({ block: 'nearest' })
  }, [selected])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelected((i) => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelected((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && filtered[selected]) {
        e.preventDefault()
        onSelect(filtered[selected].id)
        onClose()
      }
    },
    [filtered, selected, onSelect, onClose]
  )

  return (
    <div
      onClick={(e) => { if (e.target === e.currentTarget) {onClose()} }}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        display: 'flex',
        justifyContent: 'center',
        paddingTop: '10vh',
        background: 'rgba(0,0,0,0.5)'
      }}
    >
      <div
        style={{
          width: 460,
          maxHeight: '60vh',
          background: '#1a1a1a',
          border: '1px solid var(--border, #2a2a2a)',
          borderRadius: 10,
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <input
          onChange={(e) => { setQuery(e.target.value); setSelected(0) }}
          onKeyDown={handleKeyDown}
          placeholder="Switch session…"
          ref={inputRef}
          style={{
            width: '100%',
            padding: '12px 14px',
            background: 'transparent',
            border: 'none',
            borderBottom: '1px solid var(--border, #2a2a2a)',
            color: 'var(--foreground, #efefef)',
            fontSize: 14,
            fontFamily: 'inherit',
            
          }}
          value={query}
        />
        <div ref={listRef} style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
          {filtered.length === 0 && (
            <div style={{ padding: '16px 14px', color: 'var(--muted-foreground, #888)', fontSize: 13 }}>
              No sessions found.
            </div>
          )}
          {filtered.map((s, i) => (
            <button
              key={s.id}
              onClick={() => { onSelect(s.id); onClose() }}
              onMouseEnter={() => setSelected(i)}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 14px',
                textAlign: 'left',
                border: 'none',
                background: i === selected ? 'color-mix(in srgb, var(--accent, #5e6ad2) 25%, transparent)' : 'transparent',
                color: 'var(--foreground, #efefef)',
                cursor: 'pointer',
                fontSize: 13,
                fontFamily: 'inherit',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}
            >
              {s.title || s.id}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
