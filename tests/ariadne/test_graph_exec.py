"""Task-DAG store + graph executor + plan/exec tools tests (no model)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

import plugins.context_graph as cg
from plugins.context_graph.plan_tool import (
    handle_ariadne_exec,
    handle_ariadne_plan,
)
from plugins.context_graph.store import GraphStore
from plugins.context_graph.tasks import CycleError, TaskStore


@pytest.fixture()
def store(tmp_path: Path) -> TaskStore:
    s = TaskStore(tmp_path / "tasks.db")
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _isolate_stores(monkeypatch, tmp_path):
    """Isolate BOTH module-level stores per test (no cwd pollution)."""
    shared = GraphStore(tmp_path / "g.db")
    monkeypatch.setattr(cg, "get_store", lambda: shared, raising=True)
    import plugins.context_graph.plan_tool as pt

    tstore = TaskStore(tmp_path / "t.db")
    monkeypatch.setattr(pt, "_store", tstore, raising=True)
    yield
    try:
        shared.close()
    except Exception:
        pass
    try:
        tstore.close()
    except Exception:
        pass


def _mk(store, specs, goal="test"):
    return store.create_plan(goal, specs)


# ── store: validation ─────────────────────────────────────────────────────
class TestValidation:
    def test_rejects_bad_kind(self, store):
        with pytest.raises(ValueError, match="kind"):
            _mk(store, [{"id": "a", "kind": "vibes"}])

    def test_rejects_unknown_dep(self, store):
        with pytest.raises(ValueError, match="unknown dependencies"):
            _mk(store, [{"id": "a", "kind": "note",
                         "depends_on": ["ghost"]}])

    def test_rejects_cycle(self, store):
        with pytest.raises(CycleError):
            _mk(store, [
                {"id": "a", "kind": "note", "depends_on": ["b"]},
                {"id": "b", "kind": "note", "depends_on": ["a"]},
            ])

    def test_dedupes_ids(self, store):
        pid = _mk(store, [{"title": "Do thing", "kind": "note"},
                          {"title": "Do Thing", "kind": "note"}])
        ids = [t["id"] for t in store.plan(pid)["tasks"]]
        assert len(ids) == len(set(ids))

    def test_clamps_attempts(self, store):
        pid = _mk(store, [{"id": "a", "kind": "tool", "max_attempts": 99}])
        assert store.plan(pid)["tasks"][0]["max_attempts"] == 5


# ── store: state machine ──────────────────────────────────────────────────
class TestStateMachine:
    def test_retry_then_terminal_fail(self, store):
        pid = _mk(store, [{"id": "a", "kind": "tool", "max_attempts": 2}])
        tid = store.plan(pid)["tasks"][0]["id"]
        store.mark_running(tid)
        assert store.mark_failed(tid, "boom") == "ready"   # attempts=1 < 2
        store.mark_running(tid)
        assert store.mark_failed(tid, "boom") == "failed"  # attempts=2 = 2
        state = store.task(tid)
        assert state["attempts"] == 2 and state["state"] == "failed"

    def test_cascade_skip_transitive(self, store):
        pid = _mk(store, [
            {"id": "root", "kind": "note"},
            {"id": "mid", "kind": "note", "depends_on": ["root"]},
            {"id": "leaf", "kind": "note", "depends_on": ["mid"]},
            {"id": "free", "kind": "note"},
        ])
        by_id = {t["id"]: t for t in store.plan(pid)["tasks"]}
        root_id = by_id[pid + "-root"]["id"]
        mid_id = by_id[pid + "-mid"]["id"]
        leaf_id = by_id[pid + "-leaf"]["id"]
        free_id = by_id[pid + "-free"]["id"]
        store.mark_running(root_id)
        store.mark_failed(root_id, "x")  # attempts exhausted -> failed
        skipped = store.cascade_skip(pid)
        assert set(skipped) == {mid_id, leaf_id}
        assert store.task(free_id)["state"] == "pending"

    def test_ready_tasks_gating(self, store):
        pid = _mk(store, [
            {"id": "a", "kind": "note"},
            {"id": "b", "kind": "note", "depends_on": ["a"]},
        ])
        by_id = {t["id"]: t for t in store.plan(pid)["tasks"]}
        ready = [t["id"] for t in store.ready_tasks(pid)]
        assert ready == [by_id[pid + "-a"]["id"]]
        store.mark_done(by_id[pid + "-a"]["id"], {"v": 1})
        ready = [t["id"] for t in store.ready_tasks(pid)]
        assert ready == [by_id[pid + "-b"]["id"]]

    def test_reset_stale_running(self, store):
        pid = _mk(store, [{"id": "a", "kind": "note"}])
        tid = store.plan(pid)["tasks"][0]["id"]
        store.mark_running(tid)
        assert store.reset_stale_running(pid) == 1
        assert store.task(tid)["state"] == "pending"

    def test_resolve_refs(self):
        out = TaskStore.resolve_refs(
            {"code": "x = {{gen.result}}", "n": "{{gen.result}}"},
            {"gen": {"value": 42}},
        )
        assert out["n"] == {"value": 42}
        assert '"value": 42' in out["code"]

    def test_resolve_refs_missing_raises(self):
        with pytest.raises(KeyError, match="unresolved"):
            TaskStore.resolve_refs({"x": "{{ghost.result}}"}, {})


# ── executor ──────────────────────────────────────────────────────────────
class TestExecutor:
    def test_linear_chain_with_artifacts(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        pid = _mk(store, [
            {"id": "src", "kind": "note", "payload": {"text": "hello"}},
            {"id": "sink", "kind": "kernel", "depends_on": ["src"],
             "payload": {"code": "print({{src.result}})"},
             "max_attempts": 2},
        ])
        seen = {}

        def fake_kernel(self, payload):
            seen["code"] = payload["code"]
            return {"ok": True, "result": {"output": "ran"}}

        monkeypatch.setattr(GraphExecutor, "_exec_kernel", fake_kernel)
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "done"
        assert seen["code"] == "print({\"note\": \"hello\"})"

    def test_parallel_branches_actually_overlap(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        pid = _mk(store, [
            {"id": "p1", "kind": "note"},
            {"id": "p2", "kind": "note"},
            {"id": "join", "kind": "note",
             "depends_on": ["p1", "p2"]},
        ])
        barrier = threading.Barrier(2, timeout=10)
        calls = {"n": 0}

        def slow_note(self, payload):  # both p1+p2 must run concurrently
            calls["n"] += 1
            if calls["n"] <= 2:  # only the two leaves wait; join passes
                barrier.wait()
            return {"ok": True, "result": "met"}

        monkeypatch.setattr(GraphExecutor, "_exec_note", slow_note)
        started = time.time()
        summary = GraphExecutor(store, pid, max_workers=2,
                                default_cell_timeout_s=15).run()
        assert summary["states"].get("done") == 3
        assert time.time() - started < 9  # serial execution would barrier-timeout

    def test_failure_routes_around_dead_branch(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        pid = _mk(store, [
            {"id": "bad", "kind": "tool"},
            {"id": "downstream", "kind": "note", "depends_on": ["bad"]},
            {"id": "independent", "kind": "note"},
        ])
        calls = {"bad": 0}

        def failing_tool(self, payload):
            calls["bad"] += 1
            return {"ok": False, "error": "simulated"}

        # patch at the KIND level so mark_running/attempts bookkeeping
        # (inside _execute_task) still runs -- otherwise max_attempts=1
        # reads stale attempts=0 and the task retries forever.
        monkeypatch.setattr(GraphExecutor, "_exec_tool", failing_tool)
        summary = GraphExecutor(store, pid).run()
        assert calls["bad"] == 1
        assert summary["final_state"] == "failed"
        plan = store.plan(pid)
        states = {t["id"]: t["state"] for t in plan["tasks"]}
        assert states[pid + "-downstream"] == "skipped"
        assert states[pid + "-independent"] == "done"

    def test_retry_recovers_flaky_task(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        pid = _mk(store, [{"id": "flaky", "kind": "tool",
                           "max_attempts": 3}])
        attempts = {"n": 0}

        def flaky_tool(self, payload):
            attempts["n"] += 1
            if attempts["n"] < 2:
                return {"ok": False, "error": "transient"}
            return {"ok": True, "result": "recovered"}

        monkeypatch.setattr(GraphExecutor, "_exec_tool", flaky_tool)
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "done"
        assert attempts["n"] == 2
        row = store.plan(pid)["tasks"][0]
        assert row["attempts"] == 2 and row["state"] == "done"

    def test_resume_skips_completed_nodes(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        pid = _mk(store, [
            {"id": "first", "kind": "note"},
            {"id": "second", "kind": "note", "depends_on": ["first"]},
        ])
        runs = {"n": 0}
        real = GraphExecutor._exec_note

        def counting(self, payload):
            runs["n"] += 1
            return {"ok": True, "result": "x"}

        monkeypatch.setattr(GraphExecutor, "_exec_note", counting)
        # simulate a crash after the first node finished
        first_id = store.plan(pid)["tasks"][0]["id"]
        store.mark_done(first_id, {"partial": True})
        GraphExecutor(store, pid).run(resume=True)
        assert runs["n"] == 1  # only 'second' executed

    def test_unknown_plan(self, store):
        from ariadne_runtime.graph_exec import GraphExecutor

        summary = GraphExecutor(store, "plan-nope").run()
        assert summary["ok"] is False


# ── interpreter for registry results ─────────────────────────────────────
class TestInterpretToolResult:
    def test_registry_error_dict(self):
        from ariadne_runtime.graph_exec import _interpret_tool_result

        out = _interpret_tool_result("t", {"error": "nope"})
        assert out["ok"] is False and "nope" in out["error"]

    def test_plain_string_ok(self):
        from ariadne_runtime.graph_exec import _interpret_tool_result

        out = _interpret_tool_result("t", "file contents here")
        assert out["ok"] is True and "contents" in out["result"]

    def test_error_string_detected(self):
        from ariadne_runtime.graph_exec import _interpret_tool_result

        out = _interpret_tool_result("t", "Tool execution failed: ValueError: x")
        assert out["ok"] is False


# ── tool surface (JSON in/out) ────────────────────────────────────────────
class TestToolSurface:
    def test_create_and_status_end_to_end(self):
        created = json.loads(handle_ariadne_plan({
            "action": "create", "goal": "demo",
            "tasks": [
                {"id": "n1", "kind": "note", "payload": {"text": "hi"}},
                {"id": "n2", "kind": "note", "depends_on": ["n1"]},
            ],
        }))
        assert created["ok"] is True
        pid = created["plan_id"]
        assert "ariadne_exec" in created["next"]
        st = json.loads(handle_ariadne_exec({"action": "status",
                                             "plan_id": pid}))
        assert st["ok"] is True and st["plan_state"] == "draft"

    def test_run_note_plan_end_to_end(self):
        created = json.loads(handle_ariadne_plan({
            "action": "create", "goal": "notes only",
            "tasks": [{"id": "only", "kind": "note",
                       "payload": {"text": "annotate"}}],
        }))
        ran = json.loads(handle_ariadne_exec({
            "action": "run", "plan_id": created["plan_id"]}))
        assert ran["final_state"] == "done"
        got = json.loads(handle_ariadne_plan({
            "action": "get", "plan_id": created["plan_id"]}))
        assert got["tasks"][0]["state"] == "done"
        assert got["tasks"][0]["result"]["note"] == "annotate"

    def test_validation_errors_surface(self):
        bad = json.loads(handle_ariadne_plan({
            "action": "create", "goal": "g",
            "tasks": [{"id": "c1", "kind": "note", "depends_on": ["c1"]}]}))
        assert bad["ok"] is False and "cycle" in bad["error"].lower()

    def test_list_and_delete(self):
        created = json.loads(handle_ariadne_plan({
            "action": "create", "goal": "temp",
            "tasks": [{"id": "x", "kind": "note"}]}))
        listing = json.loads(handle_ariadne_plan({"action": "list"}))
        assert any(p["id"] == created["plan_id"] for p in listing["plans"])
        gone = json.loads(handle_ariadne_plan({
            "action": "delete", "plan_id": created["plan_id"]}))
        assert gone["ok"] is True

    def test_mirror_into_context_graph(self):
        created = json.loads(handle_ariadne_plan({
            "action": "create", "goal": "mirrored",
            "tasks": [{"id": "m1", "kind": "note"},
                      {"id": "m2", "kind": "note", "depends_on": ["m1"]}]}))
        pid = created["plan_id"]
        sg = cg.get_store().subgraph([f"task:{pid}-m1"],
                                     depth=2, limit=20)
        keys = {n["key"] for n in sg["nodes"]}
        assert f"{pid}-m1" in keys

    def test_unknown_action_message(self):
        out = json.loads(handle_ariadne_plan({"action": "yolo"}))
        assert out["ok"] is False and "valid" in out["error"].lower()
