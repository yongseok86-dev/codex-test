# 목표
- **자연어 → SQL(NL2SQL)** 질의 정확도와 실행 성능을 높이는 에이전트 구축
- **시멘틱 레이어**(도메인 개념, 지표, 차원, 관계, 규칙)로 물리 스키마의 불일치/복잡성을 캡슐화
- 거버넌스(보안/권한), 비용 통제, 평가/관측 가능성까지 포함한 **운영 가능한** 시스템

---

# 단계별 TODO

## 0) 범위·성공기준 정의
- [ ] 1차 사용자/도메인 선정(예: 주문·고객 분석)
- [ ] 대표 질문 30~50개 수집(자연어 그대로)
- [ ] 성공지표 정의: 정답률(Top-1/Top-k), 평균 쿼리비용(GB), 평균 지연, 커버리지(의도 매핑율)
- [ ] 프라이버시·보안 요구 정의(열/행 수준, 테넌트 격리)
- [ ] 가드레일 정책(금칙어, 민감항목 마스킹, 데이터 신뢰도 경고) 수립

## 1) 소스 인벤토리 & 프로파일링 (BigQuery)
- [ ] 대상 데이터셋·테이블 목록화; 파티션/클러스터링·행수·스캔 크기·신선도 점검
- [ ] 컬럼 카디널리티/결측치/분포 프로파일링
- [ ] 조인 키 품질 평가(중복/NULL/외래키 무결성 근사)
- [ ] 비용 위험 테이블 식별(거대 테이블, 와이드 스키마)
- [ ] **물리 스키마 → 개념 스키마 초안** 작성

## 2) 시멘틱 레이어 모델링
- [ ] **엔터티**(예: Customer, Order, Product) 정의 및 **기본 grain** 명시
- [ ] **차원(Dimension)**: 속성, 정규화/코드테이블 매핑, 서브타입(예: 채널, 지역)
- [ ] **지표(Measure/Metric)**: 집계함수, 분모/분자, 윈도우 정의(예: 7일 유지율), 필터 규칙
- [ ] **관계(Relationships)**: 조인 경로, 1:N/홍합 조인 방지 규칙, 브리지/스냅샷 테이블 설계
- [ ] **비즈니스 규칙**: 취소/환불 처리, 중복 제거(unique key), 시간여행(유효기간) 규칙
- [ ] 동의어/한국어-영어 용어사전 구축(예: “구매건수”=orders_count)
- [ ] **모델 산출물**: semantic.yml(아래 예시), 데이터 카탈로그 페이지

### 시멘틱 모델 YAML 예시(발췌)
```yaml
entities:
  - name: customer
    grain: customer_id
    table: `proj.ds.customer`
    dimensions:
      - name: customer_id
      - name: join_date
      - name: channel
        synonyms: [채널]
  - name: order
    grain: order_id
    table: `proj.ds.orders`
    relationships:
      - to: customer
        type: many_to_one
        on: order.customer_id = customer.customer_id
    dimensions:
      - name: order_date
        type: date
      - name: status
        valid_values: [completed, cancelled, returned]
    measures:
      - name: orders
        expr: COUNT(DISTINCT order_id)
      - name: gmvs
        expr: SUM(net_amount)
        filters:
          - status = 'completed'
metrics:
  - name: gmv
    expr: SUM(order.net_amount)
    default_filters: [order.status='completed']
  - name: aov
    expr: gmv / NULLIF(COUNT(DISTINCT order_id),0)

vocabulary:
  synonyms:
    '구매': ['주문','order']
    '매출': ['GMV','거래액']
  units:
    currency: KRW
policies:
  row_level:
    - name: region_filter
      predicate: user_region IN (@allowed_regions)
  column_level:
    - mask: email
      using: SHA256(email)
```

## 3) NL 정렬(NLU 어댑터)
- [ ] 사용자 질의에서 **의도(Intent)**, **슬롯(엔터티/지표/차원)** 추출 파이프라인
- [ ] 토큰 표준화(숫자/날짜/상대기간 “지난달”, “지난 7일” 등) 규칙
- [ ] 동의어·약어·오탈자 교정 사전 반영
- [ ] 금칙어·민감 키워드 필터링

## 4) 에이전트 아키텍처
- [ ] 컴포넌트: (1) 질의 해석기 → (2) 시멘틱 플래너 → (3) SQL 생성기 → (4) 검증기 → (5) 실행기 → (6) 요약기
- [ ] **플래너**: 시멘틱 모델을 기반으로 조인 경로/그룹바이/필터/윈도우 계획 생성
- [ ] **SQL 생성기**: BigQuery 방언 최적화(파티션 프루닝, APPROX_* 활용 옵션)
- [ ] **검증기**: DRY RUN, EXPLAIN, 정보 스키마 검증(존재/권한), 비용 추정
- [ ] **실행기**: 매개변수화 쿼리, 쿼리 태깅(job labels), 재시도/타임아웃
- [ ] **후처리**: 결과 표/차트·자연어 요약·추가 탐색 질문 제안

### 툴/가드레일 (의사코드)
```json
{
  "tools": [
    {"name": "bq_dry_run", "args": {"sql": "..."}},
    {"name": "bq_execute", "args": {"sql": "...", "maximum_bytes_billed": 10_000_000_000}},
    {"name": "bq_schema_lookup", "args": {"dataset": "proj.ds"}},
    {"name": "cache_lookup", "args": {"fingerprint": "..."}}
  ],
  "guardrails": {
    "deny_if": ["SELECT * FROM large_table WITHOUT WHERE"],
    "require": ["DRY_RUN_BEFORE_EXECUTION"],
    "enforce_param": ["maximum_bytes_billed"],
    "safe_functions": ["SAFE_DIVIDE"]
  }
}
```

## 5) 성능·비용 최적화(빅쿼리 특화)
- [ ] 파티션/클러스터링 키 재검토(자주 필터되는 날짜/ID)
- [ ] **Materialized View**로 비싼 집계 캐시, **BI Engine** 고려
- [ ] **Approximate 함수**(APPROX_TOP_COUNT, HLL++) 선택적 사용
- [ ] **Incremental 모델**(스냅샷/증분 테이블)로 최신화 비용 절감
- [ ] 쿼리 템플릿에서 **WHERE 파티션 범위 강제**
- [ ] **maximum_bytes_billed**, 우선 DRY RUN → 초과 시 사용자 승인을 요구

## 6) 보안·거버넌스
- [ ] 데이터셋/테이블/뷰 **정교한 IAM** 롤 설계(Authorized Views 활용)
- [ ] **Row-level security**, **Column-level masking** 반영(시멘틱 정책과 동기화)
- [ ] 감사 로깅(Cloud Logging) + Job label 에 사용자/의도/메트릭 기록
- [ ] PII 필드 자동 마스킹/익명화 규칙

## 7) 평가·테스트 자동화
- [ ] **골든세트** 생성: (자연어 → 기대 SQL → 기대 결과) 100~300 케이스
- [ ] **생성 평가**: 합성 질의 증강(동의어/어순 변형)으로 커버리지 확장
- [ ] 메트릭: 정확도(정답 SQL 매칭/결과 근사), 실패 유형(스키마/논리/권한/타임아웃)
- [ ] 회귀 테스트 CI: 모델/사전/스키마 변경시 자동 실행

## 8) UX 설계
- [ ] 질의 → 해석(시멘틱 플랜) **가시화**(사용자 신뢰)
- [ ] **수정 가능한 제안**: “이렇게 이해했어요 · 차원/기간 바꾸기”
- [ ] 결과와 함께 **근거 링크**(시멘틱 모델·정의서) 제공
- [ ] 한글 자연어 시간 파싱 지원(예: “저번 분기”, “어제”) 검증

## 9) 배포·릴리즈 계획
- [ ] 알파(내부 데이터 애널리스트) → 베타(한정 사용자) → GA 단계 목표 정의
- [ ] 에러/비용 SLO, 알림(오류율·비용 급증) 설정
- [ ] 롤백 전략(이전 모델/사전)

## 10) 운영·지속 개선
- [ ] 사용 로그 기반 **질문 사전 업데이트**(신규 동의어/패턴 학습)
- [ ] 인기 질의 **머티뷰/캐시** 승격 정책
- [ ] 데이터 품질 신호(누락/급변) 감지 → 에이전트가 경고 출력

---

# 산출물 체크리스트
- [ ] 시멘틱 모델 스키마(YAML)
- [ ] 용어사전(ko↔en, 동의어, 금칙어)
- [ ] 프롬프트 템플릿 & 시스템 정책
- [ ] 평가 골든세트 + 자동화 스크립트
- [ ] 운영 대시보드(정확도·비용·지연)

---

# 프롬프트 템플릿(요약 예시)
```text
역할: 당신은 BigQuery 최적화 규칙을 준수하는 데이터 분석가입니다.
입력: 사용자 질문(한국어), 시멘틱 레이어 정의
과업: (1) 의도/슬롯 추출 → (2) 시멘틱 플랜 구성 → (3) BigQuery SQL 생성
제약: DRY RUN 통과·partition filter 필수·maximum_bytes_billed 설정
출력:
- 해석 요약
- 생성 SQL
- 예상 스캔 바이트 & 근거(사용 테이블·조인 키·필터)
```

# BigQuery SQL 베스트 프랙티스(요약)
- 날짜 범위는 **_PARTITIONTIME / partition column**으로 필터
- SELECT * 지양, 필요한 컬럼만
- 큰 조인 전에 **서브쿼리로 필터/집계**
- **SAFE_DIVIDE**, **QUALIFY**로 윈도우 후 필터
- **WITH 절**로 로직을 단계화, 중복 계산 제거
- **EXPLAIN**, **DRY RUN**으로 비용·플랜 사전 점검

---

# 초기 스프린트 제안(2주)
**Week 1**
- [ ] 도메인/질문 수집, 스키마 프로파일링
- [ ] 시멘틱 엔터티·차원·지표 초안 & 용어사전 v0

**Week 2**
- [ ] 플래너/SQL 생성기 프로토타입 + DRY RUN 가드레일
- [ ] 골든세트 100문항으로 1차 정확도 측정

---

# 다음 액션(당장)
- [ ] 대상 도메인 1개 지정(예: 이커머스 주문/고객)
- [ ] 대표 질문 30~50개 공유(원문 그대로)
- [ ] BigQuery 데이터셋 목록/행수/파티션 구조 추출 쿼리 실행
- [ ] 결과를 바탕으로 시멘틱 모델 YAML v0 초안 작성



---

# 도메인 확정: 고객 (GA4 · Mall 유입 여정)
**소스**: BigQuery GA4 Export 테이블 `ns-extr-data.analytics_310486481.events_fresh_20251106`

## 전제(Assumptions)
- 표준 GA4 Export 스키마: `event_timestamp`, `event_date`, `event_name`, `event_params`(ARRAY<STRUCT<key,string_value,int_value,double_value>>), `user_pseudo_id`, `user_id`, `geo`, `device`, `traffic_source`, `items`(ARRAY<STRUCT<...>>)
- 세션 식별: `ga_session_id`는 `event_params` 중 `ga_session_id`(int_value)로 추출
- 참여시간: `engagement_time_msec`(int_value)
- 페이지/스크린: `page_location`, `page_referrer` 등은 `event_params`에서 추출
- 구매: `event_name='purchase'`, `transaction_id`(event_params), 통화/금액은 `value` & `currency` or `items.price*items.quantity`
- “Mall 유입” 판정은 **유입 채널/소스** 기준(예: `traffic_source.source` 또는 첫 방문 `user_properties.first_touch_source`). 아래 동의어 사전에 후보값(예: `mall`, `nsmall_mall`, `ns-mall`)을 매핑

> 실제 값은 운영 데이터 확인 후 사전 업데이트 필요.

---

## 시멘틱 레이어 v0 (GA4 고객·세션·이벤트)
```yaml
version: 0.1
source:
  table: `ns-extr-data.analytics_310486481.events_fresh_20251106`
  time_column: event_timestamp
  partition_hint: event_date

entities:
  - name: user
    grain: user_key
    materialization: view
    sql: |
      WITH base AS (
        SELECT
          COALESCE(CAST(user_id AS STRING), user_pseudo_id) AS user_key,
          user_id,
          user_pseudo_id,
          ANY_VALUE(traffic_source.source) AS first_source,
          ANY_VALUE(traffic_source.medium) AS first_medium,
          ANY_VALUE(traffic_source.name) AS first_campaign
        FROM ${source}
        GROUP BY 1,2,3
      )
      SELECT * FROM base
    dimensions:
      - name: user_key
      - name: first_source
        synonyms: [유입소스, 소스]
      - name: first_medium
        synonyms: [매체, 미디엄]
      - name: first_campaign
        synonyms: [캠페인]

  - name: session
    grain: session_key
    materialization: view
    sql: |
      WITH exploded AS (
        SELECT
          COALESCE(CAST(user_id AS STRING), user_pseudo_id) AS user_key,
          (SELECT CAST(p.int_value AS STRING) FROM UNNEST(event_params) p WHERE p.key='ga_session_id') AS ga_session_id,
          TIMESTAMP_MICROS(event_timestamp) AS event_ts,
          (SELECT p.int_value FROM UNNEST(event_params) p WHERE p.key='engagement_time_msec') AS engagement_ms,
          traffic_source.source AS source,
          traffic_source.medium AS medium,
          traffic_source.name AS campaign
        FROM ${source}
      )
      , agg AS (
        SELECT
          CONCAT(user_key, ':', ga_session_id) AS session_key,
          user_key,
          MIN(event_ts) AS session_start,
          MAX(event_ts) AS session_end,
          SUM(IFNULL(engagement_ms,0)) AS engagement_ms,
          ANY_VALUE(source) AS source,
          ANY_VALUE(medium) AS medium,
          ANY_VALUE(campaign) AS campaign,
          COUNT(*) AS events
        FROM exploded
        WHERE ga_session_id IS NOT NULL
        GROUP BY 1,2
      )
      SELECT * FROM agg
    relationships:
      - to: user
        type: many_to_one
        on: session.user_key = user.user_key
    dimensions:
      - name: session_key
      - name: session_start
        type: timestamp
      - name: session_end
        type: timestamp
      - name: source
      - name: medium
      - name: campaign
    measures:
      - name: sessions
        expr: COUNT(DISTINCT session_key)
      - name: engaged_sessions
        expr: COUNTIF(engagement_ms >= 10000)

  - name: event
    grain: event_row
    materialization: view
    sql: |
      SELECT
        TIMESTAMP_MICROS(event_timestamp) AS event_ts,
        event_date,
        event_name,
        COALESCE(CAST(user_id AS STRING), user_pseudo_id) AS user_key,
        (SELECT CAST(p.int_value AS STRING) FROM UNNEST(event_params) p WHERE p.key='ga_session_id') AS ga_session_id,
        CONCAT(COALESCE(CAST(user_id AS STRING), user_pseudo_id), ':', (SELECT CAST(p.int_value AS STRING) FROM UNNEST(event_params) p WHERE p.key='ga_session_id')) AS session_key,
        (SELECT p.int_value FROM UNNEST(event_params) p WHERE p.key='engagement_time_msec') AS engagement_ms,
        (SELECT p.string_value FROM UNNEST(event_params) p WHERE p.key='page_location') AS page_location,
        (SELECT p.string_value FROM UNNEST(event_params) p WHERE p.key='page_referrer') AS page_referrer,
        (SELECT p.string_value FROM UNNEST(event_params) p WHERE p.key='transaction_id') AS transaction_id,
        (SELECT p.double_value FROM UNNEST(event_params) p WHERE p.key='value') AS value,
        traffic_source.source AS source,
        traffic_source.medium AS medium,
        traffic_source.name AS campaign,
        geo.country AS country,
        geo.region AS region,
        device.category AS device_category
      FROM ${source}
    relationships:
      - to: session
        type: many_to_one
        on: event.session_key = session.session_key
      - to: user
        type: many_to_one
        on: event.user_key = user.user_key
    dimensions:
      - name: event_ts
        type: timestamp
      - name: event_name
      - name: page_location
      - name: page_referrer
      - name: source
      - name: medium
      - name: campaign
      - name: country
      - name: region
      - name: device_category
    measures:
      - name: events
        expr: COUNT(*)
      - name: pageviews
        expr: COUNTIF(event_name IN ('page_view','screen_view'))
      - name: add_to_cart
        expr: COUNTIF(event_name = 'add_to_cart')
      - name: purchases
        expr: COUNTIF(event_name = 'purchase')
      - name: revenue_value
        expr: SUM(IFNULL(value,0))

metrics:
  - name: sessions
    expr: session.sessions
  - name: active_users
    expr: COUNT(DISTINCT user.user_key)
  - name: conversion_rate
    expr: SAFE_DIVIDE(COUNTIF(event.event_name='purchase'), COUNT(DISTINCT session.session_key))
  - name: add_to_cart_rate
    expr: SAFE_DIVIDE(COUNTIF(event.event_name='add_to_cart'), COUNTIF(event.event_name='view_item'))
  - name: revenue
    expr: SUM(event.value)

vocabulary:
  synonyms:
    'Mall 유입': ['mall','nsmall_mall','ns-mall','mall.nsmall','몰유입']
    '구매': ['결제','주문완료','purchase']
    '장바구니': ['add_to_cart','ATC']
    '상품상세': ['view_item','상품뷰']
    '방문': ['세션','session']
  units:
    currency: KRW
policies:
  row_level:
    - name: mall_source_only
      predicate: LOWER(event.source) IN (@mall_sources)
  column_level:
    - mask: user_id
      using: TO_HEX(SHA256(CAST(user_id AS STRING)))
```

### 파라미터 추출 헬퍼 SQL (재사용 스니펫)
```sql
-- 파라미터 추출 UDF 예시
CREATE TEMP FUNCTION get_param_string(params ARRAY<STRUCT<key STRING, value STRUCT<string_value STRING, int_value INT64, double_value FLOAT64>>> , k STRING)
RETURNS STRING AS (
  (SELECT p.value.string_value FROM UNNEST(params) p WHERE p.key = k LIMIT 1)
);

CREATE TEMP FUNCTION get_param_int(params ARRAY<STRUCT<key STRING, value STRUCT<string_value STRING, int_value INT64, double_value FLOAT64>>> , k STRING)
RETURNS INT64 AS (
  (SELECT p.value.int_value FROM UNNEST(params) p WHERE p.key = k LIMIT 1)
);

CREATE TEMP FUNCTION get_param_float(params ARRAY<STRUCT<key STRING, value STRUCT<string_value STRING, int_value INT64, double_value FLOAT64>>> , k STRING)
RETURNS FLOAT64 AS (
  (SELECT p.value.double_value FROM UNNEST(params) p WHERE p.key = k LIMIT 1)
);
```

---

## 자연어 질문 초안 (시나리오: “Mall 유입 고객의 여정/행동”)
1. 지난 7일 기준 **Mall 유입 고객의 방문자 수**와 **세션 수**는?
2. Mall 유입의 **신규 vs. 재방문 사용자 비율**은?
3. Mall 유입 고객의 **장치(모바일/데스크탑)** 분포와 **이탈률**은?
4. Mall 유입 고객의 **평균 세션 길이**와 **평균 참여시간(engagement_time_msec)**은?
5. Mall 유입 고객의 **랜딩 페이지 TOP 10**과 이후 **2번째 페이지**는 무엇인가?
6. Mall 유입 고객의 **주요 경로(페이지 경로 3스텝)** 빈도는?
7. Mall 유입 고객의 **상품상세(view_item) → 장바구니 → 구매** 전환 깔때기 전환율은?
8. Mall 유입 고객의 **장바구니 이탈률**(ATC 이후 구매 미완료 비율)은?
9. Mall 유입 고객의 **구매전환율(CVR)**과 **AOV(평균 주문금액)**은?
10. Mall 유입 고객의 **일자별 매출 추이(최근 30일)**는?
11. Mall 유입 고객의 **시간대별(시/요일) 유입 패턴**은?
12. Mall 유입 고객의 **지역/도시별 전환율** 차이는?
13. Mall 유입 고객의 **신규 사용자 첫 방문 후 구매까지 평균 소요시간**은?
14. Mall 유입 고객의 **재방문까지 걸리는 평균 기간(리텐션 래그)**은?
15. Mall 유입 고객의 **N일 리텐션(1/7/30일)**은?
16. Mall 유입 고객의 **상품 카테고리별 구매 비중**은?
17. Mall 유입 고객의 **검색 이벤트(view_search_results) 이후 전환율**은?
18. Mall 유입 고객의 **프로모션 클릭(select_promotion) 대비 구매율**은?
19. Mall 유입 고객의 **캠페인별(source/medium/campaign) 성과**는?
20. Mall 유입 고객의 **이벤트당 평균 참여시간** Top 10 이벤트는?
21. Mall 유입 고객의 **첫 페이지 이탈(Bounce) 비율**은?
22. Mall 유입 고객 중 **로그인 사용자 비중**과 그들의 CVR은?
23. Mall 유입 사용자의 **세션당 페이지뷰 수** 분포는?
24. Mall 유입 고객의 **쿠폰 적용 여부별** 전환율/매출 차이는?
25. Mall 유입 고객의 **거치 장치별(브라우저/OS)** 오류 이벤트(예: exception) 발생률은?
26. Mall 유입 고객의 **결제단계 드롭오프 단계**는 어디에서 가장 큰가?
27. Mall 유입 고객의 **재구매율(30/60/90일)**은?
28. Mall 유입 고객의 **신규 고객 코호트별** 매출 누적 곡선은?
29. Mall 유입 고객의 **스크롤 깊이**(scroll) 상위/하위 그룹 전환율 차이는?
30. Mall 유입 고객의 **검색어 상위 20개**와 전환율은?
31. Mall 유입 고객의 **상품상세 체류시간**이 전환에 미치는 영향은?
32. Mall 유입 고객의 **찜/위시리스트(add_to_wishlist)** 사용률과 구매 연계는?
33. Mall 유입 고객의 **채널 간 이동(크로스세션)** 패턴은?
34. Mall 유입 고객의 **첫 유입 채널 vs. 최종 클릭 채널** 전환 기여 비교는?
35. Mall 유입 고객의 **장바구니까지 평균 클릭수**와 **구매까지 평균 이벤트수**는?
36. Mall 유입 고객의 **추천 영역 클릭**(select_content) 이후 전환율은?
37. Mall 유입 고객의 **리마케팅 노출(view_promotion)** 후 재방문/구매율은?
38. Mall 유입 고객의 **고객 세그먼트(고가/중가/저가)**별 전환/매출은?
39. Mall 유입 고객의 **상품 리뷰 보기 이벤트**(view_item + view_item_list + user_engagement) 후 전환은?
40. Mall 유입 고객의 **장바구니 금액대 구간별** 구매전환율은?

> 위 질문은 바로 **골든세트** 후보로 사용 가능하며, 실제 데이터의 이벤트/파라미터 키 이름을 확인해 사전·시멘틱 모델을 업데이트하면 자동 커버리지가 늘어납니다.

---

## 샘플 쿼리 템플릿(발췌)
**Mall 유입 판정 + 기본 세션 팩트**
```sql
WITH base AS (
  SELECT
    TIMESTAMP_MICROS(event_timestamp) AS event_ts,
    event_date,
    COALESCE(CAST(user_id AS STRING), user_pseudo_id) AS user_key,
    (SELECT CAST(p.int_value AS STRING) FROM UNNEST(event_params) p WHERE p.key='ga_session_id') AS ga_session_id,
    (SELECT p.int_value FROM UNNEST(event_params) p WHERE p.key='engagement_time_msec') AS engagement_ms,
    traffic_source.source AS source,
    traffic_source.medium AS medium,
    traffic_source.name AS campaign
  FROM `ns-extr-data.analytics_310486481.events_fresh_20251106`
  WHERE LOWER(traffic_source.source) IN ('mall','nsmall_mall','ns-mall') -- TODO: 운영값 확인
)
, sessions AS (
  SELECT
    CONCAT(user_key, ':', ga_session_id) AS session_key,
    MIN(event_ts) AS session_start,
    MAX(event_ts) AS session_end,
    SUM(IFNULL(engagement_ms,0)) AS engagement_ms
  FROM base
  WHERE ga_session_id IS NOT NULL
  GROUP BY 1
)
SELECT COUNT(*) AS sessions, APPROX_QUANTILES(engagement_ms, 101)[OFFSET(50)] AS p50_eng_ms
FROM sessions;
```

**뷰아이템→ATC→구매 퍼널**
```sql
WITH e AS (
  SELECT
    CONCAT(COALESCE(CAST(user_id AS STRING), user_pseudo_id), ':', CAST(get_param_int(event_params,'ga_session_id') AS STRING)) AS session_key,
    event_name
  FROM `ns-extr-data.analytics_310486481.events_fresh_20251106`
  WHERE LOWER(traffic_source.source) IN ('mall','nsmall_mall','ns-mall')
)
SELECT
  SAFE_DIVIDE(COUNTIF(event_name='add_to_cart'), COUNTIF(event_name='view_item')) AS atc_rate,
  SAFE_DIVIDE(COUNTIF(event_name='purchase'), COUNTIF(event_name='add_to_cart')) AS purchase_after_atc
FROM e;
```



---

# 다음 단계(실행 플랜)

## Week 1 — 스키마·용어 확정 & 시멘틱 뼈대 고정
- [ ] **Mall 소스값 수집**: 실제 유입 소스 후보 추출 후 사전에 반영
  ```sql
  SELECT LOWER(traffic_source.source) AS source, COUNT(*) AS events
  FROM `ns-extr-data.analytics_310486481.events_fresh_20251106`
  WHERE event_date >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
  GROUP BY 1 ORDER BY events DESC;
  ```
- [ ] **핵심 파라미터 키 검증**: `ga_session_id`, `engagement_time_msec`, `page_location`, `transaction_id`, `value`, `currency`
  ```sql
  SELECT key, COUNT(*) cnt
  FROM `ns-extr-data.analytics_310486481.events_fresh_20251106`, UNNEST(event_params) ep
  WHERE event_date >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
  GROUP BY key ORDER BY cnt DESC;
  ```
- [ ] **지표 정의서 확정**: CVR, AOV, Revenue, Sessions, Active Users, Engaged Sessions, ATC Rate 등 수식/필터(취소/반품 제외 여부) 명시
- [ ] **시멘틱 뷰 v0 생성**: user/session/event 뷰를 개발 데이터셋에 생성 (예: `ns_exploration.semantic_*`)
- [ ] **동의어/약어 사전 v0** 반영(아래 용어사전 참조)

## Week 2 — 평가·가드레일·성능
- [ ] **골든세트 v0(15문항)** 작성: 질문→기대 SQL→기대 결과 스냅샷 저장
- [ ] **DRY RUN 가드레일**: 실행 전 DRY RUN·`maximum_bytes_billed` 필수 체크, 파티션 필터 미존재시 차단
- [ ] **퍼포먼스 튜닝**: 파티션 강제, 필요 시 materialized view(일자·소스별 퍼널 집계)
- [ ] **UX 스펙**: 해석 로그(시멘틱 플랜)와 생성 SQL 노출, 수정 가능한 토글(기간/채널/디바이스)
- [ ] **보안**: user_id 해시 마스킹, 행 수준 정책(Mall 유입만) 샘플 적용

## 산출물
- 시멘틱 뷰 DDL, 지표 정의서, 동의어 사전(JSON/YAML), 골든세트 노트북/스크립트, 실행 가드레일 정책

---

# 용어사전 v0 (고객·세션·이벤트 / GA4)

## 1) 엔터티·차원 동의어
- **사용자(user)**: [고객, 유저, visitor]
  - `user_key`: [고객ID, 유저키] → COALESCE(CAST(user_id AS STRING), user_pseudo_id)
  - `first_source`: [유입소스, 소스]
  - `first_medium`: [매체, 미디엄]
  - `first_campaign`: [캠페인]
- **세션(session)**: [방문, 방문세션]
  - `session_key`: [세션키]
  - `session_start`: [방문시작]
  - `session_end`: [방문종료]
- **이벤트(event)**: [행동, 액션]
  - `event_ts`: [이벤트시각]
  - `event_name`: [이벤트명]
  - `page_location`: [현재페이지, URL]
  - `page_referrer`: [유입경로, 레퍼러]
  - `device_category`: [디바이스, 장치]

## 2) 지표(Measure/Metric) 정의·동의어
- **sessions**: 세션 수, 방문수 → COUNT(DISTINCT session_key)
- **active_users**: 활성 사용자 수 → COUNT(DISTINCT user_key)
- **engaged_sessions**: 참여세션 수(engagement_time_msec ≥ 10s)
- **pageviews**: 페이지뷰 수 → COUNTIF(event_name IN ('page_view','screen_view'))
- **ATC(add_to_cart)**: 장바구니 추가 수 → COUNTIF(event_name='add_to_cart')
- **purchases**: 구매 수 → COUNTIF(event_name='purchase')
- **revenue**: 매출(원화) → SUM(value) [취소/반품 제외 정책 필요]
- **CVR(conversion_rate)**: 구매전환율 → purchases / sessions
- **AOV**: 객단가 → revenue / purchases
- **ATC Rate**: 장바구니 전환율 → ATC / view_item
- **Purchase after ATC**: ATC 대비 구매율 → purchases / ATC

## 3) 이벤트명·행동 동의어 맵
- `page_view`: [페이지뷰, PV]
- `view_item`: [상품상세보기, PDP]
- `add_to_cart`: [장바구니담기, ATC]
- `begin_checkout`: [결제진입, 체크아웃시작]
- `purchase`: [구매, 주문완료, 결제완료]
- `view_item_list`: [리스트보기, 카테고리뷰]
- `select_promotion` / `view_promotion`: [프로모션클릭/노출]
- `view_search_results`: [검색결과보기]
- `scroll`: [스크롤]
- `login`: [로그인]
- `exception`: [오류, 에러]

## 4) Mall 유입 판정 사전 (초안)
> Week 1에서 추출 쿼리 결과로 업데이트
```yaml
mall_sources:
  - mall
  - nsmall_mall
  - ns-mall
  - mall.nsmall
aliases:
  'Mall 유입': ['mall','nsmall_mall','ns-mall','mall.nsmall','몰유입']
```

## 5) 시간 표현(자연어 → 기간) 규칙
- **오늘**: CURRENT_DATE()
- **어제**: CURRENT_DATE() - 1 day
- **지난 7일**: [CURRENT_DATE()-7, CURRENT_DATE()-1]
- **지난 30일**: [CURRENT_DATE()-30, CURRENT_DATE()-1]
- **지난달**: DATE_TRUNC(CURRENT_DATE()-1, MONTH) - 1 MONTH (월 단위)
- **저번 분기**: QUARTER 기준 한 분기 전

## 6) 단위·형식
- 통화: KRW (원), 소수점 0~2자리 반올림 정책 명시
- 시간: Asia/Seoul, 타임스탬프는 TIMESTAMP(MICROS)
- 퍼센트: 0~1 비율 → 보고 시 ×100 표시

## 7) 정책(금칙/가드레일) 용어
- **금칙어**: 개인정보 직접 추출 요청(이메일 원문, 전화번호 등)
- **강제조건**: 파티션 필터 필수, DRY RUN 필수, maximum_bytes_billed 지정

---

# 운영 체크리스트 추가
- [ ] Mall 소스 사전 최신화 자동 잡(주 1회) — 상위 100 소스 스캔→신규 후보 알림
- [ ] 골든세트 회귀 테스트 CI — 시멘틱/사전 변경 시 자동 실행
- [ ] 비용·지연 SLO 대시보드 — 쿼리 라벨(job labels: user, intent, metric) 집계

