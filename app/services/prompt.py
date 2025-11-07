"""
LLM 프롬프트 빌더 모듈 (Prompt Builder)

시맨틱 모델을 기반으로 LLM에게 전달할 SQL 생성 프롬프트를 구성합니다.
Few-shot 학습, 메트릭 정의, 어휘 등을 포함하여 정확한 SQL 생성을 유도합니다.

주요 역할:
    - 시맨틱 모델을 LLM 프롬프트로 변환
    - Few-shot 학습을 위한 유사 질문 검색
    - 메트릭 정의 및 어휘 포함
    - 테이블 오버라이드 적용

프롬프트 구성 요소:
    1. 시스템 지시사항 (BigQuery SQL 전문가)
    2. 시맨틱 모델 (엔티티, 차원, 측정항목)
    3. 메트릭 정의 (expr, default_filters)
    4. 어휘 및 동의어
    5. 유사 질문 (Few-shot 예제)
    6. 사용자 질문

사용처:
    - llm.py의 generate_sql_via_llm() (레거시)
    - 시맨틱 모델 기반 프롬프트 생성

Note:
    - 이 모듈은 레거시 llm.py와 함께 사용됩니다.
    - 새로운 sqlgen.py는 자체 프롬프트 빌더 사용
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re
from app.semantic.loader import load_semantic_root, load_datasets_overrides, apply_table_overrides
from app.deps import get_logger

logger = get_logger(__name__)


def _tokenize(s: str) -> List[str]:
    """
    문자열을 토큰(단어)으로 분리합니다.

    한글과 영문 단어를 추출하여 소문자로 변환합니다.
    유사도 계산에 사용됩니다.

    Args:
        s: 토큰화할 문자열

    Returns:
        List[str]: 토큰 리스트 (소문자)

    Example:
        >>> _tokenize("지난 7일 주문 추이")
        ["지난", "7일", "주문", "추이"]
    """
    return re.findall(r"[\w가-힣]+", s.lower())


def _similar_golden(question: str, semantic_root: Dict[str, Any], k: int = 3) -> List[Dict[str, Any]]:
    """
    질문과 유사한 골든 쿼리를 찾습니다 (Few-shot 학습용).

    토큰 중복도 기반으로 유사한 예제 질문을 찾아
    Few-shot 학습에 활용합니다.

    Args:
        question: 사용자 질문
        semantic_root: 시맨틱 모델 루트
        k: 반환할 유사 질문 개수 (기본값: 3)

    Returns:
        List[Dict]: 유사 질문 리스트 (점수 순)
            - nl: 자연어 질문
            - intent: 의도
            - slots: 슬롯 정보

    Example:
        >>> _similar_golden("지난 7일 주문 추이", semantic_root, k=3)
        [
            {
                "nl": "최근 7일 매출 추이",
                "intent": "metric_over_time",
                "slots": {"metric": "gmv", "time_window": {"days": 7}}
            },
            ...
        ]

    Algorithm:
        1. 질문 토큰화
        2. 각 골든 쿼리와 토큰 중복도 계산
        3. 점수순 정렬
        4. 상위 k개 반환 (점수 > 0)
    """
    # golden_queries.yaml 로드
    gq = semantic_root.get("golden_queries.yaml", {}) or {}
    items = gq.get("queries") or []

    if not items:
        logger.debug("No golden queries found")
        return []

    # 질문 토큰화
    q_tokens = set(_tokenize(question))

    # 각 골든 쿼리와 유사도 계산
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for it in items:
        nl = str(it.get("nl", ""))
        # 토큰 중복도 = 교집합 크기
        score = len(q_tokens.intersection(_tokenize(nl)))
        scored.append((score, it))

    # 점수 역순 정렬
    scored.sort(key=lambda x: x[0], reverse=True)

    # 상위 k개 반환 (점수 > 0만)
    similar = [it for sc, it in scored[:k] if sc > 0]

    logger.debug(f"Found {len(similar)} similar golden queries")

    return similar


def build_sql_prompt(question: str, semantic_root: Dict[str, Any]) -> str:
    """
    시맨틱 모델을 기반으로 LLM SQL 생성 프롬프트를 구성합니다.

    시맨틱 모델의 엔티티, 메트릭, 어휘, Few-shot 예제를 포함하여
    LLM이 정확한 BigQuery SQL을 생성하도록 유도합니다.

    Args:
        question: 사용자의 자연어 질문
        semantic_root: 시맨틱 모델 루트 딕셔너리
            - semantic.yml: 엔티티 및 어휘
            - metrics_definitions.yaml: 메트릭 정의
            - golden_queries.yaml: Few-shot 예제

    Returns:
        str: LLM에게 전달할 프롬프트 문자열

    Prompt Structure:
        1. 시스템 역할 및 규칙
        2. 시맨틱 모델 (엔티티, 차원, 측정항목)
        3. 메트릭 정의 (expr, filters)
        4. 어휘 및 동의어
        5. 유사 질문 (Few-shot)
        6. 사용자 질문
        7. 응답 형식 지정

    Example:
        >>> prompt = build_sql_prompt("지난 7일 주문 추이", semantic_root)
        >>> print(prompt)
        '''
        You are an expert data analyst generating BigQuery SQL.
        Follow these rules strictly:
        - Use fully-qualified table names when present.
        ...

        Semantic model (entities/dimensions/measures):
        {...}

        Question:
        지난 7일 주문 추이

        Respond with:
        ```sql
        <SQL>
        ```
        '''

    Note:
        - 이 함수는 레거시 llm.py에서 사용됩니다.
        - 새로운 sqlgen.py는 자체 프롬프트 빌더 사용
        - 테이블 오버라이드 자동 적용 (datasets.yaml)
    """
    # 1. 시맨틱 모델 로드 및 테이블 오버라이드 적용
    sem_raw = semantic_root.get("semantic.yml", {})
    overrides = load_datasets_overrides()
    sem = apply_table_overrides(sem_raw, overrides) if isinstance(sem_raw, dict) else sem_raw

    # 2. 메트릭 및 어휘 로드
    metrics = semantic_root.get("metrics_definitions.yaml", {})
    vocab = sem.get("vocabulary", {}) if isinstance(sem, dict) else {}

    # 3. 프롬프트 구성 시작
    lines = []

    # 3-1. 시스템 지시사항 및 규칙
    lines.append("You are an expert data analyst generating BigQuery SQL.")
    lines.append("Follow these rules strictly:")
    lines.append("- Use fully-qualified table names when present.")
    lines.append("- Prefer approximate functions (APPROX_*) only when requested.")
    lines.append("- Never use SELECT * ; select only necessary columns.")
    lines.append("- Output ONLY SQL in a code block. No explanations.")
    lines.append("")

    # 3-2. 시맨틱 모델 포함
    if sem:
        lines.append("Semantic model (entities/dimensions/measures):")
        lines.append(str(sem))
        lines.append("")

    # 3-3. 메트릭 정의 포함
    if metrics:
        lines.append("Metric definitions:")
        lines.append(str(metrics))
        lines.append("")

    # 3-4. 어휘 및 동의어 포함
    if vocab:
        lines.append("Vocabulary/Synonyms:")
        lines.append(str(vocab))
        lines.append("")

    # 3-5. Few-shot 학습: 유사 질문 추가
    # 토큰 중복도 기반으로 상위 k개 골든 쿼리 검색
    sims = _similar_golden(question, semantic_root, k=3)
    if sims:
        lines.append("Similar questions (with intended structure):")
        for s in sims:
            # NL, intent, slots만 포함 (SQL은 제외 - 생성하도록 유도)
            lines.append(str({
                "nl": s.get("nl"),
                "intent": s.get("intent"),
                "slots": s.get("slots")
            }))
        lines.append("")

    # 3-6. 사용자 질문
    lines.append("Question:")
    lines.append(question)
    lines.append("")

    # 3-7. 응답 형식 지정
    lines.append("Respond with:\\n```sql\\n<SQL>\\n```")

    # 4. 최종 프롬프트 반환
    prompt = "\\n".join(lines)

    logger.debug(f"Built prompt for question: '{question[:50]}...' (length: {len(prompt)} chars)")

    return prompt
