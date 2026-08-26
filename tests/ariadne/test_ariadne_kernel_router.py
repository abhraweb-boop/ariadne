"""Kernel + ledger REST router tests (kernel svc faked; ledger real)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault(
    "HERMES_HOME", str(Path.home() / "AppData" / "Local" / "Temp" / "ariadne-test-home")
)

from hermes_cli.web_routers import ariadne_kernel as kr  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    (tmp_path / "ariadne").mkdir(parents=True, exist_ok=True)


class FakeSvc:
    def __init__(self):
        self.calls: list[str] = []

    def start_kernel(self):
        self.calls.append("start")
        return {"ok": True, "running": True}

    def kernel_status(self):
        self.calls.append("status")
        return {"running": True, "cells": 3}

    def execute_cell(self, code, timeout_s=120):
        self.calls.append("execute")
        return {"ok": True, "output": "42", "status": "ok"}

    def shutdown_kernel(self, force=True):
        self.calls.append("stop")
        return {"ok": True}


@pytest.fixture()
def fake_svc(monkeypatch):
    svc = FakeSvc()
    monkeypatch.setattr(kr, "_svc", lambda: svc)
    return svc


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(kr.router)
    return TestClient(app)


# ── kernel ───────────────────────────────────────────────────────────────


def test_kernel_start(fake_svc):
    c = _client()
    r = c.post("/api/ariadne/kernel/start")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert fake_svc.calls == ["start"]


def test_kernel_status(fake_svc):
    c = _client()
    r = c.get("/api/ariadne/kernel/status")
    assert r.status_code == 200
    assert r.json()["cells"] == 3


def test_kernel_execute_requires_code(fake_svc):
    c = _client()
    assert c.post("/api/ariadne/kernel/execute", json={}).status_code == 400


def test_kernel_execute(fake_svc):
    c = _client()
    r = c.post("/api/ariadne/kernel/execute", json={"code": "6*7"})
    assert r.status_code == 200
    assert r.json()["output"] == "42"


def test_kernel_stop(fake_svc):
    c = _client()
    r = c.post("/api/ariadne/kernel/stop")
    assert r.status_code == 200
    assert fake_svc.calls == ["stop"]


# ── ledger (real MemoryLedger over temp HERMES_HOME) ─────────────────────


def test_ledger_entries_empty(tmp_path):
    c = _client()
    r = c.get("/api/ariadne/ledger/entries")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "entries": []}


def test_ledger_add_rollback_flow(tmp_path):
    from plugins.memory.ariadne.ledger import MemoryLedger

    ledger = MemoryLedger(tmp_path / "ariadne" / "memory.db")
    entry = ledger.add(body="original", kind="memory")
    eid = entry["id"]
    ledger.update(eid, body="edited")
    ledger.close()

    c = _client()
    entry = c.get(f"/api/ariadne/ledger/{eid}").json()
    assert entry["ok"] is True
    assert entry["entry"]["body"] == "edited"
    assert len(entry["history"]) >= 2

    rolled = c.post(f"/api/ariadne/ledger/{eid}/rollback", json={}).json()
    assert rolled["ok"] is True
    assert rolled["entry"]["body"] == "original"
