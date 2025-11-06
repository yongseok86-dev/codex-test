# 작업 요약(Worklog)

이 문서는 “Mall 유입 고객의 여정/행동” 시나리오를 위한 NL→SQL(BigQuery) 에이전트 구축 작업의 진행 기록과 핵심 결정을 요약합니다. 후속 작업을 빠르게 이어가기 위한 문맥 스냅샷입니다.

## 목표/범위
- 자연어 질의를 BigQuery 최적 SQL로 생성/검증/실행
- 시멘틱 레이어(엔티티/지표/어휘) + 골든쿼리 기반 정확도 향상
- 프런트(ChatGPT 스타일) UI + 스트리밍 진행(SSE)
- 가드레일·비용/안전(드라이런)·도메인 검증 플로우 제공

## 핵심 구현(요지)
- 백엔드(FastAPI)
  - 라우트: `POST /api/query`, `GET /api/query/stream`(SSE: nlu→plan→sql→validated→check→result)
  - LLM: OpenAI(기본)/Claude/Gemini 다중 제공자, per-request `llm_provider` 선택, 키/튜닝(.env) 백엔드 관리
  - 프롬프트: 시멘틱/메트릭/어휘 + golden_queries 유사도 기반 few-shot 자동 주입
  - 검증 파이프라인: lint → DRY RUN(바이트/비용) → EXPLAIN → LIMIT 0 스키마 → 카나리아 → 도메인 assertion(시간버킷/타임윈도우/기본필터/엔티티 테이블/group_by)
  - 실행: DRY RUN/전체 실행/머티리얼라이즈(`materialize: true`, 만료시간 설정)
  - BigQuery 커넥터: 공용 client/config/query 헬퍼
- 시멘틱 레이어
  - 모델: `app/semantic/semantic.yml` (user/session/event/order + 관계/측정/어휘)
  - 메트릭: `metrics_definitions.yaml` (sessions/users/events/gmv/orders/conversion_rate/aov/bounce_rate)
  - 골든쿼리: `golden_queries.yaml` (한국어 질문 다수, intent/slots)
  - 데이터셋 오버라이드: `datasets.yaml`로 엔티티→BQ 테이블 매핑
- 프런트엔드(Vue3 + Element Plus)
  - Chat UI: 입력/메시지/결과 패널(페이지네이션+CSV), 다크 모드, 히스토리 저장
  - 스트리밍 진행/LLM 토글/Provider 선택(키는 백엔드 관리)
  - 렌더링: Markdown + 코드 하이라이트 + KaTeX + Mermaid
- Dev/운영
  - CI(GitHub Actions), PR 템플릿, CODEOWNERS, .env.example 추가

## 주요 설정(.env)
- GCP: `gcp_project`, `bq_default_location`, `maximum_bytes_billed`, `bq_materialize_dataset`
- LLM: `llm_provider`(openai|claude|gemini), 각 API Key/모델, `llm_temperature`, `llm_max_tokens`, `llm_system_prompt`

## 사용 요약
- 서버: `uvicorn app.main:app --port 8080`
- 프런트: `cd frontend && npm ci && npm run dev`
- REST: `POST /api/query` { q, use_llm?, llm_provider?, dry_run?, limit?, materialize? }
- SSE: `/api/query/stream?q=...&use_llm=...&llm_provider=...`

## 남은 작업(제안)
- 시멘틱 기반 도메인 규칙 고도화(필수 차원/허용 값/조인 정책)
- 규칙 기반 SQLGen에 group_by/order_by/filters 해석 확대
- 검증 실패 시 자동 수정/패치 제안(리라이팅)
- Materialized View 증분/캐시 정책, 비용 보고서
- README/개발가이드 한글 정제 및 예시 확대
