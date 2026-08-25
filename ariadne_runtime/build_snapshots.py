"""BuildSnapshots -- git-backed builds (completes Phase 14).

Every plan run can checkpoint its working directory through git:
snapshot BEFORE the run, snapshot AFTER, and write a machine-readable
record to ``<repo>/.prime-runs/<plan_id>.json`` with both SHAs. One
function call reverts a repo to any recorded point (as a new commit --
history is never rewritten).

All functions degrade silently (return None / no-op) outside git repos
or when git is unavailable -- never raise into the executor.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

RUNS_DIRNAME = ".prime-runs"
GIT_IDENTITY = ["-c", "user.name=prime-hermes",
                "-c", "user.email=prime-hermes@local"]


def _git(args: list, cwd: Path) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", *GIT_IDENTITY, *args], cwd=str(cwd),
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return None
        return (r.stdout or "").strip()
    except Exception:
        return None


def ensure_repo(path: str) -> bool:
    """Make ``path`` a git repo if it isn't; True when usable."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    probe = _git(["rev-parse", "--is-inside-work-tree"], p)
    if probe == "true":
        return True
    if probe is None and not (p / ".git").exists():
        # either not a repo or git itself missing; try init once
        if _git(["init", "-q"], p) is None:
            return False
        return _git(["rev-parse", "--is-inside-work-tree"], p) == "true"
    return probe == "true"


def snapshot(path: str, label: str) -> Optional[str]:
    """Commit current worktree state; return the short SHA (None on skip)."""
    p = Path(path)
    if not ensure_repo(p):
        return None
    _git(["add", "-A"], p)
    msg = f"prime-hermes snapshot: {label}"
    _git(["commit", "-m", msg, "--allow-empty", "-q"], p)
    sha = _git(["rev-parse", "--short", "HEAD"], p)
    return sha


def record_run(repo_path: str, plan_id: str,
               before: Optional[str], after: Optional[str],
               final_state: str, extra: Optional[Dict[str, Any]] = None
               ) -> Optional[Path]:
    """Write <repo>/.prime-runs/<plan_id>.json describing the run."""
    p = Path(repo_path)
    if not p.exists():
        return None
    runs = p / RUNS_DIRNAME
    try:
        runs.mkdir(parents=True, exist_ok=True)
        rec = {"plan_id": plan_id, "before": before, "after": after,
               "final_state": final_state,
               "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if extra:
            rec.update(extra)
        out = runs / f"{plan_id}.json"
        out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        return out
    except Exception:
        return None


def load_run(repo_path: str, plan_id: str) -> Optional[Dict[str, Any]]:
    f = Path(repo_path) / RUNS_DIRNAME / f"{plan_id}.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None


def revert_to(path: str, sha: str) -> Optional[str]:
    """Restore the worktree to ``sha`` as a NEW commit (history intact)."""
    p = Path(path)
    if not ensure_repo(p):
        return None
    if _git(["cat-file", "-e", sha], p) is None and \
            _git(["rev-parse", "--verify", sha], p) is None:
        return None
    _git(["checkout", sha, "--", "."], p)
    _git(["commit", "-m", f"prime-hermes revert to {sha}",
          "--allow-empty", "-q"], p)
    return _git(["rev-parse", "--short", "HEAD"], p)
