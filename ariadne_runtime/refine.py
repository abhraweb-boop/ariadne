"""Kernel-side refine client shim (Prime parity, Phase-2 scope).

Inside the Ariadne kernel:

    from ariadne_runtime.refine import refine
    await refine.status()
    await refine.run("remember: always check git status before committing")

MVP semantics: requests are recorded as host-request rows; the host-side
refine procedure (skills/software-development/refine) applies them at the
next turn boundary via ariadne_memory. Divergence from Prime documented in
docs/architecture-ariadne-phase2.md (frozen-snapshot rule instead of
turn-end prompt rebuild).
"""

from __future__ import annotations

from typing import Optional

from ariadne_runtime.bridge import _async_request


class refine:  # noqa: N801 - Prime-compatible lowercase namespace
    @staticmethod
    async def status() -> dict:
        return await _async_request("refine.status", {})

    @staticmethod
    async def run(instructions: Optional[str] = None, *, global_: bool = True) -> dict:
        return await _async_request(
            "refine.run",
            {"instructions": instructions or "", "scope": "global" if global_ else "session"},
        )
