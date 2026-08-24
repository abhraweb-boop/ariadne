"""ariadne_prime tool surface tests (engine mocked, no node spawn)."""

from __future__ import annotations

import json

import pytest

from tools.ariadne_prime_tool import (
    TOOL_NAME,
    handle_ariadne_prime,
)


@pytest.fixture(autouse=True)
def _reset_engine_singleton(monkeypatch):
    import ariadne.prime_engine as pe

    monkeypatch.setattr(pe, "_engine", None, raising=True)
    yield
    monkeypatch.setattr(pe, "_engine", None, raising=True)


class FakeEngine:
    def __init__(self, *, fail=None):
        self.fail = fail
        self.pid = 4242
        self.prompts = []

    def state(self, timeout_s=None):
        if self.fail == "state":
            raise RuntimeError("rpc write failed: pipe gone")
        return {"success": True,
                "result": {"model": "fake", "session": "s-0"}}

    def new_session(self, timeout_s=None):
        return {"success": True, "result": {"session": "sess-2"}}

    def steer(self, text, timeout_s=None):
        return {"success": True, "result": {"steered": True}}

    def prompt(self, text, timeout_s=None, **kw):
        self.prompts.append(text)
        if self.fail == "timeout":
            raise TimeoutError("prime prompt timed out")
        if self.fail == "nokey":
            return {"ok": False, "text": "", "events": [],
                    "raw": {"success": False, "error": "no_key"}}
        return {"ok": True, "text": f"echo: {text}", "events": [1, 2],
                "raw": {"success": True}}


def _bind(monkeypatch, engine):
    import ariadne.prime_engine as pe

    monkeypatch.setattr(pe, "get_engine", lambda: engine, raising=True)


def test_run_happy(monkeypatch):
    eng = FakeEngine()
    _bind(monkeypatch, eng)
    out = json.loads(handle_ariadne_prime(
        {"action": "run", "prompt": "refactor auth"}))
    assert out["ok"] is True and out["text"] == "echo: refactor auth"
    assert eng.prompts == ["refactor auth"]


def test_run_requires_prompt():
    out = json.loads(handle_ariadne_prime({"action": "run"}))
    assert out["ok"] is False and "non-empty prompt" in out["error"]


def test_no_key_is_structured_not_crash(monkeypatch):
    _bind(monkeypatch, FakeEngine(fail="nokey"))
    out = json.loads(handle_ariadne_prime(
        {"action": "run", "prompt": "x"}))
    assert out["ok"] is False and "no_key" in out["error"]


def test_timeout_gives_hint(monkeypatch):
    _bind(monkeypatch, FakeEngine(fail="timeout"))
    out = json.loads(handle_ariadne_prime(
        {"action": "run", "prompt": "x"}))
    assert out["ok"] is False and "hint" in out


def test_status_reports_running(monkeypatch):
    _bind(monkeypatch, FakeEngine())
    out = json.loads(handle_ariadne_prime({"action": "status"}))
    assert out["running"] is True and out["pid"] == 4242


def test_steer_and_new_session(monkeypatch):
    _bind(monkeypatch, FakeEngine())
    s = json.loads(handle_ariadne_prime(
        {"action": "steer", "message": "go left"}))
    n = json.loads(handle_ariadne_prime({"action": "new_session"}))
    assert s["ok"] and n["result"]["session"] == "sess-2"


def test_unknown_action_lists_valid():
    out = json.loads(handle_ariadne_prime({"action": "vibes"}))
    assert out["ok"] is False and "new_session" in out["error"]
