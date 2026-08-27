/**
 * C2 — CronPane: jobs list, create form, pause/resume/delete.
 */

import { useCallback, useEffect, useState } from 'react'

import { del, get, post } from '../api'

interface CronJob {
  job_id?: string
  name?: string
  schedule?: string
  paused?: boolean
  enabled?: boolean
  prompt?: string
}

export function CronPane({ onClose }: { onClose: () => void }) {
  const [jobs, setJobs] = useState<CronJob[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [schedule, setSchedule] = useState('0 9 * * *')
  const [prompt, setPrompt] = useState('')
  const [formMsg, setFormMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const r = await get<{ ok?: boolean; jobs?: CronJob[] } | CronJob[]>('/api/cron/jobs')
      const list = Array.isArray(r) ? r : (r as any).jobs ?? []
      setJobs(list)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const create = useCallback(async () => {
    if (!name.trim() || !schedule.trim()) {return}
    setFormMsg('Creating…')

    try {
      await post('/api/cron/jobs', { name: name.trim(), schedule: schedule.trim(), prompt: prompt.trim() })
      setFormMsg('Job created.')
      setShowForm(false)
      setName(''); setSchedule('0 9 * * *'); setPrompt('')
      void load()
    } catch (e) {
      setFormMsg(`Failed: ${String(e)}`)
    }
  }, [name, schedule, prompt, load])

  const togglePause = useCallback(async (job: CronJob, pause: boolean) => {
    const id = job.job_id ?? ''
    const prev = jobs
    setJobs((cur) => cur.map((j) => (j.job_id === id ? { ...j, paused: pause } : j)))

    try {
      await post(`/api/cron/jobs/${id}/${pause ? 'pause' : 'resume'}`, {})
    } catch {
      setJobs(prev)
    }
  }, [jobs])

  const remove = useCallback(async (id: string) => {
    const prev = jobs
    setJobs((cur) => cur.filter((j) => j.job_id !== id))

    try {
      await del(`/api/cron/jobs/${id}`)
    } catch {
      setJobs(prev)
    }
  }, [jobs])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)' }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>⏰ Cron</span>
        <button onClick={() => void load()} style={ghostBtn}>↻</button>
        <button onClick={() => { setShowForm(!showForm); setFormMsg(null) }} style={{ ...ghostBtn, marginLeft: 'auto' }}>+ New job</button>
        <button aria-label="Close" onClick={onClose} style={ghostBtn}>✕</button>
      </div>

      {showForm && (
        <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <input onChange={(e) => setName(e.target.value)} placeholder="Job name" style={inputStyle} value={name} />
          <input onChange={(e) => setSchedule(e.target.value)} placeholder="Schedule (cron), e.g. 0 9 * * *" style={inputStyle} value={schedule} />
          <textarea onChange={(e) => setPrompt(e.target.value)} placeholder="Prompt the agent runs" rows={3} style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }} value={prompt} />
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button disabled={!name.trim() || !schedule.trim()} onClick={() => void create()} style={{ ...ghostBtn, opacity: name.trim() && schedule.trim() ? 1 : 0.5 }}>Create</button>
            <button onClick={() => { setShowForm(false); setFormMsg(null) }} style={ghostBtn}>Cancel</button>
            {formMsg && <span style={{ fontSize: 11, color: 'var(--muted-foreground, #888)' }}>{formMsg}</span>}
          </div>
        </div>
      )}

      <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
        {loading && <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>Loading…</div>}
        {error && (
          <div style={{ padding: 16, fontSize: 12, color: '#f7768e' }}>
            {error} <button onClick={() => void load()} style={ghostBtn}>Retry</button>
          </div>
        )}
        {!loading && !error && jobs.length === 0 && (
          <div style={{ padding: 16, fontSize: 12, color: 'var(--muted-foreground, #888)' }}>No cron jobs. Create one to schedule recurring work.</div>
        )}
        {jobs.map((j) => (
          <div key={j.job_id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderBottom: '1px solid var(--border, #2a2a2a)', fontSize: 12 }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: j.paused ? '#e0af68' : '#9ece6a' }} />
            <span style={{ fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{j.name ?? j.job_id}</span>
            <code style={{ fontSize: 10, color: 'var(--muted-foreground, #888)' }}>{j.schedule}</code>
            <button onClick={() => void togglePause(j, !j.paused)} style={ghostBtn}>{j.paused ? 'Resume' : 'Pause'}</button>
            <button onClick={() => void remove(j.job_id ?? '')} style={{ ...ghostBtn, color: '#f7768e' }}>Delete</button>
          </div>
        ))}
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

const inputStyle: React.CSSProperties = {
  padding: '4px 8px',
  background: 'transparent',
  border: '1px solid var(--border, #2a2a2a)',
  borderRadius: 4,
  color: 'inherit',
  fontSize: 12,
  fontFamily: 'inherit'
}