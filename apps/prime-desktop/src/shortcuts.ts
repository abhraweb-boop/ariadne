/**
 * A6 — Central keyboard shortcut registry (port of Hermes desktop's keybinds).
 *
 * Every shortcut is registered here with a label + key combo; the same
 * registry powers the command palette's shortcut hints (G1) and a
 * discoverable shortcuts dialog. Combos use 'Ctrl+Key' syntax; both Ctrl
 * and Cmd (meta) are accepted on all platforms.
 */

export interface Shortcut {
  id: string
  label: string
  /** e.g. 'Ctrl+K' — display form. */
  combo: string
  /** Normalized keys (derived from combo on registration); readonly after. */
  keys?: string[]
  handler: (e: KeyboardEvent) => void
}

const registry = new Map<string, Shortcut>()

function normalize(combo: string): string[] {
  return combo.toLowerCase().split('+').map((k) => k.trim())
}

export function registerShortcut(s: Shortcut): void {
  registry.set(s.id, { ...s, keys: normalize(s.combo) })
}

export function getAllShortcuts(): Shortcut[] {
  return [...registry.values()].map((s) => ({ ...s, keys: s.keys ?? [] }))
}

export function shortcutForAction(actionId: string): Shortcut | undefined {
  return registry.get(actionId)
}

function matches(e: KeyboardEvent, keys: string[]): boolean {
  const mods = keys.filter((k): k is 'ctrl' | 'alt' | 'shift' | 'meta' =>
    k === 'ctrl' || k === 'alt' || k === 'shift' || k === 'meta')

  const main = keys.find((k) => !mods.includes(k as 'ctrl' | 'alt' | 'shift' | 'meta'))

  const ctrl = keys.includes('ctrl')
  const alt = keys.includes('alt')
  const shift = keys.includes('shift')
  const meta = keys.includes('meta')

  // Ctrl and Cmd (meta) are interchangeable (Hermes desktop behavior).
  const ctrlOk = ctrl ? (e.ctrlKey || e.metaKey) : !e.ctrlKey && !e.metaKey

  if (!ctrlOk) {return false}

  // Alt/Shift must match exactly.
  if (e.altKey !== alt) {return false}

  if (e.shiftKey !== shift) {return false}

  if (!main) {return true}

  return e.key.toLowerCase() === main
}

let mounted = 0

/** Install/remove the global keydown dispatcher (ref-counted). */
export function installShortcuts(): () => void {
  mounted += 1

  if (mounted === 1) {
    window.addEventListener('keydown', dispatcher)
  }

  return () => {
    mounted -= 1

    if (mounted === 0) {
      window.removeEventListener('keydown', dispatcher)
    }
  }
}

function dispatcher(e: KeyboardEvent): void {
  for (const s of registry.values()) {
    const keys = s.keys ?? []

    if (matches(e, keys)) {
      e.preventDefault()
      s.handler(e)

      return
    }
  }
}
