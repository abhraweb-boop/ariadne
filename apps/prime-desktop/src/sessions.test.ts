/**
 * C1 — sessions API client tests (fetch stubbed).
 *
 * @vitest-environment jsdom
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createSession, deleteSession, listSessions, renameSession } from './sessions'

const fetchMock = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function jsonOk(body: unknown) {
  return { ok: true, json: async () => body } as Response
}

describe('sessions API', () => {
  it('lists sessions', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, sessions: [{ id: 's1', title: 'One' }] }))
    const sessions = await listSessions()
    expect(sessions).toHaveLength(1)
    expect(sessions[0].id).toBe('s1')
  })

  it('returns [] on list failure', async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) } as Response)
    expect(await listSessions()).toEqual([])
  })

  it('renames a session', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true }))
    expect(await renameSession('s1', 'New name')).toBe(true)
    // PATCH with title body
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/sessions/s1')
    expect((init as RequestInit).method).toBe('PATCH')
  })

  it('deletes a session', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true }))
    expect(await deleteSession('s1')).toBe(true)
    const [, init] = fetchMock.mock.calls[0]
    expect((init as RequestInit).method).toBe('DELETE')
  })

  it('creates a session', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, session_id: 's-new' }))
    expect(await createSession('Fresh')).toBe('s-new')
    const [, init] = fetchMock.mock.calls[0]
    expect((init as RequestInit).method).toBe('POST')
  })
})