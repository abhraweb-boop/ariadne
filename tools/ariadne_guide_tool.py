"""ariadne_guide -- the guided-build tool surface (Phase 9).

Actions: start | answer | decide | status | why | abandon
Every response embeds step position so the Console can render a ribbon.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

TOOL_NAME = "ariadne_guide"

SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string",
                   "enum": ["start", "answer", "decide", "status", "why",
                            "abandon"],
                   "description": "Guided-build action."},
        "goal": {"type": "string", "description": "start: what to build"},
        "archetype": {"type": "string",
                      "description": "start: web-app (default) or freeform"},
        "build_id": {"type": "string"},
        "question_id": {"type": "string", "description": "answer: which Q"},
        "option_id": {"type": "string",
                      "description": ("answer: chosen option id (or your own "
                                      "words for freeform questions)")},
    },
    "required": ["action"],
}


def handle_ariadne_guide(args: Dict[str, Any], **_kw) -> str:
    args = dict(args or {})
    action = str(args.get("action") or "").lower()
    from ariadne_runtime.guide_engine import get_guide_engine

    eng = get_guide_engine()

    def _abandon() -> Dict[str, Any]:
        from ariadne_runtime.guide import _get_guide_store

        bid = str(args.get("build_id") or "")
        store = _get_guide_store()
        b = store.get_build(bid)
        if b is None:
            raise KeyError(f"unknown build {bid}")
        store.set_state(bid, "abandoned")
        return {"ok": True, "build_id": bid, "state": "abandoned"}

    handlers = {
        "start": lambda: eng.start(str(args.get("goal") or "").strip(),
                                   str(args.get("archetype") or "web-app")),
        "answer": lambda: eng.answer(str(args.get("build_id")),
                                     str(args.get("question_id") or ""),
                                     str(args.get("option_id") or "")),
        "decide": lambda: eng.auto_decide(str(args.get("build_id"))),
        "status": lambda: eng.status(str(args.get("build_id"))),
        "why": lambda: eng.why(str(args.get("build_id"))),
        "abandon": _abandon,
    }
    fn = handlers.get(action)
    if fn is None:
        return json.dumps({"ok": False,
                           "error": (f"unknown action '{action}'. "
                                     f"Use one of: {sorted(handlers)}")})
    try:
        return json.dumps(fn(), default=str)
    except KeyError as exc:
        return json.dumps({"ok": False,
                           "error": f"unknown: {exc.args[0]}"})
    except Exception as exc:
        logger.exception("ariadne_guide %s failed", action)
        return json.dumps({"ok": False,
                           "error": f"{type(exc).__name__}: {exc}"})


from tools.registry import registry  # noqa: E402

registry.register(
    name=TOOL_NAME,
    toolset="ariadne",
    schema=SCHEMA,
    handler=lambda args, **kw: handle_ariadne_guide(args, **kw),
    check_fn=None,
    emoji="🧭",
    max_result_size_chars=60_000,
)

__all__ = ["handle_ariadne_guide"]
