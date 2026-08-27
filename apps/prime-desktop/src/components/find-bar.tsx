/**
 * A4 — Find bar (Ctrl+F). Port of Hermes desktop's find-bar.
 *
 * Searches the transcript: match count, prev/next, Enter to advance,
 * Esc to close. Active match is reported to the transcript so it can
 * scroll + highlight.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { findMatches } from '../lib/highlight'

export function FindBar({
  messages,
  onClose,
  onActiveMatch,
  onQueryChange
}: {
  messages: Array<{ role: string; text: string }>
  onClose: () => void
  onActiveMatch: (match: { messageIndex: number; textIndex: number } | null) => void
  onQueryChange?: (query: string) => void
}) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const matches = useMemo(() => findMatches(messages, query), [messages, query])

  // Focus on open
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Report active match to transcript
  useEffect(() => {
    onActiveMatch(matches.length > 0 ? matches[active] : null)
  }, [matches, active, onActiveMatch])

  const go = useCallback((dir: 1 | -1) => {
    if (matches.length === 0) {return}
    setActive((a) => (a + dir + matches.length) % matches.length)
  }, [matches.length])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      } else if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        go(1)
      } else if (e.key === 'Enter' && e.shiftKey) {
        e.preventDefault()
        go(-1)
      }
    },
    [go, onClose]
  )

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 12px',
        borderBottom: '1px solid var(--border, #2a2a2a)',
        background: 'color-mix(in srgb, var(--accent, #5e6ad2) 8%, transparent)'
      }}
    >
      <span style={{ fontSize: 12, opacity: 0.7 }}>🔍</span>
      <input
        onChange={(e) => {
          setQuery(e.target.value)
          setActive(0)
          onQueryChange?.(e.target.value)
        }}
        onKeyDown={handleKeyDown}
        placeholder="Find in conversation…"
        ref={inputRef}
        style={{
          flex: 1,
          background: 'transparent',
          border: 'none',
          borderBottom: '1px solid var(--border, #2a2a2a)',
          padding: '2px 4px',
          color: 'var(--foreground, #efefef)',
          fontSize: 13,
          fontFamily: 'inherit',
          
        }}
        value={query}
      />
      <span
        style={{
          fontSize: 11,
          color: 'var(--muted-foreground, #888)',
          fontVariantNumeric: 'tabular-nums',
          minWidth: 40,
          textAlign: 'right'
        }}
      >
        {query ? `${matches.length === 0 ? 0 : active + 1}/${matches.length}` : ''}
      </span>
      <button
        aria-label="Previous match"
        disabled={matches.length === 0}
        onClick={() => go(-1)}
        style={navBtnStyle}
      >
        ↑
      </button>
      <button
        aria-label="Next match"
        disabled={matches.length === 0}
        onClick={() => go(1)}
        style={navBtnStyle}
      >
        ↓
      </button>
      <button aria-label="Close find" onClick={onClose} onMouseEnter={(e) => hoverBtn(e, true)} onMouseLeave={(e) => hoverBtn(e, false)} style={navBtnStyle}>
        ✕
      </button>
    </div>
  )
}

function hoverBtn(e: React.MouseEvent<HTMLButtonElement>, on: boolean): void {
  e.currentTarget.style.background = on
    ? 'color-mix(in srgb, var(--foreground, #efefef) 8%, transparent)'
    : 'transparent'
}

const navBtnStyle: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  borderRadius: 4,
  padding: '2px 6px',
  color: 'var(--muted-foreground, #888)',
  cursor: 'pointer',
  fontSize: 12,
  fontFamily: 'inherit',
  opacity: 1
}
