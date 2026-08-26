/**
 * B3 — StreamingCaret tests: renders with correct testid, has animation.
 *
 * @vitest-environment jsdom
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StreamingCaret } from './streaming-caret'

describe('StreamingCaret', () => {
  it('renders with testid', () => {
    render(<StreamingCaret />)
    expect(screen.getByTestId('streaming-caret')).toBeTruthy()
  })

  it('has the blink animation', () => {
    const { container } = render(<StreamingCaret />)
    const span = container.querySelector('span')
    expect(span?.style.animation).toContain('ph-caret')
  })
})