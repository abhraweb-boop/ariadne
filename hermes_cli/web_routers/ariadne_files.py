"""Ariadne files router — read-only workspace browsing for the Files pane.

The desktop app's Files pane reads through Electron's native fs; prime-desktop
keeps the seam clean by serving a read-only listing from the backend instead.

Security: path is resolved against the current working directory and must be
contained within it (no traversal).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/ariadne/files", tags=["ariadne-files"])


def _root() -> Path:
    return Path(os.getcwd()).resolve()


def _resolve(subpath: str) -> Path:
    root = _root()
    target = (root / subpath.lstrip("/")).resolve()
    # Containment via relative_to — correct for prefix-siblings (e.g.
    # "/workspace" vs "/workspace-evil"), Windows case + backslashes, and
    # symlink escapes (resolve() follows links before this check).
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(400, "path escapes workspace") from None
    return target


@router.get("/list")
def list_files(
    path: str = Query("", description="Relative path under the workspace root"),
) -> Dict[str, Any]:
    """List one directory level. Returns entries with type/size/mtime."""
    target = _resolve(path)
    if not target.is_dir():
        raise HTTPException(404, "not a directory")
    entries: List[Dict[str, Any]] = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            try:
                st = child.stat()
            except OSError:
                st = None
            entries.append(
                {
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": st.st_size if st else 0,
                    "mtime": int(st.st_mtime) if st else 0,
                }
            )
    except OSError as e:
        raise HTTPException(500, str(e)) from e
    return {"ok": True, "path": str(target), "entries": entries}


@router.get("/read")
def read_file(
    path: str = Query(...),
    limit_chars: int = Query(100_000, ge=1000, le=500_000),
) -> Dict[str, Any]:
    """Read a text file (capped). Returns content + truncated flag."""
    target = _resolve(path)
    if not target.is_file():
        raise HTTPException(404, "not a file")
    try:
        data = target.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise HTTPException(500, str(e)) from e
    truncated = len(data) > limit_chars
    return {"ok": True, "content": data[:limit_chars], "truncated": truncated, "path": str(target)}
