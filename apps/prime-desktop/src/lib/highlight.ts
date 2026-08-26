/**
 * A4 — Highlight utility (pure, testable).
 *
 * Splits text into segments marking which parts match a case-insensitive
 * query. The transcript renderer colors the `match` segments.
 */

export interface Segment {
  text: string
  match: boolean
}

export function highlightSegments(text: string, query: string): Segment[] {
  if (!query) {return [{ text, match: false }]}
  const q = query.toLowerCase()
  const lower = text.toLowerCase()
  const segments: Segment[] = []
  let cursor = 0

  while (cursor < text.length) {
    const idx = lower.indexOf(q, cursor)

    if (idx === -1) {
      segments.push({ text: text.slice(cursor), match: false })

      break
    }

    if (idx > cursor) {
      segments.push({ text: text.slice(cursor, idx), match: false })
    }

    segments.push({ text: text.slice(idx, idx + q.length), match: true })
    cursor = idx + q.length
  }

  return segments
}

export interface MatchLocation {
  messageIndex: number
  textIndex: number
}

/** All matches across messages (flattened for prev/next navigation). */
export function findMatches(
  messages: Array<{ role: string; text: string }>,
  query: string
): Array<{ messageIndex: number; textIndex: number }> {
  if (!query) {return []}
  const q = query.toLowerCase()
  const matches: Array<{ messageIndex: number; textIndex: number }> = []

  messages.forEach((m, mi) => {
    const lower = m.text.toLowerCase()
    let idx = lower.indexOf(q)

    while (idx !== -1) {
      matches.push({ messageIndex: mi, textIndex: idx })
      idx = lower.indexOf(q, idx + q.length)
    }
  })

  return matches
}
