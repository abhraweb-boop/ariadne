/**
 * C1 — SessionRail tests: renders sessions, create button, menu actions
 * (rename/delete) with optimistic updates.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SessionRail } from './session-rail'

// Stub the sessions API module
const listMock = vi.fn()
const createMock = vi.fn()
const renameMock = vi.fn()
const deleteMock = vi.fn()

vi.mock('../sessions', () => ({
  listSessions: () => listMock(),
  createSession: () => createMock(),
  renameSession: () => renameMock(),
  deleteSession: () => deleteMock()
}))

const onSelect = vi.fn()
const onNewSession = vi.fn()

describe('SessionRail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listMock.mockResolvedValue([
      { id: 's1', title: 'First' },
      { id: 's2', title: 'Second' }
    ])
  })

  afterEach(cleanup)

  it('renders sessions from API', async () => {
    render(<SessionRail activeId={null} onNewSession={onNewSession} onSelect={onSelect} />)
    await waitFor(() => {
      expect(screen.getByText('First')).toBeTruthy()
      expect(screen.getByText('Second')).toBeTruthy()
    })
  })

  it('creates a session on + New', async () => {
    createMock.mockResolvedValue('s-new')
    render(<SessionRail activeId={null} onNewSession={onNewSession} onSelect={onSelect} />)
    fireEvent.click(screen.getByLabelText('New session'))
    await waitFor(() => {
      expect(onSelect).toHaveBeenCalledWith('s-new')
    })
  })

  it('renames a session via menu', async () => {
    renameMock.mockResolvedValue(true)
    render(<SessionRail activeId="s1" onNewSession={onNewSession} onSelect={onSelect} />)
    await waitFor(() => expect(screen.getByText('First')).toBeTruthy())
    fireEvent.click(screen.getByLabelText('Session menu First'))
    fireEvent.click(screen.getByText('✏️ Rename'))
    const input = screen.getByDisplayValue('First')
    fireEvent.change(input, { target: { value: 'Renamed' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    await waitFor(() => {
      expect(screen.getByText('Renamed')).toBeTruthy()
    })
  })

  it('deletes a session via menu', async () => {
    deleteMock.mockResolvedValue(true)
    render(<SessionRail activeId="s1" onNewSession={onNewSession} onSelect={onSelect} />)
    await waitFor(() => expect(screen.getByText('First')).toBeTruthy())
    fireEvent.click(screen.getByLabelText('Session menu First'))
    fireEvent.click(screen.getByText('🗑 Delete'))
    await waitFor(() => {
      expect(screen.queryByText('First')).toBeNull()
    })
  })
})