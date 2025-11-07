from typing import Any, Dict


SEMANTIC_DEFAULT_TABLE = "ns-extr-data.analytics_310486481.events_fresh_20251106"


def generate(plan: Dict[str, Any], limit: int | None = 100) -> str:
    metric = plan.get("metric", "orders")
    grain = plan.get("grain", "day")

    table = SEMANTIC_DEFAULT_TABLE
    is_events = "events" in table

    # Very small, opinionated mapping for scaffold (events vs orders flavor)
    if is_events:
        if metric == "gmv":
            expr = "SUM(CASE WHEN event_name='purchase' THEN event_value ELSE 0 END) AS gmv"
        elif metric == "orders":
            expr = "SUM(CASE WHEN event_name='purchase' THEN 1 ELSE 0 END) AS orders"
        elif metric == "sessions":
            expr = "COUNT(DISTINCT session_id) AS sessions"
        else:
            expr = "COUNT(1) AS cnt"
        # GA4 exports event_timestamp is INT64 micros; convert to DATE
        if grain == "day":
            group = "DATE(TIMESTAMP_MICROS(event_timestamp)) AS day"
            group_by = "GROUP BY day"
            order = "ORDER BY day"
        else:
            group = "1"
            group_by = ""
            order = ""
    else:
        if metric == "gmv":
            expr = "SUM(net_amount) AS gmv"
        elif metric == "orders":
            expr = "COUNT(DISTINCT order_id) AS orders"
        elif metric == "sessions":
            expr = "COUNT(DISTINCT session_id) AS sessions"
        else:
            expr = "COUNT(1) AS cnt"
        if grain == "day":
            group = "DATE(order_date) AS day"
            group_by = "GROUP BY day"
            order = "ORDER BY day"
        else:
            group = "1"
            group_by = ""
            order = ""

    sql = f"""
SELECT
  {group},
  {expr}
FROM `{table}`
WHERE 1=1
{group_by}
{order}
""".strip()

    if limit:
        sql += f"\nLIMIT {int(limit)}"
    return sql
