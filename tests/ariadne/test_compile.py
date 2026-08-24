"""Compiler + plan patching tests (no model, no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ariadne_runtime.compile import compile_build, patch_plan, reset_downstream
from ariadne_runtime.guide_engine import WEB_APP_MILESTONES
from plugins.context_graph.tasks import TaskStore


@pytest.fixture()
def store(tmp_path):
    s = TaskStore(tmp_path / "t.db")
    yield s
    s.close()


def _ids(store, pid):
    return [t["id"] for t in store.plan(pid)["tasks"]]


def _states(store, pid):
    return {t["id"]: t["state"] for t in store.plan(pid)["tasks"]}


class TestCompile:
    def test_web_app_milestones_compile(self):
        out = compile_build(
            [m for m in WEB_APP_MILESTONES if m.get("kind") == "run"],
            {"core-action-label": "habits"})
        assert out["ok"] is True
        ids = [s["id"] for s in out["tasks"]]
        assert any(i.startswith("m1-") for i in ids)
        assert any(i.startswith("m2-") for i in ids)
        assert any(i.startswith("checkpoint-m") for i in ids)
        # slots filled from context
        m1 = [s for s in out["tasks"] if s["id"] == "m1-plan-schema"][0]
        assert "habits" in json.dumps(m1["payload"])
        import re as _re

        flat = str(out["tasks"])
        assert not _re.search(r"\{\{\s*[A-Z_][A-Z0-9_]*\s*\}\}", flat)

    def test_checkpoint_chains_milestones(self):
        out = compile_build(
            [m for m in WEB_APP_MILESTONES if m.get("kind") == "run"], {})
        tasks = {s["id"]: s for s in out["tasks"]}
        cp1 = tasks["checkpoint-m1"]
        # every m2 task must trace back (directly or transitively) to cp1
        m2 = [s for s in out["tasks"] if s["id"].startswith("m2-")]
        assert m2, "expected m2 tasks"
        dep_map = {s["id"]: set(s.get("depends_on") or []) for s in out["tasks"]}

        def reaches(tid, target):
            if tid == target:
                return True
            return any(reaches(d, target) for d in dep_map.get(tid, ()))

        assert all(reaches(s["id"], "checkpoint-m1") for s in m2)
        # and checkpoint-m1 depends on all of m1
        m1_ids = [s["id"] for s in out["tasks"]
                  if s["id"].startswith("m1-")]
        assert set(dep_map["checkpoint-m1"]) == set(m1_ids)

    def test_missing_slots_fail_loud(self):
        ms = [{"kind": "run", "id": "s", "title": "S",
               "template": "watch-alert",
               "slot_map": {}}]
        out = compile_build(ms, {})  # TARGET_URL has default -> ok
        assert out["ok"] is True


class TestPatchPlan:
    def _seed(self, store):
        pid = store.create_plan("demo", [
            {"id": "a", "kind": "note", "payload": {"v": 1}},
            {"id": "b", "kind": "note", "depends_on": ["a"],
             "payload": {"v": 2}},
            {"id": "c", "kind": "note", "depends_on": ["b"],
             "payload": {"v": 3}},
        ])
        return pid

    def test_leaf_change_resets_only_downstream_done(self, store):
        pid = self._seed(store)
        a_id = pid + "-a"
        b_id = pid + "-b"
        c_id = pid + "-c"
        store.mark_running(a_id)
        store.mark_done(a_id, {})
        store.mark_running(b_id)
        store.mark_done(b_id, {})
        # edit only 'c'
        report = patch_plan(store, pid, [
            {"id": "a", "kind": "note", "payload": {"v": 1}},
            {"id": "b", "kind": "note", "depends_on": ["a"],
             "payload": {"v": 2}},
            {"id": "c", "kind": "note", "depends_on": ["b"],
             "payload": {"v": 42}},
        ])
        states = _states(store, pid)
        assert report["kept"] == [a_id, b_id]
        assert c_id in report["reset"]
        assert states[c_id] == "pending"
        assert states[a_id] == "done" and states[b_id] == "done"

    def test_root_change_invalidates_all_done_descendants(self, store):
        pid = self._seed(store)
        a_id = pid + "-a"
        b_id = pid + "-b"
        c_id = pid + "-c"
        for tid in (a_id, b_id, c_id):
            store.mark_running(tid)
            store.mark_done(tid, None)
        report = patch_plan(store, pid, [
            {"id": "a", "kind": "note", "payload": {"v": 999}},  # changed
            {"id": "b", "kind": "note", "depends_on": ["a"],
             "payload": {"v": 2}},
            {"id": "c", "kind": "note", "depends_on": ["b"],
             "payload": {"v": 3}},
        ])
        states = _states(store, pid)
        assert set(report["reset"]) >= {a_id, b_id, c_id}
        assert all(states[t] == "pending" for t in (a_id, b_id, c_id))

    def test_insert_and_drop(self, store):
        pid = self._seed(store)
        report = patch_plan(store, pid, [
            {"id": "a", "kind": "note", "payload": {"v": 1}},
            {"id": "b", "kind": "note", "depends_on": ["a"],
             "payload": {"v": 2}},
            {"id": "c", "kind": "note", "depends_on": ["b"],
             "payload": {"v": 3}},
            {"id": "d", "kind": "note", "depends_on": ["c"],
             "payload": {"v": 4}},                      # inserted
        ])
        assert report["inserted"] == [pid + "-d"]
        # now drop 'c' and 'd' from the spec
        report2 = patch_plan(store, pid, [
            {"id": "a", "kind": "note", "payload": {"v": 1}},
            {"id": "b", "kind": "note", "depends_on": ["a"],
             "payload": {"v": 2}},
        ])
        states = _states(store, pid)
        assert states[pid + "-c"] == "skipped"

    def test_duplicate_ids_rejected(self, store):
        pid = self._seed(store)
        out = patch_plan(store, pid, [
            {"id": "x", "kind": "note"},
            {"id": "x", "kind": "note"},
        ])
        assert out["ok"] is False and "duplicate" in out["error"]

    def test_reset_downstream_helper(self, store):
        pid = self._seed(store)
        reset = reset_downstream(store, pid, pid + "-a")
        assert set(reset) == {pid + "-b", pid + "-c"}
