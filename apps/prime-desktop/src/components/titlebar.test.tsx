/**
 * A1 — Titlebar tests: brand mark renders; 3 window controls present;
 * controls call the bridge (window.primeHermes.*).
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Titlebar } from './titlebar'
import { DRAG_CLASS, NO_DRAG_CLASS } from './titlebar-css'

describe('Titlebar', () => {
  const bridge = {
    windowMinimize: vi.fn().mockResolvedValue(undefined),
    windowMaximize: vi.fn().mockResolvedValue(undefined),
    windowClose: vi.fn().mockResolvedValue(undefined)
  }

  beforeEach(() => {
    vi.clearAllMocks()
    ;(window as unknown as Record<string, unknown>).primeHermes = bridge
  })

  afterEach(cleanup)

  it('renders the brand mark', () => {
    render(<Titlebar />)
    expect(screen.getByText('Prime Hermes')).toBeTruthy()
  })

  it('renders three window controls', () => {
    render(<Titlebar />)
    expect(screen.getByRole('button', { name: 'Minimize' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Maximize' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Close' })).toBeTruthy()
  })

  it('calls bridge methods on click', () => {
    render(<Titlebar />)
    fireEvent.click(screen.getByRole('button', { name: 'Minimize' }))
    fireEvent.click(screen.getByRole('button', { name: 'Maximize' }))
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(bridge.windowMinimize).toHaveBeenCalledTimes(1)
    expect(bridge.windowMaximize).toHaveBeenCalledTimes(1)
    expect(bridge.windowClose).toHaveBeenCalledTimes(1)
  })

  it('is a drag region with no-drag controls', () => {
    const { container } = render(<Titlebar />)
    const header = container.querySelector('header')
    expect(header?.className).toContain(DRAG_CLASS)
    const controls = container.querySelector('header > div:last-child')
    expect(controls?.className).toContain(NO_DRAG_CLASS)
  })
})
