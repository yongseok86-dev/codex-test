from typing import Any, Dict, Tuple


def extract(q: str) -> Tuple[str, Dict[str, Any]]:
    text = q.lower()
    # Extremely minimal heuristic NLU for scaffold/demo
    intent = "metric_over_time" if any(k in text for k in ["추이", "trend", "over time"]) else "metric"
    slots: Dict[str, Any] = {}

    # Metric hints
    if any(k in text for k in ["매출", "gmv", "매출액"]):
        slots["metric"] = "gmv"
    elif any(k in text for k in ["주문", "orders", "구매건수"]):
        slots["metric"] = "orders"

    # Time hints (very rough)
    if any(k in text for k in ["지난 7일", "최근 7일", "last 7 days"]):
        slots["time_window"] = {"days": 7}

    return intent, slots

