from __future__ import annotations

from datetime import datetime, timedelta, timezone


def last_n_days_utc(n: int) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=n)
    return start, now

