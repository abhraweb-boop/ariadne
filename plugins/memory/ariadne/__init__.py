"""Ariadne memory provider -- versioned SQLite ledger + refine support.

Activated with ``memory.provider: ariadne`` in config.yaml. Implements the
Hermes MemoryProvider ABC (agent/memory_provider.py) and injects ONE tool,
``ariadne_memory``, action-dispatched:

    add / update / delete / get / search / list / history /
    rollback / snapshot / restore_snapshot / stats

Design contract: docs/architecture-ariadne-phase2.md
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider, RecallStatus

logger = logging.getLogger(__name__)

_TOOL = "ariadne_memory"

_KINDS = ("memory", "user", "skill_desc", "prompt_note", "subagent_spec", "event")

# Model-friendly aliases -> canonical actions (weak models invent verbs).
_ACTION_ALIASES = {
    "read": "get",
    "create": "add",
    "new": "add",
    "remove": "delete",
    "rm": "delete",
    "del": "delete",
    "find": "search",
    "query": "search",
    "ls": "list",
    "entries": "list",
    "versions": "history",
    "log": "history",
    "undo": "rollback",
    "revert": "rollback",
    "info": "stats",
    "status": "stats",
}

# Fallback keys models use instead of `body`.
_BODY_FALLBACK_KEYS = ("content", "text", "value", "entry", "memory", "note", "data")


def _canonical_action(raw: str) -> str:
    a = (raw or "").strip().lower()
    return _ACTION_ALIASES.get(a, a)


def _extract_body(args: Dict[str, Any]) -> str:
    """body, then known fallbacks, then any lone string field."""
    v = args.get("body")
    if isinstance(v, str) and v.strip():
        return v
    for k in _BODY_FALLBACK_KEYS:
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            return v
    strings = [
        val for val in args.values()
        if isinstance(val, str) and len(val) > 24 and val != args.get("action")
    ]
    return max(strings, key=len) if strings else ""


def _cfg(section: str) -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config
        return ((load_config() or {}).get("ariadne") or {}).get(section) or {}
    except Exception:
        return {}


class AriadneMemoryProvider(MemoryProvider):
    """10x-envelope memory provider backed by plugins.memory.ariadne.ledger."""

    def __init__(self) -> None:
        self._ledger = None
        self._session_id: Optional[str] = None
        self._snapshot_cache: str = ""
        self._dirty = False
        self._lock = threading.RLock()

    # ── lifecycle ────────────────────────────────────────────────────────
    @property
    def name(self) -> str:
        return "ariadne"

    def is_available(self) -> bool:
        cfg = _cfg("memory")
        if not cfg.get("enabled", True):
            when_active = _active_provider()
            if when_active != "ariadne":
                return False
        try:
            import sqlite3  # noqa: F401

            return True
        except ImportError:
            return False

    def unavailable_reason(self) -> str:
        if _active_provider() != "ariadne":
            return "set memory.provider: ariadne in config.yaml to activate"
        return ""

    def initialize(self, session_id: str, **kwargs) -> None:
        from plugins.memory.ariadne.ledger import MemoryLedger

        hermes_home = kwargs.get("hermes_home") or "."
        mcfg = _cfg("memory")
        budget_mb = int(mcfg.get("budget_mb", 36))
        db_path = (
            Path(hermes_home) / "ariadne" / "memory.db"
        )
        with self._lock:
            if self._ledger is None or str(self._ledger._path) != str(db_path):
                self.close()
                self._ledger = MemoryLedger(
                    db_path, budget_bytes=budget_mb * 1024 * 1024
                )
            self._session_id = session_id
            # Frozen snapshot for this session's system prompt.
            self._snapshot_cache = self._render_snapshot()

    def shutdown(self) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if self._ledger is not None:
                try:
                    self._ledger.close()
                except Exception:
                    pass
                self._ledger = None

    # ── prompt injection (cache-safe frozen snapshot) ────────────────────
    def system_prompt_block(self) -> str:
        return self._snapshot_cache

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """FTS5-ranked recall injected per turn (does NOT mutate the prompt)."""
        del session_id
        if self._ledger is None:
            return ""
        q = (query or "").strip()
        if len(q.split()) < 3:  # trivial prompts get no recall round-trip
            return ""
        hits = self._ledger.search(q, limit=int(_cfg("memory").get("prefetch_top_k", 12)))
        if not hits:
            return ""
        lines = ["<ariadne-memory-recall>"]
        for h in hits[: int(_cfg("memory").get("prefetch_top_k", 12))]:
            title = h["title"] or (h["body"][:60] + "…")
            lines.append(f"- [{h['kind']}#{h['id']}] {title}")
        lines.append(
            "Use ariadne_memory action=get with an id to read the full entry."
        )
        lines.append("</ariadne-memory-recall>")
        return "\n".join(lines)

    def recall_status(self) -> RecallStatus:
        return RecallStatus(provider_label="Ariadne", count=1)

    def on_turn_start(self, turn_number: int, message: str, **kwargs) -> None:
        pass

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        pass

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        return ""

    def on_delegation(self, task: str, result: str, **kwargs) -> None:
        pass

    def on_memory_write(self, target: str, entry: str) -> None:
        pass

    def backup_paths(self) -> List[str]:
        if self._ledger is None:
            return []
        return [str(self._ledger._path)]

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "ariadne.memory.budget_mb", "type": "int",
             "default": 36, "description": "Ledger soft budget in MB"},
            {"key": "ariadne.memory.max_entry_chars", "type": "int",
             "default": 8192, "description": "Max chars per entry"},
            {"key": "ariadne.memory.prefetch_top_k", "type": "int",
             "default": 12, "compact_only": False,
             "description": "Recall entries injected per qualifying turn"},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        pass

    # ── tool schema + dispatch ───────────────────────────────────────────
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        max_chars = int(_cfg("memory").get("max_entry_chars", 8192))
        return [
            {
                "name": _TOOL,
                "description": (
                    "Ariadne persistent memory ledger. Actions: add, update, "
                    "delete, get, search, list, history, rollback, snapshot, "
                    "restore_snapshot, stats. Every change is versioned + "
                    "rollback-able. EXAMPLE add call: "
                    '{"action":"add","body":"the text to remember",'
                    '"kind":"memory","title":"short label",'
                    '"evidence":"why this is being stored"}. '
                    "Kinds: memory/user/skill_desc/prompt_note/subagent_spec/event."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "add", "update", "delete", "get", "search",
                                "list", "history", "rollback", "snapshot",
                                "restore_snapshot", "stats",
                            ],
                            "description": "Ledger operation.",
                        },
                        "id": {"type": "string",
                               "description": "Entry id (from add/search/list)"},
                        "body": {"type": "string", "description": "Entry text"},
                        "title": {"type": "string", "description": "Short label"},
                        "kind": {"type": "string", "enum": list(_KINDS)},
                        "scope": {"type": "string", "enum": ["global", "session"]},
                        "weight": {"type": "number"},
                        "pinned": {"type": "boolean"},
                        "query": {"type": "string", "description": "Search text"},
                        "seq": {"type": "integer",
                                "description": "Version seq for rollback"},
                        "snapshot_id": {"type": "integer"},
                        "evidence": {"type": "string",
                                     "description": "Why this edit; required by "
                                     "the refine procedure"},
                    },
                    "required": ["action"],
                },
            }
        ]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name != _TOOL:
            return json.dumps({"ok": False, "error": f"unknown tool {tool_name}"})
        args = dict(args or {})
        # Some models nest everything under a single field; unwrap once.
        if len(args) == 1:
            (only_key, only_val), = args.items()
            if isinstance(only_val, dict):
                inner = {str(k): v for k, v in only_val.items()}
                inner.setdefault("action", str(only_key))
                args = inner
        action = _canonical_action(str(args.get("action") or ""))
        logger.info(
            "ariadne_memory call: action=%s arg_keys=%s body_len=%s",
            action,
            sorted(args.keys()),
            len(_extract_body(args)),
        )
        handlers = {
            "add": self._h_add, "update": self._h_update,
            "delete": self._h_delete, "get": self._h_get,
            "search": self._h_search, "list": self._h_list,
            "history": self._h_history, "rollback": self._h_rollback,
            "snapshot": self._h_snapshot, "restore_snapshot": self._h_restore,
            "stats": self._h_stats,
        }
        fn = handlers.get(action)
        if fn is None:
            return json.dumps({
                "ok": False,
                "error": (
                    f"unknown action '{args.get('action')}'. Valid actions: "
                    f"{sorted(handlers)} (aliases like read/create/find also work). "
                    f"Received arg keys: {sorted(args.keys())}. Example: "
                    f'{{"action":"add","body":"<text>","kind":"memory",'
                    f'"evidence":"<why>"}}'
                ),
            })
        try:
            out = fn(args)
            self._dirty = True
            return json.dumps(out, default=str)
        except Exception as exc:
            logger.exception("ariadne_memory %s failed", action)
            return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    # ── action handlers ──────────────────────────────────────────────────
    def _ledger_or_err(self):
        if self._ledger is None:
            raise RuntimeError("ledger not initialized")
        return self._ledger

    def _h_add(self, a: Dict[str, Any]) -> Dict[str, Any]:
        body = _extract_body(a)
        max_chars = int(_cfg("memory").get("max_entry_chars", 8192))
        if not body.strip():
            return {
                "ok": False,
                "error": (
                    "add requires non-empty text in the 'body' field. Example: "
                    '{"action":"add","body":"<text>","kind":"memory",'
                    '"evidence":"<why>"}'
                ),
            }
        if len(body) > max_chars:
            return {"ok": False,
                    "error": f"entry exceeds {max_chars} chars ({len(body)})"}
        rec = self._ledger_or_err().add(
            body=body,
            kind=a.get("kind") or "memory",
            scope=a.get("scope") or "global",
            session_id=self._session_id if (a.get("scope") == "session") else None,
            title=a.get("title") or "",
            weight=float(a.get("weight", 1.0)),
            pinned=bool(a.get("pinned", False)),
            evidence=str(a.get("evidence") or ""),
        )
        return {"ok": True, "entry": rec}

    def _h_update(self, a): 
        kw = {}
        for k in ("body", "title"):
            if a.get(k) is not None:
                kw[k] = str(a[k])
        if a.get("weight") is not None:
            kw["weight"] = float(a["weight"])
        if a.get("pinned") is not None:
            kw["pinned"] = bool(a["pinned"])
        rec = self._ledger_or_err().update(
            str(a.get("id") or ""), evidence=str(a.get("evidence") or ""), **kw
        )
        return {"ok": True, "entry": rec}

    def _h_delete(self, a):
        rec = self._ledger_or_err().delete(
            str(a.get("id") or ""), evidence=str(a.get("evidence") or "")
        )
        return {"ok": True, "entry": rec}

    def _h_get(self, a):
        rec = self._ledger_or_err().get(str(a.get("id") or ""))
        return {"ok": rec is not None, "entry": rec}

    def _h_search(self, a):
        rows = self._ledger_or_err().search(
            str(a.get("query") or ""), limit=int(a.get("limit", 12))
        )
        return {"ok": True, "results": rows}

    def _h_list(self, a):
        rows = self._ledger_or_err().list(
            kind=a.get("kind"), scope=a.get("scope"), limit=int(a.get("limit", 100))
        )
        return {"ok": True, "entries": rows}

    def _h_history(self, a):
        rows = self._ledger_or_err().history(
            a.get("id") or None, limit=int(a.get("limit", 50))
        )
        return {"ok": True, "versions": rows}

    def _h_rollback(self, a):
        rec = self._ledger_or_err().rollback_entry(
            str(a.get("id") or ""),
            seq=(int(a["seq"]) if a.get("seq") else None),
            evidence=str(a.get("evidence") or ""),
        )
        return {"ok": True, "entry": rec}

    def _h_snapshot(self, a):
        return self._ledger_or_err().snapshot(str(a.get("label") or ""))

    def _h_restore(self, a):
        return self._ledger_or_err().restore_snapshot(
            int(a.get("snapshot_id")), evidence=str(a.get("evidence") or "")
        )

    def _h_stats(self, a):
        return {"ok": True, **self._ledger_or_err().stats()}

    # ── snapshot rendering ───────────────────────────────────────────────
    def _render_snapshot(self) -> str:
        if self._ledger is None:
            return ""
        rows = self._ledger.list(limit=int(_cfg("memory").get("prefetch_top_k", 12)))
        if not rows:
            return ""
        lines = ["<ariadne-memory>"]
        for r in rows[:12]:
            title = r["title"] or r["body"][:60]
            lines.append(f"[{r['kind']}#{r['id']}] {title}")
        lines.append("</ariadne-memory>")
        return "\n".join(lines)


def _active_provider() -> str:
    try:
        from hermes_cli.config import load_config
        return ((load_config() or {}).get("memory") or {}).get("provider") or ""
    except Exception:
        return ""


# Plugin discovery contract: export the provider class.
provider_class = AriadneMemoryProvider
