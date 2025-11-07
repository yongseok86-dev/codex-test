from __future__ import annotations

from typing import Any, Dict


def generate_template_sql(plan: Dict[str, Any]) -> str:
    """Very simple template-based SQL for easy queries.
    Uses plan.metric and plan.grain to create a SELECT with GROUP BY date.
    """
    metric = plan.get("metric", "orders")
    grain = plan.get("grain", "day")
    table = plan.get("table") or "`proj.mall.orders`"

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
        group_by = "GROUP BY day ORDER BY day"
    else:
        group = "1"
        group_by = ""

    sql = f"SELECT {group}, {expr} FROM {table} WHERE 1=1 {group_by}"
    return sql

