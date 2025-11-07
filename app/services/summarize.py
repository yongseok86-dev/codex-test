from __future__ import annotations

from typing import Dict, Any, List


def summarize(rows: List[dict] | None, meta: Dict[str, Any]) -> str:
    if not rows:
        return "결과 행이 없습니다."
    n = len(rows)
    keys = list(rows[0].keys()) if rows else []
    cost = meta.get("estimated_cost_usd")
    parts = [f"행 수: {n}"]
    if keys:
        parts.append(f"컬럼: {', '.join(keys[:6])}{'...' if len(keys)>6 else ''}")
    if cost is not None:
        parts.append(f"예상비용(USD): {cost}")
    return " | ".join(parts)

