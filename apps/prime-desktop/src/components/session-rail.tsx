/**
 * C1 — Session rail with full CRUD (port of Hermes desktop session rail).
 *
 * Create button, active highlight, hover actions (rename/delete) with
 * optimistic updates + rollback on failure (desktop AGENTS.md: be
 * optimistic, then honest).
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { createSession, deleteSession, listSessions, renameSession, type SessionInfo } from '../sessions'

export function SessionRail({
  activeId,
  onSelect,
  onNewSession
}: {
  activeId: string | null
  onSelect: (id: string) => void
  onNewSession: () => void
}) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [menuFor, setMenuFor] = useState<string | null>(null)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const menuRef = useRef<HTMLDivElement>(null)

  const refresh = useCallback(() => {
    void listSessions().then(setSessions)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // Close menu on outside click
  useEffect(() => {
    if (!menuFor) {return}

    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuFor(null)
      }
    }

    document.addEventListener('mousedown', handler)

    return () => document.removeEventListener('mousedown', handler)
  }, [menuFor])

  const handleCreate = useCallback(async () => {
    const id = await createSession()

    if (id) {
      refresh()
      onSelect(id)
    }
  }, [onSelect, refresh])

  const handleRename = useCallback(async (id: string, title: string) => {
    const prev = sessions
    // Optimistic
    setSessions((cur) => cur.map((s) => (s.id === id ? { ...s, title } : s)))
    setRenaming(null)
    const ok = await renameSession(id, title)

    if (!ok) {setSessions(prev)} // rollback
  }, [sessions])

  const handleDelete = useCallback(async (id: string) => {
    const prev = sessions
    setMenuFor(null)
    // Optimistic
    setSessions((cur) => cur.filter((s) => s.id !== id))
    const ok = await deleteSession(id)

    if (!ok) {setSessions(prev)}
  }, [sessions])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', padding: '4px 14px' }}>
        <span style={{ fontSize: 11, opacity: 0.5, flex: 1 }}>Sessions</span>
        <button
          aria-label="New session"
          onClick={() => void handleCreate()}
          style={{
            background: 'transparent',
            border: '1px solid var(--border, #2a2a2a)',
            borderRadius: 4,
            color: 'var(--foreground, #efefef)',
            cursor: 'pointer',
            fontSize: 11,
            lineHeight: 1,
            padding: '2px 6px',
            fontFamily: 'inherit'
          }}
          title="New session"
        >
          + New
        </button>
      </div>

      {sessions.length === 0 && (
        <div style={{ padding: '8px 14px', fontSize: 12, opacity: 0.5 }}>
          No sessions found. Start a new one.
        </div>
      )}

      {sessions.map((s) => (
        <div
          key={s.id}
          onMouseEnter={() => { if (menuFor !== s.id) {setMenuFor(null)} }}
          style={{ position: 'relative', display: 'flex', alignItems: 'center' }}
        >
          {renaming === s.id ? (
            <input
              autoFocus
              defaultValue={s.title || s.id}
              onBlur={(e) => { void handleRename(s.id, e.target.value.trim() || s.id) }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  void handleRename(s.id, (e.target as HTMLInputElement).value.trim() || s.id)
                }

                if (e.key === 'Escape') {setRenaming(null)}
              }}
              style={{
                flex: 1,
                margin: '2px 14px',
                background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)',
                border: '1px solid var(--accent, #5e6ad2)',
                borderRadius: 4,
                padding: '4px 8px',
                color: 'inherit',
                fontSize: 13,
                fontFamily: 'inherit'
              }}
            />
          ) : (
            <button
              onClick={() => onSelect(s.id)}
              style={{
                display: 'block',
                flex: 1,
                width: '100%',
                padding: '8px 14px',
                textAlign: 'left',
                background: activeId === s.id ? 'var(--accent, #5e6ad2)' : 'transparent',
                color: '#efefef',
                border: 'none',
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
          )}
          {activeId === s.id && renaming !== s.id && (
            <button
              aria-label={`Session menu ${s.title || s.id}`}
              onClick={() => setMenuFor(menuFor === s.id ? null : s.id)}
              style={{
                position: 'absolute',
                right: 6,
                background: 'transparent',
                border: 'none',
                color: '#efefef',
                cursor: 'pointer',
                fontSize: 11,
                padding: '2px 4px',
                fontFamily: 'inherit',
                opacity: 0.8
              }}
            >
              ⋯
            </button>
          )}
          {menuFor === s.id && (
            <div
              ref={menuRef}
              style={{
                position: 'absolute',
                right: 6,
                top: '100%',
                zIndex: 50,
                background: '#1a1a1a',
                border: '1px solid var(--border, #2a2a2a)',
                borderRadius: 6,
                boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                minWidth: 140
              }}
            >
              <button
                onClick={() => { setMenuFor(null); setRenaming(s.id); setRenameValue(s.title || s.id) }}
                style={menuItemStyle}
              >
                ✏️ Rename
              </button>
              <button
                onClick={() => { void handleDelete(s.id) }}
                style={{ ...menuItemStyle, color: '#f7768e' }}
              >
                🗑 Delete
              </button>
            </div>
          )}
        </div>
      ))}
      <span style={{ display: 'none' }}>{renameValue}</span>
    </div>
  )
}

const menuItemStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '6px 10px',
  textAlign: 'left',
  background: 'transparent',
  border: 'none',
  color: 'var(--foreground, #efefef)',
  cursor: 'pointer',
  fontSize: 12,
  fontFamily: 'inherit'
}
