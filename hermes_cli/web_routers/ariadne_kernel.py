"""Ariadne kernel + ledger REST endpoints.

Kernel:
    POST /api/ariadne/kernel/start    — start persistent kernel
    GET  /api/ariadne/kernel/status   — kernel status + cells
    POST /api/ariadne/kernel/execute  — run a cell
    POST /api/ariadne/kernel/stop     — shutdown kernel

Ledger:
    GET  /api/ariadne/ledger/entries  — list entries
    GET  /api/ariadne/ledger/{id}     — single entry + history
    POST /api/ariadne/ledger/{id}/rollback  — rollback to version
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ariadne", tags=["ariadne-kernel-ledger"])


# ── kernel endpoints ─────────────────────────────────────────────────────


def _svc():
    from ariadne import service as svc

    return svc


@router.post("/kernel/start")
def kernel_start() -> Dict[str, Any]:
    try:
        return _svc().start_kernel()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/kernel/status")
def kernel_status() -> Dict[str, Any]:
    try:
        return _svc().kernel_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/kernel/execute")
def kernel_execute(body: Dict[str, Any]) -> Dict[str, Any]:
    code = body.get("code", "")
    if not code:
        raise HTTPException(400, "code required")
    timeout_s = body.get("timeout_s", 120)
    try:
        return _svc().execute_cell(code, timeout_s=timeout_s)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/kernel/stop")
def kernel_stop() -> Dict[str, Any]:
    try:
        _svc().shutdown_kernel(force=True)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── ledger endpoints ─────────────────────────────────────────────────────


def _ledger() -> Any:
    from plugins.memory.ariadne.ledger import MemoryLedger

    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    db = home / "ariadne" / "memory.db"
    return MemoryLedger(db)


@router.get("/ledger/entries")
def ledger_entries() -> Dict[str, Any]:
    try:
        ledger = _ledger()
        entries = ledger.list()
        return {"ok": True, "entries": entries}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/ledger/{entry_id}")
def ledger_entry(entry_id: str) -> Dict[str, Any]:
    try:
        ledger = _ledger()
        entry = ledger.get(entry_id)
        if not entry:
            raise HTTPException(404, "entry not found")
        history = ledger.history(entry_id)
        return {"ok": True, "entry": entry, "history": history}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ledger/{entry_id}/rollback")
def ledger_rollback(entry_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    seq = body.get("version")
    try:
        ledger = _ledger()
        rolled = ledger.rollback_entry(entry_id, seq=seq)
        return {"ok": True, "entry": rolled}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))