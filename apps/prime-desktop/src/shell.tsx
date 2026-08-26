/**
 * Prime Hermes — App shell (chat-first layout, fully wired).
 *
 * Chat is the primary surface (Hermes-style). Composer POSTs to the real
 * Prime worker (/api/prime/prompt). Transcript renders from event bus
 * (prime.message_update events → text deltas). All capability panes are
 * registered through the pane registry and open from the sessions rail.
 * Statusbar shows cost/token/monitoring info (S3).
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { registerCoreActions } from './actions-registry'
import { get, post } from './api'
import { KernelCellCard, TaskCard, type TaskInfo, ToolCallCard } from './cards'
import { CommandPalette } from './components/command-palette'
import { Composer } from './components/composer'
import { ErrorBoundary } from './components/error-boundary'
import { FindBar } from './components/find-bar'
import { MarkdownText } from './components/markdown-text'
import { Notifications } from './components/notifications'
import { Statusbar } from './components/statusbar'
import { StreamingCaret } from './components/streaming-caret'
import { Titlebar } from './components/titlebar'
import { type BusEvent, onEvent, startEventBus } from './event-bus'
import { highlightSegments } from './lib/highlight'
import { streamReducer } from './lib/stream-reducer'
import { registerAllPanes } from './panes/index'
import { getPanes } from './panes/registry'
import { installShortcuts, registerShortcut } from './shortcuts'

// Register all panes once at module load.
registerAllPanes()

// ── Shell ───────────────────────────────────────────────────────────────

interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  cards?: Array<{ type: string; data: Record<string, unknown> }>
}

// S5: detached-execution resume banner state
interface FinishedAwayPlan {
  id: string
  goal: string
  state: string
}

const LAST_SEEN_KEY = 'prime-hermes-last-seen-at'

interface PlanSummary {
  id: string
  goal: string
  state: string
  created_at: number
  updated_at?: number
}

export function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [openPaneId, setOpenPaneId] = useState<string | null>(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [findOpen, setFindOpen] = useState(false)
  const [findQuery, setFindQuery] = useState('')
  const [activeFind, setActiveFind] = useState<{ messageIndex: number; textIndex: number } | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [primeState, setPrimeState] = useState<string>('idle')
  const [tokenCount, setTokenCount] = useState(0)
  const [planCount, setPlanCount] = useState(0)
  const endRef = useRef<HTMLDivElement>(null)
  const [sessions, setSessions] = useState<Array<{ id: string; title: string }>>([])
  // S5: resume banner
  const [finishedAway, setFinishedAway] = useState<FinishedAwayPlan[]>([])

  // Event bus — S1 unified spine, listen for prime events.
  useEffect(() => {
    startEventBus()

    const unsubPrime = onEvent('prime.*', (ev: BusEvent) => {
      const typ = ev.type
      const payload = ev.payload as Record<string, unknown>

      // Accumulate text deltas (B3: via tested streamReducer)
      if (typ === 'prime.message_update') {
        const assistant = payload.assistantMessageEvent as Record<string, unknown> | undefined

        if (assistant?.type === 'text_delta') {
          const delta = (assistant.delta as string) ?? ''
          setMessages((prev) => streamReducer(prev, { type: 'delta', delta }))
        }
      }

      if (typ === 'prime.agent_end') {
        setSending(false)
        setMessages((prev) => streamReducer(prev, { type: 'finalize' }))
      }

      // Update prime state badge
      if (typ === 'prime.spawned') {setPrimeState('running')}

      if (typ === 'prime.stopped') {setPrimeState('stopped')}
    })

    return () => unsubPrime()
  }, [])

  // S5: detect plans that finished while the app was closed (detached exec)
  useEffect(() => {
    const lastSeen = Number(localStorage.getItem(LAST_SEEN_KEY) ?? '0')
    const now = Date.now()
    localStorage.setItem(LAST_SEEN_KEY, String(now))

    void get<{ ok: boolean; plans: PlanSummary[] }>('/api/ariadne/plans')
      .then((r) => {
        if (!r.ok) {return}
        const terminal = new Set(['done', 'partial', 'failed', 'cancelled'])

        const away = r.plans.filter((p) => {
          // Finished after we last looked, and we were gone for a while.
          const endedAt = Number(p.updated_at ?? 0) * 1000

          return terminal.has(p.state) && endedAt >= lastSeen && endedAt < now
        })

        setFinishedAway(
          away.map((p) => ({ id: p.id, goal: p.goal, state: p.state }))
        )
      })
      .catch(() => {})
  }, [])

  // A3+A6: register core actions + shortcuts through the central registry
  useEffect(() => {
    registerCoreActions({
      openPane: (id) => setOpenPaneId(id),
      newSession: () => {
        setSessionId(null)
        setMessages([])
      }
    })

    registerShortcut({
      id: 'palette:open',
      label: 'Open command palette',
      combo: 'Ctrl+K',
      handler: () => setPaletteOpen(true)
    })
    registerShortcut({
      id: 'find:open',
      label: 'Find in conversation',
      combo: 'Ctrl+F',
      handler: () => setFindOpen(true)
    })

    return installShortcuts()
  }, [])

  // Load sessions + poll plans count
  useEffect(() => {
      void get<{ ok?: boolean; sessions?: Array<{ id: string; title: string }> }>('/api/sessions')
      .then((r) => setSessions(r.sessions ?? []))
      .catch(() => setSessions([]))

    // Poll plans count for statusbar
    const interval = setInterval(() => {
      void get<{ ok: boolean; plans: unknown[] }>('/api/ariadne/plans')
        .then((r) => { if (r.ok) {setPlanCount(r.plans.length)} })
        .catch(() => {})
    }, 10000)

    return () => clearInterval(interval)
  }, [])

  // Auto-scroll
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = useCallback(async () => {
    const text = input.trim()

    if (!text || sending) {return}
    setInput('')
    setSending(true)
    setMessages((prev) => streamReducer(prev, { type: 'user', text }))

    try {
      await post('/api/prime/prompt', { prompt: text })
    } catch (e) {
      setMessages((prev) => streamReducer(prev, { type: 'system', text: `Error: ${String(e)}` }))
      setSending(false)
    }
  }, [input, sending])

  const openPane = useCallback((id: string) => {
    setOpenPaneId((prev) => (prev === id ? null : id))
  }, [])

  const activePane = openPaneId ? getPanes().find((p) => p.id === openPaneId) ?? null : null

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#101012',
        color: '#efefef',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
        fontSize: 14
      }}
    >
      <Notifications />
      <Titlebar />
      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Sessions rail */}
        <nav
          style={{
            width: 260,
            borderRight: '1px solid #2a2a2a',
            display: 'flex',
            flexDirection: 'column',
            background: '#101012',
            overflowY: 'auto'
          }}
        >
          <div style={{ padding: '10px 14px', fontWeight: 600, fontSize: 13, opacity: 0.8 }}>
            Prime Hermes
          </div>
          <div style={{ padding: '4px 14px', fontSize: 11, opacity: 0.5 }}>Sessions</div>
          {sessions.length === 0 && (
            <div style={{ padding: '8px 14px', fontSize: 12, opacity: 0.5 }}>
              {sessions.length === 0 ? 'No sessions found. Start a new one.' : ''}
            </div>
          )}
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => setSessionId(s.id)}
              style={{
                display: 'block',
                width: '100%',
                padding: '8px 14px',
                textAlign: 'left',
                background: sessionId === s.id ? 'var(--accent, #5e6ad2)' : 'transparent',
                color: '#efefef',
                border: 'none',
                cursor: 'pointer',
                fontSize: 13,
                fontFamily: 'inherit'
              }}
            >
              {s.title || s.id}
            </button>
          ))}
          <div style={{ borderTop: '1px solid #2a2a2a', marginTop: 8, paddingTop: 8 }}>
            <div style={{ padding: '4px 14px', fontSize: 11, opacity: 0.5 }}>Panels</div>
            {getPanes().map((pane) => (
              <button
                key={pane.id}
                onClick={() => openPane(pane.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '6px 14px',
                  textAlign: 'left',
                  background: 'transparent',
                  color: '#efefef',
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

        {/* Main area */}
        <div style={{ flex: 1, display: 'flex', minHeight: 0, position: 'relative' }}>
          {/* Chat */}
          <ErrorBoundary>
          <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
            {findOpen && (
              <FindBar
                messages={messages}
                onActiveMatch={setActiveFind}
                onClose={() => { setFindOpen(false); setFindQuery(''); setActiveFind(null) }}
                onQueryChange={setFindQuery}
              />
            )}
            <div style={{ flex: 1, overflowY: 'auto', padding: 14 }}>
              {/* S5: resume banner — plans finished while the app was away */}
              {finishedAway.length > 0 && (
                <div
                  style={{
                    border: '1px solid #9ece6a',
                    borderRadius: 8,
                    padding: 10,
                    marginBottom: 12,
                    background: 'color-mix(in srgb, #9ece6a 8%, transparent)'
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                    Plans finished while you were away
                  </div>
                  {finishedAway.map((p) => (
                    <div key={p.id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                      <span style={{ fontSize: 12, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.goal.slice(0, 80)}
                      </span>
                      <span style={{ fontSize: 11, color: '#9ece6a', border: '1px solid #9ece6a', borderRadius: 999, padding: '0 8px' }}>
                        {p.state}
                      </span>
                      <button
                        onClick={() => openPane('dags')}
                        style={{
                          background: 'none',
                          border: '1px solid var(--border, #2a2a2a)',
                          borderRadius: 4,
                          color: 'inherit',
                          cursor: 'pointer',
                          fontSize: 11,
                          padding: '2px 8px',
                          fontFamily: 'inherit'
                        }}
                      >
                        View results
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {!sessionId && (
                <p style={{ color: '#888', fontSize: 13, marginTop: 40, textAlign: 'center' }}>
                  Select a session or start typing below. The composer sends to the Prime worker.
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
                        ? 'color-mix(in srgb, #5e6ad2 15%, transparent)'
                        : 'color-mix(in srgb, #efefef 5%, transparent)',
                    maxWidth: '85%',
                    alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start'
                  }}
                >
                  <div style={{ fontSize: 11, opacity: 0.5, marginBottom: 4 }}>{m.role}</div>
                  <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {findQuery && highlightSegments(m.text, findQuery).map((seg, si) =>
                      seg.match ? (
                        <mark
                          key={si}
                          style={{
                            background: activeFind?.messageIndex === messages.indexOf(m)
                              ? '#e0af68'
                              : '#5e6ad2',
                            color: '#101012',
                            borderRadius: 2,
                            padding: '0 1px'
                          }}
                        >
                          {seg.text}
                        </mark>
                      ) : (
                        <span key={si}>{seg.text}</span>
                      )
                    )}
                    {!findQuery && m.role === 'assistant' && <MarkdownText text={m.text} />}
                    {!findQuery && m.role !== 'assistant' && m.text}
                    {/* B3: streaming caret on the last assistant message */}
                    {sending && m.role === 'assistant' && m.id === messages[messages.length - 1]?.id && (
                      <StreamingCaret />
                    )}
                  </div>
                  {m.cards?.map((c, i) => {
                    if (c.type === 'task')
                      {return <TaskCard key={i} onOpenBoard={() => openPane('dags')} task={c.data as unknown as TaskInfo} />}

                    if (c.type === 'kernel')
                      {return <KernelCellCard code={c.data.code as string} key={i} output={c.data.output as string | undefined} />}

                    if (c.type === 'tool')
                      {return <ToolCallCard durationMs={c.data.durationMs as number | undefined} key={i} name={c.data.name as string} status={c.data.status as 'ok' | 'running' | 'failed'} />}

                    return null
                  })}
                </div>
              ))}
              <div ref={endRef} />
            </div>
            <Composer
              input={input}
              onInputChange={setInput}
              onSend={send}
              sending={sending}
            />
          </div>
          </ErrorBoundary>

          {/* Pane overlay */}
          <ErrorBoundary>
          {activePane && (
            <div
              style={{
                width: 480,
                borderLeft: '1px solid #2a2a2a',
                background: '#101012',
                overflow: 'auto',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              <activePane.render onClose={() => setOpenPaneId(null)} />
            </div>
          )}
          </ErrorBoundary>
        </div>
      </div>

      {/* Statusbar (A2 — port of Hermes statusbar-controls; G2 adds prime widgets) */}
      <Statusbar onOpenPane={(id) => setOpenPaneId(id)} />

      {/* Command palette (A3) */}
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
    </div>
  )
}