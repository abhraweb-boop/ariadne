"""Ariadne event spine (S1) — one replayable event stream for the harness.

Every subsystem (plans, tasks, kernel, agents, prime worker, graph) pushes
events here with a monotonically increasing sequence id. The harness desktop
subscribes to a single SSE endpoint and replays from ``after_id`` on
reconnect, so no surface ever shows a stale state.

In-memory ring buffer (bounded) + condition-variable notification so the SSE
endpoint can hold the connection open and push new events as they arrive
(rather than snapshot-and-close, which forces the client into a poll loop).
"""

from __future__ import annotations

import itertools
import threading
import time
from typing import Any, Dict, List

_lock = threading.Lock()
_cond = threading.Condition(_lock)
_counter = itertools.count(1)
_buffer: List[Dict[str, Any]] = []
_MAX = 256


def emit(event_type: str, payload: Dict[str, Any]) -> str:
    """Record one event, notify waiters, return its id."""
    with _lock:
        seq = next(_counter)
        ev = {
            "id": f"{seq:012d}",
            "type": event_type,
            "payload": payload,
            "ts": time.time(),
        }
        _buffer.append(ev)
        if len(_buffer) > _MAX:
            del _buffer[: len(_buffer) - _MAX]
        _cond.notify_all()
        return ev["id"]


def events_after(after_id: str | None = None) -> List[Dict[str, Any]]:
    """Events strictly after ``after_id`` (None = all retained)."""
    with _lock:
        if after_id:
            try:
                seq = int(after_id)
            except ValueError:
                return list(_buffer)
            return [e for e in _buffer if int(e["id"]) > seq]
        return list(_buffer)


def wait_for_events(after_id: str, timeout_s: float) -> List[Dict[str, Any]]:
    """Block until new events arrive (or timeout), then return them.

    Returns [] on timeout so SSE generators can send a heartbeat frame and
    keep the connection alive.
    """
    with _lock:
        _cond.wait(timeout=timeout_s)
        try:
            seq = int(after_id)
        except ValueError:
            return list(_buffer)
        return [e for e in _buffer if int(e["id"]) > seq]
