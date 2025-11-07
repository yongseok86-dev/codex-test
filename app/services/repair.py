from __future__ import annotations

from typing import Optional
from app.services.llm import generate_sql_via_llm, LLMNotConfigured


def attempt_repair(question: str, sql: str, error: str, provider: Optional[str]) -> Optional[str]:
    """Ask LLM to repair SQL given error message. Returns new SQL or None."""
    try:
        prompt = f"문제가 있는 SQL을 고쳐주세요. 오류: {error}\n원본 질의: {question}\n원본 SQL:\n```sql\n{sql}\n```\n수정된 SQL만 코드펜스로 답변."
        fixed = generate_sql_via_llm(prompt, provider=provider)
        return fixed
    except Exception:
        return None

