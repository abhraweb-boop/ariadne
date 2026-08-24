"""Ariadne persistent-kernel subsystem: real-process integration + contracts.

Runs a REAL ipykernel child over loopback ZMQ against an isolated HERMES_HOME.
No model/API access needed: rlm admission is exercised with the same fake
child builders the subagent-lifecycle contract tests use.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

HERMES_CORE = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def isolated_home(tmp_path_factory):
    home = tmp_path_factory.mktemp("hermes-home")
    old = os.environ.get("HERMES_HOME")
    os.environ["HERMES_HOME"] = str(home)
    yield home
    if old is None:
        os.environ.pop("HERMES_HOME", None)
    else:
        os.environ["HERMES_HOME"] = old


@pytest.fixture()
def service(isolated_home):
    # Fresh module state per test (singleton manager).
    import importlib

    import ariadne.service as svc

    importlib.reload(svc)
    try:
        yield svc
    finally:
        try:
            svc.shutdown_kernel(force=True)
        except Exception:
            pass


# ── kernel transport + persistence ────────────────────────────────────────
def test_state_survives_across_execute_calls(service):
    info = service.start_kernel()
    assert info.get("pid"), f"kernel failed to start: {info}"

    r1 = service.execute_cell("a = 41\nb = a + 1\nprint('set', b)", timeout_s=60)
    assert r1["status"] == "ok", r1
    assert any("set 42" in p.get("text", "") for p in r1["outputs"])

    # A separate call == a separate turn: namespace must persist.
    r2 = service.execute_cell("print('still', b); c = b * 2", timeout_s=60)
    assert r2["status"] == "ok", r2
    texts = "".join(p.get("text", "") for p in r2["outputs"])
    assert "still 42" in texts
    assert r2.get("idle_seen") is True


def test_cell_error_reports_traceback_and_kernel_survives(service):
    service.start_kernel()
    r = service.execute_cell("raise ValueError('boom-marker')", timeout_s=60)
    assert r["status"] == "error"
    assert r["error"] and "ValueError" in r["error"]["ename"]
    assert "boom-marker" in "\n".join(r["error"]["traceback"])
    # Kernel must remain usable after a cell exception.
    r2 = service.execute_cell("print('alive')", timeout_s=30)
    assert r2["status"] == "ok"


def test_timeout_returns_and_kernel_stays_alive(service):
    service.start_kernel()
    r = service.execute_cell("import time; time.sleep(8)", timeout_s=2.0)
    assert r["status"] == "timeout"
    assert r["timeout_seconds"] == 2.0
    # An interrupted-by-timeout cell may still be running; give it a beat,
    # then confirm the kernel accepts new work again once idle.
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        probe = service.execute_cell("print('ready again')", timeout_s=20)
        if probe["status"] == "ok":
            break
        time.sleep(0.5)
    assert probe["status"] == "ok"


def test_shutdown_removes_conn_file(service):
    from ariadne.service import _runtime_dirs

    service.start_kernel()
    runtime_dir, _ = _runtime_dirs()
    conn_files = list(Path(runtime_dir).glob("conn-*.json"))
    assert conn_files, "conn file should exist while running"
    service.shutdown_kernel()
    assert not list(Path(runtime_dir).glob("conn-*.json"))


# ── rlm bridge ────────────────────────────────────────────────────────────
def test_bridge_roundtrip_list_children_empty(service):
    service.start_kernel()
    r = service.execute_cell(
        "import asyncio\n"
        "from ariadne_runtime.bridge import rlm\n"
        "kids = await rlm.list_subagents()\n"
        "print('KIDS:', kids)\n",
        timeout_s=45,
    )
    assert r["status"] == "ok", r
    texts = "".join(p.get("text", "") for p in r["outputs"])
    assert "KIDS: []" in texts


def test_rlm_run_without_active_parent_fails_cleanly(service):
    service.start_kernel()
    r = service.execute_cell(
        "import asyncio\n"
        "try:\n"
        "    from ariadne_runtime.bridge import rlm\n"
        "    h = await rlm('subtask', name='x')\n"
        "    print('UNEXPECTED', h)\n"
        "except Exception as e:\n"
        "    print('ERR:', type(e).__name__)\n",
        timeout_s=45,
    )
    assert r["status"] == "ok", r
    texts = "".join(p.get("text", "") for p in r["outputs"])
    assert "UNEXPECTED" not in texts
    assert "RLMError" in texts


def test_spawn_handle_is_admission_only_shape():
    from ariadne_runtime.bridge import RLMSpawnHandle

    h = RLMSpawnHandle(rlm_child_id="sa-1", name="reviewer")
    d = h.to_dict()
    assert set(d) == {"rlm_child_id", "name", "session_dir", "model"}
    payload = json.dumps(d)  # must be plain JSON-serializable metadata
    assert "answer" not in payload


def test_host_admission_launches_real_record(service, monkeypatch):
    """rlm.run through the HOST handler admits a child via the public API."""
    from agent.subagent_lifecycle import bind_subagent_parent

    parent = SimpleNamespace(session_id="ariadne-test-parent")
    counter = iter(range(1000))

    class FakeChild:
        def __init__(self):
            self._subagent_id = f"sa-{next(counter)}"
            self._delegate_role = "leaf"
            self._delegate_depth = 1
            self.provider = "test"
            self.model = "test-model"

    def build(**_kwargs):
        return FakeChild()

    def run(_i, _goal, child, _parent):
        time.sleep(0.01)
        return {"status": "completed", "summary": "ok", "api_calls": 1}

    monkeypatch.setattr("tools.delegate_tool._build_child_agent", build)
    monkeypatch.setattr("tools.delegate_tool._run_single_child", run)

    with bind_subagent_parent(parent):
        result = service._handle_host_request(
            "rlm.run",
            {"prompt": "inspect the API", "name": "api-reviewer"},
        )
        # Children are scoped to their parent session (same rule as the
        # lifecycle contract tests); query status while still bound.
        status = service.kernel_status()
    assert result["name"] == "api-reviewer"
    assert result["rlm_child_id"].startswith("sa-")

    kids = [c for c in status["children"] if c["rlm_child_id"] == result["rlm_child_id"]]
    assert len(kids) == 1
    assert kids[0]["state"] in {"PENDING", "STARTING", "RUNNING", "SUCCEEDED"}


# ── core tool dispatch ────────────────────────────────────────────────────
def test_tool_rejects_unknown_action():
    from tools.ariadne_kernel_tool import handle_ariadne_kernel

    out = json.loads(handle_ariadne_kernel({"action": "teleport"}))
    assert out["ok"] is False
    assert "unknown action" in out["error"]
