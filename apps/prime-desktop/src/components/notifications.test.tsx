/**
 * A5 — Notifications tests: tone/title mapping, heartbeat filtering.
 *
 * @vitest-environment jsdom
 */

import { cleanup, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Notifications, titleFor, toneFor } from './notifications'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('Notification mapping', () => {
  it('toneFor maps event types', () => {
    expect(toneFor('plan.completed')).toBe('success')
    expect(toneFor('plan.failed')).toBe('error')
    expect(toneFor('plan.cancelled')).toBe('info')
    expect(toneFor('kernel.crash')).toBe('error')
    expect(toneFor('plan.created')).toBe('info')
  })

  it('titleFor returns correct titles', () => {
    expect(titleFor('plan.completed', { goal: 'test' }).title).toBe('Plan completed')
    expect(titleFor('plan.failed', { goal: 'test' }).body).toBe('test')
    expect(titleFor('kernel.crash', { error: 'OOM' }).body).toBe('OOM')
    expect(titleFor('unknown', {}).title).toBe('unknown')
  })
})

describe('Notifications', () => {
  it('renders nothing when no events', () => {
    const { container } = render(<Notifications />)
    expect(container.innerHTML).toBe('')
  })
})