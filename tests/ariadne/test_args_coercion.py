"""Regression: executor-side schema normalization + arg coercion must preserve
ariadne_memory's fields (live gate observed empty `body` reaching the handler)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERMES_CORE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERMES_CORE))
os.environ.setdefault("HERMES_HOME", str(HERMES_CORE / ".hermes" / "probe-home"))

from agent.memory_manager import normalize_tool_schema
from model_tools import coerce_tool_args
from plugins.memory.ariadne import AriadneMemoryProvider


def _schema():
    return normalize_tool_schema(AriadneMemoryProvider().get_tool_schemas()[0])


def test_normalization_preserves_properties():
    norm = _schema()
    assert norm is not None, "schema was rejected by normalize_tool_schema"
    props = sorted((norm.get("input_schema") or {}).get("properties", {}).keys())
    assert {"action", "body", "evidence", "kind"} <= set(props)


def test_coercion_keeps_string_fields_intact():
    args = {
        "action": "add",
        "body": "Deploy target is always staging first",
        "kind": "memory",
        "title": "deploy policy",
        "evidence": "user correction",
    }
    coerced = coerce_tool_args("ariadne_memory", dict(args))
    for key, want in args.items():
        got = coerced.get(key)
        assert got == want, f"coercion mangled {key!r}: {got!r} != {want!r}"


# ── model-verb tolerance (live-gate regressions) ─────────────────────────
def test_action_aliases_resolve(tmp_path):
    p = AriadneMemoryProvider()
    p.initialize("sess-a", hermes_home=str(tmp_path))
    try:
        p.handle_tool_call("ariadne_memory",
                           {"action": "add", "body": "alias me",
                            "evidence": "t"})
        # 'read' -> get
        out = json.loads(p.handle_tool_call(
            "ariadne_memory", {"action": "list"}))
        eid = out["entries"][0]["id"]
        got = json.loads(p.handle_tool_call(
            "ariadne_memory", {"action": "read", "id": eid}))
        assert got["ok"] and "alias me" in got["entry"]["body"]
        # 'create' -> add
        made = json.loads(p.handle_tool_call(
            "ariadne_memory", {"action": "create", "body": "second",
                               "evidence": "t2"}))
        assert made["ok"]
    finally:
        p.close()


def test_body_fallback_keys(tmp_path):
    p = AriadneMemoryProvider()
    p.initialize("sess-b", hermes_home=str(tmp_path))
    try:
        out = json.loads(p.handle_tool_call(
            "ariadne_memory",
            {"action": "add", "content": "body came as content",
             "evidence": "fb"}))
        assert out["ok"], out
    finally:
        p.close()


def test_nested_single_field_unwrapped(tmp_path):
    p = AriadneMemoryProvider()
    p.initialize("sess-c", hermes_home=str(tmp_path))
    try:
        out = json.loads(p.handle_tool_call(
            "ariadne_memory",
            {"add": {"body": "nested payload", "evidence": "n"}}))
        assert out["ok"], out
    finally:
        p.close()


def test_unknown_action_error_is_teaching(tmp_path):
    p = AriadneMemoryProvider()
    p.initialize("sess-d", hermes_home=str(tmp_path))
    try:
        out = json.loads(p.handle_tool_call(
            "ariadne_memory", {"action": "teleport", "body": "x" * 40}))
        assert out["ok"] is False
        assert "Valid actions" in out["error"]
        assert "Example" in out["error"]
    finally:
        p.close()
