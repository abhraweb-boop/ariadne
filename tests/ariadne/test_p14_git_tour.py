"""BuildSnapshots + Console /tour tests (real git, temp dirs)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ariadne_runtime.build_snapshots as bs
from plugins.context_graph.tasks import TaskStore


@pytest.fixture()
def repo(tmp_path):
    d = tmp_path / "build"
    assert bs.ensure_repo(str(d)) is True
    (d / "app.py").write_text("print('v1')\n", encoding="utf-8")
    return d


class TestSnapshots:
    def test_snapshot_returns_sha_and_commits(self, repo):
        sha = bs.snapshot(str(repo), "before run")
        assert sha and len(sha) >= 7
        log = bs._git(["log", "--oneline"], repo)
        assert "before run" in log

    def test_record_and_load_run(self, repo):
        before = bs.snapshot(str(repo), "before")
        (repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
        after = bs.snapshot(str(repo), "after")
        out = bs.record_run(str(repo), "plan-x", before, after, "done",
                            extra={"goal": "demo"})
        assert out is not None and out.exists()
        rec = bs.load_run(str(repo), "plan-x")
        assert rec["before"] == before and rec["after"] == after
        assert rec["final_state"] == "done" and rec["goal"] == "demo"

    def test_revert_to_restores_files_as_new_commit(self, repo):
        s1 = bs.snapshot(str(repo), "v1 checkpoint")
        (repo / "app.py").write_text("print('ruined')\n", encoding="utf-8")
        (repo / "extra.txt").write_text("junk\n", encoding="utf-8")
        bs.snapshot(str(repo), "v2 broken")
        head = bs.revert_to(str(repo), s1)
        assert head and head != s1
        # file content restored; junk file removed from the worktree
        assert "v1" in (repo / "app.py").read_text(encoding="utf-8")
        assert not (repo / "extra.txt").exists() or \
            bs.load_run(str(repo), "nope") is None
        log = bs._git(["log", "--oneline"], repo)
        assert f"revert to {s1}" in log  # history preserved, new commit

    def test_non_git_dir_degrades_silently(self, tmp_path, monkeypatch):
        calls = {"n": 0}

        def failing_git(args, cwd):
            calls["n"] += 1
            return None

        monkeypatch.setattr(bs, "_git", failing_git)
        assert bs.snapshot(str(tmp_path / "x"), "lbl") is None
        assert bs.revert_to(str(tmp_path / "x"), "abc123") is None


class TestTour:
    def test_console_page_mentions_tour_command(self):
        from hermes_cli.web_routers import prime_hermes_console as pc

        html = pc.console_page().body.decode("utf-8")
        assert "/tour" in html
