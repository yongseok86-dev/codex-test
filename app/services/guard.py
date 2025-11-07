"""
SQL 파싱 및 가드 모듈 (SQL Guard)

생성된 SQL을 파싱하여 구문 검증 및 AST(Abstract Syntax Tree) 분석을 수행합니다.
SQLGlot 라이브러리를 사용하여 BigQuery SQL 방언을 파싱합니다.

주요 역할:
    - SQL 구문 검증 (syntax validation)
    - AST 생성 및 분석
    - BigQuery 방언 지원
    - 구문 오류 조기 감지

사용 시나리오:
    - SQL 생성 직후 구문 검증
    - 복잡한 SQL 구조 분석
    - 쿼리 최적화 힌트 추출
    - 보안 검사 전처리

의존성:
    - sqlglot 라이브러리 (선택적)
    - 미설치 시 None 반환 (우아한 degradation)

예시:
    ```python
    sql = "SELECT COUNT(*) FROM orders WHERE date >= '2025-01-01'"

    # 파싱 성공
    ast = parse_sql(sql)
    # → SQLGlot AST 객체 반환

    sql = "SELECT COUNT(* FROM orders"  # 구문 오류

    # 파싱 실패
    parse_sql(sql)
    # → SQLSyntaxError 예외 발생
    ```

Note:
    - sqlglot이 설치되지 않았어도 시스템은 계속 작동합니다.
    - parse_sql()은 None을 반환하고 후속 검증은 다른 방법 사용
    - BigQuery 방언만 지원 (다른 DB는 미지원)
"""
from __future__ import annotations

from typing import Any
from app.deps import get_logger

logger = get_logger(__name__)

# SQLGlot 라이브러리 임포트 (선택적)
try:
    import sqlglot
    logger.info("SQLGlot library loaded successfully")
except Exception as e:
    logger.warning(f"SQLGlot library not available: {e}")
    sqlglot = None  # type: ignore


class SQLSyntaxError(Exception):
    """SQL 구문 오류 시 발생하는 예외"""
    pass


def parse_sql(sql: str) -> Any:
    """
    SQL을 파싱하여 AST(Abstract Syntax Tree)를 생성합니다.

    SQLGlot 라이브러리를 사용하여 BigQuery SQL 방언을 파싱하고
    추상 구문 트리를 반환합니다. 구문 오류가 있으면 예외를 발생시킵니다.

    Args:
        sql: 파싱할 SQL 문자열 (BigQuery 방언)

    Returns:
        Any: SQLGlot AST 객체
             sqlglot이 없으면 None 반환

    Raises:
        SQLSyntaxError: SQL 구문 오류 시

    Example:
        >>> sql = "SELECT COUNT(*) AS cnt FROM orders WHERE date >= '2025-01-01'"
        >>> ast = parse_sql(sql)
        >>> ast  # SQLGlot Expression 객체
        <sqlglot.expressions.Select object at 0x...>

        >>> # AST 활용 예시
        >>> ast.find(sqlglot.expressions.Table)
        <Table: orders>

        >>> # 구문 오류
        >>> parse_sql("SELECT COUNT(* FROM orders")
        SQLSyntaxError: Expected ), Line 1, Col 14

    Use Cases:
        1. 구문 검증: SQL이 유효한지 확인
        2. 구조 분석: SELECT, FROM, WHERE 절 추출
        3. 테이블 추출: 사용된 테이블 목록 파악
        4. 보안 검사: 위험한 패턴 감지

    Note:
        - sqlglot이 미설치면 None 반환 (예외 없음)
        - BigQuery 방언만 지원
        - 파싱 성공 ≠ 실행 성공 (스키마 검증은 별도)
        - AST는 쿼리 최적화, 변환 등에 활용 가능
    """
    # sqlglot 미설치 시 우아하게 None 반환
    if sqlglot is None:
        logger.debug("SQLGlot not available, skipping parse")
        return None

    try:
        # BigQuery 방언으로 파싱
        # sqlglot.parse_one(): 단일 SQL 문 파싱 (복수는 parse() 사용)
        ast = sqlglot.parse_one(sql, read="bigquery")
        logger.debug(f"SQL parsed successfully: {type(ast).__name__}")
        return ast

    except Exception as e:
        # 파싱 실패 → SQL 구문 오류
        logger.error(f"SQL syntax error: {e}")
        raise SQLSyntaxError(str(e))

