"""Ariadne graph executor -- runs task DAGs to completion (Phase 6).

This module is where "graph engineering replaces the agent loop" becomes
literal: instead of one while-loop around an LLM call, a *plan* (task DAG)
is executed by walking topological order -- independent branches run
concurrently, artifacts flow along edges via ``{{task.result}}`` refs, and
failures re-route locally (retry -> cascade-skip downstream) instead of
unwinding a whole conversation turn.

Design contract: docs/architecture-ariadne-phase6.md

Execution kinds:
    kernel  -- run python in the persistent IPython kernel
               (ariadne.service.execute_cell)
    rlm     -- admit a recursive child through SubagentLifecycleService
               (must run inside a live parent turn, same as the direct tool)
    tool    -- dispatch any registered Hermes tool via tools.registry
    note    -- pure annotation / artifact node (no execution)

Supplemental-state rule preserved: the executor mutates only task rows and
its own outputs -- never past conversation context.
"""

from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import Any, Dict, List, Optional

from plugins.context_graph.tasks import TASK_KINDS, TaskStore

logger = logging.getLogger(__name__)


class GraphExecutor:
    """Executes one plan's DAG. Re-instantiate per run; safe to resume."""

    def __init__(
        self,
        store: TaskStore,
        plan_id: str,
        *,
        max_workers: int = 4,
        default_cell_timeout_s: Optional[float] = None,
        poll_interval_s: float = 0.25,
        max_iterations: Optional[int] = None,
        tier: Optional[str] = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        from ariadne_runtime import policy

        pol = policy.get(tier) if tier else policy.active()
        self._store = store
        self._plan_id = plan_id
        self._max_workers = max_workers
        self._cell_timeout_s = (default_cell_timeout_s
                                or float(pol["cell_timeout_s"]))
        self._poll_s = poll_interval_s
        self._max_iterations = max_iterations or int(pol["max_iterations"])
        self._tier = pol

    # ── public API ────────────────────────────────────────────────────────
    def run(self, *, resume: bool = False,
            max_iterations: Optional[int] = None) -> Dict[str, Any]:
        """Execute the DAG to a terminal state. Idempotent-resumable."""
        cap = max_iterations or self._max_iterations
        plan = self._store.plan(self._plan_id)
        if plan is None:
            return {"ok": False, "error": f"unknown plan {self._plan_id}"}
        self._store.reset_stale_running(self._plan_id)
        self._store.set_plan_state(self._plan_id, "running")

        in_flight: Dict[Future, str] = {}
        iterations = 0
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            while True:
                if iterations >= cap:
                    logger.warning("graph_exec: max_iterations reached")
                    break
                iterations += 1
                self._store.cascade_skip(self._plan_id)
                ready = {
                    t["id"]: t for t in self._store.ready_tasks(self._plan_id)
                    if t["id"] not in in_flight.values()
                }
                for tid, task in ready.items():
                    if len(in_flight) >= self._max_workers:
                        break
                    fut = pool.submit(self._execute_task, task)
                    in_flight[fut] = tid

                if not in_flight:
                    break  # nothing running, nothing ready -> terminal

                done, _ = wait(
                    list(in_flight), timeout=self._poll_s,
                    return_when=FIRST_COMPLETED,
                )
                if not done:
                    continue  # poll window elapsed; re-check readiness (retries)
                for fut in done:
                    tid = in_flight.pop(fut)
                    try:
                        outcome = fut.result()
                    except Exception as exc:  # defensive: worker blew up
                        logger.exception("graph_exec worker crashed: %s", tid)
                        outcome = {"ok": False,
                                   "error": f"executor: {type(exc).__name__}: {exc}"}
                    self._apply_outcome(tid, outcome)

        self._store.cascade_skip(self._plan_id)
        return self.finish()

    def finish(self) -> Dict[str, Any]:
        """Compute the terminal summary and persist the plan state."""
        p = self._store.plan(self._plan_id)
        states: Dict[str, int] = {}
        for t in p["tasks"]:
            states[t["state"]] = states.get(t["state"], 0) + 1
        if states.get("running") or states.get("ready"):
            final = "running"
        elif states.get("pending"):
            final = "blocked"  # unreachable deps that were not skippable
        elif states.get("failed"):
            final = "failed"
        elif states.get("skipped"):
            final = "partial"
        elif not p["tasks"]:
            final = "empty"
        else:
            final = "done"
        self._store.set_plan_state(self._plan_id, final)
        return {
            "ok": final in ("done", "partial"),
            "plan_id": self._plan_id, "goal": p["goal"],
            "final_state": final, "states": states,
        }

    # ── outcome application ───────────────────────────────────────────────
    def _apply_outcome(self, task_id: str, outcome: Dict[str, Any]) -> None:
        if outcome.get("ok"):
            self._store.mark_done(task_id, outcome.get("result"))
            return
        err = str(outcome.get("error") or "unknown error")
        new_state = self._store.mark_failed(task_id, err)
        if new_state == "ready":
            logger.info("graph_exec: %s failed, retrying (%s)",
                        task_id, err[:120])
        # 'failed' is terminal; next loop's cascade_skip skips descendants.

    # ── task execution ────────────────────────────────────────────────────
    def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        tid = task["id"]
        self._store.mark_running(tid)
        try:
            payload = self._resolve_payload(task)
        except Exception as exc:
            return {"ok": False,
                    "error": f"payload resolution: {type(exc).__name__}: {exc}"}
        kind = task["kind"]
        if kind not in TASK_KINDS:
            return {"ok": False, "error": f"unknown kind {kind!r}"}
        try:
            if kind == "note":
                return self._exec_note(payload)
            if kind == "kernel":
                return self._exec_kernel(payload)
            if kind == "rlm":
                return self._exec_rlm(payload)
            if kind == "prime":
                return self._exec_prime(payload)
            if kind == "tool":
                return self._exec_tool(payload)
        except Exception as exc:
            logger.exception("graph_exec task %s raised", tid)
            return {"ok": False,
                    "error": f"{type(exc).__name__}: {exc}"}
        return {"ok": False, "error": f"unhandled kind {kind!r}"}

    def _exec_note(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = str(payload.get("text") or "").strip()
        return {"ok": True,
                "result": {"note": text[:8000]}}

    def _resolve_payload(self, task: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.loads(task["payload"] or "{}")
        dep_ids = json.loads(task["depends_on"] or "[]")
        if not dep_ids:
            return payload
        results = {}
        for d in dep_ids:
            row = self._store.task(d)
            if row is None or row["state"] != "done":
                continue  # resolver raises a clear KeyError on missing refs
            try:
                results[d] = json.loads(row["result"]) if row["result"] else None
            except json.JSONDecodeError:
                results[d] = row["result"]
        return TaskStore.resolve_refs(payload, results)

    def _exec_kernel(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        code = str(payload.get("code") or "").strip()
        if not code:
            return {"ok": False, "error": "kernel task needs payload.code"}
        from ariadne import service as svc

        if not svc.deps_available():
            return {"ok": False,
                    "error": ("ariadne kernel deps unavailable "
                              "(ipykernel/pyzmq missing)")}
        timeout_s = float(payload.get("timeout_s") or self._cell_timeout_s)
        cell = svc.execute_cell(code, timeout_s=timeout_s)
        ok = cell.get("status") == "ok"
        return {"ok": ok, "result": {
            "status": cell.get("status"), "output": _summarize_cell(cell),
        }} if ok else {"ok": False, "error": _summarize_cell(cell),
                       "result": None}

    def _exec_rlm(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return {"ok": False, "error": "rlm task needs payload.prompt"}
        from agent.subagent_lifecycle import get_active_subagent_parent

        if get_active_subagent_parent() is None:
            return {"ok": False,
                    "error": ("no active parent session bound; executor-driven "
                              "rlm tasks require a live agent turn")}
        from ariadne import service as svc

        handle = svc._handle_host_request(
            "rlm.run",
            {"prompt": prompt, "name": payload.get("name"),
             "model": payload.get("model")},
        )
        return {"ok": True, "result": {"admitted": True, "handle": handle}}

    def _exec_prime(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            return {"ok": False, "error": "prime task needs payload.prompt"}
        try:
            from ariadne.prime_engine import get_engine
        except RuntimeError as exc:  # disabled by config
            return {"ok": False, "error": str(exc)}
        try:
            engine = get_engine()
        except RuntimeError as exc:
            msg = str(exc)
            if "bundle missing" in msg:
                return {"ok": False,
                        "error": ("prime bundle missing — run "
                                  "scripts/build-prime.sh")}
            return {"ok": False, "error": msg}
        timeout = float(payload.get("timeout_s") or self._cell_timeout_s)
        try:
            out = engine.prompt(prompt, timeout_s=timeout)
        except TimeoutError:
            return {"ok": False,
                    "error": f"prime prompt timed out after {timeout}s"}
        except RuntimeError as exc:
            return {"ok": False, "error": f"prime rpc: {exc}"}
        if not out.get("ok"):
            err = (out.get("raw") or {}).get("error") or "prime prompt failed"
            if isinstance(err, dict):
                err = json.dumps(err)
            return {"ok": False, "error": str(err)[:2000],
                    "result": out.get("text") or None}
        return {"ok": True, "result": {
            "text": (out.get("text") or "")[:16_000],
            "events": len(out.get("events") or []),
        }}

    def _exec_tool(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = str(payload.get("tool") or "").strip()
        if not name:
            return {"ok": False, "error": "tool task needs payload.tool"}
        args = payload.get("args") or {}
        if not isinstance(args, dict):
            return {"ok": False, "error": "payload.args must be an object"}
        from tools.registry import registry

        raw = registry.dispatch(name, args)
        return _interpret_tool_result(name, raw)


# ── helpers ───────────────────────────────────────────────────────────────
def _summarize_cell(cell: Dict[str, Any]) -> str:
    parts: List[str] = []
    for piece in cell.get("outputs") or []:
        t = piece.get("type")
        if t == "stream":
            parts.append(str(piece.get("text") or ""))
        elif t in ("execute_result", "display_data"):
            parts.append(f"[out] {piece.get('text', '')}")
        elif t == "error":
            tb = "\n".join(piece.get("traceback") or [])
            parts.append(
                f"[error] {piece.get('ename')}: {piece.get('evalue')}\n{tb}")
    body = "\n".join(parts).strip()
    if cell.get("status") == "timeout":
        body += "\n[cell TIMEOUT — kernel still alive]"
    return body[:16_000] or "(no output)"


def _interpret_tool_result(name: str, raw: Any) -> Dict[str, Any]:
    """Registry returns str | dict; normalize to ok/result/error outcome."""
    if isinstance(raw, dict):
        text = json.dumps(raw, default=str)
        parsed: Any = raw
    else:
        text = str(raw)
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = None
    if isinstance(parsed, dict):
        if parsed.get("error"):
            return {"ok": False, "error": str(parsed["error"])[:4000],
                    "result": parsed}
        if parsed.get("ok") is False:
            return {"ok": False,
                    "error": str(parsed.get("error") or parsed)[:4000],
                    "result": parsed}
        return {"ok": True, "result": parsed}
    lowered = text.lstrip().lower()
    if lowered.startswith(("tool execution failed", "error")):
        return {"ok": False, "error": text[:4000]}
    return {"ok": True, "result": text[:16_000]}
