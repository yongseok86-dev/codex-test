# 메타 질문 처리 가이드

**메타 질문**: SQL 생성이 아닌 시스템 정보 요청 질문

---

## 메타 질문 유형

### 1. 스키마 정보 요청
```
"분석 할 수 있는 디멘전, 메져를 알려줘"
"어떤 메트릭을 조회할 수 있어?"
"사용 가능한 차원이 뭐야?"
```

### 2. 예시 질문 요청
```
"어떤 질문을 할 수 있어?"
"예시를 보여줘"
```

### 3. 도움말 요청
```
"사용법 알려줘"
"어떻게 사용해?"
```

---

## 해결 방안

### 방안 1: NLU에 schema_info Intent 추가 (권장)

#### 1-1. semantic.yml 수정

```yaml
nlu_keywords:
  intents:
    schema_info:  # 새로 추가
      - '알려줘'
      - '보여줘'
      - '무엇'
      - '어떤'
      - '디멘전'
      - '메져'
      - 'dimension'
      - 'measure'
      - '사용 가능한'
      - '분석 가능한'
      - '예시'
      - '도움말'
    metric_over_time:
      - '추이'
      - 'trend'
    ...

planner_config:
  valid_intents:
    - metric
    - metric_over_time
    - comparison
    - aggregation
    - schema_info  # 새로 추가
```

#### 1-2. query.py에 메타 질문 처리 추가

```python
# app/routers/query.py

@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    # ... NLU 및 Planner 실행

    # 메타 질문 감지
    if plan.get("intent") == "schema_info":
        # SQL 생성하지 않고 스키마 정보 반환
        schema_response = generate_schema_info_response(plan, norm_q)
        return QueryResponse(
            sql="-- Schema information (no SQL generated)",
            dry_run=True,
            rows=None,
            metadata={
                "intent": "schema_info",
                "schema_info": schema_response
            }
        )

    # 일반 SQL 생성 계속...
```

#### 1-3. 스키마 정보 생성 함수

```python
# app/services/schema_info.py (새 파일)

def generate_schema_info_response(plan: Dict, question: str) -> Dict:
    """
    스키마 정보를 자연어 응답으로 생성합니다.
    """
    semantic = load_semantic_root()
    semantic_model = semantic.get("semantic.yml", {})

    # 엔티티 정보 추출
    entities = semantic_model.get("entities", [])

    # 메트릭 정보 추출
    metrics = semantic_model.get("metrics", [])

    # 차원 수집
    all_dimensions = []
    for entity in entities:
        if isinstance(entity, dict):
            dims = entity.get("dimensions", [])
            for dim in dims:
                if isinstance(dim, dict):
                    all_dimensions.append({
                        "name": dim.get("name"),
                        "entity": entity.get("name"),
                        "type": dim.get("type", "string")
                    })

    # 메트릭 수집
    all_metrics = []
    for metric in metrics:
        if isinstance(metric, dict):
            all_metrics.append({
                "name": metric.get("name"),
                "description": metric.get("description", ""),
                "expr": metric.get("expr", "")
            })

    # LLM으로 자연어 응답 생성
    if question에 "디멘전" in question:
        # 차원 위주 응답
        return {
            "type": "dimensions",
            "dimensions": all_dimensions,
            "count": len(all_dimensions)
        }
    elif "메져" in question or "메트릭" in question:
        # 메트릭 위주 응답
        return {
            "type": "metrics",
            "metrics": all_metrics,
            "count": len(all_metrics)
        }
    else:
        # 전체 응답
        return {
            "type": "schema_overview",
            "dimensions": all_dimensions,
            "metrics": all_metrics,
            "entities": len(entities)
        }
```

---

### 방안 2: LLM이 스키마 정보 SQL 생성 (현재 방식)

LLM이 스키마를 조회하는 SQL을 생성하도록 프롬프트 개선:

```python
# sqlgen.py 프롬프트에 추가

prompt = f"""...

# 메타 질문 처리
질문이 "사용 가능한 차원/메트릭 알려줘" 같은 메타 질문이면:
- 시맨틱 모델 정보를 자연어로 요약하는 SELECT 문 생성
- 예: SELECT '사용 가능한 메트릭: orders, gmv, sessions, users, events' AS info

사용 가능한 엔티티:
{entities_list}

사용 가능한 메트릭:
{metrics_list}

사용 가능한 차원:
{dimensions_list}
"""
```

**응답 예시**:
```sql
SELECT
  '사용 가능한 메트릭' AS category,
  'orders, gmv, sessions, users, events' AS available_items
UNION ALL
SELECT
  '사용 가능한 차원',
  'event_date, user_pseudo_id, device.category, geo.country'
```

---

### 방안 3: 전용 엔드포인트 추가 (가장 깔끔)

```python
# app/routers/schema.py (새 파일)

from fastapi import APIRouter
from app.semantic.loader import load_semantic_root

router = APIRouter(prefix="/api/schema", tags=["schema"])

@router.get("/dimensions")
async def get_dimensions():
    """사용 가능한 차원 목록 반환"""
    semantic = load_semantic_root()
    semantic_model = semantic.get("semantic.yml", {})
    entities = semantic_model.get("entities", [])

    dimensions = []
    for entity in entities:
        if isinstance(entity, dict):
            entity_name = entity.get("name")
            for dim in entity.get("dimensions", []):
                if isinstance(dim, dict):
                    dimensions.append({
                        "name": dim.get("name"),
                        "entity": entity_name,
                        "type": dim.get("type", "string"),
                        "description": dim.get("description", "")
                    })

    return {"dimensions": dimensions, "count": len(dimensions)}

@router.get("/metrics")
async def get_metrics():
    """사용 가능한 메트릭 목록 반환"""
    semantic = load_semantic_root()
    metrics = semantic.get("metrics_definitions.yaml", {}).get("metrics", [])

    return {
        "metrics": [
            {
                "name": m.get("name"),
                "description": m.get("description", ""),
                "expr": m.get("expr", "")
            }
            for m in metrics if isinstance(m, dict)
        ],
        "count": len(metrics)
    }

@router.get("/schema")
async def get_schema():
    """전체 스키마 정보 반환"""
    dimensions_response = await get_dimensions()
    metrics_response = await get_metrics()

    return {
        "dimensions": dimensions_response["dimensions"],
        "metrics": metrics_response["metrics"],
        "total_dimensions": dimensions_response["count"],
        "total_metrics": metrics_response["count"]
    }
```

**사용법**:
```bash
# 차원 조회
curl http://localhost:8080/api/schema/dimensions

# 메트릭 조회
curl http://localhost:8080/api/schema/metrics

# 전체 스키마
curl http://localhost:8080/api/schema/schema
```

---

### 방안 4: 프론트엔드에서 처리

```javascript
// frontend/src/views/ChatView.vue

async function onSend(text) {
  // 메타 질문 감지
  const metaKeywords = ['알려줘', '보여줘', '디멘전', '메져', '예시', '도움말'];
  const isMetaQuery = metaKeywords.some(kw => text.includes(kw));

  if (isMetaQuery && (text.includes('디멘전') || text.includes('메져'))) {
    // 스키마 정보 엔드포인트 호출
    const response = await fetch('/api/schema/schema');
    const data = await response.json();

    // 자연어 응답 생성
    const answer = `
사용 가능한 메트릭 (${data.total_metrics}개):
${data.metrics.map(m => `- ${m.name}: ${m.description}`).join('\n')}

사용 가능한 차원 (${data.total_dimensions}개):
${data.dimensions.map(d => `- ${d.name} (${d.entity})`).join('\n')}
`;

    addMessage('assistant', answer);
    return;
  }

  // 일반 SQL 질문 처리
  // ...
}
```

---

## 권장 구현 (단계별)

### Phase 1: 빠른 해결 (프론트엔드)

프론트엔드에서 메타 질문을 감지하고 하드코딩된 응답 반환:

```javascript
const META_RESPONSES = {
  'dimensions': `
📊 사용 가능한 차원:

**Event 엔티티:**
- event_date: 이벤트 날짜
- event_name: 이벤트 이름
- user_pseudo_id: 사용자 ID

**Session 엔티티:**
- device.category: 디바이스 (mobile, desktop, tablet)
- geo.country: 국가
- traffic_source.medium: 유입 채널

**시간 차원:**
- 시간대별, 일별, 주별, 월별
`,

  'metrics': `
📈 사용 가능한 메트릭:

- **orders**: 주문 건수
- **gmv**: 총 거래액 (매출)
- **sessions**: 세션 수
- **users**: 사용자 수
- **events**: 이벤트 수
- **conversion_rate**: 전환율
- **aov**: 평균 주문 금액
- **bounce_rate**: 이탈률
`
};

if (text.includes('디멘전') || text.includes('차원')) {
  addMessage('assistant', META_RESPONSES.dimensions);
  return;
}

if (text.includes('메져') || text.includes('메트릭')) {
  addMessage('assistant', META_RESPONSES.metrics);
  return;
}
```

### Phase 2: API 엔드포인트 추가

`/api/schema` 엔드포인트 생성하여 동적으로 스키마 정보 제공

### Phase 3: NLU 통합

`schema_info` intent를 정식으로 추가하여 자동 처리

---

## 즉시 적용 가능한 해결책

가장 빠른 방법은 **.env 파일 수정**입니다:

```bash
# .env

# 메타 질문 감지 패턴 (선택적)
meta_query_keywords=알려줘,보여줘,디멘전,메져,도움말,예시
```

그리고 `query.py`에 간단한 체크 추가:

```python
# 메타 질문 간단 감지
meta_keywords = ['알려줘', '보여줘', '디멘전', '메져', '차원', '메트릭']
is_meta = any(kw in norm_q for kw in meta_keywords) and not any(kw in norm_q for kw in ['추이', '건수', '합계'])

if is_meta:
    # 스키마 정보 반환
    schema_info = {
        "available_metrics": ["orders", "gmv", "sessions", "users", "events"],
        "available_dimensions": ["event_date", "device.category", "geo.country", "traffic_source.medium"],
        "message": "위 메트릭과 차원을 조합하여 질문하세요. 예: '지난 7일 디바이스별 주문 추이'"
    }

    return QueryResponse(
        sql="-- Schema information request (no SQL generated)",
        dry_run=True,
        rows=None,
        metadata={"schema_info": schema_info}
    )
```

---

## 추천 방식

**당장 테스트하려면**: 프론트엔드 하드코딩 (Phase 1)
**프로덕션**: API 엔드포인트 추가 (Phase 2) + NLU 통합 (Phase 3)

이렇게 하면 사용자가 "사용 가능한 메트릭 알려줘"라고 물으면 SQL 대신 스키마 정보를 자연어로 답변할 수 있습니다!