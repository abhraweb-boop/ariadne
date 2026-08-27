"""Prime RPC router tests — hermetic (no real bridge, no subprocess).

The bridge import is guarded: tests force it unavailable (monkeypatch
sys.path / import) to exercise the 503 path, and use a fake bridge module
to exercise the happy paths.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import hermes_cli.web_routers.ariadne_prime as rp  # noqa: E402


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(rp.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_bridge():
    """Reset the module-level singleton between tests."""
    rp._bridge = None
    yield
    rp._bridge = None


class _FakeBridge:
    def __init__(self):
        self.started = False
        self.state = None

    def start(self):
        self.started = True
        self.state = {"model": "fake", "session": "s1"}

    def get_state(self):
        return self.state

    def prompt(self, message, stream=True, timeout=None):
        return f"response-to: {message}"

    def steer(self, message, **kwargs):
        pass

    def stop(self):
        self.state = None
        self.started = False


def test_state_when_unavailable(client, monkeypatch):
    """Bridge import fails -> running False, no 500."""
    def _boom():
        return None
    monkeypatch.setattr(rp, "_load_bridge", _boom)
    r = client.get("/api/ariadne/prime/state")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "running": False, "state": None}


def test_start_when_unavailable_returns_503(client, monkeypatch):
    def _boom():
        return None
    monkeypatch.setattr(rp, "_load_bridge", _boom)
    r = client.post("/api/ariadne/prime/start")
    assert r.status_code == 503
    assert "unavailable" in r.json()["detail"]


def test_start_and_state_happy_path(client, monkeypatch):
    fake = _FakeBridge()
    monkeypatch.setattr(rp, "_load_bridge", lambda: fake)
    r = client.post("/api/ariadne/prime/start")
    assert r.status_code == 200
    assert r.json()["running"] is True
    assert r.json()["state"]["model"] == "fake"

    r = client.get("/api/ariadne/prime/state")
    assert r.status_code == 200
    assert r.json()["running"] is True


def test_prompt_starts_then_responds(client, monkeypatch):
    fake = _FakeBridge()
    monkeypatch.setattr(rp, "_load_bridge", lambda: fake)
    r = client.post("/api/ariadne/prime/prompt", json={"goal": "refactor auth"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["response"] == "response-to: refactor auth"
    assert fake.started is True


def test_prompt_empty_goal_rejected(client, monkeypatch):
    fake = _FakeBridge()
    monkeypatch.setattr(rp, "_load_bridge", lambda: fake)
    r = client.post("/api/ariadne/prime/prompt", json={"goal": "   "})
    assert r.status_code == 400


def test_steer_and_stop(client, monkeypatch):
    fake = _FakeBridge()
    monkeypatch.setattr(rp, "_load_bridge", lambda: fake)
    fake.start()
    r = client.post("/api/ariadne/prime/steer", json={"message": "RLM review"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r = client.post("/api/ariadne/prime/stop")
    assert r.status_code == 200
    assert fake.started is False
