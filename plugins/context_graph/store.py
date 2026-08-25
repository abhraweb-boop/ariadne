"""Ariadne context-graph store -- nodes/edges SQLite with BFS subgraph recall.

Phase-3 substrate: every tool touch becomes graph state; the waterfall loader
recalls ranked subgraphs. Idempotent upserts; edge weight = recency x frequency.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id         TEXT PRIMARY KEY,
    type       TEXT NOT NULL,
    key        TEXT NOT NULL,
    title      TEXT NOT NULL DEFAULT '',
    meta       TEXT NOT NULL DEFAULT '{}',
    first_seen REAL NOT NULL,
    last_seen  REAL NOT NULL,
    touches    INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);

CREATE TABLE IF NOT EXISTS edges (
    src       TEXT NOT NULL,
    rel       TEXT NOT NULL,
    dst       TEXT NOT NULL,
    weight    REAL NOT NULL DEFAULT 1.0,
    last_seen REAL NOT NULL,
    PRIMARY KEY (src, rel, dst)
);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
"""


def node_id(ntype: str, key: str) -> str:
    return f"{ntype}:{key}"


class GraphStore:
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

    # ── recording ────────────────────────────────────────────────────────
    def touch(
        self,
        ntype: str,
        key: str,
        *,
        title: str = "",
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Upsert a node; bumps touches + last_seen. Returns node id."""
        nid = node_id(ntype, key)
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO nodes(id,type,key,title,meta,first_seen,last_seen,"
                "touches) VALUES(?,?,?,?,?,?,?,1) "
                "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen,"
                "touches=touches+1,"
                "title=CASE WHEN excluded.title!='' THEN excluded.title "
                "ELSE nodes.title END",
                (nid, ntype, key, title or "", json.dumps(meta or {}), now, now),
            )
            self._conn.commit()
        return nid

    def link(
        self,
        src: str,
        rel: str,
        dst: str,
        *,
        bump: float = 1.0,
    ) -> None:
        """Idempotent edge; repeated links raise weight (capped)."""
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT INTO edges(src,rel,dst,weight,last_seen) VALUES(?,?,?,?,?) "
                "ON CONFLICT(src,rel,dst) DO UPDATE SET "
                "weight=MIN(16.0, edges.weight+?), last_seen=excluded.last_seen",
                (src, rel, dst, bump, now, bump),
            )
            self._conn.commit()

    def record_touch(
        self,
        *,
        session_id: str,
        target_type: str,
        target_key: str,
        title: str = "",
        meta: Optional[Dict[str, Any]] = None,
        rel: str = "touched-by",
    ) -> Tuple[str, str]:
        """Convenience: touch a target node and link it to the session hub."""
        tgt = self.touch(target_type, target_key, title=title, meta=meta)
        sess = self.touch("session", session_id, title=f"session {session_id}")
        self.link(tgt, rel, sess)
        return tgt, sess

    # ── recall ───────────────────────────────────────────────────────────
    def _decay(self, last_seen: float) -> float:
        age_days = max(0.0, (time.time() - last_seen) / 86400.0)
        return 1.0 / (1.0 + age_days)

    def seeds_by_keyword(self, query: str, *, limit: int = 5) -> List[str]:
        # Strip punctuation so prompt tokens like "phase6," or "deploy?" still
        # match node titles (live-gate finding: LIKE missed punctuated seeds).
        words = [
            re.sub(r"[^\w\-./]+", "", w)
            for w in (query or "").split()
        ]
        words = [w for w in words if len(w) >= 3][:8]
        if not words:
            return []
        clauses = " OR ".join("title LIKE ?" for _ in words)
        args = [f"%{w}%" for w in words]
        with self._lock:
            rows = self._conn.execute(
                f"SELECT id FROM nodes WHERE {clauses} "
                "ORDER BY touches DESC, last_seen DESC LIMIT ?",
                [*args, int(limit)],
            ).fetchall()
        return [r["id"] for r in rows]

    def subgraph(
        self,
        seeds: List[str],
        *,
        depth: int = 2,
        limit: int = 12,
    ) -> Dict[str, Any]:
        """BFS from seeds over weighted undirected edges, ranked."""
        if not seeds:
            return {"nodes": [], "edges": []}
        visited: Dict[str, float] = {}
        frontier = list(seeds)
        for nid in seeds:
            visited[nid] = 2.0  # seed bonus
        edge_rows: List[sqlite3.Row] = []
        seen_edges: set = set()
        for _ in range(max(1, depth)):
            if not frontier:
                break
            marks = ",".join("?" for _ in frontier)
            with self._lock:
                rows = self._conn.execute(
                    f"SELECT * FROM edges WHERE src IN ({marks}) "
                    f"OR dst IN ({marks})",
                    [*frontier, *frontier],
                ).fetchall()
            nxt: List[str] = []
            for e in rows:
                ek = (e["src"], e["rel"], e["dst"])
                if ek not in seen_edges:
                    seen_edges.add(ek)
                    edge_rows.append(e)
                score = e["weight"] * self._decay(e["last_seen"])
                for end in (e["src"], e["dst"]):
                    if end not in visited:
                        visited[end] = score
                        nxt.append(end)
                    else:
                        visited[end] = max(visited[end], score)
            frontier = nxt[: limit * 2]
        ranked = sorted(visited, key=lambda n: visited[n], reverse=True)[:limit]
        rset = set(ranked)
        out_edges = [
            dict(e)
            for e in edge_rows
            if e["src"] in rset and e["dst"] in rset
        ]
        with self._lock:
            marks = ",".join("?" for _ in ranked)
            node_rows = (
                self._conn.execute(
                    f"SELECT * FROM nodes WHERE id IN ({marks})", ranked
                ).fetchall()
                if ranked
                else []
            )
        by_score = sorted(
            (dict(n) for n in node_rows),
            key=lambda n: visited.get(n["id"], 0),
            reverse=True,
        )
        return {"nodes": by_score, "edges": out_edges}

    # ── maintenance / introspection ──────────────────────────────────────
    def timeline(self, nid: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM edges WHERE src=? OR dst=? "
                "ORDER BY last_seen DESC LIMIT ?",
                (nid, nid, int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            nn = self._conn.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"]
            ne = self._conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]
            types = {
                r["type"]: r["c"]
                for r in self._conn.execute(
                    "SELECT type, COUNT(*) c FROM nodes GROUP BY type"
                ).fetchall()
            }
        return {"nodes": nn, "edges": ne, "by_type": types,
                "db_path": str(self._path)}

    def prune(self, *, older_than_days: float = 30.0) -> Dict[str, int]:
        cutoff = time.time() - older_than_days * 86400.0
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM nodes WHERE last_seen < ? AND touches <= 1", (cutoff,)
            )
            removed_nodes = cur.rowcount
            cur = self._conn.execute(
                "DELETE FROM edges WHERE last_seen < ?", (cutoff,)
            )
            removed_edges = cur.rowcount
            self._conn.commit()
        return {"nodes": max(0, removed_nodes), "edges": max(0, removed_edges)}

    def export(self, *, limit: int = 100) -> Dict[str, Any]:
        with self._lock:
            nodes = [
                dict(r)
                for r in self._conn.execute(
                    "SELECT * FROM nodes ORDER BY last_seen DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            ]
            edges = [
                dict(r)
                for r in self._conn.execute(
                    "SELECT * FROM edges ORDER BY last_seen DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
            ]
        return {"nodes": nodes, "edges": edges}
