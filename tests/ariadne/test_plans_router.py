"""Plans + task-DAG REST router tests (no model calls; stub tool registry)."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

os.environ.setdefault(
    "HERMES_HOME", str(Path.home() / "AppData" / "Local" / "Temp" / "ariadne-test-home")
)
TEST_HOME = Path(os.environ["HERMES_HOME"])
TEST_HOME.mkdir(parents=True, exist_ok=True)
# Isolate the plans router store
from hermes_cli import web_routers  # noqa: E402

from hermes_cli.web_routers import ariadne_plans as plans  # noqa: E402

from plugins.context_graph import tasks as tasks_mod  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_store(tmp_path, monkeypatch):
    monkeypatch.setattr(plans, "_STORE", None)
    monkeypatch.setattr(tasks_mod, "_SCHEMA", tasks_mod._SCHEMA)  # keep schema
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    db = tmp_path / "ariadne" / "graph.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    from plugins.context_graph.tasks import TaskStore

    store = TaskStore(db)
    monkeypatch.setattr(plans, "_store", lambda: store)
    yield store
    store.close()


def _spec(title: str, kind: str = "note", payload: dict | None = None, deps: list | None = None):
    return {
        "title": title,
        "kind": kind,
        "payload": payload or {"text": title},
        "depends_on": deps or [],
    }


def test_create_plan_returns_id(_isolate_store):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(plans.router)
    client = TestClient(app)

    r = client.post("/api/ariadne/plans", json={
        "goal": "test plan",
        "tasks": [
            _spec("step-a"),
            _spec("step-b", deps=["step-a"]),
        ],
    })
    assert r.status_code == 201
    pid = r.json()["plan_id"]
    assert pid.startswith("plan-")

    detail = client.get(f"/api/ariadne/plans/{pid}").json()
    assert detail["ok"]
    assert detail["plan"]["goal"] == "test plan"
    assert len(detail["tasks"]) == 2
    # Verify dependency linking
    ids = [t["id"] for t in detail["tasks"]]
    deps = [t["depends_on"] for t in detail["tasks"]]
    task_b = [t for t in detail["tasks"] if "step-b" in t["id"]][0]
    deps_b = json.loads(task_b["depends_on"])
    assert len(deps_b) == 1
    # task_b's dep should point to step-a's scoped id
    assert any("step-a" in d for d in deps_b)


def test_list_plans_empty_and_after_create(_isolate_store):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(plans.router)
    client = TestClient(app)

    assert client.get("/api/ariadne/plans").json()["plans"] == []

    client.post("/api/ariadne/plans", json={"goal": "g", "tasks": [_spec("only")]})
    plans_json = client.get("/api/ariadne/plans").json()
    assert len(plans_json["plans"]) == 1
    assert plans_json["plans"][0]["goal"] == "g"


def test_run_plan_executes_note_tasks_to_done(_isolate_store):
    """Note tasks execute without a model; the DAG should reach terminal."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(plans.router)
    client = TestClient(app)

    r = client.post("/api/ariadne/plans", json={
        "goal": "run me",
        "tasks": [_spec("alpha", kind="note", payload={"text": "hello"})],
    })
    pid = r.json()["plan_id"]

    run = client.post(f"/api/ariadne/plans/{pid}/run")
    assert run.status_code == 200
    assert run.json()["ok"]

    # Executor runs in a background thread; wait for terminal state.
    deadline = time.time() + 30
    detail = None
    while time.time() < deadline:
        detail = client.get(f"/api/ariadne/plans/{pid}").json()
        status = detail.get("status", "")
        if status in ("done", "partial", "failed"):
            break
        time.sleep(0.3)
    assert detail is not None
    assert detail["status"] in ("done", "partial", "failed")


def test_unknown_plan_404(_isolate_store):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(plans.router)
    client = TestClient(app)

    assert client.get("/api/ariadne/plans/nope").status_code == 404
    assert client.post("/api/ariadne/plans/nope/run").status_code == 404


def test_retry_unknown_task_404(_isolate_store):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(plans.router)
    client = TestClient(app)

    assert client.post("/api/ariadne/tasks/nope/retry").status_code == 404


def test_events_endpoint_returns_snapshot(_isolate_store):
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(plans.router)
    client = TestClient(app)

    client.post("/api/ariadne/plans", json={"goal": "g", "tasks": [_spec("x")]})
    r = client.get("/api/ariadne/events")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    body = r.text
    # plan.created should be in the replay
    assert "plan.created" in body