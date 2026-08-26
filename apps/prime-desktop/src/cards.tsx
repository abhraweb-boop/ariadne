/**
 * Prime Hermes — capability-aware chat cards (M2/M3).
 *
 * Rich, point-and-click cards rendered inline in the transcript — never raw
 * stream text. Each card has real affordances (badges, buttons, expand).
 */

import { useState } from 'react'

export interface TaskInfo {
  id: string
  title: string
  kind: string
  state: string
  depends_on: string[]
  payload?: Record<string, unknown>
  result?: unknown
}

const TASK_STATE_META: Record<string, { label: string; color: string }> = {
  pending: { label: 'Pending', color: '#8a8f98' },
  ready: { label: 'Ready', color: '#8a8f98' },
  running: { label: 'Running', color: '#e0af68' },
  done: { label: 'Done', color: '#9ece6a' },
  failed: { label: 'Failed', color: '#f7768e' },
  skipped: { label: 'Skipped', color: '#565f89' },
  bypassed: { label: 'Bypassed', color: '#565f89' }
}

/** Live task card — shown in chat when a plan runs (M3). */
export function TaskCard({
  task,
  onOpenBoard
}: {
  task: TaskInfo
  onOpenBoard?: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  const meta = TASK_STATE_META[task.state] ?? TASK_STATE_META.pending

  return (
    <div
      style={{
        border: '1px solid var(--border, #2a2a2a)',
        borderRadius: 8,
        padding: 10,
        background: 'color-mix(in srgb, var(--foreground, #efefef) 4%, transparent)'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span
          aria-label={meta.label}
          role="img"
          style={{
            width: 10,
            height: 10,
            borderRadius: '50%',
            background: meta.color,
            flexShrink: 0
          }}
        />
        <span style={{ fontWeight: 600, fontSize: 13 }}>{task.title || task.id}</span>
        <span
          style={{
            marginLeft: 'auto',
            fontSize: 11,
            color: meta.color,
            border: `1px solid ${meta.color}`,
            borderRadius: 999,
            padding: '1px 8px'
          }}
        >
          {meta.label}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
        <span style={{ fontSize: 11, opacity: 0.6 }}>
          {task.kind} · deps: {task.depends_on.length}
        </span>
        {onOpenBoard && (
          <button
            onClick={onOpenBoard}
            style={{
              marginLeft: 'auto',
              background: 'none',
              border: '1px solid var(--border, #2a2a2a)',
              borderRadius: 4,
              color: 'inherit',
              fontSize: 11,
              padding: '2px 8px',
              cursor: 'pointer',
              fontFamily: 'inherit'
            }}
          >
            Open board →
          </button>
        )}
        {(task.result !== undefined || expanded) && (
          <button
            onClick={() => setExpanded((v) => !v)}
            style={{
              background: 'none',
              border: 'none',
              color: 'inherit',
              fontSize: 11,
              cursor: 'pointer',
              fontFamily: 'inherit',
              opacity: 0.7
            }}
          >
            {expanded ? 'collapse' : 'result'}
          </button>
        )}
      </div>
      {expanded && (
        <pre
          style={{
            marginTop: 8,
            maxHeight: 180,
            overflow: 'auto',
            fontSize: 11,
            padding: 8,
            borderRadius: 4,
            background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word'
          }}
        >
          {typeof task.result === 'string'
            ? task.result
            : JSON.stringify(task.result ?? {}, null, 2)}
        </pre>
      )}
    </div>
  )
}

/** Kernel cell card — rich stdout, not a terminal (UX constraint 2). */
export function KernelCellCard({ code, output }: { code: string; output?: string }) {
  const [open, setOpen] = useState(false)

  return (
    <div
      style={{
        border: '1px solid var(--border, #2a2a2a)',
        borderRadius: 8,
        overflow: 'hidden'
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '6px 10px',
          background: 'color-mix(in srgb, var(--foreground, #efefef) 4%, transparent)'
        }}
      >
        <span aria-hidden style={{ fontSize: 11 }}>▶</span>
        <code style={{ fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {code}
        </code>
        <button
          onClick={() => setOpen((v) => !v)}
          style={{
            marginLeft: 'auto',
            background: 'none',
            border: 'none',
            color: 'inherit',
            cursor: 'pointer',
            fontSize: 11,
            opacity: 0.7,
            fontFamily: 'inherit'
          }}
        >
          {open ? 'hide output' : output ? `output (${output.length} ch)` : 'no output'}
        </button>
      </div>
      {open && output && (
        <pre
          style={{
            margin: 0,
            padding: 10,
            fontSize: 12,
            maxHeight: 220,
            overflow: 'auto',
            borderTop: '1px solid var(--border, #2a2a2a)',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word'
          }}
        >
          {output}
        </pre>
      )}
    </div>
  )
}

/** Tool call card — name, status, duration. */
export function ToolCallCard({
  name,
  status,
  durationMs
}: {
  name: string
  status: 'ok' | 'running' | 'failed'
  durationMs?: number
}) {
  const color = status === 'ok' ? '#9ece6a' : status === 'failed' ? '#f7768e' : '#e0af68'

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        border: '1px solid var(--border, #2a2a2a)',
        borderRadius: 8,
        padding: '6px 10px',
        fontSize: 12
      }}
    >
      <span style={{ color, fontWeight: 600 }}>⚙</span>
      <span style={{ fontWeight: 500 }}>{name}</span>
      {durationMs !== undefined && (
        <span style={{ marginLeft: 'auto', opacity: 0.6, fontVariantNumeric: 'tabular-nums' }}>
          {durationMs}ms
        </span>
      )}
      <span
        style={{
          color,
          border: `1px solid ${color}`,
          borderRadius: 999,
          padding: '0 8px',
          fontSize: 10
        }}
      >
        {status}
      </span>
    </div>
  )
}
