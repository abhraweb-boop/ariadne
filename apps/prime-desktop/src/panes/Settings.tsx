/**
 * Settings pane — per-surface model routing (S6), gateway base, layout reset.
 */

import { useCallback, useEffect, useState } from 'react'

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
  // P2: embedded gateway state
  const [gatewayStatus, setGatewayStatus] = useState<'healthy' | 'connecting' | 'offline'>('connecting')
  const [restarting, setRestarting] = useState(false)
  // P4: update state
  const [checkingUpdate, setCheckingUpdate] = useState(false)
  const [downloadingUpdate, setDownloadingUpdate] = useState(false)
  const [updateMsg, setUpdateMsg] = useState<string | null>(null)
  const [updateAvailable, setUpdateAvailable] = useState(false)
  const [updateVersion, setUpdateVersion] = useState('')

  const checkUpdate = useCallback(async () => {
    if (!window.primeHermes?.updateCheck) {
      setUpdateMsg('Updates available in the packaged app.')

      return
    }

    setCheckingUpdate(true)
    setUpdateMsg(null)

    try {
      const r = await window.primeHermes.updateCheck()

      if (r.available) {
        setUpdateAvailable(true)
        setUpdateVersion(r.version)
        setUpdateMsg(`Update v${r.version} available.`)
      } else if (r.error) {
        setUpdateMsg(`Failed: ${r.error}`)
      } else {
        setUpdateMsg('You’re on the latest version.')
      }
    } catch (e) {
      setUpdateMsg(`Failed: ${String(e)}`)
    } finally {
      setCheckingUpdate(false)
    }
  }, [])

  const downloadUpdate = useCallback(async () => {
    if (!window.primeHermes?.updateDownload) {return}
    setDownloadingUpdate(true)
    setUpdateMsg('Downloading…')

    try {
      const r = await window.primeHermes.updateDownload()
      setUpdateMsg(r.ok ? 'Downloaded — ready to install.' : `Failed: ${r.error ?? ''}`)
    } finally {
      setDownloadingUpdate(false)
    }
  }, [])

  const installUpdate = useCallback(() => {
    void window.primeHermes?.updateInstall?.()
  }, [])

  const checkGateway = useCallback(async () => {
    if (!window.primeHermes?.gatewayStatus) {
      setGatewayStatus('healthy') // browser dev fallback: assume reachable

      return
    }

    try {
      const st = await window.primeHermes.gatewayStatus()
      setGatewayStatus(st.healthy ? 'healthy' : 'offline')
    } catch {
      setGatewayStatus('offline')
    }
  }, [])

  const restartGateway = useCallback(async () => {
    if (!window.primeHermes?.gatewayRestart) {return}
    setRestarting(true)
    setGatewayStatus('connecting')

    try {
      await window.primeHermes.gatewayRestart()
      // give it a moment, then re-probe
      await new Promise((r) => setTimeout(r, 1500))
      await checkGateway()
    } finally {
      setRestarting(false)
    }
  }, [checkGateway])

  useEffect(() => {
    void gatewayBase().then(setBase)
    void checkGateway()
    const poll = setInterval(() => void checkGateway(), 15_000)

    return () => clearInterval(poll)

    try {
      const saved = localStorage.getItem(MODEL_KEY)

      if (saved) {setModels(JSON.parse(saved!) as typeof models)}
    } catch {
      /* ignore */
    }
  }, [checkGateway])

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
        <button aria-label="Close" onClick={onClose} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}></button>
      </div>

      <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>Gateway base URL</div>
      <code style={{ display: 'block', fontSize: 12, padding: '6px 10px', border: '1px solid var(--border, #2a2a2a)', borderRadius: 4, marginBottom: 16 }}>{base}</code>

      {/* P2: Embedded gateway status */}
      <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>
        Embedded gateway (P2)
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span
          aria-label={gatewayStatus === 'healthy' ? 'Gateway healthy' : gatewayStatus === 'connecting' ? 'Gateway connecting' : 'Gateway offline'}
          style={{
            width: 8,
            height: 8,
            borderRadius: 4,
            background:
              gatewayStatus === 'healthy' ? '#9ece6a'
                : gatewayStatus === 'connecting' ? '#e0af68' : '#f7768e'
          }}
        />
        <span style={{ fontSize: 12 }}>
          {gatewayStatus === 'healthy' ? 'Running' : gatewayStatus === 'connecting' ? 'Connecting…' : 'Offline'}
        </span>
        {gatewayStatus === 'offline' && (
          <button
            disabled={restarting}
            onClick={restartGateway}
            style={ghostBtn}
          >
            {restarting ? 'Restarting…' : 'Restart gateway'}
          </button>
        )}
        {gatewayStatus !== 'offline' && (
          <button onClick={() => void checkGateway()} style={ghostBtn}>↻ check</button>
        )}
      </div>

      {/* P4: Auto-update */}
      <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 6 }}>
        Updates (P4) — GitHub Releases channel
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <button disabled={checkingUpdate} onClick={() => void checkUpdate()} style={ghostBtn}>
          {checkingUpdate ? 'Checking…' : 'Check for updates'}
        </button>
        {updateMsg && (
          <span style={{ fontSize: 11, color: updateMsg.startsWith('Failed') ? '#f7768e' : 'var(--muted-foreground, #888)' }}>
            {updateMsg}
          </span>
        )}
        {updateAvailable && (
          <>
            <button disabled={downloadingUpdate} onClick={() => void downloadUpdate()} style={ghostBtn}>
              {downloadingUpdate ? 'Downloading…' : 'Download v' + updateVersion}
            </button>
            <button onClick={() => void installUpdate()} style={ghostBtn}>Install & restart</button>
          </>
        )}
      </div>

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