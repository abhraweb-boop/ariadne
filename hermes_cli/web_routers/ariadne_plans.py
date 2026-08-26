"""Ariadne plans + task DAG control — per-plan executor threads, event spine.

Endpoints:
    GET  /api/ariadne/plans                — list plans
    GET  /api/ariadne/plans/{id}            — plan + task list
    POST /api/ariadne/plans                 — create plan
    POST /api/ariadne/plans/{id}/run        — run (background thread)
    POST /api/ariadne/plans/{id}/cancel     — cooperative cancel
    POST /api/ariadne/tasks/{id}/retry      — reset one task
    GET  /api/ariadne/events                — SSE event stream (S1)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from hermes_cli.web_routers.ariadne_events import emit, events_after, wait_for_events

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ariadne", tags=["ariadne-plans"])

# ── store resolver ───────────────────────────────────────────────────────

_STORE = None


def _store():
    global _STORE
    if _STORE is None:
        from plugins.context_graph.tasks import TaskStore

        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        db = home / "ariadne" / "graph.db"
        db.parent.mkdir(parents=True, exist_ok=True)
        _STORE = TaskStore(db)
    return _STORE


# ── per-plan executor threads ────────────────────────────────────────────

_THREADS: Dict[str, threading.Thread] = {}
_EXEC_LOCK = threading.Lock()


def _run_plan_blocking(plan_id: str) -> None:
    """Run in a background thread so the API returns immediately."""
    from ariadne_runtime.graph_exec import GraphExecutor

    try:
        store = _store()
        emit("plan.running", {"plan_id": plan_id, "ts": time.time()})
        executor = GraphExecutor(store, plan_id)
        result = executor.run()
        emit("plan.completed", {"plan_id": plan_id, "result": result})
    except Exception as exc:
        logger.exception("plan %s crashed", plan_id)
        emit("plan.failed", {"plan_id": plan_id, "error": str(exc)})
    finally:
        with _EXEC_LOCK:
            _THREADS.pop(plan_id, None)


# ── endpoints ────────────────────────────────────────────────────────────


@router.get("/plans")
def list_plans(limit: int = Query(20, ge=1, le=100)) -> Dict[str, Any]:
    try:
        plans = _store().list_plans(limit=limit)
        return {"ok": True, "plans": plans}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str) -> Dict[str, Any]:
    try:
        store = _store()
        plan = store.plan(plan_id)
        if not plan:
            raise HTTPException(404, "plan not found")
        tasks = store.list_plan_tasks(plan_id)
        status = "running" if plan_id in _THREADS else plan.get("state", "unknown")
        return {"ok": True, "plan": plan, "tasks": tasks, "status": status}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/plans", status_code=201)
def create_plan(body: Dict[str, Any]) -> Dict[str, Any]:
    goal = body.get("goal", "")
    specs = body.get("tasks", [])
    if not specs:
        raise HTTPException(400, "at least one task required")
    try:
        pid = _store().create_plan(goal, specs)
        emit("plan.created", {"plan_id": pid, "goal": goal, "task_count": len(specs)})
        return {"ok": True, "plan_id": pid}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/plans/{plan_id}/run")
def run_plan(plan_id: str) -> Dict[str, Any]:
    store = _store()
    plan = store.plan(plan_id)
    if not plan:
        raise HTTPException(404, "plan not found")
    with _EXEC_LOCK:
        if plan_id in _THREADS:
            raise HTTPException(409, "plan already running")
        t = threading.Thread(target=_run_plan_blocking, args=(plan_id,), daemon=True)
        _THREADS[plan_id] = t
        t.start()
    return {"ok": True, "status": "started"}


@router.post("/plans/{plan_id}/cancel")
def cancel_plan(plan_id: str) -> Dict[str, Any]:
    try:
        _store().set_plan_state(plan_id, "cancelled")
        emit("plan.cancelled", {"plan_id": plan_id})
        with _EXEC_LOCK:
            _THREADS.pop(plan_id, None)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: str) -> Dict[str, Any]:
    try:
        store = _store()
        ok = store.reset_task(task_id)
        if not ok:
            raise HTTPException(404, "task not found or not terminal")
        emit("task.retry", {"task_id": task_id})
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/events")
def stream_events(
    after_id: Optional[str] = Query(None),
    stream: bool = Query(True, description="If false, returns snapshot only (no live push loop)."),
):
    """SSE endpoint — one unified event stream with replay + live push (S1).

    Replays any retained events after ``after_id``, then holds the connection
    open and pushes new events as they are emitted. Heartbeat every 15s of
    silence so the client can detect a dead connection.
    Pass ``?stream=false`` for a one-shot snapshot (testing / one-shot reads).
    """

    def generate():
        cursor = after_id or None
        # Replay pass.
        for ev in events_after(cursor):
            yield f"data: {json.dumps(ev)}\n\n"
            cursor = ev["id"]
        if not stream:
            return
        # Live push loop.
        while True:
            fresh = wait_for_events(cursor or "0", timeout_s=15.0)
            if fresh:
                for ev in fresh:
                    yield f"data: {json.dumps(ev)}\n\n"
                    cursor = ev["id"]
            else:
                yield f"data: {json.dumps({'id': '_hb', 'type': '_heartbeat', 'payload': {}, 'ts': time.time()})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")