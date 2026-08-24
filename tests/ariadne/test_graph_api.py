"""Web-server route registration + endpoint behavior for the Ariadne graph API."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

HERMES_CORE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERMES_CORE))

import os

os.environ.setdefault("HERMES_HOME", str(HERMES_CORE / ".hermes" / "test-graph-home"))


def _seed_store(tmp_path):
    from plugins.context_graph.store import GraphStore

    s = GraphStore(tmp_path / "g.db")
    f = s.touch("file", "deploy.py", title="deploy.py")
    sess = s.touch("session", "s1")
    s.link(f, "read-by", sess)
    c = s.touch("cmd", "kubectl", title="kubectl rollout")
    s.link(f, "produced", c)
    return s


def test_routes_registered_and_serve(monkeypatch, tmp_path):
    import hermes_cli.web_routers.ariadne_graph as ag

    importlib.reload(ag)

    store = _seed_store(tmp_path)
    monkeypatch.setattr(ag, "_store", lambda: store)

    client = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(
        __import__("fastapi").FastAPI()
    )
    # Mount only this router (web_server itself is too heavy for unit scope).
    client.app.include_router(ag.router)

    r = client.get("/api/ariadne/graph/stats")
    assert r.status_code == 200 and r.json()["ok"] is True
    assert r.json()["nodes"] >= 3

    r = client.get("/api/ariadne/graph/related", params={"query": "deploy"})
    body = r.json()
    assert r.status_code == 200 and body["ok"] is True
    titles = " ".join(n.get("title", "") for n in body["nodes"])
    assert "deploy.py" in titles

    node_id = body["nodes"][0]["id"]
    r = client.get("/api/ariadne/graph/timeline", params={"node": node_id})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert len(r.json()["events"]) >= 1

    r = client.post("/api/ariadne/graph/prune", json={"older_than_days": 30})
    assert r.status_code == 200 and r.json()["ok"] is True

    r = client.get("/api/ariadne/graph/export", params={"limit": 50})
    assert r.status_code == 200 and "nodes" in r.json()


def test_web_server_includes_router():
    """The real web_server module must mount the ariadne graph router."""
    src = (HERMES_CORE / "hermes_cli" / "web_server.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "_ariadne_graph_routes.router" in src
    assert (
        "from hermes_cli.web_routers import ariadne_graph as _ariadne_graph_routes"
        in src
    )


def test_runs_api_endpoints(monkeypatch, tmp_path):
    """Phase 8: Runs API serves plan state from the TaskStore."""
    import hermes_cli.web_routers.ariadne_graph as ag
    from plugins.context_graph.tasks import TaskStore

    importlib.reload(ag)

    tstore = TaskStore(tmp_path / "t.db")
    monkeypatch.setattr(ag, "_store", lambda: tstore)
    monkeypatch.setattr(ag, "_tasks_store", lambda: tstore)

    pid = tstore.create_plan("dogfood run", [
        {"id": "a", "kind": "note"},
        {"id": "b", "kind": "note", "depends_on": ["a"]},
    ])
    a_id = [t for t in tstore.plan(pid)["tasks"]
            if t["id"].endswith("-a")][0]["id"]
    tstore.mark_running(a_id)
    tstore.mark_done(a_id, {"ok": 1})

    client = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(
        __import__("fastapi").FastAPI()
    )
    client.app.include_router(ag.router)

    r = client.get(f"/api/ariadne/graph/runs/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["plan"]["id"] == pid
    states = {t["id"]: t["state"] for t in body["tasks"]}
    assert states[a_id] == "done"
    assert any(t["state"] == "pending" for t in body["tasks"])
    assert body["counts"]["done"] == 1

    r = client.get("/api/ariadne/graph/runs")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json()["plans"])

    r = client.get("/api/ariadne/graph/runs/plan-nope")
    assert r.status_code == 404

    tstore.close()
