/**
 * A3 — Command palette tests: opens with registered actions, filters by
 * keyword, keyboard navigation (↑↓/Enter/Esc).
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { registerAction } from '../actions'

import { CommandPalette } from './command-palette'

describe('CommandPalette', () => {
  const opened: string[] = []

  beforeEach(() => {
    opened.length = 0
    registerAction({
      id: 'pane:dags',
      label: 'Open DAG Board',
      keywords: ['dag', 'plan'],
      category: 'Pane',
      run: () => { opened.push('dags') }
    })
    registerAction({
      id: 'session:new',
      label: 'New Session',
      keywords: ['new', 'chat'],
      category: 'Session',
      run: () => { opened.push('session') }
    })
  })

  afterEach(cleanup)

  it('shows all actions on open', () => {
    render(<CommandPalette onClose={() => {}} />)
    expect(screen.getByText('Open DAG Board')).toBeTruthy()
    expect(screen.getByText('New Session')).toBeTruthy()
  })

  it('filters by keyword', () => {
    render(<CommandPalette onClose={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText('Search actions…'), {
      target: { value: 'dag' }
    })
    expect(screen.getByText('Open DAG Board')).toBeTruthy()
    expect(screen.queryByText('New Session')).toBeNull()
  })

  it('selects on Enter', () => {
    render(<CommandPalette onClose={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText('Search actions…'), {
      target: { value: 'dag' }
    })
    fireEvent.keyDown(screen.getByPlaceholderText('Search actions…'), { key: 'Enter' })
    expect(opened).toEqual(['dags'])
  })

  it('closes on Escape', () => {
    const onClose = vi.fn()
    render(<CommandPalette onClose={onClose} />)
    fireEvent.keyDown(screen.getByPlaceholderText('Search actions…'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
