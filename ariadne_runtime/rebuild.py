"""Visible rebuilds -- erase-and-prove change primitive (Phase 12).

The contract that kills "trust me, I changed it":

    MAP      resolve requested changes -> exact affected files
    DEMOLISH archive those files (into .rebuilds/gen-<N>/) then DELETE
             them from the workspace -- the void is observable
    REBUILD  workers write fresh implementations into the void
    PROOF    byte-level diff vs the archive -> verdict per file

Rules enforced here (not by politeness):
  * nothing outside build_dir is ever demolishable
  * a rebuild response WITHOUT a proof bundle is not a success
    (require_proof() rejects it)
  * identical rebuilt bytes => verdict 'noop' ("nothing needed changing")
    -- never reported as work
  * archives keep the last MAX_GENERATIONS generations
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

MAX_GENERATIONS = 5
ARCHIVE_DIR = ".rebuilds"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RebuildError(Exception):
    pass


class RebuildSession:
    """One erase-and-rebuild cycle over a build directory."""

    def __init__(self, build_dir: Path) -> None:
        self.build_dir = Path(build_dir).resolve()
        if not self.build_dir.exists():
            raise RebuildError(f"build dir missing: {self.build_dir}")
        self._archive_root = self.build_dir / ARCHIVE_DIR
        self.generation: Optional[str] = None
        self.manifest: List[Dict[str, Any]] = []

    # ── MAP ───────────────────────────────────────────────────────────────
    def map_targets(self, patterns: Iterable[str]) -> List[Path]:
        out: List[Path] = []
        for pat in patterns:
            matches = sorted(self.build_dir.glob(pat))
            out.extend(m for m in matches if m.is_file())
        uniq = []
        seen = set()
        for p in out:
            rp = p.resolve()
            try:
                rp.relative_to(self.build_dir)
            except ValueError:
                raise RebuildError(
                    f"refusing target outside build dir: {p}")
            if rp not in seen:
                seen.add(rp)
                uniq.append(p)
        return uniq

    # ── DEMOLISH ──────────────────────────────────────────────────────────
    def demolish(self, targets: List[Path],
                 *, confirm_mass: bool = True,
                 mass_threshold: int = 40) -> Dict[str, Any]:
        if not targets:
            raise RebuildError("demolish called with no targets")
        n_total = sum(1 for _ in self.build_dir.rglob("*")
                      if _.is_file()
                      and ARCHIVE_DIR not in _.parts)
        # snapshot of what exists BEFORE demolition: prove() needs this to
        # distinguish genuinely-new files from untouched survivors
        self._pre_existing = {
            f.relative_to(self.build_dir).as_posix()
            for f in self.build_dir.rglob("*")
            if f.is_file() and ARCHIVE_DIR not in f.parts}
        pct = round(100.0 * len(targets) / max(1, n_total), 1)
        if confirm_mass and pct > mass_threshold:
            return {"ok": False,
                    "needs_confirm": True,
                    "message": (f"this rewrites {pct}% of your app "
                                f"({len(targets)}/{n_total} files). "
                                f"Confirm to proceed.")}

        self._archive_root.mkdir(exist_ok=True)
        gens = sorted(int(d.name.split("-")[1])
                      for d in self._archive_root.iterdir()
                      if d.name.startswith("gen-"))
        gen_n = (gens[-1] + 1) if gens else 1
        gen_dir = self._archive_root / f"gen-{gen_n}"
        gen_dir.mkdir()
        self.generation = gen_dir.name

        self.manifest = []
        erased: List[str] = []
        for t in targets:
            data = t.read_bytes()
            rel = t.relative_to(self.build_dir).as_posix()
            (gen_dir / rel).parent.mkdir(parents=True, exist_ok=True)
            (gen_dir / rel).write_bytes(data)
            t.unlink()
            erased.append(rel)
            self.manifest.append({"path": rel,
                                  "sha_before": _sha(data),
                                  "bytes": len(data)})
        self._prune_generations()
        return {"ok": True, "generation": self.generation,
                "erased": erased, "pct_of_app": pct}

    def restore(self) -> List[str]:
        """Put the newest generation back (abort path)."""
        if not self.generation:
            raise RebuildError("nothing demolished in this session")
        gen_dir = self._archive_root / self.generation
        restored = []
        for f in sorted(gen_dir.rglob("*")):
            if f.is_file():
                dest = self.build_dir / f.relative_to(gen_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                restored.append(dest.relative_to(self.build_dir).as_posix())
        return restored

    # ── PROVE ─────────────────────────────────────────────────────────────
    def prove(self) -> Dict[str, Any]:
        if not self.manifest or not self.generation:
            raise RebuildError("prove called before demolish")
        files: List[Dict[str, Any]] = []
        changed = added = unchanged = missing = 0
        for m in self.manifest:
            cur = self.build_dir / m["path"]
            if not cur.exists():
                files.append({"path": m["path"], "verdict": "missing"})
                missing += 1
                continue
            now = _sha(cur.read_bytes())
            if now == m["sha_before"]:
                files.append({"path": m["path"], "verdict": "unchanged"})
                unchanged += 1
            else:
                files.append({"path": m["path"], "verdict": "changed",
                              "sha_after": now})
                changed += 1
        for f in sorted(self.build_dir.rglob("*")):
            if not f.is_file() or ARCHIVE_DIR in f.parts:
                continue
            rel = f.relative_to(self.build_dir).as_posix()
            if rel in {x["path"] for x in self.manifest}:
                continue  # already judged above
            if rel in getattr(self, "_pre_existing", set()):
                continue  # untouched survivor, not new work
            files.append({"path": rel, "verdict": "added"})
            added += 1
        if changed + added == 0 and missing == 0 and unchanged > 0:
            verdict = "noop"
        elif missing:
            verdict = "incomplete"
        else:
            verdict = "rebuilt"
        return {
            "ok": verdict in ("rebuilt",),
            "proof": {
                "generation": self.generation,
                "verdict": verdict,
                "counts": {"changed": changed, "added": added,
                           "unchanged": unchanged, "missing": missing},
                "files": files,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
        }

    # ── internals ─────────────────────────────────────────────────────────
    def _prune_generations(self) -> None:
        gens = sorted((d for d in self._archive_root.iterdir()
                       if d.name.startswith("gen-")),
                      key=lambda d: int(d.name.split("-")[1]))
        for old in gens[:-MAX_GENERATIONS] if len(gens) > MAX_GENERATIONS \
                else []:
            shutil.rmtree(old, ignore_errors=True)


# ── the CLAIM GATE ────────────────────────────────────────────────────────
def require_proof(response: Dict[str, Any]) -> Dict[str, Any]:
    """A rebuild response without a proof bundle is NOT a success."""
    claimed_done = bool(response.get("ok") or response.get("done"))
    has_proof = isinstance(response.get("proof"), dict) and \
        response["proof"].get("verdict") in ("rebuilt", "noop",
                                             "partial")
    if claimed_done and not has_proof:
        return {"ok": False,
                "error": ("proof missing — rerun the rebuild so a proof "
                          "bundle can be produced; a bare 'success' is "
                          "not accepted")}
    return response


__all__ = ["RebuildSession", "RebuildError", "require_proof"]
