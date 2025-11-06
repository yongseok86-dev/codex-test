# 프로젝트 개요
- **프로젝트명:** NL2SQL 시멘틱 레이어 에이전트 구축 (BigQuery·GA4 기반)
- **고객 도메인:** Mall 유입 고객 여정/행동 분석
- **핵심 데이터소스:** `ns-extr-data.analytics_310486481.events_fresh_20251106`
- **목표:** 자연어 질의 → 시멘틱 레이어 → BigQuery 최적화 SQL 생성 및 실행, 신뢰 가능한 결과/비용 통제, 운영 관측 가능성 확보
- **기간(초안):** 2025-11-10 ~ 2026-01-09 (8주)  
  - Week 1~2: 데이터/시멘틱 정합·골든세트 v0  
  - Week 3~5: 에이전트 핵심 컴포넌트 개발·가드레일·성능  
  - Week 6~7: UX/통합·보안·관측·베타  
  - Week 8: 안정화·문서화·GA 결정

---

# 성공지표(AC)
- **정확도:** Top-1 정답 SQL 또는 결과 일치 ≥ 80%(v1), Top-3 ≥ 92%
- **성능/비용:** 대표 20문항 평균 스캔바이트 50%↓(캐시·머티뷰 적용 전 대비), P50 지연 30%↓
- **안전성:** 무파티션·과금초과 쿼리 100% 차단, 권한오류/PII 노출 0건
- **관측:** 모든 실행에 Job Labels 수집율 100%, 실패 유형 자동 분류 커버리지 ≥ 90%
- **UX:** 파일럿 사용자 만족도(내부 설문) ≥ 4.2/5, 수정가능 토글로 재시도 성공률 ≥ 30%

---

# 범위(Scope)
## 포함
- 시멘틱 레이어(v0→v1): user/session/event, Mall 유입 사전, KPI 정의서, 용어사전
- 에이전트: NLU 파서, 시멘틱 플래너, SQL 생성기(BigQuery 방언), 검증기(DRY RUN/EXPLAIN), 실행기, 결과요약기
- 성능/캐시: 일자×소스×이벤트 요약 머티뷰, 퍼널 집계 테이블, 파티션·클러스터링 가이드
- 보안/거버넌스: Authorized View, RLS(옵션), 마스킹
- 관측/로그: Job labels, 실행/해석 로그, 실패 유형 태깅
- UX: 해석요약·수정 토글(기간/채널/디바이스), SQL 미리보기, 근거 링크

## 제외(초기)
- 다국어(영문) 지원 고도화, 고급 경로탐색 시각화, 오프라인 배치 리포트 자동화

---

# 일정·마일스톤
| 주차 | 마일스톤 | 산출물 |
|---|---|---|
| W1 (11/10–11/14) | Mall 소스/파라미터 검증 | `mall_sources_60d`, `ga4_param_*` 테이블, 용어사전 초안 |
| W2 (11/17–11/21) | 시멘틱 뷰 v0·KPI 정의·골든세트 v0(15문항) | `semantic_*` 뷰, `metrics_definitions.yaml`, 골든세트 스냅샷 |
| W3 (11/24–11/28) | 파서·플래너 v0 + SQL 생성기 v0 | `planner_rules.md`, `prompt.sqlgen.txt`, 생성 SQL 유효성 로그 |
| W4 (12/01–12/05) | 가드레일·검증기·실행기 | `guardrails.json`, DRY RUN 훅, 실행 라벨링 |
| W5 (12/08–12/12) | 성능/캐시 레이어 | 머티뷰/요약테이블 DDL, 비용·지연 리포트 |
| W6 (12/15–12/19) | UX 통합·보안 정책 | UX 프로토타입, Authorized View/RLS/마스킹 스크립트 |
| W7 (12/22–12/26) | 베타(파일럿)·관측 대시보드 | 베타 릴리즈 노트, 실패 코드북, 대시보드 스케치 |
| W8 (12/29–01/09) | 안정화·문서화·Go/No-Go | 운영 핸드북, 회귀테스트 결과, GA 체크리스트 |

> 휴무 기간(말일~신정)에 따라 W8은 2주 캘린더를 포괄

---

# 작업 분해(WBS)
## 1. 데이터/시멘틱 (W1–W2)
- D1. Mall 소스/미디엄/캠페인 후보 추출·병합 (owner: DA)
- D2. event_params 키 존재율·타입 확인, KPI 정의에 필요한 키 보완 (DA)
- D3. `semantic_user/session/event` 뷰 DDL 배포 (DE)
- D4. KPI 정의서·용어사전 v0 완성 (DA)
- D5. 골든세트 v0 작성(15문항)·스냅샷 저장 (DA)

## 2. 에이전트 코어 (W3–W4)
- A1. NL 파서(한글 상대기간·동의어 사전) (App)
- A2. 시멘틱 플래너(조인 경로/그룹바이/윈도우/필터) (App)
- A3. SQL 생성기(BigQuery 최적화, 파티션 강제) (App)
- A4. 검증기(DRY RUN/EXPLAIN/정보스키마) (App)
- A5. 실행기(매개변수화·job labels·재시도/타임아웃) (App)

## 3. 가드레일/성능 (W4–W5)
- G1. `guardrails.json` 적용, 무파티션/SELECT * 차단 (App)
- G2. 비용 상한(`maximum_bytes_billed`) 기본값·오버라이드 (App)
- P1. 일자×소스×이벤트 머티뷰·퍼널 집계 테이블 (DE)
- P2. BI Engine/클러스터링 가이드 (DE)

## 4. 보안/관측/UX (W6–W7)
- S1. Authorized View, RLS, 마스킹 배포 (DE)
- O1. 실행/해석 로그 테이블, 실패 유형 태깅 (DE)
- U1. 해석요약·수정 토글 UX, SQL 미리보기 (App)
- U2. 파일럿 온보딩·설문/피드백 수집 (PO/DA)

## 5. 안정화/문서화 (W8)
- R1. 회귀 테스트 자동화(골든세트) (App/DA)
- R2. 운영 핸드북·보안 점검표·FAQ (DA/DE)
- R3. Go/No-Go 미팅·릴리즈 노트 (PO)

---

# 환경/아키텍처
- **런타임/프레임워크:** Python 3.11 + **uv**(초고속 패키지/런처) + **FastAPI**
- **패키지/설정:** `pyproject.toml` + `uv.lock` 커밋, `pydantic-settings`로 환경변수 관리
- **서빙:** Uvicorn(ASGI) + FastAPI, `/healthz`·`/readyz` 헬스엔드포인트
- **로깅/관측:** 표준 `logging` JSON + Google Cloud Logging Handler, OpenTelemetry(선택) Trace/Metric
- **데이터레이어:** BigQuery(GA4 Export), Authorized Views, Materialized Views
- **시멘틱 레이어:** YAML 정의 + 뷰/UDTF/UDF(필요 시)
- **가드레일:** DRY RUN·무파티션·MAX BYTES 정책, 금칙어 필터
- **보안:** IAM 최소권한, RLS/마스킹, Secret Manager(키/토큰)

## 개발 환경 구성 (Python + uv + FastAPI)
```bash
# 1) uv 설치 및 프로젝트 초기화
curl -LsSf https://astral.sh/uv/install.sh | sh
uv init nl2sql-agent && cd nl2sql-agent

# 2) 의존성 추가
uv add fastapi uvicorn[standard] google-cloud-bigquery google-cloud-logging pydantic-settings python-dotenv
uv add --dev pytest httpx pytest-asyncio ruff mypy

# 3) 로컬 실행
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2
```

**`pyproject.toml`(발췌)**
```toml
[tool.ruff]
line-length = 100
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**폴더 구조 제안**
```
app/
 ├─ main.py           # FastAPI 엔트리, 라우팅
 ├─ deps.py           # DI/클라이언트(BigQuery, Logging)
 ├─ config.py         # Pydantic Settings
 ├─ routers/
 │   ├─ query.py      # NL→SQL 요청/응답
 │   └─ health.py     # /healthz, /readyz
 ├─ services/
 │   ├─ nlu.py        # 의도/슬롯 추출
 │   ├─ planner.py    # 시멘틱 플래너
 │   ├─ sqlgen.py     # BigQuery SQL 생성기
 │   ├─ validator.py  # DRY RUN/EXPLAIN/가드레일
 │   └─ executor.py   # 실행/요약
 ├─ semantic/
 │   ├─ semantic.yml
 │   └─ metrics_definitions.yaml
 └─ utils/
     └─ timeparse.py  # 한국어 기간 파서
```

## 공통 로깅 구성(표준 JSON + Cloud Logging)
```python
# app/deps.py
import logging
from google.cloud.logging_v2.handlers import StructuredLogHandler

logger = logging.getLogger("app")
handler = StructuredLogHandler()  # Cloud Run 상에서 자동 추적/연계
handler.setLevel(logging.INFO)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# 사용 예: request-scoped context
logger.info("query_received", extra={
    "intent": intent,
    "metric": metric,
    "mall_flag": mall_flag,
})
```

**요청/응답 로깅 미들웨어**
```python
from fastapi import FastAPI, Request
from time import perf_counter
app = FastAPI()

@app.middleware("http")
async def access_log(request: Request, call_next):
    t0 = perf_counter()
    response = await call_next(request)
    dt = perf_counter() - t0
    app.logger.info("access", extra={
        "path": request.url.path, "status": response.status_code, "latency_ms": int(dt*1000)
    })
    return response
```

## GCP Cloud Run 배포 구성
**Dockerfile(경량·보안)**
```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim as base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir uv && uv sync --frozen
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

**배포(예시 명령)**
```bash
gcloud run deploy nl2sql-agent \
  --source . \
  --region=asia-northeast3 \
  --allow-unauthenticated \
  --cpu=1 --memory=1Gi --concurrency=40 \
  --max-instances=5 --min-instances=0 \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT,ENV=prod \
  --service-account=nl2sql-agent@${PROJECT}.iam.gserviceaccount.com
```

**권장 설정**
- VPC 커넥터(필요 시)로 사내 리소스 접근
- Secret Manager: 키 주입(`--set-secrets`)
- Cloud Run 리비전 태깅(blue/green), 트래픽 분할
- Cloud Build/GitHub Actions로 CI/CD 파이프라인

---

# 위험·대응
| 리스크 | 영향 | 완화 |
|---|---|---|
| GA4 파라미터 결측/명칭 상이 | 정확도 하락 | Week1 키 센서스·용어사전 업데이트 파이프라인 |
| 퍼널 집계 중복 | KPI 왜곡 | grain 주석·브리지 전략·회귀테스트 |
| 비용 급증 | 예산 초과 | 가드레일·머티뷰·BI Engine·쿼리 캐시 |
| 권한/PII 이슈 | 컴플라이언스 리스크 | Authorized View, 마스킹, RLS, 감사로그 |
| 사용자 기대 불일치 | 도입 저항 | 해석요약 UI·수정 토글·피드백 루프 |

---

# 품질보증·테스트
- **정확도 테스트:** 골든세트 v0(15) → v1(40), Top-1/Top-3 평가
- **회귀 테스트:** 사전/시멘틱 변경 시 자동 재평가
- **부하/비용 테스트:** 대표 쿼리 20개, 파라미터 스윕으로 스캔바이트·지연 측정
- **보안 테스트:** 권한/마스킹/RLS 케이스, 금칙어 차단 검증

---

# 배포/운영 체크리스트(단독 개발용)
- [ ] Cloud Run 서비스·서비스계정·IAM 설정(원 최소권한)
- [ ] 지역: `asia-northeast3(Seoul)`
- [ ] Secret Manager 바인딩 및 런타임 주입
- [ ] 모니터링 대시보드(Log Explorer·Error Reporting·Trace) 구성
- [ ] 알림 룰: 5xx 비율, 지연, BigQuery 비용 급증
- [ ] 롤백: 이전 리비전 신속 전환(트래픽 100%)

# 인수인계 산출물 목록
- `semantic.yml`, `metrics_definitions.yaml`, `guardrails.json`
- `semantic_*` 뷰 DDL, `materialized_views.sql`
- `planner_rules.md`, `prompt.sqlgen.txt`
- `goldenset/*` SQL·결과 스냅샷, 회귀 테스트 스크립트
- 운영 핸드북, 보안 점검표, FAQ, 릴리즈 노트

---

# 커뮤니케이션/의사결정
- 주간 스탠드업(월), 중간 데모(격주 수요일), 위험/이슈 트래킹(전담 보드)
- 변경관리: 사전/시멘틱/가드레일 변경 시 PR·리뷰 2인 승인

---

# Go/No-Go 기준
- 정확도/비용/안전성/UX AC 달성, 파일럿 2주 지표 안정, 주요 리스크 Close → **Go**
- 미달성 항목 잔존 시 보강 플랜 수립 후 결정 → **Hold**

