/**
 * T2 — usePrimeState hook tests.
 *
 * @vitest-environment jsdom
 */

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePrimeState } from './use-prime-state'

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

describe('usePrimeState', () => {
  it('reports stopped when bridge not running', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, running: false, state: null }))
    const { result } = renderHook(() => usePrimeState(60000))
    await waitFor(() => expect(result.current.running).toBe(false))
    expect(result.current.state).toBeNull()
  })

  it('reports running with model', async () => {
    fetchMock.mockResolvedValue(jsonOk({ ok: true, running: true, state: { model: 'x', session: 's' } }))
    const { result } = renderHook(() => usePrimeState(60000))
    await waitFor(() => expect(result.current.running).toBe(true))
    expect(result.current.state?.model).toBe('x')
  })

  it('refresh re-polls', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonOk({ ok: true, running: false, state: null }))
      .mockResolvedValueOnce(jsonOk({ ok: true, running: true, state: { model: 'y' } }))
    const { result } = renderHook(() => usePrimeState(60000))
    await waitFor(() => expect(result.current.running).toBe(false))
    await act(async () => { await result.current.refresh() })
    await waitFor(() => expect(result.current.running).toBe(true))
  })
})