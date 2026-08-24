"""PrimeEngine -- drives vendored prime-agent over `--mode rpc` (JSONL).

Wire format (decoded from vendor/prime-agent rpc-types.ts / rpc-mode.ts /
rpc-client.ts -- the adapter contract lives here):

    request   : {"id": "<rid>", "type": "<command>", ...payload}
    response  : {"id": "<rid>", "type": "response", "command": "<command>",
                 "success": bool, "data"?: object, "error"?: string}
    events    : any other JSON line (agent stream); terminal = agent_end

Prompt flow: ACK response arrives first, agent events stream, run ends with
an `agent_end` event; final text is fetched via `get_last_assistant_text`.
Upstream drift ever touches exactly this file plus fixtures.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import uuid
from collections import deque
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
        env_passthrough: bool = True,
    ) -> None:
        self._command = list(command or _DEFAULT_COMMAND)
        self._model = model
        self._provider = provider
        self._cwd = cwd
        self._default_timeout = request_timeout_s
        self._env_passthrough = env_passthrough
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.RLock()
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._events: List[Dict[str, Any]] = []
        self._event_ping = threading.Condition(self._lock)
        self._stderr_tail: deque = deque(maxlen=40)
        self._alive = False

    # ── lifecycle ──────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._alive:
            return
        env = os.environ.copy() if self._env_passthrough else None
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self._cwd,
            env=env,
        )
        self._alive = True
        threading.Thread(target=self._read_loop, name="prime-rpc-reader",
                         daemon=True).start()
        threading.Thread(target=self._stderr_loop, name="prime-rpc-stderr",
                         daemon=True).start()

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    def stderr_summary(self) -> str:
        return " | ".join(self._stderr_tail)[-600:]

    def stop(self) -> None:
        self._alive = False
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass
        if os.name == "nt" and proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True)
        with self._lock:
            waiters = list(self._pending.items())
            self._pending.clear()
        for _, entry in waiters:
            entry["resp"] = {"success": False, "error": "engine stopped"}
            entry["event"].set()

    # ── requests ───────────────────────────────────────────────────────────
    def state(self, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        resp = self._request("get_state", {}, timeout_s)
        resp["data"] = resp.get("data") or {}
        return resp

    def new_session(self, timeout_s: Optional[float] = None) -> Dict[str, Any]:
        return self._request("new_session", {}, timeout_s)

    def steer(self, text: str,
              timeout_s: Optional[float] = None) -> Dict[str, Any]:
        return self._request("steer", {"message": text}, timeout_s)

    def last_text(self, timeout_s: Optional[float] = None) -> str:
        resp = self._request("get_last_assistant_text", {}, timeout_s)
        data = resp.get("data")
        if isinstance(data, dict):
            return str(data.get("text") or "")
        return str(data or "")

    def prompt(
        self,
        text: str,
        *,
        streaming_behavior: str = "followUp",
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        marker = len(self._events)
        payload: Dict[str, Any] = {
            "message": text, "streamingBehavior": streaming_behavior}
        ack = self._request("prompt", payload, min(60.0, self._default_timeout))
        if not ack.get("success"):
            return {"ok": False, "text": "", "events": [], "raw": ack}
        ended = self._wait_for_event(
            "agent_end",
            timeout_s if timeout_s is not None else self._default_timeout,
            after=marker)
        events = [e for e in self._events[marker:]]
        if not ended:
            return {
                "ok": False, "text": self.last_text(15), "events": events,
                "raw": {"success": False,
                        "error": ("timeout waiting for agent_end; "
                                  f"stderr: {self.stderr_summary()}")},
            }
        return {
            "ok": True, "text": self.last_text(30),
            "events": events, "raw": ack,
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
        msg = {"id": rid, "type": command, **extra}
        try:
            self._proc.stdin.write(
                (json.dumps(msg) + "\n").encode("utf-8"))
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
            exited = self._proc.poll() if self._proc else None
            raise TimeoutError(
                f"rpc timeout after {deadline}s ({command})"
                + (f"; process exited code={exited}; "
                   f"stderr: {self.stderr_summary()}" if exited is not None else ""))
        return entry["resp"] or {}

    def _wait_for_event(self, name: str, timeout_s: float,
                        *, after: int = 0) -> bool:
        deadline = time.time() + max(0.05, timeout_s)
        with self._event_ping:
            while True:
                if any(e.get("type") == name for e in self._events[after:]):
                    return True
                remaining = deadline - time.time()
                if remaining <= 0 or not self._alive:
                    return False
                self._event_ping.wait(timeout=min(0.25, remaining))

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
                logger.debug("prime rpc: unparsable %r", line[:120])
                continue
            if isinstance(msg, dict) and msg.get("type") == "response":
                with self._lock:
                    entry = self._pending.pop(str(msg.get("id")), None)
                if entry:
                    entry["resp"] = msg
                    entry["event"].set()
                continue
            with self._event_ping:
                self._events.append(msg)
                self._event_ping.notify_all()
        with self._lock:
            waiters = list(self._pending.items())
            self._pending.clear()
        for _, entry in waiters:
            exited = proc.poll()
            entry["resp"] = {
                "success": False,
                "error": (f"engine exited code={exited}; "
                          f"stderr: {self.stderr_summary()}"),
            }
            entry["event"].set()

    def _stderr_loop(self) -> None:
        proc = self._proc
        assert proc is not None and proc.stderr is not None
        for raw in proc.stderr:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line:
                with self._lock:
                    self._stderr_tail.append(line[:200])


# ── singleton ──────────────────────────────────────────────────────────────
_engine: Optional[PrimeEngine] = None


def get_engine() -> PrimeEngine:
    """Config-gated shared engine (ariadne.prime.enabled)."""
    global _engine
    if _engine is None:
        enabled = True
        try:
            from hermes_cli.config import load_config

            pcfg = ((load_config() or {}).get("ariadne") or {}).get("prime") or {}
            enabled = bool(pcfg.get("enabled", True))
        except Exception:
            pass
        if not enabled:
            raise RuntimeError(
                "prime engine disabled by config (ariadne.prime.enabled=false)")
        if not Path(_DEFAULT_COMMAND[1]).exists():
            raise RuntimeError(
                "prime bundle missing — run scripts/build-prime.sh")
        _engine = PrimeEngine()
        _engine.start()
    return _engine


def close_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.stop()
        _engine = None
