/**
 * F2 — Onboarding tests.
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { Onboarding } from './onboarding'

beforeEach(() => { localStorage.clear() })
afterEach(cleanup)

describe('Onboarding', () => {
  it('renders first step', () => {
    render(<Onboarding onClose={() => {}} />)
    expect(screen.getByText('Welcome')).toBeTruthy()
    expect(screen.getByText('Welcome to Prime Hermes. Your AI harness.')).toBeTruthy()
  })
  it('navigates to next step', () => {
    render(<Onboarding onClose={() => {}} />)
    fireEvent.click(screen.getByText('Next'))
    expect(screen.getByText('Chat')).toBeTruthy()
  })
  it('shows Start button on last step', () => {
    render(<Onboarding onClose={() => {}} />)
    for (let i = 0; i < 5; i++) { fireEvent.click(screen.getByText('Next')) }
    expect(screen.getByText('Start using Prime')).toBeTruthy()
  })
  it('does not show after completion', () => {
    localStorage.setItem('prime-hermes:onboarding-done', '1')
    const { container } = render(<Onboarding onClose={() => {}} />)
    expect(container.innerHTML).toBe('')
  })
})