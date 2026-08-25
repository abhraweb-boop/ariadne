"""FloEngine -- swarm orchestration via vendored ruflo (Phase 13).

Adapter seam (same discipline as PrimeEngine): ALL protocol specifics in
this file. ruflo runs from the vendored tree; `flo` DAG nodes delegate
here. Scope wall: ruflo coordinates agents UNDER a plan node -- it never
replaces our executor.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Optional

_HERMES_CORE = Path(__file__).resolve().parents[1]


def cli_path() -> Path:
    return _HERMES_CORE / "vendor" / "ruflo" / "bin" / "cli.js"


def status() -> Dict[str, Any]:
    """Console-friendly roll-up: vendored? node? runnable?"""
    p = cli_path()
    vendored = p.exists()
    node = shutil.which("node")
    if not vendored:
        state, hint = "missing", f"vendored CLI not found at {p}"
    elif not node:
        state, hint = "no_node", ("node not on PATH — ruflo needs "
                                  "Node >= 20")
    else:
        try:
            out = subprocess.run(
                ["node", str(p), "--version"], capture_output=True,
                text=True, timeout=30)
            if out.returncode == 0:
                return {"ok": True, "state": "ok",
                        "version": out.stdout.strip().split()[-1]
                        if out.stdout else "?",
                        "cli": str(p)}
            state, hint = "error", out.stderr.strip()[:200] or "cli failed"
        except Exception as exc:
            state, hint = "error", f"{type(exc).__name__}: {exc}"[:200]
    return {"ok": False, "state": state, "hint": hint, "cli": str(p)}


class FloEngine:
    """One-shot swarm task runner over `node vendor/ruflo/bin/cli.js`.

    v1 executes `ruflo <objective> --output json` style invocations in a
    build directory and captures stdout as the artifact. Long-lived swarm
    sessions land with the Flow tab work; this seam is the only place
    that changes when they do.
    """

    def __init__(self, *, cwd: Optional[Path] = None) -> None:
        self.cwd = Path(cwd or os.environ.get("HERMES_BUILD_DIR")
                        or _HERMES_CORE)

    def run_swarm(self, objective: str, *, timeout_s: float = 600.0,
                  extra_args: Optional[list] = None) -> Dict[str, Any]:
        st = status()
        if st["state"] != "ok":
            return {"ok": False, "error": st["state"], "hint": st["hint"]}
        argv = ["node", str(cli_path()), objective] + (extra_args or [])
        try:
            proc = subprocess.run(
                argv, cwd=str(self.cwd), capture_output=True, text=True,
                timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout",
                    "hint": f"flo swarm exceeded {timeout_s}s"}
        ok = proc.returncode == 0
        return {
            "ok": ok,
            "stdout": proc.stdout[-16_000:],
            "stderr": proc.stderr[-4_000:] if not ok else "",
            "returncode": proc.returncode,
        }


__all__ = ["FloEngine", "status", "cli_path"]
