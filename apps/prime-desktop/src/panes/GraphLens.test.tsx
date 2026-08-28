/**
 * G1 — GraphLens tests: nodes render, empty state, error handling + re-search recovery.
 *
 * GraphLens has no Retry button: a failed search is swallowed into the
 * "No nodes found." empty state and the recovery path is re-typing a query
 * (useEffect re-runs search). We assert both halves of that contract.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { GraphLens } from './GraphLens'

const fetchMock = vi.fn()

function jsonOk(body: unknown) {
  return { ok: true, json: async () => body } as Response
}

function getCalls(urlPart: string): string[] {
  return fetchMock.mock.calls
    .filter(([url]) => String(url).includes(urlPart))
    .map(([url]) => String(url))
}

function node(id: string, title: string, type = 'file'): Record<string, unknown> {
  return { id, type, key: title, title, meta: '', first_seen: 1, last_seen: 2, touches: 3 }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('GraphLens', () => {
  it('renders the context graph after searching', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (String(url).includes('/api/ariadne/graph/related')) {
        return Promise.resolve(jsonOk({ ok: true, nodes: [node('n1', 'main.ts'), node('n2', 'App.tsx')] }))
      }

      return Promise.resolve(jsonOk({ ok: true, nodes: [] }))
    })

    render(<GraphLens onClose={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText(/Search nodes/), { target: { value: 'alpha' } })

    expect(await screen.findByRole('img', { name: 'Context graph' })).toBeTruthy()
    expect(getCalls('/api/ariadne/graph/related').length).toBe(1)
    expect(getCalls('query=alpha')).toHaveLength(1)
  })

  it('shows the empty state when no nodes match', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, nodes: [] }))
    render(<GraphLens onClose={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText(/Search nodes/), { target: { value: 'zzz' } })

    expect(await screen.findByText('No nodes found.')).toBeTruthy()
  })

  it('handles a failed fetch and recovers on a new search', async () => {
    fetchMock
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce(jsonOk({ ok: true, nodes: [node('n1', 'recovered.ts')] }))

    render(<GraphLens onClose={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText(/Search nodes/), { target: { value: 'alpha' } })

    // failed search -> error swallowed into the empty state, no crash
    expect(await screen.findByText('No nodes found.')).toBeTruthy()

    // re-search (the pane's retry affordance) -> nodes render again
    fireEvent.change(screen.getByPlaceholderText(/Search nodes/), { target: { value: 'beta' } })
    expect(await screen.findByRole('img', { name: 'Context graph' })).toBeTruthy()
    expect(getCalls('/api/ariadne/graph/related').length).toBe(2)
  })
})
