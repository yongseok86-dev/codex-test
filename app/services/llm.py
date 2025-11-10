"""
LLM 기반 SQL 생성 모듈 (레거시)

시맨틱 모델과 LLM을 사용하여 자연어 질문을 BigQuery SQL로 변환합니다.
다중 LLM 프로바이더를 지원하며, 시맨틱 모델 기반 프롬프트를 자동 구성합니다.

주요 역할:
    - 시맨틱 모델 기반 프롬프트 구성 (prompt_builder 활용)
    - 다중 LLM 프로바이더 지원 (OpenAI, Claude, Gemini)
    - SQL 추출 및 후처리

지원 프로바이더:
    - OpenAI: gpt-4o-mini, gpt-4o (기본값)
    - Anthropic: claude-3-5-sonnet, claude-3-opus
    - Google: gemini-1.5-flash, gemini-1.5-pro

사용 시나리오:
    - 레거시 엔드포인트 (이전 use_llm=True 방식)
    - 간단한 SQL 생성 (시맨틱 모델 + Few-shot)
    - prompt_builder 기반 프롬프트

참고:
    - 이 모듈은 레거시입니다.
    - 새로운 구현은 sqlgen.py를 사용하세요.
    - sqlgen.py는 더 고급 기능 제공 (테이블 서픽스, JOIN 등)
"""
from __future__ import annotations

from typing import Optional
from app.services import prompt as prompt_builder
from app.semantic.loader import load_semantic_root
from app.config import settings
from app.deps import get_logger

# LLM 클라이언트 라이브러리 임포트 (선택적)
try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

try:
    import anthropic  # type: ignore
except Exception:  # pragma: no cover
    anthropic = None  # type: ignore

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore


class LLMNotConfigured(Exception):
    """LLM 프로바이더가 설정되지 않았거나 사용할 수 없을 때 발생하는 예외"""
    pass


def generate_sql_via_llm(question: str, provider: Optional[str] = None) -> str:
    """
    LLM을 사용하여 자연어 질문을 BigQuery SQL로 변환합니다 (레거시).

    시맨틱 모델을 기반으로 프롬프트를 구성하고, 선택된 LLM 프로바이더를
    호출하여 SQL을 생성합니다. Few-shot 예제와 메트릭 정의를 포함합니다.

    Args:
        question: 자연어 질문 (예: "지난 7일 주문 추이")
        provider: LLM 프로바이더 선택 (선택적)
            - "openai" (기본값)
            - "claude" / "anthropic"
            - "gemini" / "google" / "gcp"
            - None이면 settings.llm_provider 사용

    Returns:
        str: 생성된 BigQuery SQL

    Raises:
        LLMNotConfigured: 프로바이더가 설정되지 않았거나 API 키 누락

    Example:
        >>> sql = generate_sql_via_llm("지난 7일 주문 추이", provider="openai")
        '''
        SELECT
          DATE(TIMESTAMP_MICROS(event_timestamp)) AS day,
          SUM(CASE WHEN event_name='purchase' THEN 1 ELSE 0 END) AS orders
        FROM `ns-extr-data.analytics_310486481.events_*`
        WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY))
        GROUP BY day
        ORDER BY day
        '''

    Note:
        - 이 함수는 레거시 인터페이스입니다.
        - 새로운 구현은 sqlgen.generate()를 사용하세요.
        - 프롬프트는 prompt_builder.build_sql_prompt()에서 구성됩니다.
        - Few-shot 예제와 시맨틱 모델이 자동으로 포함됩니다.
    """
    # 1. 시맨틱 모델 로드
    semantic = load_semantic_root()

    # 2. 프롬프트 구성 (prompt_builder 사용)
    # - 시맨틱 모델 (엔티티, 메트릭, 어휘)
    # - Golden queries (Few-shot 예제)
    # - 메트릭 정의
    prompt = prompt_builder.build_sql_prompt(question, semantic)

    # 3. LLM 설정 준비
    provider = (provider or settings.llm_provider or "").lower()
    system_prompt = settings.llm_system_prompt or "Generate ONLY SQL in BigQuery dialect in a code fence."
    temperature = float(getattr(settings, "llm_temperature", 0.1))
    max_tokens = int(getattr(settings, "llm_max_tokens", 1024))
    logger = get_logger(__name__)

    logger.info(f"Generating SQL via LLM: provider={provider}, question='{question[:50]}...'")

    # 4. 프로바이더별 LLM 호출
    # 4-1. OpenAI 프로바이더
    if provider == "openai":
        if OpenAI is None or not settings.openai_api_key:
            raise LLMNotConfigured("OpenAI provider not available or missing API key")

        client = OpenAI(api_key=settings.openai_api_key)
        model = settings.openai_model or "gpt-4o-mini"

        # OpenAI 최신 모델은 max_completion_tokens 사용
        token_param = {}
        if any(x in model for x in ["gpt-4o", "gpt-5", "o1-", "o3-"]):
            token_param["max_completion_tokens"] = max_tokens
        else:
            token_param["max_tokens"] = max_tokens

        logger.info(f"Calling OpenAI: model={model}")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            **token_param,
        )
        content = resp.choices[0].message.content or ""
        logger.info(f"OpenAI response received (tokens: {resp.usage.total_tokens})")
        return _extract_sql_from_text(content)

    # 4-2. Anthropic Claude 프로바이더
    if provider in {"claude", "anthropic"}:
        if anthropic is None or not settings.anthropic_api_key:
            raise LLMNotConfigured("Anthropic provider not available or missing API key")

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        model = settings.anthropic_model or "claude-3-5-sonnet-20240620"

        logger.info(f"Calling Anthropic: model={model}")
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        # Anthropic 응답은 content blocks 리스트
        text_parts = []
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", "") == "text":
                text_parts.append(getattr(block, "text", ""))
        content = "\n".join(text_parts) or str(resp)

        logger.info("Anthropic response received")
        return _extract_sql_from_text(content)

    # 4-3. Google Gemini 프로바이더
    if provider in {"gemini", "google", "gcp"}:
        if genai is None or not settings.gemini_api_key:
            raise LLMNotConfigured("Gemini provider not available or missing API key")

        genai.configure(api_key=settings.gemini_api_key)
        model = settings.gemini_model or "gemini-1.5-flash"

        logger.info(f"Calling Gemini: model={model}")
        m = genai.GenerativeModel(model)
        resp = m.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
        )
        content = getattr(resp, "text", None) or "\n".join(getattr(resp, "candidates", []) or [])

        logger.info("Gemini response received")
        return _extract_sql_from_text(content)

    # 4-4. 프로바이더 미설정 또는 미지원
    # 향후 추가 가능: Vertex AI, Azure OpenAI, Cohere 등
    raise LLMNotConfigured(f"No LLM provider configured or unsupported provider: {provider}")


def _extract_sql_from_text(text: str) -> str:
    """
    LLM 응답에서 SQL 코드를 추출합니다.

    LLM이 반환한 텍스트에서 ```sql ... ``` 코드 블록을 찾아
    순수 SQL만 추출합니다. 코드 블록이 없으면 전체 텍스트를 반환합니다.

    Args:
        text: LLM 응답 텍스트

    Returns:
        str: 추출된 SQL 문자열

    Example:
        >>> text = '''Here is the SQL:
        ... ```sql
        ... SELECT * FROM orders
        ... ```
        ... '''
        >>> _extract_sql_from_text(text)
        'SELECT * FROM orders'

        >>> text = "SELECT * FROM orders"  # 코드 블록 없음
        >>> _extract_sql_from_text(text)
        'SELECT * FROM orders'

    Note:
        - ```sql 마커를 우선 검색
        - 없으면 전체 텍스트를 SQL로 간주
        - 앞뒤 공백 제거
    """
    # ```sql 코드 블록 찾기
    start = text.find("```sql")
    if start == -1:
        # 코드 블록 없으면 전체 텍스트 반환
        return text.strip()

    # ```sql 이후 시작
    start += len("```sql")

    # 닫는 ``` 찾기
    end = text.find("```", start)
    if end == -1:
        # 닫는 마커 없으면 끝까지
        end = len(text)

    # SQL 추출 및 공백 제거
    return text[start:end].strip()
