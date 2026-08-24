"""Ariadne kernel manager -- persistent IPython kernel lifecycle + transport.

Channel transport is delegated to ``jupyter_client.blocking.BlockingKernelClient``
-- the reference implementation for Jupyter-over-ZMQ (signing, subscription
handshake, channel threads, timeouts). Hand-rolling those produced iopub
subscription-propagation races under load; the client library already solved
them. This manager keeps ownership of:

- the ipykernel child process (loopback TCP, connection file under HERMES_HOME),
- serialized ``execute()`` with rich output collection,
- the custom host-request ROUTER bridge answering the kernel-side ``rlm``
  shim (admission-only replies over a side channel -- never the Jupyter shell
  channel -- mirroring Prime Agent's deadlock-free comm design),
- graceful shutdown_request -> terminate -> kill fallback.
"""

from __future__ import annotations

import json
import logging
import secrets
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_BOOT_TIMEOUT_S = 45.0


class KernelError(RuntimeError):
    pass


class KernelManager:
    """Lifecycle + transport for one persistent IPython kernel."""

    def __init__(
        self,
        python_exe: str,
        *,
        runtime_dir: Path,
        host_request_handler: Optional[
            Callable[[str, Dict[str, Any]], Dict[str, Any]]
        ] = None,
        env_extra: Optional[Dict[str, str]] = None,
    ) -> None:
        self._python = str(python_exe)
        self._runtime_dir = Path(runtime_dir)
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        self._host_handler = host_request_handler
        self._env_extra = dict(env_extra or {})

        self._exec_lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._kc = None                      # BlockingKernelClient
        self._conn_path: Optional[str] = None
        self._host_endpoint: Optional[str] = None
        self._started_at: Optional[float] = None
        self._kernel_log = None
        self._kernel_log_path: Optional[Path] = None

    # ── lifecycle ────────────────────────────────────────────────────────
    @property
    def host_endpoint(self) -> Optional[str]:
        return self._host_endpoint

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> Dict[str, Any]:
        if self.is_running():
            return {"already_running": True, "pid": self._proc.pid}
        import zmq
        from jupyter_client.blocking import BlockingKernelClient
        from jupyter_client.connect import write_connection_file

        self._ctx = zmq.Context.instance()

        fname = str(self._runtime_dir / f"conn-{uuid.uuid4().hex}.json")
        cf_path, _cfg = write_connection_file(
            fname=fname,
            ip="127.0.0.1",
            transport="tcp",
            kernel_name="ariadne",
            # Hex-encoded so write_connection_file can utf-8-decode it into
            # the JSON file; client and kernel then share the same bytes.
            key=secrets.token_hex(32).encode("ascii"),
        )
        self._conn_path = cf_path

        router = self._ctx.socket(zmq.ROUTER)
        router.setsockopt(zmq.LINGER, 0)
        router.bind("tcp://127.0.0.1:0")
        self._host_endpoint = router.getsockopt(zmq.LAST_ENDPOINT).decode()
        self._sock_router = router
        threading.Thread(
            target=self._serve_host_requests,
            daemon=True,
            name="ariadne-host-bridge",
        ).start()

        import os

        env: Dict[str, str] = {**os.environ, **self._env_extra}
        env["ARIADNE_HOST_ENDPOINT"] = self._host_endpoint
        self._kernel_log_path = self._runtime_dir / (
            f"kernel-{Path(cf_path).stem}.log"
        )
        self._kernel_log = open(self._kernel_log_path, "ab")
        self._proc = subprocess.Popen(
            [self._python, "-m", "ipykernel_launcher", "-f", cf_path],
            stdout=self._kernel_log,
            stderr=self._kernel_log,
            env=env,
            cwd=str(self._runtime_dir),
        )

        try:
            kc = BlockingKernelClient()
            kc.load_connection_file(cf_path)
            kc.start_channels()
            # Handles the SUB subscription handshake + kernel_info probe
            # correctly (the piece a naive sleep gets wrong).
            kc.wait_for_ready(timeout=_BOOT_TIMEOUT_S)
        except Exception:
            tail = self._kernel_log_tail()
            self.shutdown(force=True)
            raise KernelError(f"kernel failed readiness probe\n{tail}") from None

        if self._proc.poll() is not None:
            tail = self._kernel_log_tail()
            rc = self._proc.returncode
            self.shutdown(force=True)
            raise KernelError(f"kernel exited during boot (rc={rc})\n{tail}")

        self._kc = kc
        self._started_at = time.time()
        return {"pid": self._proc.pid, "ready": True}

    # ── execution ────────────────────────────────────────────────────────
    def execute(self, code: str, *, timeout_s: float = 300.0) -> Dict[str, Any]:
        """Run one cell. Serialized across threads; namespace persists."""
        if self._kc is None or not self.is_running():
            raise KernelError("kernel is not running")

        from queue import Empty

        with self._exec_lock:
            msg_id = self._kc.execute(
                code, store_history=True, allow_stdin=False, stop_on_error=False
            )

            outputs: list[Dict[str, Any]] = []
            error: Optional[Dict[str, Any]] = None
            saw_idle = False
            reply: Optional[Dict[str, Any]] = None
            deadline = time.monotonic() + timeout_s

            # Collect iopub until our cell goes idle; fetch the shell reply.
            while not saw_idle:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return {
                        "status": "timeout",
                        "outputs": outputs,
                        "timeout_seconds": timeout_s,
                        "error": None,
                        "idle_seen": False,
                        "reply_seen": reply is not None,
                    }
                try:
                    frame = self._kc.get_iopub_msg(timeout=min(remaining, 0.25))
                except Empty:
                    continue
                except Exception:
                    continue
                if (frame.get("parent_header") or {}).get("msg_id") != msg_id:
                    continue
                mt = frame.get("msg_type")
                c = frame.get("content") or {}
                if mt == "stream":
                    outputs.append({
                        "type": "stream",
                        "name": c.get("name"),
                        "text": c.get("text"),
                    })
                elif mt in ("execute_result", "display_data"):
                    data = c.get("data") or {}
                    piece: Dict[str, Any] = {"type": mt}
                    if "text/plain" in data:
                        piece["text"] = data["text/plain"]
                    if "image/png" in data:
                        piece["image_png_b64"] = data["image/png"]
                    outputs.append(piece)
                elif mt == "error":
                    error = {
                        "ename": c.get("ename"),
                        "evalue": c.get("evalue"),
                        "traceback": c.get("traceback"),
                    }
                    outputs.append({"type": "error", **error})
                elif mt == "status" and c.get("execution_state") == "idle":
                    saw_idle = True

            remaining = max(0.5, deadline - time.monotonic())
            try:
                reply = self._kc.get_shell_msg(timeout=remaining)
            except Exception:
                reply = None
            status = ((reply or {}).get("content") or {}).get("status") or "error"
            if status == "error" and error is None:
                rc_content = (reply or {}).get("content") or {}
                error = {
                    "ename": rc_content.get("ename"),
                    "evalue": rc_content.get("evalue"),
                    "traceback": rc_content.get("traceback"),
                }
            return {
                "status": "ok" if status == "ok" else "error",
                "outputs": outputs,
                "error": error,
                "idle_seen": True,
            }

    # ── host-request bridge ──────────────────────────────────────────────
    def _serve_host_requests(self) -> None:
        import zmq

        router = self._sock_router
        poller = zmq.Poller()
        poller.register(router, zmq.POLLIN)
        while True:
            try:
                events = dict(poller.poll(500))
            except zmq.ZMQError:
                break  # context torn down
            if router not in events:
                if self._proc is not None and self._proc.poll() is not None:
                    break
                continue
            try:
                identity, raw = router.recv_multipart()
                req = json.loads(raw.decode("utf-8"))
            except Exception:
                continue
            req_type = str(req.get("type") or "")
            payload = req.get("payload") or {}
            if self._host_handler is None:
                result, ok, err = {}, False, "host bridge not configured"
            else:
                try:
                    result = self._host_handler(req_type, payload)
                    ok, err = True, None
                except Exception as exc:
                    result, ok, err = {}, False, f"{type(exc).__name__}: {exc}"
            reply = json.dumps(
                {
                    "id": req.get("id"),
                    "ok": ok,
                    **({} if ok else {"error": err}),
                    "result": result,
                }
            ).encode("utf-8")
            try:
                router.send_multipart([identity, reply])
            except zmq.ZMQError:
                break

    # ── teardown ─────────────────────────────────────────────────────────
    def restart(self) -> Dict[str, Any]:
        self.shutdown()
        return self.start()

    def shutdown(self, *, force: bool = False) -> None:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            if not force and self._kc is not None:
                try:
                    self._kc.shutdown_request(content={"restart": False})
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        try:
                            proc.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            else:
                try:
                    proc.kill()
                except Exception:
                    pass
        if self._kc is not None:
            try:
                self._kc.stop_channels()
            except Exception:
                pass
        self._kc = None
        try:
            self._sock_router.close(0)
        except Exception:
            pass
        if self._conn_path:
            for attempt in range(4):
                try:
                    Path(self._conn_path).unlink(missing_ok=True)
                    break
                except OSError:
                    time.sleep(0.25 * (attempt + 1))
        self._conn_path = None
        self._proc = None
        self._started_at = None
        if self._kernel_log is not None:
            try:
                self._kernel_log.close()
            except Exception:
                pass
            self._kernel_log = None

    # ── helpers ──────────────────────────────────────────────────────────
    def _kernel_log_tail(self) -> str:
        if self._kernel_log_path and self._kernel_log_path.exists():
            try:
                return self._kernel_log_path.read_text(
                    encoding="utf-8", errors="replace"
                )[-800:]
            except Exception:
                return ""
        return ""


__all__ = ["KernelManager", "KernelError"]
