/**
 * F2 — First-run onboarding (port of Hermes desktop onboarding).
 *
 * Step-by-step overlay shown once (localStorage flag). Step 4 hands off
 * with Ctrl+K hint; "Start using Prime" completes.
 */

import { useCallback, useEffect, useState } from 'react'

const DONE_KEY = 'prime-hermes:onboarding-done'

const STEPS = [
  { title: 'Welcome', body: 'Welcome to Prime Hermes. Your AI harness.' },
  { title: 'Chat', body: 'Send messages to the Prime worker. Type code, ask questions, run plans.' },
  { title: 'Capabilities', body: 'Manage kernels, DAG plans, agents, and memory from the panel rail.' },
  { title: 'Get started', body: 'Type a message to begin, or press Ctrl+K to explore.' }
]

export function Onboarding({ onClose }: { onClose: () => void }) {
  const [visible, setVisible] = useState(false)
  const [step, setStep] = useState(0)

  useEffect(() => {
    let done = false
    try { done = localStorage.getItem(DONE_KEY) === '1' } catch { /* ignore */ }
    setVisible(!done)
  }, [])

  const finish = useCallback(() => {
    try { localStorage.setItem(DONE_KEY, '1') } catch { /* ignore */ }
    setVisible(false)
    onClose()
  }, [onClose])

  if (!visible) {return null}

  const s = STEPS[step]
  const last = step === STEPS.length - 1

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 400,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.6)'
      }}
      role="dialog"
      aria-label="Welcome to Prime Hermes"
    >
      <div
        style={{
          width: 420,
          background: 'var(--background, #101012)',
          border: '1px solid var(--border, #2a2a2a)',
          borderRadius: 12,
          padding: 24,
          color: 'var(--foreground, #efefef)'
        }}
      >
        <div style={{ fontSize: 11, color: 'var(--muted-foreground, #888)', marginBottom: 8 }}>
          Step {step + 1}/{STEPS.length}
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 10 }}>{s.title}</div>
        <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--muted-foreground, #888)', marginBottom: 20 }}>
          {s.body}
        </div>

        {/* Progress dots */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 20 }}>
          {STEPS.map((_, i) => (
            <span
              key={i}
              style={{
                width: 24,
                height: 4,
                borderRadius: 2,
                background: i <= step ? 'var(--accent, #5e6ad2)' : 'var(--border, #2a2a2a)'
              }}
            />
          ))}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            style={{
              background: 'transparent',
              border: '1px solid var(--border, #2a2a2a)',
              borderRadius: 6,
              padding: '8px 16px',
              color: 'var(--foreground, #efefef)',
              cursor: step === 0 ? 'default' : 'pointer',
              fontSize: 13,
              fontFamily: 'inherit'
            }}
          >
            Back
          </button>
          {last ? (
            <button
              onClick={finish}
              style={{
                background: 'var(--accent, #5e6ad2)',
                border: 'none',
                borderRadius: 6,
                padding: '8px 18px',
                color: '#fff',
                cursor: 'pointer',
                fontSize: 13,
                fontFamily: 'inherit'
              }}
            >
              Start using Prime
            </button>
          ) : (
            <button
              onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
              style={{
                background: 'var(--accent, #5e6ad2)',
                border: 'none',
                borderRadius: 6,
                padding: '8px 18px',
                color: '#fff',
                cursor: 'pointer',
                fontSize: 13,
                fontFamily: 'inherit'
              }}
            >
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
