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