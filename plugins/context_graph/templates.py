"""Vibe-mode template library (Phase 8): chat -> executable graph.

Templates are data, not code: each has a plain-english identity, keyword
vocabulary for `suggest`, and task specs with {{SLOT}} placeholders that
`instantiate` fills from user answers. Stdlib-only.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

_SLOT_RE = re.compile(r"\{\{\s*([A-Z_][A-Z0-9_]*)\s*\}\}")

TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "saas-crud-api",
        "name": "SaaS CRUD API",
        "description": ("Stand up a small SaaS-style REST API: schema, "
                        "endpoints for one resource, and tests."),
        "keywords": ["saas", "api", "rest", "crud", "backend", "database",
                     "app", "service", "endpoints"],
        "slots": {
            "RESOURCE": {"question": "What resource does it manage? "
                                      "(e.g. clients, invoices, habits)",
                         "default": "items"},
            "STACK": {"question": "Preferred stack? (fastapi | flask)",
                      "default": "fastapi"},
        },
        "tasks": [
            {"id": "plan-schema", "kind": "note",
             "title": "Decide fields for {{RESOURCE}}",
             "payload": {"text": "resource={{RESOURCE}} stack={{STACK}}"}},
            {"id": "scaffold", "kind": "prime",
             "title": "Scaffold the {{STACK}} project",
             "depends_on": ["plan-schema"],
             "payload": {"prompt": ("Create a minimal {{STACK}} project in "
                                    "the current directory managing "
                                    "'{{RESOURCE}}': CRUD endpoints, sqlite "
                                    "storage, pytest tests. Explain each "
                                    "file you create.")},
             "max_attempts": 2},
            {"id": "verify", "kind": "tool",
             "title": "Run the test suite",
             "depends_on": ["scaffold"],
             "payload": {"tool": "terminal",
                         "args": {"command": "python -m pytest -q"}}},
            {"id": "report", "kind": "note",
             "title": "Summarize what exists now",
             "depends_on": ["verify"],
             "payload": {"text": "{{RESOURCE}} API on {{STACK}} built."}},
        ],
    },
    {
        "id": "scraper-digest",
        "name": "Scraper → Digest",
        "description": ("Fetch a web source on demand, extract the "
                        "interesting bits, and write a digest file."),
        "keywords": ["scrape", "scraping", "digest", "news", "crawl",
                     "monitor", "extract", "summarize", "web"],
        "slots": {
            "SOURCE_URL": {"question": "Which URL should be watched?",
                           "default": "https://news.ycombinator.com"},
            "DIGEST_NAME": {"question": "Name for the digest output?",
                            "default": "digest.md"},
        },
        "tasks": [
            {"id": "fetch", "kind": "tool",
             "title": "Fetch the source",
             "payload": {"tool": "web_extract",
                         "args": {"urls": ["{{SOURCE_URL}}"]}},
             "max_attempts": 3},
            {"id": "distill", "kind": "prime",
             "title": "Pick the interesting items",
             "depends_on": ["fetch"],
             "payload": {"prompt": ("From this content, list the 10 most "
                                    "interesting items as markdown bullets "
                                    "with links:\n\n{{fetch.result}}")}},
            {"id": "save", "kind": "tool",
             "title": "Write the digest",
             "depends_on": ["distill"],
             "payload": {"tool": "write_file",
                         "args": {"path": "{{DIGEST_NAME}}",
                                  "content": "{{distill.result}}"}}},
        ],
    },
    {
        "id": "watch-alert",
        "name": "Watch & Alert loop",
        "description": ("Check whether something is healthy; act only when "
                        "it is not. The template of a safe 'loop'."),
        "keywords": ["watch", "alert", "health", "uptime", "check", "loop",
                     "cron", "schedule", "notify", "down"],
        "slots": {
            "TARGET_URL": {"question": "What URL should be watched?",
                           "default": "http://localhost:8000/health"},
        },
        "tasks": [
            {"id": "probe", "kind": "tool",
             "title": "Probe the target",
             "payload": {"tool": "web_extract",
                         "args": {"urls": ["{{TARGET_URL}}"]}},
             "max_attempts": 2},
            {"id": "assess", "kind": "note",
             "title": "Was the probe healthy?",
             "depends_on": ["probe"],
             "payload": {"passed": True}},
            {"id": "alert-if-down", "kind": "prime",
             "title": "Alert because target looks down",
             "depends_on": ["assess"],
             "payload": {"when": {"task": "assess", "field": "passed",
                                  "equals": False},
                         "prompt": ("The watched endpoint {{TARGET_URL}} "
                                    "failed its probe. Draft an incident "
                                    "note describing likely causes and next "
                                    "checks.")}},
        ],
    },
    {
        "id": "report-mailer",
        "name": "Report Mailer",
        "description": ("Gather facts, compose a report with the prime "
                        "engine, and save it ready to send."),
        "keywords": ["report", "mail", "email", "newsletter", "summary",
                     "weekly", "compose", "send"],
        "slots": {
            "TOPIC": {"question": "What is the report about?",
                      "default": "project status"},
        },
        "tasks": [
            {"id": "gather", "kind": "tool",
             "title": "Collect context files",
             "payload": {"tool": "search_files",
                         "args": {"pattern": "*.md", "target": "files"}}},
            {"id": "compose", "kind": "prime",
             "title": "Draft the {{TOPIC}} report",
             "depends_on": ["gather"],
             "payload": {"prompt": ("Write a crisp one-page {{TOPIC}} "
                                    "report. Ground it in these found "
                                    "files:\n\n{{gather.result}}")}},
            {"id": "store", "kind": "tool",
             "title": "Save the report",
             "depends_on": ["compose"],
             "payload": {"tool": "write_file",
                         "args": {"path": "report-{{TOPIC}}.md",
                                  "content": "{{compose.result}}"}}},
        ],
    },
]

_BY_ID = {t["id"]: t for t in TEMPLATES}


def get(template_id: str) -> Optional[Dict[str, Any]]:
    return _BY_ID.get(template_id)


def all_templates() -> List[Dict[str, Any]]:
    return [dict(t) for t in TEMPLATES]


def slots_for(template_id: str) -> Dict[str, Dict[str, str]]:
    t = get(template_id)
    return dict(t["slots"]) if t else {}


def suggest(goal: str, *, limit: int = 3) -> List[Dict[str, Any]]:
    """Rank templates against a free-text goal.

    Score = keyword overlap (weighted by keyword rarity) + fuzzy similarity
    of the goal to the description. Transparent on purpose.
    """
    text = goal.lower()
    words = set(re.findall(r"[a-z]+", text))
    scored = []
    for t in TEMPLATES:
        kw_hits = sum(1 for k in t["keywords"] if k in text or k in words)
        desc_sim = SequenceMatcher(
            None, text, t["description"].lower()).ratio()
        name_sim = SequenceMatcher(
            None, text, t["name"].lower()).ratio()
        score = kw_hits * 10 + desc_sim * 8 + name_sim * 6
        reasons = [f"{kw_hits} keyword hit(s)"] if kw_hits else []
        if desc_sim > 0.25:
            reasons.append("description matches your goal")
        scored.append({
            "template_id": t["id"], "name": t["name"],
            "description": t["description"],
            "score": round(score, 1),
            "reasons": reasons or ["general similarity"],
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def instantiate(template_id: str,
                slot_values: Optional[Dict[str, str]] = None
                ) -> Dict[str, Any]:
    """Fill a template's {{SLOT}} placeholders; return plan specs + explainer.

    Returns {"ok": False, "error", ...} on unknown template or missing slots
    (teaching error lists what's needed).
    """
    t = get(template_id)
    if not t:
        return {
            "ok": False,
            "error": (f"unknown template '{template_id}'. "
                      f"Available: {[x['id'] for x in TEMPLATES]}"),
        }
    values: Dict[str, str] = {}
    missing = []
    for key, meta in t["slots"].items():
        v = str((slot_values or {}).get(key) or meta["default"] or "").strip()
        if not v:
            missing.append(key)
        values[key] = v
    if missing:
        return {
            "ok": False,
            "error": f"missing slot value(s): {missing}",
            "questions": {k: t["slots"][k]["question"] for k in missing},
        }

    def fill(obj: Any) -> Any:
        if isinstance(obj, str):
            return _SLOT_RE.sub(
                lambda m: values.get(m.group(1), m.group(0)), obj)
        if isinstance(obj, dict):
            return {k: fill(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [fill(v) for v in obj]
        return obj

    specs = [dict(fill(task)) for task in t["tasks"]]
    # explainer: topological order already guaranteed by construction;
    # build human sentences from titles + deps
    by_id = {s["id"]: s for s in specs}
    done = set()
    steps: List[str] = []
    remaining = list(specs)
    while remaining:
        progressed = False
        for s in list(remaining):
            deps = s.get("depends_on") or []
            if all(d in done for d in deps):
                dep_note = ""
                if deps:
                    dep_note = (f" (after {', '.join(by_id[d]['title'].lower() for d in deps)})")
                elif len(specs) > 1:
                    dep_note = " (first)"
                steps.append(f"{len(steps)+1}. {s['title']}{dep_note}")
                done.add(s["id"])
                remaining.remove(s)
                progressed = True
        if not progressed:  # defensive; templates are acyclic by design
            break
    return {
        "ok": True,
        "template_id": t["id"],
        "goal": t["name"],
        "values": values,
        "tasks": specs,
        "explainer": steps,
    }
