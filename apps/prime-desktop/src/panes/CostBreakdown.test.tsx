/**
 * G3 — CostBreakdown tests.
 * @vitest-environment jsdom
 */
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { CostBreakdown } from './CostBreakdown'

afterEach(cleanup)
describe('CostBreakdown', () => {
  it('shows empty state', () => {
    render(<CostBreakdown onClose={() => {}} />)
    expect(screen.getByText(/No token data collected/)).toBeTruthy()
  })
  it('renders total header', () => {
    render(<CostBreakdown onClose={() => {}} />)
    expect(screen.getByText('total: 0')).toBeTruthy()
  })
  it('renders cost icon', () => {
    render(<CostBreakdown onClose={() => {}} />)
    expect(screen.getByText(/Cost & tokens/)).toBeTruthy()
  })
})