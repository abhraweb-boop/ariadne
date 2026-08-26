/**
 * A4 — highlight utility tests.
 */

import { describe, expect, it } from 'vitest'

import { findMatches, highlightSegments } from './highlight'

describe('highlightSegments', () => {
  it('returns empty segment for empty query', () => {
    expect(highlightSegments('hello', '')).toEqual([{ text: 'hello', match: false }])
  })

  it('highlights matching substring', () => {
    expect(highlightSegments('hello world', 'lo')).toEqual([
      { text: 'hel', match: false },
      { text: 'lo', match: true },
      { text: ' world', match: false }
    ])
  })

  it('is case-insensitive', () => {
    expect(highlightSegments('Hello World', 'world')).toEqual([
      { text: 'Hello ', match: false },
      { text: 'World', match: true }
    ])
  })

  it('handles multiple matches', () => {
    expect(highlightSegments('test test test', 'test')).toEqual([
      { text: 'test', match: true },
      { text: ' ', match: false },
      { text: 'test', match: true },
      { text: ' ', match: false },
      { text: 'test', match: true }
    ])
  })

  it('no matches returns full text as non-match', () => {
    expect(highlightSegments('hello', 'xyz')).toEqual([{ text: 'hello', match: false }])
  })
})

describe('findMatches', () => {
  it('finds matches across messages', () => {
    const msgs = [
      { role: 'user', text: 'hello world' },
      { role: 'assistant', text: 'hello again' }
    ]

    const matches = findMatches(msgs, 'hello')
    expect(matches).toHaveLength(2)
    expect(matches[0]).toEqual({ messageIndex: 0, textIndex: 0 })
    expect(matches[1]).toEqual({ messageIndex: 1, textIndex: 0 })
  })

  it('returns empty for empty query', () => {
    expect(findMatches([{ role: 'user', text: 'hello' }], '')).toEqual([])
  })

  it('returns empty for no matches', () => {
    expect(findMatches([{ role: 'user', text: 'hello' }], 'xyz')).toEqual([])
  })
})