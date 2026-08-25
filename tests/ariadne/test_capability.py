"""Capability acquisition + inspiration scoring tests (no network)."""

from __future__ import annotations

import pytest

from ariadne_runtime.capability import (
    extract_manifest,
    score_inspiration,
    score_skill_candidate,
    select_capabilities,
    tier_of,
)


class TestManifest:
    def test_extracts_techs_and_domains_from_specs(self):
        specs = [
            {"kind": "prime",
             "payload": {"prompt": "build a fastapi rest api with sqlite "
                                   "and pytest tests"}},
            {"kind": "tool", "payload": {"tool": "web_extract"}},
        ]
        m = extract_manifest(specs)
        assert "fastapi" in m["technologies"]
        assert {"api", "database", "testing"} <= set(m["domains"])

    def test_scout_technologies_flow_into_manifest(self):
        specs = [{"kind": "scout",
                  "payload": {"technologies": ["sqlmodel", "postgres"]}}]
        m = extract_manifest(specs)
        assert "sqlmodel" in m["technologies"]
        assert "database" in m["domains"]


class TestSkillSelection:
    def test_specific_beats_generic(self):
        needed = ["testing"]
        generic = {
            "name": "do anything helper",
            "description": "a universal assistant for all tasks ever",
            "domains": ["testing", "auth", "deploy"],
            "has_steps": True,
        }
        specific = {
            "name": "pytest fixtures and parametrize",
            "description": "pytest patterns: fixtures, parametrize, "
                           "coverage for testing python projects",
            "domains": ["testing"],
            "has_steps": True, "references": True, "examples": True,
        }
        out = select_capabilities([generic, specific], needed)
        ids = [s["id"] for s in out["selected"]]
        assert specific["name"] in ids
        # generic either rejected as overlap or scored lower
        if generic["name"] not in ids:
            assert any(r["id"] == generic["name"]
                       and r["reason"] == "skipped_overlap"
                       for r in out["rejected"])

    def test_overlap_rejected_not_merged(self):
        needed = ["auth"]
        a = {"name": "jwt auth guide",
             "description": "jwt oauth login session auth patterns",
             "domains": ["auth"], "has_steps": True}
        b = {"name": "another jwt auth guide",
             "description": "jwt login auth session patterns again",
             "domains": ["auth"], "has_steps": True}
        out = select_capabilities([a, b], ["auth"])
        assert len(out["selected"]) == 1
        assert out["rejected"][0]["reason"] == "skipped_overlap"

    def test_slop_skill_penalized(self):
        slop = {"name": "🚀 REVOLUTIONARY 10x ultimate coding skill 🚀🚀🚀",
                "description": ("this mind-blowing game-changing skill "
                                "will supercharge everything, insane "
                                "results, secret sauce inside"),
                "domains": ["testing"]}
        clean = {"name": "pytest basics",
                 "description": "pytest testing patterns with coverage",
                 "domains": ["testing"], "has_steps": True,
                 "references": True}
        s1 = score_skill_candidate(slop, ["testing"])
        s2 = score_skill_candidate(clean, ["testing"])
        assert s1["breakdown"]["slop_penalty"] < 0
        assert s1["score"] < s2["score"]

    def test_breakdown_is_transparent(self):
        sc = score_skill_candidate(
            {"name": "fastapi deps",
             "description": "fastapi dependency injection patterns",
             "domains": ["api"], "steps": True}, ["api"])
        assert set(sc["breakdown"]) == {"relevance", "completeness",
                                        "specificity", "slop_penalty"}
        assert abs(sum(v for k, v in sc["breakdown"].items()
                       if k != "slop_penalty") + sc["breakdown"]
                   ["slop_penalty"] - sc["score"]) < 0.5


class TestInspirationScoring:
    def test_craft_outweighs_stars(self):
        hype_star = score_inspiration({
            "name": "SUPER MEGA BOILERPLATE",
            "description": "the ULTIMATE revolutionary starter, insane!! "
                           "game-changing 🚀🚀🚀",
            "url": "https://github.com/x/super-mega",
            "stars": 50_000,
        }, ["fastapi"])
        quiet_craft = score_inspiration({
            "name": "tidy-fastapi-template",
            "description": "a clean fastapi project template",
            "url": "https://github.com/dev/tidy-fastapi-template",
            "stars": 120, "has_tests": True, "has_ci": True,
            "has_license": True, "typed": True,
            "age_days": 60,
        }, ["fastapi"])
        assert quiet_craft["score"] > hype_star["score"]
        assert quiet_craft["tier"] in ("gold", "silver")

    def test_tiers_and_dropping(self):
        assert tier_of(85) == "gold"
        assert tier_of(60) == "silver"
        assert tier_of(40) == "bronze"
        assert tier_of(39.9) == "slop"
        low = score_inspiration({
            "name": "tutorial-copy trash",
            "description": "",
            "url": "", "stars": 3,
        }, [])
        assert low["score"] < 40 and low["tier"] == "slop"

    def test_recency_and_fit_move_scores(self):
        base = {"name": "proj", "description": "fastapi sqlmodel service",
                "url": "https://github.com/a/proj", "stars": 500,
                "has_tests": True}
        fresh = dict(base, age_days=30)
        stale = dict(base, age_days=1500)
        s_new = score_inspiration(fresh, ["fastapi"])["score"]
        s_old = score_inspiration(stale, ["fastapi"])["score"]
        assert s_new > s_old

        on_topic = score_inspiration(base, ["fastapi", "sqlmodel"])["score"]
        off_topic = score_inspiration(base, ["react"])["score"]
        assert on_topic > off_topic

    def test_unknown_age_neutral(self):
        card = {"name": "mystery", "description": "some project",
                "url": ""}
        sc = score_inspiration(card, [])
        assert sc["breakdown"]["recency"] == 6.0


class TestSlopDetector:
    def test_hype_words_each_cost(self):
        from ariadne_runtime.capability import _slop_penalty

        assert _slop_penalty("clean description") == 0.0
        one = _slop_penalty("this is revolutionary")
        three = _slop_penalty("revolutionary game-changing ultimate")
        assert one == -10.0 and three == -30.0
        assert _slop_penalty("x" * 10) >= -40  # capped