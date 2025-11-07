# 검증 아키텍처 (Validation Architecture)

**작성일**: 2025-11-07
**모듈**: validator.py, validation.py

---

## 1. 모듈 관계도

```
┌─────────────────────────────────────────────────────────────┐
│                     SQL 생성 완료                              │
└─────────────────────┬───────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│                validator.py (단일 검사)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ensure_safe(sql)                                      │   │
│  │  - 가드레일 정책 검사                                    │   │
│  │  - 위험한 SQL 연산 차단                                  │   │
│  │  - 실패 시: GuardrailViolation 예외                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ lint(sql) → List[Issue]                              │   │
│  │  - SQL 품질 검사                                        │   │
│  │  - SELECT * 금지                                        │   │
│  │  - 시간 필터 권장                                        │   │
│  │  - 반환: 이슈 리스트                                     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────────┐
│              validation.py (다단계 파이프라인)                   │
│                                                              │
│  run_pipeline(sql, plan, logger) → ValidationReport         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 1단계: lint_sql(sql)                                 │     │
│  │    - validator.lint() 호출                          │     │
│  │    - error 레벨 이슈 있으면 실패                       │     │
│  └────────────────────────────────────────────────────┘     │
│              ↓ (성공 시 계속)                                 │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 2단계: dry_run(sql)                                 │     │
│  │    - BigQuery Dry Run                              │     │
│  │    - 구문 검증 + 비용 추정                            │     │
│  └────────────────────────────────────────────────────┘     │
│              ↓ (성공 시 계속)                                 │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 3단계: explain(sql)                                 │     │
│  │    - EXPLAIN 실행 계획                               │     │
│  │    - 실패해도 계속 진행 (선택적)                        │     │
│  └────────────────────────────────────────────────────┘     │
│              ↓                                               │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 4단계: schema(sql)                                  │     │
│  │    - LIMIT 0으로 스키마 추출                          │     │
│  │    - 컬럼명, 타입 정보                                │     │
│  └────────────────────────────────────────────────────┘     │
│              ↓ (성공 시 계속)                                 │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 5단계: canary(sql)                                  │     │
│  │    - 실제 샘플 실행 (LIMIT 100)                       │     │
│  │    - 런타임 오류 사전 감지                             │     │
│  └────────────────────────────────────────────────────┘     │
│              ↓ (성공 시 계속)                                 │
│  ┌────────────────────────────────────────────────────┐     │
│  │ 6단계: domain_assertions(sql, plan)                 │     │
│  │    - 시맨틱 모델 기반 비즈니스 규칙                      │     │
│  │    - 메트릭 필터, 시간 버킷팅 등                        │     │
│  └────────────────────────────────────────────────────┘     │
│              ↓ (모두 성공)                                    │
│         ValidationReport 반환                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 두 모듈의 역할 차이

### `validator.py` - 단일 검사 도구

| 특징 | 설명 |
|------|------|
| **역할** | 개별 검사 함수 제공 |
| **사용처** | validation.py의 1단계(lint)에서 호출 |
| **검사 항목** | 보안(guardrail), 품질(lint) |
| **의존성** | 독립적 (다른 검증 단계와 무관) |
| **실행 방식** | 동기식, 빠름 |
| **비용** | 무료 |

#### 제공 함수
1. **`ensure_safe(sql)`**
   - 보안 검사
   - 위험한 SQL 차단
   - 예외 발생 (차단)

2. **`lint(sql)`**
   - 품질 검사
   - 이슈 리스트 반환
   - 예외 없음 (권고)

### `validation.py` - 다단계 파이프라인

| 특징 | 설명 |
|------|------|
| **역할** | 6단계 검증 파이프라인 orchestration |
| **사용처** | query.py에서 SQL 생성 후 호출 |
| **검사 항목** | 품질, 구문, 비용, 스키마, 실행, 도메인 |
| **의존성** | validator.py, connector.py, semantic 모델 |
| **실행 방식** | 순차 실행, Early Exit |
| **비용** | 단계별 차등 (무료 → 저렴 → 비쌈) |

#### 제공 함수
1. **`run_pipeline(sql, plan, logger)`**
   - 전체 파이프라인 실행
   - ValidationReport 반환

2. **개별 단계 함수들**
   - `lint_sql()`, `dry_run()`, `explain()`
   - `schema()`, `canary()`, `domain_assertions()`

---

## 3. 검증 단계 상세

### 1단계: Lint (validator.py 사용)

```python
# validation.py
def lint_sql(sql: str) -> StepResult:
    issues = validator.lint(sql)  # ← validator.py 호출
    ok = all(i.get("level") != "error" for i in issues)
    return StepResult(name="lint", ok=ok, meta={"issues": issues})
```

**검사 항목**:
- ✅ SELECT * 금지
- ✅ 이벤트 테이블 시간 필터 권장
- ✅ 시맨틱 엔티티 시간 필터 권장

**특징**:
- 빠름 (< 10ms)
- 무료
- 코드 정적 분석만 수행

### 2단계: Dry Run (BigQuery API)

```python
def dry_run(sql: str) -> StepResult:
    job = connector.run_query(sql, dry_run=True)
    total = job.total_bytes_processed
    return StepResult(name="dry_run", ok=True, meta={"total_bytes_processed": total})
```

**검사 항목**:
- ✅ SQL 구문 오류 감지
- ✅ 처리할 바이트 수 계산
- ✅ 예상 비용 산출

**특징**:
- 빠름 (< 1초)
- 무료 (dry_run은 과금 없음)
- BigQuery 서버에서 검증

### 3단계: Explain (선택적)

```python
def explain(sql: str) -> StepResult:
    job = connector.run_query(f"EXPLAIN {sql}")
    rows = list(job.result())
    return StepResult(name="explain", ok=True, meta={"rows": rows})
```

**검사 항목**:
- ✅ 쿼리 실행 계획 분석
- ✅ JOIN 순서 확인
- ✅ 인덱스 사용 확인

**특징**:
- 빠름 (< 1초)
- 무료
- **실패해도 계속 진행** (비치명적)

### 4단계: Schema

```python
def schema(sql: str) -> StepResult:
    wrapped = f"SELECT * FROM ({sql}) LIMIT 0"
    job = connector.run_query(wrapped, dry_run=False)
    schema = [{"name": f.name, "type": f.field_type} for f in job.schema]
    return StepResult(name="schema", ok=True, meta={"schema": schema})
```

**검사 항목**:
- ✅ 결과 컬럼명 확인
- ✅ 데이터 타입 확인
- ✅ NULL 허용 여부 확인

**특징**:
- 빠름 (< 1초)
- 거의 무료 (LIMIT 0)
- 실제 BigQuery 실행

### 5단계: Canary

```python
def canary(sql: str, limit_rows: int = 100) -> StepResult:
    canary_sql = f"SELECT * FROM ({sql}) LIMIT {limit_rows}"
    job = connector.run_query(canary_sql, dry_run=False)
    rows = [dict(r) for r in job.result()]
    return StepResult(name="canary", ok=True, meta={"rowcount": len(rows)})
```

**검사 항목**:
- ✅ 런타임 오류 감지
- ✅ 데이터 타입 불일치
- ✅ NULL 처리 오류
- ✅ 실제 데이터 샘플 확인

**특징**:
- 느림 (1-5초)
- 저렴 (소량 데이터만 처리)
- **가장 중요한 단계** (실제 실행)

### 6단계: Domain Assertions (시맨틱 모델 기반)

```python
def domain_assertions(sql: str, plan: Dict) -> StepResult:
    # 1. 메트릭 기본 필터 확인
    # 2. 시간 버킷팅 확인 (metric_over_time)
    # 3. 시간 필터 확인 (time_window)
    # 4. 엔티티 테이블 참조 확인
    # 5. GROUP BY 차원 확인
    return StepResult(name="assertions", ok=True)
```

**검사 항목**:
- ✅ 메트릭 필수 필터 (예: gmv는 status='completed')
- ✅ 시간 추이 쿼리 GROUP BY 검증
- ✅ 시간 윈도우 필터 검증
- ✅ 엔티티 테이블 참조 검증
- ✅ GROUP BY 차원 검증

**특징**:
- 빠름 (< 10ms)
- 무료
- **비즈니스 로직 검증**

---

## 4. 파이프라인 흐름도

### 성공 시나리오

```
SQL 생성
    ↓
validator.ensure_safe(sql) ← 가드레일 검사
    ↓ (통과)
validation.run_pipeline(sql, plan)
    ↓
[1] lint_sql ✅
    ↓
[2] dry_run ✅ → 75MB 처리, $0.0003
    ↓
[3] explain ❌ → (실패해도 계속)
    ↓
[4] schema ✅ → [{"name": "day", "type": "DATE"}, ...]
    ↓
[5] canary ✅ → 10행 반환
    ↓
[6] assertions ✅ → 모든 규칙 통과
    ↓
ValidationReport (모든 단계 성공)
    ↓
실제 쿼리 실행 (query.py)
```

### 실패 시나리오 (Early Exit)

```
SQL 생성
    ↓
validator.ensure_safe(sql)
    ↓ (통과)
validation.run_pipeline(sql, plan)
    ↓
[1] lint_sql ✅
    ↓
[2] dry_run ❌ → 구문 오류: "Column 'xyz' not found"
    ↓
ValidationReport (2단계만 포함)
    ↓
실행 중단 (에러 반환)
```

---

## 5. 코드 사용 예시

### 예시 1: query.py에서의 사용

```python
from app.services import validator, validation

# SQL 생성 후
sql = "SELECT DATE(order_date) AS day, COUNT(*) FROM orders GROUP BY day"

# 1. 가드레일 검사 (validator.py)
try:
    validator.ensure_safe(sql)
except validator.GuardrailViolation as e:
    return {"error": "Security violation"}

# 2. 다단계 검증 (validation.py)
report = validation.run_pipeline(
    sql=sql,
    plan={"metric": "orders", "intent": "metric_over_time"},
    logger=logger
)

# 3. 결과 확인
if all(step.ok for step in report.steps):
    # 모두 성공 → 실행
    result = executor.run(sql, dry_run=False)
else:
    # 실패한 단계 찾기
    failed = next(s for s in report.steps if not s.ok)
    return {"error": f"Validation failed at {failed.name}: {failed.message}"}
```

### 예시 2: 위험한 SQL 차단

```python
sql = "DELETE FROM orders WHERE order_id = 123"

# validator.ensure_safe()에서 차단
try:
    validator.ensure_safe(sql)
except validator.GuardrailViolation:
    # 가드레일 위반 → 즉시 차단
    # validation.run_pipeline()까지 도달하지 못함
    print("Security violation: DELETE not allowed")
```

### 예시 3: SELECT * 감지

```python
sql = "SELECT * FROM orders"

# lint에서 감지
issues = validator.lint(sql)
# [{"level": "error", "code": "no_select_star", "message": "SELECT * is not allowed"}]

# run_pipeline의 1단계에서 실패
report = validation.run_pipeline(sql)
# report.steps[0].ok = False
# 후속 단계 실행 안 됨
```

---

## 6. 검증 레벨

### ERROR (실행 차단)

| 검사 | 모듈 | 단계 | 차단 여부 |
|------|------|------|----------|
| DELETE/UPDATE/INSERT | validator.py | guardrail | ✅ 예외 발생 |
| SELECT * | validator.py | lint | ✅ 파이프라인 중단 |
| 구문 오류 | validation.py | dry_run | ✅ 파이프라인 중단 |

### WARNING (실행 허용)

| 검사 | 모듈 | 단계 | 차단 여부 |
|------|------|------|----------|
| 시간 필터 누락 | validator.py | lint | ❌ 경고만 |
| EXPLAIN 실패 | validation.py | explain | ❌ 계속 진행 |

---

## 7. 모듈 의존성

### validator.py 의존성
```
validator.py
    ├─ guardrails.json (보안 정책)
    ├─ app.semantic.loader (시맨틱 모델)
    └─ app.deps (로거)
```

### validation.py 의존성
```
validation.py
    ├─ validator.py (lint, ensure_safe)
    ├─ app.bq.connector (BigQuery 클라이언트)
    ├─ app.semantic.loader (시맨틱 모델)
    └─ app.deps (로거)
```

---

## 8. 시맨틱 모델 활용

### validator.py에서

```python
# 시맨틱 엔티티별 시간 필터 검사
sem = load_semantic_root().get("semantic.yml", {})
entities = sem.get("entities")

for entity in entities:
    if entity.has_time_dimension and entity.table in sql:
        # 시간 필터 권장
        if no_time_filter:
            issues.append({"level": "warning", ...})
```

### validation.py에서

```python
# 도메인 규칙 검증
metrics_def = load_semantic_root().get("metrics_definitions.yaml", {})

for metric in metrics_def:
    if metric.name == plan["metric"]:
        # 기본 필터 검증
        for filter in metric.default_filters:
            if filter not in sql:
                return StepResult(ok=False, ...)
```

---

## 9. 검증 비용 분석

| 단계 | 실행 시간 | 비용 | BigQuery 호출 | 데이터 처리 |
|------|----------|------|--------------|-----------|
| **1. Lint** | < 10ms | 무료 | ❌ | ❌ |
| **2. Dry Run** | < 1s | 무료 | ✅ | ❌ |
| **3. Explain** | < 1s | 무료 | ✅ | ❌ |
| **4. Schema** | < 1s | ~$0.00001 | ✅ | LIMIT 0 |
| **5. Canary** | 1-5s | ~$0.0001 | ✅ | LIMIT 100 |
| **6. Assertions** | < 10ms | 무료 | ❌ | ❌ |
| **총합** | ~3-8s | ~$0.00011 | - | - |

### 비용 절감 전략

1. **Early Exit**: 초기 단계 실패 시 즉시 중단
2. **Explain 선택적**: 실패해도 계속 진행
3. **LIMIT 사용**: Schema(0), Canary(100)
4. **무료 단계 우선**: Lint, Dry Run, Assertions 먼저

---

## 10. 오류 처리 전략

### 가드레일 위반 (validator.py)

```python
try:
    validator.ensure_safe(sql)
except validator.GuardrailViolation:
    # 즉시 차단, 파이프라인 실행 안 함
    raise HTTPException(403, "Security violation")
```

### 검증 실패 (validation.py)

```python
report = validation.run_pipeline(sql, plan)

# 실패한 단계 찾기
failed_steps = [s for s in report.steps if not s.ok]

if failed_steps:
    # 첫 번째 실패 단계
    first_failure = failed_steps[0]

    # Repair 시도 (LLM)
    if first_failure.name in ["dry_run", "assertions"]:
        repaired_sql = repair.attempt_repair(question, sql, first_failure.message)
        # 재검증
        report = validation.run_pipeline(repaired_sql, plan)
```

---

## 11. 실제 사용 흐름 (query.py)

```python
from app.services import validator, validation

# 1. SQL 생성
sql = sqlgen.generate(plan, question)

# 2. 가드레일 검사 (validator.py)
validator.ensure_safe(sql)

# 3. 다단계 검증 (validation.py)
report = validation.run_pipeline(sql, plan=plan, logger=logger)

# 4. 검증 실패 시 수정 시도
if not all(s.ok for s in report.steps):
    # LLM 기반 수정
    repaired_sql = repair.attempt_repair(question, sql, error)

    # 재검증
    validator.ensure_safe(repaired_sql)
    report = validation.run_pipeline(repaired_sql, plan=plan, logger=logger)

# 5. 실행
if all(s.ok for s in report.steps):
    result = executor.run(sql, dry_run=req.dry_run)
```

---

## 12. 검증 결과 구조

### StepResult

```python
@dataclass
class StepResult:
    name: str           # 단계명 ("lint", "dry_run", ...)
    ok: bool           # 성공 여부
    message: str = ""  # 오류 메시지
    meta: Dict = {}    # 메타데이터 (바이트 수, 스키마 등)
```

**예시**:
```python
StepResult(
    name="dry_run",
    ok=True,
    message="",
    meta={"total_bytes_processed": 75832225}
)
```

### ValidationReport

```python
@dataclass
class ValidationReport:
    steps: List[StepResult]  # 모든 단계 결과
    sql: str                 # 검증된 SQL
    schema: List[Dict] | None  # 결과 스키마
```

**예시**:
```python
ValidationReport(
    steps=[
        StepResult(name="lint", ok=True, ...),
        StepResult(name="dry_run", ok=True, meta={"total_bytes_processed": 75832225}),
        StepResult(name="explain", ok=False, message="Not supported"),
        StepResult(name="schema", ok=True, meta={"schema": [...]})
    ],
    sql="SELECT ...",
    schema=[
        {"name": "day", "type": "DATE", "mode": "NULLABLE"},
        {"name": "orders", "type": "INT64", "mode": "NULLABLE"}
    ]
)
```

---

## 13. 요약 비교표

| 항목 | validator.py | validation.py |
|------|-------------|--------------|
| **타입** | 유틸리티 모듈 | 파이프라인 orchestrator |
| **함수 개수** | 3개 | 7개 (6개 단계 + 1개 runner) |
| **주 기능** | 보안, 품질 검사 | 다단계 검증 파이프라인 |
| **BigQuery 호출** | ❌ 없음 | ✅ 있음 (4단계) |
| **시맨틱 모델** | ✅ 사용 (엔티티) | ✅ 사용 (메트릭, 엔티티) |
| **실행 방식** | 동기식 | 순차 실행 (Early Exit) |
| **오류 처리** | 예외 발생 | StepResult 반환 |
| **사용처** | validation.py의 1단계 | query.py의 검증 단계 |

---

## 14. 향후 개선 방향

### validator.py
1. **동적 가드레일**: 시맨틱 모델에서 정책 로드
2. **커스텀 린트 규칙**: YAML 기반 규칙 정의
3. **성능 린트**: 비효율적 패턴 감지 (SELECT DISTINCT 남용 등)

### validation.py
1. **병렬 실행**: 독립적인 단계 병렬 처리
2. **캐싱**: 동일 SQL 재검증 시 캐시 사용
3. **커스텀 파이프라인**: 단계 선택적 활성화
4. **7단계 추가**: Full Execution (모든 데이터)

---

## 15. 관계 요약

```
┌───────────────────┐
│  validator.py     │  ← 기본 검사 도구
│  - ensure_safe()  │     (보안, 품질)
│  - lint()         │
└─────────┬─────────┘
          │
          │ (호출)
          ↓
┌───────────────────┐
│  validation.py    │  ← 파이프라인 orchestrator
│  - run_pipeline() │     (6단계 검증)
│  - lint_sql()     │  ──┐
│  - dry_run()      │    │
│  - explain()      │    │ 6단계
│  - schema()       │    │
│  - canary()       │    │
│  - assertions()   │  ──┘
└─────────┬─────────┘
          │
          │ (결과 반환)
          ↓
┌───────────────────┐
│    query.py       │  ← API 엔드포인트
│  - 검증 성공 시   │     (검증 결과 활용)
│    실제 쿼리 실행  │
└───────────────────┘
```

**핵심 관계**:
- `validator.py`는 **기본 도구** (재사용 가능한 검사 함수)
- `validation.py`는 **파이프라인 관리자** (validator + BigQuery 검증 통합)
- `query.py`는 **최종 사용자** (검증 결과로 실행 여부 결정)

---

**작성자**: AI 분석 도구
**버전**: 1.0
**최종 업데이트**: 2025-11-07
