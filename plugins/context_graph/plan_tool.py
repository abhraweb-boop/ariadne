"""Ariadne planning/execution tools -- ariadne_plan + ariadne_exec.

Injected by the context_graph plugin alongside ariadne_graph. Together they
let the model drive graph-engineered execution instead of the agent loop:

    1. ariadne_plan action=create  -> emit a task DAG (validated, acyclic)
    2. ariadne_exec action=run     -> executor walks topological order
                                      (parallel branches, artifact refs,
                                      retry + cascade-skip on failure)
    3. ariadne_exec action=status  -> inspect; resume after interruption

Task kinds: kernel (persistent IPython cell), rlm (recursive child),
tool (any registered Hermes tool), note (annotation).
Artifact passing: payload values like "{{build.result}}" resolve to the
upstream task's output before execution.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from plugins.context_graph.tasks import TASK_KINDS, TaskStore

logger = logging.getLogger(__name__)

_PLAN_TOOL = "ariadne_plan"
_EXEC_TOOL = "ariadne_exec"

_store = None


def _get_store() -> TaskStore:
    global _store
    if _store is None:
        from plugins.context_graph import _db_path

        _store = TaskStore(_db_path())
    return _store


def close_store() -> None:
    global _store
    if _store is not None:
        try:
            _store.close()
        except Exception:
            pass
        _store = None


# ── schemas ───────────────────────────────────────────────────────────────
PLAN_SCHEMA = {
    "name": _PLAN_TOOL,
    "description": (
        "Create and manage executable task DAGs (graph engineering). Emit a "
        "plan INSTEAD of executing steps one-by-one yourself: each node is a "
        "kernel cell, rlm child, Hermes tool call, or note; edges are "
        "dependencies. Independent nodes run in parallel. Pass upstream "
        "outputs downstream with {{task_id.result}} references. "
        'EXAMPLE: {"action":"create","goal":"migrate config",'
        '"tasks":[{"id":"scan","kind":"tool","title":"list files",'
        '"payload":{"tool":"search_files","args":{"pattern":"*.yaml"}},'
        '"max_attempts":2},{"id":"analyze","kind":"kernel",'
        '"depends_on":["scan"],"payload":{"code":"print(open(\'x\').read())"}}]} '
        "Then run it with ariadne_exec."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string",
                       "enum": ["create", "get", "list", "delete",
                                "reset_task"]},
            "goal": {"type": "string"},
            "tasks": {
                "type": "array",
                "description": "DAG nodes for action=create",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string",
                               "description": "Short slug; referenced by deps"},
                        "kind": {"type": "string",
                                 "enum": list(TASK_KINDS)},
                        "title": {"type": "string"},
                        "depends_on": {"type": "array",
                                       "items": {"type": "string"}},
                        "payload": {"type": "object",
                                    "description": ("kernel:{code,timeout_s} "
                                                    "rlm:{prompt,name,model} "
                                                    "tool:{tool,args} "
                                                    "note:{text}")},
                        "max_attempts": {"type": "integer",
                                         "minimum": 1, "maximum": 5},
                    },
                    "required": ["kind"],
                },
            },
            "plan_id": {"type": "string"},
            "task_id": {"type": "string"},
        },
        "required": ["action"],
    },
}

EXEC_SCHEMA = {
    "name": _EXEC_TOOL,
    "description": (
        "Execute/resume Ariadne task DAGs created via ariadne_plan. The "
        "graph executor walks topological order: independent tasks run "
        "concurrently, failures retry then cascade-skip downstream branches "
        "instead of aborting the whole run. Interrupted runs resume from "
        "completed nodes. Use this for multi-step work instead of doing "
        "each step inline."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["run", "status"]},
            "plan_id": {"type": "string", "required": True},
            "max_workers": {"type": "integer", "minimum": 1, "maximum": 8},
        },
        "required": ["action", "plan_id"],
    },
}


# ── ariadne_plan handlers ────────────────────────────────────────────────
def handle_ariadne_plan(args: Dict[str, Any], **_kw) -> str:
    args = dict(args or {})
    action = str(args.get("action") or "").lower()
    handlers = {
        "create": _hp_create, "get": _hp_get, "list": _hp_list,
        "delete": _hp_delete, "reset_task": _hp_reset,
    }
    fn = handlers.get(action)
    if fn is None:
        return json.dumps({
            "ok": False,
            "error": (f"unknown action '{args.get('action')}'. Valid: "
                      f"{sorted(handlers)}. Example: "
                      '{"action":"create","goal":"...","tasks":[{"id":"a",'
                      '"kind":"note","title":"start"}]}'),
        })
    try:
        return json.dumps(fn(args), default=str)
    except Exception as exc:
        logger.exception("ariadne_plan %s failed", action)
        return json.dumps({"ok": False,
                           "error": f"{type(exc).__name__}: {exc}"})


def _hp_create(a: Dict[str, Any]) -> Dict[str, Any]:
    goal = str(a.get("goal") or "").strip()
    specs = a.get("tasks")
    if not goal:
        return {"ok": False, "error": "create requires goal"}
    if not isinstance(specs, list) or not specs:
        return {"ok": False,
                "error": ("create requires non-empty tasks array; kinds: "
                          f"{TASK_KINDS}")}
    store = _get_store()
    plan_id = store.create_plan(goal, specs)
    p = store.plan(plan_id)
    return {
        "ok": True, "plan_id": plan_id,
        "tasks": [{"id": t["id"], "kind": t["kind"], "state": t["state"],
                   "depends_on": json.loads(t["depends_on"])}
                  for t in p["tasks"]],
        "next": f'ariadne_exec {{"action":"run","plan_id":"{plan_id}"}}',
    }


def _hp_get(a: Dict[str, Any]) -> Dict[str, Any]:
    pid = str(a.get("plan_id") or "")
    if not pid:
        return {"ok": False, "error": "get requires plan_id"}
    p = _get_store().plan(pid)
    if p is None:
        return {"ok": False, "error": f"unknown plan {pid}"}
    for t in p["tasks"]:
        t["depends_on"] = json.loads(t.pop("depends_on", "[]"))
        if t.get("result"):
            try:
                t["result"] = json.loads(t["result"])
            except (json.JSONDecodeError, ValueError):
                pass
    return {"ok": True, **p}


def _hp_list(_a: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, "plans": _get_store().list_plans()}


def _hp_delete(a: Dict[str, Any]) -> Dict[str, Any]:
    pid = str(a.get("plan_id") or "")
    if not pid:
        return {"ok": False, "error": "delete requires plan_id"}
    ok = _get_store().delete_plan(pid)
    return ({"ok": True, "deleted": pid} if ok
            else {"ok": False, "error": f"unknown plan {pid}"})


def _hp_reset(a: Dict[str, Any]) -> Dict[str, Any]:
    tid = str(a.get("task_id") or "")
    if not tid:
        return {"ok": False, "error": "reset_task requires task_id"}
    ok = _get_store().reset_task(tid)
    return ({"ok": True, "reset": tid} if ok
            else {"ok": False, "error": f"unknown task {tid}"})


# ── ariadne_exec handlers ────────────────────────────────────────────────
def handle_ariadne_exec(args: Dict[str, Any], **_kw) -> str:
    args = dict(args or {})
    action = str(args.get("action") or "").lower()
    handlers = {"run": _he_run, "status": _he_status}
    fn = handlers.get(action)
    if fn is None:
        return json.dumps({
            "ok": False,
            "error": (f"unknown action '{args.get('action')}'. Valid: "
                      f"{sorted(handlers)}"),
        })
    try:
        return json.dumps(fn(args), default=str)
    except Exception as exc:
        logger.exception("ariadne_exec %s failed", action)
        return json.dumps({"ok": False,
                           "error": f"{type(exc).__name__}: {exc}"})


def _he_run(a: Dict[str, Any]) -> Dict[str, Any]:
    pid = str(a.get("plan_id") or "")
    if not pid:
        return {"ok": False, "error": "run requires plan_id"}
    store = _get_store()
    if store.plan(pid) is None:
        return {"ok": False, "error": f"unknown plan {pid}"}
    workers = int(a.get("max_workers") or 4)
    from ariadne_runtime.graph_exec import GraphExecutor

    summary = GraphExecutor(store, pid, max_workers=max(1, min(8, workers))).run(
        resume=True)
    return summary


def _he_status(a: Dict[str, Any]) -> Dict[str, Any]:
    pid = str(a.get("plan_id") or "")
    if not pid:
        return {"ok": False, "error": "status requires plan_id"}
    return _get_store().plan_summary(pid)
