"""
스키마 링킹 (Schema Linking) 모듈 - LLM 기반 개선 버전

사용자 질문에서 언급된 단어들을 데이터베이스의 테이블, 컬럼, 별칭과 매칭합니다.
하이브리드 방식: 토큰 기반 빠른 매칭 + LLM 기반 의미적 매칭

주요 역할:
    - 질문 토큰화 (한글, 영문 지원)
    - 시맨틱 모델 어휘(vocabulary) 활용
    - 별칭(aliases) 매칭 (한글 → 영문 컬럼명)
    - LLM 기반 의미적 스키마 링킹
    - 테이블명/컬럼명 매칭
    - 후보 점수화 및 정렬

하이브리드 전략:
    1. 토큰 + 동의어 기반 빠른 매칭 (우선)
    2. 신뢰도 < 0.6이면 LLM 기반 의미 분석
    3. 시맨틱 모델의 vocabulary.synonyms 활용

매칭 우선순위:
    1. 별칭 매칭 (점수: 2.0) - 가장 높음
    2. 동의어 매칭 (점수: 1.8) - 시맨틱 모델 어휘
    3. 테이블명 매칭 (점수: 1.0)
    4. 컬럼명 정확 매칭 (점수: 1.0)
    5. 컬럼명 부분 매칭 (점수: 0.5)

출력:
    - candidates: 매칭된 스키마 요소 리스트 (점수순 정렬)
    - confidence: 전체 매칭 신뢰도 (0.0 ~ 1.0)
    - method: 사용된 매칭 방법 ("token" | "llm" | "hybrid")

예시:
    질문: "주문일별 채널별 매출액"

    매칭 결과:
    - "주문일" → alias → "order.order_date" (score: 2.0)
    - "채널" → alias → "session.source_medium" (score: 2.0)
    - "매출액" → alias → "order.gmv" (score: 2.0)

    confidence: 1.0 (매우 높음)
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional
import re
import yaml
import json
from pathlib import Path
from app.schema.catalog import load_catalog
from app.semantic.loader import load_semantic_root
from app.config import settings
from app.deps import get_logger

logger = get_logger(__name__)


def _tokens(q: str) -> List[str]:
    """
    질문을 토큰(단어)으로 분리합니다.

    한글과 영문 단어를 추출하고 소문자로 변환합니다.
    특수문자, 공백 등은 제거됩니다.

    Args:
        q: 질문 문자열

    Returns:
        List[str]: 추출된 토큰 리스트 (소문자)

    Example:
        >>> _tokens("지난 7일 주문 추이")
        ["지난", "7일", "주문", "추이"]

        >>> _tokens("Device별 Revenue")
        ["device별", "revenue"]
    """
    # 정규식: 영문자, 숫자, 한글 매칭
    # \w: 영문자, 숫자, 언더스코어
    # 가-힣: 한글 음절
    return re.findall(r"[\w가-힣]+", (q or "").lower())


def schema_link(question: str, use_llm: bool = True) -> Dict[str, Any]:
    """
    질문에서 언급된 단어를 스키마 요소(테이블, 컬럼, 별칭)와 매칭합니다 (하이브리드).

    1차: 토큰 + 동의어 기반 빠른 매칭
    2차: 신뢰도 낮으면 LLM 기반 의미 분석

    Args:
        question: 사용자 질문 (정규화 완료된 텍스트)
        use_llm: LLM 사용 여부 (기본값: True)

    Returns:
        Dict[str, Any]:
            - candidates: 매칭된 후보 리스트 (점수 역순 정렬)
                * type: "alias" | "table" | "column" | "synonym"
                * name: 스키마 요소명
                * score: 매칭 점수 (높을수록 관련성 높음)
                * table: 컬럼인 경우 소속 테이블명
            - confidence: 전체 매칭 신뢰도 (0.0 ~ 1.0)
            - method: 사용된 방법 ("token" | "llm" | "hybrid")

    Example:
        >>> schema_link("주문일별 채널별 매출액")
        {
            "candidates": [
                {"type": "alias", "name": "order.order_date", "score": 2.0},
                {"type": "alias", "name": "session.source_medium", "score": 2.0},
                {"type": "alias", "name": "order.gmv", "score": 2.0}
            ],
            "confidence": 1.0,
            "method": "token"
        }

        >>> schema_link("작년 대비 올해 구매 증가율")  # 복잡한 질문
        {
            "candidates": [
                {"type": "synonym", "name": "order.orders", "score": 1.8},  # "구매" → "주문"
                {"type": "column", "name": "order_date", "score": 1.5}
            ],
            "confidence": 0.8,
            "method": "llm"
        }
    """
    # 1단계: 토큰 + 동의어 기반 매칭
    result = _schema_link_token_based(question)
    confidence = result["confidence"]

    logger.info(f"Token-based linking: confidence={confidence:.2f}, candidates={len(result['candidates'])}")

    # 2단계: 신뢰도 낮으면 LLM 보완
    if use_llm and confidence < 0.6 and settings.llm_provider:
        logger.info("Low confidence, attempting LLM-based linking")
        try:
            llm_result = _schema_link_llm_based(question)
            if llm_result and llm_result.get("confidence", 0) > confidence:
                logger.info(f"LLM linking successful: confidence={llm_result['confidence']:.2f}")
                llm_result["method"] = "llm"
                return llm_result
        except Exception as e:
            logger.warning(f"LLM linking failed: {e}, using token-based result")

    result["method"] = "token"
    return result


def _schema_link_token_based(question: str) -> Dict[str, Any]:
    """
    토큰 + 동의어 기반 스키마 링킹 (빠른 매칭).

    Args:
        question: 사용자 질문

    Returns:
        Dict[str, Any]: 링킹 결과
    """
    # 1. 질문 토큰화
    toks = set(_tokens(question))
    logger.debug(f"Question tokens: {toks}")

    # 2. 카탈로그 로드 (테이블 및 컬럼 정보)
    cat = load_catalog()

    # 3. 시맨틱 모델 어휘(vocabulary) 로드
    semantic_root = load_semantic_root()
    semantic_model = semantic_root.get("semantic.yml", {})
    vocab = semantic_model.get("vocabulary", {}) if isinstance(semantic_model, dict) else {}
    synonyms = vocab.get("synonyms", {}) if isinstance(vocab, dict) else {}

    logger.debug(f"Loaded {len(synonyms)} synonym groups from semantic model")

    # 4. 별칭(Aliases) 로드
    # aliases.yaml 파일에서 한글 → 영문 컬럼명 매핑 로드
    aliases = {}
    p = Path(__file__).resolve().parents[1] / "schema" / "aliases.yaml"
    if p.exists():
        try:
            aliases = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            logger.debug(f"Loaded {len(aliases)} aliases")
        except Exception as e:
            logger.warning(f"Failed to load aliases: {e}")
            aliases = {}

    candidates: List[Dict[str, Any]] = []

    # 5. 별칭 매칭 (우선순위 1: 점수 2.0)
    # 한글 용어가 질문에 있으면 매핑된 영문 컬럼명을 후보로 추가
    for k, v in aliases.items():
        if str(k).lower() in toks:
            candidates.append({
                "type": "alias",
                "name": v,
                "score": 2.0
            })
            logger.debug(f"Alias match: '{k}' → '{v}'")

    # 6. 동의어 매칭 (우선순위 2: 점수 1.8)
    # 시맨틱 모델의 vocabulary.synonyms 활용
    # 예: "구매" → "주문" 동의어 그룹
    for canonical, synonym_list in synonyms.items():
        # canonical이 토큰에 있거나, synonym_list에 토큰이 있으면 매칭
        canonical_lower = str(canonical).lower()
        matched_synonym = None

        # canonical 자체가 매칭되는지 확인
        if canonical_lower in toks:
            matched_synonym = canonical

        # synonym_list에서 매칭 확인
        if not matched_synonym:
            for syn in synonym_list:
                if str(syn).lower() in toks:
                    matched_synonym = syn
                    break

        if matched_synonym:
            # canonical을 메트릭/컬럼명으로 매핑 시도
            # 예: "주문" → "order.orders" 또는 "orders" 메트릭
            candidates.append({
                "type": "synonym",
                "name": canonical,
                "matched_term": matched_synonym,
                "score": 1.8
            })
            logger.debug(f"Synonym match: '{matched_synonym}' → canonical '{canonical}'")

    # 7. 테이블명 매칭 (우선순위 3: 점수 1.0)
    # 테이블명에 질문 토큰이 포함되어 있으면 후보로 추가
    for tkey, table in (cat.tables or {}).items():
        tname = table.name.lower()
        if any(tok in tname for tok in toks):
            candidates.append({
                "type": "table",
                "name": table.name,
                "score": 1.0
            })
            logger.debug(f"Table match: '{table.name}'")

        # 8. 컬럼명 매칭 (우선순위 4: 점수 0.5 ~ 1.5)
        for c in table.columns:
            cname = c.name.lower()
            score = 0.0

            # 6-1. 컬럼명 정확 매칭 (전체 일치)
            if cname in toks:
                score += 1.0

            # 6-2. 컬럼명 부분 매칭 (토큰이 컬럼명에 포함)
            if any(tok in cname for tok in toks):
                score += 0.5

            # 점수가 있으면 후보로 추가
            if score > 0:
                candidates.append({
                    "type": "column",
                    "name": c.name,
                    "table": table.name,
                    "score": score
                })
                logger.debug(f"Column match: '{c.name}' in '{table.name}' (score: {score})")

    # 9. 전체 신뢰도 계산
    # 총 점수를 5로 나눔 (휴리스틱: 5개 매칭되면 완전 신뢰)
    # 최대값 1.0으로 제한
    total_score = sum(x["score"] for x in candidates)
    conf = min(1.0, total_score / max(1, 5))

    logger.info(f"Token-based schema linking: {len(candidates)} candidates, confidence={conf:.2f}")

    # 10. 후보를 점수 역순으로 정렬하여 반환
    return {
        "candidates": sorted(candidates, key=lambda x: x["score"], reverse=True),
        "confidence": conf
    }


def _schema_link_llm_based(question: str) -> Optional[Dict[str, Any]]:
    """
    LLM을 사용하여 의미적 스키마 링킹을 수행합니다.

    질문의 의미를 이해하고 시맨틱 모델의 엔티티, 차원, 메트릭과
    의미적으로 연결합니다.

    Args:
        question: 사용자 질문

    Returns:
        Optional[Dict[str, Any]]: 링킹 결과 또는 None (실패 시)

    Raises:
        Exception: LLM 호출 실패 시
    """
    # 시맨틱 모델 로드
    semantic_root = load_semantic_root()
    semantic_model = semantic_root.get("semantic.yml", {})

    # 카탈로그 로드
    cat = load_catalog()

    # 사용 가능한 스키마 요소 목록 생성
    available_schema = _format_schema_for_llm(semantic_model, cat)

    # LLM 프롬프트 구성
    prompt = f"""다음 질문에서 언급된 개념을 데이터베이스 스키마 요소와 매칭하세요.

# 질문
{question}

# 사용 가능한 스키마 요소
{available_schema}

# 출력 형식 (JSON만 반환)
{{
  "candidates": [
    {{
      "type": "table | column | metric",
      "name": "스키마 요소명",
      "table": "소속 테이블 (컬럼인 경우)",
      "score": 0.0-2.0,
      "reason": "매칭 이유"
    }}
  ],
  "confidence": 0.0-1.0
}}

# 매칭 규칙
1. 질문의 개념과 의미적으로 관련된 스키마 요소만 선택
2. score는 관련성에 따라 0.5(약함) ~ 2.0(강함)
3. confidence는 전체 매칭 확신도
4. JSON 형식만 반환 (설명 불필요)
"""

    # LLM 호출
    provider = settings.llm_provider or "openai"
    logger.info(f"Calling LLM for schema linking: {provider}")

    try:
        if provider == "openai":
            result = _call_openai_for_linking(prompt)
        elif provider in ["claude", "anthropic"]:
            result = _call_anthropic_for_linking(prompt)
        elif provider in ["gemini", "google", "gcp"]:
            result = _call_gemini_for_linking(prompt)
        else:
            raise Exception(f"Unsupported LLM provider: {provider}")

        # JSON 파싱
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            result = result.split("```")[1].split("```")[0]

        data = json.loads(result.strip())
        logger.info(f"LLM linking parsed successfully: {len(data.get('candidates', []))} candidates")

        return data

    except Exception as e:
        logger.error(f"LLM-based linking failed: {e}")
        return None


def _format_schema_for_llm(semantic_model: Dict[str, Any], cat: Any) -> str:
    """LLM 프롬프트용으로 스키마 정보를 포맷팅"""
    lines = []

    # 엔티티 및 메트릭
    lines.append("## 엔티티:")
    entities = semantic_model.get("entities", [])
    for entity in entities:
        if isinstance(entity, dict):
            name = entity.get("name")
            lines.append(f"- {name}")

            dimensions = entity.get("dimensions", [])
            if dimensions:
                lines.append("  Dimensions:")
                for dim in dimensions:
                    if isinstance(dim, dict):
                        lines.append(f"    - {dim.get('name')}")

            measures = entity.get("measures", [])
            if measures:
                lines.append("  Measures:")
                for measure in measures:
                    if isinstance(measure, dict):
                        lines.append(f"    - {measure.get('name')}")

    # 메트릭
    lines.append("\n## 메트릭:")
    metrics = semantic_model.get("metrics", [])
    for metric in metrics:
        if isinstance(metric, dict):
            lines.append(f"- {metric.get('name')}")

    # 동의어
    lines.append("\n## 동의어:")
    vocab = semantic_model.get("vocabulary", {})
    synonyms = vocab.get("synonyms", {}) if isinstance(vocab, dict) else {}
    for canonical, syns in synonyms.items():
        lines.append(f"- {canonical}: {syns}")

    return "\n".join(lines)


def _call_openai_for_linking(prompt: str) -> str:
    """OpenAI API로 스키마 링킹"""
    import openai

    client = openai.OpenAI(api_key=settings.openai_api_key)

    # OpenAI 최신 모델은 max_completion_tokens 사용
    model = settings.openai_model or "gpt-4o-mini"
    token_param = {}

    if any(x in model for x in ["gpt-4o", "gpt-5", "o1-", "o3-"]):
        token_param["max_completion_tokens"] = 1000
    else:
        token_param["max_tokens"] = 1000

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        **token_param
    )
    return response.choices[0].message.content or ""


def _call_anthropic_for_linking(prompt: str) -> str:
    """Anthropic Claude API로 스키마 링킹"""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model or "claude-3-5-sonnet-20240620",
        max_tokens=1000,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def _call_gemini_for_linking(prompt: str) -> str:
    """Google Gemini API로 스키마 링킹"""
    import google.generativeai as genai

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(settings.gemini_model or "gemini-1.5-flash")
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=1000
        )
    )
    return response.text

