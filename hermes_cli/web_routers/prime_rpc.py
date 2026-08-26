"""Prime Agent RPC proxy — one in-process PrimeBridge, events into the spine.

prime_bridge.py is a stdlib-only library that keeps a persistent
`prime-agent --mode rpc` subprocess. This router holds a single bridge
instance and a background poller that forwards its buffered events into the
unified ariadne event spine — so the harness renderer needs only ONE SSE
subscription (/api/ariadne/events) to see plan, task, and prime events.

Endpoints:
    POST /api/prime/spawn    — start the bridge (idempotent)
    GET  /api/prime/state    — current agent state
    POST /api/prime/prompt   — send a prompt (returns immediately; text streams via events)
    POST /api/prime/steer    — steer mid-stream
    POST /api/prime/stop     — stop the subprocess
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from hermes_cli.web_routers.ariadne_events import emit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prime", tags=["prime-rpc"])

# ── singleton bridge ─────────────────────────────────────────────────────

_BRIDGE = None
_POLLER: Optional[threading.Thread] = None
_LOCK = threading.Lock()
_STOP = threading.Event()


def _bridge():
    global _BRIDGE, _POLLER
    with _LOCK:
        if _BRIDGE is not None:
            return _BRIDGE
        scripts_dir = Path.home() / "AppData" / "Local" / "hermes" / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from prime_bridge import PrimeBridge

        _BRIDGE = PrimeBridge()
        _BRIDGE.start()
        _STOP.clear()
        _POLLER = threading.Thread(target=_poll_loop, daemon=True)
        _POLLER.start()
        emit("prime.spawned", {"pid": _BRIDGE.proc.pid if _BRIDGE.proc else None})
        return _BRIDGE


def _poll_loop() -> None:
    """Forward bridge events into the unified spine (S1)."""
    while not _STOP.is_set():
        try:
            bridge = _BRIDGE
            if bridge is not None:
                for ev in bridge.poll_events():
                    ev_type = str(ev.get("type", "prime.event"))
                    emit("prime." + ev_type, ev)
        except Exception:
            logger.exception("prime event poll failed")
        time.sleep(0.25)


# ── endpoints ────────────────────────────────────────────────────────────


@router.post("/spawn")
def spawn() -> Dict[str, Any]:
    try:
        b = _bridge()
        return {"ok": True, "pid": b.proc.pid if b.proc else None}
    except Exception as exc:
        logger.exception("prime spawn failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/state")
def get_state() -> Dict[str, Any]:
    try:
        b = _bridge()
        return {"ok": True, "state": b.get_state()}
    except Exception as exc:
        logger.exception("prime state failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/prompt")
def prompt(body: Dict[str, Any]) -> Dict[str, Any]:
    text = body.get("prompt", "")
    if not text:
        raise HTTPException(400, "prompt required")
    try:
        b = _bridge()
        rid = b.prompt(text, stream=False)
        return {"ok": True, "request_id": rid}
    except Exception as exc:
        logger.exception("prime prompt failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/steer")
def steer(body: Dict[str, Any]) -> Dict[str, Any]:
    msg = body.get("message", "")
    if not msg:
        raise HTTPException(400, "message required")
    try:
        b = _bridge()
        b.steer(msg)
        return {"ok": True}
    except Exception as exc:
        logger.exception("prime steer failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/stop")
def stop() -> Dict[str, Any]:
    global _BRIDGE, _POLLER
    with _LOCK:
        if _BRIDGE is not None:
            _STOP.set()
            try:
                _BRIDGE.stop()
            except Exception:
                logger.exception("prime stop error")
            _BRIDGE = None
            _POLLER = None
        emit("prime.stopped", {})
        return {"ok": True}
