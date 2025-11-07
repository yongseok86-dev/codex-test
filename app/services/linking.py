from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re
import yaml
from pathlib import Path
from app.schema.catalog import load_catalog


def _tokens(q: str) -> List[str]:
    return re.findall(r"[\w가-힣]+", (q or "").lower())


def schema_link(question: str) -> Dict[str, Any]:
    """Very light schema linking: token overlap with table/column names and aliases.
    Returns { candidates: [{type, name, score, table?}], confidence }
    """
    toks = set(_tokens(question))
    cat = load_catalog()

    # Aliases
    aliases = {}
    p = Path(__file__).resolve().parents[1] / "schema" / "aliases.yaml"
    if p.exists():
        try:
            aliases = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            aliases = {}

    candidates: List[Dict[str, Any]] = []
    # alias mapping
    for k, v in aliases.items():
        if str(k).lower() in toks:
            candidates.append({"type": "alias", "name": v, "score": 2.0})

    # table/columns
    for tkey, table in (cat.tables or {}).items():
        tname = table.name.lower()
        if any(tok in tname for tok in toks):
            candidates.append({"type": "table", "name": table.name, "score": 1.0})
        for c in table.columns:
            cname = c.name.lower()
            score = 0.0
            if cname in toks:
                score += 1.0
            if any(tok in cname for tok in toks):
                score += 0.5
            if score > 0:
                candidates.append({"type": "column", "name": c.name, "table": table.name, "score": score})

    # crude confidence
    conf = min(1.0, sum(x["score"] for x in candidates) / max(1, 5))
    return {"candidates": sorted(candidates, key=lambda x: x["score"], reverse=True), "confidence": conf}

