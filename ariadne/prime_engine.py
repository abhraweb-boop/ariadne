"""PrimeEngine -- drives vendored prime-agent over `--mode rpc` (JSONL).

Phase-7 seam. All protocol specifics live here (adapter contract): spawn,
framing (strict \\n out, trailing \\r tolerated in), request/response ids,
streaming events. Upstream drift ever touches exactly this file plus its
fixtures.

Auth: provider env vars pass through at spawn. A missing key is NEVER an
exception path — the engine surfaces structured no_key states from upstream
or its own pre-flight (`{"ok": false, "error": "no_key", ...}`).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_COMMAND = [
    "node",
    str(_REPO_ROOT / "vendor" / "prime-agent" / "packages" / "coding-agent"
        / "dist" / "bundle" / "cli.js"),
    "--mode", "rpc",
]


class PrimeEngine:
    """JSONL RPC session against one prime-agent subprocess."""

    def __init__(
        self,
        *,
        command: Optional[List[str]] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        cwd: Optional[str] = None,
        request_timeout_s: float = 180.0,
    ) -> None:
        self._command = list(command or _DEFAULT_COMMAND)
        self._model = model
        self._provider = provider
        self._cwd = cwd
        self._default_timeout = request_timeout_s
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self._pending: Dict[str, Dict[str, Any]] = {}  # id -> {"event": Event, "resp": ...}
        self._events: List[Dict[str, Any]] = []
        self._reader: Optional[threading.Thread] = None
        self._alive = False

    # ── lifecycle ──────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._alive:
            return
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=self._cwd,
        )
        self._alive = True
        self._reader = threading.Thread(
            target=self._read_loop, name="prime-rpc-reader", daemon=True)
        self._reader.start()

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    def stop(self) -> None:
        self._alive = False
        if self._proc is None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
        except Exception:
            pass
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            pass
        if os.name == "nt" and self._proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(self._proc.pid), "/T", "/F"],
                           capture_output=True)
        self._proc = None

    # ── requests ───────────────────────────────────────────────────────────
    def state(self, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        return self._request("get_state", {}, timeout_s)

    def new_session(self, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        return self._request("new_session", {}, timeout_s)

    def steer(self, text: str,
              timeout_s: Optional[float] = None) -> Dict[str, Any]:
        return self._request("steer", {"message": text}, timeout_s)

    def prompt(
        self,
        text: str,
        *,
        stream: bool = False,
        streaming_behavior: str = "followUp",
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "text": text, "streamingBehavior": streaming_behavior}
        if model or self._model:
            payload["model"] = model or self._model
        marker = len(self._events)
        resp = self._request("prompt", payload, timeout_s)
        events = [e for e in self._events[marker:]
                  if e.get("id") == resp.get("id")]
        ok = bool(resp.get("success"))
        result = resp.get("result") or {}
        text_out = result.get("text") if isinstance(result, dict) else None
        return {
            "ok": ok, "text": text_out or "",
            "events": events, "raw": resp,
        }

    # ── internals ──────────────────────────────────────────────────────────
    def _request(self, command: str, extra: Dict[str, Any],
                 timeout_s: Optional[float]) -> Dict[str, Any]:
        if not self._alive or self._proc is None or self._proc.stdin is None:
            raise RuntimeError("engine not started")
        rid = uuid.uuid4().hex[:12]
        entry = {"event": threading.Event(), "resp": None}
        with self._lock:
            self._pending[rid] = entry
        msg = {"id": rid, "type": "request", "command": command, **extra}
        line = (json.dumps(msg) + "\n").encode("utf-8")
        try:
            self._proc.stdin.write(line)
            self._proc.stdin.flush()
        except Exception as exc:
            with self._lock:
                self._pending.pop(rid, None)
            raise RuntimeError(f"rpc write failed: {exc}") from exc
        deadline = (timeout_s if timeout_s is not None
                    else self._default_timeout)
        if not entry["event"].wait(timeout=max(0.01, deadline)):
            with self._lock:
                self._pending.pop(rid, None)
            raise TimeoutError(f"rpc timeout after {deadline}s ({command})")
        resp = entry["resp"] or {}
        if isinstance(resp.get("result"), dict) and \
                resp["result"].get("error") == "no_key":
            logger.info("prime engine reports missing provider key")
        return resp

    def _read_loop(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stdout is not None
        for raw in proc.stdout:
            if not self._alive:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("prime rpc: unparsable line %r", line[:120])
                continue
            if msg.get("type") == "response":
                with self._lock:
                    entry = self._pending.pop(str(msg.get("id")), None)
                if entry:
                    entry["resp"] = msg
                    entry["event"].set()
            elif msg.get("type") == "event":
                with self._lock:
                    self._events.append({
                        "id": msg.get("id"),
                        "event": msg.get("event"),
                        "data": msg.get("data"),
                        "ts": time.time(),
                    })
        # EOF: fail all waiters fast
        with self._lock:
            waiters = list(self._pending.items())
            self._pending.clear()
        for _, entry in waiters:
            entry["resp"] = {"success": False, "error": "engine exited"}
            entry["event"].set()


# ── singleton ──────────────────────────────────────────────────────────────
_engine: Optional[PrimeEngine] = None


def get_engine() -> PrimeEngine:
    """Config-gated shared engine (ariadne.prime.enabled)."""
    global _engine
    if _engine is None:
        enabled = False
        try:
            from hermes_cli.config import load_config

            pcfg = ((load_config() or {}).get("ariadne") or {}).get("prime") or {}
            enabled = bool(pcfg.get("enabled", True))
        except Exception:
            pass
        if not enabled:
            raise RuntimeError(
                "prime engine disabled by config (ariadne.prime.enabled=false)")
        try:
            _engine = PrimeEngine()
            _engine.start()
        except FileNotFoundError as exc:
            raise RuntimeError(
                "prime bundle missing — run scripts/build-prime.sh "
                f"({exc})") from exc
    return _engine


def close_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.stop()
        _engine = None
