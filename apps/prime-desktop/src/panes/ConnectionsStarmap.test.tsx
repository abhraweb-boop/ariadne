/**
 * C5 — ConnectionsPane + StarmapPane tests.
 *
 * @vitest-environment jsdom
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ConnectionsPane } from './ConnectionsPane'
import { StarmapPane } from './StarmapPane'

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

describe('ConnectionsPane', () => {
  it('shows gateway status from bridge', async () => {
    ;(window as unknown as Record<string, unknown>).primeHermes = {
      gatewayStatus: async () => ({ healthy: true, spawned: false, base: 'http://127.0.0.1:8000' })
    }
    render(<ConnectionsPane onClose={() => {}} />)
    expect(await screen.findByText('Gateway connected')).toBeTruthy()
    expect(screen.getByText('http://127.0.0.1:8000')).toBeTruthy()
    delete (window as unknown as Record<string, unknown>).primeHermes
  })
})

describe('StarmapPane', () => {
  it('renders graph stats and runs', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/stats')) {
        return Promise.resolve(jsonOk({ stats: { nodes: 12, edges: 20 } }))
      }

      return Promise.resolve(jsonOk({ runs: [{ plan_id: 'p1', goal: 'Build feature', state: 'done' }] }))
    })
    render(<StarmapPane onClose={() => {}} />)
    expect(await screen.findByText('Build feature')).toBeTruthy()
    expect(screen.getByText('12')).toBeTruthy()
  })

  it('shows error with retry', async () => {
    fetchMock.mockRejectedValue(new Error('boom'))
    render(<StarmapPane onClose={() => {}} />)
    expect(await screen.findByText(/boom/)).toBeTruthy()
  })
})