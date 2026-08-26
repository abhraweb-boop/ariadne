/**
 * F1 — PageLoader + StatusDot tests.
 *
 * @vitest-environment jsdom
 */

import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'

import { PageLoader } from './page-loader'
import { StatusDot } from './status-dot'

describe('PageLoader', () => {
  it('renders branding + connecting text', () => {
    render(<PageLoader />)
    expect(screen.getByText('Prime Hermes')).toBeTruthy()
    expect(screen.getByText('Connecting to gateway…')).toBeTruthy()
  })
})

describe('StatusDot', () => {
  it('renders with state color', () => {
    const { container } = render(<StatusDot state="connected" />)
    const dot = container.querySelector('span')
    expect(dot?.style.background).toBe('rgb(158, 206, 106)')
  })

  it('renders offline red', () => {
    const { container } = render(<StatusDot state="offline" />)
    const dot = container.querySelector('span')
    expect(dot?.style.background).toBe('rgb(247, 118, 142)')
  })

  it('has accessible label', () => {
    render(<StatusDot state="busy" label="kernel busy" />)
    expect(screen.getByLabelText('kernel busy')).toBeTruthy()
  })
})