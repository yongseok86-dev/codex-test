from typing import Any, Dict


SEMANTIC_DEFAULT_TABLE = "ns-extr-data.analytics_310486481.events_fresh_20251106"


def generate(plan: Dict[str, Any], limit: int | None = 100) -> str:
    metric = plan.get("metric", "orders")
    grain = plan.get("grain", "day")

    # Very small, opinionated mapping for scaffold
    if metric == "gmv":
        expr = "SUM(net_amount) AS gmv"
    elif metric == "orders":
        expr = "COUNT(DISTINCT order_id) AS orders"
    else:
        expr = "COUNT(1) AS cnt"

    if grain == "day":
        group = "DATE(event_timestamp) AS day"
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
    FROM `{SEMANTIC_DEFAULT_TABLE}`
    WHERE 1=1
    {group_by}
    {order}
    """.strip()

    if limit:
        sql += f"\nLIMIT {int(limit)}"
    return sql

