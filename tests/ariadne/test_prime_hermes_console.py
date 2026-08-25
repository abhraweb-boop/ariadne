"""Prime Hermes Console router tests (engine mocked, no node spawn)."""

from __future__ import annotations

import asyncio
import json

import pytest


class FakeEngine:
    def __init__(self):
        self.pid = 4321
        self.prompts = []

    def state(self, timeout_s=None):
        return {"success": True,
                "data": {"model": {"id": "stealth/ox-alpha",
                                   "provider": "openrouter"},
                         "session": "s-0"}}

    def prompt(self, text, timeout_s=None, **kw):
        self.prompts.append(text)
        if text == "boom":
            return {"ok": False, "text": "", "events": [],
                    "raw": {"success": False, "error": "no_key"}}
        return {"ok": True, "text": f"echo: {text}", "events": [1],
                "raw": {"success": True}}

    def steer(self, text, timeout_s=None):
        return {"success": True}

    def new_session(self, timeout_s=None):
        return {"success": True}


@pytest.fixture()
def api(monkeypatch):
    import ariadne.prime_engine as pe
    from hermes_cli.web_routers import prime_hermes_console as pc

    fake = FakeEngine()
    monkeypatch.setattr(pe, "_engine", None, raising=True)
    monkeypatch.setattr(pc, "_engine", lambda: fake, raising=True)
    yield pc, fake
    monkeypatch.setattr(pe, "_engine", None, raising=True)


def test_status_live(api):
    pc, _ = api
    out = pc.console_status()
    assert out["product"] == "Prime Hermes"
    assert out["engine_running"] is True
    assert out["tier"] == "governed"
    assert out["model"] == "stealth/ox-alpha"
    assert out["provider"] == "openrouter"


def test_status_engine_down_is_structured(api, monkeypatch):
    pc, _ = api

    def boom():
        raise RuntimeError("prime bundle missing — run scripts/build-prime.sh")

    monkeypatch.setattr(pc, "_engine", boom)
    out = pc.console_status()
    assert out["engine_running"] is False
    assert "build-prime.sh" in out["reason"]


def test_prompt_roundtrip(api):
    pc, fake = api
    out = asyncio.run(pc.console_prompt({"text": "hello"}))
    assert out["ok"] is True
    assert out["text"] == "echo: hello"
    assert fake.prompts == ["hello"]


def test_prompt_requires_text(api):
    pc, _ = api
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        asyncio.run(pc.console_prompt({"text": ""}))
    assert ei.value.status_code == 422


def test_steer_and_new_session(api):
    pc, _ = api
    assert pc.console_steer({"text": "go left"})["ok"] is True
    assert pc.console_new_session()["ok"] is True


def test_exec_endpoint_runs_plan(monkeypatch, tmp_path):
    from ariadne_runtime.graph_exec import GraphExecutor
    from plugins.context_graph.tasks import TaskStore
    from hermes_cli.web_routers import prime_hermes_console as pc
    from plugins.context_graph import plan_tool as pt

    tstore = TaskStore(tmp_path / "t.db")
    pid = tstore.create_plan("console exec", [
        {"id": "a", "kind": "note"},
        {"id": "b", "kind": "note", "depends_on": ["a"]},
    ])

    monkeypatch.setattr(pt, "_get_store", lambda: tstore)
    out = pc.console_exec(pid, {})
    assert out["ok"] is True
    assert out["summary"]["final_state"] == "done"
    tstore.close()


def test_page_contains_branding(api):
    pc, _ = api
    html = pc.console_page().body.decode("utf-8")
    assert "PRIME HERMES" in html
    assert "/api/prime-hermes/console" in html
