"""Ariadne memory ledger -- SQLite-backed, versioned, FTS5-searchable store.

The Phase-2 "10x" envelope vs Hermes' builtin two-file memory:
  capacity   ~3.6 KB hard cap  -> 36 MB soft budget (configurable, SQLite-scale)
  entries    flat text blocks  -> rows with kind/scope/weight/pin/status
  history    none              -> append-only version chain per entry
  rollback   none              -> per-entry point-in-time + whole-store snapshots
  search     substring (edit ops only) -> FTS5 keyword ranking at recall time

Cache-safety invariant inherited from upstream Hermes: callers inject a frozen
snapshot at session start; mid-session writes are durable here but never mutate
past context mid-conversation.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    scope      TEXT NOT NULL DEFAULT 'global',
    session_id TEXT,
    title      TEXT NOT NULL DEFAULT '',
    body       TEXT NOT NULL,
    weight     REAL NOT NULL DEFAULT 1.0,
    pinned     INTEGER NOT NULL DEFAULT 0,
    status     TEXT NOT NULL DEFAULT 'active',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_kind ON entries(kind);
CREATE INDEX IF NOT EXISTS idx_entries_scope ON entries(scope, session_id);

CREATE TABLE IF NOT EXISTS versions (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id   TEXT NOT NULL,
    op         TEXT NOT NULL,
    before     TEXT,
    after      TEXT,
    evidence   TEXT,
    source     TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_versions_entry ON versions(entry_id);

CREATE TABLE IF NOT EXISTS snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT,
    created_at REAL NOT NULL,
    payload    TEXT NOT NULL
);
"""


class LedgerError(RuntimeError):
    pass


class MemoryLedger:
    """Versioned SQLite memory ledger with FTS5 recall."""

    def __init__(self, db_path: Path, *, budget_bytes: int = 36 * 1024 * 1024) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._budget = int(budget_bytes)
        self._conn = sqlite3.connect(
            str(self._path), check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        # fts5 is optional at runtime (some builds omit it); degrade cleanly.
        try:
            self._conn.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                    title, body, content='entries', content_rowid='rowid'
                );
                CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
                    INSERT INTO entries_fts(rowid, title, body)
                    VALUES (new.rowid, new.title, new.body);
                END;
                CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
                    INSERT INTO entries_fts(entries_fts, rowid, title, body)
                    VALUES ('delete', old.rowid, old.title, old.body);
                END;
                CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE OF title, body
                ON entries BEGIN
                    INSERT INTO entries_fts(entries_fts, rowid, title, body)
                    VALUES ('delete', old.rowid, old.title, old.body);
                    INSERT INTO entries_fts(rowid, title, body)
                    VALUES (new.rowid, new.title, new.body);
                END;
                """
            )
            self._fts_enabled = True
        except sqlite3.OperationalError:
            logger.warning("ariadne.memory: FTS5 unavailable; search falls back to LIKE")
            self._fts_enabled = False
        self._conn.commit()

    # ── internals ────────────────────────────────────────────────────────
    @contextmanager
    def _tx(self):
        with self._lock_wrap():
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _lock_wrap(self):
        # sqlite3 with check_same_thread=False needs serialization.
        if not hasattr(self, "_wlock"):
            import threading

            self._wlock = threading.RLock()
        return self._wlock

    def _record_version(
        self,
        conn: sqlite3.Connection,
        entry_id: str,
        op: str,
        before: Optional[Dict[str, Any]],
        after: Optional[Dict[str, Any]],
        evidence: str,
        source: str,
    ) -> None:
        conn.execute(
            "INSERT INTO versions(entry_id, op, before, after, evidence, source,"
            " created_at) VALUES (?,?,?,?,?,?,?)",
            (
                entry_id,
                op,
                json.dumps(before) if before is not None else None,
                json.dumps(after) if after is not None else None,
                evidence,
                source,
                time.time(),
            ),
        )

    # ── CRUD ─────────────────────────────────────────────────────────────
    def add(
        self,
        *,
        body: str,
        kind: str = "memory",
        scope: str = "global",
        session_id: Optional[str] = None,
        title: str = "",
        weight: float = 1.0,
        pinned: bool = False,
        evidence: str = "",
        source: str = "tool",
    ) -> Dict[str, Any]:
        body = (body or "").strip()
        if not body:
            raise LedgerError("cannot add empty entry")
        now = time.time()
        eid = uuid.uuid4().hex[:16]
        rec = {
            "id": eid,
            "kind": kind,
            "scope": scope,
            "session_id": session_id,
            "title": title.strip(),
            "body": body,
            "weight": float(weight),
            "pinned": int(bool(pinned)),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        with self._tx() as conn:
            self._enforce_budget(conn, incoming=len(body))
            cols = ",".join(rec)
            marks = ",".join("?" for _ in rec)
            conn.execute(f"INSERT INTO entries({cols}) VALUES ({marks})",
                         tuple(rec.values()))
            self._record_version(conn, eid, "create", None, rec, evidence, source)
        return rec

    def update(
        self,
        entry_id: str,
        *,
        body: Optional[str] = None,
        title: Optional[str] = None,
        weight: Optional[float] = None,
        pinned: Optional[bool] = None,
        evidence: str = "",
        source: str = "tool",
    ) -> Dict[str, Any]:
        with self._tx() as conn:
            row = self._get_active(conn, entry_id)
            before = dict(row)
            sets, vals = [], []
            if body is not None:
                body = body.strip()
                if not body:
                    raise LedgerError("update cannot set an empty body")
                sets.append("body=?")
                vals.append(body)
            if title is not None:
                sets.append("title=?")
                vals.append(title.strip())
            if weight is not None:
                sets.append("weight=?")
                vals.append(float(weight))
            if pinned is not None:
                sets.append("pinned=?")
                vals.append(int(bool(pinned)))
            if not sets:
                raise LedgerError("update: nothing to change")
            sets += ["updated_at=?"]
            vals += [time.time(), entry_id]
            conn.execute(f"UPDATE entries SET {', '.join(sets)} WHERE id=?", vals)
            after = dict(self._get_active(conn, entry_id))
            self._record_version(conn, entry_id, "update", before, after,
                                 evidence, source)
        return after

    def delete(self, entry_id: str, *, evidence: str = "", source: str = "tool") -> Dict[str, Any]:
        """Soft-delete: status flips to 'deleted'; history retains everything."""
        with self._tx() as conn:
            row = self._get_active(conn, entry_id)
            before = dict(row)
            conn.execute(
                "UPDATE entries SET status='deleted', updated_at=? WHERE id=?",
                (time.time(), entry_id),
            )
            after = {**before, "status": "deleted"}
            self._record_version(conn, entry_id, "delete", before, after,
                                 evidence, source)
        return after

    def get(self, entry_id: str, *, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        with self._lock_wrap():
            row = self._conn.execute(
                "SELECT * FROM entries WHERE id=?", (entry_id,)
            ).fetchone()
        if row is None:
            return None
        rec = dict(row)
        if rec["status"] != "active" and not include_deleted:
            return None
        return rec

    def list(
        self,
        *,
        kind: Optional[str] = None,
        scope: Optional[str] = None,
        session_id: Optional[str] = None,
        include_deleted: bool = False,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        q = ["SELECT * FROM entries WHERE 1=1"]
        args: List[Any] = []
        if not include_deleted:
            q.append("AND status='active'")
        if kind:
            q.append("AND kind=?")
            args.append(kind)
        if scope:
            q.append("AND scope=?")
            args.append(scope)
        if session_id:
            q.append("AND session_id=?")
            args.append(session_id)
        q.append("ORDER BY pinned DESC, weight DESC, updated_at DESC LIMIT ?")
        args.append(int(limit))
        with self._lock_wrap():
            rows = self._conn.execute(" ".join(q), args).fetchall()
        return [dict(r) for r in rows]

    # ── search ───────────────────────────────────────────────────────────
    def search(self, query: str, *, limit: int = 12) -> List[Dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []
        with self._lock_wrap():
            if getattr(self, "_fts_enabled", False):
                try:
                    rows = self._conn.execute(
                        """
                        SELECT e.* FROM entries_fts f
                        JOIN entries e ON e.rowid = f.rowid
                        WHERE entries_fts MATCH ? AND e.status='active'
                        ORDER BY bm25(entries_fts) LIMIT ?
                        """,
                        (query, int(limit)),
                    ).fetchall()
                    return [dict(r) for r in rows]
                except sqlite3.OperationalError:
                    pass  # fall through to LIKE
            like = f"%{query}%"
            rows = self._conn.execute(
                "SELECT * FROM entries WHERE status='active' AND "
                "(title LIKE ? OR body LIKE ?) "
                "ORDER BY pinned DESC, weight DESC, updated_at DESC LIMIT ?",
                (like, like, int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── history / rollback ───────────────────────────────────────────────
    def history(self, entry_id: Optional[str] = None, *, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock_wrap():
            if entry_id:
                rows = self._conn.execute(
                    "SELECT * FROM versions WHERE entry_id=? "
                    "ORDER BY seq DESC LIMIT ?",
                    (entry_id, int(limit)),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM versions ORDER BY seq DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            for col in ("before", "after"):
                if d.get(col):
                    d[col] = json.loads(d[col])
            out.append(d)
        return out

    def rollback_entry(self, entry_id: str, *, seq: Optional[int] = None,
                       evidence: str = "", source: str = "rollback") -> Dict[str, Any]:
        """Restore entry to state after `seq` (default: previous version)."""
        with self._tx() as conn:
            hist = conn.execute(
                "SELECT * FROM versions WHERE entry_id=? AND (? IS NULL OR seq<=?)"
                " ORDER BY seq DESC",
                (entry_id, seq, seq or -1),
            ).fetchall()
            if not hist:
                raise LedgerError(f"no version history for {entry_id}")
            if seq is None:
                # Undo the LATEST change: restore its recorded 'before' state.
                target = json.loads(hist[0]["before"] or "null")
                if not target:
                    raise LedgerError(
                        "nothing to roll back (newest version is the entry's creation)"
                    )
            else:
                # State AS OF seq = that version's 'after' snapshot.
                row_at = next((h for h in hist if h["seq"] == int(seq)), None)
                if row_at is None:
                    raise LedgerError(f"no version seq={seq} for {entry_id}")
                target = json.loads(row_at["after"] or row_at["before"] or "null")
            if not target:
                raise LedgerError("no restorable historical state found")
            # Entry may currently be soft-deleted/evicted -- read any row.
            cur = conn.execute(
                "SELECT * FROM entries WHERE id=?", (entry_id,)
            ).fetchone()
            before = dict(cur) if cur else None
            conn.execute(
                "INSERT INTO entries(id,kind,scope,session_id,title,body,weight,"
                "pinned,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET kind=excluded.kind, scope=excluded.scope,"
                " title=excluded.title, body=excluded.body, weight=excluded.weight,"
                " pinned=excluded.pinned, status='active', updated_at=excluded.updated_at",
                (
                    target["id"], target["kind"], target["scope"],
                    target.get("session_id"), target["title"], target["body"],
                    target["weight"], target["pinned"], "active",
                    target["created_at"], time.time(),
                ),
            )
            self._record_version(conn, entry_id, "update", before, target,
                                 evidence or f"rollback to seq<={seq}", source)
        return self.get(entry_id)

    def snapshot(self, label: str = "") -> Dict[str, Any]:
        with self._lock_wrap():
            rows = self._conn.execute(
                "SELECT * FROM entries WHERE status='active'"
            ).fetchall()
            payload = json.dumps([dict(r) for r in rows])
            cur = self._conn.execute(
                "INSERT INTO snapshots(label, created_at, payload) VALUES (?,?,?)",
                (label, time.time(), payload),
            )
            sid = cur.lastrowid
            count = len(rows)
            self._conn.commit()
        return {"snapshot_id": sid, "label": label, "entries": count}

    def restore_snapshot(self, snapshot_id: int, *, evidence: str = "") -> Dict[str, Any]:
        """Restore the WHOLE active set to a prior snapshot (versioned per entry)."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT payload FROM snapshots WHERE id=?", (int(snapshot_id),)
            ).fetchone()
            if row is None:
                raise LedgerError(f"unknown snapshot {snapshot_id}")
            wanted = {e["id"]: e for e in json.loads(row["payload"])}
            current = {
                r["id"]: dict(r)
                for r in conn.execute(
                    "SELECT * FROM entries WHERE status='active'"
                ).fetchall()
            }
            restored = 0
            for eid, target in wanted.items():
                cur = current.get(eid)
                if cur and all(cur.get(k) == v for k, v in target.items()):
                    continue
                before = dict(cur) if cur else None
                conn.execute(
                    "INSERT INTO entries(id,kind,scope,session_id,title,body,weight,"
                    "pinned,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(id) DO UPDATE SET title=excluded.title,"
                    " body=excluded.body, weight=excluded.weight,"
                    " pinned=excluded.pinned, status='active',"
                    " updated_at=excluded.updated_at",
                    (
                        eid, target["kind"], target["scope"],
                        target.get("session_id"), target["title"], target["body"],
                        target["weight"], target["pinned"], "active",
                        target["created_at"], time.time(),
                    ),
                )
                self._record_version(conn, eid, "update", before, target,
                                     evidence or f"restore snapshot {snapshot_id}",
                                     "restore_snapshot")
                restored += 1
            # Entries created after the snapshot get soft-deleted.
            for eid, cur in current.items():
                if eid not in wanted:
                    conn.execute(
                        "UPDATE entries SET status='deleted', updated_at=? WHERE id=?",
                        (time.time(), eid),
                    )
                    self._record_version(conn, eid, "delete", dict(cur),
                                         {**cur, "status": "deleted"},
                                         evidence or f"restore snapshot {snapshot_id}",
                                         "restore_snapshot")
        return {"restored": restored, "snapshot_id": int(snapshot_id)}

    def stats(self) -> Dict[str, Any]:
        with self._lock_wrap():
            n = self._conn.execute(
                "SELECT COUNT(*) c FROM entries WHERE status='active'"
            ).fetchone()["c"]
            total = self._conn.execute(
                "SELECT COALESCE(SUM(LENGTH(body)),0) s FROM entries "
                "WHERE status='active'"
            ).fetchone()["s"]
            nv = self._conn.execute("SELECT COUNT(*) c FROM versions").fetchone()["c"]
            ns = self._conn.execute("SELECT COUNT(*) c FROM snapshots").fetchone()["c"]
        return {
            "active_entries": n,
            "body_bytes": int(total),
            "budget_bytes": self._budget,
            "budget_used_pct": round(100.0 * total / max(1, self._budget), 2),
            "versions": nv,
            "snapshots": ns,
            "db_path": str(self._path),
            "fts5": bool(getattr(self, "_fts_enabled", False)),
        }

    def close(self) -> None:
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:
            pass

    # ── helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _get_active(conn: sqlite3.Connection, entry_id: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM entries WHERE id=? AND status='active'", (entry_id,)
        ).fetchone()
        if row is None:
            raise LedgerError(f"no active entry {entry_id}")
        return row

    def _enforce_budget(self, conn: sqlite3.Connection, *, incoming: int) -> None:
        used = conn.execute(
            "SELECT COALESCE(SUM(LENGTH(body)),0) s FROM entries WHERE status='active'"
        ).fetchone()["s"] or 0
        shortfall = used + incoming - self._budget
        if shortfall <= 0:
            return
        # Evict lowest-value unpinned actives until the SHORTFALL is covered
        # (not `incoming` — over-eviction would destroy good state).
        candidates = conn.execute(
            "SELECT id, LENGTH(body) blen FROM entries WHERE status='active' "
            "AND pinned=0 ORDER BY weight ASC, updated_at ASC"
        ).fetchall()
        freed = 0
        evicted = []
        for cand in candidates:
            if freed >= shortfall:
                break
            freed += cand["blen"] or 0
            evicted.append(cand["id"])
        if freed < shortfall:
            raise LedgerError(
                f"memory budget exhausted ({used}+{incoming} > {self._budget} bytes); "
                f"free space by deleting low-weight entries or raising ariadne.memory.budget_mb"
            )
        for eid in evicted:
            row = conn.execute("SELECT * FROM entries WHERE id=?", (eid,)).fetchone()
            conn.execute(
                "UPDATE entries SET status='evicted', updated_at=? WHERE id=?",
                (time.time(), eid),
            )
            self._record_version(conn, eid, "delete", dict(row),
                                 {"status": "evicted"},
                                 "budget eviction (lowest weight, oldest)", "budget")
