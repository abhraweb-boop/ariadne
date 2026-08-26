/**
 * Token audit (polish spec item 5): every node-type hue must hold >=3:1
 * contrast against the dark panel background, and the palette must stay
 * within the <=3-hue-families + neutrals budget (anti-slop #10).
 */

import { describe, expect, it } from 'vitest'

import { NODE_TYPE_META } from './colors'

// Panel canvas background: var(--background) on the dark theme (~#1E1E1E
// family). We test against the darkest plausible surface used behind nodes.
const BG = { r: 0x1e, g: 0x1e, b: 0x1e }

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace('#', '')

  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16)
  }
}

function relLuminance({ r, g, b }: { r: number; g: number; b: number }): number {
  const lin = (c: number) => {
    const s = c / 255

    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }

  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
}

function contrast(a: string): number {
  const l1 = relLuminance(BG)
  const l2 = relLuminance(hexToRgb(a))
  const hi = Math.max(l1, l2)
  const lo = Math.min(l1, l2)

  return (hi + 0.05) / (lo + 0.05)
}

describe('graph color tokens', () => {
  it('every concrete hue clears 3:1 against the dark background', () => {
    const offenders: string[] = []

    for (const [type, meta] of Object.entries(NODE_TYPE_META)) {
      if (!meta.color.startsWith('#')) {continue} // var(--accent) checked by theme
      const ratio = contrast(meta.color)

      if (ratio < 3) {offenders.push(`${type}: ${meta.color} = ${ratio.toFixed(2)}`)}
    }

    expect(offenders).toEqual([])
  })

  it('stays within the hue budget (blue, green, amber families + neutral)', () => {
    const families = new Set<string>()

    for (const meta of Object.values(NODE_TYPE_META)) {
      if (!meta.color.startsWith('#')) {continue}
      const { r, g, b } = hexToRgb(meta.color)

      if (b > r && b > g) {families.add('blue')}
      else if (g > r && g >= b) {families.add('green')}
      else if (r > g && g > b) {families.add('amber')}
      else {families.add('neutral')}
    }

    expect(families.size).toBeLessThanOrEqual(3)
  })
})
