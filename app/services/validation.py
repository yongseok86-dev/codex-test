"""
다단계 검증 파이프라인 (Multi-Stage Validation Pipeline) 모듈

생성된 SQL을 6단계 검증 파이프라인을 통해 철저히 검사합니다.
각 단계는 독립적으로 실행되며, 실패 시 즉시 중단됩니다.

검증 단계 (순서대로):
    1. Lint: SQL 품질 및 모범 사례 검사
    2. Dry Run: BigQuery에서 구문 검사 및 비용 추정
    3. Explain: 쿼리 실행 계획 분석
    4. Schema: 결과 스키마 추출 (LIMIT 0)
    5. Canary: 샘플 실행 (첫 N행)
    6. Domain Assertions: 시맨틱 모델 기반 도메인 규칙 검증

각 단계의 목적:
    - Lint: 코드 품질 (빠름, 무료)
    - Dry Run: 구문 검증 및 비용 (빠름, 무료)
    - Explain: 쿼리 플랜 최적화 (빠름, 무료)
    - Schema: 결과 구조 확인 (빠름, 저렴)
    - Canary: 실제 실행 테스트 (느림, 저렴)
    - Assertions: 비즈니스 규칙 검증 (빠름, 무료)

실패 시 동작:
    - 각 단계 실패 시 즉시 중단
    - 실패한 단계까지의 결과를 포함한 리포트 반환
    - 후속 단계는 실행하지 않음 (비용/시간 절약)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging
from app.semantic.loader import load_semantic_root
from app.deps import get_logger

from app.services import validator
from app.bq import connector

logger = get_logger(__name__)


@dataclass
class StepResult:
    """
    검증 단계 결과

    Attributes:
        name: 단계명 (예: "lint", "dry_run")
        ok: 성공 여부
        message: 오류 메시지 (실패 시)
        meta: 추가 메타데이터 (바이트 수, 스키마 등)
    """
    name: str
    ok: bool
    message: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """
    전체 검증 파이프라인 결과

    Attributes:
        steps: 실행된 검증 단계 결과 리스트
        sql: 검증된 SQL 문자열
        schema: 결과 스키마 (schema 단계 성공 시)
    """
    steps: List[StepResult]
    sql: str
    schema: Optional[List[Dict[str, Any]]] = None


def lint_sql(sql: str) -> StepResult:
    """
    1단계: SQL 린트 검사

    validator.lint()를 호출하여 SQL 품질 이슈를 찾습니다.
    error 레벨 이슈가 있으면 실패로 처리합니다.

    Args:
        sql: 검사할 SQL

    Returns:
        StepResult: 린트 결과
            - ok: error 레벨 이슈가 없으면 True
            - meta.issues: 전체 이슈 리스트
    """
    issues = validator.lint(sql)
    ok = all(i.get("level") != "error" for i in issues)
    return StepResult(name="lint", ok=ok, meta={"issues": issues})


def dry_run(sql: str) -> StepResult:
    """
    2단계: BigQuery Dry Run

    실제 실행 없이 BigQuery에서 SQL 구문을 검증하고 비용을 추정합니다.
    처리할 바이트 수를 계산하여 예상 비용을 산출합니다.

    Args:
        sql: 검증할 SQL

    Returns:
        StepResult: Dry Run 결과
            - ok: 구문 오류 없으면 True
            - meta.total_bytes_processed: 처리할 바이트 수
            - message: 오류 메시지 (실패 시)

    Note:
        - BigQuery 클라이언트 미설치 시 건너뜀
        - 실제 데이터 처리 없음 (비용 무료)
    """
    if not connector.available():
        return StepResult("dry_run", ok=True, message="bigquery client not installed", meta={})
    try:
        job = connector.run_query(sql, dry_run=True)
        total = getattr(job, "total_bytes_processed", 0) or 0
        logger.info(f"Dry run successful: {total:,} bytes")
        return StepResult(
            name="dry_run",
            ok=True,
            meta={
                "total_bytes_processed": total,
            },
        )
    except Exception as e:
        logger.error(f"Dry run failed: {e}")
        return StepResult("dry_run", ok=False, message=str(e))


def explain(sql: str) -> StepResult:
    """
    3단계: EXPLAIN 실행 계획 분석

    BigQuery의 EXPLAIN 문을 실행하여 쿼리 실행 계획을 가져옵니다.
    조인 순서, 인덱스 사용 등 최적화 정보를 확인합니다.

    Args:
        sql: 분석할 SQL

    Returns:
        StepResult: Explain 결과
            - ok: 실행 계획 추출 성공 시 True
            - meta.rows: 실행 계획 데이터
            - message: 오류 메시지 (실패 시)

    Note:
        - BigQuery가 EXPLAIN을 지원하지 않는 경우 실패할 수 있음
        - 실패해도 치명적이지 않음 (선택적 검증)
    """
    if not connector.available():
        return StepResult("explain", ok=True, message="bigquery client not installed")
    try:
        job = connector.run_query(f"EXPLAIN {sql}")
        rows = list(job.result())
        logger.info(f"Explain successful: {len(rows)} rows")
        return StepResult(name="explain", ok=True, meta={"rows": [dict(r) for r in rows]})
    except Exception as e:
        logger.warning(f"Explain failed (non-critical): {e}")
        return StepResult("explain", ok=False, message=str(e))


def schema(sql: str) -> StepResult:
    """
    4단계: 결과 스키마 추출

    LIMIT 0 쿼리를 실행하여 데이터 처리 없이 결과 스키마만 가져옵니다.
    컬럼명, 타입, 모드(NULLABLE, REPEATED) 정보를 추출합니다.

    Args:
        sql: 스키마를 추출할 SQL

    Returns:
        StepResult: Schema 결과
            - ok: 스키마 추출 성공 시 True
            - meta.schema: 스키마 정보 리스트
                * name: 컬럼명
                * type: 데이터 타입
                * mode: NULLABLE | REQUIRED | REPEATED
            - message: 오류 메시지 (실패 시)

    Example:
        meta.schema = [
            {"name": "day", "type": "DATE", "mode": "NULLABLE"},
            {"name": "orders", "type": "INT64", "mode": "NULLABLE"}
        ]

    Note:
        - LIMIT 0이므로 데이터 처리 비용 거의 없음
        - 결과 구조 확인용
    """
    if not connector.available():
        return StepResult("schema", ok=True, message="bigquery client not installed")
    try:
        # LIMIT 0으로 스키마만 추출 (비용 절감)
        wrapped = f"SELECT * FROM ({sql}) LIMIT 0"
        job = connector.run_query(wrapped, dry_run=False)
        _ = list(job.result())  # 결과 소비

        # 스키마 정보 추출
        sch = []
        for f in job.schema or []:
            sch.append({
                "name": f.name,
                "type": f.field_type,
                "mode": f.mode
            })

        logger.info(f"Schema extracted: {len(sch)} columns")
        return StepResult(name="schema", ok=True, meta={"schema": sch})
    except Exception as e:
        logger.error(f"Schema extraction failed: {e}")
        return StepResult("schema", ok=False, message=str(e))


def canary(sql: str, limit_rows: int = 100) -> StepResult:
    """
    5단계: Canary 샘플 실행

    실제로 쿼리를 실행하여 첫 N행을 가져옵니다.
    런타임 오류(데이터 타입 불일치, NULL 처리 오류 등)를 사전 감지합니다.

    Args:
        sql: 실행할 SQL
        limit_rows: 가져올 행 수 (기본값: 100)

    Returns:
        StepResult: Canary 결과
            - ok: 실행 성공 시 True
            - meta.rowcount: 반환된 행 수
            - message: 오류 메시지 (실패 시)

    Example:
        >>> canary("SELECT day, orders FROM (...)", limit_rows=10)
        StepResult(name="canary", ok=True, meta={"rowcount": 10})

    Note:
        - 실제 데이터를 처리하므로 비용 발생 (소량)
        - 대용량 쿼리도 LIMIT으로 제한하여 안전
        - 런타임 오류 조기 발견에 유용
    """
    if not connector.available():
        return StepResult("canary", ok=True, message="bigquery client not installed")
    try:
        canary_sql = f"SELECT * FROM ({sql}) LIMIT {int(limit_rows)}"
        job = connector.run_query(canary_sql, dry_run=False)
        rows = [dict(r) for r in job.result()]
        logger.info(f"Canary execution successful: {len(rows)} rows returned")
        return StepResult(name="canary", ok=True, meta={"rowcount": len(rows)})
    except Exception as e:
        logger.error(f"Canary execution failed: {e}")
        return StepResult("canary", ok=False, message=str(e))


def domain_assertions(sql: str, plan: Optional[Dict[str, Any]] = None) -> StepResult:
    """
    6단계: 도메인 규칙 검증 (Domain Assertions)

    시맨틱 모델과 실행 계획을 바탕으로 비즈니스 규칙을 검증합니다.
    SQL이 의도와 메트릭 정의를 올바르게 구현했는지 확인합니다.

    검증 항목:
        1. 메트릭 기본 필터 포함 여부
           - 예: gmv 메트릭은 status='completed' 필터 필수
        2. 시간 추이 쿼리의 GROUP BY 검증
           - intent=metric_over_time이면 DATE() 등 시간 버킷 필수
        3. 시간 윈도우 요청 시 시간 필터 검증
           - time_window 슬롯이 있으면 WHERE 절에 시간 조건 필수
        4. 메트릭의 엔티티 테이블 참조 검증
           - 메트릭이 속한 엔티티의 테이블이 FROM 절에 있는지 확인
        5. GROUP BY 차원 검증
           - slots.group_by에 명시된 차원이 SQL에 포함되는지 확인

    Args:
        sql: 검증할 SQL
        plan: 실행 계획 (의도, 메트릭, 슬롯 정보 포함)

    Returns:
        StepResult: 검증 결과
            - ok: 모든 규칙 통과 시 True
            - message: 위반된 규칙 설명 (실패 시)

    Example:
        >>> plan = {"metric": "gmv", "intent": "metric_over_time", "grain": "day"}
        >>> sql = "SELECT DATE(order_date) AS day, SUM(net_amount) FROM orders WHERE status='completed' GROUP BY day"
        >>> domain_assertions(sql, plan)
        StepResult(name="assertions", ok=True)

        >>> sql = "SELECT SUM(net_amount) FROM orders"  # status 필터 누락
        >>> domain_assertions(sql, plan)
        StepResult(name="assertions", ok=False, message="missing default filter for metric 'gmv': status='completed'")

    Note:
        - 시맨틱 모델의 정의와 SQL 일치 여부를 확인
        - 비즈니스 로직 정합성 보장
        - 휴리스틱 기반이므로 false positive 가능
    """
    # 시맨틱 모델 로드
    sem = load_semantic_root()
    metrics_def = sem.get("metrics_definitions.yaml", {}) or {}
    sem_model = sem.get("semantic.yml", {}) or {}

    # 계획에서 정보 추출
    metric = (plan or {}).get("metric") if plan else None
    intent = (plan or {}).get("intent") if plan else None
    grain = (plan or {}).get("grain") if plan else None
    slots = (plan or {}).get("slots", {}) if plan else {}

    lowered = sql.lower()

    try:
        # 검증 1: GROUP BY 차원 검증
        # slots.group_by에 명시된 차원이 SQL에 포함되는지 확인
        if isinstance(slots, dict) and slots.get("group_by"):
            g = slots.get("group_by") or []
            if isinstance(g, list):
                for dim in g:
                    if str(dim).lower() not in lowered:
                        logger.warning(f"Assertion failed: GROUP BY dimension '{dim}' not found in SQL")
                        return StepResult(
                            name="assertions",
                            ok=False,
                            message=f"missing group_by dimension in SQL: {dim}"
                        )

        # 검증 2: 메트릭 기본 필터 검증
        # 시맨틱 모델에 정의된 메트릭의 default_filters가 SQL에 포함되는지 확인
        # 예: gmv 메트릭은 status='completed' 필터 필수
        if metric and isinstance(metrics_def, dict):
            items = metrics_def.get("metrics") or []
            if isinstance(items, list):
                for m in items:
                    if m.get("name") == metric:
                        default_filters = m.get("default_filters") or []
                        for f in default_filters:
                            if str(f).lower() not in lowered:
                                logger.warning(f"Assertion failed: Default filter missing for '{metric}': {f}")
                                return StepResult(
                                    name="assertions",
                                    ok=False,
                                    message=f"missing default filter for metric '{metric}': {f}"
                                )

        # 검증 3: 시간 추이 쿼리의 시간 버킷팅 검증
        # intent=metric_over_time이면 GROUP BY와 날짜 함수(DATE, TIMESTAMP_TRUNC 등) 필수
        if intent == "metric_over_time" and grain:
            has_group_by = "group by" in lowered
            has_time_bucket = any(k in lowered for k in [
                "date(",
                "timestamp_trunc",
                "format_timestamp",
                "extract("
            ])

            if not has_group_by or not has_time_bucket:
                logger.warning("Assertion failed: metric_over_time without time bucketing")
                return StepResult(
                    name="assertions",
                    ok=False,
                    message="expected time bucketing and GROUP BY for over-time metric"
                )

        # 검증 4: 시간 윈도우 요청 시 시간 필터 검증
        # slots.time_window가 있으면 WHERE 절에 시간 조건 필수
        if isinstance(slots, dict) and slots.get("time_window"):
            has_time_filter = any(tok in lowered for tok in [
                " where ",
                "_table_suffix",
                "timestamp",
                "date(",
                "order_date",
                "event_date"
            ])

            if not has_time_filter:
                logger.warning("Assertion failed: time_window requested but no time filter in SQL")
                return StepResult(
                    name="assertions",
                    ok=False,
                    message="expected time filter for requested time window"
                )

        # 검증 5: 메트릭의 엔티티 테이블 참조 검증
        # 메트릭이 특정 엔티티에 속하면 해당 엔티티의 테이블이 FROM 절에 있어야 함
        if metric and isinstance(sem_model, dict):
            entities = sem_model.get("entities") or []
            target_table = None

            # 메트릭이 속한 엔티티의 테이블 찾기
            for e in entities or []:
                measures = e.get("measures") or []
                for meas in measures:
                    if meas.get("name") == metric and e.get("table"):
                        target_table = str(e.get("table")).lower()
                        break
                if target_table:
                    break

            # 테이블 참조 확인
            if target_table and target_table not in lowered:
                logger.warning(f"Assertion failed: Expected table '{target_table}' not found for metric '{metric}'")
                return StepResult(
                    name="assertions",
                    ok=False,
                    message=f"expected entity table reference: {target_table}"
                )

        logger.info("Domain assertions passed")
        return StepResult(name="assertions", ok=True)

    except Exception as e:
        logger.error(f"Domain assertions error: {e}")
        return StepResult(name="assertions", ok=False, message=str(e))


def run_pipeline(
    sql: str,
    perform_execute: bool = False,
    plan: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None
) -> ValidationReport:
    """
    6단계 검증 파이프라인을 순차적으로 실행합니다.

    각 단계를 순서대로 실행하며, 한 단계라도 실패하면 즉시 중단하고
    그때까지의 결과를 반환합니다.

    검증 파이프라인:
        1. Lint: SQL 품질 검사 (빠름, 무료)
        2. Dry Run: 구문 검증 및 비용 추정 (빠름, 무료)
        3. Explain: 실행 계획 분석 (빠름, 무료)
        4. Schema: 결과 스키마 추출 (빠름, 거의 무료)
        5. Canary: 샘플 실행 (느림, 저렴)
        6. Domain Assertions: 비즈니스 규칙 검증 (빠름, 무료)

    Args:
        sql: 검증할 SQL 문자열
        perform_execute: 실제 실행 여부 (현재 미사용, 향후 7단계 추가용)
        plan: 실행 계획 (도메인 검증용)
        logger: 로거 인스턴스 (선택적)

    Returns:
        ValidationReport: 전체 검증 결과
            - steps: 각 단계별 결과 리스트
            - sql: 검증된 SQL
            - schema: 결과 스키마 (schema 단계 성공 시)

    Example:
        >>> report = run_pipeline(
        ...     sql="SELECT...",
        ...     plan={"metric": "gmv", "intent": "metric_over_time"},
        ...     logger=my_logger
        ... )
        >>> report.steps
        [
            StepResult(name="lint", ok=True, ...),
            StepResult(name="dry_run", ok=True, meta={"total_bytes_processed": 1000000}),
            StepResult(name="explain", ok=False, message="..."),  # 실패 → 중단
        ]

    Early Exit 예시:
        - Lint 실패 → steps = [lint]
        - Dry Run 실패 → steps = [lint, dry_run]
        - 모두 성공 → steps = [lint, dry_run, explain, schema, canary, assertions]

    Note:
        - 각 단계는 이전 단계 성공 시에만 실행
        - 실패 시 즉시 중단하여 비용/시간 절약
        - 모든 단계 성공 시에만 실제 쿼리 실행 (caller가 처리)
    """
    steps: List[StepResult] = []

    # 1단계: Lint (SQL 품질 검사)
    if logger:
        logger.info("stage=lint start")
    steps.append(lint_sql(sql))
    if logger:
        logger.info("stage=lint end ok=%s", steps[-1].ok)
    if not steps[-1].ok:
        logger.warning("Validation stopped at lint stage")
        return ValidationReport(steps=steps, sql=sql)

    # 2단계: Dry Run (구문 검증 및 비용 추정)
    if logger:
        logger.info("stage=dry_run start")
    steps.append(dry_run(sql))
    if logger:
        logger.info("stage=dry_run end ok=%s bytes=%s", steps[-1].ok, steps[-1].meta.get("total_bytes_processed") if steps[-1].ok else None)
    if not steps[-1].ok:
        logger.warning("Validation stopped at dry_run stage")
        return ValidationReport(steps=steps, sql=sql)

    # 3단계: Explain (실행 계획 분석)
    if logger:
        logger.info("stage=explain start")
    steps.append(explain(sql))
    if logger:
        logger.info("stage=explain end ok=%s", steps[-1].ok)
    # Explain 실패는 치명적이지 않음 (계속 진행)
    # if not steps[-1].ok:
    #     return ValidationReport(steps=steps, sql=sql)

    # 4단계: Schema (결과 스키마 추출)
    if logger:
        logger.info("stage=schema start")
    sch = schema(sql)
    steps.append(sch)
    if logger:
        logger.info("stage=schema end ok=%s cols=%s", steps[-1].ok, len((sch.meta.get("schema") or [])) if steps[-1].ok else None)
    if not steps[-1].ok:
        logger.warning("Validation stopped at schema stage")
        return ValidationReport(steps=steps, sql=sql)

    # 5단계: Canary (샘플 실행)
    if logger:
        logger.info("stage=canary start")
    steps.append(canary(sql))
    if logger:
        logger.info("stage=canary end ok=%s rows=%s", steps[-1].ok, steps[-1].meta.get("rowcount") if steps[-1].ok else None)
    if not steps[-1].ok:
        logger.warning("Validation stopped at canary stage")
        return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))

    # 6단계: Domain Assertions (비즈니스 규칙 검증)
    if logger:
        logger.info("stage=assertions start")
    steps.append(domain_assertions(sql, plan=plan))
    if logger:
        logger.info("stage=assertions end ok=%s", steps[-1].ok)
    if not steps[-1].ok:
        logger.warning("Validation stopped at assertions stage")
        return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))

    # 7단계: 최종 실행은 호출자가 처리
    # perform_execute 파라미터는 향후 확장용
    logger.info("All validation stages passed")
    return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))
