"""Verify context_graph registers cleanly through the plugin contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERMES_CORE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERMES_CORE))

import os

os.environ["HERMES_HOME"] = str(HERMES_CORE / ".hermes" / "gate-home")


class FakeCtx:
    def __init__(self):
        self.hooks = {}
        self.tools = []

    def register_hook(self, name, cb):
        self.hooks.setdefault(name, []).append(cb)

    def register_tool(self, *, name, toolset, schema, handler, description="",
                      **kw):
        self.tools.append({"name": name, "toolset": toolset,
                           "schema": schema, "handler": handler})


def main() -> int:
    from plugins.context_graph import register, _on_post_tool_call

    ctx = FakeCtx()
    register(ctx)
    assert set(ctx.hooks) == {"post_tool_call", "pre_llm_call", "on_session_end"}, ctx.hooks
    assert len(ctx.tools) == 1 and ctx.tools[0]["name"] == "ariadne_graph"
    print("registration OK:", sorted(ctx.hooks), "+ tool ariadne_graph")

    # Fire the hook exactly as the lifecycle would.
    _on_post_tool_call(
        tool_name="read_file",
        args={"path": "src/deploy.py"},
        session_id="gate-sess-1",
    )
    _on_post_tool_call(
        tool_name="terminal",
        args={"command": "kubectl rollout status"},
        session_id="gate-sess-1",
    )
    from plugins.context_graph import flush
    flush()

    handler = ctx.tools[0]["handler"]
    stats = json.loads(handler({"action": "stats"}))
    assert stats["ok"] and stats["nodes"] >= 3, stats
    related = json.loads(handler({"action": "related", "query": "deploy"}))
    titles = " ".join(n.get("title", "") for n in related["nodes"])
    assert "deploy.py" in titles, related
    print("hook->store OK:", stats)
    print("related OK:", titles[:80])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
