/**
 * S1 — SelfImprovePane tests.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SelfImprovePane } from './SelfImprovePane'

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

describe('SelfImprovePane', () => {
  it('shows empty heals state', async () => {
    fetchMock.mockResolvedValue(jsonOk({ heals: [] }))
    render(<SelfImprovePane onClose={() => {}} />)
    expect(await screen.findByText(/No self-healing events/)).toBeTruthy()
  })

  it('lists heals', async () => {
    fetchMock.mockResolvedValue(jsonOk({ heals: [{ what: 'restarted gateway', outcome: 'ok' }] }))
    render(<SelfImprovePane onClose={() => {}} />)
    expect(await screen.findByText('restarted gateway')).toBeTruthy()
  })

  it('records a refine', async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonOk({ ok: true, entry: { id: 'e1' } }))
      }

      return Promise.resolve(jsonOk({ heals: [] }))
    })
    render(<SelfImprovePane onClose={() => {}} />)
    await screen.findByText(/No self-healing events/)
    fireEvent.change(screen.getByPlaceholderText('What to improve? (optional)'), { target: { value: 'better diffs' } })
    fireEvent.click(screen.getByText('Refine'))
    expect(await screen.findByText(/Refine recorded \(e1\)/)).toBeTruthy()
  })
})