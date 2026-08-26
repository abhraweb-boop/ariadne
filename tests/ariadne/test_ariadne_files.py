"""Files router tests — list/read/traversal guard, real tmp dir."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("HERMES_HOME", str(Path(__file__).parent / ".tmp-home"))

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermes_cli.web_routers import ariadne_files


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the router's cwd at a temp workspace
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alpha.txt").write_text("hello world", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.md").write_text("# inner", encoding="utf-8")

    app = FastAPI()
    app.include_router(ariadne_files.router)
    return TestClient(app)


def test_list_root(client):
    r = client.get("/api/ariadne/files/list")
    assert r.status_code == 200
    names = [e["name"] for e in r.json()["entries"]]
    assert "alpha.txt" in names
    assert "sub" in names


def test_list_nested(client):
    r = client.get("/api/ariadne/files/list", params={"path": "sub"})
    assert r.status_code == 200
    names = [e["name"] for e in r.json()["entries"]]
    assert names == ["inner.md"]


def test_read_file(client):
    r = client.get("/api/ariadne/files/read", params={"path": "alpha.txt"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["content"] == "hello world"
    assert body["truncated"] is False


def test_read_missing_file_404(client):
    r = client.get("/api/ariadne/files/read", params={"path": "nope.txt"})
    assert r.status_code == 404


def test_traversal_blocked(client):
    r = client.get("/api/ariadne/files/read", params={"path": "../secret.txt"})
    assert r.status_code == 400


def test_prefix_sibling_blocked(tmp_path, monkeypatch):
    """Prefix-sibling escape: workspace dir 'repo' must not allow 'repo-evil'."""
    (tmp_path / "repo").mkdir(exist_ok=True)
    (tmp_path / "repo-evil").mkdir(exist_ok=True)
    (tmp_path / "repo-evil" / "secret.txt").write_text("secret", encoding="utf-8")
    (tmp_path / "repo" / "ok.txt").write_text("ok", encoding="utf-8")
    monkeypatch.chdir(tmp_path / "repo")

    app = FastAPI()
    app.include_router(ariadne_files.router)
    c = TestClient(app)

    r = c.get("/api/ariadne/files/read", params={"path": "../repo-evil/secret.txt"})
    assert r.status_code == 400


def test_windows_style_backslash_blocked(client):
    """Backslash traversal (Windows separator) must be blocked too."""
    r = client.get("/api/ariadne/files/read", params={"path": "..\\..\\secret.txt"})
    assert r.status_code == 400
