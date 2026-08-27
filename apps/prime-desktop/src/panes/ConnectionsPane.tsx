/**
 * C5 — Connections pane: gateway status + restart.
 */

import { useCallback, useEffect, useState } from 'react'

export function ConnectionsPane({ onClose }: { onClose: () => void }) {
  const [status, setStatus] = useState<'healthy' | 'offline' | 'unknown'>('unknown')
  const [base, setBase] = useState('')
  const [restarting, setRestarting] = useState(false)

  const probe = useCallback(async () => {
    if (!window.primeHermes?.gatewayStatus) {
      setStatus('healthy')

      return
    }

    try {
      const st = await window.primeHermes.gatewayStatus()
      setBase(st.base)
      setStatus(st.healthy ? 'healthy' : 'offline')
    } catch {
      setStatus('offline')
    }
  }, [])

  useEffect(() => { void probe() }, [probe])

  const restart = useCallback(async () => {
    if (!window.primeHermes?.gatewayRestart) {return}
    setRestarting(true)
    setStatus('unknown')

    try {
      await window.primeHermes.gatewayRestart()
      await new Promise((r) => setTimeout(r, 1500))
      await probe()
    } finally {
      setRestarting(false)
    }
  }, [probe])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>🔌 Connections</span>
        <button onClick={() => void probe()} style={ghostBtn}>↻</button>
        <button aria-label="Close" onClick={onClose} style={ghostBtn}>✕</button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, padding: '8px 10px', border: '1px solid var(--border, #2a2a2a)', borderRadius: 6, marginBottom: 10 }}>
        <span style={{ width: 8, height: 8, borderRadius: 4, background: status === 'healthy' ? '#9ece6a' : status === 'offline' ? '#f7768e' : '#e0af68' }} />
        <span>{status === 'healthy' ? 'Gateway connected' : status === 'offline' ? 'Gateway offline' : 'Checking…'}</span>
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--muted-foreground, #888)' }}>{base}</span>
      </div>

      {status === 'offline' && (
        <button disabled={restarting} onClick={() => void restart()} style={{ ...ghostBtn, alignSelf: 'flex-start' }}>
          {restarting ? 'Restarting…' : 'Restart gateway'}
        </button>
      )}

      <div style={{ marginTop: 16, fontSize: 11, color: 'var(--muted-foreground, #888)', lineHeight: 1.6 }}>
        <strong>Platforms</strong> (connected via gateway):<br />
        • Telegram, Discord, Slack, WhatsApp, Signal, SMS, and ~20 more — live when the gateway is configured.<br />
        • Manage channels and platforms from the Settings tab.
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