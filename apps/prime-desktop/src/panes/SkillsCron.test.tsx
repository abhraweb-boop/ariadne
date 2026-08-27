/**
 * C1+C2 — SkillsHub + CronPane tests.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { CronPane } from './CronPane'
import { SkillsHub } from './SkillsHub'

const fetchMock = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function jsonOk(body: unknown) {
  return { ok: true, json: async () => body } as Response
}

describe('SkillsHub', () => {
  it('lists installed skills', async () => {
    fetchMock.mockResolvedValue(jsonOk([
      { name: 'obsidian', description: 'Notes', enabled: true, provenance: 'hub' }
    ]))
    render(<SkillsHub onClose={() => {}} />)
    expect(await screen.findByText('obsidian')).toBeTruthy()
  })

  it('filters by search', async () => {
    fetchMock.mockResolvedValue(jsonOk([
      { name: 'obsidian', description: 'Notes', enabled: true },
      { name: 'arxiv', description: 'Papers', enabled: true }
    ]))
    render(<SkillsHub onClose={() => {}} />)
    await screen.findByText('obsidian')
    fireEvent.change(screen.getByPlaceholderText('Search installed skills…'), { target: { value: 'arxiv' } })
    expect(screen.queryByText('obsidian')).toBeNull()
    expect(screen.getByText('arxiv')).toBeTruthy()
  })

  it('shows error with retry', async () => {
    fetchMock.mockRejectedValue(new Error('boom'))
    render(<SkillsHub onClose={() => {}} />)
    expect(await screen.findByText(/boom/)).toBeTruthy()
    expect(screen.getByText('Retry')).toBeTruthy()
  })
})

describe('CronPane', () => {
  it('lists jobs with schedule', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, jobs: [{ job_id: 'j1', name: 'Morning', schedule: '0 9 * * *', paused: false }] }))
    render(<CronPane onClose={() => {}} />)
    expect(await screen.findByText('Morning')).toBeTruthy()
    expect(screen.getByText('0 9 * * *')).toBeTruthy()
  })

  it('creates a job', async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonOk({ ok: true }))
      }

      return Promise.resolve(jsonOk({ ok: true, jobs: [] }))
    })
    render(<CronPane onClose={() => {}} />)
    await screen.findByText('No cron jobs. Create one to schedule recurring work.')
    fireEvent.click(screen.getByText('+ New job'))
    fireEvent.change(screen.getByPlaceholderText('Job name'), { target: { value: 'Scout' } })
    fireEvent.click(screen.getByText('Create'))
    await waitFor(() => {
      const [, init] = fetchMock.mock.calls.find(([, i]) => (i as RequestInit | undefined)?.method === 'POST') ?? []
      expect((init as RequestInit).method).toBe('POST')
    })
  })

  it('shows empty state', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, jobs: [] }))
    render(<CronPane onClose={() => {}} />)
    expect(await screen.findByText(/No cron jobs/)).toBeTruthy()
  })
})