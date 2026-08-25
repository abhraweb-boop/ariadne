"""Google SDK layer -- Gemini provider + Google tooling (Phase 13).

In-process via google-genai (no extra runtime installs). Everything
degrades to TEACHING STATES, never tracebacks:

    not_installed -> google-genai missing; message says how to add it
    no_key        -> GEMINI_API_KEY/GOOGLE_API_KEY absent
    ok            -> {"text", "model", "usage"}

The executor's `gemini` kind and the Console both consume this module.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

_DEFAULT_MODEL = "gemini-2.5-flash"


def _key() -> Optional[str]:
    return (os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY") or None)


def status() -> Dict[str, Any]:
    """Console-friendly roll-up: installed? key? model?"""
    try:
        import google.genai  # noqa: F401

        installed = True
    except Exception:
        installed = False
    key = _key()
    if not installed:
        state = "not_installed"
        hint = ("pip install google-genai  (or: uv pip install "
                "google-genai --active)")
    elif not key:
        state = "no_key"
        hint = ("set GEMINI_API_KEY (or GOOGLE_API_KEY) in the "
                "environment or .env — get one at "
                "https://aistudio.google.com/apikey")
    else:
        state = "ok"
        hint = ""
    return {"ok": state == "ok", "state": state,
            "model": _DEFAULT_MODEL, "hint": hint}


def generate(prompt: str, *, model: Optional[str] = None,
             system: Optional[str] = None,
             timeout_s: float = 120.0) -> Dict[str, Any]:
    """One-shot Gemini generate_content. Structured errors only."""
    st = status()
    if st["state"] != "ok":
        return {"ok": False, "error": st["state"], "hint": st["hint"]}
    try:
        from google import genai
        from google.genai import types as gtypes

        client = genai.Client(api_key=_key())
        cfg = gtypes.GenerateContentConfig(
            system_instruction=system) if system else None
        resp = client.models.generate_content(
            model=model or _DEFAULT_MODEL,
            contents=prompt,
            config=cfg,
        )
        text = getattr(resp, "text", "") or ""
        usage = {}
        um = getattr(resp, "usage_metadata", None)
        if um is not None:
            usage = {"input_tokens": getattr(um, "prompt_token_count", 0),
                     "output_tokens": getattr(um,
                                              "candidates_token_count", 0)}
        return {"ok": True, "text": text,
                "model": model or _DEFAULT_MODEL, "usage": usage}
    except Exception as exc:
        msg = str(exc)
        if "api key" in msg.lower() or "api_key" in msg.lower():
            return {"ok": False, "error": "no_key",
                    "hint": "GEMINI_API_KEY rejected or absent"}
        return {"ok": False, "error": f"{type(exc).__name__}: {msg}"}


__all__ = ["status", "generate"]
