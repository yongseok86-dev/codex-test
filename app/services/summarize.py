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


def summarize_llm(question: str, sql: str, meta: Dict[str, Any], provider: str | None = None) -> str | None:
    try:
        from app.services.llm import generate_sql_via_llm
        prompt = (
            "다음 SQL 실행 결과에 대해 간단한 한국어 요약을 1~2문장으로 작성하세요. "
            "숫자는 과도한 정밀도를 피하고, 비용/기간/그룹 기준을 강조하세요.\n\n"
            f"원본 질의: {question}\nSQL:\n```sql\n{sql}\n```\n"
            f"메타: { {k: meta.get(k) for k in ['estimated_cost_usd','total_bytes_processed','validation_steps']} }\n"
            "설명만 출력하세요."
        )
        # 재사용: generate_sql_via_llm는 SQL 추출을 위해 만들어졌지만, 코드펜스가 없으면 원문 반환
        text = generate_sql_via_llm(prompt, provider=provider)
        return text
    except Exception:
        return None
