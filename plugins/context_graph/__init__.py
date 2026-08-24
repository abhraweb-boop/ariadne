"""Ariadne context graph -- records agent work as nodes/edges and recalls it.

Plugin entry: register(ctx) taps the post_tool_call observer hook (fail-open,
batched writes) and injects the ariadne_graph tool. The waterfall loader
injects ranked subgraph context per turn via pre_llm_call context injection.

Design contract: docs/architecture-ariadne-phase3.md
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TOOL = "ariadne_graph"

_store = None
_pending: List[Dict[str, Any]] = []
_lock = threading.RLock()
_session_id = ""
_FLUSH_EVERY = 12


def _cfg() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config
        return ((load_config() or {}).get("ariadne") or {}).get("graph") or {}
    except Exception:
        return {}


def _db_path(hermes_home: Optional[str] = None) -> Path:
    home = Path(hermes_home or os.environ.get("HERMES_HOME") or ".")
    return home / "ariadne" / "graph.db"


def get_store() -> Any:
    global _store
    if _store is None:
        from plugins.context_graph.store import GraphStore

        mcfg = _cfg()
        _store = GraphStore(_db_path())
    return _store


def close_store() -> None:
    global _store
    with _lock:
        if _store is not None:
            try:
                _store.close()
            except Exception:
                pass
            _store = None


# ── extraction: tool call -> nodes/edges ─────────────────────────────────
def _extract(tool_name: str, args: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map one tool call to a (target_type, key, title, meta, rel) record."""
    if not isinstance(args, dict):
        return None

    def _path_key(raw: str) -> str:
        return str(raw or "").replace("\\", "/").strip().lower()

    if tool_name in ("read_file", "write_file", "patch"):
        p = _path_key(args.get("path") or "")
        if not p:
            return None
        rel = {"read_file": "read-by", "write_file": "written-by",
               "patch": "edited-by"}[tool_name]
        title = str(Path(p).name)
        return dict(target_type="file", target_key=p, title=title,
                    rel=rel, meta=None)

    if tool_name == "search_files":
        pat = str(args.get("pattern") or "").strip()
        if not pat:
            return None
        return dict(target_type="search", target_key=pat[:80],
                    title=f"search {pat[:40]}", rel="issued-by", meta=None)

    if tool_name == "terminal":
        cmd = str(args.get("command") or "").strip()
        if not cmd:
            return None
        head = cmd.split()[0][:40] if cmd.split() else "cmd"
        return dict(target_type="cmd", target_key=head,
                    title=cmd[:60], rel="ran-in", meta={"cmd": cmd[:200]})

    if tool_name in ("web_search",):
        q = str(args.get("query") or "").strip()
        if not q:
            return None
        return dict(target_type="web", target_key=q[:80],
                    title=q[:60], rel="queried-by", meta=None)

    if tool_name == "web_extract":
        urls = args.get("urls")
        first = ""
        if isinstance(urls, list) and urls:
            first = str(urls[0])
        elif isinstance(urls, str):
            first = urls
        if not first:
            return None
        return dict(target_type="url", target_key=first[:120],
                    title=first[:80], rel="fetched-by", meta=None)

    if tool_name == "ariadne_memory":
        act = str(args.get("action") or "")
        eid = str(args.get("id") or "") or f"pending-{hash(str(args)) & 0xffff:x}"
        if act in ("add", "update", "delete", "create", "remove"):
            return dict(target_type="mem", target_key=eid,
                        title=str(args.get("title") or act),
                        rel="refined-into", meta=None)
        return None

    if tool_name == "ariadne_kernel":
        # Kernel cells are recorded by the rlm/host bridge for children;
        # plain runs are too noisy per-cell -- record only rlm admissions.
        return None

    return None


def record(tool_name: str, args: Dict[str, Any], *, session_id: str) -> None:
    """Queue one extracted touch; flushed in batches."""
    rec = _extract(tool_name, args)
    if rec is None:
        return
    rec["session_id"] = session_id
    with _lock:
        _pending.append(rec)
        should_flush = len(_pending) >= _FLUSH_EVERY
    if should_flush:
        flush()


def flush() -> int:
    """Write pending touches to the store. Returns count written."""
    global _pending
    with _lock:
        batch = _pending
        _pending = []
    if not batch:
        return 0
    store = get_store()
    written = 0
    for rec in batch:
        try:
            tgt, sess = store.record_touch(
                session_id=rec["session_id"],
                target_type=rec["target_type"],
                target_key=rec["target_key"],
                title=rec.get("title", ""),
                meta=rec.get("meta"),
                rel=rec.get("rel", "touched-by"),
            )
            written += 1
        except Exception:
            logger.debug("context_graph: failed to record %r", rec, exc_info=True)
    return written


# ── hook callbacks ────────────────────────────────────────────────────────
def _on_post_tool_call(**kwargs: Any) -> None:
    try:
        tool = str(kwargs.get("tool_name") or "")
        args = kwargs.get("args") or {}
        session = str(kwargs.get("session_id") or "")
        record(tool, args, session_id=session or "unknown-session")
    except Exception:
        logger.debug("context_graph post_tool_call tap failed", exc_info=True)


def _on_session_end(**kwargs: Any) -> None:
    try:
        flush()
    finally:
        close_store()


# ── waterfall loader (pre_llm_call context injection) ────────────────────
def _on_pre_llm_call(**kwargs: Any) -> Any:
    gcfg = _cfg()
    if not gcfg.get("waterfall_enabled", True):
        return None
    prompt = str(kwargs.get("message") or kwargs.get("prompt") or "")
    if len(prompt.split()) < 4:
        return None
    try:
        store = get_store()
        seeds = store.seeds_by_keyword(prompt, limit=int(gcfg.get("seeds", 5)))
        if not seeds:
            return None
        sg = store.subgraph(
            seeds,
            depth=int(gcfg.get("depth", 2)),
            limit=int(gcfg.get("max_nodes", 12)),
        )
        if not sg["nodes"]:
            return None
        budget = int(gcfg.get("char_budget", 1200))
        lines = ["<ariadne-context-graph>"]
        used = len(lines[0])
        for n in sg["nodes"]:
            line = f"- [{n['type']}] {n['title'] or n['key']} ({n['touches']}x)"
            if used + len(line) + 20 > budget:
                break
            lines.append(line)
            used += len(line) + 1
        lines.append("(related prior work; use ariadne_graph action=related)")
        lines.append("</ariadne-context-graph>")
        block = "\n".join(lines)
        if len(block) < len("<ariadne-context-graph>") * 2 + 10:
            return None
        return {"context": block}
    except Exception:
        logger.debug("context_graph waterfall failed", exc_info=True)
        return None


# ── tool schema + dispatch ───────────────────────────────────────────────
_SCHEMA = {
    "name": _TOOL,
    "description": (
        "Ariadne context graph over your own work: which files/commands/"
        "memories/URLs were touched, by which sessions, how they relate. "
        "Actions: related (ranked subgraph), timeline, stats, prune, export. "
        'EXAMPLE: {"action":"related","query":"deploy","depth":2}.'
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["related", "timeline", "stats", "prune", "export"],
            },
            "query": {"type": "string",
                      "description": "Keyword seed(s) for related"},
            "node": {"type": "string", "description": "Node id for timeline"},
            "depth": {"type": "integer"},
            "limit": {"type": "integer"},
            "older_than_days": {"type": "number"},
        },
        "required": ["action"],
    },
}


def handle_ariadne_graph(args: Dict[str, Any], **_kw) -> str:
    args = dict(args or {})
    action = str(args.get("action") or "").lower()
    aliases = {"find": "related", "graph": "related", "neighbors": "related"}
    action = aliases.get(action, action)
    handlers = {
        "related": _h_related, "timeline": _h_timeline,
        "stats": _h_stats, "prune": _h_prune, "export": _h_export,
    }
    fn = handlers.get(action)
    if fn is None:
        return json.dumps({
            "ok": False,
            "error": (f"unknown action '{args.get('action')}'. Valid: "
                      f"{sorted(handlers)}. Example: "
                      '{"action":"related","query":"deploy","depth":2}'),
        })
    try:
        flush()  # serve on fresh data
        return json.dumps(fn(args), default=str)
    except Exception as exc:
        logger.exception("ariadne_graph %s failed", action)
        return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def _h_related(a: Dict[str, Any]) -> Dict[str, Any]:
    store = get_store()
    query = str(a.get("query") or a.get("node") or "")
    seeds = (
        [a["node"]] if a.get("node")
        else store.seeds_by_keyword(query, limit=int(a.get("limit", 5)))
    )
    sg = store.subgraph(seeds, depth=int(a.get("depth", 2)),
                        limit=int(a.get("limit", 20)))
    return {"ok": True, **sg}


def _h_timeline(a: Dict[str, Any]) -> Dict[str, Any]:
    nid = str(a.get("node") or "")
    if not nid:
        return {"ok": False, "error": "timeline requires node id"}
    return {"ok": True, "events": get_store().timeline(nid)}


def _h_stats(_a: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, **get_store().stats()}


def _h_prune(a: Dict[str, Any]) -> Dict[str, Any]:
    res = get_store().prune(older_than_days=float(a.get("older_than_days", 30)))
    return {"ok": True, **res}


def _h_export(a: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, **get_store().export(limit=int(a.get("limit", 100)))}


# ── plugin registration ──────────────────────────────────────────────────
def register(ctx) -> None:
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("on_session_end", _on_session_end)
    ctx.register_tool(
        name=_TOOL,
        toolset="ariadne",
        schema=_SCHEMA,
        handler=lambda args, **kw: handle_ariadne_graph(args, **kw),
        description="Context graph over Ariadne's work: related subgraphs, "
                    "timelines, stats.",
    )
