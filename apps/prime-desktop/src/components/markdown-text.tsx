/**
 * B1 — Markdown transcript renderer.
 *
 * Port of Hermes desktop's markdown-text surface, using react-markdown.
 * Code blocks get a copy button; tables render; links open externally.
 * Streaming text (B3) renders through the same component.
 */

import { memo, useCallback, useState } from 'react'
import ReactMarkdown from 'react-markdown'

function CodeBlock({ code, lang }: { code: string; lang?: string }) {
  const [copied, setCopied] = useState(false)

  const copy = useCallback(() => {
    void navigator.clipboard?.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }, [code])

  return (
    <div style={{ margin: '6px 0', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border, #2a2a2a)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '2px 8px', background: 'color-mix(in srgb, var(--foreground, #efefef) 4%, transparent)' }}>
        <span style={{ fontSize: 10, color: 'var(--muted-foreground, #888)', flex: 1 }}>
          {lang || 'code'}
        </span>
        <button
          onClick={copy}
          style={{
            background: 'transparent',
            border: 'none',
            borderRadius: 4,
            padding: '2px 8px',
            color: 'var(--muted-foreground, #888)',
            cursor: 'pointer',
            fontSize: 10,
            fontFamily: 'inherit'
          }}
        >
          {copied ? '✓ copied' : 'copy'}
        </button>
      </div>
      <pre
        style={{
          margin: 0,
          padding: 8,
          fontSize: 12,
          overflow: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontFamily: 'monospace'
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  )
}

export const MarkdownText = memo(function MarkdownText({ text }: { text: string }) {
  return (
    <div style={{ fontSize: 13, lineHeight: 1.5 }}>
      <ReactMarkdown
        components={{
          code({ className, children }) {
            const lang = /language-(\w+)/.exec(className ?? '')?.[1]
            const code = String(children ?? '')

            // Inline code (no language + single line) stays inline.
            if (!lang && !code.includes('\n')) {
              return (
                <code
                  style={{
                    background: 'color-mix(in srgb, var(--foreground, #efefef) 8%, transparent)',
                    borderRadius: 4,
                    padding: '1px 5px',
                    fontSize: 12,
                    fontFamily: 'monospace'
                  }}
                >
                  {children}
                </code>
              )
            }

            return <CodeBlock code={code} lang={lang} />
          },
          a({ href, children }) {
            return (
              <a href={href} rel="noreferrer" style={{ color: 'var(--accent, #5e6ad2)' }} target="_blank">
                {children}
              </a>
            )
          },
          table({ children }) {
            return (
              <div style={{ overflow: 'auto', margin: '6px 0' }}>
                <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>{children}</table>
              </div>
            )
          },
          th({ children }) {
            return <th style={{ border: '1px solid var(--border, #2a2a2a)', padding: '4px 8px', textAlign: 'left' }}>{children}</th>
          },
          td({ children }) {
            return <td style={{ border: '1px solid var(--border, #2a2a2a)', padding: '4px 8px' }}>{children}</td>
          }
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
})
