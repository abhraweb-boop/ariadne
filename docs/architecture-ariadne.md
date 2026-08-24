# Ariadne — Architecture

Status: Phase 1 design · Owner: Ariadne (Hermes fork) · Date: 2026-08-24

## 0. What this documents

How the Prime Agent capabilities are absorbed into the Hermes fork, subsystem
by subsystem. Phase 1 = persistent IPython kernel + `rlm()` recursion.

## 1. Source material (what Prime actually does)

From `prime-agent/packages/coding-agent/docs/rlm-runtime.md` (pinned upstream):

- Each agent session gets a **persistent IPython kernel**; state survives turns.
- The kernel is a separate process speaking **Jupyter protocol over ZeroMQ**
  (shell + iopub + control channels, HMAC-signed frames).
- The model-facing surface is a Python object `rlm` injected into the kernel
  namespace. `await rlm("task", name="child")` sends a **host request** over a
  comm target (`host.request`) to the host process.
- Host responses to in-flight cells go over the **control channel**, never
  shell — shell-channel replies deadlock a serially-executing cell.
- Spawn handles are **admission-only** (`rlm_child_id`, name, dir, model) —
  they never carry the child's answer. Results arrive later via explicit
  agent messages or files.
- Children run with incremented depth; default max depth is 1.
- Kernel lifecycle: lazily provisioned venv, temp connection file with
  loopback TCP + HMAC key, readiness probed via `kernel_info_request`,
  graceful shutdown_request then kill fallback.
- One kernel = one shared namespace; ordinary cells are serialized.

## 2. Target: Hermes extension points we build on

| Concern | Hermes mechanism (verified in-repo) |
|---|---|
| Tool registration | `tools/<name>_tool.py` self-registers via `registry.register(name, toolset, schema, handler, check_fn, ...)` |
| Toolset visibility | `toolsets.py` TOOLSETS dict entry |
| Optional heavy deps | `tools/lazy_deps.py` LAZY_DEPS + matching `[project.optional-dependencies]` extra (exact-pinned) |
| Service gating | `check_fn` returning False hides the tool until deps/env are ready |
| Child agents | `tools/delegate_tool.py::delegate_task(parent_agent=...)` — in-process children, depth limit `_delegate_depth` vs `delegation.max_spawn_depth`; async fan-out via `tools/async_delegation.py` (durable sqlite dispatch/completion delivery) |
| Child isolation | `agent/delegation_context.py::delegated_child_context()` contextvar |
| Async tool handlers | registry supports async handlers (`_run_awaitable`) |
| Config | `config.yaml` keys only for behavior; `.env` for secrets |

## 3. Design decisions

### D1. One new core tool: `ariadne_kernel` (user's explicit call)

A single service-gated core tool, toolset `ariadne`. Sub-actions keep the
schema narrow:

- `run(code)` — execute a cell in the persistent kernel, return rich output.
- `rlm(prompt, name?, model?)` — admit a child agent from inside code OR
  directly as an action (thin sugar over the bridge below).
- `status()` / `restart()` / `shutdown()` — lifecycle introspection.

One tool (not several) because every tool ships on every API call; actions
keep footprint minimal while preserving one obvious entry point.

### D2. Kernel manager is a Python module in core, not a subprocess of the CLI

`ariadne/kernel_manager.py`: Jupyter-over-ZMQ client modeled on Prime's
`KernelManager` (shell/iopub/control channels, HMAC key, loopback TCP, temp
connection file, serialized executes). It runs inside the Hermes process so it
can call delegation machinery directly.

### D3. rlm() recursion reuses Hermes' proven child machinery

Prime's `AgentSession.runRlmChild()` ≈ Hermes' `delegate_task`. We do NOT
port Prime's TypeScript child runtime. Instead the bridge:

1. Kernel-side shim `ariadne_runtime` exposes `rlm`/`agent_message` objects.
2. `await rlm("goal", name=...)` → comm message `{type: "rlm.run", prompt,
   name, model}` on control channel → host validates depth
   (`delegation.max_spawn_depth`), calls the same internal path
   `delegate_task(goal=prompt, background=True, parent_agent=<session agent>)`
   under `delegated_child_context()`.
3. Admission-only `RLMSpawnHandle{rlm_child_id, name, session_dir}` returns
   over control channel immediately (deadlock-safe).
4. Child completion re-enters the conversation through async delegation's
   existing durable delivery (identical to background delegate_task today).

### D4. Dependencies arrive lazily, exact-pinned

New extra `[project.optional-dependencies] ariadne = ["ipykernel==x.y.z",
"pyzmq==a.b.c"]`; LAZY_DEPS entry `"ariadne.kernel": (...)`. `check_fn`
returns False until `lazy_deps.is_available("ariadne.kernel")`; first tool use
prompts/installs per house convention. Nothing new in the base install.

### D5. Trust boundary unchanged from Prime's honest position

The kernel executes model-authored Python with user OS permissions — same
trust level as Hermes' existing terminal/execute_code tools; not a sandbox.
Credentials stay host-side; only bounded metadata crosses the comm.

### D6. Windows is a first-class target

Loopback TCP transport (no AF_UNIX), pywinpty already present for PTY needs;
kernel venv bootstrapped via `uv` like Prime but resolved against our pinned
runtime. Connection files under HERMES_HOME, cleaned up on shutdown.

### D7. What is explicitly NOT in Phase 1

Kernel namespace snapshot/revival (`kernel-state.dill`), daemon-backed
retained children, `goal.*` host requests, harness-state ledger (that's
Phase 2 `/refine` territory), graph recording (Phase 3).

## 4. Module layout (new files)

```
ariadne/
  __init__.py
  kernel_manager.py     # ZMQ client: channels, HMAC, exec, comms, lifecycle
  bootstrap.py          # managed kernel venv resolution/provisioning (uv)
  host_bridge.py        # control-channel server side: rlm.run admission
  config.py             # config.yaml keys (ariadne.kernel.*)
ariadne_runtime/        # installed INTO the kernel env (kept tiny, stdlib+zmq)
  __init__.py
  rlm.py                # callable rlm, handle types, comm client side
tools/ariadne_kernel_tool.py   # schema + handlers + check_fn + register()
tests/test_ariadne_kernel*.py  # unit + integration (real ipykernel)
```

## 5. Config keys (all defaults sane; nothing required)

```yaml
ariadne:
  kernel:
    enabled: true          # master gate (ANDed with check_fn)
    max_cells_per_session: 500
    cell_timeout_s: 300
    python: null           # override interpreter for the kernel env
```

## 6. Test strategy

- Unit: frame signing, channel routing, handle validation, depth checks.
- Integration (real ipykernel subprocess): start → exec across two "turns"
  asserting namespace persistence → rlm.run admission via fake host →
  shutdown cleanliness (no orphan processes, connection file removed).
- E2E smoke: drive the real tool handler twice in one session; assert state
  survived between calls; assert no stray kernels after session teardown.

## 7. Exit gate (Phase 1)

A live Hermes session uses `ariadne_kernel` in turn N, and again in turn N+k;
variables set in turn N are readable in turn N+k; an `rlm()` call admits a
real Hermes child whose completion arrives as a normal agent message; depth
limits hold; teardown leaves no orphans.
