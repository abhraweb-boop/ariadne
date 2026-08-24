# Ariadne — Architecture (Phase 4): Desktop Context-Graph Panel

Status: Phase 4 design · Owner: Ariadne · Date: 2026-08-24
Built from 5 inspiration-research passes (graph UI SOTA, anti-slop tells,
timeline surfaces, selection-inspect-steer, dark-theme tokens) + the
desktop AGENTS.md/DESIGN.md contracts.

## 0. Research distilled → binding principles

From the graph-SOTA pass:
- P1 Global view is diagnosis, not navigation. Default = local subgraph of the
  active session; global view is an explicit health-check mode.
- P2 Deterministic layout, computed once. No visible physics reheat; positions
  must be memorizable across opens.
- P3 Hierarchical/deterministic layout (layered, e.g. ELK/Dagre thinking) over
  force simulation for dependency-shaped data.
- P4 Selection-inspection is one model with two projections (Figma rule):
  canvas node ↔ list row, always synchronized.

From the timeline pass:
- P5 Order by sequence (lanes), annotate time as a column — never a time-axis
  layout driver (git clients).
- P6 Node types distinguished by shape+one hue family each, not rainbow.

From selection-inspect-steer:
- P7 Progressive disclosure: canvas shows identity; side inspector reveals
  metadata/actions for the single selected node.
- P8 Destructive actions (prune) are two-step with explicit scope shown.

From the tokens pass + anti-slop report (binding checklist in research file):
- P9 ≤3 hues + neutral ramp; color encodes semantics only; flat surfaces,
  1px borders, no gradients/glow/glass; all transitions <300ms;
  `prefers-reduced-motion` honored; honest empty/error states; no hero copy.

## 1. Architecture (seams respected)

Three-party split per desktop AGENTS.md:
- Backend authoritative: new REST `/api/ariadne/graph/*` (shipped, tested)
  over plugins/context_graph store. Renderer caches, never owns.
- Renderer owns: view mode, selection, filters, layout options.
- Electron untouched (no new capabilities needed).

## 2. Component plan

```
src/app/graph/                 # new contributed full-page route /graph
  index.tsx                    # GraphView page (lazy-loaded like starmap)
  api.ts                       # typed client over window.hermesDesktop.api
  use-graph.ts                 # query hooks (related/stats/timeline/prune)
  graph-canvas.tsx             # deterministic layered layout, SVG<500 nodes /
                               #   canvas fallback beyond
  node-list.tsx                # synchronized list projection (P4)
  inspector.tsx                # selected-node detail + timeline + actions
  toolbar.tsx                  # session filter, depth, view toggle, prune
  colors.ts                    # type->hue map (P9 tokens)
routes.ts                      # register GRAPH_ROUTE '/graph'
```

Layout algorithm: deterministic layered by node-type rank (session → mem →
file/cmd/web/url/search), ordered by last_seen within rank; simple lane
assignment, no simulation. Stable across opens (P2). Zoom via wheel with
label decluttering thresholds; pan via drag.

## 3. Views

1. **Session subgraph (default)** — nodes touched by the selected session,
   laid out by type-rank lanes (P5/P3).
2. **Related** — keyword-seeded ranked subgraph (powers search box).
3. **Overview (diagnostic)** — all-node density map, explicitly labeled as
   health-check (P1); orphans highlighted, not hidden.

Inspector shows: title/type/touches/first-last seen, meta JSON pretty,
timeline events, actions: copy id, focus in canvas.

## 4. Gates

1. `npm run check` clean in apps/desktop.
2. Panel renders real data from live-home graph.db through REST.
3. Anti-slop checklist (research file) run and passing.
4. Deterministic-layout test: two mounts produce identical positions.
