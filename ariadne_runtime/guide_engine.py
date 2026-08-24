"""Guide engine -- next-step logic + milestone execution (Phase 9).

Four step kinds drive a build:
    question : MCQ with every option explained (human answers by index/id)
    auto     : too many options -> guide decides, states rationale + impact
    run      : instantiate the milestone's template -> create plan -> execute
    done     : terminal summary

Milestones are data (dicts). v1 ships one archetype: `web-app` (5 steps,
per plan amendment A2), plus freeform fallback for anything else.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ariadne_runtime.guide import GuideStore, _get_guide_store

logger = logging.getLogger(__name__)

# ── archetypes ────────────────────────────────────────────────────────────
WEB_APP_MILESTONES: List[Dict[str, Any]] = [
    {
        "id": "idea-clarify",
        "title": "What are we building?",
        "kind": "question",
        "questions": [
            {
                "id": "audience",
                "question": "Who will use it?",
                "options": [
                    {"id": "just-me", "label": "Just me",
                     "explainer": "No login screens; fastest first result.",
                     "impact": "We skip accounts entirely.",
                     "recommended": True},
                    {"id": "few-users", "label": "A few people",
                     "explainer": "Simple shared password or invite link.",
                     "impact": "Adds one small accounts step later."},
                    {"id": "public", "label": "The public",
                     "explainer": "Real logins and hosting costs.",
                     "impact": "~2 extra steps at the end; I handle them."},
                ],
            },
            {
                "id": "core-action",
                "question": "What is the ONE main thing users do?",
                "freeform": True,
                "options": [
                    {"id": "track", "label": "Track things over time",
                     "explainer": "Lists + add form + history view.",
                     "impact": "Classic CRUD app shape.", "recommended": True},
                    {"id": "share", "label": "Share content",
                     "explainer": "Public pages + an editor.",
                     "impact": "We focus on pages, less on forms."},
                ],
                "note": "(reply with your own words if neither fits)",
            },
        ],
    },
    {
        "id": "stack-choice",
        "title": "How it's built under the hood",
        "kind": "auto",
        "decide": lambda ctx: {
            "choice_id": "fastapi-sqlite",
            "chosen_label": "FastAPI + SQLite",
            "rationale": ("few files, zero setup, grows fine for "
                          "single/few-user apps"),
            "impact": ("Your app runs with one command; no database server "
                       "to install. If you outgrow it, migration comes "
                       "later as its own step."),
        },
    },
    {
        "id": "scaffold",
        "title": "Build the skeleton",
        "kind": "run",
        "template": "saas-crud-api",
        "slot_map": {"RESOURCE": "core-action-label", "STACK": None},
        "payoff": True,  # dev-server URL moment
    },
    {
        "id": "data-model",
        "title": "What your app remembers",
        "kind": "question",
        "questions": [
            {"id": "fields",
             "question": "What information should each record hold? "
                         "(e.g. name, date, done/not-done)",
             "freeform": True,
             "options": [
                 {"id": "basic", "label": "Just a name and status",
                  "explainer": "Two columns; easiest to change later.",
                  "impact": "You can add fields anytime after.",
                  "recommended": True},
             ]},
        ],
    },
    {
        "id": "polish-loop",
        "title": "Make it yours",
        "kind": "run",
        "template": "report-mailer",
        "slot_map": {"TOPIC": "static:your app"},
        "payoff": False,
    },
]

ARCHETYPES = {"web-app": WEB_APP_MILESTONES}


def _milestones_for(archetype: str) -> List[Dict[str, Any]]:
    return ARCHETYPES.get(archetype, WEB_APP_MILESTONES)


# ── step computation ──────────────────────────────────────────────────────
def _answered(store: GuideStore, build_id: str, qid: str) -> bool:
    return any(d["question_id"] == qid
               for d in store.decisions_for(build_id))


class GuideEngine:
    def __init__(self, store: Optional[GuideStore] = None) -> None:
        self._store = store or _get_guide_store()

    # ── public surface ─────────────────────────────────────────────────
    def start(self, goal: str, archetype: str = "web-app") -> Dict[str, Any]:
        bid = self._store.create_build(goal, archetype)
        ms = _milestones_for(archetype)
        return {
            "ok": True, "build_id": bid, "goal": goal,
            "greeting": (f"Let's build it together. I'll ask a few "
                         f"questions ({len(ms)} steps total), explain every "
                         f"option, and you can always say 'you decide'."),
            "step": self._step_payload(bid, 0),
        }

    def answer(self, build_id: str, question_id: str,
               option_id: str) -> Dict[str, Any]:
        b = self._require(build_id)
        ms = _milestones_for(b["archetype"])
        idx = b["milestone_idx"]
        milestone = ms[idx] if idx < len(ms) else None
        recorded_label = option_id
        rationale = ""
        if milestone:
            for q in milestone.get("questions", []):
                if q["id"] != question_id:
                    continue
                for opt in q.get("options", []):
                    if opt["id"] == option_id:
                        recorded_label = opt["label"]
                        rationale = opt.get("impact", "")
                        break
        self._store.record_decision(
            build_id, question_id=question_id, option_id=option_id,
            chosen_label=recorded_label, rationale=rationale,
            milestone_id=(milestone or {}).get("id", ""))
        if milestone and milestone["kind"] == "question":
            self._store.merge_context(build_id, {question_id: option_id})
            # all questions answered -> advance to next milestone
            qids = [q["id"] for q in milestone.get("questions", [])]
            if qids and all(_answered(self._store, build_id, q)
                            for q in qids):
                self._store.set_milestone(build_id, idx + 1)
        return self.status(build_id)

    def auto_decide(self, build_id: str) -> Dict[str, Any]:
        """Guide picks for the human ('you decide'), transparently."""
        b = self._require(build_id)
        ms = _milestones_for(b["archetype"])
        idx = b["milestone_idx"]
        milestone = ms[idx] if idx < len(ms) else None
        if not milestone:
            return self.status(build_id)
        if milestone["kind"] == "auto":
            choice = milestone["decide"](b.get("context") or {})
            self._store.record_decision(
                build_id,
                question_id=milestone["id"],
                option_id=f"auto:{choice['choice_id']}",
                chosen_label=choice["chosen_label"],
                rationale=choice["rationale"],
                milestone_id=milestone["id"])
            self._store.merge_context(build_id, {
                milestone["id"]: choice["choice_id"]})
            return {"ok": True, "build_id": build_id,
                    "decided": choice,
                    "step": self._step_payload(build_id, idx + 1)}
        # question milestone: pick recommended options
        for q in milestone.get("questions", []):
            if _answered(self._store, build_id, q["id"]):
                continue
            rec = next((o for o in q.get("options", [])
                        if o.get("recommended")), None)
            rec = rec or (q.get("options") or [{}])[0]
            oid = rec.get("id", "decide")
            self._store.record_decision(
                build_id, question_id=q["id"], option_id=f"auto:{oid}",
                chosen_label=rec.get("label", ""),
                rationale=rec.get("impact", ""),
                milestone_id=milestone["id"])
            self._store.merge_context(build_id, {q["id"]: oid})
        return self.status(build_id)

    def status(self, build_id: str) -> Dict[str, Any]:
        b = self._require(build_id)
        idx = b["milestone_idx"]
        return {"ok": True, "build_id": build_id, "goal": b["goal"],
                "state": b["state"],
                "step": self._step_payload(build_id, idx)}

    def why(self, build_id: str) -> Dict[str, Any]:
        self._require(build_id)
        dec = self._store.decisions_for(build_id)
        return {"ok": True, "build_id": build_id, "decisions": [
            {k: d[k] for k in ("question_id", "option_id", "chosen_label",
                               "rationale")} for d in dec]}

    def advance_after_run(self, build_id: str,
                          run_summary: Dict[str, Any]) -> Dict[str, Any]:
        b = self._require(build_id)
        final = run_summary.get("final_state")
        if final == "failed":
            return {"ok": False, "build_id": build_id,
                    "recovery": {
                        "message": ("That step hit errors I couldn't "
                                    "auto-fix. How should I proceed?"),
                        "options": [
                            {"id": "retry", "label": "Retry it",
                             "impact": "Same plan, fresh attempt."},
                            {"id": "change", "label": "Change approach",
                             "impact": "I'll propose a different route."},
                            {"id": "skip", "label": "Skip this part",
                             "impact": "App continues without this piece; "
                                       "you can revisit later."},
                        ]}}
        ms = _milestones_for(b["archetype"])
        nxt = b["milestone_idx"] + 1
        if nxt >= len(ms):
            self._store.set_state(build_id, "done")
            return {"ok": True, "build_id": build_id,
                    "done": True,
                    "summary": ("Build complete. Every milestone finished "
                                "(or was consciously skipped).")}
        self._store.set_milestone(build_id, nxt)
        return self.status(build_id)

    # ── internals ──────────────────────────────────────────────────────
    def _require(self, build_id: str) -> Dict[str, Any]:
        b = self._store.get_build(build_id)
        if b is None:
            raise KeyError(f"unknown build {build_id}")
        return b

    def _step_payload(self, build_id: str, idx: int) -> Dict[str, Any]:
        b = self._store.get_build(build_id)
        ms = _milestones_for(b["archetype"])
        total = len(ms)
        if idx >= total:
            return {"index": total, "of": total, "kind": "done"}
        m = ms[idx]
        base = {"index": idx, "of": total, "title": m["title"],
                "milestone_id": m["id"]}
        if m["kind"] == "question":
            open_qs = [q for q in m.get("questions", [])
                       if not _answered(self._store, build_id, q["id"])]
            if open_qs:
                base.update({"kind": "question",
                             "questions": open_qs})
                return base
            base.update({"kind": "ready-to-run"})
            return base
        if m["kind"] == "auto" and not _answered(
                self._store, build_id, m["id"]):
            base.update({"kind": "offer-auto"})
            return base
        if m["kind"] == "run":
            from plugins.context_graph.templates import get as get_template

            t = get_template(m["template"])
            base.update({"kind": "run", "template": m["template"],
                         "slots": list((t or {}).get("slots", {}) or {}),
                         "payoff": bool(m.get("payoff"))})
            return base
        base.update({"kind": m["kind"]})
        return base


_engine: Optional[GuideEngine] = None


def get_guide_engine() -> GuideEngine:
    global _engine
    if _engine is None:
        _engine = GuideEngine()
    return _engine


def close_guide_engine() -> None:
    global _engine
    _engine = None
