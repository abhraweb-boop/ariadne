/**
 * S4 recipes store — pure logic tests (localStorage mocked via happy path).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Minimal localStorage stub
const store = new Map<string, string>()
vi.stubGlobal('localStorage', {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => void store.set(k, v),
  removeItem: (k: string) => void store.delete(k)
})

import {
  deleteRecipe,
  extractSlots,
  listRecipes,
  materializeRecipe,
  type Recipe,
  saveRecipe
} from './recipes'

const SAMPLE_TASKS = [
  { title: 'fetch {{repo}} data', kind: 'note', payload: { text: 'get {{repo}}' }, depends_on: [] },
  { title: 'analyze {{repo}}', kind: 'note', payload: { text: 'analyze' }, depends_on: ['fetch {{repo}} data'] }
]

describe('recipes', () => {
  beforeEach(() => store.clear())
  afterEach(() => vi.restoreAllMocks())

  it('starts empty', () => {
    expect(listRecipes()).toEqual([])
  })

  it('saves and lists a recipe', () => {
    const r = saveRecipe('data-pipeline', 'Process {{repo}}', SAMPLE_TASKS)
    const all = listRecipes()
    expect(all).toHaveLength(1)
    expect(all[0].name).toBe('data-pipeline')
    expect(r.id).toMatch(/^recipe-/)
  })

  it('upserts by name', () => {
    saveRecipe('dup', 'goal one', SAMPLE_TASKS)
    saveRecipe('dup', 'goal two', SAMPLE_TASKS)
    const all = listRecipes()
    expect(all).toHaveLength(1)
    expect(all[0].goal).toBe('goal two')
  })

  it('deletes by name', () => {
    saveRecipe('gone', 'g', SAMPLE_TASKS)
    deleteRecipe('gone')
    expect(listRecipes()).toHaveLength(0)
  })

  it('extracts slots from titles and payloads', () => {
    const slots = extractSlots(SAMPLE_TASKS)
    expect(slots).toEqual(['repo'])
  })

  it('materializes with slot substitution', () => {
    const recipe: Recipe = {
      id: 'r1', name: 'n', goal: 'g', createdAt: 0,
      tasks: SAMPLE_TASKS
    }

    const out = materializeRecipe(recipe, { repo: 'ariadne' })
    expect(out[0].title).toBe('fetch ariadne data')
    expect(out[0].payload.text).toBe('get ariadne')
    expect(out[1].depends_on[0]).toBe('fetch {{repo}} data') // deps stay literal
  })

  it('leaves unset slots literal', () => {
    const recipe: Recipe = { id: 'r1', name: 'n', goal: 'g', createdAt: 0, tasks: SAMPLE_TASKS }
    const out = materializeRecipe(recipe, {})
    expect(out[0].title).toBe('fetch {{repo}} data')
  })
})
