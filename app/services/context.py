from __future__ import annotations

from typing import Dict, Any

_CTX: Dict[str, Dict[str, Any]] = {}


def get_context(conv_id: str) -> Dict[str, Any]:
    if not conv_id:
        return {}
    return _CTX.setdefault(conv_id, {})


def update_context(conv_id: str, patch: Dict[str, Any]) -> None:
    if not conv_id:
        return
    ctx = _CTX.setdefault(conv_id, {})
    ctx.update(patch or {})

