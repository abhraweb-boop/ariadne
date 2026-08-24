"""ariadne_prime — direct tool over the vendored Prime engine (Phase 7).

Actions: run | status | new_session | steer
Teaching errors throughout: disabled/bundle-missing/no-key states return
structured, actionable messages instead of tracebacks.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

TOOL_NAME = "ariadne_prime"

SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["run", "status", "new_session", "steer"],
            "description": "What to do with the prime engine.",
        },
        "prompt": {"type": "string",
                   "description": "Task text for action=run."},
        "message": {"type": "string",
                    "description": "Steering text for action=steer."},
    },
    "required": ["action"],
}


def _engine_error(exc: Exception) -> str:
    msg = str(exc)
    if "disabled by config" in msg:
        return ("prime engine is disabled (ariadne.prime.enabled=false in "
                "config.yaml). Enable it to use this tool.")
    if "bundle missing" in msg or "No such file" in msg or "not found" in msg.lower():
        return ("prime bundle not built yet. Run scripts/build-prime.sh, "
                "then retry.")
    return f"{type(exc).__name__}: {msg}"


def _handle_run(args: Dict[str, Any]) -> str:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return json.dumps({"ok": False,
                           "error": "run requires a non-empty prompt"})
    from ariadne.prime_engine import get_engine

    try:
        engine = get_engine()
    except RuntimeError as exc:
        return json.dumps({"ok": False, "error": _engine_error(exc)})
    timeout_s = float(args.get("timeout_s") or 300)
    try:
        out = engine.prompt(prompt, timeout_s=timeout_s)
    except TimeoutError:
        return json.dumps({
            "ok": False,
            "error": f"prime prompt timed out after {timeout_s}s",
            "hint": ("the engine stays alive; retry with a smaller task "
                     "or raise timeout_s"),
        })
    except RuntimeError as exc:
        return json.dumps({"ok": False,
                           "error": f"prime rpc: {exc}"})
    if not out.get("ok"):
        raw = out.get("raw") or {}
        err = raw.get("error") or "prime run failed"
        return json.dumps({"ok": False, "error": str(err)[:2000],
                           "partial_text": (out.get("text") or "")[:4000]})
    return json.dumps({
        "ok": True,
        "text": (out.get("text") or "")[:16_000],
        "events": len(out.get("events") or []),
    })


def _handle_status(_args: Dict[str, Any]) -> str:
    try:
        from ariadne.prime_engine import get_engine

        engine = get_engine()
    except RuntimeError as exc:
        return json.dumps({"ok": True, "running": False,
                           "reason": _engine_error(exc)})
    st = engine.state(timeout_s=15)
    result = st.get("result") or {}
    return json.dumps({
        "ok": bool(st.get("success")),
        "running": True,
        "pid": engine.pid,
        **(result if isinstance(result, dict) else {}),
    })


def _handle_new_session(_args: Dict[str, Any]) -> str:
    from ariadne.prime_engine import get_engine

    engine = get_engine()
    res = engine.new_session(timeout_s=15)
    return json.dumps({"ok": bool(res.get("success")),
                       "result": res.get("result")})


def _handle_steer(args: Dict[str, Any]) -> str:
    message = str(args.get("message") or "").strip()
    if not message:
        return json.dumps({"ok": False, "error": "steer requires message"})
    from ariadne.prime_engine import get_engine

    engine = get_engine()
    res = engine.steer(message, timeout_s=15)
    return json.dumps({"ok": bool(res.get("success")),
                       "result": res.get("result")})


def handle_ariadne_prime(args: Dict[str, Any], **_kw) -> str:
    args = args or {}
    action = str(args.get("action") or "").strip().lower()
    handlers = {
        "run": _handle_run,
        "status": _handle_status,
        "new_session": _handle_new_session,
        "steer": _handle_steer,
    }
    fn = handlers.get(action)
    if fn is None:
        return json.dumps({
            "ok": False,
            "error": f"unknown action '{action}'. Use one of: {sorted(handlers)}",
        })
    try:
        return fn(args)
    except RuntimeError as exc:
        return json.dumps({"ok": False, "error": _engine_error(exc)})
    except Exception as exc:
        logger.exception("ariadne_prime %s failed", action)
        return json.dumps({"ok": False,
                           "error": f"{type(exc).__name__}: {exc}"})


from tools.registry import registry  # noqa: E402

registry.register(
    name=TOOL_NAME,
    toolset="ariadne",
    schema=SCHEMA,
    handler=lambda args, **kw: handle_ariadne_prime(args, **kw),
    check_fn=None,
    emoji="⚡",
    max_result_size_chars=100_000,
)

__all__ = ["handle_ariadne_prime"]
