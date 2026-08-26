/**
 * G2 — Statusbar widgets tests: render and show dots.
 * @vitest-environment jsdom
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { KernelWidget, PlanCountWidget, WorkerWidget, MemoryWidget } from './statusbar-widgets'

beforeEach(() => { vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })) })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('KernelWidget', () => {
  it('renders kernel label', () => {
    render(<KernelWidget />)
    expect(screen.getByText('kernel')).toBeTruthy()
  })
  it('has accessible label', () => {
    render(<KernelWidget />)
    expect(screen.getByLabelText('Kernel status')).toBeTruthy()
  })
})
describe('PlanCountWidget', () => {
  it('renders plan count', () => {
    render(<PlanCountWidget />)
    expect(screen.getByText(/plans/)).toBeTruthy()
  })
})
describe('WorkerWidget', () => {
  it('renders worker label', () => {
    render(<WorkerWidget />)
    expect(screen.getByText('worker')).toBeTruthy()
  })
})
describe('MemoryWidget', () => {
  it('renders memory label', () => {
    render(<MemoryWidget />)
    expect(screen.getByText(/mem/)).toBeTruthy()
  })
})