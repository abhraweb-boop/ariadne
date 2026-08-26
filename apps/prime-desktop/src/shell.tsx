/**
 * Prime Hermes — App shell (chat-first layout).
 *
 * Hermes-inspired: session rail | chat (primary) | panes overlay | statusbar.
 * All panes registered via a simple registry, openable from the rail or
 * command palette. Chat is the home surface.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { startEventBus } from './event-bus'

// ── Pane registry ───────────────────────────────────────────────────────

export interface Pane {
  id: string
  label: string
  icon: string
  render: React.FC<{ onClose: () => void }>
}

const paneRegistry = new Map<string, Pane>()

export function registerPane(pane: Pane): void {
  paneRegistry.set(pane.id, pane)
}

export function getPanes(): Pane[] {
  return [...paneRegistry.values()]
}

// ── Shell component ──────────────────────────────────────────────────────

export function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [openPaneId, setOpenPaneId] = useState<string | null>(null)
  const [layout, setLayout] = useState<{ rail: number; panes: string[] }>(() => {
    try {
      const saved = localStorage.getItem('prime-hermes-layout')
      return saved ? JSON.parse(saved) : { rail: 260, panes: [] }
    } catch {
      return { rail: 260, panes: [] }
    }
  })

  useEffect(() => {
    startEventBus()
  }, [])

  const openPane = useCallback(
    (id: string) => {
      setOpenPaneId((prev) => (prev === id ? null : id))
    },
    []
  )

  const openPaneView = useCallback((pane: Pane) => {
    setOpenPaneId(pane.id)
  }, [])

  const activePane = openPaneId ? paneRegistry.get(openPaneId) : null
  const sessionIds = useMemo(() => ['session-1', 'session-2'], [])

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--background, #101012)',
        color: 'var(--foreground, #efefef)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
        fontSize: 14
      }}
    >
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Sessions rail */}
        <nav
          style={{
            width: layout.rail,
            borderRight: '1px solid var(--border, #2a2a2a)',
            display: 'flex',
            flexDirection: 'column',
            background: 'var(--background, #101012)',
            overflowY: 'auto'
          }}
        >
          <div style={{ padding: '10px 14px', fontWeight: 600, fontSize: 13, opacity: 0.8 }}>
            Sessions
          </div>
          {sessionIds.map((id) => (
            <button
              key={id}
              onClick={() => setSessionId(id)}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 14px',
                textAlign: 'left',
                background: sessionId === id ? 'var(--accent, #5e6ad2)' : 'transparent',
                color: 'var(--foreground, #efefef)',
                border: 'none',
                cursor: 'pointer',
                fontSize: 13,
                fontFamily: 'inherit'
              }}
            >
              {id}
            </button>
          ))}
          <div style={{ borderTop: '1px solid var(--border, #2a2a2a)', marginTop: 8, paddingTop: 8 }}>
            <div style={{ padding: '4px 14px', fontSize: 11, opacity: 0.5 }}>Panels</div>
            {getPanes().map((pane) => (
              <button
                key={pane.id}
                onClick={() => openPaneView(pane)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '6px 14px',
                  textAlign: 'left',
                  background: 'transparent',
                  color: 'var(--foreground, #efefef)',
                  border: 'none',
                  cursor: 'pointer',
                  fontSize: 12,
                  fontFamily: 'inherit',
                  opacity: 0.8
                }}
              >
                <span>{pane.icon}</span>
                <span>{pane.label}</span>
              </button>
            ))}
          </div>
        </nav>

        {/* Main area: chat (primary) + pane overlay */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0, position: 'relative' }}>
          {/* Chat (always visible, primary surface) */}
          <ChatView sessionId={sessionId} />

          {/* Pane overlay (slides in from right) */}
          {activePane && (
            <div
              style={{
                width: 480,
                borderLeft: '1px solid var(--border, #2a2a2a)',
                background: 'var(--background, #101012)',
                overflow: 'auto'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>
                  {activePane.icon} {activePane.label}
                </span>
                <button
                  onClick={() => setOpenPaneId(null)}
                  style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}
                >
                  ✕
                </button>
              </div>
              <activePane.render onClose={() => setOpenPaneId(null)} />
            </div>
          )}
        </div>
      </div>

      {/* Statusbar (S3: cost meter, model badge, SSE status) */}
      <Statusbar sessionId={sessionId} />
    </div>
  )
}

// ── Chat view ────────────────────────────────────────────────────────────

function ChatView({ sessionId }: { sessionId: string | null }) {
  const [messages, setMessages] = useState<
    Array<{ role: string; text: string; id: string }>
  >([])
  const [input, setInput] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (endRef.current) endRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function send() {
    if (!input.trim()) return
    const id = `msg-${Date.now()}`
    setMessages((prev) => [...prev, { role: 'user', text: input.trim(), id }])
    setInput('')
    // In real use, this would POST to the chat/gateway endpoint.
    // For now, echo a placeholder response.
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: `Received. (Session: ${sessionId ?? 'none'})`,
          id: `msg-${Date.now()}`
        }
      ])
    }, 300)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: 14 }}>
        {!sessionId && (
          <p style={{ color: 'var(--muted-foreground, #888)', fontSize: 13, marginTop: 40, textAlign: 'center' }}>
            Select a session to start chatting, or create a new one.
          </p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              marginBottom: 10,
              padding: '8px 12px',
              borderRadius: 8,
              background:
                m.role === 'user'
                  ? 'color-mix(in srgb, var(--accent, #5e6ad2) 15%, transparent)'
                  : 'color-mix(in srgb, var(--foreground, #efefef) 5%, transparent)',
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%'
            }}
          >
            <div style={{ fontSize: 11, opacity: 0.5, marginBottom: 4 }}>{m.role}</div>
            <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{m.text}</div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: '10px 14px',
          borderTop: '1px solid var(--border, #2a2a2a)'
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          placeholder="Send a message…"
          aria-label="Chat message"
          style={{
            flex: 1,
            background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)',
            border: '1px solid var(--border, #2a2a2a)',
            borderRadius: 6,
            padding: '8px 12px',
            color: 'inherit',
            fontSize: 13,
            outline: 'none',
            fontFamily: 'inherit'
          }}
        />
        <button
          onClick={send}
          style={{
            background: 'var(--accent, #5e6ad2)',
            border: 'none',
            color: '#fff',
            borderRadius: 6,
            padding: '8px 16px',
            cursor: 'pointer',
            fontSize: 13,
            fontFamily: 'inherit'
          }}
        >
          Send
        </button>
      </div>
    </div>
  )
}

// ── Statusbar (S3: cost meter, model, SSE status) ───────────────────────

function Statusbar({ sessionId: _sessionId }: { sessionId: string | null }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '3px 14px',
        borderTop: '1px solid var(--border, #2a2a2a)',
        fontSize: 11,
        color: 'var(--muted-foreground, #888)',
        fontVariantNumeric: 'tabular-nums'
      }}
    >
      <span>⚡ gpt-4o-mini</span>
      <span>| Tokens: 0</span>
      <span>| Plans: 0</span>
      <span style={{ marginLeft: 'auto' }}>Prime Hermes v0.1.0</span>
    </div>
  )
}