/**
 * D1 — DagBoard tests: plan list render, empty state, failed-task Retry re-fetch.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DagBoard } from './DagBoard'

const fetchMock = vi.fn()

function jsonOk(body: unknown) {
  return { ok: true, json: async () => body } as Response
}

function getCalls(urlPart: string): string[] {
  return fetchMock.mock.calls
    .filter(([url]) => String(url).includes(urlPart))
    .map(([url]) => String(url))
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('DagBoard', () => {
  it('renders the empty state when there are no plans', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, plans: [] }))
    render(<DagBoard onClose={() => {}} />)

    expect(
      await screen.findByText('Select a plan or create one to see the DAG board.')
    ).toBeTruthy()
    expect(screen.getByText('🚀 Create & run a sample plan')).toBeTruthy()
    expect(screen.getByRole('option', { name: '— select plan —' })).toBeTruthy()
  })

  it('renders plan names in the plan selector', async () => {
    fetchMock.mockResolvedValue(
      jsonOk({
        ok: true,
        plans: [
          { id: 'plan-1', goal: 'Build feature', state: 'running', created_at: 1, n_tasks: 3, n_done: 1 },
          { id: 'plan-2', goal: 'Analyze data', state: 'done', created_at: 2, n_tasks: 5, n_done: 5 }
        ]
      })
    )
    render(<DagBoard onClose={() => {}} />)

    expect(await screen.findByRole('option', { name: 'Build feature (running)' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Analyze data (done)' })).toBeTruthy()
    expect(getCalls('/api/ariadne/plans').length).toBe(1)
  })

  it('shows Retry for a failed task and re-fetches the plan on click', async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const u = String(url)
      const method = init?.method ?? 'GET'

      if (u.includes('/api/ariadne/plans/plan-1') && method === 'GET') {
        return Promise.resolve(
          jsonOk({
            ok: true,
            plan: { id: 'plan-1' },
            status: 'failed',
            tasks: [
              { id: 't1', title: 'fetch-data', kind: 'note', state: 'failed', depends_on: [], error: 'boom' }
            ]
          })
        )
      }

      if (u.includes('/api/ariadne/plans') && method === 'GET') {
        return Promise.resolve(
          jsonOk({
            ok: true,
            plans: [{ id: 'plan-1', goal: 'Build feature', state: 'failed', created_at: 1, n_tasks: 1, n_done: 0 }]
          })
        )
      }

      if (u.includes('/api/ariadne/tasks/t1/retry') && method === 'POST') {
        return Promise.resolve(jsonOk({ ok: true }))
      }

      return Promise.resolve(jsonOk({ ok: true }))
    })

    render(<DagBoard onClose={() => {}} />)
    await screen.findByRole('option', { name: 'Build feature (failed)' })
    fireEvent.change(screen.getByLabelText('Select plan'), { target: { value: 'plan-1' } })

    // plan detail fetched once, failed task card rendered
    expect(await screen.findByText('fetch-data')).toBeTruthy()
    expect(getCalls('/api/ariadne/plans/plan-1').length).toBe(1)

    // select the failed task -> inspector with Retry
    fireEvent.click(screen.getByText('fetch-data'))
    expect(screen.getByText('Retry')).toBeTruthy()

    // Retry -> POST retry + re-fetch of the plan
    fireEvent.click(screen.getByText('Retry'))

    await waitFor(() => {
      expect(getCalls('/api/ariadne/plans/plan-1').length).toBe(2)
    })
    expect(getCalls('/api/ariadne/tasks/t1/retry').length).toBe(1)
  })
})
