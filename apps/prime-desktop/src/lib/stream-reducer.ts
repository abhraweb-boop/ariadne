/**
 * B3 — Streaming reducer (pure, testable).
 *
 * The shell's transcript uses this to accumulate text deltas and finalize
 * on agent_end, mirroring Hermes desktop's streaming feel.
 */

export interface StreamMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
}

let msgSeq = 0

export function nextMessageId(): string {
  return `msg-${Date.now()}-${msgSeq++}`
}

export type StreamAction =
  | { type: 'user'; text: string }
  | { type: 'delta'; delta: string }
  | { type: 'system'; text: string }
  | { type: 'finalize' }

export function streamReducer(state: StreamMessage[], action: StreamAction): StreamMessage[] {
  switch (action.type) {
    case 'user':
      return [...state, { id: nextMessageId(), role: 'user', text: action.text }]

    case 'system':
      return [...state, { id: nextMessageId(), role: 'system', text: action.text }]
    case 'delta': {
      const last = state[state.length - 1]

      if (last?.role === 'assistant') {
        const next = [...state]
        next[next.length - 1] = { ...last, text: last.text + action.delta }

        return next
      }

      return [...state, { id: nextMessageId(), role: 'assistant', text: action.delta }]
    }

    case 'finalize':
      // No structural change — finalize clears the streaming flag (handled by
      // the component via `sending` state). Kept for symmetry/tests.
      return state
  }
}
