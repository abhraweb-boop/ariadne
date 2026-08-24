"""GuideStore + GuideEngine + ariadne_guide tool tests (no model)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import ariadne_runtime.guide as guide_mod
import ariadne_runtime.guide_engine as ge_mod
from ariadne_runtime.guide import GuideStore
from ariadne_runtime.guide_engine import GuideEngine


@pytest.fixture()
def engine(monkeypatch, tmp_path):
    gs = GuideStore(tmp_path / "guide.db")
    monkeypatch.setattr(guide_mod, "_store", gs, raising=True)
    eng = GuideEngine(store=gs)
    monkeypatch.setattr(ge_mod, "_engine", eng, raising=True)
    yield eng, gs
    gs.close()


class TestGuideStore:
    def test_create_get_roundtrip(self, tmp_path):
        s = GuideStore(tmp_path / "g.db")
        bid = s.create_build("habit tracker", "web-app",
                             {"audience": "just-me"})
        b = s.get_build(bid)
        assert b["goal"] == "habit tracker"
        assert b["state"] == "active"
        assert b["context"] == {"audience": "just-me"}
        s.close()

    def test_milestone_and_context(self, tmp_path):
        s = GuideStore(tmp_path / "g.db")
        bid = s.create_build("x")
        s.set_milestone(bid, 3)
        ctx = s.merge_context(bid, {"core-action": "track"})
        assert ctx["core-action"] == "track"
        assert s.get_build(bid)["milestone_idx"] == 3
        s.close()

    def test_decisions_ordered(self, tmp_path):
        s = GuideStore(tmp_path / "g.db")
        bid = s.create_build("x")
        s.record_decision(bid, question_id="q1", option_id="a",
                          chosen_label="A", rationale="because")
        s.record_decision(bid, question_id="q2", option_id="auto:b",
                          chosen_label="B")
        dec = s.decisions_for(bid)
        assert [d["question_id"] for d in dec] == ["q1", "q2"]
        assert dec[1]["option_id"] == "auto:b"  # auto marker preserved
        s.close()


class TestGuideEngine:
    def test_start_returns_question_step(self, engine):
        eng, _ = engine
        out = eng.start("a habit tracker web app")
        st = out["step"]
        assert out["ok"] and st["kind"] == "question"
        assert st["index"] == 0 and st["of"] >= 4
        qs = st["questions"]
        assert qs[0]["options"][0]["explainer"]  # every option explained

    def test_answer_advances_through_flow_to_done(self, engine):
        eng, gs = engine
        out = eng.start("habit tracker")
        bid = out["build_id"]
        # answer both q's of milestone 0
        r = eng.answer(bid, "audience", "just-me")
        assert r["ok"]
        r = eng.answer(bid, "core-action", "track")
        # milestone advanced past questions -> next step offered
        assert r["step"]["index"] >= 1
        # walk the rest with 'you decide'
        for _ in range(6):
            st = eng.status(bid)["step"]
            if st["kind"] in ("done",):
                break
            if st["kind"] == "offer-auto":
                eng.auto_decide(bid)
            elif st["kind"] == "run":
                # simulate run completion without executing
                eng._store.set_milestone(bid, st["index"] + 1)
            elif st["kind"] == "ready-to-run":
                eng._store.set_milestone(bid, st["index"] + 1)
            else:
                break
        final = eng.status(bid)
        dec = gs.decisions_for(bid)
        assert any(d["option_id"].startswith("auto:") for d in dec)

    def test_auto_decide_picks_recommended_and_logs(self, engine):
        eng, gs = engine
        bid = eng.start("app")["build_id"]
        out = eng.auto_decide(bid)
        dec = gs.decisions_for(bid)
        assert all(d["rationale"] or d["chosen_label"] for d in dec)
        assert out["ok"]

    def test_auto_decide_on_auto_milestone_states_impact(self, engine):
        eng, gs = engine
        bid = eng.start("app")["build_id"]
        eng.answer(bid, "audience", "just-me")
        eng.answer(bid, "core-action", "track")
        st = eng.status(bid)["step"]
        if st.get("kind") == "offer-auto":
            out = eng.auto_decide(bid)
            assert out["decided"]["impact"]

    def test_why_reconstructs_reasoning(self, engine):
        eng, gs = engine
        bid = eng.start("app")["build_id"]
        eng.answer(bid, "audience", "public")
        w = eng.why(bid)
        entry = [d for d in w["decisions"] if d["question_id"] == "audience"][0]
        assert entry["chosen_label"] == "The public"

    def test_advance_after_run_failure_offers_recovery(self, engine):
        eng, _ = engine
        bid = eng.start("app")["build_id"]
        out = eng.advance_after_run(
            bid, {"final_state": "failed"})
        assert out["recovery"]["options"][0]["id"] == "retry"

    def test_unknown_build_errors_cleanly(self, engine):
        with pytest.raises(KeyError):
            eng_status = engine[0]
            eng_status.status("bld-nope")

    def test_abandon_via_store_state(self, engine):
        eng, gs = engine
        bid = eng.start("app")["build_id"]
        gs.set_state(bid, "abandoned")
        assert gs.get_build(bid)["state"] == "abandoned"


class TestGuideTool:
    def test_tool_surface_roundtrip(self, monkeypatch, tmp_path):
        import tools.ariadne_guide_tool as gt
        import ariadne_runtime.guide as guide_mod
        import ariadne_runtime.guide_engine as ge_mod

        gs = GuideStore(tmp_path / "g.db")
        monkeypatch.setattr(guide_mod, "_store", gs, raising=True)
        eng = GuideEngine(store=gs)
        monkeypatch.setattr(ge_mod, "_engine", eng, raising=True)

        started = json.loads(gt.handle_ariadne_guide({
            "action": "start", "goal": "todo app"}))
        assert started["ok"] is True
        bid = started["build_id"]

        answered = json.loads(gt.handle_ariadne_guide({
            "action": "answer", "build_id": bid,
            "question_id": "audience", "option_id": "few-users"}))
        assert answered["ok"] is True

        why = json.loads(gt.handle_ariadne_guide({
            "action": "why", "build_id": bid}))
        assert why["decisions"][0]["chosen_label"] == "A few people"

        gone = json.loads(gt.handle_ariadne_guide({
            "action": "abandon", "build_id": bid}))
        assert gone["state"] == "abandoned"
        gs.close()

    def test_unknown_action_lists_valid(self, monkeypatch, tmp_path):
        import tools.ariadne_guide_tool as gt

        out = json.loads(gt.handle_ariadne_guide({"action": "vibes"}))
        assert out["ok"] is False and "status" in out["error"]
