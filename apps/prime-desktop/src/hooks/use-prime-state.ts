/**
 * T2 — Shared Prime RPC state hook.
 *
 * Polls GET /api/ariadne/prime/state and exposes { running, state }.
 * DRYs the duplicated loaders in KernelConsole, Agents, SelfImprovePane.
 */

import { useCallback, useEffect, useState } from 'react'

import { get } from '../api'

export interface PrimeRpcState {
  running: boolean
  state: { model?: string; session?: string; kernel?: string } | null
  /** Force an immediate re-poll. */
  refresh: () => void
}

export function usePrimeState(intervalMs = 30000): PrimeRpcState {
  const [running, setRunning] = useState(false)
  const [state, setState] = useState<PrimeRpcState['state']>(null)

  const refresh = useCallback(async () => {
    try {
      const r = await get<{ ok?: boolean; running?: boolean; state?: PrimeRpcState['state'] }>('/api/ariadne/prime/state')
      setRunning(!!r.running)
      setState(r.state ?? null)
    } catch {
      // bridge unavailable — stay in stopped state
    }
  }, [])

  useEffect(() => {
    void refresh()
    const interval = setInterval(() => void refresh(), intervalMs)

    return () => clearInterval(interval)
  }, [refresh, intervalMs])

  return { running, state, refresh }
}