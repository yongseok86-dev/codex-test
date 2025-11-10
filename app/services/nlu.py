"""
자연어 이해 (NLU: Natural Language Understanding) 모듈

사용자의 자연어 질문에서 의도(intent)와 슬롯(slots)을 추출합니다.
하이브리드 방식을 사용하여 간단한 질문은 빠른 키워드 매칭으로,
복잡한 질문은 LLM 기반으로 처리합니다.

주요 개념:
    - Intent (의도): 사용자가 원하는 작업 유형
        * "metric": 단순 메트릭 조회 (예: "오늘 매출은?")
        * "metric_over_time": 시간 추이 분석 (예: "지난 7일 매출 추이")
        * "comparison": 비교 분석 (예: "이번달과 지난달 비교")
        * "aggregation": 집계 분석 (예: "디바이스별 매출")

    - Slots (슬롯): 질문에서 추출한 구체적인 정보
        * "metric": 조회할 메트릭 (gmv, orders, sessions 등)
        * "time_window": 시간 범위 (예: {"days": 7})
        * "grain": 집계 단위 (day, week, month)
        * "group_by": 그룹핑 기준 (device, channel 등)
        * "filters": 필터 조건 (예: {"device": "mobile"})

하이브리드 전략:
    1. 키워드 기반 추출 시도 (빠른 처리)
    2. 신뢰도 계산 (슬롯 추출 성공률 기반)
    3. 신뢰도 낮으면 LLM으로 재추출 (정확도 향상)

키워드 관리:
    - 모든 NLU 키워드는 semantic.yml의 nlu_keywords 섹션에서 관리
    - 키워드 추가/수정 시 코드 변경 불필요, YAML만 수정
    - 다국어 지원 용이 (한국어/영어 동시 지원)

예시:
    질문: "지난 7일 주문 추이"
    → 키워드 매칭 성공 (신뢰도: 1.0)
    → intent: "metric_over_time"
    → slots: {"metric": "orders", "time_window": {"days": 7}}

    질문: "작년 같은 기간 대비 올해 모바일 매출 성장률은?"
    → 키워드 매칭 실패 (신뢰도: 0.3)
    → LLM 호출
    → intent: "comparison"
    → slots: {"metric": "gmv", "group_by": ["device"], "filters": {"device": "mobile"}}
"""
from typing import Any, Dict, Tuple, Optional
import json
from app.config import settings
from app.deps import get_logger
from app.semantic.loader import load_semantic_root

logger = get_logger(__name__)

# 시맨틱 모델에서 NLU 키워드 로드 (캐시)
_NLU_KEYWORDS: Optional[Dict[str, Any]] = None


def _load_nlu_keywords() -> Dict[str, Any]:
    """
    시맨틱 모델에서 NLU 키워드를 로드합니다.

    Returns:
        Dict[str, Any]: NLU 키워드 설정
            - intents: 의도 키워드 매핑
            - metrics: 메트릭 키워드 매핑
            - time_windows: 시간 범위 키워드 매핑
            - group_by: 그룹핑 키워드 매핑
            - filters: 필터 키워드 매핑
            - grains: 집계 단위 키워드 매핑
    """
    global _NLU_KEYWORDS

    if _NLU_KEYWORDS is not None:
        return _NLU_KEYWORDS

    try:
        semantic_root = load_semantic_root()
        semantic_model = semantic_root.get("semantic.yml", {})
        keywords = semantic_model.get("nlu_keywords", {}) if isinstance(semantic_model, dict) else {}

        if not keywords:
            logger.warning("No nlu_keywords found in semantic.yml, using empty keywords")
            keywords = {
                "intents": {},
                "metrics": {},
                "time_windows": {},
                "group_by": {},
                "filters": {},
                "grains": {}
            }

        _NLU_KEYWORDS = keywords
        logger.info(f"Loaded NLU keywords: {len(keywords.get('intents', {}))} intents, "
                   f"{len(keywords.get('metrics', {}))} metrics, "
                   f"{len(keywords.get('time_windows', {}))} time_windows")

        return _NLU_KEYWORDS

    except Exception as e:
        logger.error(f"Failed to load NLU keywords from semantic model: {e}")
        # 폴백: 빈 키워드 반환
        return {
            "intents": {},
            "metrics": {},
            "time_windows": {},
            "group_by": {},
            "filters": {},
            "grains": {}
        }


def extract(q: str, use_llm: bool = True) -> Tuple[str, Dict[str, Any]]:
    """
    자연어 질문에서 의도(intent)와 슬롯(slots)을 추출합니다 (하이브리드 방식).

    1차: 키워드 매칭으로 빠른 추출 시도
    2차: 신뢰도가 낮으면 LLM으로 재추출

    Args:
        q: 사용자 입력 자연어 질문 (정규화 완료된 텍스트)
        use_llm: LLM 사용 여부 (기본값: True)

    Returns:
        Tuple[str, Dict[str, Any]]:
            - intent: 의도 문자열
            - slots: 추출된 슬롯 정보 딕셔너리

    Example:
        >>> extract("지난 7일 매출 추이")
        ("metric_over_time", {"metric": "gmv", "time_window": {"days": 7}})

        >>> extract("작년 대비 올해 모바일 매출 증가율")
        ("comparison", {"metric": "gmv", "filters": {"device": "mobile"}})
    """
    # 1단계: 키워드 기반 추출 (빠른 처리)
    intent, slots = _extract_keyword_based(q)
    confidence = _calculate_confidence(q, intent, slots)

    logger.info(f"Keyword-based extraction: intent={intent}, slots={slots}, confidence={confidence:.2f}")

    # 2단계: 신뢰도 검사 및 LLM 보완
    if use_llm and confidence < 0.7 and settings.llm_provider:
        logger.info("Low confidence, attempting LLM-based extraction")
        try:
            llm_intent, llm_slots = _extract_llm_based(q)
            if llm_intent and llm_slots:
                logger.info(f"LLM extraction successful: intent={llm_intent}, slots={llm_slots}")
                return llm_intent, llm_slots
        except Exception as e:
            logger.warning(f"LLM extraction failed: {e}, falling back to keyword-based result")

    return intent, slots


def _extract_keyword_based(q: str) -> Tuple[str, Dict[str, Any]]:
    """
    키워드 매칭 기반으로 의도와 슬롯을 추출합니다 (빠른 처리).

    시맨틱 모델(semantic.yml)의 nlu_keywords 섹션에서 키워드를 로드하여 사용합니다.
    키워드 추가/수정 시 YAML 파일만 수정하면 되며, 코드 변경은 불필요합니다.

    Args:
        q: 사용자 입력 질문

    Returns:
        Tuple[str, Dict[str, Any]]: (intent, slots)
    """
    text = q.lower()
    slots: Dict[str, Any] = {}

    # 시맨틱 모델에서 NLU 키워드 로드
    keywords = _load_nlu_keywords()

    # 1. 의도(Intent) 감지
    # semantic.yml의 nlu_keywords.intents에서 키워드 로드
    intent = "metric"  # 기본값
    intents_config = keywords.get("intents", {})

    for intent_name, intent_keywords in intents_config.items():
        if any(k.lower() in text for k in intent_keywords):
            intent = intent_name
            break  # 첫 번째 매칭된 의도 사용

    # 2. 메트릭(Metric) 추출
    # semantic.yml의 nlu_keywords.metrics에서 키워드 로드
    metrics_config = keywords.get("metrics", {})

    for metric_name, metric_keywords in metrics_config.items():
        if any(k.lower() in text for k in metric_keywords):
            slots["metric"] = metric_name
            break  # 첫 번째 매칭된 메트릭 사용

    # 3. 시간 범위(Time Window) 추출
    # semantic.yml의 nlu_keywords.time_windows에서 키워드 로드
    # 키 형식: days_7 → {"days": 7}, weeks_1 → {"weeks": 1}
    time_windows_config = keywords.get("time_windows", {})

    for time_key, time_keywords in time_windows_config.items():
        if any(k.lower() in text for k in time_keywords):
            # 키 파싱: "days_7" → {"days": 7}
            parts = time_key.split("_")
            if len(parts) == 2:
                unit, value = parts[0], parts[1]
                try:
                    slots["time_window"] = {unit: int(value)}
                    break
                except ValueError:
                    logger.warning(f"Invalid time_window key format: {time_key}")

    # 4. 그룹핑(Group By) 추출
    # semantic.yml의 nlu_keywords.group_by에서 키워드 로드
    group_by = []
    group_by_config = keywords.get("group_by", {})

    for group_name, group_keywords in group_by_config.items():
        if any(k.lower() in text for k in group_keywords):
            group_by.append(group_name)

    if group_by:
        slots["group_by"] = group_by

    # 5. 필터(Filters) 추출
    # semantic.yml의 nlu_keywords.filters에서 키워드 로드
    # 키 형식: device_mobile → {"device_category": "mobile"}
    filters = {}
    filters_config = keywords.get("filters", {})

    for filter_key, filter_keywords in filters_config.items():
        if any(k.lower() in text for k in filter_keywords):
            # 키 파싱: "device_mobile" → {"device_category": "mobile"}
            parts = filter_key.split("_")
            if len(parts) == 2:
                field, value = parts[0], parts[1]
                # 필드명 매핑
                if field == "device":
                    filters["device_category"] = value
                elif field == "status":
                    filters["status"] = value
                else:
                    filters[field] = value

    if filters:
        slots["filters"] = filters

    # 6. 집계 단위(Grain) 추출
    # semantic.yml의 nlu_keywords.grains에서 키워드 로드
    grains_config = keywords.get("grains", {})

    for grain_name, grain_keywords in grains_config.items():
        if any(k.lower() in text for k in grain_keywords):
            slots["grain"] = grain_name
            break  # 첫 번째 매칭된 grain 사용

    return intent, slots


def _calculate_confidence(q: str, intent: str, slots: Dict[str, Any]) -> float:
    """
    키워드 기반 추출 결과의 신뢰도를 계산합니다.

    신뢰도 계산 기준:
    - metric 슬롯 있음: +0.4
    - time_window 또는 grain 있음: +0.3
    - group_by 또는 filters 있음: +0.2
    - intent가 기본값(metric)이 아님: +0.1

    Args:
        q: 원본 질문
        intent: 추출된 의도
        slots: 추출된 슬롯

    Returns:
        float: 신뢰도 (0.0 ~ 1.0)
    """
    confidence = 0.0

    # 메트릭 추출 성공
    if "metric" in slots:
        confidence += 0.4

    # 시간 정보 추출 성공
    if "time_window" in slots or "grain" in slots:
        confidence += 0.3

    # 고급 슬롯 추출 성공
    if "group_by" in slots or "filters" in slots:
        confidence += 0.2

    # 의도가 기본값이 아님
    if intent != "metric":
        confidence += 0.1

    # 질문이 너무 짧으면 신뢰도 감소
    if len(q) < 5:
        confidence *= 0.5

    # 복잡한 표현이 있으면 신뢰도 감소
    complex_keywords = ["대비", "비교", "증가율", "감소율", "비율", "평균", "같은 기간"]
    if any(k in q for k in complex_keywords):
        confidence *= 0.7

    return min(confidence, 1.0)


def _extract_llm_based(q: str) -> Tuple[str, Dict[str, Any]]:
    """
    LLM을 사용하여 의도와 슬롯을 추출합니다 (정확도 높음).

    Args:
        q: 사용자 입력 질문

    Returns:
        Tuple[str, Dict[str, Any]]: (intent, slots)

    Raises:
        Exception: LLM 호출 실패 시
    """
    provider = settings.llm_provider

    # LLM 프롬프트 구성
    prompt = f"""다음 자연어 질문을 분석하여 JSON 형식으로 의도(intent)와 슬롯(slots)을 추출하세요.

질문: "{q}"

응답 형식 (JSON만 반환):
{{
  "intent": "metric | metric_over_time | comparison | aggregation",
  "slots": {{
    "metric": "gmv | orders | sessions | users | events",
    "time_window": {{"days": 7}},
    "grain": "day | week | month",
    "group_by": ["device_category", "source_medium"],
    "filters": {{"device_category": "mobile"}}
  }}
}}

규칙:
1. intent는 반드시 하나만 선택
2. slots는 질문에서 추출 가능한 것만 포함
3. JSON 형식만 반환 (설명 불필요)
"""

    # LLM 호출
    if provider == "openai":
        result = _call_openai(prompt)
    elif provider in ["claude", "anthropic"]:
        result = _call_anthropic(prompt)
    elif provider in ["gemini", "google", "gcp"]:
        result = _call_gemini(prompt)
    else:
        raise Exception(f"Unsupported LLM provider: {provider}")

    # JSON 파싱
    try:
        # 코드 블록 제거
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]

        data = json.loads(result.strip())
        intent = data.get("intent", "metric")
        slots = data.get("slots", {})

        return intent, slots
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {result}")
        raise Exception(f"Invalid JSON from LLM: {e}")


def _call_openai(prompt: str) -> str:
    """OpenAI API 호출"""
    try:
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)

        # OpenAI 최신 모델은 max_completion_tokens 사용
        model = settings.openai_model or "gpt-4o-mini"
        token_param = {}

        if any(x in model for x in ["gpt-4o", "gpt-5", "o1-", "o3-"]):
            token_param["max_completion_tokens"] = 500
        else:
            token_param["max_tokens"] = 500

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            **token_param
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise Exception(f"OpenAI API error: {e}")


def _call_anthropic(prompt: str) -> str:
    """Anthropic Claude API 호출"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model or "claude-sonnet-4-5",
            max_tokens=500,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
    except Exception as e:
        raise Exception(f"Anthropic API error: {e}")


def _call_gemini(prompt: str) -> str:
    """Google Gemini API 호출"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model or "gemini-2.5-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=500
            )
        )
        return response.text
    except Exception as e:
        raise Exception(f"Gemini API error: {e}")

