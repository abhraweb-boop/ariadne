/**
 * B3 — Streaming reducer tests.
 */

import { describe, expect, it } from 'vitest'

import { type StreamMessage, streamReducer } from './stream-reducer'

describe('streamReducer', () => {
  it('adds user message', () => {
    const r = streamReducer([], { type: 'user', text: 'hello' })
    expect(r).toHaveLength(1)
    expect(r[0].role).toBe('user')
    expect(r[0].text).toBe('hello')
  })

  it('accumulates text deltas', () => {
    let msgs: StreamMessage[] = [{ id: 'm1', role: 'user', text: 'hi' }]
    msgs = streamReducer(msgs, { type: 'delta', delta: 'hel' })
    expect(msgs).toHaveLength(2)
    expect(msgs[1].text).toBe('hel')
    msgs = streamReducer(msgs, { type: 'delta', delta: 'lo' })
    expect(msgs[1].text).toBe('hello')
  })

  it('appends delta to existing assistant message', () => {
    let msgs: StreamMessage[] = [
      { id: 'm1', role: 'user', text: 'hi' },
      { id: 'm2', role: 'assistant', text: 'hel' }
    ]

    msgs = streamReducer(msgs, { type: 'delta', delta: 'lo' })
    expect(msgs).toHaveLength(2)
    expect(msgs[1].text).toBe('hello')
  })

  it('finalize does not change state', () => {
    const msgs: StreamMessage[] = [{ id: 'm1', role: 'assistant', text: 'done' }]
    expect(streamReducer(msgs, { type: 'finalize' })).toBe(msgs)
  })
})