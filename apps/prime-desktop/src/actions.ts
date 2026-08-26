/**
 * Action registry — used by the command palette (A3) and shell integration (G1).
 *
 * Each action has an id, label, search keywords, and a run function.
 * Panes and shortcuts register themselves here; the palette finds them.
 */

export interface Action {
  id: string
  label: string
  keywords: string[]
  category: string
  run: () => void
}

const registry = new Map<string, Action>()

export function registerAction(action: Action): void {
  registry.set(action.id, action)
}

export function searchActions(query: string): Action[] {
  if (!query.trim()) {return [...registry.values()]}
  const q = query.toLowerCase()

  return [...registry.values()].filter(
    (a) =>
      a.label.toLowerCase().includes(q) ||
      a.keywords.some((k) => k.toLowerCase().includes(q))
  )
}

export function getAllActions(): Action[] {
  return [...registry.values()]
}