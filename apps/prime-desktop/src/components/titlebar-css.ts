/**
 * A1 — Titlebar drag-region helpers.
 * WebkitAppRegion is not a standard CSS property and jsdom drops it from
 * inline styles, so drag regions are CSS classes (matches Hermes desktop's
 * class-based approach) — testable in any environment.
 */

import type { CSSProperties } from 'react'

export const TITLEBAR_HEIGHT = 34

export const DRAG_CLASS = 'ph-drag'
export const NO_DRAG_CLASS = 'ph-no-drag'

/** Style object minus the region (region lives in a stylesheet class). */
export function titlebarStyle(region: 'drag' | 'no-drag'): CSSProperties {
  return region === 'drag'
    ? { height: TITLEBAR_HEIGHT, flexShrink: 0 }
    : {}
}
