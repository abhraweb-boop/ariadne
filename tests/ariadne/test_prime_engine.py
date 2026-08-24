"""PrimeEngine RPC tests against a fake subprocess (no network, no node)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

FAKE = Path(__file__).parent / "fake_prime_rpc.py"


def make_engine(**kw):
    from ariadne.prime_engine import PrimeEngine

    return PrimeEngine(command=[sys.executable, str(FAKE)], **kw)


@pytest.fixture()
def engine():
    e = make_engine()
    e.start()
    yield e
    e.stop()


def test_start_and_state_handshake(engine):
    st = engine.state(timeout_s=5)
    assert st["success"] is True
    assert st["data"]["model"] == "fake-model"


def test_prompt_returns_final_text(engine):
    out = engine.prompt("hello", timeout_s=5)
    assert out["ok"] is True
    assert out["text"] == "fake answer"
    assert out["events"], "streaming events should be captured"


def test_steer_roundtrip(engine):
    res = engine.steer("change approach", timeout_s=5)
    assert res["success"] is True


def test_new_session(engine):
    res = engine.new_session(timeout_s=5)
    assert res["data"]["cancelled"] is False


def test_crlf_tolerated(engine):
    # engine must accept responses terminated \r\n as well as \n
    out = engine.prompt("\r\n padded", timeout_s=5)
    assert out["ok"] is True


def test_stop_kills_process():
    e = make_engine()
    e.start()
    pid = e.pid
    assert pid is not None
    e.stop()
    if os.name == "nt":
        probe = __import__("subprocess").run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True)
        assert str(pid) not in probe.stdout
    else:
        assert e._proc.poll() is not None


def test_prompt_without_start_raises():
    e = make_engine()
    with pytest.raises(RuntimeError, match="not started"):
        e.prompt("hi")


def test_request_timeout_surfaces():
    e = make_engine(request_timeout_s=0.05)
    e.start()
    with pytest.raises(TimeoutError):
        e._request("sleep", {"s": 0.5}, timeout_s=0.05)
    e.stop()
