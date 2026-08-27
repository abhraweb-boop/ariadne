"""Refine + heals endpoint tests (S: self-learning)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("HERMES_HOME", str(Path(__file__).parent / ".tmp-home"))

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes_cli.web_routers import ariadne_kernel


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    app = FastAPI()
    app.include_router(ariadne_kernel.router)
    return TestClient(app)


def test_heals_empty(client):
    r = client.get("/api/ariadne/heals")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "heals": []}


def test_heals_reads_sentinel(client):
    heals_path = Path(os.environ["HERMES_HOME"]) / "ariadne" / "heals.json"
    heals_path.parent.mkdir(parents=True, exist_ok=True)
    heals_path.write_text('[{"what": "restarted gateway", "outcome": "ok"}]', encoding="utf-8")
    r = client.get("/api/ariadne/heals")
    assert r.status_code == 200
    assert r.json()["heals"][0]["what"] == "restarted gateway"


def test_refine_records_entry(client):
    r = client.post("/api/ariadne/refine", json={"goal": "improve terminal pane"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["entry"]["kind"] == "refine"
