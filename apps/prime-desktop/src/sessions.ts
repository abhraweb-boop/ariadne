/**
 * C1 — Sessions API client.
 * Backend endpoints for listing, renaming, deleting sessions.
 */

import { del, get, patch, post } from './api'

export interface SessionInfo {
  id: string
  title: string
  created_at?: number
  updated_at?: number
}

export async function listSessions(): Promise<SessionInfo[]> {
  try {
    const r = await get<{ ok?: boolean; sessions?: SessionInfo[] }>('/api/sessions')

    return r.sessions ?? []
  } catch {
    return []
  }
}

export async function createSession(title?: string): Promise<string | null> {
  try {
    const r = await post<{ ok: boolean; session_id: string }>('/api/sessions', { title: title ?? 'New session' })

    return r.ok ? r.session_id : null
  } catch {
    return null
  }
}

export async function renameSession(id: string, title: string): Promise<boolean> {
  try {
    const r = await patch<{ ok: boolean }>(`/api/sessions/${id}`, { title })

    return r.ok
  } catch {
    return false
  }
}

export async function deleteSession(id: string): Promise<boolean> {
  try {
    const r = await del<{ ok: boolean }>(`/api/sessions/${id}`)

    return r.ok
  } catch {
    return false
  }
}