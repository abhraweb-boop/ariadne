"""Ariadne context-graph REST routes for the desktop/web dashboard.

Read-mostly surface over plugins/context_graph/store.py:
    GET  /api/ariadne/graph/stats
    GET  /api/ariadne/graph/related?query=&depth=&limit=
    GET  /api/ariadne/graph/timeline?node=
    GET  /api/ariadne/graph/export?limit=
    POST /api/ariadne/graph/prune        {older_than_days}
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ariadne/graph", tags=["ariadne-graph"])


def _store():
    os.environ.setdefault(
        "HERMES_HOME", os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    )
    from plugins.context_graph import get_store

    return get_store()


@router.get("/stats")
def graph_stats() -> Dict[str, Any]:
    try:
        return {"ok": True, **_store().stats()}
    except Exception as exc:  # pragma: no cover
        logger.exception("graph stats failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/related")
def graph_related(
    query: str = Query("", description="Keyword seed(s)"),
    node: str = Query("", description="Explicit node id seed"),
    depth: int = Query(2, ge=1, le=5),
    limit: int = Query(20, ge=1, le=200),
) -> Dict[str, Any]:
    try:
        store = _store()
        seeds = [node] if node else store.seeds_by_keyword(query, limit=5)
        sg = store.subgraph(seeds, depth=depth, limit=limit)
        return {"ok": True, "seeds": seeds, **sg}
    except Exception as exc:  # pragma: no cover
        logger.exception("graph related failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/timeline")
def graph_timeline(
    node: str = Query(..., description="Node id"),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    try:
        events = _store().timeline(node, limit=limit)
        return {"ok": True, "node": node, "events": events}
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/export")
def graph_export(limit: int = Query(200, ge=1, le=2000)) -> Dict[str, Any]:
    try:
        return {"ok": True, **_store().export(limit=limit)}
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/prune")
def graph_prune(payload: Dict[str, Any]) -> Dict[str, Any]:
    days = float(payload.get("older_than_days", 30))
    try:
        res = _store().prune(older_than_days=days)
        return {"ok": True, **res}
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
