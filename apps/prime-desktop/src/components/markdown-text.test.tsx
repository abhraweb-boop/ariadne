/**
 * B1 — MarkdownText tests: headings/code/tables/links render; code copy button.
 *
 * @vitest-environment jsdom
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { MarkdownText } from './markdown-text'

afterEach(cleanup)

describe('MarkdownText', () => {
  it('renders headings', () => {
    render(<MarkdownText text={'# Title\n\nSome **bold** text'} />)
    expect(screen.getByRole('heading', { level: 1, name: 'Title' })).toBeTruthy()
    // bold text is split across <strong> — match by substring
    expect(screen.getByText((content) => content.includes('bold'))).toBeTruthy()
  })

  it('renders code blocks with copy button', () => {
    render(<MarkdownText text={'```ts\nconst x = 1\n```'} />)
    expect(screen.getByText('const x = 1')).toBeTruthy()
    expect(screen.getByText('copy')).toBeTruthy()
    expect(screen.getByText('ts')).toBeTruthy()
  })

  it('renders tables', () => {
    render(<MarkdownText text={'| A | B |\n|---|---|\n| 1 | 2 |'} />)
    // table cells render as text; use substring matching
    expect(screen.getByText((content) => content.includes('A'))).toBeTruthy()
    expect(screen.getByText((content) => content.includes('2'))).toBeTruthy()
  })

  it('renders links', () => {
    render(<MarkdownText text={'[docs](https://example.com)'} />)
    const link = screen.getByRole('link', { name: 'docs' }) as HTMLAnchorElement
    expect(link.href).toBe('https://example.com/')
  })

  it('handles empty text', () => {
    const { container } = render(<MarkdownText text="" />)
    expect(container.innerHTML).not.toBeNull()
  })
})