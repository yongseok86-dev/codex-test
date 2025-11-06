# codex-test

NL→SQL BigQuery 시멘틱 레이어 에이전트 + ChatGPT 스타일 프런트엔드.
FastAPI(백엔드)와 Vite+Vue3(프런트엔드)로 구성되어 자연어 질의를 SQL로 변환하고 실행/요약을 지원합니다.

## 프로젝트 구성
- `app/` 백엔드 FastAPI
  - `routers/` API 라우트 (`health.py`, `query.py` 등)
  - `services/` 코어 로직 (NLU/Planner/SQLGen/Validator/Executor/LLM/Prompt)
  - `semantic/` 시멘틱 모델 (`semantic.yml`, `metrics_definitions.yaml`, `golden_queries.yaml`)
  - `guardrails.json` 가드레일 정책(금칙어 등)
- `frontend/` Vite + Vue3 UI (ChatGPT 유사 인터랙션)
- `tests/` PyTest 기본 테스트
- `.github/` CI, PR 템플릿, CODEOWNERS

## 백엔드(FastAPI)
- 실행: `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- API:
  - `GET /healthz`, `GET /readyz`
  - `POST /api/query` { q, limit?, dry_run?, use_llm? }
  - `GET /api/query/stream?q=...&limit=...&dry_run=...&use_llm=...` (SSE: nlu → plan → sql → validated → result)
- BigQuery:
  - 기본은 드라이런(`dry_run_only=true`)으로 비용/안전 보장
  - 실제 실행 시 GCP 인증과 `gcp_project`, `bq_default_location` 필요
  - DRY RUN 메타: `total_bytes_processed`, `estimated_tb`, `estimated_cost_usd`
- 가드레일: `app/guardrails.json` 기준으로 금칙어 검사(SELECT * 등)

## LLM 설정(OpenAI 기본, Claude/Gemini 지원)
- `.env` 예시(루트의 `.env.example` 참조):
  - `llm_provider=openai | claude | gemini`
  - OpenAI: `openai_api_key`, `openai_model`(기본 gpt-4o-mini)
  - Claude: `anthropic_api_key`, `anthropic_model`
  - Gemini: `gemini_api_key`, `gemini_model`
- 프롬프트에 시멘틱 레이어/메트릭/사전을 주입하여 SQL 정확도 향상

## 프런트엔드(Vite + Vue3)
- 설치/실행: `cd frontend && npm ci && npm run dev` (http://localhost:5173)
- 개발 프록시: `/api` → `http://localhost:8080` (`vite.config.ts`)
- 기능:
  - ChatGPT 스타일 대화, 스트리밍 진행(SSE), LLM 토글, Dry Run/Limit 제어
  - 결과 패널(페이지네이션/CSV 다운로드), 다크 모드
  - 고급 마크다운(목록/표) + 코드 하이라이트 + 수식(KaTeX) + 다이어그램(Mermaid)

## 테스트
- `pytest -q`

## 환경 템플릿
- 루트의 `.env.example`를 복사해 `.env`로 사용하세요. GCP/BigQuery 및 LLM(openai/claude/gemini) 키를 채운 뒤 서버를 재시작하면 적용됩니다.

- LLM 선택: 프런트엔드에서 Provider(OpenAI/Claude/Gemini)만 선택합니다. 키/토큰/튜닝(온도, 토큰)은 백엔드 .env 설정으로 관리하며, 제공자 호출 실패 시 서버 로그에 경고를 남기고 규칙 기반 SQL로 자동 폴백합니다.


- 검증 흐름: 규칙 린팅 → DRY RUN → EXPLAIN → LIMIT 0 스키마 → 카나리아 → 도메인 규칙 → 전체 실행/머티뷰.

- 실행 옵션: REST 바디 `materialize: true` 로 결과를 BigQuery 테이블로 머티리얼라이즈(만료시간 기본 24h, .env 설정).
