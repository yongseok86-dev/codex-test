from __future__ import annotations

import re
from typing import Dict, Any, Tuple
from app.semantic.loader import load_semantic_root


def normalize(text: str) -> Tuple[str, Dict[str, Any]]:
    """Lightweight normalization: trim, collapse spaces, unify common variants.
    Returns (normalized_text, meta)
    """
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    # synonyms to canonical tokens (e.g., '구매'→'주문')
    sem = load_semantic_root().get("semantic.yml", {}) or {}
    vocab = (sem.get("vocabulary") or {}).get("synonyms", {}) if isinstance(sem, dict) else {}
    for canon, arr in (vocab or {}).items():
        for alt in arr or []:
            t = t.replace(str(alt), str(canon))
    meta = {"normalized": True}
    return t, meta

