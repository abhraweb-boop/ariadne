/**
 * Settings pane — per-surface model routing (S6), gateway base, layout reset.
 */

import { useEffect, useState } from 'react'

import { gatewayBase } from '../api'

const MODEL_KEY = 'prime-hermes-models'

export function Settings({ onClose }: { onClose: () => void }) {
  const [models, setModels] = useState<{ chat: string; dag: string; prime: string }>({
    chat: 'openai/gpt-4o-mini',
    dag: 'openai/gpt-4o-mini',
    prime: ''
  })

  const [base, setBase] = useState('…')

  useEffect(() => {
    void gatewayBase().then(setBase)

    try {
      const saved = localStorage.getItem(MODEL_KEY)

      if (saved) {setModels(JSON.parse(saved))}
    } catch {
      /* ignore */
    }
  }, [])

  function save(next: typeof models) {
    setModels(next)
    localStorage.setItem(MODEL_KEY, JSON.stringify(next))
  }

  function resetLayout() {
    localStorage.removeItem('prime-hermes-layout')
    localStorage.removeItem(MODEL_KEY)
    window.location.reload()
  }

  return (
    <div style={{ padding: 14, fontSize: 13 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>⚙ Settings</span>
        <button onClick={onClose} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}>✕</button>
      </div>

      <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>Gateway base URL</div>
      <code style={{ display: 'block', fontSize: 12, padding: '6px 10px', border: '1px solid var(--border, #2a2a2a)', borderRadius: 4, marginBottom: 16 }}>{base}</code>

      <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>
        Per-surface model routing (S6) — stored locally
      </div>
      {(['chat', 'dag', 'prime'] as const).map((surface) => (
        <label key={surface} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <span style={{ width: 64, textTransform: 'capitalize' }}>{surface}</span>
          <input
            onChange={(e) => save({ ...models, [surface]: e.target.value })}
            placeholder={surface === 'prime' ? '(inherit from env PRIME_AGENT_MODEL)' : 'model id'}
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
            value={models[surface]}
          />
        </label>
      ))}

      <div style={{ borderTop: '1px solid var(--border, #2a2a2a)', marginTop: 16, paddingTop: 12 }}>
        <button
          onClick={resetLayout}
          style={{
            background: 'none',
            border: '1px solid #f7768e',
            borderRadius: 4,
            padding: '6px 14px',
            color: '#f7768e',
            cursor: 'pointer',
            fontSize: 12,
            fontFamily: 'inherit'
          }}
        >
          Reset layout & models
        </button>
      </div>
    </div>
  )
}