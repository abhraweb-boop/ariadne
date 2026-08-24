"""GuideStore -- build sessions + decision log (Phase 9).

A "build" is a guided conversation that turns a vague goal into a working
application, one milestone at a time. Every question the guide asks and
every answer (human or auto-decided) is persisted so `/why` can always
reconstruct reasoning. Same graph.db family as everything else.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS builds(
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    archetype TEXT NOT NULL DEFAULT 'freeform',
    milestone_idx INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'active',   -- active|done|abandoned
    context TEXT NOT NULL DEFAULT '{}',     -- accumulated slot values/decisions
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_id TEXT NOT NULL REFERENCES builds(id),
    milestone_id TEXT NOT NULL DEFAULT '',
    question_id TEXT NOT NULL DEFAULT '',
    option_id TEXT NOT NULL,                -- 'auto:<choice>' when auto-decided
    chosen_label TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_build ON decisions(build_id);
"""


class GuideStore:
    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._lock = threading.RLock()

    def close(self) -> None:
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:
            pass

    # ── builds ────────────────────────────────────────────────────────────
    def create_build(self, goal: str, archetype: str = "freeform",
                     context: Optional[Dict[str, Any]] = None) -> str:
        now = time.time()
        bid = f"bld-{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO builds(id,goal,archetype,milestone_idx,state,"
                "context,created_at,updated_at) VALUES(?,?,?,0,'active',?,?,?)",
                (bid, goal.strip(), archetype,
                 json.dumps(context or {}), now, now))
            self._conn.commit()
        return bid

    def get_build(self, build_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM builds WHERE id=?", (build_id,)).fetchone()
            if r is None:
                return None
            d = dict(r)
            d["context"] = json.loads(d.get("context") or "{}")
            return d

    def set_milestone(self, build_id: str, idx: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE builds SET milestone_idx=?, updated_at=? WHERE id=?",
                (idx, time.time(), build_id))
            self._conn.commit()

    def set_state(self, build_id: str, state: str) -> None:
        assert state in ("active", "done", "abandoned")
        with self._lock:
            self._conn.execute(
                "UPDATE builds SET state=?, updated_at=? WHERE id=?",
                (state, time.time(), build_id))
            self._conn.commit()

    def merge_context(self, build_id: str, patch: Dict[str, Any]) -> Dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT context FROM builds WHERE id=?", (build_id,)).fetchone()
            if row is None:
                raise KeyError(build_id)
            ctx = json.loads(row["context"] or "{}")
            ctx.update(patch)
            self._conn.execute(
                "UPDATE builds SET context=?, updated_at=? WHERE id=?",
                (json.dumps(ctx), time.time(), build_id))
            self._conn.commit()
            return ctx

    # ── decisions ─────────────────────────────────────────────────────────
    def record_decision(self, build_id: str, *, question_id: str = "",
                        option_id: str, chosen_label: str = "",
                        rationale: str = "", milestone_id: str = "") -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO decisions(build_id,milestone_id,question_id,"
                "option_id,chosen_label,rationale,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (build_id, milestone_id, question_id, option_id,
                 chosen_label[:200], rationale[:800], time.time()))
            self._conn.commit()
            return cur.lastrowid

    def decisions_for(self, build_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(
                "SELECT * FROM decisions WHERE build_id=? ORDER BY id",
                (build_id,))]


# ── module singleton (same seam as plan_tool) ─────────────────────────────
_store: Optional[GuideStore] = None


def _get_guide_store() -> GuideStore:
    global _store
    if _store is None:
        from plugins.context_graph import _db_path

        _store = GuideStore(_db_path())
    return _store


def close_guide_store() -> None:
    global _store
    if _store is not None:
        _store.close()
        _store = None
