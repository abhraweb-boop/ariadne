/**
 * A4 — FindBar tests: search, match count, prev/next, Esc close.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { FindBar } from './find-bar'

const messages = [
  { role: 'user', text: 'hello world' },
  { role: 'assistant', text: 'hello again world' }
]

describe('FindBar', () => {
  const onClose = vi.fn()
  const onActiveMatch = vi.fn()

  beforeEach(() => { vi.clearAllMocks() })
  afterEach(cleanup)

  it('shows match count', () => {
    render(<FindBar messages={messages} onActiveMatch={onActiveMatch} onClose={onClose} />)
    fireEvent.change(screen.getByPlaceholderText('Find in conversation…'), {
      target: { value: 'hello' }
    })
    // 2 matches across 2 messages
    expect(screen.getByText('1/2')).toBeTruthy()
  })

  it('shows 0/0 for no matches', () => {
    render(<FindBar messages={messages} onActiveMatch={onActiveMatch} onClose={onClose} />)
    fireEvent.change(screen.getByPlaceholderText('Find in conversation…'), {
      target: { value: 'xyz' }
    })
    expect(screen.getByText('0/0')).toBeTruthy()
  })

  it('closes on Escape', () => {
    render(<FindBar messages={messages} onActiveMatch={onActiveMatch} onClose={onClose} />)
    fireEvent.keyDown(screen.getByPlaceholderText('Find in conversation…'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('reports active match', () => {
    render(<FindBar messages={messages} onActiveMatch={onActiveMatch} onClose={onClose} />)
    fireEvent.change(screen.getByPlaceholderText('Find in conversation…'), {
      target: { value: 'world' }
    })
    expect(onActiveMatch).toHaveBeenCalledWith({ messageIndex: 0, textIndex: 6 })
  })
})