"""
SQL 검증기 (SQL Validator) 모듈

생성된 SQL의 안전성과 품질을 검사합니다.
보안 가드레일과 린트 규칙을 적용하여 위험한 쿼리를 차단합니다.

주요 역할:
    1. 보안 검사 (Guardrail): 위험한 SQL 연산 차단
    2. 린트 검사 (Lint): SQL 품질 및 모범 사례 검사
    3. 시맨틱 인식 검증: 엔티티별 시간 필터 검사

검증 레벨:
    - ERROR: 실행 차단 (보안 위반, SELECT * 등)
    - WARNING: 실행 허용하지만 경고 (시간 필터 누락 등)

보안 규칙 (guardrails.json):
    - DELETE, UPDATE, INSERT 차단
    - DROP, TRUNCATE 차단
    - SELECT * 차단

린트 규칙:
    - SELECT * 금지 (error)
    - 이벤트 테이블 시간 필터 필수 (warning)
    - 엔티티별 시간 차원 필터 권장 (warning)
"""
import json
from pathlib import Path
import re
from app.semantic.loader import load_semantic_root
from app.deps import get_logger

logger = get_logger(__name__)


class GuardrailViolation(Exception):
    """가드레일 정책 위반 시 발생하는 예외"""
    pass


# 가드레일 정책 캐시
_POLICY = None


def _load_policy() -> dict:
    """
    가드레일 정책을 로드합니다.

    guardrails.json 파일에서 보안 정책을 읽어옵니다.
    파일이 없으면 기본 정책을 사용합니다.

    Returns:
        dict: 가드레일 정책
            - deny_contains: 차단할 SQL 키워드 리스트

    Example:
        {
            "deny_contains": [
                "delete ", "update ", "insert ",
                "drop ", "truncate ", " select * "
            ]
        }
    """
    global _POLICY
    if _POLICY is not None:
        return _POLICY

    # guardrails.json 파일 경로
    policy_path = Path(__file__).resolve().parent.parent / "guardrails.json"

    # 기본 정책 (폴백)
    default = {
        "deny_contains": [
            "delete ",
            "update ",
            "insert ",
            "drop ",
            "truncate ",
            " select * "
        ]
    }

    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            _POLICY = json.load(f)
            logger.info(f"Loaded guardrail policy: {len(_POLICY.get('deny_contains', []))} rules")
    except Exception as e:
        logger.warning(f"Failed to load guardrails.json, using default policy: {e}")
        _POLICY = default

    return _POLICY


def ensure_safe(sql: str) -> None:
    """
    SQL이 가드레일 정책을 준수하는지 검사합니다.

    위험한 SQL 연산(DELETE, UPDATE, INSERT, DROP 등)이 포함되어 있으면
    GuardrailViolation 예외를 발생시켜 실행을 차단합니다.

    Args:
        sql: 검사할 SQL 문자열

    Raises:
        GuardrailViolation: 가드레일 정책 위반 시

    Example:
        >>> ensure_safe("SELECT count(*) FROM orders")
        # 통과 (예외 없음)

        >>> ensure_safe("DELETE FROM orders")
        GuardrailViolation: query violates guardrail policy

        >>> ensure_safe("SELECT * FROM users")
        GuardrailViolation: query violates guardrail policy  # SELECT * 차단

    Note:
        - 이 함수는 실행 전에 반드시 호출되어야 합니다.
        - 정책 위반 시 쿼리 실행이 완전히 차단됩니다.
        - guardrails.json에서 정책 수정 가능
    """
    # 앞뒤 공백 추가하여 정확한 키워드 매칭
    # 예: "update" 토큰이 "updated_at" 컬럼명에 매칭되는 것 방지
    lowered = f" {sql.lower()} "

    # 정책 로드
    policy = _load_policy()
    deny = policy.get("deny_contains", [])

    # 차단 키워드 검사
    for tok in deny:
        if tok in lowered:
            logger.error(f"Guardrail violation detected: keyword '{tok.strip()}' found in SQL")
            raise GuardrailViolation("query violates guardrail policy")

    logger.debug("Guardrail check passed")


def lint(sql: str) -> list:
    """
    SQL 린트 검사를 수행하여 품질 이슈를 찾습니다.

    보안 위험은 아니지만 개선이 필요한 SQL 패턴을 감지합니다.
    오류(error)와 경고(warning) 두 레벨로 구분됩니다.

    Args:
        sql: 검사할 SQL 문자열

    Returns:
        List[Dict]: 이슈 리스트
            - level: "error" | "warning"
            - code: 이슈 코드 (예: "no_select_star")
            - message: 이슈 설명

    Example:
        >>> lint("SELECT * FROM orders")
        [{"level": "error", "code": "no_select_star", "message": "SELECT * is not allowed"}]

        >>> lint("SELECT count(*) FROM events_20251106")
        [{"level": "warning", "code": "missing_time_filter", "message": "events-like table without time filter"}]

        >>> lint("SELECT order_id, gmv FROM orders WHERE order_date >= '2025-01-01'")
        []  # 이슈 없음

    검사 항목:
        1. SELECT * 사용 금지 (error)
        2. 이벤트 테이블 시간 필터 권장 (warning)
        3. 시맨틱 엔티티의 시간 차원 필터 권장 (warning)
    """
    issues = []
    lowered = sql.lower()

    # 1. SELECT * 검사 (error 레벨)
    # SELECT *는 성능 문제와 스키마 변경 취약성 때문에 금지
    if " select * " in f" {lowered} ":
        issues.append({
            "level": "error",
            "code": "no_select_star",
            "message": "SELECT * is not allowed"
        })
        logger.warning("Lint issue: SELECT * detected")

    # 2. 이벤트 테이블 시간 필터 검사 (warning 레벨)
    # GA4 이벤트 테이블은 데이터량이 많으므로 시간 필터 권장
    # 정규식: FROM `...events...` 패턴 감지
    has_events_table = re.search(r"from\s+`?[^`]*events[^`]*`?", lowered)
    has_time_filter = re.search(r"where\s+.*(date|time|\_table\_suffix)", lowered)

    if has_events_table and not has_time_filter:
        issues.append({
            "level": "warning",
            "code": "missing_time_filter",
            "message": "events-like table without time filter"
        })
        logger.warning("Lint issue: Events table without time filter")

    # 3. 시맨틱 엔티티별 시간 필터 검사 (warning 레벨)
    # 시맨틱 모델에 정의된 엔티티가 date/datetime 차원을 가지면
    # 해당 테이블 사용 시 시간 필터 권장
    try:
        sem = load_semantic_root().get("semantic.yml", {}) or {}
        entities = sem.get("entities") or []

        for e in entities or []:
            table = str(e.get("table", "")).lower()
            if not table:
                continue

            # SQL에 해당 테이블이 언급되었는지 확인
            if table in lowered:
                # 엔티티의 차원 중 시간 타입이 있는지 확인
                dimensions = e.get("dimensions") or []
                has_time_dim = any(
                    (d.get("type") or "").lower() in {"date", "datetime", "timestamp"}
                    for d in dimensions
                )

                # 시간 차원이 있는데 WHERE 절에 시간 필터가 없으면 경고
                if has_time_dim and not has_time_filter:
                    issues.append({
                        "level": "warning",
                        "code": "missing_time_filter",
                        "message": f"table {table} likely needs a time filter"
                    })
                    logger.warning(f"Lint issue: Entity table {table} without time filter")

    except Exception as e:
        # 시맨틱 모델 로드 실패는 무시 (선택적 검사)
        logger.debug(f"Semantic entity check skipped: {e}")

    logger.info(f"Lint check completed: {len(issues)} issues found")

    return issues
