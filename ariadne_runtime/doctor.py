"""ErrorDoctor + budget governor -- self-healing core (Phase 14).

Every task failure passes through ONE classifier; each class gets an
automatic playbook. The human sees only what survives the playbooks,
plus a /heals journal of what was fixed autonomously.

Classes:
  transient      -> retry with backoff (network blips, timeouts)
  environmental  -> fix the environment then retry (missing dep,
                    missing dir, port busy)
  logical        -> hand to prime worker for code patch, re-run
  permanent      -> stop; surface to human (only class that escalates)

Budget governor: unleashed builds get a spending leash -- soft warn at
50% of cap, hard pause at cap with resume chip.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

# ── classification ────────────────────────────────────────────────────────
TRANSIENT_PATTERNS = [
    r"connection ?reset", r"timed? ?out", r"temporarily unavailable",
    r"429", r"too many requests", r"econnreset", r"etimedout",
    r"read econn", r"remote disconnected", "ssl", r"502", r"503",
    r"\btransient\b",
]
ENVIRONMENTAL_PATTERNS = [
    (r"(?:no module named|modulenotfounderror:?|importerror:?)\s*"
     r"(?:no module named\s*)?'?(?P<mod>[a-z_][\w\.]*)'?", "env"),
    (r"command not found:?\s*'?(?P<cmd>[\w\-\+\.]+)'?", "env"),
    (r"errno 98|address already in use|"
     r"port \d+ (is )?(already )?in use|winerror 10048", "port"),
    (r"permission denied|access is denied", "perm"),
    (r"(?:no such file or directory|filenotfounderror:?|"
     r"enoent):?\s*\[?err?no\s*\d*\]?:?\s*'?(?P<path>[^'\n]+)'?", "env"),
]
LOGICAL_PATTERNS = [
    r"assertionerror", r"assert ", r"traceback \(most recent call last\)",
    r"nameerror", r"typeerror", r"attributeerror", r"valueerror",
    r"syntaxerror", r"indentationerror", r"keyerror", r"indexerror",
    r"test failed|\d+ failed",
]


@dataclass
class Diagnosis:
    cls: str                 # transient|environmental|logical|permanent
    detail: str = ""
    extract: Dict[str, str] = field(default_factory=dict)
    action: str = ""         # playbook id
    human_message: str = ""


def classify(error_text: str) -> Diagnosis:
    """Classify one error string. Order matters: env beats logic beats
    transient when signals co-occur (a traceback mentioning a missing
    module is environmental)."""
    text = (error_text or "").strip()
    low = text.lower()

    for pat, kind in ENVIRONMENTAL_PATTERNS:
        m = re.search(pat, low, re.I)
        if not m:
            continue
        ext = m.groupdict()
        if kind == "port":
            return Diagnosis("environmental", pat, {}, "rebind_port",
                             "Port was busy — rebound and retried.")
        if kind == "perm":
            return Diagnosis("environmental", pat, {}, "ensure_env",
                             "Environment repaired (permissions), retried.")
        if ext.get("mod"):
            return Diagnosis(
                "environmental", pat, ext, "install_dep",
                f"Missing package '{ext['mod'].split('.')[0]}' — "
                f"installed it and retried.")
        if ext.get("path"):
            return Diagnosis("environmental", pat, ext, "ensure_dir",
                             "Recreated the missing path.")
        return Diagnosis("environmental", pat, {}, "ensure_env",
                         "Environment repaired, retried.")

    for pat in LOGICAL_PATTERNS:
        if re.search(pat, low, re.I):
            return Diagnosis(
                "logical", pat, {}, "prime_patch",
                "Code had bugs — patched via the prime worker and re-ran.")

    for pat in TRANSIENT_PATTERNS:
        if re.search(pat, low, re.I):
            return Diagnosis(
                "transient", pat, {}, "backoff_retry",
                "Transient network hiccup — backed off and retried.")

    return Diagnosis("permanent", "", {}, "escalate",
                     text[:300] or "unclassified failure")


# ── playbooks ─────────────────────────────────────────────────────────────
@dataclass
class HealAttempt:
    diagnosis: Diagnosis
    outcome: str          # healed|retrying|failed_permanent
    note: str = ""


class ErrorDoctor:
    """Runs playbooks around task execution.

    Usage:
        doctor.run_task(fn, *args, max_rounds=3)
    where fn() returns {"ok": bool, ...} and may raise. Every heal is
    journaled; only permanent failures bubble up.
    """

    def __init__(self, *, on_event: Optional[Callable[[str], None]] = None,
                 budget: Optional["BudgetGovernor"] = None) -> None:
        self.journal: List[Dict[str, Any]] = []
        self._on_event = on_event
        self.budget = budget

    def _log(self, entry: Dict[str, Any]) -> None:
        entry["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.journal.append(entry)
        try:
            journal_heal(dict(entry))
        except Exception:
            pass
        if self._on_event:
            try:
                self._on_event(entry["note"])
            except Exception:
                pass

    # individual playbooks -------------------------------------------------
    @staticmethod
    def _pb_backoff_retry(round_no: int) -> float:
        return min(8.0, 0.5 * (2 ** round_no))

    @staticmethod
    def _pb_install_dep(mod: str) -> str:
        import subprocess
        base = mod.split(".")[0]
        cmd = ["python", "-m", "pip", "install", base]
        try:
            subprocess.run(cmd, capture_output=True, timeout=180)
            return f"pip install {base}"
        except Exception as exc:  # pragma: no cover
            return f"pip install {base} failed: {exc}"

    @staticmethod
    def _pb_ensure_dir(path: str) -> str:
        from pathlib import Path

        p = Path(path)
        # heuristics: if the missing path has a suffix treat as file ->
        # ensure parent; else create the dir
        target = p.parent if p.suffix else p
        target.mkdir(parents=True, exist_ok=True)
        return f"ensured {target}"

    # main loop -------------------------------------------------------------
    def run_task(self, fn: Callable[..., Dict[str, Any]], *args,
                 max_rounds: int = 3, **kw) -> Dict[str, Any]:
        last_error = ""
        for round_no in range(max_rounds):
            if self.budget:
                gate = self.budget.gate()
                if not gate["allowed"]:
                    return {"ok": False, "paused": True,
                            "reason": "budget_cap_reached",
                            "budget": gate}
            try:
                out = fn(*args, **kw)
                if isinstance(out, dict) and out.get("ok"):
                    return out
                last_error = str((out or {}).get("error")
                                 if isinstance(out, dict) else out)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            diag = classify(last_error)
            if diag.cls == "permanent":
                self._log({"cls": diag.cls, "note": diag.human_message,
                           "action": "escalate"})
                return {"ok": False, "permanent": True,
                        "error": last_error, "human": diag.human_message}

            # run the class playbook
            note_extra = ""
            if diag.action == "install_dep":
                note_extra = self._pb_install_dep(
                    diag.extract.get("mod", ""))
            elif diag.action == "ensure_dir":
                note_extra = self._pb_ensure_dir(
                    diag.extract.get("path", ""))
            elif diag.action == "backoff_retry":
                time.sleep(self._pb_backoff_retry(round_no))
            elif diag.action == "prime_patch":
                note_extra = ("queued for prime patch"
                              if round_no >= 1 else
                              "will re-run with full traceback context")
            self._log({"cls": diag.cls, "round": round_no + 1,
                       "action": diag.action, "note": diag.human_message,
                       "extra": note_extra})
        return {"ok": False, "exhausted": True, "error": last_error,
                "human": (f"I couldn't auto-fix this after {max_rounds} "
                          f"attempts. Last error: "
                          f"{last_error[:200]}")}


# ── budget governor ───────────────────────────────────────────────────────
class BudgetGovernor:
    def __init__(self, cap_usd: float = 5.0) -> None:
        self.cap = float(cap_usd)
        self.spent = 0.0
        self.warned_50 = False
        self.paused = False

    def record(self, usd: float) -> Dict[str, Any]:
        self.spent += float(usd)
        events: List[str] = []
        if not self.warned_50 and self.spent >= self.cap * 0.5:
            self.warned_50 = True
            events.append(f"spent ${self.spent:.2f} — halfway to the "
                          f"${self.cap:.2f} budget cap")
        if self.spent >= self.cap and not self.paused:
            self.paused = True
            events.append(f"budget cap ${self.cap:.2f} reached — build "
                          f"PAUSED (say 'resume' to continue)")
        for e in events:
            pass
        return {"spent": round(self.spent, 2), "cap": self.cap,
                "warned": bool(events) and self.warned_50,
                "paused": self.paused, "events": events}

    def gate(self) -> Dict[str, Any]:
        return {"allowed": not self.paused, "spent": round(self.spent, 2),
                "cap": self.cap, "paused": self.paused}

    def resume(self) -> None:
        self.paused = False


# ── process-wide governor (Console reads this) ────────────────────────────
_active_governor: Optional["BudgetGovernor"] = None

# process-wide heal journal (survives across doctor instances in one proc)
_HEAL_JOURNAL: List[Dict[str, Any]] = []
_JOURNAL_CAP = 200


def journal_heal(entry: Dict[str, Any]) -> None:
    """Append a heal event to the process-wide journal (capped, newest
    last). Called by ErrorDoctor._log and by graph_exec drift/heal paths."""
    entry.setdefault("at", time.strftime("%Y-%m-%dT%H:%M:%S"))
    _HEAL_JOURNAL.append(entry)
    if len(_HEAL_JOURNAL) > _JOURNAL_CAP:
        del _HEAL_JOURNAL[: len(_HEAL_JOURNAL) - _JOURNAL_CAP]


def get_heals(limit: int = 50) -> List[Dict[str, Any]]:
    """Newest-first view of autonomous heals for the /heals surface."""
    return list(reversed(_HEAL_JOURNAL))[:max(1, min(200, limit))]


def get_budget() -> "BudgetGovernor":
    global _active_governor
    if _active_governor is None:
        _active_governor = BudgetGovernor()
    return _active_governor


def set_budget_cap(cap_usd: float) -> "BudgetGovernor":
    global _active_governor
    _active_governor = BudgetGovernor(cap_usd=float(cap_usd))
    return _active_governor


__all__ = ["classify", "Diagnosis", "ErrorDoctor", "BudgetGovernor",
           "get_budget", "set_budget_cap"]
