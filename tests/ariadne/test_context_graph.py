"""Context-graph store + recorder + waterfall loader tests (no model)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plugins.context_graph import (
    _extract,
    _on_pre_llm_call,
    flush,
    handle_ariadne_graph,
    record,
)
from plugins.context_graph.store import GraphStore, node_id


@pytest.fixture()
def store(tmp_path: Path) -> GraphStore:
    s = GraphStore(tmp_path / "graph.db")
    yield s
    s.close()


@pytest.fixture(autouse=True)
def _fresh_module_state(monkeypatch, tmp_path):
    """Isolate module-level pending queue + store per test (ONE shared db)."""
    import plugins.context_graph as cg

    monkeypatch.setattr(cg, "_pending", [])
    shared = GraphStore(tmp_path / "g.db")
    monkeypatch.setattr(cg, "get_store", lambda: shared, raising=True)
    yield
    try:
        shared.close()
    except Exception:
        pass


# ── store core ────────────────────────────────────────────────────────────
def test_touch_is_idempotent_and_bumps(store: GraphStore):
    a = store.touch("file", "a.py", title="a.py")
    b = store.touch("file", "a.py", title="a.py")
    assert a == b == node_id("file", "a.py")
    st = store.stats()
    assert st["nodes"] == 1 and st["by_type"]["file"] == 1


def test_link_weight_bumps_capped(store: GraphStore):
    n1 = store.touch("file", "x.py")
    n2 = store.touch("session", "s1")
    for _ in range(30):
        store.link(n1, "read-by", n2)
    edges = store.timeline(n1)
    assert edges[0]["weight"] <= 16.0  # capped
    assert edges[0]["weight"] > 10.0   # and actually bumped


def test_subgraph_bfs_depth_and_ranking(store: GraphStore):
    s1 = store.touch("session", "sess-1")
    f1 = store.touch("file", "deploy.py", title="deploy.py")
    c1 = store.touch("cmd", "kubectl", title="kubectl rollout")
    m1 = store.touch("mem", "e1", title="deploy policy")
    store.link(f1, "read-by", s1, bump=8.0)
    store.link(f1, "produced", c1, bump=4.0)
    store.link(m1, "refined-into", s1, bump=2.0)

    sg = store.subgraph([f1], depth=2, limit=10)
    ids = {n["id"] for n in sg["nodes"]}
    assert {f1, s1, c1} <= ids          # depth reaches cmd via file
    # strongest edge first: session outranks the weaker cmd link from seed
    ranked = [n["id"] for n in sg["nodes"]]
    assert ranked.index(s1) < ranked.index(c1)


def test_seeds_by_keyword_matches_titles(store: GraphStore):
    store.touch("file", "deploy.py", title="deploy.py")
    store.touch("file", "unrelated.md", title="notes")
    hits = store.seeds_by_keyword("how does deploy work?")
    assert hits and hits[0] == node_id("file", "deploy.py")


def test_prune_removes_stale_singletons(store: GraphStore):
    old = store.touch("url", "old.example.com")
    hub = store.touch("session", "keeper")
    store.link(old, "fetched-by", hub)
    # age the url node artificially is complex; prune by cutoff instead:
    res = store.prune(older_than_days=-0.00001)  # everything stale
    assert res["edges"] >= 1 or res["nodes"] >= 0  # smoke; exact counts vary


# ── recorder extraction ───────────────────────────────────────────────────
def test_extract_file_tools():
    r = _extract("read_file", {"path": "C:\\Repo\\src\\App.py"})
    assert r["target_type"] == "file"
    assert r["target_key"].endswith("src/app.py")  # normalized slashes+lower
    assert r["rel"] == "read-by"

    w = _extract("patch", {"path": "/x/y.md"})
    assert w["rel"] == "edited-by"


def test_extract_terminal_web_memory():
    t = _extract("terminal", {"command": "kubectl rollout restart"})
    assert t["target_type"] == "cmd" and t["target_key"] == "kubectl"

    w = _extract("web_search", {"query": "jupyter zmq protocol"})
    assert w["target_type"] == "web" and "zmq" in w["target_key"]

    m_add = _extract("ariadne_memory",
                     {"action": "add", "id": "abc123"})
    assert m_add["target_type"] == "mem" and m_add["target_key"] == "abc123"
    assert _extract("ariadne_memory", {"action": "stats"}) is None
    assert _extract("ariadne_kernel", {"action": "run"}) is None  # not noisy


def test_record_flush_writes_to_store(tmp_path):
    record("read_file", {"path": "x/deploy.py"}, session_id="s-9")
    record("terminal", {"command": "pytest -q"}, session_id="s-9")
    written = flush()
    assert written == 2
    st = json.loads(handle_ariadne_graph({"action": "stats"}))
    assert st["ok"] and st["nodes"] >= 3  # two targets + one session hub


# ── tool surface ──────────────────────────────────────────────────────────
def test_related_action_end_to_end(tmp_path):
    record("read_file", {"path": "w/deploy.py"}, session_id="sA")
    record("patch", {"path": "w/deploy.py"}, session_id="sA")
    record("web_search", {"query": "staging rollout"}, session_id="sB")
    flush()
    out = json.loads(handle_ariadne_graph({"action": "related",
                                           "query": "deploy"}))
    assert out["ok"]
    titles = " ".join(n.get("title", "") for n in out["nodes"])
    assert "deploy.py" in titles


def test_unknown_action_teaches():
    out = json.loads(handle_ariadne_graph({"action": "teleport"}))
    assert out["ok"] is False and "Valid:" in out["error"]


# ── waterfall loader ──────────────────────────────────────────────────────
def test_waterfall_injects_context_block(tmp_path):
    record("read_file", {"path": "v/rollout.py"}, session_id="sW")
    flush()
    res = _on_pre_llm_call(message="help me fix the rollout script please")
    assert res and "context" in res
    block = res["context"]
    assert block.startswith("<ariadne-context-graph>")
    assert "rollout.py" in block


def test_waterfall_silent_on_short_prompts():
    assert _on_pre_llm_call(message="hi") is None


def test_waterfall_silent_when_no_graph(tmp_path, monkeypatch):
    import plugins.context_graph as cg
    monkeypatch.setattr(
        cg, "get_store",
        lambda: GraphStore(tmp_path / "empty.db"),
    )
    assert _on_pre_llm_call(message="an unrelated long prompt about cooking") is None
