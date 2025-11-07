"""
대화형 컨텍스트 관리 모듈

이 모듈은 사용자와의 대화 세션별로 컨텍스트(이전 질문, SQL, 계획 등)를
메모리에 저장하고 관리합니다. 이를 통해 연속된 질문에서 이전 대화 내용을
참조할 수 있습니다.

주의:
    - 현재는 인메모리 저장소를 사용하므로 서버 재시작 시 모든 컨텍스트가 소실됩니다.
    - 프로덕션 환경에서는 Redis, Memcached 등 외부 캐시를 사용하는 것을 권장합니다.
"""
from __future__ import annotations

from typing import Dict, Any

# 전역 컨텍스트 저장소: {conversation_id: {key: value}}
# 예: {"user123": {"last_sql": "SELECT...", "last_plan": {...}}}
_CTX: Dict[str, Dict[str, Any]] = {}


def get_context(conv_id: str) -> Dict[str, Any]:
    """
    대화 ID에 해당하는 컨텍스트를 조회합니다.

    대화 세션별로 저장된 이전 대화 정보(마지막 SQL, 계획 등)를 가져옵니다.
    존재하지 않는 conversation_id인 경우 빈 딕셔너리를 반환합니다.

    Args:
        conv_id: 대화 세션 식별자 (conversation_id)
                클라이언트에서 생성한 UUID 또는 세션 ID

    Returns:
        Dict[str, Any]: 해당 대화의 컨텍스트 딕셔너리
                       빈 문자열이거나 존재하지 않으면 빈 딕셔너리 {}

    Example:
        >>> get_context("session_abc123")
        {"last_sql": "SELECT * FROM orders", "last_plan": {...}}

        >>> get_context("")
        {}
    """
    if not conv_id:
        return {}
    return _CTX.setdefault(conv_id, {})


def update_context(conv_id: str, patch: Dict[str, Any]) -> None:
    """
    대화 컨텍스트를 업데이트합니다.

    기존 컨텍스트에 새로운 키-값 쌍을 추가하거나 기존 값을 갱신합니다.
    대화가 진행되면서 누적된 정보(SQL, 계획, 메타데이터 등)를 저장합니다.

    Args:
        conv_id: 대화 세션 식별자
        patch: 업데이트할 키-값 딕셔너리
               예: {"last_sql": "SELECT...", "last_intent": "metric"}

    Returns:
        None

    Example:
        >>> update_context("session_abc123", {"last_sql": "SELECT COUNT(*) FROM events"})
        >>> update_context("session_abc123", {"last_plan": {"metric": "gmv"}})
        >>> get_context("session_abc123")
        {"last_sql": "SELECT COUNT(*) FROM events", "last_plan": {"metric": "gmv"}}

    Note:
        - 동일한 키로 업데이트하면 기존 값이 덮어쓰기됩니다.
        - conv_id가 빈 문자열이면 아무 작업도 수행하지 않습니다.
    """
    if not conv_id:
        return
    ctx = _CTX.setdefault(conv_id, {})
    ctx.update(patch or {})

