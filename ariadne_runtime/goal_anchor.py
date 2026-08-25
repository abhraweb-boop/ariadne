"""Goal anchoring + drift sentinel -- anti-drift core (Phase 15).

Three primitives keep long builds on-mission:

    build_anchor(goal, milestone)  -> [GOAL]/[MILESTONE]/[SCOPE] header
                                      prepended to every model prompt
    cap_artifact(text, limit)      -> head+tail cap so upstream results
                                      can't drown the objective
    judge_output(goal, title, out) -> None (pass/unavailable) or a drift
                                      reason string, via cheap Gemini Flash

Judge is conservative: only an explicit "DRIFT:" verdict fails; garbage,
PASS, and unconfigured-Google all pass silently.
"""

from __future__ import annotations

import json
from typing import Optional

_GOAL_TRUNC = 300
_JUDGE_INPUT_CAP = 6000


def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def build_anchor(goal: str, milestone: str = "") -> str:
    lines = [f"[GOAL] {_clip(goal, _GOAL_TRUNC)}"]
    if milestone:
        lines.append(f"[MILESTONE] {_clip(milestone, _GOAL_TRUNC)}")
    lines.append(
        "[SCOPE] Do ONLY this milestone's job. No unrelated refactors. "
        "Stop when done.")
    return "\n".join(lines)


def cap_artifact(value, limit: int = 2048) -> str:
    """Stringify + head/tail-cap one injected artifact."""
    if not isinstance(value, str):
        value = json.dumps(value, default=str)
    if len(value) <= limit:
        return value
    marker = "\n...[truncated]...\n"
    keep = max(0, limit - len(marker))
    head = keep * 2 // 3
    tail = keep - head
    return value[:head] + marker + value[-tail:] if tail else \
        value[:keep] + marker


# ── drift sentinel ────────────────────────────────────────────────────────
def judge_output(goal: str, title: str, output_text: str) -> Optional[str]:
    """Ask cheap Gemini whether the output serves the node's intent.

    Returns None when passing OR when judging is unavailable (never
    raises). Returns the drift reason on an explicit DRIFT verdict.
    """
    from ariadne_runtime import google_provider as gp

    st = gp.status()
    if st.get("state") != "ok":
        return None
    output_text = (output_text or "")[:_JUDGE_INPUT_CAP]
    prompt = (
        f"You are a drift judge for an autonomous build agent.\n"
        f"{build_anchor(goal, title)}\n\n"
        f"NODE OUTPUT (may be truncated):\n{output_text}\n\n"
        f"Does this output serve the GOAL and MILESTONE above? "
        f"Reply with EXACTLY one line:\n"
        f"PASS\nor\nDRIFT: <one-sentence reason>")
    try:
        res = gp.generate(
            prompt, model="gemini-2.5-flash", timeout_s=30)
    except Exception:
        return None
    if not res.get("ok"):
        return None
    text = (res.get("text") or "").strip()
    if text.upper().startswith("DRIFT"):
        # strip the prefix for the reason; fall back to whole line
        reason = text.split(":", 1)[1].strip() if ":" in text else text
        return reason or text
    return None


__all__ = ["build_anchor", "cap_artifact", "judge_output"]
