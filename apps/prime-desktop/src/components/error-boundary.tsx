/**
 * A5 — Error boundary (port of Hermes desktop error-boundary).
 * Catches pane render errors; shows a recover card instead of a white screen.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  onReset?: () => void
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[prime-hermes] render error:', error, info.componentStack)
  }

  handleReset = (): void => {
    this.setState({ error: null })
    this.props.onReset?.()
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div
          role="alert"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
            height: '100%',
            padding: 24,
            textAlign: 'center',
            background: 'var(--background, #101012)'
          }}
        >
          <span style={{ fontSize: 28 }}>⚠️</span>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--foreground, #efefef)' }}>
            Something went wrong
          </div>
          <div
            style={{
              fontSize: 12,
              color: 'var(--muted-foreground, #888)',
              maxWidth: 480,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word'
            }}
          >
            {this.state.error.message}
          </div>
          <button
            onClick={this.handleReset}
            style={{
              background: 'var(--accent, #5e6ad2)',
              border: 'none',
              borderRadius: 6,
              padding: '6px 16px',
              color: '#fff',
              cursor: 'pointer',
              fontSize: 13,
              fontFamily: 'inherit'
            }}
          >
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
