"""P14 completion tests: /heals journal + secret-scan gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ariadne_runtime.secret_scan as ss
from plugins.context_graph.tasks import TaskStore


@pytest.fixture()
def store(tmp_path):
    s = TaskStore(tmp_path / "t.db")
    yield s
    s.close()


# ── heal journal ──────────────────────────────────────────────────────────
class TestHealJournal:
    def test_journal_heal_and_get_heals(self):
        from ariadne_runtime import doctor as doc

        doc._HEAL_JOURNAL.clear()
        doc.journal_heal({"task": "t1", "kind": "pip-install",
                          "note": "installed pyzmq", "action": "pip install pyzmq"})
        doc.journal_heal({"task": "t2", "kind": "drift",
                          "note": "flagged DRIFT: built a blog"})
        heals = doc.get_heals()
        assert len(heals) == 2
        assert heals[0]["task"] == "t2"          # newest first
        assert all("at" in h for h in heals)

    def test_journal_capped_at_200(self):
        from ariadne_runtime import doctor as doc

        doc._HEAL_JOURNAL.clear()
        for i in range(230):
            doc.journal_heal({"task": f"t{i}", "note": f"n{i}"})
        assert len(doc._HEAL_JOURNAL) == 200
        # oldest entries were evicted, newest retained
        assert doc.get_heals()[0]["task"] == "t229"

    def test_doctor_log_feeds_process_journal(self):
        from ariadne_runtime import doctor as doc

        doc._HEAL_JOURNAL.clear()
        d = doc.ErrorDoctor()
        d._log({"kind": "test", "note": "hello"})
        assert any(h["note"] == "hello" for h in doc.get_heals())


# ── secret scan ───────────────────────────────────────────────────────────
class TestSecretScan:
    def test_detects_common_key_shapes(self):
        text = ("use key sk-abcdefghijklmnopqrstuvwx and "
                "ghp_" + "a" * 36 + " now")
        labels = {f["label"] for f in ss.scan_text(text)}
        assert "openai-key" in labels or "github-token" in labels

    def test_private_key_block(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."
        assert ss.scan_text(text)[0]["label"] == "private-key-block"

    def test_env_references_not_flagged(self):
        text = "const k = process.env.OPENROUTER_API_KEY;"
        assert ss.scan_text(text) == []

    def test_placeholder_values_not_flagged(self):
        text = 'api_key = "your-api-key-here"'
        assert ss.scan_text(text) == []
        text2 = 'password = "${DB_PASSWORD}"'
        assert ss.scan_text(text2) == []

    def test_real_assigned_secret_flagged(self):
        text = 'api_key = "9f2c74b1aa55e0d3c8b7e6f5a4b3c2d1"'
        findings = ss.scan_text(text)
        assert findings and findings[0]["label"] == "assigned-secret"

    def test_scan_task_payload_walks_nested(self):
        payload = {"prompt": "deploy with token ghp_" + "b" * 36,
                   "args": {"nested": ["xoxb-abcdef123456"]}}
        labels = {f["label"] for f in ss.scan_task_payload(payload)}
        assert "github-token" in labels and "slack-token" in labels


# ── executor gate integration (advisory by default) ───────────────────────
class TestExecutorGate:
    def _plan(self, store, secret_text, ctx=None):
        pid = store.create_plan("leaky plan", [
            {"id": "k", "kind": "note",
             "payload": {"text": secret_text}}])
        if ctx:
            store.set_plan_context(pid, ctx)
        return pid

    def test_advisory_mode_still_runs(self, store):
        from ariadne_runtime.graph_exec import GraphExecutor

        pid = self._plan(store, "key is sk-abcdefghijklmnopqrstuvwx ok")
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "done"

    def test_strict_mode_blocks(self, store, monkeypatch):
        from ariadne_runtime.graph_exec import GraphExecutor
        import plugins.context_graph.tasks as tasks_mod

        monkeypatch.setattr(tasks_mod.TaskStore, "get_plan_context",
                            lambda self, pid: {"secret_scan": "strict"},
                            raising=False)
        pid = self._plan(store,
                         'token = "ghp_' + "c" * 36 + '"')
        summary = GraphExecutor(store, pid).run()
        assert summary["final_state"] == "failed"
        row = store.plan(pid)["tasks"][0]
        assert "secret" in (row["error"] or "").lower()
