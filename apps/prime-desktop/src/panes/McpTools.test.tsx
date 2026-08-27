/**
 * C3 — McpPane + ToolsPane tests.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { McpPane } from './McpPane'
import { ToolsPane } from './ToolsPane'

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

describe('McpPane', () => {
  it('lists servers', async () => {
    fetchMock.mockResolvedValue(jsonOk({ servers: [{ name: 'github', command: 'npx mcp-github' }] }))
    render(<McpPane onClose={() => {}} />)
    expect(await screen.findByText('github')).toBeTruthy()
  })

  it('shows empty state', async () => {
    fetchMock.mockResolvedValue(jsonOk({ servers: [] }))
    render(<McpPane onClose={() => {}} />)
    expect(await screen.findByText(/No MCP servers configured/)).toBeTruthy()
  })
})

describe('ToolsPane', () => {
  it('lists toolsets with toggle', async () => {
    fetchMock.mockResolvedValue(jsonOk({ toolsets: [{ name: 'web', enabled: true }] }))
    render(<ToolsPane onClose={() => {}} />)
    expect(await screen.findByText('web')).toBeTruthy()
    expect(screen.getByText('Disable')).toBeTruthy()
  })

  it('toggles a toolset', async () => {
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      if ((init?.method ?? 'GET') === 'PUT') {
        return Promise.resolve(jsonOk({ ok: true }))
      }

      return Promise.resolve(jsonOk({ toolsets: [{ name: 'web', enabled: true }] }))
    })
    render(<ToolsPane onClose={() => {}} />)
    await screen.findByText('web')
    fireEvent.click(screen.getByText('Disable'))
    expect(screen.getByText('Enable')).toBeTruthy()
  })
})