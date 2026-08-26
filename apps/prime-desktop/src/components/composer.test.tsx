/**
 * B2 — Composer tests: multiline, Enter sends, stop during sending,
 * drag-drop shows overlay + attachment hints.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Composer } from './composer'

describe('Composer', () => {
  const onSend = vi.fn()
  const onStop = vi.fn()
  const onInputChange = vi.fn()

  beforeEach(() => { vi.clearAllMocks() })
  afterEach(cleanup)

  it('sends on Enter without Shift', () => {
    render(<Composer input="hello" onInputChange={onInputChange} onSend={onSend} sending={false} />)
    fireEvent.keyDown(screen.getByPlaceholderText('Send a message to the Prime worker…'), { key: 'Enter' })
    expect(onSend).toHaveBeenCalledTimes(1)
  })

  it('inserts newline on Shift+Enter', () => {
    render(<Composer input="hello" onInputChange={onInputChange} onSend={onSend} sending={false} />)
    fireEvent.keyDown(screen.getByPlaceholderText('Send a message to the Prime worker…'), { key: 'Enter', shiftKey: true })
    expect(onSend).not.toHaveBeenCalled()
  })

  it('shows Stop button while sending', () => {
    render(<Composer input="hi" onInputChange={onInputChange} onSend={onSend} onStop={onStop} sending={true} />)
    fireEvent.click(screen.getByLabelText('Stop'))
    expect(onStop).toHaveBeenCalledTimes(1)
  })

  it('disables Send when input empty', () => {
    render(<Composer input="" onInputChange={onInputChange} onSend={onSend} sending={false} />)
    const send = screen.getByLabelText('Send') as HTMLButtonElement
    expect(send.disabled).toBe(true)
  })

  it('shows drag-drop overlay on dragover', () => {
    render(<Composer input="" onInputChange={onInputChange} onSend={onSend} sending={false} />)
    fireEvent.dragOver(screen.getByText('Send'))
    expect(screen.getByText('Drop files here')).toBeTruthy()
  })
})