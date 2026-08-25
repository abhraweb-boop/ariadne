"""Prime Hermes Console — REST surface over the prime engine + plans.

    GET  /api/prime-hermes/console/status   engine + tier + plan roll-up
    POST /api/prime-hermes/console/prompt   {"text", "timeout_s"?}
    POST /api/prime-hermes/console/steer    {"text"}
    POST /api/prime-hermes/console/new_session
    GET  /api/prime-hermes/console/plans    recent plans
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prime-hermes/console",
                   tags=["prime-hermes-console"])


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def console_page() -> HTMLResponse:
    """The Prime Hermes Console — standalone text surface (no Electron)."""
    return HTMLResponse(_CONSOLE_HTML)


def _engine():
    from ariadne.prime_engine import get_engine

    return get_engine()


def _engine_error(exc: Exception) -> str:
    msg = str(exc)
    if "disabled by config" in msg:
        return ("Prime engine is disabled "
                "(ariadne.prime.enabled=false in config.yaml).")
    if "bundle missing" in msg or "No such file" in msg:
        return "Prime bundle not built. Run scripts/build-prime.sh."
    return f"{type(exc).__name__}: {msg}"


@router.get("/status")
def console_status() -> Dict[str, Any]:
    import ariadne_runtime.policy as policy

    out: Dict[str, Any] = {
        "product": "Prime Hermes",
        "tier": policy.active()["name"],
        "engine_running": False,
    }
    try:
        eng = _engine()
    except RuntimeError as exc:
        out["reason"] = _engine_error(exc)
        try:
            from ariadne_runtime.graph_exec import close_engine

            close_engine()
        except Exception:
            pass
        return out
    try:
        st = eng.state(timeout_s=15)
        data = st.get("data") or {}
        model = data.get("model")
        out.update({
            "engine_running": True,
            "pid": eng.pid,
            "model": (model.get("id") if isinstance(model, dict)
                      else str(model)) if model else None,
            "provider": (model.get("provider") if isinstance(model, dict)
                         else None),
        })
    except Exception as exc:
        out["reason"] = f"{type(exc).__name__}: {exc}"
    try:
        from plugins.context_graph.plan_tool import _get_store

        plans = _get_store().list_plans(limit=1)
        if plans:
            p = plans[0]
            out["last_plan"] = {
                "id": p["id"], "goal": p["goal"], "state": p["state"],
                "n_tasks": p.get("n_tasks"), "n_done": p.get("n_done"),
            }
        else:
            out["last_plan"] = None
    except Exception:
        out["last_plan"] = None
    # P13/P14 surfaces: google + flo status, budget governor state
    try:
        from ariadne_runtime import google_provider as gp

        out["google"] = gp.status()
    except Exception as exc:  # pragma: no cover
        out["google"] = {"ok": False, "state": "error", "hint": str(exc)[:120]}
    try:
        from ariadne_runtime import flo_engine as fe

        out["flo"] = fe.status()
    except Exception as exc:  # pragma: no cover
        out["flo"] = {"ok": False, "state": "error", "hint": str(exc)[:120]}
    try:
        from ariadne_runtime.doctor import get_budget

        g = get_budget().gate()
        out["budget"] = {**g,
                         "configured": getattr(get_budget(), "cap", 5.0)
                         != 5.0}
    except Exception:
        out["budget"] = {"configured": False}
    return out


@router.post("/prompt")
async def console_prompt(body: Dict[str, Any]) -> Dict[str, Any]:
    text = str((body or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text required")
    try:
        timeout_s = float((body or {}).get("timeout_s") or 300)
    except (TypeError, ValueError):
        timeout_s = 300.0
    try:
        eng = _engine()
        out = eng.prompt(text, timeout_s=timeout_s)
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=(f"prime prompt timed out after {timeout_s}s; "
                    "the engine stays alive — steer or new_session"))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=_engine_error(exc))
    return {
        "ok": out.get("ok"),
        "text": out.get("text") or "",
        "n_events": len(out.get("events") or []),
        "error": (out.get("raw") or {}).get("error"),
    }


@router.post("/steer")
def console_steer(body: Dict[str, Any]) -> Dict[str, Any]:
    text = str((body or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="text required")
    try:
        eng = _engine()
        res = eng.steer(text, timeout_s=15)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=_engine_error(exc))
    return {"ok": bool(res.get("success"))}


@router.post("/new_session")
def console_new_session() -> Dict[str, Any]:
    try:
        eng = _engine()
        res = eng.new_session(timeout_s=15)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=_engine_error(exc))
    return {"ok": bool(res.get("success"))}


@router.get("/heals")
def console_heals(limit: int = 25) -> Dict[str, Any]:
    """Autonomous-heal journal: what the doctor fixed without asking."""
    from ariadne_runtime.doctor import get_heals

    return {"ok": True, "heals": get_heals(limit)}


@router.post("/exec/{plan_id}")
def console_exec(plan_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
    """Run a plan from the Console (P14-aware: tier + budget gate)."""
    try:
        from ariadne_runtime.doctor import get_budget

        gov = get_budget()
        gate = gov.gate()
        if not gate["allowed"]:
            return {"ok": False, "paused": True,
                    "reason": ("budget cap reached — raise the cap or "
                               "resume before running more")}
    except Exception:
        gov = None
    try:
        from plugins.context_graph.plan_tool import _get_store
        from ariadne_runtime.graph_exec import GraphExecutor

        store = _get_store()
        if store.plan(plan_id) is None:
            raise HTTPException(status_code=404,
                                detail=f"unknown plan {plan_id}")
        tier = (body or {}).get("tier") or None
        summary = GraphExecutor(store, plan_id, tier=tier).run(resume=True)
        try:
            import json as _json

            est = float((summary.pop("_est_cost_usd", None) or 0))
        except Exception:
            est = 0.0
        if gov is not None and est:
            rec = gov.record(est)
            summary["budget"] = rec
        return {"ok": bool(summary.get("ok")), "summary": summary}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── the Console surface ───────────────────────────────────────────────────
_CONSOLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Prime Hermes — Console</title>
<style>
  :root {
    --bg: #0b0e14; --fg: #d6deeb; --dim: #5f6b7d; --accent: #7aa2f7;
    --ok: #9ece6a; --warn: #e0af68; --err: #f7768e; --line: #1e2430;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body { height: 100%; }
  body {
    background: var(--bg); color: var(--fg);
    font: 14px/1.55 "Cascadia Code", "JetBrains Mono", Consolas, monospace;
    display: flex; flex-direction: column;
  }
  header {
    display: flex; gap: 14px; align-items: baseline;
    padding: 10px 16px; border-bottom: 1px solid var(--line);
    color: var(--dim); font-size: 12px;
  }
  header b { color: var(--accent); font-size: 13px; letter-spacing: .4px; }
  #scroller { flex: 1; overflow-y: auto; padding: 16px 16px 8px; }
  .line { white-space: pre-wrap; word-break: break-word; margin-bottom: 6px; }
  .you  { color: var(--accent); }
  .sys  { color: var(--dim); }
  .err  { color: var(--err); }
  .ok   { color: var(--ok); }
  form {
    display: flex; align-items: center; gap: 8px;
    border-top: 1px solid var(--line); padding: 10px 16px;
  }
  .prompt-mark { color: var(--accent); white-space: nowrap; }
  input {
    flex: 1; background: transparent; border: none; outline: none;
    color: var(--fg); font: inherit; caret-color: var(--accent);
  }
  .badge {
    border: 1px solid var(--line); border-radius: 3px;
    padding: 0 6px; font-size: 11px;
  }
  .busy { animation: pulse 1s infinite; }
  @keyframes pulse { 50% { opacity: .45; } }
</style>
</head>
<body>
<header>
  <b>PRIME HERMES</b>
  <span id="st-model" class="badge">…</span>
  <span id="st-tier" class="badge">tier: …</span>
  <span id="st-engine" class="badge">engine: …</span>
  <span id="st-google" class="badge" title="Gemini provider">g:…</span>
  <span id="st-flo" class="badge" title="ruflo swarm engine">flo:…</span>
  <span id="st-budget" class="badge" title="budget governor">$0/$5</span>
  <span style="margin-left:auto">/help for commands</span>
</header>
<div id="scroller"></div>
<form id="f" autocomplete="off">
  <span class="prompt-mark">prime-hermes ▌</span>
  <input id="inp" placeholder="Talk to the prime engine… (/help)">
</form>
<script>
const sc = document.getElementById("scroller");
const inp = document.getElementById("inp");
const API = location.origin + "/api/prime-hermes/console";

function line(text, cls) {
  const d = document.createElement("div");
  d.className = "line " + (cls || "");
  d.textContent = text;
  sc.appendChild(d);
  sc.scrollTop = sc.scrollHeight;
}
function busy(on) {
  document.querySelector(".prompt-mark").classList.toggle("busy", on);
  inp.disabled = on;
}

async function refreshStatus() {
  try {
    const r = await fetch(API + "/status");
    const s = await r.json();
    document.getElementById("st-tier").textContent = "tier: " + s.tier;
    if (s.engine_running) {
      document.getElementById("st-engine").textContent =
        "engine: live pid " + s.pid;
      document.getElementById("st-model").textContent =
        s.model || "(model?)";
    } else {
      document.getElementById("st-engine").textContent = "engine: down";
      document.getElementById("st-model").textContent = "—";
      line("[console] engine down: " + (s.reason || "unknown"), "err");
    }
    const gEl = document.getElementById("st-google");
    if (s.google && s.google.state) {
      gEl.textContent = "g:" + s.google.state;
      gEl.style.color = s.google.ok ? "var(--ok)"
        : (s.google.state === "no_key" ? "var(--warn)" : "var(--err)");
    }
    const fEl = document.getElementById("st-flo");
    if (s.flo && s.flo.state) {
      fEl.textContent = "flo:" + s.flo.state;
      fEl.style.color = s.flo.ok ? "var(--ok)" : "var(--dim)";
    }
    const bEl = document.getElementById("st-budget");
    if (s.budget && typeof s.budget.spent === "number") {
      bEl.textContent = "$" + s.budget.spent.toFixed(2) + "/" +
        s.budget.cap.toFixed(0);
      bEl.style.color = s.budget.paused ? "var(--err)"
        : (s.budget.spent >= s.budget.cap * 0.5 ? "var(--warn)"
           : "var(--dim)");
    }
  } catch (e) {
    line("[console] status failed: " + e, "err");
  }
}

async function sendPrompt(text) {
  busy(true);
  try {
    const r = await fetch(API + "/prompt", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({text})
    });
    const j = await r.json();
    if (r.ok && j.ok !== false) line(j.text || "(empty response)", "");
    else line("error: " + (j.detail || j.error || r.status), "err");
    refreshStatus();
  } catch (e) { line("network error: " + e, "err"); }
  finally { busy(false); }
}

async function act(path, body) {
  busy(true);
  try {
    const r = await fetch(API + path, {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body || {})
    });
    const j = await r.json();
    line(r.ok ? "[ok]" : ("error: " + (j.detail || r.status)),
         r.ok ? "ok" : "err");
    refreshStatus();
  } catch (e) { line("network error: " + e, "err"); }
  finally { busy(false); }
}

const HELP = [
  "/status        — refresh engine/model/tier badges",
  "/session       — start a new prime session",
  "/steer <text>  — steer a running prompt",
  "/heals         — what the doctor fixed autonomously",
  "/help          — this list",
  "anything else is sent to the prime engine as a prompt."
].join("\\n");

document.getElementById("f").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = inp.value.trim();
  if (!text || inp.disabled) return;
  inp.value = "";
  line("prime-hermes ▌ " + text, "you");
  if (text === "/help") return line(HELP, "sys");
  if (text === "/status") return refreshStatus();
  if (text === "/session") return act("/new_session");
  if (text === "/heals") {
    return fetch("heals").then(r => r.json()).then(d => {
      if (!d.heals.length) return line("no heals yet — nothing needed fixing", "sys");
      for (const h of d.heals)
        line(`[${h.at}] ${h.task || "-"} · ${h.note}` +
             (h.action ? ` → ${h.action}` : ""), "sys");
    }).catch(() => line("heals unavailable", "err"));
  }
  if (text.startsWith("/steer ")) {
    const msg = text.slice(7).trim();
    if (msg) return act("/steer", {text: msg});
    return line("/steer needs a message", "err");
  }
  await sendPrompt(text);
});

line("Prime Hermes console ready.", "ok");
refreshStatus();
setInterval(refreshStatus, 30000);
</script>
</body>
</html>
"""
