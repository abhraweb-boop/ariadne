/**
 * S4 — Plan recipes: named, reusable plan templates with {{slot}} variables.
 *
 * Pure client-side store over localStorage; a recipe is a task list in the
 * same shape the DAG composer produces. When materializing, {{slots}} are
 * substituted from a values map (or left literal if unset).
 */

export interface RecipeTask {
  title: string
  kind: string
  payload: Record<string, string>
  depends_on: string[]
}

export interface Recipe {
  id: string
  name: string
  goal: string
  tasks: RecipeTask[]
  createdAt: number
}

const KEY = 'prime-hermes-recipes'

export function listRecipes(): Recipe[] {
  try {
    const raw = localStorage.getItem(KEY)

    if (!raw) {return []}
    const parsed = JSON.parse(raw) as Recipe[]

    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveRecipe(name: string, goal: string, tasks: RecipeTask[]): Recipe {
  const recipes = listRecipes()

  const recipe: Recipe = {
    id: `recipe-${Date.now()}`,
    name,
    goal,
    tasks,
    createdAt: Date.now()
  }

  // Upsert by name (keep it simple — a name is the identity).
  const without = recipes.filter((r) => r.name !== name)
  without.push(recipe)
  localStorage.setItem(KEY, JSON.stringify(without))

  return recipe
}

export function deleteRecipe(name: string): void {
  localStorage.setItem(
    KEY,
    JSON.stringify(listRecipes().filter((r) => r.name !== name))
  )
}

/** Slot regex — {{word}} style, word can contain dashes/underscores. */
const SLOT_RE = /\{\{([a-zA-Z0-9_-]+)\}\}/g

export function extractSlots(tasks: RecipeTask[]): string[] {
  const slots = new Set<string>()

  for (const t of tasks) {
    for (const m of t.title.matchAll(SLOT_RE)) {slots.add(m[1])}

    for (const v of Object.values(t.payload)) {
      for (const m of v.matchAll(SLOT_RE)) {slots.add(m[1])}
    }
  }

  return [...slots]
}

export function materializeRecipe(recipe: Recipe, values: Record<string, string>): RecipeTask[] {
  return recipe.tasks.map((t) => ({
    ...t,
    title: substitute(t.title, values),
    payload: Object.fromEntries(
      Object.entries(t.payload).map(([k, v]) => [k, substitute(v, values)])
    )
  }))
}

function substitute(text: string, values: Record<string, string>): string {
  return text.replace(SLOT_RE, (_, name: string) => values[name] ?? `{{${name}}}`)
}
