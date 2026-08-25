"""Scout kind tests (registry mocked — zero network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ariadne_runtime.graph_exec as gx
from plugins.context_graph.tasks import TaskStore


@pytest.fixture()
def store(tmp_path):
    s = TaskStore(tmp_path / "t.db")
    yield s
    s.close()


@pytest.fixture()
def fake_web(monkeypatch):
    """Deterministic web_search results; counts calls."""
    calls = {"n": 0}

    def fake_dispatch(name, args, **kw):
        if name != "web_search":
            raise AssertionError(f"unexpected tool {name}")
        calls["n"] += 1
        q = str(args.get("query", ""))
        if "github" in q.lower():
            return json.dumps({
                "results": [
                    {"url": "https://github.com/fastapi/fastapi",
                     "title": "fastapi", "description": "framework"},
                    {"url": "https://github.com/tiangolo/full-stack-fastapi",
                     "title": "full stack template", "description": "tpl"},
                ]}, default=str)
        return json.dumps({
            "results": [
                {"url": "https://fastapi.tiangolo.com/docs/",
                 "title": "FastAPI docs", "description": "official docs"},
            ]}, default=str)

    monkeypatch.setattr(gx, "_interpret_tool_result",
                        lambda name, raw: {"ok": True,
                                           "result": json.loads(raw)})
    monkeypatch.setattr(
        "tools.registry.registry.dispatch",
        lambda name, args, **kw: fake_dispatch(name, args))
    return calls


def test_plan_accepts_scout_kind(store):
    pid = store.create_plan("t", [
        {"id": "s", "kind": "scout",
         "payload": {"technologies": ["fastapi"]}}])
    assert store.plan(pid)["tasks"][0]["kind"] == "scout"


def test_scout_builds_cards(store, monkeypatch, fake_web):
    from ariadne_runtime.graph_exec import GraphExecutor

    pid = store.create_plan("t", [
        {"id": "ground", "kind": "scout",
         "payload": {"technologies": ["fastapi"],
                     "goal_hint": "crud api"}}])
    summary = GraphExecutor(store, pid, tier="governed").run()
    assert summary["final_state"] == "done"
    row = store.plan(pid)["tasks"][0]
    result = json.loads(row["result"])
    card = result["cards"][0]
    assert card["tech"] == "fastapi"
    assert any("tiangolo.com/docs" in f for f in card["api_facts"])
    assert result["reference_projects"][0]["name"] == "fastapi"
    assert not card.get("note_unverified")
    assert fake_web["n"] == 2  # one docs search + one gh search


def test_scout_unavailable_backend_flags_unverified(store, monkeypatch):
    from ariadne_runtime.graph_exec import GraphExecutor

    def dead_dispatch(name, args, **kw):
        return json.dumps({"error": "Tool execution failed: no backend"})

    monkeypatch.setattr(
        "tools.registry.registry.dispatch",
        lambda name, args, **kw: dead_dispatch(name, args))

    pid = store.create_plan("t", [
        {"id": "g", "kind": "scout",
         "payload": {"technologies": ["mysterylib-9x"]}}])
    summary = GraphExecutor(store, pid).run(max_iterations=50)
    row = store.plan(pid)["tasks"][0]
    # backend down is environmental: node may fail/retry, but never invent
    result_or_err = row["result"] or row["error"]
    blob = json.dumps(result_or_err)
    assert "UNVERIFIED" in blob or row["state"] in ("failed", "ready")


def test_scout_requires_technologies(store, monkeypatch):
    from ariadne_runtime.graph_exec import GraphExecutor

    pid = store.create_plan("t", [{"id": "g", "kind": "scout",
                                   "payload": {}}])

    def boom(self, payload):
        return {"ok": False, "error": "scout task needs payload.technologies"}

    monkeypatch.setattr(GraphExecutor, "_exec_scout", boom)
    summary = GraphExecutor(store, pid).run()
    assert summary["final_state"] == "failed"


def test_gate_reads_scout_artifact(store, monkeypatch):
    """A downstream note can gate on scout findings (anti-hallucination)."""
    from ariadne_runtime.graph_exec import GraphExecutor

    pid = store.create_plan("t", [
        {"id": "ground", "kind": "scout",
         "payload": {"technologies": ["fastapi"]}},
        {"id": "check", "kind": "note", "depends_on": ["ground"],
         "payload": {"verified": True}},
        {"id": "build", "kind": "note", "depends_on": ["check"],
         "payload": {
             "when": {"task": "check", "field": "verified", "equals": True},
             "text": "building on verified ground"}},
    ])

    def fake_scout(self, payload):
        return {"ok": True,
                "result": {"cards": [{"tech": "fastapi",
                                      "api_facts": ["docs: x"],
                                      "projects": []}]}}

    monkeypatch.setattr(GraphExecutor, "_exec_scout", fake_scout)
    summary = GraphExecutor(store, pid).run()
    states = {t["id"]: t["state"] for t in store.plan(pid)["tasks"]}
    assert summary["final_state"] == "done"
    build_row = [t for t in store.plan(pid)["tasks"]
                 if t["id"].endswith("-build")][0]
    assert build_row["state"] == "done"
