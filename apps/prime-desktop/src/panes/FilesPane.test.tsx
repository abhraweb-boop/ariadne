/**
 * D1 — FilesPane tests: lists dir, navigates into folder, opens file,
 * shows empty/error states.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { FilesPane } from './FilesPane'

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

describe('FilesPane', () => {
  it('lists root directory', async () => {
    fetchMock.mockResolvedValue(jsonOk({
      ok: true,
      entries: [
        { name: 'sub', type: 'dir', size: 0, mtime: 0 },
        { name: 'a.txt', type: 'file', size: 1024, mtime: 0 }
      ]
    }))
    render(<FilesPane onClose={() => {}} />)
    expect(await screen.findByText('sub')).toBeTruthy()
    expect(screen.getByText('a.txt')).toBeTruthy()
  })

  it('shows empty state', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, entries: [] }))
    render(<FilesPane onClose={() => {}} />)
    expect(await screen.findByText('Empty directory.')).toBeTruthy()
  })

  it('shows error with retry', async () => {
    fetchMock.mockRejectedValue(new Error('boom'))
    render(<FilesPane onClose={() => {}} />)
    expect(await screen.findByText(/boom/)).toBeTruthy()
    expect(screen.getByText('Retry')).toBeTruthy()
  })

  it('opens a file preview', async () => {
    fetchMock.mockImplementation((url: string) => {
      if (url.includes('/files/list')) {
        return Promise.resolve(jsonOk({
          ok: true,
          entries: [{ name: 'a.txt', type: 'file', size: 10, mtime: 0 }]
        }))
      }

      if (url.includes('/files/read')) {
        return Promise.resolve(jsonOk({ ok: true, content: 'file contents', truncated: false }))
      }

      return Promise.resolve(jsonOk({ ok: true }))
    })
    render(<FilesPane onClose={() => {}} />)
    await screen.findByText('a.txt')
    fireEvent.click(screen.getByText('a.txt'))
    expect(await screen.findByText('file contents')).toBeTruthy()
  })
})