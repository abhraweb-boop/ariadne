"""Ariadne webhooks router — webhook registry for the Webhooks pane.

Read-only registry view with create/delete. Webhook delivery itself is
handled by the gateway's outbound machinery; this router just manages the
configured webhook list so the desktop UI can browse and edit it.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ariadne/webhooks", tags=["ariadne-webhooks"])

# In-memory registry (persisted to HERMES_HOME/webhooks.json by the gateway
# when webhook delivery is enabled). Kept simple: this pane's job is CRUD UX,
# and the actual delivery engine reads the same file.


def _webhooks_path() -> Path:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    return home / "webhooks.json"


def _load() -> List[Dict[str, Any]]:
    p = _webhooks_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save(webhooks: List[Dict[str, Any]]) -> None:
    p = _webhooks_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(webhooks, indent=2), encoding="utf-8")


class WebhookCreate(BaseModel):
    url: str
    events: List[str] = []


@router.get("")
def list_webhooks() -> Dict[str, Any]:
    return {"ok": True, "webhooks": _load()}


@router.post("")
def create_webhook(body: WebhookCreate) -> Dict[str, Any]:
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "url must be http(s)")
    webhooks = _load()
    if any(w.get("url") == body.url for w in webhooks):
        raise HTTPException(409, "webhook already exists")
    entry = {"url": body.url, "events": body.events, "created": int(time.time())}
    webhooks.append(entry)
    _save(webhooks)
    return {"ok": True, "webhook": entry}


@router.delete("/{index}")
def delete_webhook(index: int) -> Dict[str, Any]:
    webhooks = _load()
    if index < 0 or index >= len(webhooks):
        raise HTTPException(404, "webhook not found")
    removed = webhooks.pop(index)
    _save(webhooks)
    return {"ok": True, "removed": removed}
