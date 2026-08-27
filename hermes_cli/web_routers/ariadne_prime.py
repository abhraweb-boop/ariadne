"""Ariadne prime RPC router — drive the Prime Agent bridge over HTTP.

Thin wrapper over the stdlib bridge at
``C:\\Users\\abhra\\AppData\\Local\\hermes\\scripts\\prime_bridge.py``
(``PrimeBridge``: start/prompt/steer/get_state/stop over ``prime-agent
--mode rpc``). The bridge import is guarded so the router can be imported
and tested without the bridge installed; endpoints return 503 with an
honest message when the bridge is unavailable.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ariadne/prime", tags=["ariadne-prime"])

_lock = threading.Lock()
_bridge = None  # Optional[PrimeBridge]


def _load_bridge():
    """Import and instantiate the bridge; returns None when unavailable."""
    global _bridge
    if _bridge is not None:
        return _bridge
    try:
        import os
        import sys

        # Resolve the Hermes scripts dir: env override, else the default
        # desktop install location.
        scripts_dir = os.environ.get(
            "PRIME_BRIDGE_SCRIPTS_DIR",
            r"C:\Users\abhra\AppData\Local\hermes\scripts",
        )
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from prime_bridge import PrimeBridge

        # The bridge respects PRIME_AGENT_CMD / PRIME_AGENT_PROVIDER /
        # PRIME_AGENT_MODEL env vars for the child process. If unset and
        # prime-agent is not on PATH, the bridge will fail to start.
        _bridge = PrimeBridge()
        return _bridge
    except Exception:
        return None


def _require_bridge():
    bridge = _load_bridge()
    if bridge is None:
        raise HTTPException(status_code=503, detail="prime bridge unavailable")
    return bridge


class PromptRequest(BaseModel):
    goal: str


class SteerRequest(BaseModel):
    message: str


@router.get("/state")
def prime_state() -> Dict[str, Any]:
    bridge = _load_bridge()
    if bridge is None:
        return {"ok": True, "running": False, "state": None}
    try:
        state = bridge.get_state()
        return {"ok": True, "running": state is not None, "state": state}
    except Exception:
        # Bridge not started yet — get_state() raises. Honest stopped state.
        return {"ok": True, "running": False, "state": None}


@router.post("/start")
def prime_start() -> Dict[str, Any]:
    bridge = _require_bridge()
    with _lock:
        try:
            bridge.start()
            state = bridge.get_state()
            return {"ok": True, "running": True, "state": state}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/prompt")
def prime_prompt(body: PromptRequest) -> Dict[str, Any]:
    if not body.goal.strip():
        raise HTTPException(status_code=400, detail="goal must not be empty")
    bridge = _require_bridge()
    with _lock:
        try:
            if bridge.get_state() is None:
                bridge.start()
            response = bridge.prompt(body.goal, stream=True)
            return {"ok": True, "response": response}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/steer")
def prime_steer(body: SteerRequest) -> Dict[str, Any]:
    bridge = _require_bridge()
    with _lock:
        try:
            bridge.steer(body.message)
            return {"ok": True}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/stop")
def prime_stop() -> Dict[str, Any]:
    bridge = _load_bridge()
    if bridge is None:
        return {"ok": True}
    with _lock:
        try:
            bridge.stop()
            return {"ok": True}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
