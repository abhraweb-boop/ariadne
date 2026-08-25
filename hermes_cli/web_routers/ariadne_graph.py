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
from fastapi.responses import HTMLResponse

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


# ── Phase 8: Runs API (Flow-view data source) ─────────────────────────────
def _tasks_store():
    os.environ.setdefault(
        "HERMES_HOME", os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    )
    from plugins.context_graph.plan_tool import _get_store

    return _get_store()


@router.get("/runs/{plan_id}")
def run_detail(plan_id: str) -> Dict[str, Any]:
    """Poll-friendly plan state for the Flow tab."""
    try:
        store = _tasks_store()
        p = store.plan(plan_id)
        if p is None:
            raise HTTPException(status_code=404,
                                detail=f"unknown plan {plan_id}")
        tasks = [{
            "id": t["id"],
            "kind": t["kind"],
            "title": t["title"],
            "state": t["state"],
            "attempts": t["attempts"],
            "depends_on": json.loads(t.get("depends_on") or "[]"),
            "error": (t.get("error") or "")[:300] or None,
        } for t in p["tasks"]]
        counts: Dict[str, int] = {}
        for t in tasks:
            counts[t["state"]] = counts.get(t["state"], 0) + 1
        return {
            "ok": True,
            "plan": {"id": p["id"], "goal": p["goal"], "state": p["state"]},
            "tasks": tasks,
            "counts": counts,
        }
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("run detail failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runs")
def runs_list(limit: int = Query(10, ge=1, le=50)) -> Dict[str, Any]:
    """Recent plans for the Flow picker."""
    try:
        plans = _tasks_store().list_plans(limit=limit)
        return {"ok": True, "plans": [
            {"id": p["id"], "goal": p["goal"], "state": p["state"],
             "n_tasks": p.get("n_tasks"), "n_done": p.get("n_done")}
            for p in plans]}
    except Exception as exc:  # pragma: no cover
        logger.exception("runs list failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Phase 8-D: the Flow tab (live plan visualization) ─────────────────────
_FLOW_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Prime Hermes — Flow</title>
<style>
  :root {
    --bg:#0b0e14; --fg:#d6deeb; --dim:#5f6b7d; --accent:#7aa2f7;
    --ok:#9ece6a; --warn:#e0af68; --err:#f7768e; --line:#1e2430;
    --run:#bb9af7;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--fg);
    font:14px/1.5 "Cascadia Code",Consolas,monospace; padding:16px; }
  header { display:flex; gap:12px; align-items:center; margin-bottom:14px; }
  header b { color:var(--accent); }
  select { background:#11151f; color:var(--fg); border:1px solid var(--line);
    padding:4px 8px; border-radius:4px; font:inherit; }
  #meta { color:var(--dim); font-size:12px; margin-bottom:10px; min-height:18px; }
  .lane { display:flex; flex-direction:column; gap:0; position:relative; }
  .node {
    display:flex; align-items:center; gap:10px;
    border:1px solid var(--line); border-left:4px solid var(--dim);
    border-radius:6px; padding:9px 12px; margin:0 0 14px 0;
    background:#10141d; max-width:720px; transition:border-color .3s;
  }
  .node.done   { border-left-color:var(--ok); }
  .node.running{ border-left-color:var(--run); animation:pulse 1.1s infinite; }
  .node.failed { border-left-color:var(--err); }
  .node.bypassed{ border-left-color:var(--warn); opacity:.75; }
  .node.skipped{ opacity:.45; }
  @keyframes pulse { 50% { opacity:.55; } }
  .dot { width:9px; height:9px; border-radius:50%; background:var(--dim);
    flex:none; }
  .node.done .dot { background:var(--ok); }
  .node.running .dot { background:var(--run); }
  .node.failed .dot { background:var(--err); }
  .node.bypassed .dot { background:var(--warn); }
  .kind { color:var(--dim); font-size:11px; border:1px solid var(--line);
    padding:0 5px; border-radius:3px; flex:none; }
  .title { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .state { font-size:11px; flex:none; }
  .node.done .state { color:var(--ok); }
  .node.running .state { color:var(--run); }
  .node.failed .state { color:var(--err); }
  .node.bypassed .state { color:var(--warn); }
  .error { color:var(--err); font-size:12px; margin:-10px 0 12px 22px;
    max-width:700px; white-space:pre-wrap; }
  .arrow { color:var(--dim); margin:-9px 0 -5px 24px; font-size:11px; }
  footer { margin-top:18px; color:var(--dim); font-size:12px; }
</style>
</head>
<body>
<header>
  <b>PRIME HERMES · FLOW</b>
  <select id="picker"><option>loading runs…</option></select>
  <span id="plan-state" class="kind"></span>
</header>
<div id="meta"></div>
<div id="flow" class="lane"></div>
<footer>polling every 2s · green=done · purple pulse=running · red=failed
· amber=bypassed (gate) · grey=skipped</footer>
<script>
const flow = document.getElementById("flow");
const picker = document.getElementById("picker");
const meta = document.getElementById("meta");
const stateEl = document.getElementById("plan-state");
let current = null;

async function jget(u){ const r = await fetch(u); return r.json(); }

async function loadPicker(){
  const d = await jget(location.origin + "/api/ariadne/graph/runs?limit=25");
  if (!d.ok) return;
  picker.innerHTML = "";
  for (const p of d.plans){
    const o = document.createElement("option");
    o.value = p.id;
    o.textContent = p.goal + " (" + p.state + ")";
    picker.appendChild(o);
  }
  if (!current && d.plans.length) current = d.plans[0].id;
  if (current) picker.value = current;
}

function render(d){
  if (!d.ok){ meta.textContent = "run not found"; flow.innerHTML = ""; return; }
  stateEl.textContent = d.plan.state;
  meta.textContent = d.plan.goal + " — " +
    Object.entries(d.counts).map(([k,v])=>v+" "+k).join(" · ");
  flow.innerHTML = "";
  for (const t of d.tasks){
    const n = document.createElement("div");
    n.className = "node " + t.state;
    n.innerHTML = '<span class="dot"></span>' +
      '<span class="kind">' + t.kind + '</span>' +
      '<span class="title"></span>' +
      '<span class="state">' + t.state +
      (t.attempts>1 ? ' ×'+t.attempts : '') + '</span>';
    n.querySelector(".title").textContent = t.title || t.id;
    flow.appendChild(n);
    if ((t.depends_on||[]).length && t !== d.tasks[d.tasks.length-1]){
      const a = document.createElement("div");
      a.className = "arrow"; a.textContent = "↓";
      flow.appendChild(a);
    }
    if (t.error){
      const e = document.createElement("div");
      e.className = "error";
      e.textContent = "⚠ " + t.error;
      flow.appendChild(e);
    }
  }
}

async function tick(){
  try {
    if (!current || !picker.options.length) await loadPicker();
    if (!current) { meta.textContent = "no runs yet — execute a plan first"; return; }
    const d = await jget("/api/ariadne/graph/runs/" + current);
    render(d);
  } catch(e){ /* transient */ }
}
picker.addEventListener("change", () => { current = picker.value; tick(); });
tick(); setInterval(tick, 2000); setInterval(loadPicker, 15000);
</script>
</body>
</html>
"""


@router.get("/flow", response_class=HTMLResponse, include_in_schema=False)
def flow_page() -> HTMLResponse:
    """Live Flow view over /runs data (P8-D)."""
    return HTMLResponse(_FLOW_HTML)


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
