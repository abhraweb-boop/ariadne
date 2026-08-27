/**
 * S1 — SelfImprovePane tests (C2: live Prime RPC).
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

  it('drives the live prime worker on refine', async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET'

      if (method === 'POST') {
        return Promise.resolve(jsonOk({ ok: true, response: 'refined the auth module' }))
      }

      if (url.includes('/prime/state')) {
        return Promise.resolve(jsonOk({ ok: true, running: false, state: null }))
      }

      return Promise.resolve(jsonOk({ heals: [] }))
    })
    render(<SelfImprovePane onClose={() => {}} />)
    await screen.findByText(/No self-healing events/)
    fireEvent.change(screen.getByPlaceholderText('What to improve? (sent to Prime RPC)'), { target: { value: 'better diffs' } })
    fireEvent.click(screen.getByText('Refine'))
    expect(await screen.findByText(/Prime worker responded: refined the auth module/)).toBeTruthy()
  })

  it('shows live worker state dot', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/prime/state')) {
        return Promise.resolve(jsonOk({ ok: true, running: true, state: { model: 'deepseek-v4-flash' } }))
      }

      return Promise.resolve(jsonOk({ heals: [] }))
    })
    render(<SelfImprovePane onClose={() => {}} />)
    expect(await screen.findByText(/Prime worker live · deepseek-v4-flash/)).toBeTruthy()
  })
})