"""
쿼리 계획(Query Planner) 모듈

NLU에서 추출한 의도(intent)와 슬롯(slots)을 바탕으로 구체적인 쿼리 실행 계획을 생성합니다.
누락된 정보는 시맨틱 모델에서 정의한 기본값으로 채우고, 기본적인 검증을 수행합니다.

주요 역할:
    1. 의도와 슬롯을 통합하여 실행 가능한 계획 생성
    2. 시맨틱 모델 기반 기본값 보완
    3. 의도, 메트릭, Grain 검증
    4. 후속 단계(SQL 생성)가 사용할 수 있는 표준화된 계획 제공

개선 사항:
    - 시맨틱 모델(semantic.yml)에서 기본값 로드
    - 유효한 의도, 메트릭, grain 검증
    - 의도별 최적 기본값 적용

계획(Plan)에 포함되는 정보:
    - intent: 의도 (metric, metric_over_time, comparison, aggregation)
    - slots: NLU에서 추출한 슬롯 전체
    - metric: 조회할 메트릭 (시맨틱 모델 기반 기본값)
    - grain: 집계 단위 (의도별 최적 기본값)
    - time_window: 시간 범위 (슬롯에서 추출)
    - group_by: 그룹핑 기준 (슬롯에서 추출)
    - filters: 필터 조건 (슬롯에서 추출)

예시:
    입력:
        intent = "metric_over_time"
        slots = {"metric": "gmv", "time_window": {"days": 7}}

    출력:
        plan = {
            "intent": "metric_over_time",
            "slots": {"metric": "gmv", "time_window": {"days": 7}},
            "metric": "gmv",
            "grain": "day"  # 기본값 자동 추가
        }
"""
from typing import Any, Dict, Optional
from app.semantic.loader import load_semantic_root
from app.deps import get_logger

logger = get_logger(__name__)

# 시맨틱 모델 캐시
_SEMANTIC_CONFIG: Optional[Dict[str, Any]] = None


def _load_semantic_config() -> Dict[str, Any]:
    """
    시맨틱 모델에서 플래너 설정을 로드합니다.

    Returns:
        Dict[str, Any]: 플래너 설정
            - valid_intents: 유효한 의도 목록
            - valid_metrics: 유효한 메트릭 목록
            - valid_grains: 유효한 grain 목록
            - defaults: 기본값 설정
            - intent_defaults: 의도별 기본값
    """
    global _SEMANTIC_CONFIG

    if _SEMANTIC_CONFIG is not None:
        return _SEMANTIC_CONFIG

    try:
        semantic_root = load_semantic_root()
        semantic_model = semantic_root.get("semantic.yml", {})

        # 유효한 메트릭 목록 추출 (metrics 섹션)
        metrics = semantic_model.get("metrics", []) if isinstance(semantic_model, dict) else []
        valid_metrics = [m.get("name") for m in metrics if isinstance(m, dict) and m.get("name")]

        # 플래너 설정 로드 (planner_config 섹션)
        planner_config = semantic_model.get("planner_config", {}) if isinstance(semantic_model, dict) else {}

        # 기본 설정
        config = {
            "valid_intents": planner_config.get("valid_intents", [
                "metric", "metric_over_time", "comparison", "aggregation"
            ]),
            "valid_metrics": valid_metrics if valid_metrics else ["orders", "gmv", "sessions", "users", "events"],
            "valid_grains": planner_config.get("valid_grains", ["day", "week", "month", "hour"]),
            "defaults": planner_config.get("defaults", {
                "metric": "orders",
                "grain": "day"
            }),
            "intent_defaults": planner_config.get("intent_defaults", {
                "metric": {"grain": "day"},
                "metric_over_time": {"grain": "day"},
                "comparison": {"grain": "month"},
                "aggregation": {"grain": "day"}
            })
        }

        _SEMANTIC_CONFIG = config
        logger.info(f"Loaded planner config: {len(config['valid_metrics'])} valid metrics, "
                   f"{len(config['valid_intents'])} valid intents")

        return _SEMANTIC_CONFIG

    except Exception as e:
        logger.error(f"Failed to load planner config from semantic model: {e}")
        # 폴백: 하드코딩된 기본값
        return {
            "valid_intents": ["metric", "metric_over_time", "comparison", "aggregation"],
            "valid_metrics": ["orders", "gmv", "sessions", "users", "events"],
            "valid_grains": ["day", "week", "month", "hour"],
            "defaults": {
                "metric": "orders",
                "grain": "day"
            },
            "intent_defaults": {
                "metric": {"grain": "day"},
                "metric_over_time": {"grain": "day"},
                "comparison": {"grain": "month"},
                "aggregation": {"grain": "day"}
            }
        }


class PlanValidationError(ValueError):
    """계획 검증 실패 시 발생하는 예외"""
    pass


def make_plan(intent: str, slots: Dict[str, Any], validate: bool = True) -> Dict[str, Any]:
    """
    NLU 추출 결과를 바탕으로 쿼리 실행 계획을 생성합니다 (개선 버전).

    의도(intent)와 슬롯(slots)을 결합하고, 시맨틱 모델에서 로드한 기본값으로 보완합니다.
    의도별 최적 기본값을 적용하고, 기본적인 검증을 수행합니다.

    개선 사항:
        1. 시맨틱 모델에서 기본값 로드
        2. 의도별 최적 grain 기본값 적용
        3. 유효한 intent, metric, grain 검증

    Args:
        intent: NLU에서 추출한 의도
            - "metric": 단순 메트릭 조회
            - "metric_over_time": 시간 추이 분석
            - "comparison": 비교 분석
            - "aggregation": 집계 분석

        slots: NLU에서 추출한 슬롯 딕셔너리
            - metric: 메트릭명 (예: "gmv", "orders")
            - time_window: 시간 범위 (예: {"days": 7})
            - grain: 집계 단위 (예: "day", "week")
            - group_by: 그룹핑 기준 리스트 (예: ["device_category"])
            - filters: 필터 조건 (예: {"device_category": "mobile"})

        validate: 검증 수행 여부 (기본값: True)

    Returns:
        Dict[str, Any]: 완전한 실행 계획 딕셔너리
            - intent: 의도 (검증됨)
            - slots: 원본 슬롯 (참조용)
            - metric: 메트릭명 (시맨틱 모델 기반 기본값)
            - grain: 집계 단위 (의도별 최적 기본값)
            - 기타 슬롯 정보는 직접 접근 가능

    Raises:
        PlanValidationError: 검증 실패 시 (validate=True인 경우)

    Example:
        >>> make_plan("metric_over_time", {"metric": "gmv", "time_window": {"days": 7}})
        {
            "intent": "metric_over_time",
            "slots": {"metric": "gmv", "time_window": {"days": 7}},
            "metric": "gmv",
            "grain": "day"  # metric_over_time의 최적 기본값
        }

        >>> make_plan("comparison", {"metric": "gmv"})
        {
            "intent": "comparison",
            "slots": {"metric": "gmv"},
            "metric": "gmv",
            "grain": "month"  # comparison의 최적 기본값
        }

        >>> make_plan("metric", {})  # 슬롯이 비어있는 경우
        {
            "intent": "metric",
            "slots": {},
            "metric": "orders",  # 시맨틱 모델 기본값
            "grain": "day"
        }

        >>> make_plan("invalid_intent", {})  # 검증 실패
        PlanValidationError: Invalid intent: invalid_intent
    """
    # 1. 시맨틱 모델에서 설정 로드
    config = _load_semantic_config()

    # 2. 검증 수행 (validate=True인 경우)
    if validate:
        _validate_intent(intent, config)
        _validate_metric(slots.get("metric"), config)
        _validate_grain(slots.get("grain"), config)

    # 3. 기본 계획 구조 생성
    plan: Dict[str, Any] = {"intent": intent, "slots": slots}

    # 4. 의도별 최적 기본값 가져오기
    intent_defaults = config["intent_defaults"].get(intent, {})
    global_defaults = config["defaults"]

    # 5. 메트릭 기본값 설정
    # 우선순위: 슬롯 > 시맨틱 모델 기본값
    default_metric = global_defaults.get("metric", "orders")
    plan["metric"] = slots.get("metric", default_metric)

    # 6. Grain 기본값 설정
    # 우선순위: 슬롯 > 의도별 기본값 > 글로벌 기본값
    default_grain = intent_defaults.get("grain", global_defaults.get("grain", "day"))
    plan["grain"] = slots.get("grain", default_grain)

    # 7. 로깅
    logger.debug(f"Created plan: intent={intent}, metric={plan['metric']}, grain={plan['grain']}")

    return plan


def _validate_intent(intent: str, config: Dict[str, Any]) -> None:
    """
    의도(intent)가 유효한지 검증합니다.

    Args:
        intent: 검증할 의도
        config: 플래너 설정

    Raises:
        PlanValidationError: 유효하지 않은 의도인 경우
    """
    valid_intents = config["valid_intents"]
    if intent not in valid_intents:
        logger.warning(f"Invalid intent: {intent}, valid intents: {valid_intents}")
        raise PlanValidationError(
            f"Invalid intent: '{intent}'. Valid intents are: {', '.join(valid_intents)}"
        )


def _validate_metric(metric: Optional[str], config: Dict[str, Any]) -> None:
    """
    메트릭이 유효한지 검증합니다 (None은 허용).

    Args:
        metric: 검증할 메트릭 (None 가능)
        config: 플래너 설정

    Raises:
        PlanValidationError: 유효하지 않은 메트릭인 경우
    """
    if metric is None:
        return  # 메트릭이 없으면 기본값 사용

    valid_metrics = config["valid_metrics"]
    if metric not in valid_metrics:
        logger.warning(f"Invalid metric: {metric}, valid metrics: {valid_metrics}")
        raise PlanValidationError(
            f"Invalid metric: '{metric}'. Valid metrics are: {', '.join(valid_metrics)}"
        )


def _validate_grain(grain: Optional[str], config: Dict[str, Any]) -> None:
    """
    Grain이 유효한지 검증합니다 (None은 허용).

    Args:
        grain: 검증할 grain (None 가능)
        config: 플래너 설정

    Raises:
        PlanValidationError: 유효하지 않은 grain인 경우
    """
    if grain is None:
        return  # grain이 없으면 기본값 사용

    valid_grains = config["valid_grains"]
    if grain not in valid_grains:
        logger.warning(f"Invalid grain: {grain}, valid grains: {valid_grains}")
        raise PlanValidationError(
            f"Invalid grain: '{grain}'. Valid grains are: {', '.join(valid_grains)}"
        )

