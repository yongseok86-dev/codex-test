"""
시맨틱 모델 기반 동적 SQL 생성 (Semantic SQL Generator) 모듈

시맨틱 모델과 LLM을 활용하여 자연어 질문을 BigQuery SQL로 변환합니다.
GA4 테이블 서픽스 자동 처리, 다중 테이블 JOIN 지원 등 고급 기능을 제공합니다.

주요 특징:
    - 시맨틱 모델 기반 메트릭 정의 활용
    - LLM을 통한 동적 SQL 생성 (OpenAI, Claude, Gemini)
    - GA4 테이블 서픽스 자동 추론 (_TABLE_SUFFIX)
    - 다중 테이블 JOIN 지원 (향후 확장)
    - 컨텍스트 기반 테이블 날짜 선택

지원하는 LLM 프로바이더:
    - OpenAI (기본값): gpt-4o-mini, gpt-4o
    - Anthropic: claude-3-5-sonnet, claude-3-opus
    - Google: gemini-1.5-flash, gemini-1.5-pro

GA4 테이블 서픽스 처리:
    - 기본 패턴: events_* 또는 events_intraday_*
    - 날짜 추론: 질문의 시간 범위와 컨텍스트에서 최적 날짜 결정
    - _TABLE_SUFFIX 활용: 여러 날짜 파티션 동시 조회

다중 테이블 JOIN 지원:
    - 엔티티 관계 기반 자동 JOIN 생성
    - 시맨틱 모델의 relationships 활용
    - 최적 JOIN 경로 선택

예시:
    질문: "지난 7일 모바일 주문 추이"

    생성 SQL:
    ```sql
    SELECT
      DATE(TIMESTAMP_MICROS(event_timestamp)) AS day,
      SUM(CASE WHEN event_name='purchase' THEN 1 ELSE 0 END) AS orders
    FROM `ns-extr-data.analytics_310486481.events_*`
    WHERE _TABLE_SUFFIX BETWEEN '20251031' AND '20251106'
      AND device.category = 'mobile'
    GROUP BY day
    ORDER BY day
    ```
"""
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
import json

from app.config import settings
from app.deps import get_logger
from app.semantic.loader import load_semantic_root
from app.services.context import get_context

logger = get_logger(__name__)

# GA4 기본 테이블 템플릿 (서픽스 제외)
# 실제 테이블: events_YYYYMMDD 또는 events_intraday_YYYYMMDD
GA4_TABLE_TEMPLATE = "ns-extr-data.analytics_310486481.events"


def generate(
    plan: Dict[str, Any],
    question: str,
    limit: int | None = 100,
    llm_provider: Optional[str] = None,
    conversation_id: Optional[str] = None
) -> str:
    """
    시맨틱 모델과 LLM을 활용하여 동적 SQL을 생성합니다.

    이 함수는 LLM에게 시맨틱 모델, 실행 계획, 대화 컨텍스트를 제공하여
    최적화된 BigQuery SQL을 생성하도록 합니다. GA4 테이블의 경우
    _TABLE_SUFFIX를 활용하여 날짜 파티션을 동적으로 선택합니다.

    Args:
        plan: 쿼리 실행 계획 딕셔너리
            - intent: 의도
            - metric: 메트릭명
            - grain: 집계 단위
            - slots: NLU 슬롯 (time_window, group_by, filters 등)

        question: 원본 자연어 질문 (LLM 컨텍스트용)

        limit: 결과 행 제한 (기본값: 100)

        llm_provider: LLM 프로바이더 선택
            - "openai" (기본값)
            - "claude" / "anthropic"
            - "gemini" / "google"
            - None이면 settings에서 로드

        conversation_id: 대화 ID (컨텍스트 로드용)

    Returns:
        str: LLM이 생성한 BigQuery SQL

    Example:
        >>> plan = {
        ...     "intent": "metric_over_time",
        ...     "metric": "orders",
        ...     "grain": "day",
        ...     "slots": {"time_window": {"days": 7}}
        ... }
        >>> sql = generate(plan, "지난 7일 주문 추이", limit=10)
        '''
        SELECT
          DATE(TIMESTAMP_MICROS(event_timestamp)) AS day,
          SUM(CASE WHEN event_name='purchase' THEN 1 ELSE 0 END) AS orders
        FROM `ns-extr-data.analytics_310486481.events_*`
        WHERE _TABLE_SUFFIX BETWEEN '20251031' AND '20251106'
        GROUP BY day
        ORDER BY day
        LIMIT 10
        '''

    Raises:
        Exception: LLM 호출 실패 또는 SQL 생성 실패 시
    """
    # 1. LLM 프로바이더 결정
    provider = llm_provider or settings.llm_provider or "openai"
    logger.info(f"Generating SQL using LLM provider: {provider}")

    # 2. 대화 컨텍스트 로드
    context = get_context(conversation_id or "")

    # 3. 시맨틱 모델 로드
    semantic_root = load_semantic_root()
    semantic_model = semantic_root.get("semantic.yml", {})

    # 4. GA4 테이블 날짜 범위 결정
    table_suffix_info = _determine_table_suffix(plan, question, context)

    # 5. 필요한 테이블 및 JOIN 분석
    required_tables = _analyze_required_tables(plan, semantic_model)

    # 6. LLM 프롬프트 구성
    prompt = _build_sql_generation_prompt(
        question=question,
        plan=plan,
        semantic_model=semantic_model,
        table_suffix_info=table_suffix_info,
        required_tables=required_tables,
        context=context,
        limit=limit
    )

    # 7. LLM 호출하여 SQL 생성
    sql = _call_llm_for_sql(prompt, provider)

    # 8. SQL 후처리
    sql = _post_process_sql(sql, limit)

    logger.info(f"Generated SQL successfully (length: {len(sql)} chars)")

    return sql


def _determine_table_suffix(
    plan: Dict[str, Any],
    question: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    GA4 테이블의 날짜 서픽스를 결정합니다.

    질문의 시간 범위(time_window)와 대화 컨텍스트, 질문 텍스트를 분석하여
    조회할 GA4 테이블의 날짜 범위를 결정합니다.

    Args:
        plan: 실행 계획 (time_window 슬롯 포함)
        question: 원본 질문 (날짜 추론용)
        context: 대화 컨텍스트 (이전 날짜 참조)

    Returns:
        Dict[str, Any]:
            - use_wildcard: 와일드카드 사용 여부 (events_*)
            - start_date: 시작 날짜 (YYYYMMDD)
            - end_date: 종료 날짜 (YYYYMMDD)
            - suffix_condition: _TABLE_SUFFIX 조건문

    Example:
        >>> _determine_table_suffix(
        ...     {"slots": {"time_window": {"days": 7}}},
        ...     "지난 7일",
        ...     {}
        ... )
        {
            "use_wildcard": True,
            "start_date": "20251104",
            "end_date": "20251110",
            "suffix_condition": "_TABLE_SUFFIX BETWEEN '20251104' AND '20251110'"
        }

        >>> _determine_table_suffix(
        ...     {"slots": {}},
        ...     "오늘 방문자",
        ...     {}
        ... )
        {
            "use_wildcard": False,
            "start_date": "20251110",
            "end_date": "20251110",
            "suffix_condition": "_TABLE_SUFFIX = '20251110'"
        }
    """
    slots = plan.get("slots", {})
    time_window = slots.get("time_window", {})

    # 오늘 날짜
    today = datetime.now()

    # 질문 텍스트에서 날짜 키워드 감지
    question_lower = question.lower()

    # 1. time_window 슬롯이 있으면 사용
    if time_window:
        days = time_window.get("days")
        weeks = time_window.get("weeks")
        months = time_window.get("months")

        if days:
            if days == 1:
                # "지난 1일" 또는 "어제" → 어제만
                target_date = today - timedelta(days=1)
                start_date = target_date
                end_date = target_date
            else:
                # "지난 7일" → 7일 전부터 오늘까지
                start_date = today - timedelta(days=days - 1)  # -1 수정: 오늘 포함
                end_date = today
        elif weeks:
            # "이번주" → 7일 전부터 오늘까지
            start_date = today - timedelta(days=weeks * 7 - 1)
            end_date = today
        elif months:
            # "이번달" → 30일 전부터 오늘까지
            start_date = today - timedelta(days=months * 30 - 1)
            end_date = today
        else:
            # time_window 있지만 값 없음 → 오늘만
            start_date = today
            end_date = today

    # 2. 질문 텍스트에서 특정 날짜 키워드 감지
    elif "오늘" in question_lower or "금일" in question_lower or "today" in question_lower:
        # "오늘" → 오늘만
        start_date = today
        end_date = today

    elif "어제" in question_lower or "yesterday" in question_lower:
        # "어제" → 어제만
        yesterday = today - timedelta(days=1)
        start_date = yesterday
        end_date = yesterday

    elif "그제" in question_lower or "이틀 전" in question_lower:
        # "그제" → 그제만
        day_before = today - timedelta(days=2)
        start_date = day_before
        end_date = day_before

    # 3. 기본값: 시간 범위 없으면 오늘만 (변경: 이전에는 30일)
    else:
        start_date = today
        end_date = today

    # YYYYMMDD 형식으로 변환
    start_suffix = start_date.strftime("%Y%m%d")
    end_suffix = end_date.strftime("%Y%m%d")

    # 단일 날짜 vs 범위
    use_wildcard = start_suffix != end_suffix

    if use_wildcard:
        suffix_condition = f"_TABLE_SUFFIX BETWEEN '{start_suffix}' AND '{end_suffix}'"
    else:
        suffix_condition = f"_TABLE_SUFFIX = '{end_suffix}'"

    logger.info(f"Table suffix determined: {start_suffix} to {end_suffix}, wildcard={use_wildcard}, today={today.strftime('%Y%m%d')}")

    return {
        "use_wildcard": use_wildcard,
        "start_date": start_suffix,
        "end_date": end_suffix,
        "suffix_condition": suffix_condition
    }


def _analyze_required_tables(
    plan: Dict[str, Any],
    semantic_model: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    쿼리에 필요한 테이블과 JOIN 관계를 분석합니다.

    시맨틱 모델의 엔티티와 관계(relationships)를 분석하여
    필요한 테이블 목록과 JOIN 조건을 추출합니다.

    Args:
        plan: 실행 계획
        semantic_model: 시맨틱 모델

    Returns:
        List[Dict[str, Any]]: 필요한 테이블 정보 리스트
            - entity: 엔티티명
            - table: 테이블명
            - alias: 테이블 별칭
            - join_type: JOIN 타입 (LEFT, INNER 등)
            - join_condition: JOIN 조건

    Example:
        [
            {
                "entity": "event",
                "table": "ns-extr-data.analytics_310486481.events_*",
                "alias": "e",
                "is_primary": True
            },
            {
                "entity": "session",
                "table": "ns-extr-data.analytics_310486481.sessions",
                "alias": "s",
                "join_type": "LEFT",
                "join_condition": "e.session_id = s.session_id",
                "is_primary": False
            }
        ]
    """
    # 현재는 단일 테이블만 지원 (MVP)
    # TODO: 향후 다중 테이블 JOIN 지원

    entities = semantic_model.get("entities", [])
    metric = plan.get("metric", "orders")

    # 메트릭이 속한 엔티티 찾기
    primary_entity = None
    for entity in entities:
        if not isinstance(entity, dict):
            continue

        measures = entity.get("measures", [])
        for measure in measures:
            if isinstance(measure, dict) and measure.get("name") == metric:
                primary_entity = entity
                break

        if primary_entity:
            break

    # 기본 엔티티 (event)
    if not primary_entity:
        for entity in entities:
            if isinstance(entity, dict) and entity.get("name") == "event":
                primary_entity = entity
                break

    if not primary_entity:
        # 폴백: GA4 이벤트 테이블
        return [{
            "entity": "event",
            "table": f"{GA4_TABLE_TEMPLATE}_*",
            "alias": "e",
            "is_primary": True
        }]

    # 주 테이블 정보 생성
    entity_name = primary_entity.get("name", "event")
    table_name = primary_entity.get("table", f"{GA4_TABLE_TEMPLATE}_*")

    # GA4 테이블이면 와일드카드 추가
    if "events" in table_name and not table_name.endswith("*"):
        # events_20251106 → events_*
        base_table = table_name.rsplit("_", 1)[0] if "_" in table_name else table_name
        table_name = f"{base_table}_*"

    tables = [{
        "entity": entity_name,
        "table": table_name,
        "alias": entity_name[0],  # 첫 글자를 별칭으로
        "is_primary": True
    }]

    # TODO: relationships를 분석하여 JOIN 테이블 추가
    # relationships = primary_entity.get("relationships", [])
    # for rel in relationships:
    #     tables.append({
    #         "entity": rel["to"],
    #         "table": ...,
    #         "join_type": "LEFT",
    #         "join_condition": rel["on"]
    #     })

    logger.info(f"Required tables: {[t['entity'] for t in tables]}")

    return tables


def _build_sql_generation_prompt(
    question: str,
    plan: Dict[str, Any],
    semantic_model: Dict[str, Any],
    table_suffix_info: Dict[str, Any],
    required_tables: List[Dict[str, Any]],
    context: Dict[str, Any],
    limit: Optional[int]
) -> str:
    """
    LLM을 위한 SQL 생성 프롬프트를 구성합니다.

    Args:
        question: 원본 질문
        plan: 실행 계획
        semantic_model: 시맨틱 모델
        table_suffix_info: GA4 테이블 서픽스 정보
        required_tables: 필요한 테이블 목록
        context: 대화 컨텍스트
        limit: 결과 행 제한

    Returns:
        str: LLM 프롬프트
    """
    # 엔티티 정보 추출
    entities_info = _format_entities_for_prompt(semantic_model)

    # 메트릭 정의 추출
    metrics_info = _format_metrics_for_prompt(semantic_model)

    # 메트릭 및 차원 목록 생성 (메타 질문용)
    metrics_list = _extract_metrics_list(semantic_model)
    dimensions_list = _extract_dimensions_list(semantic_model)

    # 테이블 정보 포맷팅
    tables_info = _format_tables_for_prompt(required_tables, table_suffix_info)

    # GA4 스키마 정보 추출
    ga4_schema_info = _format_ga4_schema_for_prompt(semantic_model)

    # 프롬프트 구성
    prompt = f"""당신은 BigQuery SQL 전문가입니다. 다음 자연어 질문을 BigQuery SQL로 변환하세요.

# 질문
{question}

# 실행 계획
- Intent: {plan.get('intent')}
- Metric: {plan.get('metric')}
- Grain: {plan.get('grain')}
- Slots: {json.dumps(plan.get('slots', {}), ensure_ascii=False)}

# 메타 질문 처리
질문이 "사용 가능한 차원/메트릭 알려줘", "어떤 분석 가능해?" 같은 **메타 질문**이면:
- 시맨틱 모델 정보를 자연어로 요약하는 SELECT 문 생성
- SQL이 아닌 정보성 결과를 반환하도록 함
- 예시:

```sql
SELECT
  '사용 가능한 메트릭' AS category,
  '{metrics_list}' AS available_items
UNION ALL
SELECT
  '사용 가능한 차원' AS category,
  '{dimensions_list}' AS available_items
UNION ALL
SELECT
  '예시 질문' AS category,
  '지난 7일 디바이스별 주문 추이, 국가별 매출 상위 10개' AS available_items
```

# 시맨틱 모델

## 엔티티 및 측정항목
{entities_info}

## 메트릭 정의
{metrics_info}

## 사용 가능한 메트릭 목록
{metrics_list}

## 사용 가능한 차원 목록
{dimensions_list}

# 테이블 정보
{tables_info}

# GA4 테이블 서픽스 처리
- 사용: {table_suffix_info['use_wildcard']}
- 날짜 범위: {table_suffix_info['start_date']} ~ {table_suffix_info['end_date']}
- 조건: {table_suffix_info['suffix_condition']}

# GA4 스키마 (중요!)
{ga4_schema_info}

# SQL 생성 규칙
1. BigQuery 표준 SQL 문법 사용
2. GA4 테이블은 events_* 와일드카드와 _TABLE_SUFFIX 조건 사용
3. event_timestamp는 INT64 마이크로초이므로 TIMESTAMP_MICROS() 변환 필수
4. **GA4 네스티드 필드는 반드시 dot notation 사용**:
   - device_category → device.category
   - traffic_medium → traffic_source.medium
   - geo_country → geo.country
5. **event_name 필터 필수 (중요!)**: GA4는 모든 이벤트가 하나의 테이블에 저장됨
   - "페이지 조회" → WHERE event_name = 'page_view'
   - "구매" → WHERE event_name = 'purchase'
   - "장바구니" → WHERE event_name = 'add_to_cart'
   - "세션 시작" → WHERE event_name = 'session_start'
   - "사용자 참여" → WHERE event_name = 'user_engagement'
   - "환불" → WHERE event_name = 'refund'
   - "상품조회" → WHERE event_name = 'view_item'
   - "로그인" → WHERE event_name = 'login'
   - "자동로그인" → WHERE event_name = 'auto_login'
   - "회원가입" → WHERE event_name = 'sign_up'
   - "클릭이벤트" → WHERE event_name = 'click'
   - "세션시작" → WHERE event_name = 'session_start'
   - "첫방문" → WHERE event_name = 'first_visit'
   - "로그아웃" → WHERE event_name = 'logout'
   - "장바구니제거" → WHERE event_name = 'remove_from_wishlist'
   - 질문의 문맥에 맞는 event_name 필터를 반드시 추가할 것
   - 예: "방문자별 페이지 오픈 수" → WHERE event_name = 'page_view'
6. 시맨틱 모델의 메트릭 정의(expr)를 정확히 따를 것
7. GROUP BY, ORDER BY는 grain에 맞게 생성
8. LIMIT {limit if limit else '없음'}

# 대화 컨텍스트
{_format_context_for_prompt(context)}

# 출력 형식
SQL 쿼리만 반환하세요. 설명이나 주석은 불필요합니다.
코드 블록 없이 순수 SQL만 반환하세요.
"""

    return prompt


def _format_entities_for_prompt(semantic_model: Dict[str, Any]) -> str:
    """엔티티 정보를 프롬프트용으로 포맷팅"""
    entities = semantic_model.get("entities", [])
    lines = []

    for entity in entities:
        if not isinstance(entity, dict):
            continue

        name = entity.get("name", "unknown")
        table = entity.get("table", "")
        dimensions = entity.get("dimensions", [])
        measures = entity.get("measures", [])

        lines.append(f"\n### {name}")
        lines.append(f"Table: {table}")

        if dimensions:
            lines.append("Dimensions:")
            for dim in dimensions:
                if isinstance(dim, dict):
                    lines.append(f"  - {dim.get('name')}")

        if measures:
            lines.append("Measures:")
            for measure in measures:
                if isinstance(measure, dict):
                    lines.append(f"  - {measure.get('name')}: {measure.get('expr', '')}")

    return "\n".join(lines)


def _format_metrics_for_prompt(semantic_model: Dict[str, Any]) -> str:
    """메트릭 정의를 프롬프트용으로 포맷팅"""
    metrics = semantic_model.get("metrics", [])
    lines = []

    for metric in metrics:
        if not isinstance(metric, dict):
            continue

        name = metric.get("name")
        expr = metric.get("expr")
        filters = metric.get("default_filters", [])

        lines.append(f"\n- {name}:")
        if expr:
            lines.append(f"  expr: {expr}")
        if filters:
            lines.append(f"  filters: {filters}")

    return "\n".join(lines)


def _format_tables_for_prompt(
    required_tables: List[Dict[str, Any]],
    table_suffix_info: Dict[str, Any]
) -> str:
    """테이블 정보를 프롬프트용으로 포맷팅"""
    lines = []

    for table in required_tables:
        entity = table.get("entity")
        table_name = table.get("table")
        alias = table.get("alias")
        is_primary = table.get("is_primary", False)

        lines.append(f"\n- {entity} (alias: {alias}):")
        lines.append(f"  table: `{table_name}`")
        if is_primary:
            lines.append("  (주 테이블)")

        if table.get("join_type"):
            lines.append(f"  join: {table['join_type']} JOIN ON {table.get('join_condition', '')}")

    return "\n".join(lines)


def _format_context_for_prompt(context: Dict[str, Any]) -> str:
    """대화 컨텍스트를 프롬프트용으로 포맷팅"""
    if not context:
        return "없음 (첫 질문)"

    lines = []
    if "last_sql" in context:
        lines.append(f"이전 SQL:\n{context['last_sql'][:200]}...")
    if "last_plan" in context:
        lines.append(f"이전 계획: {context['last_plan']}")

    return "\n".join(lines) if lines else "없음"


def _extract_metrics_list(semantic_model: Dict[str, Any]) -> str:
    """메트릭 목록을 간단한 문자열로 추출 (메타 질문용)"""
    metrics = semantic_model.get("metrics", [])
    metric_names = []

    for metric in metrics:
        if isinstance(metric, dict):
            name = metric.get("name")
            desc = metric.get("description", "")
            if name:
                if desc:
                    metric_names.append(f"{name} ({desc})")
                else:
                    metric_names.append(name)

    return ", ".join(metric_names) if metric_names else "orders, gmv, sessions, users, events"


def _extract_dimensions_list(semantic_model: Dict[str, Any]) -> str:
    """차원 목록을 간단한 문자열로 추출 (메타 질문용)"""
    entities = semantic_model.get("entities", [])
    dimension_names = []

    for entity in entities:
        if isinstance(entity, dict):
            entity_name = entity.get("name", "")
            dimensions = entity.get("dimensions", [])

            for dim in dimensions[:3]:  # 각 엔티티에서 상위 3개만
                if isinstance(dim, dict):
                    dim_name = dim.get("name")
                    if dim_name:
                        dimension_names.append(f"{entity_name}.{dim_name}")

    # GA4 common_dimensions도 추가
    common_dims = semantic_model.get("common_dimensions", {})
    if common_dims:
        # 상위 5개만
        for korean, field in list(common_dims.items())[:5]:
            if field not in dimension_names:
                dimension_names.append(f"{korean} ({field})")

    return ", ".join(dimension_names) if dimension_names else "event_date, device.category, geo.country, traffic_source.medium"


def _format_ga4_schema_for_prompt(semantic_model: Dict[str, Any]) -> str:
    """GA4 스키마 정보를 프롬프트용으로 포맷팅"""
    ga4_schema = semantic_model.get("ga4_schema", {})

    if not ga4_schema:
        return "GA4 스키마 정보 없음"

    lines = []
    lines.append("## GA4 네스티드 필드 (RECORD 타입)")
    lines.append("**중요**: 반드시 dot notation 사용!")
    lines.append("")

    # 일반 차원 매핑
    common_dims = semantic_model.get("common_dimensions", {})
    if common_dims:
        lines.append("### 한글 → 필드명 매핑")
        for korean, field in list(common_dims.items())[:10]:  # 상위 10개만
            lines.append(f"- {korean} → {field}")
        lines.append("")

    # 네스티드 필드 설명
    nested = ga4_schema.get("nested_fields", {})

    if nested.get("device"):
        lines.append("### Device 필드 (device.*)")
        lines.append("- device.category: mobile | desktop | tablet")
        lines.append("- device.operating_system: Windows, iOS, Android")
        lines.append("- device.browser: Chrome, Safari, Firefox")
        lines.append("")

    if nested.get("geo"):
        lines.append("### Geo 필드 (geo.*)")
        lines.append("- geo.country: KR, US, JP (국가 코드)")
        lines.append("- geo.city: 도시명")
        lines.append("")

    if nested.get("traffic_source"):
        lines.append("### Traffic Source 필드 (traffic_source.*)")
        lines.append("- traffic_source.source: google, facebook, direct")
        lines.append("- traffic_source.medium: organic, cpc, referral")
        lines.append("")

    # REPEATED 필드 (event_params, items)
    lines.append("### REPEATED 필드 (UNNEST 필요)")
    lines.append("")
    lines.append("**event_params** (페이지, 세션 정보 등):")
    lines.append("```sql")
    lines.append("-- 페이지 URL: (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') AS page_url")
    lines.append("-- 페이지 경로: (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_path') AS page_path")
    lines.append("-- 페이지 제목: (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_title') AS page_title")
    lines.append("-- 세션 ID: (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS session_id")
    lines.append("```")
    lines.append("")

    lines.append("**items** (E-commerce 상품):")
    lines.append("```sql")
    lines.append("-- FROM table, UNNEST(items) AS item")
    lines.append("-- item.item_id, item.item_name, item.price, item.quantity")
    lines.append("```")
    lines.append("")

    # 주의사항
    notes = semantic_model.get("notes", [])
    if notes:
        lines.append("### 중요 주의사항")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    # 추가 주의사항
    lines.append("**event_params 필드 사용법:**")
    lines.append("- page, page_url, page_path, page_title은 event_params에서 UNNEST로 추출")
    lines.append("- 직접 e.page 사용 금지 (GA4에는 최상위 page 필드 없음)")
    lines.append("- 세션 ID도 event_params에서 추출")

    return "\n".join(lines)


def _call_llm_for_sql(prompt: str, provider: str) -> str:
    """
    LLM을 호출하여 SQL을 생성합니다.

    Args:
        prompt: SQL 생성 프롬프트
        provider: LLM 프로바이더 (openai, claude, gemini)

    Returns:
        str: LLM이 생성한 SQL

    Raises:
        Exception: LLM 호출 실패 시
    """
    logger.info(f"Calling LLM provider: {provider}")

    if provider == "openai":
        return _call_openai_for_sql(prompt)
    elif provider in ["claude", "anthropic"]:
        return _call_anthropic_for_sql(prompt)
    elif provider in ["gemini", "google", "gcp"]:
        return _call_gemini_for_sql(prompt)
    else:
        raise Exception(f"Unsupported LLM provider: {provider}")


def _call_openai_for_sql(prompt: str) -> str:
    """OpenAI API를 사용하여 SQL 생성"""
    try:
        import openai

        api_key = settings.openai_api_key
        if not api_key:
            raise Exception("OpenAI API key not configured")

        client = openai.OpenAI(api_key=api_key)

        # OpenAI 최신 모델은 max_completion_tokens 사용
        model = settings.openai_model or "gpt-4o-mini"
        token_param = {}

        # 최신 모델은 max_completion_tokens 사용
        # gpt-4o, gpt-5, o1, o3 시리즈
        if any(x in model for x in ["gpt-4o", "gpt-5", "o1-", "o3-"]):
            token_param["max_completion_tokens"] = settings.llm_max_tokens or 2048
        else:
            # 이전 모델 (gpt-3.5, gpt-4 등)은 max_tokens 사용
            token_param["max_tokens"] = settings.llm_max_tokens or 2048

        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a BigQuery SQL expert. Generate SQL queries based on semantic models and user questions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=settings.llm_temperature or 0.1,
            **token_param
        )

        sql = response.choices[0].message.content or ""
        logger.info("OpenAI SQL generation successful (tokens: %d)", response.usage.total_tokens)

        return sql

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise Exception(f"OpenAI SQL generation failed: {e}")


def _call_anthropic_for_sql(prompt: str) -> str:
    """Anthropic Claude API를 사용하여 SQL 생성"""
    try:
        import anthropic

        api_key = settings.anthropic_api_key
        if not api_key:
            raise Exception("Anthropic API key not configured")

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=settings.anthropic_model or "claude-3-5-sonnet-20240620",
            max_tokens=settings.llm_max_tokens or 2048,
            temperature=settings.llm_temperature or 0.1,
            system="You are a BigQuery SQL expert. Generate SQL queries based on semantic models and user questions.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        sql = response.content[0].text
        logger.info("Claude SQL generation successful")

        return sql

    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        raise Exception(f"Claude SQL generation failed: {e}")


def _call_gemini_for_sql(prompt: str) -> str:
    """Google Gemini API를 사용하여 SQL 생성"""
    try:
        import google.generativeai as genai

        api_key = settings.gemini_api_key
        if not api_key:
            raise Exception("Gemini API key not configured")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings.gemini_model or "gemini-1.5-flash")

        system_prompt = "You are a BigQuery SQL expert. Generate SQL queries based on semantic models and user questions."
        full_prompt = f"{system_prompt}\n\n{prompt}"

        response = model.generate_content(
            full_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=settings.llm_temperature or 0.1,
                max_output_tokens=settings.llm_max_tokens or 2048
            )
        )

        sql = response.text
        logger.info("Gemini SQL generation successful")

        return sql

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        raise Exception(f"Gemini SQL generation failed: {e}")


def _post_process_sql(sql: str, limit: Optional[int]) -> str:
    """
    LLM이 생성한 SQL을 후처리합니다.

    Args:
        sql: LLM이 생성한 원본 SQL
        limit: 결과 행 제한

    Returns:
        str: 후처리된 SQL
    """
    # 1. 코드 블록 제거
    if "```sql" in sql:
        sql = sql.split("```sql")[1].split("```")[0]
    elif "```" in sql:
        sql = sql.split("```")[1].split("```")[0]

    # 2. 앞뒤 공백 제거
    sql = sql.strip()

    # 3. LIMIT 절 추가 (없는 경우)
    if limit and "LIMIT" not in sql.upper():
        sql += f"\nLIMIT {int(limit)}"

    # 4. 세미콜론 제거 (BigQuery는 불필요)
    if sql.endswith(";"):
        sql = sql[:-1].strip()

    return sql
