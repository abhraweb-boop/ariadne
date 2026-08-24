#!/usr/bin/env python3
"""ariadne_kernel -- persistent IPython kernel + rlm() recursion (core tool).

One tool, action-dispatched, service-gated by check_fn (lazy-installed
'ariadne' extra). Actions:

    run      execute a Python cell; namespace persists across calls/turns
    rlm      admit a child Hermes agent from inside the kernel OR directly
             (admission-only handle; results arrive as normal agent messages)
    status   kernel + children status
    restart  restart the kernel (fresh namespace)
    shutdown stop the kernel process

Config (config.yaml):
    ariadne:
      kernel:
        enabled: true
        cell_timeout_s: 300
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

TOOL_NAME = "ariadne_kernel"

SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "Persistent IPython kernel: run Python cells whose variables, imports, "
        "and data structures SURVIVE across tool calls and conversation turns. "
        "Also admits recursive child agents from inside code via "
        "await rlm('goal', name='child') — admission-only handles; child "
        "answers arrive later as normal agent messages. Use for long research/"
        "coding work where rebuilding state each call would be wasteful."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["run", "rlm", "status", "restart", "shutdown"],
                "description": "Kernel operation to perform.",
            },
            "code": {
                "type": "string",
                "description": "For action=run: the Python cell to execute.",
            },
            "prompt": {
                "type": "string",
                "description": "For action=rlm: goal for the admitted child agent.",
            },
            "name": {
                "type": "string",
                "description": "For action=rlm: readable child session name.",
            },
            "model": {
                "type": "string",
                "description": "For action=rlm: exact 'provider/model' override; "
                "child inherits the parent model when omitted.",
            },
            "timeout_s": {
                "type": "number",
                "description": "For action=run: cell timeout in seconds "
                "(default 300).",
            },
        },
        "required": ["action"],
    },
}


def _cfg_kernel() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config
        return ((load_config() or {}).get("ariadne") or {}).get("kernel") or {}
    except Exception:
        return {}


def check_ariadne_requirements() -> bool:
    """Service gate: enabled in config AND lazy deps present."""
    if not _cfg_kernel().get("enabled", True):
        return False
    try:
        from tools.lazy_deps import is_available
        if is_available("ariadne.kernel"):
            return True
    except Exception:
        return False
    # Deps missing: still visible so first use can trigger the install path.
    try:
        from tools.lazy_deps import feature_missing
        return not feature_missing("ariadne.kernel")
    except Exception:
        return False


def _fmt(result: Dict[str, Any]) -> str:
    parts = []
    for piece in result.get("outputs") or []:
        t = piece.get("type")
        if t == "stream":
            parts.append(str(piece.get("text") or ""))
        elif t in ("execute_result", "display_data"):
            parts.append(f"[out] {piece.get('text', '')}")
        elif t == "error":
            tb = "\n".join(piece.get("traceback") or [])
            parts.append(f"[error] {piece.get('ename')}: {piece.get('evalue')}\n{tb}")
    body = "\n".join(parts).strip()
    if result.get("status") == "timeout":
        body += f"\n[cell TIMEOUT after {result.get('timeout_seconds')}s — kernel still alive]"
    return body or "(no output)"


def _handle_run(args: Dict[str, Any]) -> str:
    code = str(args.get("code") or "")
    if not code.strip():
        return json.dumps({"ok": False, "error": "run requires non-empty code"})
    timeout_s = float(args.get("timeout_s") or _cfg_kernel().get("cell_timeout_s", 300))
    from ariadne import service as svc
    result = svc.execute_cell(code, timeout_s=timeout_s)
    out = {
        "ok": result.get("status") == "ok",
        "status": result.get("status"),
        "output": _fmt(result),
    }
    return json.dumps(out)


def _handle_rlm(args: Dict[str, Any]) -> str:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        return json.dumps({"ok": False,
                           "error": "rlm requires a non-empty prompt"})
    from agent.subagent_lifecycle import get_active_subagent_parent
    if get_active_subagent_parent() is None:
        return json.dumps({
            "ok": False,
            "error": ("no active parent session bound; rlm admission must run "
                      "inside a live agent turn"),
        })
    # Direct-tool admission and in-kernel admission share one path.
    from ariadne import service as svc
    result = svc._handle_host_request(
        "rlm.run",
        {"prompt": prompt, "name": args.get("name"), "model": args.get("model")},
    )
    return json.dumps({
        "ok": True,
        "handle": result,
        "note": ("Admission only. The child's answer arrives as a normal "
                 "agent message when it finishes; continue your turn."),
    })


def _handle_status(_args: Dict[str, Any]) -> str:
    from ariadne import service as svc
    return json.dumps(svc.kernel_status())


def _handle_restart(_args: Dict[str, Any]) -> str:
    from ariadne import service as svc
    return json.dumps(svc.restart_kernel())


def _handle_shutdown(_args: Dict[str, Any]) -> str:
    from ariadne import service as svc
    return json.dumps(svc.shutdown_kernel())


def handle_ariadne_kernel(args: Dict[str, Any], **_kw) -> str:
    action = str((args or {}).get("action") or "").strip().lower()
    handlers = {
        "run": _handle_run,
        "rlm": _handle_rlm,
        "status": _handle_status,
        "restart": _handle_restart,
        "shutdown": _handle_shutdown,
    }
    fn = handlers.get(action)
    if fn is None:
        return json.dumps({
            "ok": False,
            "error": f"unknown action '{action}'. "
                     f"Use one of: {sorted(handlers)}",
        })
    try:
        return fn(args or {})
    except Exception as exc:
        logger.exception("ariadne_kernel %s failed", action)
        return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


from tools.registry import registry  # noqa: E402

registry.register(
    name=TOOL_NAME,
    toolset="ariadne",
    schema=SCHEMA,
    handler=lambda args, **kw: handle_ariadne_kernel(args, **kw),
    check_fn=check_ariadne_requirements,
    emoji="🧵",
    max_result_size_chars=100_000,
)

__all__ = ["handle_ariadne_kernel", "check_ariadne_requirements"]
