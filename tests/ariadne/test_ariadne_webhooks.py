"""Webhooks router tests — CRUD + validation, real temp HERMES_HOME."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("HERMES_HOME", str(Path(__file__).parent / ".tmp-home"))

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes_cli.web_routers import ariadne_webhooks


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    app = FastAPI()
    app.include_router(ariadne_webhooks.router)
    return TestClient(app)


def test_empty_list(client):
    r = client.get("/api/ariadne/webhooks")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "webhooks": []}


def test_create_and_list(client):
    r = client.post("/api/ariadne/webhooks", json={"url": "https://example.com/hook", "events": ["plan.completed"]})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True

    r = client.get("/api/ariadne/webhooks")
    assert len(r.json()["webhooks"]) == 1
    assert r.json()["webhooks"][0]["url"] == "https://example.com/hook"


def test_duplicate_rejected(client):
    client.post("/api/ariadne/webhooks", json={"url": "https://example.com/hook"})
    r = client.post("/api/ariadne/webhooks", json={"url": "https://example.com/hook"})
    assert r.status_code == 409


def test_non_http_url_rejected(client):
    r = client.post("/api/ariadne/webhooks", json={"url": "file:///etc/passwd"})
    assert r.status_code == 400


def test_delete(client):
    client.post("/api/ariadne/webhooks", json={"url": "https://example.com/hook"})
    r = client.delete("/api/ariadne/webhooks/0")
    assert r.status_code == 200
    r = client.delete("/api/ariadne/webhooks/0")
    assert r.status_code == 404
