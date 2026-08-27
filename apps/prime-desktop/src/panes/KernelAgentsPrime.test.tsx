/**
 * H2 — KernelConsole + Agents prime-state polling tests.
 *
 * @vitest-environment jsdom
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Agents } from './Agents'
import { KernelConsole } from './KernelConsole'

const fetchMock = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', fetchMock)
  // jsdom lacks scrollIntoView
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function jsonOk(body: unknown) {
  return { ok: true, json: async () => body } as Response
}

describe('KernelConsole prime state', () => {
  it('shows prime stopped when bridge not running', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/prime/state')) {
        return Promise.resolve(jsonOk({ ok: true, running: false, state: null }))
      }

      return Promise.resolve(jsonOk({}))
    })
    render(<KernelConsole onClose={() => {}} />)
    expect(await screen.findByText('prime stopped')).toBeTruthy()
  })

  it('shows prime live when bridge running', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/prime/state')) {
        return Promise.resolve(jsonOk({ ok: true, running: true, state: { model: 'x' } }))
      }

      return Promise.resolve(jsonOk({}))
    })
    render(<KernelConsole onClose={() => {}} />)
    expect(await screen.findByText('prime live')).toBeTruthy()
  })
})

describe('Agents prime state', () => {
  it('shows prime live when bridge running', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/prime/state')) {
        return Promise.resolve(jsonOk({ ok: true, running: true, state: { model: 'x' } }))
      }

      return Promise.resolve(jsonOk({}))
    })
    render(<Agents onClose={() => {}} />)
    expect(await screen.findByText('prime live')).toBeTruthy()
  })

  it('shows prime stopped when bridge not running', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/prime/state')) {
        return Promise.resolve(jsonOk({ ok: true, running: false, state: null }))
      }

      return Promise.resolve(jsonOk({}))
    })
    render(<Agents onClose={() => {}} />)
    expect(await screen.findByText('prime stopped')).toBeTruthy()
  })
})