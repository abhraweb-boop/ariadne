/**
 * E1 — Theme engine (port of Hermes desktop theme context).
 *
 * Dark/light via CSS custom properties on :root / [data-theme="light"],
 * accent override, font scale. Backend-synced preference stored under a
 * scoped key (desktop AGENTS.md: persisted state declares its scope).
 */

export type ThemeMode = 'dark' | 'light'
export type Accent = 'indigo' | 'green' | 'amber' | 'rose'

export interface ThemePrefs {
  mode: ThemeMode
  accent: Accent
  fontScale: number // 0.9 .. 1.15
}

export const THEME_STORAGE_KEY = 'prime-hermes:theme:prefs'

export const ACCENTS: Record<Accent, string> = {
  indigo: '#5e6ad2',
  green: '#3f9e6a',
  amber: '#c98a2b',
  rose: '#c95e6a'
}

export const DEFAULT_PREFS: ThemePrefs = {
  mode: 'dark',
  accent: 'indigo',
  fontScale: 1
}

export function loadPrefs(): ThemePrefs {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY)

    if (!raw) {return DEFAULT_PREFS}
    const parsed = JSON.parse(raw) as Partial<ThemePrefs>

    return {
      mode: parsed.mode === 'light' ? 'light' : 'dark',
      accent: (parsed.accent && ACCENTS[parsed.accent]) ? parsed.accent : DEFAULT_PREFS.accent,
      fontScale: typeof parsed.fontScale === 'number' ? parsed.fontScale : DEFAULT_PREFS.fontScale
    }
  } catch {
    return DEFAULT_PREFS
  }
}

export function savePrefs(prefs: ThemePrefs): void {
  localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(prefs))
}

/** Apply prefs to the document root; idempotent. */
export function applyTheme(prefs: ThemePrefs): void {
  const root = document.documentElement
  // V: Hermes token layer — `:root` is light by default, `.dark` toggles dark.
  root.classList.toggle('dark', prefs.mode === 'dark')
  root.setAttribute('data-theme', prefs.mode)
  // Accent override: Hermes uses --theme-primary as the accent seed.
  root.style.setProperty('--theme-primary', ACCENTS[prefs.accent])
  root.style.setProperty('--theme-midground', ACCENTS[prefs.accent])
  root.style.setProperty('--accent', ACCENTS[prefs.accent])
  root.style.fontSize = `${prefs.fontScale * 14}px`
}
