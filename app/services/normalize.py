from __future__ import annotations

import re
from typing import Dict, Any, Tuple
from app.semantic.loader import load_semantic_root


def normalize(text: str) -> Tuple[str, Dict[str, Any]]:
    """
    텍스트 정규화: 공백 정리, 동의어 치환 등 기본적인 전처리 수행

    이 함수는 NL2SQL 파이프라인의 첫 단계로, 사용자 입력 텍스트를 정규화합니다.

    주요 작업:
    1. 앞뒤 공백 제거 (trim)
    2. 연속된 공백을 하나로 축약
    3. 동의어를 표준 용어로 통일 (예: '구매' → '주문')

    Args:
        text: 사용자가 입력한 자연어 질문 문자열

    Returns:
        Tuple[str, Dict[str, Any]]:
            - 정규화된 텍스트
            - 메타데이터 딕셔너리 (normalized: True)

    Example:
        >>> normalize("지난   7일   구매   추이")
        ("지난 7일 주문 추이", {"normalized": True})
    """
    # 1. 앞뒤 공백 제거
    t = (text or "").strip()

    # 2. 연속된 공백(스페이스, 탭, 개행 등)을 하나의 공백으로 통일
    t = re.sub(r"\s+", " ", t)

    # 3. 시맨틱 모델에서 동의어 사전 로드
    # semantic.yml 파일에서 vocabulary.synonyms 섹션을 가져옴
    sem = load_semantic_root().get("semantic.yml", {}) or {}
    vocab = (sem.get("vocabulary") or {}).get("synonyms", {}) if isinstance(sem, dict) else {}

    # 4. 동의어를 표준 용어(canonical)로 치환
    # 예: {"주문": ["구매", "오더", "purchase"]} 형태의 매핑
    # "구매"라는 단어를 모두 "주문"으로 변환
    for canon, arr in (vocab or {}).items():
        for alt in arr or []:
            t = t.replace(str(alt), str(canon))

    # 5. 메타데이터 생성
    meta = {"normalized": True}

    return t, meta

