/**
 * C4 — ProfilesPane + WebhooksPane tests.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ProfilesPane } from './ProfilesPane'
import { WebhooksPane } from './WebhooksPane'

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

describe('ProfilesPane', () => {
  it('lists profiles with active marker', async () => {
    fetchMock.mockResolvedValue(jsonOk({ profiles: [{ name: 'default', active: true }, { name: 'work', active: false }] }))
    render(<ProfilesPane onClose={() => {}} />)
    expect(await screen.findByText('default')).toBeTruthy()
    expect(screen.getByText('work')).toBeTruthy()
    expect(screen.getByText('Activate')).toBeTruthy()
  })

  it('creates a profile', async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'POST') {
        return Promise.resolve(jsonOk({ ok: true }))
      }

      return Promise.resolve(jsonOk({ profiles: [] }))
    })
    render(<ProfilesPane onClose={() => {}} />)
    await screen.findByText(/No profiles found/)
    fireEvent.change(screen.getByPlaceholderText('New profile name…'), { target: { value: 'test' } })
    fireEvent.click(screen.getByText('Create'))
    expect(await screen.findByText('Profile created.')).toBeTruthy()
  })
})

describe('WebhooksPane', () => {
  it('lists webhooks', async () => {
    fetchMock.mockResolvedValue(jsonOk({ webhooks: [{ url: 'https://example.com/hook' }] }))
    render(<WebhooksPane onClose={() => {}} />)
    expect(await screen.findByText('https://example.com/hook')).toBeTruthy()
  })

  it('shows empty state', async () => {
    fetchMock.mockResolvedValue(jsonOk({ webhooks: [] }))
    render(<WebhooksPane onClose={() => {}} />)
    expect(await screen.findByText(/No webhooks/)).toBeTruthy()
  })
})