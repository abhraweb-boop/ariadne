/**
 * Kernel Console (notebook, not REPL — UX constraint 2).
 * Execute cells, browse variables, see history.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { get, post } from '../api'

export function KernelConsole({ onClose }: { onClose: () => void }) {
  const [cells, setCells] = useState<Array<{ code: string; output?: string; status: string }>>([])
  const [input, setInput] = useState('')
  const [running, setRunning] = useState(false)
  const [status, setStatus] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const [primeRunning, setPrimeRunning] = useState(false)

  const loadPrimeState = useCallback(async () => {
    try {
      const r = await get<{ ok?: boolean; running?: boolean }>('/api/ariadne/prime/state')
      setPrimeRunning(!!r.running)
    } catch {
      /* bridge unavailable — stay in stopped state */
    }
  }, [])

  useEffect(() => {
    void loadPrimeState()
    const interval = setInterval(() => void loadPrimeState(), 30000)

    return () => clearInterval(interval)
  }, [loadPrimeState])

  useEffect(() => { void getStatus() }, [])
  useEffect(() => { endRef.current?.scrollIntoView() }, [cells])

  async function getStatus() {
    try {
      const r = await get<{ ok: boolean; running: boolean }>('/api/ariadne/kernel/status')
      setStatus(r.ok ? (r.running ? 'running' : 'idle') : 'error')
    } catch { setStatus('offline') }
  }

  async function startKernel() {
    await post('/api/ariadne/kernel/start', {})
    await getStatus()
  }

  async function runCell() {
    if (!input.trim()) {return}
    const code = input.trim()
    setInput('')
    setCells((prev) => [...prev, { code, status: 'running' }])
    setRunning(true)

    try {
      const r = await post<{ ok: boolean; output: string; status: string }>('/api/ariadne/kernel/execute', { code, timeout_s: 60 })
      setCells((prev) => {
        const next = [...prev]
        next[next.length - 1] = { code, output: r.output ?? '', status: r.ok ? 'ok' : 'error' }

        return next
      })
    } catch (e) {
      setCells((prev) => {
        const next = [...prev]
        next[next.length - 1] = { code, output: String(e), status: 'error' }

        return next
      })
    } finally { setRunning(false) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>⚡ Kernel Console</span>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: primeRunning ? '#9ece6a' : 'var(--muted-foreground, #888)' }} />
          <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)' }}>{primeRunning ? 'prime live' : 'prime stopped'}</span>
        </span>
        <span style={{ fontSize: 11, color: status === 'running' ? 'var(--accent, #9ece6a)' : 'var(--muted-foreground, #888)', fontVariantNumeric: 'tabular-nums' }}>
          {status === 'offline' ? (
            <button onClick={startKernel} style={{ background: 'none', border: '1px solid var(--accent)', borderRadius: 4, padding: '2px 8px', color: 'inherit', cursor: 'pointer', fontFamily: 'inherit' }}>Start kernel</button>
          ) : `kernel ${status}`}
        </span>
        <button aria-label="Close" onClick={onClose} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 16 }}></button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 10 }}>
        {cells.map((c, i) => (
          <div key={i} style={{ marginBottom: 10, border: '1px solid var(--border, #2a2a2a)', borderRadius: 8, overflow: 'hidden' }}>
            <div style={{ padding: '6px 10px', background: 'color-mix(in srgb, var(--foreground, #efefef) 4%, transparent)', fontSize: 12, fontFamily: 'monospace' }}>{c.code}</div>
            {c.output !== undefined && c.status !== 'running' && (
              <pre style={{ margin: 0, padding: 10, fontSize: 12, borderTop: '1px solid var(--border, #2a2a2a)', maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{c.output || '(no output)'}</pre>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div style={{ display: 'flex', gap: 8, padding: 10, borderTop: '1px solid var(--border, #2a2a2a)' }}>
        <input disabled={running} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runCell() } }} placeholder="Python code…" style={{ flex: 1, background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)', border: '1px solid var(--border, #2a2a2a)', borderRadius: 4, padding: '6px 10px', color: 'inherit', fontSize: 12, fontFamily: 'monospace' }} value={input} />
        <button disabled={running} onClick={runCell} style={{ background: running ? '#555' : 'var(--accent, #5e6ad2)', border: 'none', borderRadius: 4, padding: '6px 14px', color: '#fff', cursor: running ? 'default' : 'pointer', fontSize: 12, fontFamily: 'inherit' }}>{running ? 'Running…' : 'Run'}</button>
      </div>
    </div>
  )
}