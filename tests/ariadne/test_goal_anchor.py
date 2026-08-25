"""Goal anchoring + drift sentinel tests (all mocked, hermetic)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ariadne_runtime.goal_anchor as ga

from plugins.context_graph.tasks import TaskStore


@pytest.fixture()
def store(tmp_path):
    s = TaskStore(tmp_path / "t.db")
    yield s
    s.close()


class TestBuildAnchor:
    def test_contains_all_three_lines(self):
        a = ga.build_anchor("Build a habit tracker", "Add weekly view")
        assert "[GOAL]" in a and "habit tracker" in a
        assert "[MILESTONE]" in a and "weekly view" in a
        assert "[SCOPE]" in a and "ONLY" in a.upper()

    def test_truncates_long_inputs(self):
        a = ga.build_anchor("x" * 5000, "y" * 5000)
        assert len(a) < 1200

    def test_empty_title_still_works(self):
        a = ga.build_anchor("goal only", "")
        assert "[GOAL]" in a and "[MILESTONE]" not in a


class TestCapArtifact:
    def test_small_result_untouched(self):
        s = "hello world"
        assert ga.cap_artifact(s) == s

    def test_large_result_capped_with_marker(self):
        big = "A" * 50_000
        out = ga.cap_artifact(big, limit=2048)
        assert len(out) < 2500
        assert "truncated" in out
        assert out.startswith("A") and out.rstrip().endswith("A")

    def test_non_string_coerced(self):
        assert ga.cap_artifact({"a": 1}) == '{"a": 1}' or \
            "a" in ga.cap_artifact({"a": 1})


class TestAnchoredPrompts:
    """Task 2: every model-calling node's prompt starts with the anchor."""

    def _plan_with_prime(self, store):
        pid = store.create_plan("Build a habit tracker", [
            {"id": "w", "kind": "prime", "payload": {"prompt": "make it"}}])
        return pid

    def test_prime_prompt_carries_anchor(self, store, monkeypatch):
        import ariadne.prime_engine as pe
        from ariadne_runtime.graph_exec import GraphExecutor

        captured = {}

        class FakeEng:
            pid = 1

            def state(self, timeout_s=None):
                return {"success": True,
                        "data": {"model": {"id": "fake", "provider": "x"}}}

            def prompt(self, text, timeout_s=None, **kw):
                captured["text"] = text
                return {"ok": True, "text": "done", "events": [1],
                        "raw": {"success": True}}

        monkeypatch.setattr(pe, "get_engine", lambda: FakeEng())
        pid = self._plan_with_prime(store)
        GraphExecutor(store, pid).run()
        assert captured["text"].startswith("[GOAL]")
        assert "habit tracker" in captured["text"]
        assert captured["text"].endswith("make it")

    def test_gemini_prompt_startswith_goal(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor
        prompts = []
        monkeypatch.setattr(gp_stub, "status",
                            lambda: {"ok": True, "state": "ok"})

        def fake_gen(prompt, **kw):
            prompts.append(prompt)
            return {"ok": True, "text": "ok"}

        monkeypatch.setattr(gp_stub, "generate", fake_gen)
        pid = store.create_plan("Build a habit tracker", [
            {"id": "g", "kind": "gemini", "payload": {"prompt": "sum"}}])
        GraphExecutor(store, pid).run()
        # first call = the node prompt (anchored); later call may be the judge
        assert prompts[0].startswith("[GOAL]")
        assert "habit tracker" in prompts[0]
        assert "[SCOPE]" in prompts[0]

    def test_flo_objective_startswith_goal(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor
        import ariadne_runtime.flo_engine as fe_mod

        class FakeFlo:
            def __init__(self, **kw):
                pass

            def run_swarm(self, objective, timeout_s=600.0):
                self.objective = objective
                FakeFlo.last = objective
                return {"ok": True, "stdout": "swam", "returncode": 0}

        monkeypatch.setattr(fe_mod, "FloEngine", FakeFlo)
        pid = store.create_plan("Build a habit tracker", [
            {"id": "f", "kind": "flo",
             "payload": {"objective": "parallelize"}}])
        GraphExecutor(store, pid).run()
        assert FakeFlo.last.startswith("[GOAL]")
        assert "parallelize" in FakeFlo.last


gp_stub = __import__(
    "ariadne_runtime.google_provider", fromlist=["status"])


gp_stub = __import__(
    "ariadne_runtime.google_provider", fromlist=["status"])


class TestDriftSentinel:
    """Task 4: judge runs after prime nodes; DRIFT fails + refocuses."""

    def _plan(self, store):
        return store.create_plan("Build a habit tracker", [
            {"id": "w", "kind": "prime",
             "payload": {"prompt": "do the thing"},
             "max_attempts": 2}])

    def _wire(self, monkeypatch, judge_results):
        import ariadne.prime_engine as pe
        import ariadne_runtime.goal_anchor as ga_mod
        from ariadne_runtime.graph_exec import GraphExecutor

        calls = {"n": 0}
        prompts = []

        class FakeEng:
            pid = 1

            def state(self, timeout_s=None):
                return {"success": True,
                        "data": {"model": {"id": "fake", "provider": "x"}}}

            def prompt(self, text, timeout_s=None, **kw):
                calls["n"] += 1
                prompts.append(text)
                # first attempt wanders off-goal; second stays on-task
                text_out = ("a blog engine about cooking" if calls["n"] == 1
                            else "created habits table + weekly view")
                return {"ok": True, "text": text_out, "events": [1],
                        "raw": {"success": True}}

        monkeypatch.setattr(pe, "get_engine", lambda: FakeEng())
        # NOTE: no _exec_prime patch here — FakeEng handles the engine seam
        # judge says DRIFT on the wandering output, PASS on the focused one
        monkeypatch.setattr(
            ga_mod, "judge_output",
            lambda goal, title, out: (
                "built a blog engine" if "blog" in out else None))
        # keep google status happy for the real generate path (unused here)
        monkeypatch.setattr(gp_stub, "status",
                            lambda: {"ok": True, "state": "ok"})
        return prompts

    def test_drift_fails_then_refocused_retry_passes(self, store,
                                                     monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor

        prompts = self._wire(monkeypatch, None)
        pid = self._plan(store)
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "done"
        assert len(prompts) == 2
        assert "[GOAL]" in prompts[0]
        assert "[REFOCUS]" in prompts[1] and "blog engine" in prompts[1]

    def test_judge_optout_skips_sentinel(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor
        import ariadne.prime_engine as pe

        judged = {"hit": False}

        class FakeEng:
            pid = 1

            def state(self, timeout_s=None):
                return {"success": True,
                        "data": {"model": {"id": "f", "provider": "x"}}}

            def prompt(self, text, timeout_s=None, **kw):
                return {"ok": True, "text": "off-topic rambling",
                        "events": [], "raw": {"success": True}}

        monkeypatch.setattr(pe, "get_engine", lambda: FakeEng())
        import ariadne_runtime.goal_anchor as ga_mod

        def spy(goal, title, out):
            judged["hit"] = True
            return None

        monkeypatch.setattr(ga_mod, "judge_output", spy)
        pid = store.create_plan("g", [
            {"id": "w", "kind": "prime",
             "payload": {"prompt": "p", "judge": False}}])
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "done"
        assert judged["hit"] is False

    def test_tool_nodes_never_judged(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor
        import ariadne_runtime.goal_anchor as ga_mod

        judged = {"hit": False}

        def spy(goal, title, out):
            judged["hit"] = True
            return "would fail"

        monkeypatch.setattr(ga_mod, "judge_output", spy)
        pid = store.create_plan("g", [{"id": "t", "kind": "tool"}])

        def fake_tool(self, payload):
            return {"ok": True, "result": "anything"}

        monkeypatch.setattr(GraphExecutor, "_exec_tool", fake_tool)
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "done"
        assert judged["hit"] is False


class TestContextPackCap:
    """Task 3: oversized upstream artifacts are capped in payloads."""

    def test_big_upstream_result_is_capped(self, store):
        from ariadne_runtime.graph_exec import GraphExecutor

        big = json.dumps({"stdout": "X" * 100_000})
        pid = store.create_plan("cap test", [
            {"id": "src", "kind": "note"},
            {"id": "dst", "kind": "prime",
             "depends_on": ["src"],
             "payload": {"prompt": "context: {{src.result}}"}},
        ])
        src_id = [t for t in store.plan(pid)["tasks"]
                  if t["id"].endswith("-src")][0]["id"]
        store.mark_running(src_id)
        store.mark_done(src_id, big)
        ex = GraphExecutor(store, pid)
        task = [t for t in store.plan(pid)["tasks"]
                if t["id"].endswith("-dst")][0]
        resolved = json.dumps(ex._resolve_payload(task))
        assert len(resolved) < 8000
        assert "truncated" in resolved


class TestJudgeOutput:
    def test_pass_verdict_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            "ariadne_runtime.google_provider.generate",
            lambda *a, **kw: {"ok": True, "text": "PASS"})
        assert ga.judge_output("build a tracker", "scaffold",
                               "created app.py with habits table") is None

    def test_drift_verdict_returns_reason(self, monkeypatch):
        monkeypatch.setattr(
            "ariadne_runtime.google_provider.status",
            lambda: {"ok": True, "state": "ok"})
        monkeypatch.setattr(
            "ariadne_runtime.google_provider.generate",
            lambda *a, **kw: {"ok": True,
                              "text": "DRIFT: output builds a blog "
                                      "engine instead of a tracker"})
        reason = ga.judge_output("habit tracker", "scaffold",
                                 "# blog engine tutorial...")
        assert reason and "blog" in reason

    def test_unconfigured_google_is_silent_skip(self, monkeypatch):
        monkeypatch.setattr(
            "ariadne_runtime.google_provider.generate",
            lambda *a, **kw: {"ok": False, "error": "no_key"})
        assert ga.judge_output("g", "t", "out") is None

    def test_garbage_verdict_treated_as_pass(self, monkeypatch):
        # judge must be conservative: anything that isn't a clear DRIFT passes
        monkeypatch.setattr(
            "ariadne_runtime.google_provider.generate",
            lambda *a, **kw: {"ok": True, "text": "looks fine to me"})
        assert ga.judge_output("g", "t", "out") is None

    def test_judge_input_capped(self, monkeypatch):
        seen = {}

        def fake_generate(prompt, **kw):
            seen["prompt"] = prompt
            return {"ok": True, "text": "PASS"}

        monkeypatch.setattr(
            "ariadne_runtime.google_provider.status",
            lambda: {"ok": True, "state": "ok"})
        monkeypatch.setattr(
            "ariadne_runtime.google_provider.generate", fake_generate)
        ga.judge_output("g", "t", "Z" * 100_000)
        assert len(seen["prompt"]) < 8000
