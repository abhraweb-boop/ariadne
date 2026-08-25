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

import hashlib
import json
import logging
import re
import threading
import time
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
            # bypassed deps satisfy readiness, so pending here means
            # genuinely unreachable (e.g. behind a failed node not yet skipped)
            final = "blocked"
        elif states.get("failed"):
            final = "failed"
        elif states.get("skipped") or states.get("bypassed"):
            # gated-off branches are a normal conditional outcome
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
        if outcome.get("bypassed"):
            return  # store already holds bypassed state; do not overwrite
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
    @staticmethod
    def _gate_satisfied(when: Dict[str, Any],
                        dep_results: Dict[str, Any]) -> bool:
        """Evaluate a `when` gate against upstream task results.

        Forms:
          {"task": "<id>", "field": "<key>", "equals": V}
          {"task": "<id>", "field": "<key>", "not_equals": V}
          {"task": "<id>", "equals": V}            # whole-result compare
          {"task": "<id>", "field": "<key>"}       # truthy field
          {"task": "<id>"}                          # truthy result
        Missing upstream/field -> False (conservative).
        """
        tid = str(when.get("task") or "")
        if not tid:
            return True  # malformed gate = no gate
        actual = dep_results.get(tid)
        if "field" in when:
            actual = (actual.get(when["field"])
                      if isinstance(actual, dict) else None)
        if "equals" in when:
            return actual == when["equals"]
        if "not_equals" in when:
            return actual != when["not_equals"]
        return bool(actual)

    def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        tid = task["id"]

        # gate check BEFORE running: bypass without marking running
        payload_raw = json.loads(task["payload"] or "{}")
        when = payload_raw.get("when")
        if isinstance(when, dict):
            dep_ids = json.loads(task["depends_on"] or "[]")
            dep_results: Dict[str, Any] = {}
            for d in dep_ids:
                row = self._store.task(d)
                if row is None:
                    continue
                try:
                    val = json.loads(row["result"]) if row["result"] else None
                except json.JSONDecodeError:
                    val = row["result"]
                dep_results[d] = val
            # gates reference deps by their SHORT spec id; scoped ids end
            # with -<short>, so match on suffix
            short_results = {}
            for k, v in dep_results.items():
                short_results[k.rsplit("-", 1)[-1]] = v
            ref = str(when.get("task") or "")
            lookup = short_results.get(ref, dep_results.get(ref))
            probe = {"task": ref}
            if "field" in when:
                probe["field"] = when["field"]
            if "equals" in when:
                probe["equals"] = when["equals"]
            elif "not_equals" in when:
                probe["not_equals"] = when["not_equals"]
            satisfied = GraphExecutor._gate_satisfied(
                probe, {ref: lookup})
            if not satisfied:
                self._store.mark_bypassed(tid)
                return {"ok": True, "bypassed": True,
                        "result": {"bypassed": True,
                                   "reason": f"gate on '{ref}' false"}}

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
            if kind == "scout":
                return self._exec_scout(payload)
            if kind == "tool":
                return self._exec_tool(payload)
        except Exception as exc:
            logger.exception("graph_exec task %s raised", tid)
            return {"ok": False,
                    "error": f"{type(exc).__name__}: {exc}"}
        return {"ok": False, "error": f"unhandled kind {kind!r}"}

    def _exec_note(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Note nodes carry arbitrary condition fields (e.g. `passed`)
        into their result so downstream `when` gates can read them."""
        result = {k: v for k, v in payload.items() if k != "when"}
        text = str(result.pop("text", "") or "").strip()
        if text:
            result["note"] = text[:8000]
        return {"ok": True, "result": result}

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

    def _exec_scout(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Ground a technology set against the live web (P10-D).

        For each technology: official-docs search + top GitHub reference
        projects, distilled into a grounding card. Results cached in the
        memory ledger keyed by sorted-tech hash so identical rebuilds
        fetch nothing. Batched serially (≤1 concurrent) to respect
        provider rate limits.
        """
        techs = [str(t).strip() for t in (payload.get("technologies") or [])
                 if str(t).strip()]
        goal_hint = str(payload.get("goal_hint") or "").strip()
        if not techs:
            return {"ok": False,
                    "error": "scout task needs payload.technologies"}
        key = "scout:" + hashlib.sha256(
            json.dumps({"t": sorted(x.lower() for x in techs),
                        "g": goal_hint}).encode()).hexdigest()[:16]

        # 1) cache lookup (memory ledger via ariadne_memory store)
        try:
            from plugins.memory.ariadne import ledger

            cached = ledger.get_by_key(key) if hasattr(ledger, "get_by_key") \
                else None
        except Exception:
            cached = None
        if cached:
            return {"ok": True, "result": dict(cached, cached=True)}

        cards = []
        for tech in techs:
            card = self._scout_one(tech, goal_hint)
            cards.append(card)
        result = {
            "technologies": techs,
            "cards": cards,
            "reference_projects": [p for c in cards
                                   for p in c.get("projects", [])][:8],
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        # 2) cache write-through (best-effort)
        try:
            from plugins.memory.ariadne import ledger

            if hasattr(ledger, "put_with_key"):
                ledger.put_with_key(key, result)
        except Exception:
            pass
        return {"ok": True, "result": result}

    def _scout_one(self, tech: str, goal_hint: str) -> Dict[str, Any]:
        """One technology -> {tech, api_facts[], projects[]}."""
        from tools.registry import registry

        def _search(query: str) -> str:
            raw = registry.dispatch("web_search",
                                    {"query": query, "limit": 4})
            out = _interpret_tool_result("web_search", raw)
            return json.dumps(out.get("result", ""))[:4000] if out["ok"] \
                else f"unavailable: {out.get('error', '')[:120]}"

        docs_q = f"{tech} official documentation getting started"
        gh_q = f"github.com {tech}" + (f" {goal_hint}" if goal_hint else "")
        docs_raw = _search(docs_q)
        gh_raw = _search(gh_q)

        def _extract_urls(blob: str, want: str) -> List[str]:
            urls = re.findall(r"https?://[^\s\"'\\<>]+", blob)
            picked = []
            for u in urls:
                low = u.lower()
                if want == "docs" and ("docs" in low or "readthedocs" in low):
                    picked.append(u)
                elif want == "gh" and "github.com" in low:
                    picked.append(u)
            seen, uniq = set(), []
            for u in picked:
                base = u.rstrip("/").split("?")[0]
                if base not in seen and len(base) > 24:
                    seen.add(base)
                    uniq.append(base)
            return uniq

        docs_hits = _extract_urls(docs_raw + gh_raw, "docs")
        gh_hits = _extract_urls(gh_raw, "gh")
        unavailable = docs_raw.startswith("unavailable:") and \
            gh_raw.startswith("unavailable:")

        projects = [{"name": u.split("/")[-1], "url": u}
                    for u in gh_hits[:3]]
        card = {
            "tech": tech,
            "api_facts": ([f"docs: {u}" for u in docs_hits[:3]]
                          or ([f"search unavailable ({goal_hint or 'no hint'})"]
                              if unavailable else [])),
            "projects": projects,
            "note_unverified": bool(unavailable),
        }
        if unavailable:
            card["warning"] = ("web_search backend unreachable — this "
                               "technology is UNVERIFIED; do not invent "
                               "APIs for it")
        return card

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
    """Registry returns str | dict; normalize to ok/result/error outcome.

    The registry's own failure envelope is {"error": "Tool execution
    failed: ..."} (or a bare string starting with it) — both MUST map to
    ok=False so plans fail visibly instead of treating errors as data.
    """
    if isinstance(raw, dict):
        text = json.dumps(raw, default=str)
        parsed: Any = raw
    else:
        text = str(raw)
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            parsed = None
        # bare-string error envelopes (registry tool_error() path)
        if parsed is None and text.lstrip().startswith(
                ("Tool execution failed", "Unknown tool", "error:",
                 "Error:")):
            return {"ok": False, "error": text[:4000]}
    if isinstance(parsed, dict):
        if parsed.get("error"):
            err = str(parsed["error"])
            if not err.lower().startswith("tool execution failed"):
                err = f"Tool execution failed: {err}"
            return {"ok": False, "error": err[:4000], "result": parsed}
        if parsed.get("ok") is False:
            return {"ok": False,
                    "error": str(parsed.get("error") or parsed)[:4000],
                    "result": parsed}
        return {"ok": True, "result": parsed}
    lowered = text.lstrip().lower()
    if lowered.startswith(("tool execution failed", "unknown tool",
                           "error:", "Error:")):
        return {"ok": False, "error": text[:4000]}
    return {"ok": True, "result": text[:16_000]}
