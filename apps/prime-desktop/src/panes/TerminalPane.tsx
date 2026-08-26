/**
 * D2 — Terminal pane (degraded port of Hermes desktop Terminal sidebar).
 *
 * The full PTY surface is gated behind the dashboard embedded-chat flag and
 * needs xterm.js + WS auth plumbing (plan risk rule: degrade rather than
 * block). This pane offers the existing profile open-terminal endpoint:
 * one click opens a real system terminal in the workspace.
 */

import { useState } from 'react'

import { post } from '../api'

export function TerminalPane({ onClose }: { onClose: () => void }) {
  const [opening, setOpening] = useState(false)
  const [result, setResult] = useState<string | null>(null)

  const openTerminal = async () => {
    setOpening(true)
    setResult(null)

    try {
      const r = await post<{ ok?: boolean; detail?: string }>('/api/profiles/default/open-terminal', {})
      setResult(r.ok === false ? `Failed: ${r.detail ?? 'unknown'}` : 'System terminal opened.')
    } catch (e) {
      setResult(`Failed: ${String(e)}`)
    } finally {
      setOpening(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>🖥 Terminal</span>
        <button onClick={onClose} style={ghostBtn}>✕</button>
      </div>

      <div
        style={{
          border: '1px solid var(--border, #2a2a2a)',
          borderRadius: 8,
          padding: 18,
          textAlign: 'center'
        }}
      >
        <div style={{ fontSize: 24, marginBottom: 8 }}>🖥️</div>
        <div style={{ fontSize: 13, marginBottom: 6 }}>
          Open a real terminal in the workspace
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 12, lineHeight: 1.5 }}>
          Prime Hermes keeps terminals as native windows — no embedded REPL.
          The kernel console covers in-app Python.
        </div>
        <button
          disabled={opening}
          onClick={() => void openTerminal()}
          style={{
            background: 'var(--accent, #5e6ad2)',
            border: 'none',
            borderRadius: 6,
            padding: '8px 18px',
            color: '#fff',
            cursor: opening ? 'default' : 'pointer',
            fontSize: 13,
            fontFamily: 'inherit'
          }}
        >
          {opening ? 'Opening…' : 'Open system terminal'}
        </button>
        {result && (
          <div style={{ marginTop: 10, fontSize: 11, color: result.startsWith('Failed') ? '#f7768e' : '#9ece6a' }}>
            {result}
          </div>
        )}
      </div>
    </div>
  )
}

const ghostBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--border, #2a2a2a)',
  borderRadius: 4,
  color: 'var(--foreground, #efefef)',
  cursor: 'pointer',
  fontSize: 11,
  fontFamily: 'inherit',
  padding: '2px 6px'
}
