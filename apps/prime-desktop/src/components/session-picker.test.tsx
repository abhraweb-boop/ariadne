/**
 * C2 — SessionPicker tests: lists sessions, filters, selects on Enter,
 * closes on Escape.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SessionPicker } from './session-picker'

const listMock = vi.fn()

vi.mock('../sessions', () => ({
  listSessions: () => listMock()
}))

const onSelect = vi.fn()
const onClose = vi.fn()

describe('SessionPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listMock.mockResolvedValue([
      { id: 's1', title: 'Alpha session' },
      { id: 's2', title: 'Beta session' }
    ])
  })

  afterEach(cleanup)

  it('lists sessions', async () => {
    render(<SessionPicker onClose={onClose} onSelect={onSelect} />)
    expect(await screen.findByText('Alpha session')).toBeTruthy()
    expect(screen.getByText('Beta session')).toBeTruthy()
  })

  it('filters by query', async () => {
    render(<SessionPicker onClose={onClose} onSelect={onSelect} />)
    await screen.findByText('Alpha session')
    fireEvent.change(screen.getByPlaceholderText('Switch session…'), { target: { value: 'beta' } })
    expect(screen.queryByText('Alpha session')).toBeNull()
    expect(screen.getByText('Beta session')).toBeTruthy()
  })

  it('selects on Enter and closes', async () => {
    render(<SessionPicker onClose={onClose} onSelect={onSelect} />)
    await screen.findByText('Alpha session')
    fireEvent.keyDown(screen.getByPlaceholderText('Switch session…'), { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledWith('s1')
    expect(onClose).toHaveBeenCalled()
  })

  it('closes on Escape', async () => {
    render(<SessionPicker onClose={onClose} onSelect={onSelect} />)
    await screen.findByText('Alpha session')
    fireEvent.keyDown(screen.getByPlaceholderText('Switch session…'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalled()
  })
})