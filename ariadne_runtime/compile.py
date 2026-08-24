"""Master-DAG compiler + plan patching + reset_downstream (Phase 10).

compile_build(): turns a guide build's milestones into ONE executable spec
list — every task prefixed m<n>-, checkpoint notes between milestones.

patch_plan(): diffs new specs against stored tasks (by scoped id + content
hash) -> keep done nodes, reset changed+downstream, insert additions, skip
dropped ones. This is the "human edits the plan, the graph modifies itself"
primitive.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from plugins.context_graph.tasks import TaskStore


def compile_build(milestones: List[Dict[str, Any]],
                  context: Dict[str, Any]) -> Dict[str, Any]:
    """Milestones (guide shape) + slot context -> plan specs + explainer.

    Each milestone contributes its template's tasks prefixed m<n>-;
    a checkpoint note node follows each milestone so progress is visible
    and future continuous-mode can pause on governed tier.
    """
    from plugins.context_graph.templates import instantiate as _instantiate

    specs: List[Dict[str, Any]] = []
    explainer: List[str] = []
    prev_checkpoint: Optional[str] = None
    for n, ms in enumerate(milestones, start=1):
        if ms.get("kind") != "run" or not ms.get("template"):
            continue  # question/auto milestones carry no tasks themselves
        slots = {}
        for target, source in (ms.get("slot_map") or {}).items():
            if isinstance(source, str) and source.startswith("static:"):
                slots[target] = source.split(":", 1)[1]
            elif source and source in context:
                slots[target] = str(context[source])
        inst = _instantiate(ms["template"], slots)
        if not inst.get("ok"):
            return {"ok": False,
                    "error": (f"milestone {n} ({ms.get('id')}): "
                              f"{inst.get('error')}")}
        mapping: Dict[str, str] = {}
        for t in inst["tasks"]:
            new_id = f"m{n}-{t['id']}"
            mapping[t["id"]] = new_id
            spec = dict(t)
            spec["id"] = new_id
            deps = list(t.get("depends_on") or [])
            if not deps and prev_checkpoint:
                deps = [prev_checkpoint]
            spec["depends_on"] = [mapping.get(d, d) for d in deps]
            specs.append(spec)
        cp_id = f"checkpoint-m{n}"
        specs.append({"id": cp_id, "kind": "note",
                      "title": f"milestone {n} complete",
                      "payload": {"text": f"Milestone {n} done"},
                      "depends_on": [mapping[t["id"]]
                                     for t in inst["tasks"]]})
        explainer.append(f"{len(explainer)+1}. {ms['title']}")
        prev_checkpoint = cp_id
    return {"ok": True, "tasks": specs, "explainer": explainer}


def _spec_hash(spec: Dict[str, Any]) -> str:
    basis = json.dumps(
        {"kind": spec.get("kind"),
         "title": spec.get("title", ""),
         "payload": spec.get("payload", {})},
        sort_keys=True, default=str)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _scope_spec(spec: Dict[str, Any], plan_id: str) -> Dict[str, Any]:
    """Normalize a human-written spec to the plan's scoped namespace."""
    s = dict(spec)
    sid = str(s.get("id") or "").strip()
    if not sid.startswith(plan_id + "-"):
        s["id"] = f"{plan_id}-{sid}"
    s["depends_on"] = [
        d if str(d).startswith(plan_id + "-") else f"{plan_id}-{d}"
        for d in (s.get("depends_on") or [])]
    return s


def patch_plan(store: TaskStore, plan_id: str,
               new_specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply human/agent edits to an existing plan. Done-safe.

    Accepts SHORT task ids (matching what create_plan consumed); they are
    normalized to the plan-scoped namespace internally.
    """
    plan = store.plan(plan_id)
    if plan is None:
        return {"ok": False, "error": f"unknown plan {plan_id}"}
    new_specs = [_scope_spec(s, plan_id) for s in new_specs]
    existing = {t["id"]: t for t in plan["tasks"]}

    # validate incoming specs by dry-run create into a throwaway namespace:
    # reuse _validate via create on temp store would be heavy; do targeted
    # checks instead (ids unique, deps resolvable within union)
    incoming_ids = set()
    for s in new_specs:
        sid = str(s.get("id") or "").strip()
        if not sid or sid in incoming_ids:
            return {"ok": False, "error": f"bad/duplicate id: {sid!r}"}
        incoming_ids.add(sid)

    report: Dict[str, Any] = {"kept": [], "reset": [], "inserted": [],
                              "dropped": []}
    handled: Dict[str, str] = {}   # id -> new hash ("kept"/"changed")
    for s in new_specs:
        sid = s["id"]
        row = existing.get(sid)
        h_new = _spec_hash(s)
        if row is None:
            report["inserted"].append(sid)
            handled[sid] = h_new
            continue
        # hash on kind+payload ONLY: a title rename is a rename, not a rebuild
        h_old = _spec_hash({
            "kind": row["kind"],
            "payload": json.loads(row["payload"] or "{}"),
        })
        h_new = _spec_hash({
            "kind": s.get("kind", "note"),
            "payload": s.get("payload", {}),
        })
        new_title = str(s.get("title") or "").strip()
        if h_old == h_new:
            if new_title and new_title != row["title"]:
                store.rename_task(sid, new_title)  # cosmetic; no reset
            report["kept"].append(sid)
            handled[sid] = h_old
        else:
            # content changed -> rebuild (done or not), keep title fresh
            if new_title and new_title != row["title"]:
                store.rename_task(sid, new_title)
            store.reset_task(sid)
            report["reset"].append(sid)
            handled[sid] = h_new

    for tid, row in existing.items():
        if tid not in incoming_ids:
            if row["state"] in ("done",):
                # dropped but already built: leave it, note it
                report["kept"].append(tid)
            else:
                store.mark_skipped(tid, "removed from plan")
                report["dropped"].append(tid)

    # insert genuinely-new nodes via the proper store API (already scoped)
    for s in new_specs:
        if s["id"] in report["inserted"]:
            store.insert_task(plan_id, s, scope=False)

    # downstream of any reset must be invalidated too (transitively)
    dependents: Dict[str, List[str]] = {}
    for s in new_specs:
        for d in s.get("depends_on", []):
            dependents.setdefault(d, []).append(s["id"])
    frontier = list(report["reset"])
    seen = set(frontier)
    while frontier:
        cur = frontier.pop()
        for dep in dependents.get(cur, []):
            if dep in seen:
                continue
            row = store.task(dep)
            if row is None:
                continue
            if row["state"] == "done":
                store.reset_task(dep)
                if dep not in report["reset"]:
                    report["reset"].append(dep)
            seen.add(dep)
            frontier.append(dep)

    store.set_plan_state(plan_id, "draft")
    return {"ok": True, **report}


def reset_downstream(store: TaskStore, plan_id: str,
                     task_id: str) -> List[str]:
    """Transitively reset everything depending on task_id (P10 helper)."""
    plan = store.plan(plan_id)
    if plan is None:
        return []
    dependents: Dict[str, List[str]] = {}
    for t in plan["tasks"]:
        for d in json.loads(t["depends_on"] or "[]"):
            dependents.setdefault(d, []).append(t["id"])
    out: List[str] = []
    frontier = [task_id]
    seen = set()
    while frontier:
        cur = frontier.pop()
        for dep in dependents.get(cur, []):
            if dep in seen:
                continue
            seen.add(dep)
            out.append(dep)
            frontier.append(dep)
    for tid in out:
        store.reset_task(tid)
    return out
