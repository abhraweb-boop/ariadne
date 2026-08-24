---
name: refine
description: Review the current session trajectory and persist small, evidence-backed improvements into the Ariadne memory ledger. Every edit is versioned and rollback-able.
version: 1.0.0
author: Ariadne (Prime Agent /refine absorbed)
license: MIT
platforms: [linux, macos, windows]
---

# Refine

Refinement reviews what actually happened in this conversation — failures hit,
tactics that worked, user corrections, reusable patterns — and applies **small,
evidence-backed edits** to the Ariadne memory ledger (`ariadne_memory` tool).
The ledger versions every change automatically; nothing is ever silently
overwritten.

## When to refine

Refine after observing any of:

- a repeated failure or tool quirk worth remembering
- a tactic that measurably worked this session
- an explicit user correction or preference
- a delegation pattern that deserves a `subagent_spec` entry
- a behavior policy you want future sessions to follow

Do NOT refine when one focused entry is not enough to describe the change —
that is a sign the "improvement" is too broad.

## Procedure

1. **Review** the trajectory. Identify at most 5 candidate improvements.
2. For each candidate, require **evidence**: cite what happened (a failed
   command, a user sentence, a repeated result). No evidence → skip it.
3. Classify each edit:
   - environment fact / project convention → kind `memory`
   - communication preference → kind `user`
   - how a skill/tool should be used here → kind `skill_desc`
   - standing instruction for future sessions → kind `prompt_note`
   - reusable child-agent role → kind `subagent_spec`
4. Apply each edit via `ariadne_memory` with its `evidence` string filled in:
   - new knowledge → action `add`
   - correction of an existing entry (find id via `search`) → action `update`
   - obsolete/wrong entry → action `delete`
5. Before finishing, take a checkpoint: `action=snapshot`,
   `label="post-refine <topic>"`. This makes the whole batch reversible via
   `restore_snapshot`.

## Rules

- NEVER rewrite everything — small focused edits only (≤5 per refine run).
- NEVER modify skill files on disk, the base system prompt, or another agent's
  stores. The ledger is supplemental state, exactly like Prime's harness.
- Every write MUST carry non-empty `evidence` describing the observed cause.
- Prefer `update` of an existing near-duplicate over adding a redundant entry;
  search before you add.
- Entries are frozen into the NEXT session's prompt snapshot; mid-session they
  are durable but do not re-render past context (cache-safety).

## Rollback

`history` lists version chains; `rollback` restores one entry to a prior
version; `snapshot`/`restore_snapshot` cover whole-store checkpoints.
