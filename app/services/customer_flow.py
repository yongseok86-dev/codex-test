from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List

from app.config import settings
from app.deps import get_logger

try:
    from google.cloud import bigquery  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    bigquery = None  # type: ignore

logger = get_logger("service.customer_flow")

DEFAULT_LOOKBACK_DAYS = 14


class SegmentNotFound(ValueError):
    """Raised when a requested segment id does not exist."""


@dataclass(slots=True)
class SegmentOption:
    id: str
    label: str
    description: str
    default: bool = False


SegmentConfig = Dict[str, Any]

SEGMENTS: Dict[str, SegmentConfig] = {
    "all": {
        "label": "전체 고객",
        "description": "필터 없이 전체 고객 여정을 집계합니다.",
        "where": "TRUE",
        "default": True,
    },
    "new_customers": {
        "label": "신규 고객",
        "description": "첫 방문/구매가 진행 중인 신규 고객 흐름.",
        "where": "COALESCE(u.is_new_user, TRUE)",
    },
    "repeat_buyers": {
        "label": "반복 구매 고객",
        "description": "완료 주문 2회 이상 고객의 행동 네트워크.",
        "where": "COALESCE(o.order_count, 0) >= 2",
    },
    "vip": {
        "label": "고가 구매 고객",
        "description": "누적 결제 금액 500,000 이상 VIP 고객.",
        "where": "COALESCE(o.total_gmv, 0) >= 500000",
    },
    "churn_risk": {
        "label": "이탈 위험 고객",
        "description": "마지막 구매 이후 60일 이상 경과한 고객.",
        "where": "o.last_order_date IS NOT NULL AND DATE_DIFF(@start_date, o.last_order_date, DAY) > 60",
    },
    "browse_only": {
        "label": "구매 전환 이전",
        "description": "아직 결제 이력이 없는 탐색 고객.",
        "where": "COALESCE(o.order_count, 0) = 0",
    },
}

FAKE_SEGMENT_EDGES: Dict[str, List[tuple[str, str, int]]] = {
    "all": [
        ("landing", "category", 1800),
        ("category", "product_detail", 1520),
        ("product_detail", "add_to_cart", 870),
        ("add_to_cart", "checkout", 640),
        ("checkout", "purchase", 520),
        ("category", "search", 430),
        ("search", "product_detail", 410),
    ],
    "new_customers": [
        ("landing", "signup", 620),
        ("signup", "category", 580),
        ("category", "product_detail", 540),
        ("product_detail", "add_to_cart", 360),
        ("add_to_cart", "checkout", 220),
    ],
    "repeat_buyers": [
        ("push_notification", "product_detail", 320),
        ("product_detail", "add_to_cart", 310),
        ("add_to_cart", "purchase", 260),
        ("purchase", "referral", 120),
    ],
    "vip": [
        ("email", "product_detail", 210),
        ("product_detail", "wishlist", 190),
        ("wishlist", "add_to_cart", 170),
        ("add_to_cart", "purchase", 160),
        ("purchase", "premium_support", 60),
    ],
    "churn_risk": [
        ("landing", "category", 280),
        ("category", "product_detail", 240),
        ("product_detail", "promo_banner", 120),
        ("promo_banner", "exit", 110),
    ],
    "browse_only": [
        ("landing", "search", 520),
        ("search", "product_detail", 470),
        ("product_detail", "size_guide", 200),
        ("size_guide", "exit", 180),
    ],
}

SQL_TEMPLATE = """
with cust_info AS ( SELECT DISTINCT user_pseudo_id FROM `ns-extr-data.analytics_310486481.events_intraday_*` 
WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE("%Y%m%d", '2025-11-10') AND FORMAT_DATE("%Y%m%d", '2025-11-10') 
    AND traffic_source.source = 'PUSH' 
    AND (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'ep_page_fullurl') LIKE '%/store/atypical/home%' 
) 

SELECT source, IFNULL(target, '로그아웃') AS target, COUNT(user_id) AS weight
  FROM ( SELECT page_title AS source
              , LEAD(page_title) OVER(PARTITION BY user_id ORDER BY event_timestamp) AS target
              , user_id
              , ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY event_timestamp) AS seq
           FROM ( SELECT DISTINCT user_pseudo_id||'-'||ga_session_id AS user_id, page_title, event_timestamp              
                    FROM ( SELECT DISTINCT A.user_pseudo_id, A.event_timestamp, A.batch_ordering_id, (SELECT value.int_value from UNNEST(A.event_params) WHERE key = 'ga_session_id') AS ga_session_id
                                , CAST(FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S', TIMESTAMP_MICROS(A.event_timestamp), 'Asia/Seoul') AS DATETIME) AS event_dttm
                                , event_name
                                , REPLACE((SELECT value.string_value from UNNEST(A.event_params) WHERE key = 'page_title'), 'App>', '') AS page_title
                             FROM `ns-extr-data.analytics_310486481.events_intraday_*` A 
                           INNER JOIN cust_info B
                              ON A.user_pseudo_id = B.user_pseudo_id
                           WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE("%Y%m%d", '2025-11-10') AND FORMAT_DATE("%Y%m%d", '2025-11-10') 
                             AND A.event_name IN ('page_view','auto_login','session_start') ) ) )
GROUP BY ALL
HAVING weight > 10
"""


def segment_options() -> List[dict[str, Any]]:
    """Return UI-ready segment metadata."""
    return [
        {
            "id": seg_id,
            "label": conf["label"],
            "description": conf["description"],
            "default": bool(conf.get("default")),
        }
        for seg_id, conf in SEGMENTS.items()
    ]


def fetch_customer_flow(
    segment_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 25,
    min_edge_count: int = 3,
) -> dict[str, Any]:
    segment = SEGMENTS.get(segment_id)
    if not segment:
        raise SegmentNotFound(f"segment '{segment_id}' is not defined")

    limit = max(5, min(limit, 200))
    min_edge_count = max(1, min(min_edge_count, 100))
    start, end = _resolve_dates(start_date, end_date)

    if bigquery is None:
        rows = _fake_rows(segment_id, limit, min_edge_count)
    else:
        rows = _run_query(segment["where"], start, end, limit, min_edge_count)

    nodes, links, total_weight = _build_graph(rows)
    response = {
        "segment": {
            "id": segment_id,
            "label": segment["label"],
            "description": segment["description"],
        },
        "filters": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "limit": limit,
            "min_edge_count": min_edge_count,
        },
        "nodes": nodes,
        "links": links,
        "summary": {
            "total_transitions": total_weight,
            "edge_count": len(links),
            "node_count": len(nodes),
        },
        "raw_edges": rows,
        "data_source": {
            "events_table": settings.bq_events_table,
            "orders_table": settings.bq_orders_table,
            "users_table": settings.bq_users_table,
        },
    }
    return response


def _resolve_dates(
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    today = date.today()
    end = end_date or today
    start = start_date or (end - timedelta(days=DEFAULT_LOOKBACK_DAYS - 1))
    if start > end:
        start, end = end, start
    return start, end


def _run_query(
    segment_where: str,
    start: date,
    end: date,
    limit: int,
    min_edge_count: int,
) -> List[dict[str, Any]]:
    if bigquery is None:  # pragma: no cover - defensive
        return []

    sql = SQL_TEMPLATE.format(
        events_table=settings.bq_events_table,
        users_table=settings.bq_users_table,
        orders_table=settings.bq_orders_table,
        segment_condition=segment_where,
    )
    client = bigquery.Client(project=settings.gcp_project)  # type: ignore
    job_config = bigquery.QueryJobConfig()  # type: ignore
    job_config.maximum_bytes_billed = settings.maximum_bytes_billed
    job_config.labels = {"app": "nl2sql", "feature": "customer_flow"}
    job_config.query_parameters = [
        bigquery.ScalarQueryParameter("start_date", "DATE", start.isoformat()),
        bigquery.ScalarQueryParameter("end_date", "DATE", end.isoformat()),
        bigquery.ScalarQueryParameter("min_edge_count", "INT64", min_edge_count),
        bigquery.ScalarQueryParameter("limit_rows", "INT64", limit),
    ]

    logger.info(
        "customer_flow_query",
        extra={
            "segment": segment_where,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": limit,
            "min_edge": min_edge_count,
        },
    )

    job = client.query(sql, job_config=job_config)
    return [dict(row) for row in job.result()]


def _build_graph(rows: List[dict[str, Any]]) -> tuple[List[dict[str, Any]], List[dict[str, Any]], int]:
    if not rows:
        return [], [], 0

    node_weights: Dict[str, int] = {}
    links: List[dict[str, Any]] = []
    total_weight = 0

    for row in rows:
        source = row.get("source")
        target = row.get("target")
        weight = int(row.get("weight") or 0)
        if not source or not target or weight <= 0:
            continue
        total_weight += weight
        node_weights[source] = node_weights.get(source, 0) + weight
        node_weights[target] = node_weights.get(target, 0) + weight
        links.append({"source": source, "target": target, "value": weight})

    nodes = [
        {"id": node, "label": _labelize(node), "value": weight}
        for node, weight in sorted(node_weights.items(), key=lambda item: item[1], reverse=True)
    ]
    return nodes, links, total_weight


def _fake_rows(segment_id: str, limit: int, min_edge: int) -> List[dict[str, Any]]:
    template = FAKE_SEGMENT_EDGES.get(segment_id) or FAKE_SEGMENT_EDGES["all"]
    rows: List[dict[str, Any]] = []
    for source, target, weight in template:
        if weight < min_edge:
            continue
        rows.append({"source": source, "target": target, "weight": weight})
        if len(rows) >= limit:
            break
    return rows


def _labelize(value: str) -> str:
    if not value:
        return "Unknown"
    clean = value.replace("_", " ").strip()
    return clean[:1].upper() + clean[1:]


__all__ = [
    "fetch_customer_flow",
    "segment_options",
    "SegmentOption",
    "SegmentNotFound",
]
