/**
 * E1 — Theme engine tests.
 *
 * @vitest-environment jsdom
 */

import { beforeEach, describe, expect, it } from 'vitest'

import { ACCENTS, applyTheme, DEFAULT_PREFS, loadPrefs, savePrefs, THEME_STORAGE_KEY } from './themes'

describe('theme engine', () => {
  beforeEach(() => {
    localStorage.clear()
    // fresh root
    document.documentElement.removeAttribute('data-theme')
  })

  it('defaults to dark indigo', () => {
    expect(loadPrefs()).toEqual(DEFAULT_PREFS)
  })

  it('round-trips prefs through storage', () => {
    savePrefs({ mode: 'light', accent: 'green', fontScale: 1.1 })
    expect(loadPrefs()).toEqual({ mode: 'light', accent: 'green', fontScale: 1.1 })
  })

  it('falls back to defaults on corrupt storage', () => {
    localStorage.setItem(THEME_STORAGE_KEY, '{not json')
    expect(loadPrefs()).toEqual(DEFAULT_PREFS)
  })

  it('applies dark tokens + accent', () => {
    applyTheme({ mode: 'dark', accent: 'indigo', fontScale: 1 })
    const root = document.documentElement
    expect(root.getAttribute('data-theme')).toBe('dark')
    expect(root.classList.contains('dark')).toBe(true)
    expect(root.style.getPropertyValue('--accent')).toBe(ACCENTS.indigo)
    expect(root.style.getPropertyValue('--theme-primary')).toBe(ACCENTS.indigo)
  })

  it('applies light tokens', () => {
    applyTheme({ mode: 'light', accent: 'rose', fontScale: 1 })
    const root = document.documentElement
    expect(root.getAttribute('data-theme')).toBe('light')
    expect(root.classList.contains('dark')).toBe(false)
    expect(root.style.getPropertyValue('--accent')).toBe(ACCENTS.rose)
  })

  it('applies font scale', () => {
    applyTheme({ mode: 'dark', accent: 'indigo', fontScale: 1.1 })
    expect(parseFloat(document.documentElement.style.fontSize)).toBeCloseTo(15.4, 1)
  })
})