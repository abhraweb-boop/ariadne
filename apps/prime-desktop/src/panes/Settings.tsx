/**
 * Settings pane — per-surface model routing (S6), gateway base, layout reset.
 */

import { useEffect, useState } from 'react'

import { gatewayBase } from '../api'
import { type Accent, ACCENTS, applyTheme, loadPrefs, savePrefs, THEME_STORAGE_KEY, type ThemeMode, type ThemePrefs } from '../themes'

const MODEL_KEY = 'prime-hermes-models'

export function Settings({ onClose }: { onClose: () => void }) {
  const [models, setModels] = useState<{ chat: string; dag: string; prime: string }>({
    chat: 'openai/gpt-4o-mini',
    dag: 'openai/gpt-4o-mini',
    prime: ''
  })

  const [base, setBase] = useState('…')
  // E1: appearance state
  const [prefs, setPrefs] = useState<ThemePrefs>(loadPrefs())

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

  function updateTheme(partial: Partial<ThemePrefs>) {
    const next = { ...prefs, ...partial }
    setPrefs(next)
    savePrefs(next)
    applyTheme(next)
  }

  function resetLayout() {
    localStorage.removeItem('prime-hermes-layout')
    localStorage.removeItem(MODEL_KEY)
    localStorage.removeItem(THEME_STORAGE_KEY)
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

      {/* E1: Appearance */}
      <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>
        Appearance (E1)
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ width: 64 }}>Theme</span>
        {(['dark', 'light'] as ThemeMode[]).map((mode) => (
          <label key={mode} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
            <input
              checked={prefs.mode === mode}
              name="theme-mode"
              onChange={() => updateTheme({ mode })}
              type="radio"
            />
            <span style={{ textTransform: 'capitalize' }}>{mode}</span>
          </label>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ width: 64 }}>Accent</span>
        <div style={{ display: 'flex', gap: 6 }}>
          {(Object.keys(ACCENTS) as Accent[]).map((accent) => (
            <button
              aria-label={`Accent ${accent}`}
              key={accent}
              onClick={() => updateTheme({ accent })}
              style={{
                width: 18,
                height: 18,
                borderRadius: 9,
                border: prefs.accent === accent ? '2px solid var(--foreground, #efefef)' : '1px solid var(--border, #2a2a2a)',
                background: ACCENTS[accent],
                cursor: 'pointer',
                padding: 0
              }}
              title={accent}
            />
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span style={{ width: 64 }}>Font size</span>
        <input
          max={1.15}
          min={0.9}
          onChange={(e) => updateTheme({ fontScale: Number(e.target.value) })}
          step={0.05}
          style={{ flex: 1 }}
          type="range"
          value={prefs.fontScale}
        />
        <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', fontVariantNumeric: 'tabular-nums', minWidth: 40 }}>
          {Math.round(prefs.fontScale * 100)}%
        </span>
      </div>

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