"""Ariadne autonomy policy tiers (governed | unleashed).

Phase-7 contract: friction knobs live here; hard floors never move.

Floors survive every tier (see NEVER): no credential entry, no payment UI,
no destructive OS operations. Everything else — retries, cell timeouts,
iteration ceilings, auto-steer, per-node reporting — is a knob.

Config: config.yaml -> ariadne.autonomy: governed | unleashed (default governed).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

NEVER = (
    "credentials-entry",
    "payment-ui",
    "destructive-os-ops",
)

TIERS: Dict[str, Dict[str, Any]] = {
    "governed": {
        "name": "governed",
        "max_attempts": 2,
        "cell_timeout_s": 300.0,
        "max_iterations": 10_000,
        "auto_steer": False,
        "report_each_node": True,
    },
    "unleashed": {
        "name": "unleashed",
        "max_attempts": 5,
        "cell_timeout_s": 3600.0,
        "max_iterations": 200_000,
        "auto_steer": True,
        "report_each_node": False,
    },
}

_DEFAULT = "governed"


def _configured_tier() -> str:
    try:
        from hermes_cli.config import load_config

        cfg = ((load_config() or {}).get("ariadne") or {}).get("autonomy")
        return str(cfg or _DEFAULT).strip().lower()
    except Exception:
        return _DEFAULT


def get(tier: str | None = None) -> Dict[str, Any]:
    """Explicit tier lookup; unknown names fall back to governed."""
    name = str(tier or "").strip().lower()
    if name in TIERS:
        return dict(TIERS[name])
    if name:
        logger.debug("policy: unknown tier %r, falling back", name)
    return dict(TIERS[_DEFAULT])


def active() -> Dict[str, Any]:
    """Tier resolved from config.yaml (ariadne.autonomy)."""
    return get(_configured_tier())
