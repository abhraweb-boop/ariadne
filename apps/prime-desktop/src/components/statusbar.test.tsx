/**
 * A2 — Statusbar tests: items render; model menu opens on click;
 * model name polled from /api/prime/state.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Statusbar } from './statusbar'

// Stub fetch for the model poll
const fetchMock = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockResolvedValue({
    ok: true,
    json: async () => ({ ok: true, state: { model: 'openai/gpt-4o-mini' } })
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Statusbar', () => {
  it('renders statusbar items with correct labels', () => {
    render(<Statusbar />)
    // Items render with their label text; the model button's label is the
    // initial model name ('gpt-4o-mini'), updated after fetch.
    expect(screen.getByText('gpt-4o-mini')).toBeTruthy()
    expect(screen.getByText('Gateway')).toBeTruthy()
    expect(screen.getByText('Approval')).toBeTruthy()
  })

  it('shows model from /api/prime/state', async () => {
    render(<Statusbar />)
    await vi.waitFor(() => {
      expect(screen.getByText('openai/gpt-4o-mini')).toBeTruthy()
    })
  })

  it('opens the model dropdown on click', async () => {
    render(<Statusbar />)
    await vi.waitFor(() => {
      expect(screen.getByText('openai/gpt-4o-mini')).toBeTruthy()
    })
    fireEvent.click(screen.getByText('openai/gpt-4o-mini'))
    expect(screen.getByText('Active model')).toBeTruthy()
  })

  it('renders version footer', () => {
    render(<Statusbar />)
    expect(screen.getByText(/Prime Hermes v0\.1\.0/)).toBeTruthy()
  })
})
