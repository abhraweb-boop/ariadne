"""Ariadne memory ledger + provider: unit/integration (no model needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugins.memory.ariadne import AriadneMemoryProvider
from plugins.memory.ariadne.ledger import LedgerError, MemoryLedger


@pytest.fixture()
def ledger(tmp_path: Path) -> MemoryLedger:
    led = MemoryLedger(tmp_path / "memory.db", budget_bytes=64 * 1024)
    yield led
    led.close()


# ── ledger core ───────────────────────────────────────────────────────────
def test_add_get_roundtrip(ledger: MemoryLedger):
    rec = ledger.add(body="prefer uv over pip on this machine",
                     kind="memory", title="pkg manager")
    got = ledger.get(rec["id"])
    assert got and got["body"].startswith("prefer uv")
    assert got["status"] == "active"


def test_every_write_is_versioned(ledger: MemoryLedger):
    rec = ledger.add(body="v1")
    ledger.update(rec["id"], body="v2", evidence="correction")
    ledger.delete(rec["id"], evidence="obsolete")
    hist = ledger.history(rec["id"])
    ops = [h["op"] for h in hist]  # newest first
    assert ops == ["delete", "update", "create"]
    assert hist[1]["evidence"] == "correction"
    assert hist[2]["after"]["body"] == "v1"


def test_rollback_restores_prior_body(ledger: MemoryLedger):
    rec = ledger.add(body="original text")
    ledger.update(rec["id"], body="edited text")
    rolled = ledger.rollback_entry(rec["id"], evidence="undo")
    assert rolled["body"] == "original text"
    # Rollback itself is versioned.
    ops = [h["op"] for h in ledger.history(rec["id"])]
    assert ops[0] == "update"


def test_soft_delete_then_rollback_revives(ledger: MemoryLedger):
    rec = ledger.add(body="keep me")
    ledger.delete(rec["id"], evidence="mistake")
    assert ledger.get(rec["id"]) is None
    rolled = ledger.rollback_entry(rec["id"])
    assert rolled["body"] == "keep me"
    assert rolled["status"] == "active"


def test_fts_search_ranks_and_filters_deleted(ledger: MemoryLedger):
    a = ledger.add(title="deploy runbook", body="kubectl rollout restart staging")
    b = ledger.add(title="ssh notes", body="bastion jump host config")
    hits = ledger.search("kubectl rollout")
    ids = [h["id"] for h in hits]
    assert a["id"] in ids and b["id"] not in ids
    ledger.delete(b["id"])
    hits2 = ledger.search("bastion")
    assert all(h["id"] != b["id"] for h in hits2)


def test_snapshot_restore_roundtrip(ledger: MemoryLedger):
    e1 = ledger.add(body="before state")
    snap = ledger.snapshot(label="checkpoint-1")
    ledger.update(e1["id"], body="after drift")
    e2 = ledger.add(body="post-snapshot addition")
    res = ledger.restore_snapshot(snap["snapshot_id"])
    assert res["snapshot_id"] == snap["snapshot_id"]
    assert ledger.get(e1["id"])["body"] == "before state"
    assert ledger.get(e2["id"]) is None          # created after -> soft-deleted
    hist = ledger.history(e1["id"])
    assert any(h["source"] == "restore_snapshot" for h in hist)


def test_budget_evicts_lowest_weight_first(ledger: MemoryLedger):
    low = ledger.add(body="L" * 20000, weight=0.5, title="low")
    high = ledger.add(body="H" * 20000, weight=9.0, title="high")
    pinned = ledger.add(body="P" * 20000, pinned=True, title="pinned")
    # 60k used of 64k budget -> this 10k add has a ~4.5k shortfall, which
    # evicts exactly one candidate: lowest-weight unpinned (`low`).
    ledger.add(body="X" * 10000, title="trigger")
    assert ledger.get(low["id"]) is None
    assert ledger.get(high["id"]) is not None
    assert ledger.get(pinned["id"]) is not None
    st = ledger.stats()
    assert st["budget_used_pct"] <= 100.0


def test_budget_hard_failure_when_unavoidable(ledger: MemoryLedger):
    pinned = ledger.add(body="P" * 50000, pinned=True)
    with pytest.raises(LedgerError):
        ledger.add(body="X" * 40000)
    assert ledger.get(pinned["id"]) is not None


def test_ten_x_envelope_over_builtin(ledger: MemoryLedger):
    """The 10x claim, enforced as a behavior contract."""
    st = ledger.stats()
    builtin_cap = 2200 + 1375  # tools/memory_tool.py measured baseline
    assert st["budget_bytes"] >= 10 * builtin_cap


# ── provider contract ─────────────────────────────────────────────────────
def test_provider_contract(tmp_path, monkeypatch):
    p = AriadneMemoryProvider()
    assert p.name == "ariadne"
    p.initialize("sess-1", hermes_home=str(tmp_path))
    try:
        assert p.is_available()
        schemas = p.get_tool_schemas()
        assert len(schemas) == 1 and schemas[0]["name"] == "ariadne_memory"

        out = json.loads(p.handle_tool_call(
            "ariadne_memory",
            {"action": "add", "body": "user prefers terse replies",
             "kind": "user", "evidence": 'user said "be brief"'},
        ))
        assert out["ok"]
        eid = out["entry"]["id"]

        # search finds it; snapshot block contains it
        found = json.loads(p.handle_tool_call(
            "ariadne_memory", {"action": "search", "query": "terse"}
        ))
        assert any(r["id"] == eid for r in found["results"])

        # unknown action rejected cleanly
        bad = json.loads(p.handle_tool_call(
            "ariadne_memory", {"action": "teleport"}
        ))
        assert bad["ok"] is False

        # stats reflect usage within budget
        stats = json.loads(p.handle_tool_call("ariadne_memory", {"action": "stats"}))
        assert stats["ok"] and stats["active_entries"] >= 1
    finally:
        p.close()


def test_provider_frozen_snapshot_is_stable_within_session(tmp_path):
    p = AriadneMemoryProvider()
    p.initialize("sess-2", hermes_home=str(tmp_path))
    try:
        first = p.system_prompt_block()
        p.handle_tool_call("ariadne_memory",
                           {"action": "add", "body": "mid-session write"})
        second = p.system_prompt_block()
        assert first == second, "mid-session writes must NOT mutate prompt snapshot"
        # ...but a NEW session re-renders and sees it:
        p2 = AriadneMemoryProvider()
        p2.initialize("sess-3", hermes_home=str(tmp_path))
        assert "mid-session write" in p2.system_prompt_block()
        p2.close()
    finally:
        p.close()


# ── refine bridge ─────────────────────────────────────────────────────────
def test_refine_queue_roundtrip():
    import ariadne.service as svc

    svc._refine_requests.clear()
    res = svc._handle_host_request(
        "refine.run", {"instructions": "remember X", "scope": "global"}
    )
    assert res["scheduled"] is True
    status = svc._handle_host_request("refine.status", {})
    assert status["pending"] is True
    drained = svc.drain_refine_requests()
    assert drained and drained[0]["instructions"] == "remember X"
    assert svc._handle_host_request("refine.status", {})["pending"] is False


def test_kernel_refine_shim_importable():
    from ariadne_runtime.refine import refine

    assert hasattr(refine, "run") and hasattr(refine, "status")
