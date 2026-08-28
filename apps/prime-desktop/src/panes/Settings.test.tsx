/**
 * E1+E2 — Settings tests: appearance controls render and apply theme.
 *
 * @vitest-environment jsdom
 */

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Settings } from './Settings'

// Stub window.primeHermes.gatewayBase (api.ts resolves through bridge)
beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) }))
  ;(window as unknown as Record<string, unknown>).primeHermes = {
    gatewayBase: async () => 'http://127.0.0.1:8000'
  }
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Settings', () => {
  it('renders gateway URL', async () => {
    render(<Settings onClose={() => {}} />)
    expect(await screen.findByText('http://127.0.0.1:8000')).toBeTruthy()
  })

  it('renders appearance controls', () => {
    render(<Settings onClose={() => {}} />)
    expect(screen.getByLabelText('Accent indigo')).toBeTruthy()
    expect(screen.getByLabelText('Accent green')).toBeTruthy()
    expect(screen.getByLabelText('Accent amber')).toBeTruthy()
    expect(screen.getByLabelText('Accent rose')).toBeTruthy()
    expect(screen.getByText('Theme')).toBeTruthy()
    expect(screen.getByText('Font size')).toBeTruthy()
  })

  it('switches theme on radio click', () => {
    render(<Settings onClose={() => {}} />)
    fireEvent.click(screen.getByLabelText('light'))
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('changes accent', () => {
    render(<Settings onClose={() => {}} />)
    fireEvent.click(screen.getByLabelText('Accent green'))
    expect(document.documentElement.style.getPropertyValue('--accent')).toBe('#3f9e6a')
  })
})

describe('S1+S2', () => {
  it('renders the theme preview card', async () => {
    render(<Settings onClose={() => {}} />)
    expect(await screen.findByLabelText('Theme preview')).toBeTruthy()
  })

  it('reset button clears known keys when confirmed', async () => {
    const removeSpy = vi.spyOn(Storage.prototype, 'removeItem')
    const reloadSpy = vi.fn()
    vi.stubGlobal('location', { reload: reloadSpy })
    ;(window as unknown as Record<string, unknown>).confirm = vi.fn().mockReturnValue(true)
    render(<Settings onClose={() => {}} />)
    fireEvent.click(await screen.findByText('Reset all data'))
    expect(removeSpy).toHaveBeenCalledWith('prime-hermes:theme:prefs')
    expect(removeSpy).toHaveBeenCalledWith('prime-hermes:onboarding-done')
    expect(reloadSpy).toHaveBeenCalled()
    removeSpy.mockRestore()
  })

  it('reset does nothing when confirm is declined', async () => {
    const removeSpy = vi.spyOn(Storage.prototype, 'removeItem')

    ;(window as unknown as Record<string, unknown>).confirm = vi.fn().mockReturnValue(false)
    render(<Settings onClose={() => {}} />)
    fireEvent.click(await screen.findByText('Reset all data'))
    expect(removeSpy).not.toHaveBeenCalled()
    removeSpy.mockRestore()
  })
})