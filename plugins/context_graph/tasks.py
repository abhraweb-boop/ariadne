"""Ariadne task graph -- executable DAGs stored alongside the context graph.

Phase-6 substrate: promotes plugins/context_graph from *memory* to *control
flow*. Plans are recorded as task nodes (``task:<id>``) with ``depends-on``
edges in the SAME SQLite database family as GraphStore, so the desktop
/graph panel renders them and the waterfall loader can recall them.

Design contract: docs/architecture-ariadne-phase6.md

State machine (per task):
    pending -> ready -> running -> done
                   ^          |
                   |          v
                   +------- failed  (attempts < max_attempts -> ready)
    any dep failed/skipped -> skipped (cascade)

Supplemental-state rule (Prime parity): task rows never mutate past
conversation context; they are versioned, inspectable rows in graph.db.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

TASK_KINDS = ("kernel", "rlm", "tool", "note", "prime", "scout",
              "gemini", "flo")
TASK_STATES = ("pending", "ready", "running", "done", "failed", "skipped",
               "bypassed")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS plans(
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'draft',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks(
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id),
    kind TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    depends_on TEXT NOT NULL DEFAULT '[]',
    state TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    result TEXT,
    error TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    finished_at REAL
);
CREATE INDEX IF NOT EXISTS idx_tasks_plan ON tasks(plan_id);
CREATE INDEX IF NOT EXISTS idx_plans_state ON plans(state);
CREATE TABLE IF NOT EXISTS plan_context(
    plan_id TEXT PRIMARY KEY REFERENCES plans(id),
    data TEXT NOT NULL DEFAULT '{}'
);
"""

_SLUG_RE = re.compile(r"[^a-z0-9_-]+")
_REF_RE = re.compile(r"\{\{\s*([A-Za-z0-9_\-]+)\.(result|output)\s*\}\}")
_REF_RE_PATTERN = re.compile(
    r"\{\{\s*([A-Za-z0-9_\-]+)\.(result|output)\s*\}\}")


def _slug(s: str) -> str:
    return _SLUG_RE.sub("-", s.strip().lower())[:48] or "task"


class CycleError(ValueError):
    """Plan dependency graph contains a cycle."""


class TaskStore:
    """DAG persistence sharing graph.db with GraphStore."""

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

    # ── plans ─────────────────────────────────────────────────────────────
    def create_plan(self, goal: str, specs: List[Dict[str, Any]]) -> str:
        """Validate + persist a DAG atomically. Returns plan id.

        Task ids are plan-scoped: a spec id ``scan`` becomes
        ``plan-<id>-scan``, and any ``{{scan.result}}`` payload references
        are rewritten to the scoped id so the executor resolves them against
        stored rows. The model keeps writing the short form.
        """
        now = time.time()
        plan_id = f"plan-{uuid.uuid4().hex[:10]}"
        cleaned = self._validate(specs, prefix=plan_id)
        with self._lock:
            self._conn.execute(
                "INSERT INTO plans(id,goal,state,created_at,updated_at) "
                "VALUES(?,?,?,?,?)",
                (plan_id, goal.strip(), "draft", now, now),
            )
            for t in cleaned:
                self._conn.execute(
                    "INSERT INTO tasks(id,plan_id,kind,title,payload,depends_on,"
                    "state,max_attempts,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        t["id"], plan_id, t["kind"], t["title"],
                        json.dumps(t["payload"]), json.dumps(t["depends_on"]),
                        "pending", int(t["max_attempts"]), now,
                    ),
                )
                # Mirror into the shared context graph so /graph renders it.
                self._mirror_node(t["id"], t["title"])
                for dep in t["depends_on"]:
                    self._mirror_edge(dep, t["id"])
            self._conn.commit()
        return plan_id

    def plan(self, plan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM plans WHERE id=?", (plan_id,)
            ).fetchone()
            if row is None:
                return None
            d = dict(row)
            d["tasks"] = [
                dict(r) for r in self._conn.execute(
                    "SELECT * FROM tasks WHERE plan_id=? ORDER BY created_at,id",
                    (plan_id,),
                )
            ]
            return d

    def list_plans(self, *, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                dict(r) for r in self._conn.execute(
                    "SELECT p.*, "
                    "(SELECT COUNT(*) FROM tasks t WHERE t.plan_id=p.id) AS n_tasks, "
                    "(SELECT COUNT(*) FROM tasks t WHERE t.plan_id=p.id "
                    " AND t.state='done') AS n_done "
                    "FROM plans p ORDER BY p.created_at DESC LIMIT ?",
                    (limit,),
                )
            ]

    def set_plan_state(self, plan_id: str, state: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE plans SET state=?, updated_at=? WHERE id=?",
                (state, time.time(), plan_id),
            )
            self._conn.commit()

    def list_plan_tasks(self, plan_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                dict(r) for r in self._conn.execute(
                    "SELECT * FROM tasks WHERE plan_id=? ORDER BY created_at",
                    (plan_id,),
                )
            ]

    def delete_plan(self, plan_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM plans WHERE id=?", (plan_id,))
            self._conn.execute("DELETE FROM tasks WHERE plan_id=?", (plan_id,))
            self._conn.commit()
            return cur.rowcount > 0

    # ── task transitions ─────────────────────────────────────────────────
    def task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            r = self._conn.execute(
                "SELECT * FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            return dict(r) if r else None

    def mark_running(self, task_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET state='running', started_at=?, attempts=attempts+1 "
                "WHERE id=?",
                (time.time(), task_id),
            )
            self._conn.commit()
        self._refresh_mirror(task_id)

    def mark_done(self, task_id: str, result: Any) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET state='done', result=?, error=NULL, finished_at=? "
                "WHERE id=?",
                (json.dumps(result, default=str)[:64_000], time.time(), task_id),
            )
            self._conn.commit()
        self._refresh_mirror(task_id)

    def mark_failed(self, task_id: str, error: str) -> str:
        """Record failure; requeue for retry if attempts remain.

        Returns the new state: 'ready' (will retry) or 'failed' (terminal).
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT attempts, max_attempts FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError(task_id)
            retry = row["attempts"] < row["max_attempts"]
            new_state = "ready" if retry else "failed"
            self._conn.execute(
                "UPDATE tasks SET state=?, error=?, finished_at=? WHERE id=?",
                (new_state, error[:4000], time.time(), task_id),
            )
            self._conn.commit()
        self._refresh_mirror(task_id)
        return new_state

    def mark_skipped(self, task_id: str, reason: str = "upstream failure") -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET state='skipped', error=?, finished_at=? WHERE id=?",
                (reason[:500], time.time(), task_id),
            )
            self._conn.commit()
        self._refresh_mirror(task_id)

    def mark_bypassed(self, task_id: str,
                      reason: str = "when-condition false") -> None:
        """Gate not satisfied: skipped-for-this-run WITHOUT cascading.

        Downstream tasks still run (bypassed deps count as satisfied) --
        this is the loop/conditional primitive, distinct from failure.
        """
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET state='bypassed', error=?, finished_at=? WHERE id=?",
                (reason[:500], time.time(), task_id),
            )
            self._conn.commit()
        self._refresh_mirror(task_id)

    def reset_stale_running(self, plan_id: str) -> int:
        """Crash recovery: running -> pending before a resumed run."""
        with self._lock:
            cur = self._conn.execute(
                "UPDATE tasks SET state='pending', started_at=NULL "
                "WHERE plan_id=? AND state='running'",
                (plan_id,),
            )
            self._conn.commit()
            return cur.rowcount

    def reset_task(self, task_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "UPDATE tasks SET state='pending', attempts=0, result=NULL, "
                "error=NULL, started_at=NULL, finished_at=NULL WHERE id=?",
                (task_id,),
            )
            self._conn.commit()
            ok = cur.rowcount > 0
        if ok:
            self._refresh_mirror(task_id)
        return ok

    def insert_task(self, plan_id: str, spec: Dict[str, Any]) -> str:
        """Insert one additional task into an EXISTING plan (Phase 10).

        Id is scoped under plan_id like create_plan; deps must reference
        tasks already in that plan (or the new task's own id).
        Returns the scoped task id.
        """
        now = time.time()
        cleaned = self._validate([spec], prefix=plan_id)
        t = cleaned[0]
        with self._lock:
            self._conn.execute(
                "INSERT INTO tasks(id,plan_id,kind,title,payload,depends_on,"
                "state,max_attempts,created_at) VALUES(?,?,?,?,?,?,'pending',"
                "?,?)",
                (t["id"], plan_id, t["kind"], t["title"],
                 json.dumps(t["payload"]), json.dumps(t["depends_on"]),
                 int(t["max_attempts"]), now))
            self._conn.commit()
        try:
            self._mirror_node(t["id"], t["title"])
        except Exception:
            pass
        return t["id"]

    def set_plan_context(self, plan_id: str, data: Dict[str, Any]) -> None:
        """Store per-plan execution context (e.g. {"secret_scan": "strict"})."""
        with self._lock:
            self._conn.execute(
                "INSERT INTO plan_context(plan_id, data) VALUES(?, ?) "
                "ON CONFLICT(plan_id) DO UPDATE SET data=excluded.data",
                (plan_id, json.dumps(data or {}, default=str)))
            self._conn.commit()

    def get_plan_context(self, plan_id: str) -> Dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM plan_context WHERE plan_id=?",
                (plan_id,)).fetchone()
        try:
            return json.loads(row["data"]) if row else {}
        except Exception:
            return {}

    def rename_task(self, task_id: str, title: str) -> None:
        """In-place title update -- never triggers a rebuild."""
        with self._lock:
            self._conn.execute(
                "UPDATE tasks SET title=? WHERE id=?",
                (title.strip()[:120], task_id))
            self._conn.commit()
        self._refresh_mirror(task_id)

    def mark_failed_terminal(self, task_id: str, error: str) -> None:
        """Fail WITHOUT offering a retry (permanent-class errors, P14).

        Attempts are pinned to max_attempts so mark_failed's retry logic
        cannot resurrect the node.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT max_attempts FROM tasks WHERE id=?",
                (task_id,)).fetchone()
            cap = int(row["max_attempts"]) if row else 1
            self._conn.execute(
                "UPDATE tasks SET state='failed', attempts=?, error=?, "
                "finished_at=? WHERE id=?",
                (cap, (error or "")[:500], time.time(), task_id))
            self._conn.commit()
        self._refresh_mirror(task_id)

    def insert_task(self, plan_id: str, spec: Dict[str, Any],
                    *, scope: bool = True) -> str:
        """Insert one additional task into an EXISTING plan (Phase 10).

        Id is scoped under plan_id unless scope=False (caller already
        normalized). Deps must reference tasks in that plan.
        Returns the scoped task id.
        """
        kind = str(spec.get("kind") or "note").lower()
        if kind not in TASK_KINDS:
            raise ValueError(f"insert_task: bad kind {kind!r}")
        base = _slug(str(spec.get("id") or spec.get("title") or kind))
        nid = f"{plan_id}-{base}" if scope else str(spec.get("id"))
        title = str(spec.get("title") or "").strip() or f"{kind}: {base}"
        raw_deps = [str(d) for d in (spec.get("depends_on") or [])]
        deps = []
        for d in raw_deps:
            if scope and not d.startswith(plan_id + "-"):
                d = f"{plan_id}-{d}"
            deps.append(d)
        with self._lock:
            for d in deps:
                row = self._conn.execute(
                    "SELECT 1 FROM tasks WHERE id=?", (d,)).fetchone()
                if row is None and d != nid:
                    raise ValueError(
                        f"insert_task({nid}): unknown dependency {d}")
            self._conn.execute(
                "INSERT INTO tasks(id,plan_id,kind,title,payload,depends_on,"
                "state,max_attempts,created_at) VALUES(?,?,?,?,?,?,'pending',"
                "?,?)",
                (nid, plan_id, kind, title,
                 json.dumps(spec.get("payload") or {}, default=str),
                 json.dumps(deps),
                 max(1, min(5, int(spec.get("max_attempts") or 1))), time.time()))
            self._conn.commit()
        try:
            self._mirror_node(nid, title)
        except Exception:
            pass
        return nid

    def ready_tasks(self, plan_id: str) -> List[Dict[str, Any]]:
        """Tasks runnable now: deps all done OR bypassed (gate-skip is ok)."""
        tasks = {
            t["id"]: t for t in self.plan(plan_id)["tasks"]
        }
        out = []
        for t in tasks.values():
            if t["state"] != "pending" and t["state"] != "ready":
                continue
            deps = json.loads(t["depends_on"])
            if all(tasks[d]["state"] in ("done", "bypassed") for d in deps):
                out.append(t)
        return out

    def cascade_skip(self, plan_id: str) -> List[str]:
        """Skip every task transitively depending on a failed/skipped task.

        Bypassed deps do NOT trigger skipping -- bypass is a conditional,
        not a failure.
        """
        tasks = {t["id"]: t for t in self.plan(plan_id)["tasks"]}
        skipped: List[str] = []
        changed = True
        while changed:
            changed = False
            for t in tasks.values():
                if t["state"] in ("done", "failed", "skipped", "running",
                                  "bypassed"):
                    continue
                deps = json.loads(t["depends_on"])
                bad = [d for d in deps
                       if tasks.get(d, {}).get("state") in ("failed", "skipped")]
                if bad:
                    self.mark_skipped(t["id"], f"upstream {','.join(bad)} failed")
                    tasks[t["id"]]["state"] = "skipped"
                    skipped.append(t["id"])
                    changed = True
        return skipped

    def plan_summary(self, plan_id: str) -> Dict[str, Any]:
        p = self.plan(plan_id)
        if p is None:
            return {"ok": False, "error": f"unknown plan {plan_id}"}
        if p["state"] == "draft":
            return {"ok": True, "plan_id": plan_id, "goal": p["goal"],
                    "states": {"draft": len(p["tasks"])},
                    "plan_state": "draft"}
        counts: Dict[str, int] = {}
        for t in p["tasks"]:
            counts[t["state"]] = counts.get(t["state"], 0) + 1
        active = [t for t in p["tasks"]
                  if t["state"] in ("pending", "ready", "running")]
        if active:
            plan_state = "running"
        elif not p["tasks"]:
            plan_state = "empty"
        elif counts.get("failed"):
            plan_state = "failed"
        elif counts.get("skipped"):
            plan_state = "partial"
        else:
            plan_state = "done"
        return {
            "ok": True, "plan_id": plan_id, "goal": p["goal"],
            "states": counts,
            "blocked": [t["id"] for t in active],
            "plan_state": plan_state,
        }

    # ── artifact passing ─────────────────────────────────────────────────
    @staticmethod
    def resolve_refs(payload: Dict[str, Any],
                     results: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute {{task_id.result}} refs with upstream outputs."""
        def sub(obj: Any) -> Any:
            if isinstance(obj, str):
                m = _REF_RE.fullmatch(obj.strip())
                if m:
                    tid, field = m.group(1), m.group(2)
                    if tid not in results:
                        raise KeyError(
                            f"unresolved reference {{{{{tid}.result}}}} "
                            f"(upstream not done)")
                    return results[tid]
                return _REF_RE.sub(
                    lambda mm: json.dumps(results.get(mm.group(1), mm.group(0)),
                                          default=str),
                    obj)
            if isinstance(obj, dict):
                return {k: sub(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [sub(v) for v in obj]
            return obj

        return sub(payload)

    # ── validation ───────────────────────────────────────────────────────
    def _validate(self, specs: List[Dict[str, Any]],
                  prefix: str) -> List[Dict[str, Any]]:
        """Validate + namespace ids under ``prefix`` and rewrite refs."""
        seen: Dict[str, int] = {}
        cleaned: List[Dict[str, Any]] = []
        for i, s in enumerate(specs):
            kind = str(s.get("kind") or "").lower()
            if kind not in TASK_KINDS:
                raise ValueError(
                    f"task[{i}]: kind must be one of {TASK_KINDS}, got {kind!r}")
            title = str(s.get("title") or f"{kind} task {i}").strip()[:120]
            base = _slug(str(s.get("id") or title))
            nid = base
            n = seen.get(base, 0)
            if n:
                nid = f"{base}-{n}"
            seen[base] = n + 1
            scoped = f"{prefix}-{nid}"
            deps = [str(d) for d in (s.get("depends_on") or [])]
            scoped_deps = [f"{prefix}-{d}" for d in deps]
            payload = dict(s.get("payload") or {})
            # rewrite {{short.result}} atom refs to the scoped id
            scoped_bases = {f"seen-{base}" for base in seen}

            def _rewrite_ref(m: "re.Match[str]") -> str:
                ref = m.group(1)
                if f"seen-{ref}" in scoped_bases:
                    return f"{{{{{prefix}-{ref}.{m.group(2)}}}}}"
                return m.group(0)

            patched = re.sub(_REF_RE_PATTERN, _rewrite_ref,
                             json.dumps(payload, default=str))
            payload = json.loads(patched)
            cleaned.append({
                "id": scoped, "kind": kind, "title": title,
                "payload": payload,
                "depends_on": scoped_deps,
                "max_attempts": max(1, min(5, int(s.get("max_attempts") or 1))),
            })
        ids = {t["id"] for t in cleaned}
        for t in cleaned:
            unknown = [d for d in t["depends_on"] if d not in ids]
            if unknown:
                raise ValueError(
                    f"task '{t['id']}': unknown dependencies {unknown}")
        self._assert_acyclic(cleaned)
        return cleaned

    @staticmethod
    def _assert_acyclic(cleaned: List[Dict[str, Any]]) -> None:
        deps = {t["id"]: set(t["depends_on"]) for t in cleaned}
        resolved: set = set()
        while deps:
            ready = [n for n, ds in deps.items() if ds <= resolved]
            if not ready:
                raise CycleError(
                    f"dependency cycle among: {sorted(deps)}")
            for n in ready:
                del deps[n]
            resolved |= set(ready)

    # ── mirror into the shared context graph (/graph rendering) ─────────
    def _graph_store(self):
        from plugins.context_graph import get_store

        return get_store()

    def _mirror_node(self, task_id: str, title: str) -> None:
        try:
            self._graph_store().touch(
                "task", task_id, title=title or task_id,
                meta={"executable": True})
        except Exception:
            pass

    def _mirror_edge(self, src_task: str, dst_task: str) -> None:
        try:
            self._graph_store().link(
                f"task:{src_task}", "blocks", f"task:{dst_task}")
        except Exception:
            pass

    def _refresh_mirror(self, task_id: str) -> None:
        try:
            t = self.task(task_id)
            if t:
                self._graph_store().touch(
                    "task", task_id, title=t["title"],
                    meta={"state": t["state"]})
        except Exception:
            pass
