/**
 * Pane registry — the modular surface system.
 * Every capability registers here; the shell renders rail → registry.
 */

import type { ComponentType } from 'react'

export interface Pane {
  id: string
  label: string
  icon: string
  render: ComponentType<{ onClose: () => void }>
}

const paneRegistry = new Map<string, Pane>()

export function registerPane(pane: Pane): void {
  paneRegistry.set(pane.id, pane)
}

export function getPanes(): Pane[] {
  return [...paneRegistry.values()]
}
