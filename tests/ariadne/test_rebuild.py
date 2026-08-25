"""Visible rebuilds tests (pure filesystem, no model)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ariadne_runtime.rebuild import (
    ARCHIVE_DIR,
    RebuildError,
    RebuildSession,
    require_proof,
)


@pytest.fixture()
def app(tmp_path):
    d = tmp_path / "app"
    (d / "src").mkdir(parents=True)
    (d / "src" / "a.py").write_text("print('a v1')\n")
    (d / "src" / "b.py").write_text("print('b v1')\n")
    (d / "README.md").write_text("# app\n")
    return d


class TestRebuildSession:
    def test_full_cycle_proves_change(self, app):
        s = RebuildSession(app)
        targets = s.map_targets(["src/a.py"])
        out = s.demolish(targets)
        assert out["ok"] is True
        # the void is real: file is GONE, archive holds it
        assert not (app / "src" / "a.py").exists()
        assert (app / ARCHIVE_DIR / out["generation"] / "src"
                / "a.py").read_text() == "print('a v1')\n"

        # rebuild: fresh content
        (app / "src" / "a.py").write_text("print('a v2 WEEKLY')\n")
        proof = s.prove()
        assert proof["ok"] and proof["proof"]["verdict"] == "rebuilt"
        assert proof["proof"]["counts"]["changed"] == 1

    def test_noop_verdict_when_bytes_identical(self, app):
        s = RebuildSession(app)
        targets = s.map_targets(["src/b.py"])
        s.demolish(targets)
        # rebuild writes the SAME bytes back
        (app / "src" / "b.py").write_text("print('b v1')\n")
        proof = s.prove()
        assert proof["proof"]["verdict"] == "noop"
        assert proof["ok"] is False  # honest: not reported as work

    def test_added_files_count_as_rebuild(self, app):
        s = RebuildSession(app)
        s.demolish(s.map_targets(["README.md"]))
        # "rebuild" lands under a NEW name; old one stays gone
        (app / "README2.md").write_text("# new\n")
        proof = s.prove()
        assert proof["proof"]["counts"]["added"] == 1
        assert proof["proof"]["counts"]["missing"] == 1

    def test_missing_rebuilt_file_is_incomplete(self, app):
        s = RebuildSession(app)
        s.demolish(s.map_targets(["src/a.py"]))
        proof = s.prove()  # never rebuilt
        assert proof["proof"]["verdict"] == "incomplete"
        assert proof["ok"] is False

    def test_outside_build_dir_refused(self, tmp_path, app):
        evil = tmp_path / "outside.txt"
        evil.write_text("x")
        s = RebuildSession(app)
        with pytest.raises(RebuildError):
            s.map_targets(["../outside.txt"])

    def test_mass_demolition_requires_confirm(self, app):
        s = RebuildSession(app)
        out = s.demolish(s.map_targets(["src/*.py", "README.md"]),
                         mass_threshold=40)
        assert out.get("needs_confirm") is True and "%" in out["message"]
        # explicit confirmation proceeds
        s2 = RebuildSession(app)
        ok = s2.demolish(s2.map_targets(["src/*.py", "README.md"]),
                         confirm_mass=False)
        assert ok["ok"] is True

    def test_restore_puts_files_back(self, app):
        s = RebuildSession(app)
        s.demolish(s.map_targets(["src/a.py"]))
        restored = s.restore()
        assert "src/a.py" in restored
        assert (app / "src" / "a.py").exists()

    def test_generation_pruning_keeps_five(self, app):
        for _ in range(7):
            s = RebuildSession(app)
            s.demolish(s.map_targets(["src/a.py"]))
            (app / "src" / "a.py").write_text(f"v{_=}" if False else "next\n")
        gens = sorted((app / ARCHIVE_DIR).glob("gen-*"))
        assert len(gens) == 5


class TestClaimGate:
    def test_bare_success_rejected(self):
        out = require_proof({"ok": True, "msg": "changed everything!"})
        assert out["ok"] is False
        assert "proof missing" in out["error"]

    def test_proof_backed_success_passes(self):
        bundle = {"ok": True,
                  "proof": {"verdict": "rebuilt", "counts": {"changed": 2}}}
        assert require_proof(bundle) is bundle

    def test_honest_noop_accepted(self):
        bundle = {"ok": False, "done": True,
                  "proof": {"verdict": "noop",
                            "note": "identical bytes; nothing needed "
                                    "changing"}}
        out = require_proof(bundle)
        assert out["proof"]["verdict"] == "noop"

    def test_unclaimed_response_untouched(self):
        resp = {"ok": False, "error": "worker died"}
        assert require_proof(resp) is resp
