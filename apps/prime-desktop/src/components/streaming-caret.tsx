/**
 * B3 — StreamingCaret. Blinking cursor rendered after the last assistant
 * message while the agent streams; removed when the turn finalizes.
 */

export function StreamingCaret() {
  return (
    <span
      aria-label="streaming"
      data-testid="streaming-caret"
      style={{
        display: 'inline-block',
        width: 7,
        height: 14,
        marginLeft: 2,
        background: 'var(--accent, #5e6ad2)',
        verticalAlign: 'text-bottom',
        animation: 'ph-caret 1s steps(1) infinite'
      }}
    />
  )
}
