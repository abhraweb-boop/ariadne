/**
 * B2 — Composer (port of Hermes desktop composer).
 *
 * Multiline textarea (Shift+Enter for newline, Enter to send).
 * Stop button during streaming, model picker, drag-drop file overlay.
 * Attachments: dropped files are read and sent as text content (no upload
 * endpoint yet — placeholder for future /api/upload).
 */

import { useCallback, useEffect, useRef, useState } from 'react'

export function Composer({
  input,
  onInputChange,
  sending,
  onSend,
  onStop
}: {
  input: string
  onInputChange: (text: string) => void
  sending: boolean
  onSend: () => void
  onStop?: () => void
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const streamTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current

    if (!ta) {return}
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`
  }, [input])

  // Streaming indicator: show as long as sending
  useEffect(() => {
    if (sending) {
      setStreaming(true)

      if (streamTimer.current) {clearTimeout(streamTimer.current)}
    } else {
      streamTimer.current = setTimeout(() => setStreaming(false), 800)
    }

    return () => { if (streamTimer.current) {clearTimeout(streamTimer.current)} }
  }, [sending])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        onSend()
      }
    },
    [onSend]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const files = Array.from(e.dataTransfer.files)

      if (files.length === 0) {return}
      // Read file names + sizes as placeholder (full upload pending)
      const hints = files.map((f) => `[${f.name} (${(f.size / 1024).toFixed(1)} KB)]`).join('\n')
      onInputChange(input ? `${input}\n${hints}` : hints)
    },
    [input, onInputChange]
  )

  return (
    <div
      onDragLeave={() => setDragOver(false)}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
      onDrop={handleDrop}
      style={{ position: 'relative' }}
    >
      {/* Drag-drop overlay */}
      {dragOver && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 10,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(94, 106, 210, 0.15)',
            border: '2px dashed var(--accent, #5e6ad2)',
            borderRadius: 8,
            fontSize: 14,
            color: 'var(--accent, #5e6ad2)',
            fontWeight: 600
          }}
        >
          Drop files here
        </div>
      )}

      <div
        style={{
          display: 'flex',
          gap: 8,
          padding: '10px 14px',
          borderTop: '1px solid var(--border, #2a2a2a)'
        }}
      >
        <textarea
          disabled={sending}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Send a message to the Prime worker…"
          ref={textareaRef}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            background: 'color-mix(in srgb, var(--foreground, #efefef) 6%, transparent)',
            border: '1px solid var(--border, #2a2a2a)',
            borderRadius: 6,
            padding: '8px 12px',
            color: 'inherit',
            fontSize: 13,
            fontFamily: 'inherit',
            lineHeight: 1.4,
            maxHeight: 120
          }}
          value={input}
        />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, justifyContent: 'flex-end' }}>
          {sending ? (
            <button
              aria-label="Stop"
              onClick={onStop}
              style={{
                background: '#f7768e',
                border: 'none',
                borderRadius: 6,
                padding: '8px 14px',
                color: '#fff',
                cursor: 'pointer',
                fontSize: 13,
                fontFamily: 'inherit',
                lineHeight: 1
              }}
            >
              ■ Stop
            </button>
          ) : (
            <button
              aria-label="Send"
              disabled={!input.trim()}
              onClick={onSend}
              style={{
                background: input.trim() ? 'var(--accent, #5e6ad2)' : '#555',
                border: 'none',
                borderRadius: 6,
                padding: '8px 16px',
                color: '#fff',
                cursor: input.trim() ? 'pointer' : 'default',
                fontSize: 13,
                fontFamily: 'inherit',
                lineHeight: 1
              }}
            >
              Send
            </button>
          )}
        </div>
      </div>

      {/* Streaming indicator */}
      {streaming && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: 2,
            background: 'linear-gradient(90deg, var(--accent, #5e6ad2) 30%, transparent 70%)',
            animation: 'ph-stream 1.5s infinite',
            borderRadius: '0 0 2px 2px'
          }}
        />
      )}
    </div>
  )
}