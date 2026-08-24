"""Ariadne kernel service -- singleton lifecycle + host-request handlers.

Sits between the core tool (tools/ariadne_kernel_tool.py) and KernelManager.
Resolves/provisions the managed kernel environment (ipykernel + pyzmq +
ariadne_runtime), starts/stops the kernel, answers rlm.* host requests by
admitting children through the public SubagentLifecycleService.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_KERNEL_FEATURE = "ariadne.kernel"

_lock = threading.Lock()
_manager = None  # KernelManager | None
_children: Dict[str, Dict[str, Any]] = {}  # rlm_child_id -> handle record


# ── dependency / env resolution ──────────────────────────────────────────
def deps_available() -> bool:
    try:
        from tools.lazy_deps import is_available
        return bool(is_available(_KERNEL_FEATURE))
    except Exception:
        return False


def ensure_deps(*, prompt: bool = False) -> None:
    from tools.lazy_deps import ensure as lazy_ensure
    lazy_ensure(_KERNEL_FEATURE, prompt=prompt)


def resolve_kernel_python() -> str:
    """Interpreter for the kernel process: config override > current venv."""
    try:
        from hermes_cli.config import load_config
        override = ((load_config() or {}).get("ariadne") or {}).get("kernel", {}).get("python")
        if override:
            return str(override)
    except Exception:
        pass
    return sys.executable


def _runtime_dirs() -> tuple[Path, Path]:
    from hermes_cli.config import get_hermes_home
    home = Path(get_hermes_home())
    return home / "ariadne" / "runtime", home / "ariadne" / "sessions"


def _inject_runtime_on_syspath() -> None:
    """Make ariadne_runtime importable inside THIS venv's kernel child.

    The kernel child inherits sys.path via PYTHONPATH so it can import both
    ipykernel/pyzmq (installed with the ariadne extra) and ariadne_runtime
    (shipped inside the hermes checkout). PYTHONPATH must contain the
    PARENT of the ariadne_runtime package, not the package itself.
    """
    _, _sessions = _runtime_dirs()
    src = Path(__file__).resolve().parent.parent  # repo root (parent of ariadne_runtime/)
    if not (src / "ariadne_runtime" / "__init__.py").exists():
        try:
            import ariadne_runtime  # noqa: F401

            return  # installed wheel layout: already importable
        except ImportError:
            pass
    import os

    pypath = os.environ.get("PYTHONPATH", "")
    if str(src) not in pypath:
        os.environ["PYTHONPATH"] = f"{src}{os.pathsep}{pypath}" if pypath else str(src)


# ── host-request handling (rlm.*) ────────────────────────────────────────
def _handle_host_request(req_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Runs on the bridge thread. Must never touch the Jupyter shell channel."""
    if req_type == "rlm.run":
        return _admit_child(payload)
    if req_type == "rlm.list":
        with _lock:
            kids = [
                {k: rec.get(k) for k in ("rlm_child_id", "name", "state", "model")}
                for rec in _children.values()
            ]
        return {"children": kids}
    if req_type == "agent_message.send":
        # Phase-1: child->parent messaging rides Hermes' normal completion
        # delivery; explicit sends are recorded for the parent transcript.
        cid = str(payload.get("receiver_name") or "")
        logger.info("ariadne agent_message from %s: %s",
                    cid, str(payload.get("message"))[:200])
        return {"accepted": True}
    raise ValueError(f"unsupported host request type: {req_type}")


def _admit_child(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Admission-only spawn through Hermes' public subagent lifecycle API."""
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("rlm.run requires a non-empty prompt")

    from agent.subagent_lifecycle import (
        SubagentLaunchRequest,
        get_active_subagent_parent,
    )
    parent = get_active_subagent_parent()
    if parent is None:
        raise RuntimeError(
            "no active Hermes parent session; rlm() requires a running agent turn"
        )

    name = str(payload.get("name") or f"rlm-{uuid.uuid4().hex[:6]}").strip()
    model = payload.get("model") or None

    request = SubagentLaunchRequest(
        goal=prompt,
        context=None,
        role="leaf",
        model=model,
        metadata={"source": "ariadne.rlm"},
    )
    svc = _get_lifecycle_service()
    handle = svc.launch(request)

    rlm_child_id = handle.subagent_id
    _, sessions_dir = _runtime_dirs()
    record = {
        "rlm_child_id": rlm_child_id,
        "name": name,
        "session_dir": str(sessions_dir),
        "model": handle.model,
        "state": "RUNNING",
        "admitted_at": time.time(),
        "depth": handle.depth,
        "_handle": handle,  # original object: capability-HMAC stays valid
    }
    with _lock:
        _children[rlm_child_id] = record
    return {
        "rlm_child_id": rlm_child_id,
        "name": name,
        "session_dir": record["session_dir"],
        "model": handle.model,
    }


_svc_instance = None


def _get_lifecycle_service():
    global _svc_instance
    if _svc_instance is None:
        from agent.subagent_lifecycle import (
            SubagentLifecycleService,
            get_active_subagent_parent,
        )

        _svc_instance = SubagentLifecycleService(get_active_subagent_parent)
    return _svc_instance


def list_children_detailed() -> list:
    """Tool-side status view using the ORIGINAL handle objects (the registry
    rejects reconstructed handles -- capability HMAC exists precisely to stop
    forged handles)."""
    out = []
    svc = _get_lifecycle_service()
    with _lock:
        records = [
            (rec["rlm_child_id"], rec.get("_handle"))
            for rec in _children.values()
        ]
    for cid, handle in records:
        entry_base = {"rlm_child_id": cid}
        try:
            st = svc.status(handle)
            entry_base.update(
                {
                    "state": getattr(st.state, "value", str(st.state)),
                    "diagnostic": st.diagnostic,
                }
            )
        except Exception as exc:
            entry_base["status_error"] = str(exc)
            entry_base["state"] = "UNKNOWN"
        out.append(entry_base)
    return out


# ── public service API used by the tool ──────────────────────────────────
_atexit_registered = False


def _register_exit_cleanup() -> None:
    """Parent teardown must not orphan the kernel process (Prime parity)."""
    global _atexit_registered
    if _atexit_registered:
        return
    import atexit

    atexit.register(shutdown_kernel)
    _atexit_registered = True


def start_kernel() -> Dict[str, Any]:
    global _manager
    _inject_runtime_on_syspath()
    runtime_dir, _ = _runtime_dirs()
    from ariadne.kernel_manager import KernelManager
    _register_exit_cleanup()
    with _lock:
        if _manager is not None and _manager.is_running():
            return {"already_running": True, "host_endpoint": _manager.host_endpoint}
        if _manager is not None:
            _manager.shutdown(force=True)
        _manager = KernelManager(
            resolve_kernel_python(),
            runtime_dir=runtime_dir,
            host_request_handler=_handle_host_request,
        )
        info = _manager.start()
        info["host_endpoint"] = _manager.host_endpoint
        return info


def execute_cell(code: str, timeout_s: float) -> Dict[str, Any]:
    global _manager
    with _lock:
        mgr = _manager
    if mgr is None or not mgr.is_running():
        start_kernel()
        with _lock:
            mgr = _manager
    assert mgr is not None
    return mgr.execute(code, timeout_s=timeout_s)


def restart_kernel() -> Dict[str, Any]:
    global _manager
    with _lock:
        if _manager is None:
            return start_kernel()
        _manager.restart()
        return {"restarted": True}


def shutdown_kernel(*, force: bool = False) -> Dict[str, Any]:
    global _manager
    with _lock:
        if _manager is None:
            return {"was_running": False}
        _manager.shutdown(force=force)
        _manager = None
    return {"was_running": True}


def kernel_status() -> Dict[str, Any]:
    with _lock:
        mgr = _manager
    running = bool(mgr and mgr.is_running())
    return {
        "running": running,
        "pid": mgr._proc.pid if running else None,
        "uptime_s": (time.time() - mgr._started_at) if running and mgr._started_at else None,
        "host_endpoint": mgr.host_endpoint if running else None,
        "deps_available": deps_available(),
        "children": list_children_detailed(),
    }


__all__ = [
    "deps_available", "ensure_deps", "resolve_kernel_python",
    "start_kernel", "execute_cell", "restart_kernel", "shutdown_kernel",
    "kernel_status",
]
