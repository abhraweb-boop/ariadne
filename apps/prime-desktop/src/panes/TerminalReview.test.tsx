/**
 * D2+D3 — Terminal + Review pane tests.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ReviewPane } from './ReviewPane'
import { TerminalPane } from './TerminalPane'

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

describe('TerminalPane', () => {
  it('renders open-terminal affordance', () => {
    render(<TerminalPane onClose={() => {}} />)
    expect(screen.getByText('Open system terminal')).toBeTruthy()
  })

  it('calls open-terminal endpoint on click', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true }))
    render(<TerminalPane onClose={() => {}} />)
    fireEvent.click(screen.getByText('Open system terminal'))
    await waitFor(() => {
      expect(screen.getByText('System terminal opened.')).toBeTruthy()
    })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/profiles/default/open-terminal')
    expect((init as RequestInit).method).toBe('POST')
  })

  it('shows failure message', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: false, detail: 'nope' }))
    render(<TerminalPane onClose={() => {}} />)
    fireEvent.click(screen.getByText('Open system terminal'))
    await waitFor(() => {
      expect(screen.getByText(/Failed: nope/)).toBeTruthy()
    })
  })
})

describe('ReviewPane', () => {
  it('lists uncommitted changes', async () => {
    fetchMock.mockResolvedValue(jsonOk({
      ok: true,
      files: [
        { path: 'src/a.ts', status: 'M', staged: false, hunks: 1, insertions: 3, deletions: 1 }
      ]
    }))
    render(<ReviewPane onClose={() => {}} />)
    expect(await screen.findByText('src/a.ts')).toBeTruthy()
    expect(screen.getByText('+3')).toBeTruthy()
    expect(screen.getByText('-1')).toBeTruthy()
  })

  it('shows empty state', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, files: [] }))
    render(<ReviewPane onClose={() => {}} />)
    expect(await screen.findByText('No uncommitted changes.')).toBeTruthy()
  })

  it('opens a diff', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/review/list')) {
        return Promise.resolve(jsonOk({
          ok: true,
          files: [{ path: 'a.ts', status: 'M', staged: false, hunks: 1, insertions: 1, deletions: 0 }]
        }))
      }

      if (url.includes('/file-diff')) {
        return Promise.resolve(jsonOk({ diff: '--- a.ts\n+++ b.ts\n@@ -1 +1 @@\n-x\n+y' }))
      }

      return Promise.resolve(jsonOk({ ok: true }))
    })
    render(<ReviewPane onClose={() => {}} />)
    await screen.findByText('a.ts')
    fireEvent.click(screen.getByText('a.ts'))
    expect(await screen.findByText(/\+y/)).toBeTruthy()
  })
})