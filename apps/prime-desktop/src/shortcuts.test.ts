/**
 * A6 — Shortcut registry tests: register/match/dispatch/ref-count.
 *
 * @vitest-environment jsdom
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getAllShortcuts, installShortcuts, registerShortcut, shortcutForAction } from './shortcuts'

describe('shortcuts', () => {
  beforeEach(() => { vi.restoreAllMocks() })
  afterEach(() => { window.dispatchEvent(new KeyboardEvent('keyup')) })

  it('registers and lists shortcuts', () => {
    registerShortcut({ id: 'a', label: 'Test', combo: 'Ctrl+K', handler: () => {} })
    const list = getAllShortcuts()
    expect(list.some((s) => s.id === 'a' && (s.keys ?? []).includes('k'))).toBe(true)
  })

  it('looks up by action id', () => {
    registerShortcut({ id: 'pane:dags', label: 'DAG', combo: 'Ctrl+Alt+D', handler: () => {} })
    expect(shortcutForAction('pane:dags')?.combo).toBe('Ctrl+Alt+D')
  })

  it('dispatches matching keydown', () => {
    const handler = vi.fn()
    registerShortcut({ id: 'find', label: 'Find', combo: 'Ctrl+F', handler })
    const unsub = installShortcuts()
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'f', ctrlKey: true, bubbles: true, cancelable: true })
    )
    expect(handler).toHaveBeenCalledTimes(1)
    unsub()
  })

  it('does not dispatch on mismatched modifiers', () => {
    const handler = vi.fn()
    registerShortcut({ id: 'palette', label: 'Palette', combo: 'Ctrl+K', handler })
    const unsub = installShortcuts()
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'k', altKey: true, bubbles: true, cancelable: true })
    )
    expect(handler).not.toHaveBeenCalled()
    unsub()
  })

  it('supports meta (Cmd) as Ctrl equivalent', () => {
    const handler = vi.fn()
    registerShortcut({ id: 'new', label: 'New', combo: 'Ctrl+N', handler })
    const unsub = installShortcuts()
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'n', metaKey: true, bubbles: true, cancelable: true })
    )
    expect(handler).toHaveBeenCalledTimes(1)
    unsub()
  })
})