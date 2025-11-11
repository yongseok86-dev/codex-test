from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.config import settings
from app.deps import get_logger

try:
    from google.cloud import bigquery  # type: ignore
except Exception:  # pragma: no cover
    bigquery = None  # type: ignore

logger = get_logger("service.time_series")


def default_date_range(days: int = 30) -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=max(days - 1, 1))
    return start, end


# existing imports etc remain

def fetch_product_series(
    product_id: str | None,
    start_date: date | None,
    end_date: date | None,
    grain: str,
) -> dict[str, Any]:
    start, end = _normalize_dates(start_date, end_date)
    if bigquery is None:
        return _fake_series(product_id, start, end, grain)

    sql = _build_query(product_id, grain)
    client = bigquery.Client(project=settings.gcp_project)  # type: ignore
    query_params = [
        bigquery.ScalarQueryParameter("start_date", "DATE", start.isoformat()),
        bigquery.ScalarQueryParameter("end_date", "DATE", end.isoformat()),
    ]
    if product_id:
        query_params.append(bigquery.ScalarQueryParameter("product_id", "STRING", product_id))

    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=query_params))
    rows = [dict(row) for row in job.result()]
    return {
        "series": rows,
        "filters": {
            "product_id": product_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "grain": grain,
        },
    }


def _normalize_dates(start: date | None, end: date | None) -> tuple[date, date]:
    if start and end:
        return (start, end) if start <= end else (end, start)
    elif start:
        return start, start
    elif end:
        return end, end
    return default_date_range()


def _build_query(product_id: str | None, grain: str) -> str:
    field = {
        "day": "FORMAT_DATE('%Y-%m-%d', DATE(order_date))",
        "week": "FORMAT_DATE('%G-W%V', DATE(order_date))",
        "month": "FORMAT_DATE('%Y-%m', DATE(order_date))",
    }.get(grain, "FORMAT_DATE('%Y-%m-%d', DATE(order_date))")

    where = "status = 'completed'"
    if product_id:
        where += " AND product_id = @product_id"

    return """
    WITH order_items AS (
        SELECT FORMAT_DATETIME('%H:%M', DATETIME(TIMESTAMP_MICROS(A.event_timestamp), 'Asia/Seoul')) AS event_dttm
, items.item_name, count(*) AS cnt
  FROM `ns-extr-data.analytics_310486481.events_intraday_*` A,
  UNNEST(items) items
 WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE("%Y%m%d", '2025-11-10') AND FORMAT_DATE("%Y%m%d", '2025-11-10')
   AND event_name = 'purchase'
 GROUP BY ALL
    )
    SELECT bucket, total_quantity
    FROM order_items
    ORDER BY bucket
    """


def _fake_series(product_id: str | None, start: date, end: date, grain: str) -> dict[str, Any]:
    import random
    current = start
    series = []
    while current <= end:
        bucket = current.strftime("%Y-%m-%d")
        qty = random.randint(20, 200)
        if product_id:
            qty = int(qty * 0.6)
        series.append({"bucket": bucket, "total_quantity": qty})
        current += timedelta(days=1)

    return {
        "series": series,
        "filters": {
            "product_id": product_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "grain": grain,
        },
        "stub": True,
    }

__all__ = ["fetch_product_series", "default_date_range"]


def fetch_bubble_series() -> dict[str, Any]:
    today = date.today()
    if bigquery is None:
        return _fake_bubbles(today)

    sql = """
    WITH ordered AS (
        SELECT FORMAT_DATETIME('%H:%M', DATETIME(TIMESTAMP_MICROS(A.event_timestamp), 'Asia/Seoul')) AS time_bucket
, items.item_name AS product_name
, count(*) AS total_quantity
  FROM `ns-extr-data.analytics_310486481.events_intraday_*` A,
  UNNEST(items) items
 WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE("%Y%m%d", '2025-11-10') AND FORMAT_DATE("%Y%m%d", '2025-11-10')
   AND event_name = 'purchase'
 GROUP BY ALL
    )
    SELECT time_bucket, product_name, total_quantity
    FROM ordered
    ORDER BY time_bucket, total_quantity DESC
    LIMIT 200
    """

    client = bigquery.Client(project=settings.gcp_project)  # type: ignore
    job = client.query(sql)
    rows = [dict(row) for row in job.result()]
    return {
        "series": rows,
        "filters": {
            "date": today.isoformat(),
        },
    }


def _fake_bubbles(day: date) -> dict[str, Any]:
    import random
    products = ["티셔츠", "후드", "신발", "모자", "가방"]
    series = []
    for hour in range(9, 24):
        minute = random.choice([0, 15, 30, 45])
        bucket = f"{hour:02d}:{minute:02d}"
        for product in products:
            qty = random.randint(5, 80)
            if random.random() < 0.4:
                continue
            series.append({"time_bucket": bucket, "product_name": product, "total_quantity": qty})
    return {"series": series, "filters": {"date": day.isoformat()}, "stub": True}
