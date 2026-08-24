"""Template library + suggest/instantiate tests (no model)."""

from __future__ import annotations

import pytest

from plugins.context_graph.templates import (
    TEMPLATES,
    all_templates,
    get,
    instantiate,
    slots_for,
    suggest,
)


def test_library_shape():
    ids = [t["id"] for t in TEMPLATES]
    assert len(ids) >= 4 and len(set(ids)) == len(ids)
    for t in TEMPLATES:
        assert t["slots"], t["id"]
        for spec in t["tasks"]:
            assert spec["kind"] in ("note", "prime", "tool", "kernel")
            deps = spec.get("depends_on") or []
            assert all(d in {s["id"] for s in t["tasks"]} for d in deps)


def test_get_and_slots():
    assert get("watch-alert")["name"] == "Watch & Alert loop"
    assert "TARGET_URL" in slots_for("watch-alert")
    assert get("nope") is None


def test_suggest_ranks_watch_alert_for_uptime_goal():
    hits = suggest("watch my api and alert me if it goes down every 30 minutes")
    top = hits[0]
    assert top["template_id"] == "watch-alert"
    assert top["score"] > hits[-1]["score"]
    assert top["reasons"]


def test_suggest_ranks_scraper_for_scrape_goal():
    hits = suggest("scrape hacker news and make a daily digest")
    assert hits[0]["template_id"] in ("scraper-digest", "report-mailer")


def test_instantiate_fills_slots_and_explains():
    out = instantiate("scraper-digest", {"SOURCE_URL": "https://x.com",
                                         "DIGEST_NAME": "d.md"})
    assert out["ok"] is True
    fetch = out["tasks"][0]
    assert fetch["payload"]["args"]["urls"] == ["https://x.com"]
    save = [t for t in out["tasks"] if t["id"] == "save"][0]
    assert save["payload"]["args"]["path"] == "d.md"
    # SLOT placeholders are gone; {{task.result}} artifact refs remain
    import re as _re

    flat = str(out["tasks"])
    assert not _re.search(r"\{\{\s*[A-Z_][A-Z0-9_]*\s*\}\}", flat)
    assert "{{distill.result}}" in flat
    assert out["explainer"][0].startswith("1. ")
    assert len(out["explainer"]) == len(out["tasks"])
    # explainer respects dependency order
    order = {step.split(". ")[0]: step for step in out["explainer"]}
    distill_idx = [i for i, s in enumerate(out["explainer"])
                   if "interesting items" in s][0]
    save_idx = [i for i, s in enumerate(out["explainer"]) if "digest" in s][0]
    assert distill_idx < save_idx or "after" in order.get(str(save_idx+1), "")


def test_instantiate_defaults_fill_questions():
    out = instantiate("report-mailer")  # no values -> defaults kick in
    assert out["ok"] is True
    assert out["values"]["TOPIC"] == "project status"


def test_instantiate_unknown_template_teaches():
    out = instantiate("vibes-only")
    assert out["ok"] is False
    assert "saas-crud-api" in out["error"]  # lists valid ids


def test_gate_template_carries_when_clause():
    out = instantiate("watch-alert")
    assess = [t for t in out["tasks"] if t["id"] == "assess"][0]
    alert = [t for t in out["tasks"] if t["id"] == "alert-if-down"][0]
    assert assess["payload"]["passed"] is True
    assert alert["payload"]["when"]["field"] == "passed"
    assert alert["payload"]["when"]["equals"] is False
