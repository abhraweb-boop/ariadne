/**
 * A3 — Register all command-palette actions: panes from the registry,
 * sessions, plans, kernel, recipes, settings, cost breakdown.
 */

import { registerAction } from './actions'

export function registerCoreActions(handlers: {
  openPane: (id: string) => void
  newSession: () => void
}) {
  const { openPane, newSession } = handlers

  // Panes
  const panes = [
    { id: 'dags', label: 'Open DAG Board', keywords: ['dag', 'plan', 'board', 'tasks'] },
    { id: 'kernel', label: 'Open Kernel Console', keywords: ['kernel', 'cell', 'python', 'repl'] },
    { id: 'agents', label: 'Open Agents', keywords: ['agents', 'prime', 'worker', 'swarm'] },
    { id: 'graph', label: 'Open Graph Lens', keywords: ['graph', 'context', 'nodes'] },
    { id: 'files', label: 'Open Files', keywords: ['files', 'browse', 'workspace'] },
    { id: 'terminal', label: 'Open Terminal', keywords: ['terminal', 'shell'] },
    { id: 'review', label: 'Open Review', keywords: ['review', 'git', 'diff', 'changes'] },
    { id: 'cost', label: 'Open Cost Breakdown', keywords: ['cost', 'tokens', 'spend'] },
    { id: 'skills', label: 'Open Skills & Tools', keywords: ['skills', 'tools', 'mcp'] },
    { id: 'ledger', label: 'Open Refine Ledger', keywords: ['ledger', 'memory', 'rollback', 'refine'] },
    { id: 'settings', label: 'Open Settings', keywords: ['settings', 'config', 'preferences'] }
  ]

  for (const p of panes) {
    registerAction({
      id: `pane:${p.id}`,
      label: p.label,
      keywords: p.keywords,
      category: 'Pane',
      run: () => openPane(p.id)
    })
  }

  // Core actions
  registerAction({
    id: 'session:new',
    label: 'New Session',
    keywords: ['new', 'session', 'chat', 'create'],
    category: 'Session',
    run: newSession
  })

  registerAction({
    id: 'plan:create',
    label: 'Create Plan',
    keywords: ['create', 'plan', 'dag', 'task'],
    category: 'Plan',
    run: () => openPane('dags')
  })

  registerAction({
    id: 'cost:breakdown',
    label: 'View Cost Breakdown',
    keywords: ['cost', 'tokens', 'spend', 'budget'],
    category: 'Monitoring',
    run: () => openPane('cost')
  })
}
