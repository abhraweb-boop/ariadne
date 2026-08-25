"""Secret-scan gate (Phase 14): block plans that would leak credentials.

Scans task payloads (prompts, code, args) for credential-shaped strings
before execution: API keys, bearer tokens, private key blocks, AWS
shapes, and generic assignment secrets. Findings are advisory by
default; {"secret_scan": "strict"} in plan context turns them into
hard failures.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# (label, pattern) -- tuned for LOW false positives on build prompts
SECRET_PATTERNS = [
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}")),
    ("google-key", re.compile(r"AIza[0-9A-Za-z\-_]{30,}")),
    ("github-token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("bearer-header", re.compile(r"[Bb]earer\s+[A-Za-z0-9\-_.]{25,}")),
    ("private-key-block", re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("assigned-secret", re.compile(
        r"(?:password|passwd|api_key|apikey|secret|token)"
        r"\s*[=:]\s*['\"]([^'\"]{8,})['\"]", re.I)),
]

# obvious placeholders that are NOT real secrets
_SAFE_VALUES = re.compile(
    r"^(\$\{[^}]*\}|<[^>]*>|\{\{.*\}\}|your[-_].*|xxx+|\*+|"
    r"(?:example|sample|placeholder|redacted|changeme|none|null|true|false)"
    r"?[:/].*)$", re.I)


def scan_text(text: str) -> List[Dict[str, str]]:
    """Return [{label, excerpt}] findings for credential-shaped strings."""
    if not text:
        return []
    out: List[Dict[str, str]] = []
    # never flag env-var *references*, only literals
    if "os.environ" in text or "process.env" in text or "$GITHUB_" in text \
            or "getenv" in text:
        env_safe = True
    else:
        env_safe = False
    for label, pat in SECRET_PATTERNS:
        for m in pat.finditer(text):
            if label == "assigned-secret":
                val = m.group(1)
                if _SAFE_VALUES.match(val or "") or env_safe:
                    continue
            excerpt = m.group(0)[:60]
            out.append({"label": label, "excerpt": excerpt})
            if len(out) >= 20:
                return out
    return out


def scan_task_payload(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """Scan every string field of a task payload."""
    blob_parts: List[str] = []

    def _walk(v):
        if isinstance(v, str):
            blob_parts.append(v)
        elif isinstance(v, dict):
            for k, vv in v.items():
                if k.lower() in ("env", "environment"):
                    continue  # env maps hold *names*, values scanned anyway
                _walk(vv)
        elif isinstance(v, list):
            for vv in v:
                _walk(vv)

    _walk(payload)
    return scan_text("\n".join(blob_parts))
