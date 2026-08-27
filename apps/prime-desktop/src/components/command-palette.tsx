/**
 * A3 — Command palette (Ctrl+K). Port of Hermes desktop's command-palette.
 *
 * Opens on Ctrl+K: searchable list of actions from the registry.
 * Keyboard: ↑↓ navigate, Enter select, Esc close. No mouse needed.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { type Action, searchActions } from '../actions'

export function CommandPalette({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const results = searchActions(query)

  // Focus input on open
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Scroll selected into view
  useEffect(() => {
    const el = listRef.current?.children[selectedIndex] as HTMLElement | undefined
    el?.scrollIntoView?.({ block: 'nearest' })
  }, [selectedIndex])

  const run = useCallback(
    (action: Action) => {
      onClose()
      action.run()
    },
    [onClose]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter' && results[selectedIndex]) {
        e.preventDefault()
        run(results[selectedIndex])
      }
    },
    [onClose, results, selectedIndex, run]
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
          width: 520,
          maxHeight: '60vh',
          background: 'var(--theme-mix-card, #1a1a1a)',
          border: '1px solid var(--border, #2a2a2a)',
          borderRadius: 10,
          boxShadow: 'var(--shadow-nous, 0 8px 32px rgba(0,0,0,0.5))',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <input
          onChange={(e) => {
            setQuery(e.target.value)
            setSelectedIndex(0)
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search actions…"
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
        <div
          ref={listRef}
          style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}
        >
          {results.length === 0 && query && (
            <div style={{ padding: '16px 14px', color: 'var(--muted-foreground, #888)', fontSize: 13 }}>
              No matching actions.
            </div>
          )}
          {results.map((action, i) => {
            const selected = i === selectedIndex

            return (
              <button
                key={action.id}
                onClick={() => run(action)}
                onMouseEnter={() => setSelectedIndex(i)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  width: '100%',
                  padding: '8px 14px',
                  textAlign: 'left',
                  border: 'none',
                  background: selected ? 'color-mix(in srgb, var(--accent, #5e6ad2) 25%, transparent)' : 'transparent',
                  color: 'var(--foreground, #efefef)',
                  cursor: 'pointer',
                  fontSize: 13,
                  fontFamily: 'inherit'
                }}
              >
                <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', minWidth: 48 }}>
                  {action.category}
                </span>
                <span style={{ flex: 1 }}>{action.label}</span>
                <span style={{ fontSize: 10, color: 'var(--muted-foreground, #888)', opacity: 0.6 }}>
                  {action.keywords.slice(0, 2).join(', ')}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}