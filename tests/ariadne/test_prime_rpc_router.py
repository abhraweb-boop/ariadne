"""Prime RPC router tests — fake bridge, no real subprocess, no model calls."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault(
    "HERMES_HOME", str(Path.home() / "AppData" / "Local" / "Temp" / "ariadne-test-home")
)

from hermes_cli.web_routers import prime_rpc  # noqa: E402


class FakeBridge:
    """Duck-typed stand-in for prime_bridge.PrimeBridge."""

    def __init__(self):
        self.started = False
        self.stopped = False
        self.prompts: list[str] = []
        self.steers: list[str] = []
        self.state_data = {"model": "fake", "session": "s1", "streaming": False}
        self.proc = type("P", (), {"pid": 4242})()

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def prompt(self, message, stream=False):
        self.prompts.append(message)
        return f"rid-{len(self.prompts)}"

    def steer(self, message, mode="one-at-a-time"):
        self.steers.append(message)

    def get_state(self):
        return self.state_data

    def poll_events(self):
        return []


@pytest.fixture(autouse=True)
def _fake_bridge(monkeypatch):
    bridge = FakeBridge()
    monkeypatch.setattr(prime_rpc, "_BRIDGE", bridge)
    # Keep the poller thread from actually running.
    monkeypatch.setattr(prime_rpc, "_POLLER", None)
    yield bridge
    # Ensure module-level state resets for the next test.
    monkeypatch.setattr(prime_rpc, "_BRIDGE", None)


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(prime_rpc.router)
    return TestClient(app)


def test_spawn_returns_ok_with_pid(_fake_bridge):
    c = _client()
    r = c.post("/api/prime/spawn")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["pid"] == 4242


def test_state_returns_bridge_state(_fake_bridge):
    c = _client()
    r = c.get("/api/prime/state")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["state"]["model"] == "fake"


def test_prompt_requires_text(_fake_bridge):
    c = _client()
    r = c.post("/api/prime/prompt", json={"prompt": ""})
    assert r.status_code == 400


def test_prompt_forwards_and_returns_rid(_fake_bridge):
    c = _client()
    r = c.post("/api/prime/prompt", json={"prompt": "refactor auth"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["request_id"].startswith("rid-")
    assert _fake_bridge.prompts == ["refactor auth"]


def test_steer_forwards(_fake_bridge):
    c = _client()
    r = c.post("/api/prime/steer", json={"message": "stop and review"})
    assert r.status_code == 200
    assert _fake_bridge.steers == ["stop and review"]


def test_stop_marks_bridge_stopped(_fake_bridge):
    c = _client()
    r = c.post("/api/prime/stop")
    assert r.status_code == 200
    assert _fake_bridge.stopped is True
