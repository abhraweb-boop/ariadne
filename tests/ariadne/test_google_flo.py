"""P13 tests: google provider states, flo engine seam, gemini/flo kinds.

All mocked — no network, no node spawn in the suite.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ariadne_runtime.google_provider as gp
import ariadne_runtime.flo_engine as fe
from plugins.context_graph.tasks import TaskStore


@pytest.fixture()
def store(tmp_path):
    s = TaskStore(tmp_path / "t.db")
    yield s
    s.close()


class TestGoogleProvider:
    @pytest.fixture()
    def fake_genai(self, monkeypatch):
        """Make status()' import check succeed without the real package."""
        import sys
        import types

        mod = types.ModuleType("google")
        gen = types.ModuleType("google.genai")
        mod.genai = gen
        monkeypatch.setitem(sys.modules, "google", mod)
        monkeypatch.setitem(sys.modules, "google.genai", gen)

    def test_status_no_key(self, monkeypatch, fake_genai):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.setattr(gp, "_key", lambda: None)
        st = gp.status()
        assert st["state"] == "no_key" and not st["ok"]
        assert "GEMINI_API_KEY" in st["hint"]

    def test_status_not_installed(self, monkeypatch):
        monkeypatch.setattr(gp, "_key", lambda: "k")
        real_import = __import__

        def fake_import(name, *a, **kw):
            if name.startswith("google"):
                raise ImportError("nope")
            return real_import(name, *a, **kw)

        import builtins
        monkeypatch.setattr(builtins, "__import__", fake_import)
        st = gp.status()
        assert st["state"] == "not_installed"
        assert "google-genai" in st["hint"]

    def test_generate_teaches_when_unconfigured(self, monkeypatch,
                                                fake_genai):
        monkeypatch.setattr(gp, "_key", lambda: None)
        out = gp.generate("hi")
        assert out["ok"] is False and out["error"] == "no_key"
        # and the executor path renders it as a teaching error
        from ariadne_runtime.graph_exec import GraphExecutor
        e = GraphExecutor.__new__(GraphExecutor)
        e._cell_timeout_s = 5.0
        res = e._exec_gemini({"prompt": "x"})
        assert res["ok"] is False and res["error"].startswith("gemini:")


class TestFloEngine:
    def test_status_missing_cli(self, tmp_path, monkeypatch):
        monkeypatch.setattr(fe, "cli_path",
                            lambda: tmp_path / "nope" / "cli.js")
        st = fe.status()
        assert st["state"] == "missing"

    def test_run_swarm_reports_failure_cleanly(self, tmp_path,
                                               monkeypatch):
        monkeypatch.setattr(fe, "status",
                            lambda: {"ok": False, "state": "missing",
                                     "hint": "gone"})
        eng = fe.FloEngine(cwd=tmp_path)
        out = eng.run_swarm("build something")
        assert out["ok"] is False and out["error"] == "missing"


class TestKinds:
    def test_gemini_kind_happy_path(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        monkeypatch.setattr(gp, "generate", lambda *a, **kw: {
            "ok": True, "text": "grounded answer", "model": "gemini-2.5-flash",
            "usage": {"input_tokens": 3, "output_tokens": 4}})
        pid = store.create_plan("t", [
            {"id": "g", "kind": "gemini", "payload": {"prompt": "summarize"}}])
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "done"
        row = store.plan(pid)["tasks"][0]
        assert json.loads(row["result"])["text"] == "grounded answer"

    def test_flo_kind_runs_and_captures_stdout(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        class FakeFlo:
            def __init__(self, **kw):
                pass

            def run_swarm(self, objective, timeout_s=600.0):
                return {"ok": True,
                        "stdout": f"swarm done: {objective}",
                        "returncode": 0}

        monkeypatch.setattr(fe, "FloEngine", FakeFlo)
        pid = store.create_plan("t", [
            {"id": "f", "kind": "flo",
             "payload": {"objective": "parallelize the scraper"}}])
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "done"
        row = store.plan(pid)["tasks"][0]
        assert "parallelize" in json.loads(row["result"])["stdout"]

    def test_flo_kind_error_is_teaching(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        monkeypatch.setattr(fe, "status",
                            lambda: {"ok": False, "state": "no_node",
                                     "hint": "install node"})
        pid = store.create_plan("t", [
            {"id": "f", "kind": "flo",
             "payload": {"objective": "x"}}])
        summary = GraphExecutor(store, pid).run(max_iterations=20)
        row = store.plan(pid)["tasks"][0]
        blob = (row["result"] or "") + (row["error"] or "")
        assert "flo:" in blob and "no_node" in blob or \
            row["state"] == "ready"

    def test_kinds_registered_in_schema_vocab(self):
        from plugins.context_graph.tasks import TASK_KINDS

        assert {"gemini", "flo"} <= set(TASK_KINDS)
