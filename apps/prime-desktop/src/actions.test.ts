/**
 * H2 — actions.ts tests.
 *
 * @vitest-environment jsdom
 */

import { describe, expect, it } from 'vitest'

import { registerAction, searchActions } from './actions'

describe('actions', () => {
  it('registers and searches actions', () => {
    registerAction({ id: 'a1', label: 'Open DAG Board', category: 'panes', keywords: ['dag', 'board'], run: () => {} })
    registerAction({ id: 'a2', label: 'Open Kernel', category: 'panes', keywords: ['kernel'], run: () => {} })
    const results = searchActions('dag')
    expect(results.some((a) => a.id === 'a1')).toBe(true)
    expect(results.some((a) => a.id === 'a2')).toBe(false)
  })

  it('matches by keyword', () => {
    registerAction({ id: 'cost', label: 'Cost Breakdown', category: 'panes', keywords: ['tokens', 'usage'], run: () => {} })
    expect(searchActions('tokens').some((a) => a.id === 'cost')).toBe(true)
    expect(searchActions('money').some((a) => a.id === 'cost')).toBe(false)
  })
})