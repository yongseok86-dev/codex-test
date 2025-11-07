from __future__ import annotations

from typing import Any

try:
    import sqlglot
except Exception:
    sqlglot = None  # type: ignore


class SQLSyntaxError(Exception):
    pass


def parse_sql(sql: str) -> Any:
    if sqlglot is None:
        return None
    try:
        return sqlglot.parse_one(sql, read="bigquery")
    except Exception as e:
        raise SQLSyntaxError(str(e))

