# FastAPI NL2SQL Agent Backend - 종합 분석 보고서

**생성일**: 2025-11-07
**프로젝트**: NL2SQL Agent (Natural Language to SQL)
**기술 스택**: FastAPI, BigQuery, Multi-LLM (OpenAI/Claude/Gemini), Python 3.x

---

## 1. 프로젝트 개요

이 프로젝트는 자연어 질문을 BigQuery SQL로 변환하고 실행하는 엔터프라이즈급 NL2SQL 플랫폼입니다.

### 1.1 핵심 특징

1. **다중 LLM 지원**: OpenAI GPT-4, Anthropic Claude, Google Gemini 통합
2. **시맨틱 레이어**: 엔티티/차원/측정항목 정의로 일관된 메트릭 관리
3. **다단계 검증 파이프라인**: Lint → Dry-Run → Explain → Schema → Canary
4. **자동 오류 수정**: LLM 기반 SQL 재생성 및 재검증
5. **스키마 링킹**: 토큰 기반 테이블/컬럼 매칭
6. **SSE 스트리밍**: 실시간 파이프라인 진행상황 전송
7. **비용 추정**: BigQuery 비용 예측 및 제한
8. **보안 가드레일**: 위험한 SQL 연산 차단
9. **대화형 컨텍스트**: 대화 히스토리 유지
10. **쿼리 구체화**: BigQuery 테이블로 결과 캐싱

---

## 2. 프로젝트 구조

```
f:\codex\codex1\
├── app/                           # 메인 애플리케이션
│   ├── main.py                   # FastAPI 앱 팩토리 & 미들웨어
│   ├── config.py                 # 환경 설정 (Pydantic)
│   ├── deps.py                   # 로깅 설정 & 의존성 주입
│   ├── guardrails.json           # SQL 보안 정책
│   │
│   ├── routers/                  # API 라우터
│   │   ├── health.py             # 헬스체크 엔드포인트
│   │   └── query.py              # NL2SQL 쿼리 엔드포인트
│   │
│   ├── services/                 # 비즈니스 로직 & 파이프라인
│   │   ├── nlu.py                # 의도 및 슬롯 추출
│   │   ├── planner.py            # 쿼리 계획 생성
│   │   ├── sqlgen.py             # 규칙 기반 SQL 생성
│   │   ├── llm.py                # LLM 기반 SQL 생성
│   │   ├── normalize.py          # 텍스트 정규화 & 동의어 처리
│   │   ├── context.py            # 대화 컨텍스트 관리
│   │   ├── linking.py            # 스키마 링킹
│   │   ├── guard.py              # SQL 파싱 (SQLGlot)
│   │   ├── validator.py          # SQL 린트 & 검증 규칙
│   │   ├── validation.py         # 다단계 검증 파이프라인
│   │   ├── repair.py             # LLM 오류 수정
│   │   ├── executor.py           # BigQuery 실행
│   │   ├── summarize.py          # 결과 요약
│   │   ├── prompt.py             # LLM 프롬프트 빌더
│   │   └── templates.py          # 템플릿 기반 SQL 생성
│   │
│   ├── bq/                       # BigQuery 연동
│   │   └── connector.py          # BigQuery 클라이언트 래퍼
│   │
│   ├── schema/                   # 스키마 & 카탈로그
│   │   ├── catalog.py            # 테이블/컬럼 카탈로그 (캐싱)
│   │   └── aliases.yaml          # 한영 컬럼 별칭 매핑
│   │
│   ├── semantic/                 # 시맨틱 모델 & 메타데이터
│   │   ├── semantic.yml          # 엔티티/차원/측정 정의
│   │   ├── metrics_definitions.yaml  # 메트릭 공식
│   │   ├── golden_queries.yaml   # Few-shot 예제
│   │   ├── datasets.yaml         # 테이블명 오버라이드
│   │   └── loader.py             # YAML 로더
│   │
│   └── utils/                    # 유틸리티
│       └── timeparse.py          # 날짜/시간 파싱
│
├── tests/                        # 테스트 스위트
│   ├── test_health.py           # 헬스체크 테스트
│   ├── test_query_stub.py       # 쿼리 스텁 테스트
│   └── test_stream_sse.py       # SSE 스트리밍 테스트
│
├── pyproject.toml               # 프로젝트 메타데이터 & 의존성
├── .env.example                 # 환경변수 템플릿
└── logs/                        # 일별 로그 파일
```

---

## 3. 핵심 컴포넌트 상세 분석

### 3.1 애플리케이션 진입점

#### `app/main.py` - FastAPI 애플리케이션 팩토리

**주요 기능**:
- `create_app()`: FastAPI 인스턴스 생성 및 라우터 등록
- HTTP 미들웨어: 액세스 로그 및 지연시간 추적
- 구조화된 로깅 초기화 (`setup_logging()`)

**라우터**:
- `/healthz`, `/readyz` (헬스체크)
- `/api/query`, `/api/query/stream` (쿼리 처리)

**파일 경로**: [app/main.py](app/main.py)

---

#### `app/config.py` - 환경 설정

**주요 설정**:

**환경 & BigQuery**:
- `env`: 환경 (dev/prod)
- `gcp_project`: GCP 프로젝트 ID
- `bq_default_location`: BigQuery 위치
- `maximum_bytes_billed`: 비용 제한 (TB 단위)
- `dry_run_only`: Dry-run 전용 모드
- `price_per_tb_usd`: TB당 가격 (USD)

**LLM 설정**:
- `llm_provider`: openai | claude | gemini
- `openai_api_key`, `anthropic_api_key`, `gemini_api_key`
- `llm_temperature`: 0.1 (기본값)
- `llm_max_tokens`: 1024 (기본값)
- `llm_enable_repair`: 오류 자동 수정 활성화
- `llm_enable_result_summary`: LLM 결과 요약 활성화

**구체화 (Materialization)**:
- `bq_materialize_dataset`: 구체화 대상 데이터셋
- `bq_materialize_expiration_hours`: 테이블 만료 시간

**로깅**:
- `log_file_path`: 로그 파일 경로
- `log_rotation`: daily | size
- `log_when`: midnight (기본값)
- `log_utc`: UTC 타임스탬프 사용 여부

**파일 경로**: [app/config.py](app/config.py)

---

#### `app/deps.py` - 로깅 설정 & 의존성 주입

**주요 함수**:
- `get_logger(name: str)`: 로거 인스턴스 생성
- `setup_logging()`: 루트 로거 초기화 (멱등성)

**로깅 기능**:
- 콘솔 핸들러 (StreamHandler)
- 파일 핸들러 (TimedRotatingFileHandler / RotatingFileHandler)
- UTF-8 인코딩
- 일별 로테이션 (접미사 형식: `%Y-%m-%d`)
- Cloud Logging 통합 지원

**파일 경로**: [app/deps.py](app/deps.py)

---

### 3.2 API 라우터

#### `app/routers/health.py` - 헬스체크

**엔드포인트**:
1. `GET /healthz` → `{"status": "ok"}`
2. `GET /readyz` → `{"status": "ready"}`

**용도**: Kubernetes liveness/readiness 프로브

**파일 경로**: [app/routers/health.py](app/routers/health.py)

---

#### `app/routers/query.py` - 메인 쿼리 핸들러

**엔드포인트**:

1. **`POST /api/query`** - 동기식 쿼리 처리

**요청 스키마** (QueryRequest):
```python
q: str                      # 자연어 질문 (필수)
limit: int | None = 100     # 결과 행 제한
dry_run: bool | None = None # Dry-run 여부 (설정에서 기본값)
use_llm: bool | None = None # LLM 사용 여부
llm_provider: str | None    # 프로바이더 오버라이드: 'openai' | 'claude' | 'gemini'
materialize: bool | None    # 쿼리 결과 구체화 여부
conversation_id: str | None # 대화형 컨텍스트용 ID
```

**응답 스키마** (QueryResponse):
```python
sql: str                     # 생성/실행된 SQL
dry_run: bool               # Dry-run 여부
rows: list[dict] | None     # 쿼리 결과 (dry-run 시 None)
metadata: dict | None       # 검증, 비용, 요약 정보
```

2. **`GET /api/query/stream`** - SSE 스트리밍 엔드포인트

**SSE 이벤트 타입**:
- `normalize`, `context`, `nlu`, `plan`, `sql`, `linking`, `validated`, `check`, `result`, `error`, `info`

**파일 경로**: [app/routers/query.py](app/routers/query.py)

---

### 3.3 파이프라인 단계 (서비스 모듈)

#### 전체 파이프라인 흐름

```
1. Normalize (텍스트 정규화)
    ↓
2. Context (대화 컨텍스트 로드)
    ↓
3. NLU (의도 & 슬롯 추출)
    ↓
4. Plan (쿼리 계획 생성)
    ↓
5. LLM_SQL (SQL 생성: LLM 또는 규칙 기반)
    ↓
6. Linking (스키마 링킹)
    ↓
7. Guard (SQL 파싱 & 가드레일 체크)
    ↓
8. Validate (다단계 검증: Lint → Dry-Run → Explain → Schema → Canary)
    ↓
9. [Optional] Repair (검증 실패 시 LLM 수정 재시도)
    ↓
10. Execute (BigQuery 실행 또는 Dry-Run)
    ↓
11. Summarize (결과 요약: 규칙 기반 + 선택적 LLM 요약)
    ↓
12. End (완료)
```

---

#### 1단계: `app/services/normalize.py` - 텍스트 정규화

**함수**: `normalize(text: str) -> Tuple[str, Dict]`

**처리**:
- 공백 정리 및 축약
- 동의어 치환 (시맨틱 모델에서 로드)
- 메타데이터 반환: `{"normalized": True}`

**파일 경로**: [app/services/normalize.py](app/services/normalize.py)

---

#### 2단계: `app/services/context.py` - 대화 컨텍스트

**함수**:
- `get_context(conv_id: str) -> Dict`: 대화 컨텍스트 조회
- `update_context(conv_id: str, patch: Dict) -> None`: 컨텍스트 업데이트

**저장소**: 인메모리 딕셔너리 `_CTX` (conversation_id 키)

**저장 데이터**: `last_sql`, `last_plan` 등

**파일 경로**: [app/services/context.py](app/services/context.py)

---

#### 3단계: `app/services/nlu.py` - 자연어 이해

**함수**: `extract(q: str) -> Tuple[str, Dict[str, Any]]`

**반환**: (intent, slots)

**의도 감지**:
- `"metric_over_time"`: "추이", "trend", "over time" 포함 시
- `"metric"`: 기본값

**슬롯 추출** (휴리스틱 기반):
- 메트릭: "매출"/"gmv" → "gmv", "주문"/"orders" → "orders"
- 시간 윈도우: "지난 7일"/"last 7 days" → `{"days": 7}`

**파일 경로**: [app/services/nlu.py](app/services/nlu.py)

---

#### 4단계: `app/services/planner.py` - 쿼리 계획

**함수**: `make_plan(intent: str, slots: Dict) -> Dict`

**출력**: 의도, 슬롯, 기본값이 포함된 계획 딕셔너리

**기본값**: metric="orders", grain="day"

**파일 경로**: [app/services/planner.py](app/services/planner.py)

---

#### 5A단계: `app/services/sqlgen.py` - 규칙 기반 SQL 생성

**함수**: `generate(plan: Dict, limit: int | None = 100) -> str`

**기본 테이블**: `"ns-extr-data.analytics_310486481.events_fresh_20251106"`

**로직**:
- 이벤트 기반 vs 주문 기반 테이블 감지
- 메트릭 (gmv, orders, sessions) → SQL 표현식 매핑
- Grain 지원 ("day" → GROUP BY DATE/TIMESTAMP 변환)

**이벤트 테이블 특화**: GA4 이벤트는 `DATE(TIMESTAMP_MICROS(event_timestamp))` 사용

**파일 경로**: [app/services/sqlgen.py](app/services/sqlgen.py)

---

#### 5B단계: `app/services/llm.py` - LLM 기반 SQL 생성

**함수**: `generate_sql_via_llm(question: str, provider: Optional[str]) -> str`

**지원 프로바이더**:
- `"openai"`: OpenAI API (기본: gpt-4o-mini)
- `"claude"` / `"anthropic"`: Anthropic API (기본: claude-3-5-sonnet)
- `"gemini"` / `"google"` / `"gcp"`: Google Generative AI

**파라미터**:
- temperature: 0.1
- max_tokens: 1024
- 시스템 프롬프트: BigQuery SQL 전문가

**SQL 추출**: Markdown 코드 펜스 (```sql...```) 파싱

**오류 처리**: 프로바이더 미설정 시 `LLMNotConfigured` 예외

**파일 경로**: [app/services/llm.py](app/services/llm.py)

---

#### 5C단계: `app/services/prompt.py` - LLM 프롬프트 빌더

**함수**: `build_sql_prompt(question: str, semantic_root: Dict) -> str`

**프롬프트 구성**:
1. 시스템 지시사항 (BigQuery SQL 전문가 역할)
2. 시맨틱 모델 (엔티티, 차원, 측정항목)
3. 메트릭 정의
4. 어휘/동의어
5. 유사 골든 쿼리 (Few-shot 학습)

**헬퍼 함수**: `_similar_golden(question, semantic_root, k=3)` - 토큰 기반 유사도 매칭

**파일 경로**: [app/services/prompt.py](app/services/prompt.py)

---

#### 6단계: `app/services/linking.py` - 스키마 링킹

**함수**: `schema_link(question: str) -> Dict[str, Any]`

**반환**: `{"candidates": [...], "confidence": float}`

**로직**:
1. 질문 토큰화 (한글 + 영어)
2. 별칭, 테이블명, 컬럼명과 매칭
3. 중복도 점수 계산 (정확 일치: 1.0, 부분 일치: 0.5)
4. 후보 정렬 (점수 순)

**데이터 소스**: 카탈로그 + aliases.yaml

**파일 경로**: [app/services/linking.py](app/services/linking.py)

---

#### 7단계: `app/services/guard.py` + `validator.py` - SQL 검증

**`guard.py`**:
- **함수**: `parse_sql(sql: str) -> Any`
- **기능**: SQLGlot를 사용한 BigQuery SQL 파싱
- **오류**: `SQLSyntaxError` 발생

**파일 경로**: [app/services/guard.py](app/services/guard.py)

**`validator.py`**:
- **함수**: `ensure_safe(sql: str) -> None` - 가드레일 정책 강제
- **함수**: `lint(sql: str) -> List[Dict]` - 이슈 목록 반환

**감지 이슈**:
- `"no_select_star"`: SELECT * 금지
- `"missing_time_filter"`: 이벤트 테이블에 시간 필터 누락

**가드레일** (guardrails.json):
- 차단: delete, update, insert, drop, truncate, SELECT *

**파일 경로**: [app/services/validator.py](app/services/validator.py)

---

#### 8단계: `app/services/validation.py` - 다단계 검증 파이프라인

**함수**: `run_pipeline(sql: str, perform_execute: bool, plan: Dict, logger) -> ValidationReport`

**검증 단계**:
1. **lint**: SQL 이슈 체크
2. **dry_run**: BigQuery dry-run으로 바이트/비용 추정
3. **explain**: EXPLAIN 실행으로 쿼리 플랜 확인
4. **schema**: LIMIT 0 쿼리로 결과 스키마 가져오기
5. **canary**: 샘플 실행 (첫 몇 행)

**반환**: `ValidationReport` (StepResult 목록 포함)

**데이터 클래스**:
- `StepResult(name, ok, message, meta)`
- `ValidationReport(steps, sql, schema)`

**파일 경로**: [app/services/validation.py](app/services/validation.py)

---

#### 9단계: `app/services/repair.py` - LLM 오류 수정

**함수**: `attempt_repair(question: str, sql: str, error: str, provider: Optional[str]) -> Optional[str]`

**로직**: 오류 + 원본 SQL을 LLM에 전송하여 수정 시도

**반환**: 수정된 SQL 또는 None (실패 시)

**프롬프트**: 이중 언어 (한국어/영어)

**파일 경로**: [app/services/repair.py](app/services/repair.py)

---

#### 10단계: `app/services/executor.py` - BigQuery 실행

**함수**: `async run(sql: str, dry_run: bool = True) -> QueryResult`

**Dry-Run 모드**:
- 처리 바이트 수 추정
- 비용 계산 (bytes_tb × price_per_tb_usd)
- 작업 메타데이터 반환 (job_id, location, cache_hit)

**실행 모드**:
- 쿼리 실행 및 행을 딕셔너리 목록으로 반환
- 작업 메타데이터 반환

**함수**: `async materialize(sql: str) -> QueryResult`
- 쿼리 결과를 BigQuery 테이블로 구체화
- 테이블명: `mat_{hash(sql):08x}`
- 만료 설정: `bq_materialize_expiration_hours` 기반

**오류 처리**: BigQuery 미설치 시 스텁 반환

**파일 경로**: [app/services/executor.py](app/services/executor.py)

---

#### 11단계: `app/services/summarize.py` - 결과 요약

**함수**: `summarize(rows: List[dict] | None, meta: Dict) -> str`

**출력 예시**: "행 수: 10 | 컬럼: col1, col2... | 예상비용(USD): 0.05"

**함수**: `summarize_llm(question: str, sql: str, meta: Dict, provider: str | None) -> Optional[str]`
- LLM 기반 자연어 요약 생성

**파일 경로**: [app/services/summarize.py](app/services/summarize.py)

---

### 3.4 데이터 & 스키마 모듈

#### `app/schema/catalog.py` - 테이블/컬럼 카탈로그

**데이터 클래스**:
- `Column(name, type, sample=None)`
- `Table(name, columns[], row_count=None)`
- `Catalog(tables{}, loaded_at, ttl_minutes=30)`

**함수**:
- `load_catalog(force=False) -> Catalog`: 시맨틱 모델 + 오버라이드에서 로드, TTL 캐싱

**소스**: 시맨틱 모델 엔티티 → 차원 + 측정항목 추출

**파일 경로**: [app/schema/catalog.py](app/schema/catalog.py)

---

#### `app/schema/aliases.yaml` - 컬럼 별칭 (한영 매핑)

**예시**:
```yaml
주문일: order.order_date
채널: session.source_medium
랜딩페이지: session.landing_page
구매건수: order.orders
매출액: order.gmv
```

**파일 경로**: [app/schema/aliases.yaml](app/schema/aliases.yaml)

---

#### `app/semantic/loader.py` - 시맨틱 모델 로더

**함수**:
- `load_semantic_root() -> Dict`: semantic/ 디렉토리의 모든 YAML 로드
- `load_datasets_overrides() -> Dict`: datasets.yaml 로드 (테이블명 매핑)
- `apply_table_overrides(semantic_model, overrides)`: 테이블명 교체

**로드 파일**: semantic.yml, metrics_definitions.yaml, golden_queries.yaml

**파일 경로**: [app/semantic/loader.py](app/semantic/loader.py)

---

#### `app/semantic/semantic.yml` - 엔티티/차원/측정 정의

**엔티티** (4개 메인):

1. **user** - 사용자 pseudo ID 단위
   - 차원: user_pseudo_id, first_touch_date, first_channel, is_new_user

2. **session** - 세션 ID 단위
   - 차원: session_id, session_date, source_medium, campaign, device_category, landing_page, is_bounce
   - 측정항목: sessions, bounces

3. **event** - 이벤트 ID 단위
   - 차원: event_date, event_name, page_path, item_id, event_value
   - 측정항목: events, add_to_cart, purchases

4. **order** - 주문 ID 단위
   - 차원: order_id, order_date, status, payment_method, channel
   - 측정항목: orders, gmv, customers

**최상위 메트릭**:
- sessions, users, events, gmv, orders, conversion_rate, aov, bounce_rate

**어휘**:
- 동의어 매핑 (한글 → 표준 용어)
- 단위: currency=KRW

**파일 경로**: [app/semantic/semantic.yml](app/semantic/semantic.yml)

---

#### `app/semantic/metrics_definitions.yaml` - 메트릭 공식

**필드**: name, description, expr (SQL), default_filters

**예시**:
```yaml
gmv:
  expr: SUM(order.net_amount)
  default_filters:
    - order.status = 'completed'
```

**파일 경로**: [app/semantic/metrics_definitions.yaml](app/semantic/metrics_definitions.yaml)

---

#### `app/semantic/golden_queries.yaml` - Few-Shot 예제

**10+ 예제 쿼리**:
- `nl`: 자연어 질문 (한국어)
- `intent`: 의도 타입 (metric_over_time / metric)
- `slots`: 추출된 슬롯 (metric, grain, group_by, filters 등)

**용도**: Few-shot LLM 프롬프트 + 유사도 매칭

**파일 경로**: [app/semantic/golden_queries.yaml](app/semantic/golden_queries.yaml)

---

#### `app/semantic/datasets.yaml` - 테이블명 오버라이드

**형식**: 엔티티명 → 완전한 BigQuery 테이블 경로

**예시**:
```yaml
user: project.dataset.users
session: project.dataset.sessions
```

**파일 경로**: [app/semantic/datasets.yaml](app/semantic/datasets.yaml)

---

#### `app/guardrails.json` - 보안 정책

```json
{
  "deny_contains": [
    " delete ",
    " update ",
    " insert ",
    " drop ",
    " truncate ",
    " select * "
  ]
}
```

**파일 경로**: [app/guardrails.json](app/guardrails.json)

---

### 3.5 BigQuery & 유틸리티

#### `app/bq/connector.py` - BigQuery 클라이언트 래퍼

**함수**:
- `available() -> bool`: BigQuery 라이브러리 설치 확인
- `client() -> Any`: 설정된 BigQuery 클라이언트 반환
- `base_job_config(dry_run: bool) -> Any`: 제한 + 레이블이 포함된 작업 설정 생성
- `run_query(sql: str, dry_run: bool) -> Any`: 쿼리 실행

**안전장치**: `maximum_bytes_billed` 설정 + `labels: {"app": "nl2sql"}`

**파일 경로**: [app/bq/connector.py](app/bq/connector.py)

---

#### `app/utils/timeparse.py` - 시간 유틸리티

**함수**: `last_n_days_utc(n: int) -> tuple[datetime, datetime]`

**반환**: 최근 N일의 (start_datetime, end_datetime) UTC 형식

**파일 경로**: [app/utils/timeparse.py](app/utils/timeparse.py)

---

## 4. 설정 & 환경

### 4.1 `.env.example` - 환경변수 템플릿

```
env=dev
gcp_project=
bq_default_location=asia-northeast3
llm_provider=openai
openai_api_key=
openai_model=gpt-4o-mini
anthropic_api_key=
anthropic_model=claude-3-5-sonnet-20240620
gemini_api_key=
gemini_model=gemini-1.5-flash
dry_run_only=true
```

**파일 경로**: [.env.example](.env.example)

---

### 4.2 `pyproject.toml` - 프로젝트 의존성

**핵심 의존성**:
- **FastAPI**: >= 0.115
- **Uvicorn**: >= 0.30
- **BigQuery**: google-cloud-bigquery >= 3.25
- **Cloud Logging**: google-cloud-logging >= 3.10
- **Pydantic**: >= 2.7, pydantic-settings >= 2.4
- **환경 & 데이터**: python-dotenv, pyyaml
- **LLM SDK**:
  - openai >= 1.48
  - anthropic >= 0.34.2
  - google-generativeai >= 0.7.2
- **SQL 파싱**: sqlglot >= 20.11
- **캐싱 & HTTP**: cachetools >= 5.5, requests >= 2.31

**개발 의존성**:
- pytest, pytest-asyncio, httpx
- ruff, mypy

**파일 경로**: [pyproject.toml](pyproject.toml)

---

## 5. 테스트 스위트

### 5.1 테스트 파일

1. **`tests/test_health.py`**: `/healthz`, `/readyz` 엔드포인트 테스트
2. **`tests/test_query_stub.py`**: `/api/query` 엔드포인트 스텁 테스트
3. **`tests/test_stream_sse.py`**: `/api/query/stream` SSE 스트리밍 테스트

**파일 경로**:
- [tests/test_health.py](tests/test_health.py)
- [tests/test_query_stub.py](tests/test_query_stub.py)
- [tests/test_stream_sse.py](tests/test_stream_sse.py)

---

## 6. 로깅 아키텍처

### 6.1 로깅 설정

**초기화**: `app/deps.py::setup_logging()` (앱 시작 시 1회 호출)

**출력 대상**:
- **콘솔**: StreamHandler (커스텀 포매터)
- **파일** (선택적): TimedRotatingFileHandler (일별) 또는 RotatingFileHandler (크기 기반)

### 6.2 로그 스테이지

- `app.http`: HTTP 요청 (경로, 상태, latency_ms)
- `pipeline`: 메인 쿼리 파이프라인 (normalize, nlu, plan 등)
- `pipeline.stream`: 스트리밍 엔드포인트 스테이지
- `pipeline.exec`: 실행자 (execute, materialize)

### 6.3 파일 로테이션

- **일별**: 자정 @ UTC
- **크기 기반**: 5MB 기본값
- **백업 유지**: 5개 파일

---

## 7. 배포 아키텍처

### 7.1 진입점

**ASGI 애플리케이션**: `app.main:app` (FastAPI 인스턴스)

**실행 명령**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 7.2 파이프라인 흐름 (query.py 기준)

```
Normalize (정규화)
  ↓
Context Load (컨텍스트 로드)
  ↓
NLU (의도 + 슬롯)
  ↓
Planner (계획)
  ↓
SQL Generation (LLM 또는 규칙 기반)
  ↓
Schema Linking (스키마 링킹)
  ↓
Guardrail Check (가드레일)
  ↓
Validation Pipeline (Lint → Dry-Run → Explain → Schema → Canary)
  ↓
[Optional] Repair (실패 시 LLM 수정)
  ↓
Execute (BigQuery 실행 또는 Dry-Run)
  ↓
Summarize (규칙 기반 + 선택적 LLM 요약)
  ↓
Return Response (응답 반환)
```

**스트리밍 변형**: 동일한 파이프라인이지만 각 단계에서 SSE 이벤트 방출

---

## 8. 주요 기능 요약

### 8.1 핵심 기능

1. **다중 LLM 프로바이더**: OpenAI, Anthropic (Claude), Google Gemini
2. **규칙 기반 폴백**: LLM 실패 시 규칙 기반 SQL 생성
3. **시맨틱 레이어**: 일관된 메트릭을 위한 엔티티/차원/측정 정의
4. **스키마 링킹**: 질문 텍스트를 테이블/컬럼과 토큰 기반 매칭
5. **오류 수정 루프**: 재검증과 함께 LLM 기반 수정
6. **쿼리 검증**: Lint + Dry-run + Explain + Schema + Canary 단계
7. **비용 추정**: 청구 바이트 추적 및 예상 USD 비용 계산
8. **구체화**: BigQuery에서 선택적 쿼리 결과 캐싱
9. **대화형 컨텍스트**: conversation_id당 인메모리 컨텍스트
10. **SSE 스트리밍**: UX를 위한 실시간 파이프라인 단계 업데이트
11. **가드레일**: 위험한 SQL 연산 차단 보안 정책
12. **로깅**: 일별 파일 로테이션이 있는 구조화된 로깅

---

### 8.2 보안 기능

- **SQL 인젝션 방지**: SQLGlot 파싱 + 가드레일 정책
- **비용 제한**: `maximum_bytes_billed` 설정
- **작업 레이블**: 모든 BigQuery 작업에 `{"app": "nl2sql"}` 레이블
- **Dry-run 전용 모드**: 프로덕션 실행 방지 옵션
- **위험 연산 차단**: DELETE, UPDATE, INSERT, DROP, TRUNCATE 금지

---

### 8.3 성능 최적화

- **카탈로그 캐싱**: TTL 30분 (메모리 내)
- **BigQuery 캐시 활용**: cache_hit 메타데이터 추적
- **쿼리 구체화**: 자주 사용하는 쿼리 결과 캐싱
- **비동기 실행**: async/await 패턴
- **스트리밍 응답**: SSE로 대기 시간 감소

---

## 9. 컴포넌트 매핑 테이블

| 컴포넌트 | 타입 | 용도 | 파일 경로 |
|----------|------|------|-----------|
| main.py | 핵심 | FastAPI 앱 팩토리 | [app/main.py](app/main.py) |
| config.py | 설정 | 환경 설정 | [app/config.py](app/config.py) |
| deps.py | 유틸 | 로깅 설정 | [app/deps.py](app/deps.py) |
| health.py | 라우터 | 헬스체크 엔드포인트 | [app/routers/health.py](app/routers/health.py) |
| query.py | 라우터 | 메인 쿼리 엔드포인트 | [app/routers/query.py](app/routers/query.py) |
| nlu.py | 서비스 | 의도 추출 | [app/services/nlu.py](app/services/nlu.py) |
| planner.py | 서비스 | 쿼리 계획 | [app/services/planner.py](app/services/planner.py) |
| sqlgen.py | 서비스 | 규칙 기반 SQL 생성 | [app/services/sqlgen.py](app/services/sqlgen.py) |
| llm.py | 서비스 | LLM SQL 생성 | [app/services/llm.py](app/services/llm.py) |
| normalize.py | 서비스 | 텍스트 정규화 | [app/services/normalize.py](app/services/normalize.py) |
| context.py | 서비스 | 대화 컨텍스트 | [app/services/context.py](app/services/context.py) |
| linking.py | 서비스 | 스키마 링킹 | [app/services/linking.py](app/services/linking.py) |
| validator.py | 서비스 | SQL 검증 | [app/services/validator.py](app/services/validator.py) |
| guard.py | 서비스 | SQL 파싱 | [app/services/guard.py](app/services/guard.py) |
| validation.py | 서비스 | 다단계 파이프라인 | [app/services/validation.py](app/services/validation.py) |
| executor.py | 서비스 | BigQuery 실행 | [app/services/executor.py](app/services/executor.py) |
| repair.py | 서비스 | 오류 수정 | [app/services/repair.py](app/services/repair.py) |
| summarize.py | 서비스 | 결과 요약 | [app/services/summarize.py](app/services/summarize.py) |
| prompt.py | 서비스 | 프롬프트 빌드 | [app/services/prompt.py](app/services/prompt.py) |
| templates.py | 서비스 | 템플릿 SQL 생성 | [app/services/templates.py](app/services/templates.py) |
| catalog.py | 스키마 | 테이블 카탈로그 | [app/schema/catalog.py](app/schema/catalog.py) |
| aliases.yaml | 스키마 | 컬럼 별칭 | [app/schema/aliases.yaml](app/schema/aliases.yaml) |
| loader.py | 시맨틱 | YAML 로더 | [app/semantic/loader.py](app/semantic/loader.py) |
| semantic.yml | 시맨틱 | 엔티티 정의 | [app/semantic/semantic.yml](app/semantic/semantic.yml) |
| metrics_definitions.yaml | 시맨틱 | 메트릭 공식 | [app/semantic/metrics_definitions.yaml](app/semantic/metrics_definitions.yaml) |
| golden_queries.yaml | 시맨틱 | Few-shot 예제 | [app/semantic/golden_queries.yaml](app/semantic/golden_queries.yaml) |
| datasets.yaml | 시맨틱 | 테이블 오버라이드 | [app/semantic/datasets.yaml](app/semantic/datasets.yaml) |
| connector.py | BQ | BigQuery 래퍼 | [app/bq/connector.py](app/bq/connector.py) |
| timeparse.py | 유틸 | 날짜 유틸 | [app/utils/timeparse.py](app/utils/timeparse.py) |
| guardrails.json | 설정 | 보안 정책 | [app/guardrails.json](app/guardrails.json) |

---

## 10. 개선 권장사항

### 10.1 단기 개선 (1-2주)

1. **테스트 커버리지 확대**
   - 각 서비스 모듈별 단위 테스트 추가
   - 통합 테스트 시나리오 확대
   - LLM 모킹 테스트 추가

2. **문서화 강화**
   - API 문서 자동 생성 (OpenAPI/Swagger)
   - 시맨틱 모델 문서화
   - 운영 가이드 작성

3. **모니터링 & 알림**
   - Prometheus 메트릭 추가
   - 오류 추적 (Sentry 등)
   - 성능 대시보드 구축

### 10.2 중기 개선 (1-3개월)

1. **컨텍스트 관리 개선**
   - 인메모리 → Redis/Memcached 전환
   - 대화 히스토리 영구 저장
   - 멀티세션 지원

2. **캐시 전략 고도화**
   - SQL 결과 캐싱
   - 카탈로그 캐시 정책 최적화
   - CDN 통합 (정적 리소스)

3. **보안 강화**
   - Row-level security 지원
   - OAuth2/JWT 인증 추가
   - API 레이트 리미팅

### 10.3 장기 개선 (3-6개월)

1. **확장성 향상**
   - 비동기 작업 큐 (Celery)
   - 수평 확장 (Kubernetes)
   - 로드 밸런싱

2. **고급 NLU**
   - 의도 분류 모델 학습
   - 엔티티 인식 (NER)
   - 다중 언어 지원 확대

3. **시맨틱 레이어 자동화**
   - 스키마 변경 자동 감지
   - 메트릭 의존성 그래프
   - 자동 데이터 품질 검증

---

## 11. 결론

이 NL2SQL 플랫폼은 엔터프라이즈급 기능을 갖춘 프로덕션 준비 시스템입니다. 주요 강점은 다음과 같습니다:

### 11.1 강점

1. **견고한 아키텍처**: 명확한 계층 분리 및 모듈화
2. **다중 LLM 지원**: 프로바이더 간 유연한 전환
3. **포괄적인 검증**: 5단계 검증 파이프라인
4. **보안 중심**: 가드레일 + 비용 제한
5. **운영성**: 구조화된 로깅 + 모니터링 준비
6. **확장성**: 비동기 패턴 + 캐싱 전략

### 11.2 핵심 가치

- **개발자 친화적**: 명확한 코드 구조 및 문서화 가능성
- **비즈니스 친화적**: 비용 추정 및 제어
- **사용자 친화적**: SSE 스트리밍 실시간 피드백
- **유지보수성**: 테스트 가능한 모듈형 설계

이 시스템은 자연어 기반 데이터 분석 요구사항을 효과적으로 해결하며, 향후 확장 및 개선을 위한 견고한 기반을 제공합니다.

---

**작성자**: AI 분석 도구
**버전**: 1.0
**최종 업데이트**: 2025-11-07
