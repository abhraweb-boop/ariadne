/**
 * A5 — ErrorBoundary tests: renders children normally; catches render errors
 * and shows recovery card.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ErrorBoundary } from './error-boundary'

afterEach(cleanup)

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(<ErrorBoundary><div>safe</div></ErrorBoundary>)
    expect(screen.getByText('safe')).toBeTruthy()
  })

  it('catches error and shows recovery card', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const Thrower = () => { throw new Error('test crash') }
    render(<ErrorBoundary><Thrower /></ErrorBoundary>)
    expect(screen.getByText('Something went wrong')).toBeTruthy()
    expect(screen.getByText('test crash')).toBeTruthy()
    expect(screen.getByText('Try again')).toBeTruthy()
    spy.mockRestore()
  })

  it('resets on Try again click', () => {
    const onReset = vi.fn()
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    let shouldThrow = true

    function Wrapper() {
      if (shouldThrow) {throw new Error('boom')}

      return <div>recovered</div>
    }

    render(<ErrorBoundary onReset={onReset}><Wrapper /></ErrorBoundary>)
    expect(screen.getByText('Something went wrong')).toBeTruthy()

    // Fix the underlying cause, then click Try again — boundary must render children.
    shouldThrow = false
    fireEvent.click(screen.getByText('Try again'))
    expect(screen.getByText('recovered')).toBeTruthy()
    spy.mockRestore()
  })
})