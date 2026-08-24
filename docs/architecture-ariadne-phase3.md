# Ariadne — Architecture (Phase 3): Context Graph + Waterfall Loader

Status: Phase 3 design · Owner: Ariadne (Hermes fork) · Date: 2026-08-24
Supplements `docs/architecture-ariadne-phase2.md`.

## 0. Goal

Make Ariadne's work **legible and loadable as a graph**. Every file, memory,
skill, child-agent, and tool touch becomes a node; every causal relation
becomes an edge. Tasks then recall their *subgraph* (waterfall loader) instead
of relying on linear transcript replay. This is the differentiator neither
upstream ships, and the substrate Phase 4's desktop UI renders.

## 1. Source behavior (Prime parity where it exists)

Prime has no context graph. We keep its two governing rules anyway:
- supplemental state only — never mutates past conversation context mid-session
  (cache-safety invariant);
- everything derived is versioned/inspectable, nothing silently overwritten.

## 2. Design decisions

### D1. Recording rides the existing `post_tool_call` observer hook

`plugins/context_graph/__init__.py::register(ctx)` registers a
`post_tool_call` callback (same pattern as disk-cleanup). Zero core-file
edits. The recorder maps tool calls to nodes/edges:

| Tool | Nodes | Edges |
|---|---|---|
| read_file/write_file/patch/search_files | file:<path> | touched-by(session) |
| terminal | cmd:<first token> | ran-in(session) |
| web_search/web_extract | url:<domain/path> | fetched-by |
| ariadne_memory add/update/delete | mem:<entry_id> | refined-into |
| ariadne_kernel run | kernel-cell | produced → files it wrote |
| rlm admission / delegate | agent:<child_id> | spawned-by(parent session) |

Edges carry `weight` (recency×frequency) and `last_seen`; recording is
idempotent per (src, rel, dst) with weight bump on repeat.

### D2. Storage: SQLite in the same DB family as the ledger

`<HERMES_HOME>/ariadne/graph.db`: `nodes(id TEXT pk, type TEXT, key TEXT,
title TEXT, meta JSON, first_seen, last_seen)` +
`edges(src TEXT, rel TEXT, dst TEXT, weight REAL, last_seen,
PRIMARY KEY(src,rel,dst))` + WAL. Node ids are `<type>:<key>`.

### D3. One provider-style tool: `ariadne_graph`

Injected by the same plugin via a lightweight registry registration scoped to
the plugin's own toolset (`context` toolset family) so MemoryManager routing
isn't abused for non-memory tools. Actions:

- `related(node_or_text, depth=2, limit=20)` — BFS subgraph from a node or
  FTS-ish keyword match over node titles.
- `timeline(node, limit)` — when this node was touched, by which sessions.
- `stats()` / `prune(older_than_days)` / `export(limit)`.

### D4. Waterfall loader = prefetch injection, visualize-first

Per turn, before the model call, the loader takes the current prompt as query:
1. match seed nodes by keyword;
2. expand `depth≤2`, ranked by edge weight × node recency;
3. pack top-N nodes into a bounded `<context-graph>` block injected like
   memory recall (user-message context, never system prompt mutation).

Budgets: ≤12 nodes, ≤1200 chars default. This is "visualize-first": the graph
*informs* turns without claiming to replace transcript replay yet.

### D5. Recording is fail-open and cheap

Recorder exceptions never break tool execution (hook wrapper already isolates);
writes are batched in-memory and flushed on session end + every N ops. No
dedupe locks needed beyond SQLite PK upserts.

## 3. Module layout

```
plugins/context_graph/__init__.py   # register(ctx), post_tool_call tap, tool schema+handler
plugins/context_graph/store.py      # GraphStore: nodes/edges/upsert/BFS/prune
tests/ariadne/test_context_graph.py # store + recorder + loader tests
```

## 4. Exit gates

1. Store unit tests: upsert idempotency, weight bumps, BFS depth/rank, prune.
2. Recorder tests: synthetic post_tool_call payloads produce expected
   nodes/edges (file, terminal, memory, rlm).
3. Live gate: session A reads/edits files; fresh session B asks about them and
   gets the subgraph injected/recalled; `stats()` shows real counts.
