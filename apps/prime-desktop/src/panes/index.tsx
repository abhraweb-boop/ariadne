/**
 * Pane registry — all Prime Hermes surfaces registered here.
 * Imported by shell.tsx to populate the navigation rail.
 */

import { lazy, Suspense } from 'react'

import { FilesPane } from './FilesPane'
import { CostBreakdown } from './CostBreakdown'
import { registerPane } from './registry'
import { ReviewPane } from './ReviewPane'
import { TerminalPane } from './TerminalPane'

export function registerAllPanes() {
  // Lazy imports — each pane is a separate file, loaded on first open.
  registerPane({
    id: 'dags',
    label: 'DAG Board',
    icon: '🔀',
    render: (props) => {
      const DagBoard = lazy(() =>
        import('../dags/DagBoard').then((m) => ({ default: m.DagBoard }))
      )

      return (
        <Suspense fallback={null}>
          <DagBoard {...props} />
        </Suspense>
      )
    }
  })
  registerPane({
    id: 'kernel',
    label: 'Kernel',
    icon: '⚡',
    render: (props) => {
      const KernelConsole = lazy(() =>
        import('./KernelConsole').then((m) => ({ default: m.KernelConsole }))
      )

      return (
        <Suspense fallback={null}>
          <KernelConsole {...props} />
        </Suspense>
      )
    }
  })
  registerPane({
    id: 'agents',
    label: 'Agents',
    icon: '👾',
    render: (props) => {
      const Agents = lazy(() =>
        import('./Agents').then((m) => ({ default: m.Agents }))
      )

      return (
        <Suspense fallback={null}>
          <Agents {...props} />
        </Suspense>
      )
    }
  })
  registerPane({
    id: 'graph',
    label: 'Graph',
    icon: '🕸',
    render: (props) => {
      const GraphLens = lazy(() =>
        import('./GraphLens').then((m) => ({ default: m.GraphLens }))
      )

      return (
        <Suspense fallback={null}>
          <GraphLens {...props} />
        </Suspense>
      )
    }
  })
  registerPane({
    id: 'files',
    label: 'Files',
    icon: '📁',
    render: (props) => <FilesPane {...props} />
  })
  registerPane({
    id: 'terminal',
    label: 'Terminal',
    icon: '🖥',
    render: (props) => <TerminalPane {...props} />
  })
  registerPane({
    id: 'cost',
    label: 'Cost',
    icon: '💸',
    render: (props) => <CostBreakdown {...props} />
  })
  registerPane({
    id: 'review',
    label: 'Review',
    icon: '🔍',
    render: (props) => <ReviewPane {...props} />
  })
  registerPane({
    id: 'skills',
    label: 'Skills',
    icon: '📚',
    render: (props) => {
      const SkillsTools = lazy(() =>
        import('./SkillsToolsMCPs').then((m) => ({ default: m.SkillsToolsMCPs }))
      )

      return (
        <Suspense fallback={null}>
          <SkillsTools {...props} />
        </Suspense>
      )
    }
  })
  registerPane({
    id: 'ledger',
    label: 'Ledger',
    icon: '📓',
    render: (props) => {
      const Ledger = lazy(() =>
        import('./Ledger').then((m) => ({ default: m.Ledger }))
      )

      return (
        <Suspense fallback={null}>
          <Ledger {...props} />
        </Suspense>
      )
    }
  })
  registerPane({
    id: 'settings',
    label: 'Settings',
    icon: '⚙',
    render: (props) => {
      const Settings = lazy(() =>
        import('./Settings').then((m) => ({ default: m.Settings }))
      )

      return (
        <Suspense fallback={null}>
          <Settings {...props} />
        </Suspense>
      )
    }
  })
}
