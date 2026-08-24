"""Kernel-side bridge: rlm() callable + ZeroMQ REQ/PUSH-PULL transport.

Design notes (mirrors Prime Agent's rlm-runtime, adapted to plain ZMQ):
- Admission requests go out on a DEALER socket; admission-only handles come
  back on the same socket (host replies between request and reply frames).
- The Jupyter *shell* channel is never used for host round-trips, so an
  awaiting cell cannot deadlock the serially-executing kernel shell thread.
- Handles carry identity only -- never the child's answer.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import zmq
    import zmq.asyncio
except ImportError as _exc:  # pragma: no cover
    zmq = None  # type: ignore[assignment]
    _zmq_import_error = _exc


@dataclass(frozen=True)
class RLMSpawnHandle:
    """Admission-only handle. Never contains the child's answer."""

    rlm_child_id: str
    name: str
    session_dir: Optional[str] = None
    model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rlm_child_id": self.rlm_child_id,
            "name": self.name,
            "session_dir": self.session_dir,
            "model": self.model,
        }


class RLMError(RuntimeError):
    pass


class _Bridge:
    """One bridge per kernel process. Thread-safe; async-friendly."""

    def __init__(self, endpoint: str) -> None:
        if zmq is None:
            raise RLMError(
                "pyzmq is not installed in the kernel environment. "
                "Rebuild the Ariadne kernel env (it must include pyzmq)."
            )
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.DEALER)
        self._sock.setsockopt(zmq.IDENTITY, f"ariadne-kernel-{uuid.uuid4().hex[:8]}".encode())
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.setsockopt(zmq.RCVTIMEO, 30_000)
        self._sock.connect(endpoint)
        self._lock = threading.Lock()

    # ── low-level request/reply over the DEALER ──────────────────────────
    def request(self, req_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        msg_id = uuid.uuid4().hex
        frame = json.dumps(
            {"id": msg_id, "type": req_type, "payload": payload}
        ).encode("utf-8")
        with self._lock:
            self._sock.send(frame)
            while True:
                raw = self._sock.recv()
                try:
                    reply = json.loads(raw.decode("utf-8"))
                except Exception as exc:
                    raise RLMError(f"Malformed host reply: {exc}") from exc
                if reply.get("id") == msg_id or reply.get("type") == "reply":
                    break
            # Non-matching frames (e.g. late events) are dropped.
        if not reply.get("ok", False):
            raise RLMError(str(reply.get("error") or "host request failed"))
        return reply.get("result") or {}

    def close(self) -> None:
        try:
            self._sock.close(0)
        except Exception:
            pass


_bridge: Optional[_Bridge] = None


def init_bridge(endpoint: str) -> None:
    """Idempotent: re-init when the endpoint changes (e.g. kernel restart)."""
    global _bridge
    if _bridge is not None:
        try:
            cur = _bridge._sock.getsockopt(zmq.LAST_ENDPOINT)
        except Exception:
            cur = None
        if cur and endpoint.encode() in bytes(cur):
            return
        _bridge.close()
    _bridge = _Bridge(endpoint)


def _get_bridge() -> _Bridge:
    if _bridge is None:
        ep = os.environ.get("ARIADNE_HOST_ENDPOINT")
        if not ep:
            raise RLMError(
                "rlm bridge not initialized (no ARIADNE_HOST_ENDPOINT). "
                "Use the ariadne_kernel tool to run cells."
            )
        init_bridge(ep)
    return _bridge


class rlm:  # noqa: N801 - Prime-compatible lowercase callable namespace
    """Callable + namespace: ``await rlm("goal")`` == ``await rlm.run("goal")``."""

    def __init__(self, prompt: str = "", **kwargs: Any) -> None:
        if not prompt:
            raise RLMError("rlm(prompt, name=...) requires a non-empty prompt")
        self.prompt = prompt
        self.kwargs = kwargs

    def __await__(self):
        return self.run(self.prompt, **self.kwargs).__await__()

    @staticmethod
    async def run(
        prompt: str,
        *,
        name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> RLMSpawnHandle:
        if not prompt or not prompt.strip():
            raise RLMError("prompt must be a non-empty string")
        result = await _async_request(
            "rlm.run",
            {
                "prompt": prompt.strip(),
                "name": name,
                "model": model,
            },
        )
        return RLMSpawnHandle(
            rlm_child_id=str(result.get("rlm_child_id") or ""),
            name=str(result.get("name") or ""),
            session_dir=result.get("session_dir"),
            model=result.get("model"),
        )

    @staticmethod
    async def list_subagents() -> list:
        result = await _async_request("rlm.list", {})
        return list(result.get("children") or [])

    @staticmethod
    async def host_request(request_type: str, payload: Optional[dict] = None) -> dict:
        return await _async_request(request_type, payload or {})


async def _async_request(req_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run the blocking ZMQ round-trip off the kernel's shell thread."""
    import asyncio

    bridge = _get_bridge()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: bridge.request(req_type, payload))


# agent_message shim: Phase-1 children report via files/normal completion;
# the send side is a thin alias so Prime-style code paths still import.
class agent_message:
    @staticmethod
    async def send(message: str, *, receiver_role: str = "parent", receiver_name=None):
        return await _async_request(
            "agent_message.send",
            {"message": message, "receiver_role": receiver_role,
             "receiver_name": receiver_name},
        )
