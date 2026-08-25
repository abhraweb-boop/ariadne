"""ErrorDoctor + BudgetGovernor tests (no network; pip install mocked)."""

from __future__ import annotations

import pytest

import ariadne_runtime.doctor as doc
from ariadne_runtime.doctor import BudgetGovernor, ErrorDoctor, classify


class TestClassifier:
    def test_transient(self):
        for msg in ("connection reset by peer", "read timed out",
                    "HTTP 429 too many requests"):
            assert classify(msg).cls == "transient"
        assert classify("503 service unavailable").cls == "transient"

    def test_environmental_missing_module(self):
        d = classify("ModuleNotFoundError: No module named 'pyzmq'")
        assert d.cls == "environmental"
        assert d.action == "install_dep"
        assert d.extract.get("mod") == "pyzmq"

    def test_environmental_port_busy(self):
        d = classify("OSError: [Errno 98] Address already in use")
        assert d.cls == "environmental" and d.action == "rebind_port"

    def test_environmental_missing_path(self):
        d = classify("FileNotFoundError: [Errno 2] No such file or "
                     "directory: 'out/reports/x.md'")
        assert d.cls == "environmental" and d.action == "ensure_dir"

    def test_logical(self):
        d = classify("AssertionError: expected 4 got 5")
        assert d.cls == "logical" and d.action == "prime_patch"
        assert classify("3 failed, 2 passed in 1.2s").cls == "logical"

    def test_env_beats_logic_when_both(self):
        # traceback mentioning missing module -> environmental
        blob = ("Traceback (most recent call last):\n"
                "ImportError: No module named 'yaml'")
        assert classify(blob).cls == "environmental"

    def test_permanent_is_conservative(self):
        d = classify("invalid api key")
        assert d.cls == "permanent"


class TestErrorDoctor:
    def test_transient_heals_via_retry(self):
        doctor = ErrorDoctor()
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                return {"ok": False, "error": "connection reset"}
            return {"ok": True}

        out = doctor.run_task(flaky, max_rounds=3)
        assert out["ok"] is True and calls["n"] == 2
        assert any(e["cls"] == "transient" for e in doctor.journal)

    def test_install_dep_playbook_runs(self, monkeypatch):
        installed = {}
        monkeypatch.setattr(ErrorDoctor, "_pb_install_dep",
                            staticmethod(lambda mod: f"installed {mod}"))
        doctor = ErrorDoctor()
        state = {"n": 0}

        def needs_dep():
            state["n"] += 1
            if state["n"] == 1:
                return {"ok": False,
                        "error": "No module named 'leftpad'"}
            return {"ok": True}

        out = doctor.run_task(needs_dep)
        assert out["ok"] is True
        entry = [e for e in doctor.journal
                 if e["action"] == "install_dep"][0]
        assert "installed leftpad" in str(entry["extra"])

    def test_logical_escalates_after_exhaustion(self):
        doctor = ErrorDoctor()

        def always_buggy():
            return {"ok": False, "error": "AssertionError: 1 != 2"}

        out = doctor.run_task(always_buggy, max_rounds=2)
        assert out["exhausted"] is True
        assert len(doctor.journal) == 2  # one heal per round

    def test_permanent_bubbles_immediately(self):
        doctor = ErrorDoctor()
        calls = {"n": 0}

        def bad_key():
            calls["n"] += 1
            return {"ok": False, "error": "invalid api key"}

        out = doctor.run_task(bad_key, max_rounds=3)
        assert out["permanent"] is True and calls["n"] == 1
        assert doctor.journal[-1]["action"] == "escalate"

    def test_exception_path_classified(self):
        doctor = ErrorDoctor()
        state = {"n": 0}

        def raises_once():
            state["n"] += 1
            if state["n"] == 1:
                raise TimeoutError("operation timed out")
            return {"ok": True}

        out = doctor.run_task(raises_once)
        assert out["ok"] is True


class TestBudgetGovernor:
    def test_warn_at_half_pause_at_cap(self):
        g = BudgetGovernor(cap_usd=10.0)
        r1 = g.record(4.0)
        assert not r1["warned"]
        r2 = g.record(2.0)                      # 6.0 >= 5.0 -> warn
        assert r2["warned"] and not r2["paused"]
        r3 = g.record(5.0)                      # 11.0 >= 10 -> pause
        assert r3["paused"]
        assert g.gate() == {"allowed": False, "spent": 11.0, "cap": 10.0,
                            "paused": True}
        g.resume()
        assert g.gate()["allowed"] is True

    def test_doctor_respects_budget_gate(self):
        budget = BudgetGovernor(cap_usd=1.0)
        budget.record(2.0)                       # trips pause
        doctor = ErrorDoctor(budget=budget)
        ran = {"n": 0}

        def task():
            ran["n"] += 1
            return {"ok": True}

        out = doctor.run_task(task)
        assert out["paused"] is True and ran["n"] == 0
