/**
 * DAG Board (M3) — live plan execution with state columns, inspector, composer.
 *
 * One SSE spine (S1): subscribes to the event bus for plan/task transitions.
 * No-terminal design: visual columns of cards, point-and-click controls.
 * Keyboard: ↑/↓, R retry, C cancel, Esc clear.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { get, post } from '../api'
import { type BusEvent, onEvent } from '../event-bus'
import { extractSlots, listRecipes, materializeRecipe, type Recipe,
  saveRecipe
} from '../recipes'

interface PlanSummary {
  id: string
  goal: string
  state: string
  created_at: number
  n_tasks: number
  n_done: number
}

interface TaskView {
  id: string
  title: string
  kind: string
  state: string
  depends_on: string[]
  result?: unknown
  error?: string
  max_attempts?: number
}

const STATE_COLUMNS = ['pending', 'ready', 'running', 'done', 'failed', 'skipped'] as const

const STATE_LABEL: Record<string, string> = {
  pending: 'Pending', ready: 'Ready', running: 'Running',
  done: 'Done', failed: 'Failed', skipped: 'Skipped'
}

export function DagBoard({ onClose }: { onClose: () => void }) {
  const [planId, setPlanId] = useState<string | null>(null)
  const [plans, setPlans] = useState<PlanSummary[]>([])
  const [tasks, setTasks] = useState<TaskView[]>([])
  const [planState, setPlanState] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [composerText, setComposerText] = useState('')
  const [running, setRunning] = useState(false)
  // S4: recipe state
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [recipeName, setRecipeName] = useState('')
  const [slotValues, setSlotValues] = useState<Record<string, string>>({})
  const [activeRecipe, setActiveRecipe] = useState<Recipe | null>(null)
  const [showSlots, setShowSlots] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)

  // Load plan list
  useEffect(() => {
    void get<{ ok: boolean; plans: PlanSummary[] }>('/api/ariadne/plans').then((r) => {
      if (r.ok) {setPlans(r.plans)}
    })
  }, [])

  // S4: load recipes on mount
  useEffect(() => {
    setRecipes(listRecipes())
  }, [])

  // S4: save current composer text as a recipe
  const saveAsRecipe = useCallback(() => {
    const name = recipeName.trim()

    if (!name) {return}
    const lines = composerText.trim().split('\n').filter(Boolean)

    const tasks = lines.map((line) => ({
      title: line.replace(/^dep: (\w+): /, '').trim(),
      kind: 'note' as const,
      payload: { text: line },
      depends_on: line.startsWith('dep: ') ? [line.match(/^dep: (\w+)/)![1]] : []
    }))

    if (tasks.length === 0) {return}
    saveRecipe(name, composerText.slice(0, 80), tasks)
    setRecipes(listRecipes())
    setRecipeName('')
  }, [composerText, recipeName])

  // S4: begin loading a recipe — detect slots
  const startRecipe = useCallback((recipe: Recipe) => {
    setActiveRecipe(recipe)
    const slots = extractSlots(recipe.tasks)

    if (slots.length > 0) {
      setSlotValues(Object.fromEntries(slots.map((s) => [s, ''])))
      setShowSlots(true)
    } else {
      // No slots — load directly
      loadRecipe(recipe, {})
    }
  }, [])

  // S4: fill slots and load recipe into composer
  const confirmSlots = useCallback(() => {
    if (!activeRecipe) {return}
    loadRecipe(activeRecipe, slotValues)
    setShowSlots(false)
    setActiveRecipe(null)
  }, [activeRecipe, slotValues])

  const loadRecipe = useCallback((recipe: Recipe, values: Record<string, string>) => {
    const tasks = materializeRecipe(recipe, values)
    const text = tasks.map((t) => t.title).join('\n')
    setComposerText(text)
  }, [])

  // Load a plan's tasks
  const loadPlan = useCallback(async (pid: string) => {
    setPlanId(pid)

    try {
      const r = await get<{ ok: boolean; plan: Record<string, unknown>; tasks: TaskView[]; status: string }>(
        `/api/ariadne/plans/${pid}`
      )

      if (r.ok) {
        setTasks(r.tasks)
        setPlanState(r.status)
        setRunning(r.status === 'running')
      }
    } catch {
      setTasks([])
    }
  }, [])

  // Subscribe to event bus for real-time updates (S1)
  useEffect(() => {
    const unsub = onEvent('plan.completed', (ev: BusEvent) => {
      const pid = (ev.payload as Record<string, unknown>).plan_id as string

      if (pid === planId) {
        setRunning(false)
        setPlanState('done')
        void loadPlan(pid)
      }
    })

    const unsub2 = onEvent('plan.cancelled', (ev: BusEvent) => {
      const pid = (ev.payload as Record<string, unknown>).plan_id as string

      if (pid === planId) {
        setRunning(false)
        setPlanState('cancelled')
      }
    })

    return () => {
      unsub()
      unsub2()
    }
  }, [planId, loadPlan])

  // Reload tasks when plan changes events
  useEffect(() => {
    if (planId && running) {
      const interval = setInterval(() => void loadPlan(planId), 2000)

      return () => clearInterval(interval)
    }
  }, [planId, running, loadPlan])

  const grouped = useMemo(() => {
    const g = new Map<string, TaskView[]>()

    for (const col of STATE_COLUMNS) {g.set(col, [])}

    for (const t of tasks) {
      const arr = g.get(t.state) ?? []
      arr.push(t)
    }

    return g
  }, [tasks])

  const selected = tasks.find((t) => t.id === selectedId) ?? null

  async function runPlan() {
    if (!planId) {return}
    setRunning(true)
    setPlanState('running')
    await post(`/api/ariadne/plans/${planId}/run`, {})
  }

  async function cancelPlan() {
    if (!planId) {return}
    await post(`/api/ariadne/plans/${planId}/cancel`, {})
    setRunning(false)
    setPlanState('cancelled')
  }

  async function retryTask(taskId: string) {
    await post(`/api/ariadne/tasks/${taskId}/retry`, {})
    await loadPlan(planId!)
  }

  async function createPlan() {
    const lines = composerText.trim().split('\n').filter(Boolean)

    if (lines.length === 0) {return}

    const tasks = lines.map((line, i) => ({
      title: line.replace(/^dep: (\w+): /, '').trim(),
      kind: 'note' as const,
      payload: { text: line },
      depends_on: line.startsWith('dep: ') ? [line.match(/^dep: (\w+)/)![1]] : []
    }))

    try {
      const r = await post<{ ok: boolean; plan_id: string }>('/api/ariadne/plans', {
        goal: composerText.slice(0, 80),
        tasks
      })

      if (r.ok) {
        setComposerText('')
        void loadPlan(r.plan_id)
        void get<{ ok: boolean; plans: PlanSummary[] }>('/api/ariadne/plans').then((res) => {
          if (res.ok) {setPlans(res.plans)}
        })
      }
    } catch (e) {
      console.error('create plan failed', e)
    }
  }

  // S2: Create a sample plan (one-click onboarding)
  async function createSamplePlan() {
    try {
      const r = await post<{ ok: boolean; plan_id: string }>('/api/ariadne/plans', {
        goal: 'Sample: fetch, analyze, summarize',
        tasks: [
          { title: 'fetch-data', kind: 'note', payload: { text: 'fetching' }, depends_on: [] },
          { title: 'analyze', kind: 'note', payload: { text: 'analyzing' }, depends_on: ['fetch-data'] },
          { title: 'summarize', kind: 'note', payload: { text: 'summarizing' }, depends_on: ['analyze'] }
        ]
      })

      if (r.ok) {
        await loadPlan(r.plan_id)
        // Auto-run
        await runPlan()
      }
    } catch (e) {
      console.error('sample plan failed', e)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: '8px 12px',
          borderBottom: '1px solid var(--border, #2a2a2a)',
          alignItems: 'center'
        }}
      >
        <select
          aria-label="Select plan"
          onChange={(e) => void loadPlan(e.target.value)}
          style={{
            background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)',
            border: '1px solid var(--border, #2a2a2a)',
            borderRadius: 4,
            padding: '4px 8px',
            color: 'inherit',
            fontSize: 13,
            fontFamily: 'inherit'
          }}
          value={planId ?? ''}
        >
          <option value="">— select plan —</option>
          {plans.map((p) => (
            <option key={p.id} value={p.id}>
              {p.goal.slice(0, 60)} ({p.state})
            </option>
          ))}
        </select>
        {planId && (
          <>
            <button
              disabled={running}
              onClick={() => void runPlan()}
              style={{
                background: running ? 'color-mix(in srgb, var(--accent, #5e6ad2) 40%, transparent)' : 'var(--accent, #5e6ad2)',
                border: 'none',
                borderRadius: 4,
                padding: '4px 12px',
                color: running ? '#888' : '#fff',
                cursor: running ? 'default' : 'pointer',
                fontSize: 12,
                fontFamily: 'inherit'
              }}
            >
              {running ? 'Running…' : 'Run'}
            </button>
            <button
              onClick={() => void cancelPlan()}
              style={{
                background: 'none',
                border: '1px solid var(--accent, #f7768e)',
                borderRadius: 4,
                padding: '4px 12px',
                color: 'var(--accent, #f7768e)',
                cursor: 'pointer',
                fontSize: 12,
                fontFamily: 'inherit'
              }}
            >
              Cancel
            </button>
          </>
        )}
        <span style={{ marginLeft: 'auto', fontSize: 11, opacity: 0.5, fontVariantNumeric: 'tabular-nums' }}>
          {planState ? `state: ${planState}` : ''}
        </span>
        <button
          aria-label="Close"
          onClick={onClose}
         style={{ marginLeft: 4, background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}></button>
      </div>

      {!planId && (
        <div style={{ padding: 20, textAlign: 'center' }}>
          <p style={{ opacity: 0.6, marginBottom: 12 }}>Select a plan or create one to see the DAG board.</p>
          <button
            onClick={() => void createSamplePlan()}
            style={{
              background: 'var(--accent, #5e6ad2)',
              border: 'none',
              borderRadius: 6,
              padding: '8px 20px',
              color: '#fff',
              cursor: 'pointer',
              fontSize: 14,
              fontFamily: 'inherit'
            }}
          >
            🚀 Create & run a sample plan
          </button>
        </div>
      )}

      {/* State columns */}
      {planId && (
        <div style={{ display: 'flex', flex: 1, minHeight: 0, overflow: 'auto' }}>
          {STATE_COLUMNS.map((col) => {
            const items = grouped.get(col) ?? []

            const bgColor =
              col === 'running'
                ? 'color-mix(in srgb, var(--accent, #e0af68) 6%, transparent)'
                : col === 'failed'
                  ? 'color-mix(in srgb, var(--accent, #f7768e) 6%, transparent)'
                  : 'transparent'

            return (
              <div
                key={col}
                style={{
                  flex: 1,
                  minWidth: 120,
                  borderRight: '1px solid var(--border, #2a2a2a)',
                  background: bgColor
                }}
              >
                <div
                  style={{
                    padding: '6px 10px',
                    fontSize: 11,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                    color: 'var(--muted-foreground, #888)',
                    borderBottom: '1px solid var(--border, #2a2a2a)'
                  }}
                >
                  {STATE_LABEL[col] ?? col} {items.length > 0 && `(${items.length})`}
                </div>
                <div style={{ padding: 6 }}>
                  {items.map((task) => (
                    <button
                      key={task.id}
                      onClick={() => setSelectedId(task.id === selectedId ? null : task.id)}
                      style={{
                        display: 'block',
                        width: '100%',
                        marginBottom: 6,
                        padding: '6px 8px',
                        borderRadius: 6,
                        textAlign: 'left',
                        border: selectedId === task.id
                          ? '1.5px solid var(--accent, #5e6ad2)'
                          : '1px solid var(--border, #2a2a2a)',
                        background: '#111',
                        color: 'inherit',
                        cursor: 'pointer',
                        fontSize: 12,
                        fontFamily: 'inherit'
                      }}
                    >
                      <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {task.title}
                      </div>
                      <div style={{ fontSize: 10, opacity: 0.5, marginTop: 2 }}>
                        {task.kind} · {task.depends_on.length} deps
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Inspector */}
      {selected && (
        <div
          style={{
            borderTop: '1px solid var(--border, #2a2a2a)',
            padding: 10,
            fontSize: 12
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <strong>{selected.title}</strong>
            <code style={{ fontSize: 10, opacity: 0.5 }}>{selected.id}</code>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
              {selected.state === 'failed' && (
                <button
                  onClick={() => void retryTask(selected.id)}
                  style={{
                    background: 'none',
                    border: '1px solid var(--accent, #9ece6a)',
                    borderRadius: 4,
                    padding: '2px 8px',
                    color: 'var(--accent, #9ece6a)',
                    cursor: 'pointer',
                    fontSize: 11,
                    fontFamily: 'inherit'
                  }}
                >
                  Retry
                </button>
              )}
              <button
                onClick={() => setSelectedId(null)}
                style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 14 }}
              >
                ✕
              </button>
            </span>
          </div>
          {selected.error && (
            <pre style={{ marginTop: 6, fontSize: 11, color: 'var(--accent, #f7768e)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {selected.error}
            </pre>
          )}
        </div>
      )}

      {/* Composer (quick-add plan) + recipe save */}
            <div
              style={{
                borderTop: '1px solid var(--border, #2a2a2a)',
                padding: 10,
                display: 'flex',
                gap: 8,
                flexDirection: 'column'
              }}
            >
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  onChange={(e) => setComposerText(e.target.value)}
                  placeholder="One task per line. dep: task-id: for dependencies."
                  style={{
                    flex: 1,
                    background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)',
                    border: '1px solid var(--border, #2a2a2a)',
                    borderRadius: 4,
                    padding: '6px 10px',
                    color: 'inherit',
                    fontSize: 12,
                    fontFamily: 'inherit'
                  }}
                  value={composerText}
                />
                <button
                  onClick={() => void createPlan()}
                  style={{
                    background: 'var(--accent, #5e6ad2)',
                    border: 'none',
                    borderRadius: 4,
                    padding: '6px 14px',
                    color: '#fff',
                    cursor: 'pointer',
                    fontSize: 12,
                    fontFamily: 'inherit'
                  }}
                >
                  Create Plan
                </button>
              </div>
              {/* S4: recipe save row */}
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  onChange={(e) => setRecipeName(e.target.value)}
                  placeholder="Recipe name…"
                  style={{
                    flex: 1,
                    background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)',
                    border: '1px solid var(--border, #2a2a2a)',
                    borderRadius: 4,
                    padding: '4px 8px',
                    color: 'inherit',
                    fontSize: 11,
                    fontFamily: 'inherit'
                  }}
                  value={recipeName}
                />
                <button
                  onClick={saveAsRecipe}
                  style={{
                    background: 'none',
                    border: '1px solid var(--border, #2a2a2a)',
                    borderRadius: 4,
                    padding: '4px 10px',
                    color: 'inherit',
                    cursor: 'pointer',
                    fontSize: 11,
                    fontFamily: 'inherit'
                  }}
                >
                  Save as recipe
                </button>
              </div>
              {/* S4: recipe list */}
              {recipes.length > 0 && (
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {recipes.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => startRecipe(r)}
                      style={{
                        background: 'color-mix(in srgb, var(--foreground, #efefef) 4%, transparent)',
                        border: '1px solid var(--border, #2a2a2a)',
                        borderRadius: 999,
                        padding: '2px 10px',
                        color: 'inherit',
                        cursor: 'pointer',
                        fontSize: 11,
                        fontFamily: 'inherit'
                      }}
                      title={r.goal}
                    >
                      {r.name}
                    </button>
                  ))}
                </div>
              )}
              {/* S4 slot-fill dialog */}
              {showSlots && activeRecipe && (
                <div
                  style={{
                    border: '1px solid var(--accent, #e0af68)',
                    borderRadius: 8,
                    padding: 10,
                    background: 'color-mix(in srgb, var(--accent, #e0af68) 6%, transparent)'
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6 }}>
                    Fill recipe slots for "{activeRecipe.name}"
                  </div>
                  {Object.keys(slotValues).map((slot) => (
                    <label
                      key={slot}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginBottom: 4,
                        fontSize: 12
                      }}
                    >
                      <code style={{ minWidth: 80 }}>{slot}</code>
                      <input
                        onChange={(e) =>
                          setSlotValues((prev) => ({ ...prev, [slot]: e.target.value }))
                        }
                        placeholder={`value for ${slot}`}
                        style={{
                          flex: 1,
                          background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)',
                          border: '1px solid var(--border, #2a2a2a)',
                          borderRadius: 4,
                          padding: '4px 8px',
                          color: 'inherit',
                          fontSize: 12,
                          fontFamily: 'inherit'
                        }}
                        value={slotValues[slot]}
                      />
                    </label>
                  ))}
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    <button
                      onClick={confirmSlots}
                      style={{
                        background: 'var(--accent, #5e6ad2)',
                        border: 'none',
                        borderRadius: 4,
                        padding: '4px 12px',
                        color: '#fff',
                        cursor: 'pointer',
                        fontSize: 11,
                        fontFamily: 'inherit'
                      }}
                    >
                      Load
                    </button>
                    <button
                      onClick={() => {
                        setShowSlots(false)
                        setActiveRecipe(null)
                      }}
                      style={{
                        background: 'none',
                        border: '1px solid var(--border, #2a2a2a)',
                        borderRadius: 4,
                        padding: '4px 12px',
                        color: 'inherit',
                        cursor: 'pointer',
                        fontSize: 11,
                        fontFamily: 'inherit'
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
    </div>
  )
}