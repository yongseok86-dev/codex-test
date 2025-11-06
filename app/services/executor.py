from dataclasses import dataclass
from typing import Any, List

from app.config import settings


@dataclass
class QueryResult:
    rows: List[dict] | None
    meta: dict


async def run(sql: str, dry_run: bool = True) -> QueryResult:
    # In scaffold, perform a fake execution or DRY RUN metadata
    if dry_run:
        meta = {
            "dry_run": True,
            "project": settings.gcp_project,
            "location": settings.bq_default_location,
        }
        return QueryResult(rows=None, meta=meta)

    # Real BigQuery execution could be implemented here using google-cloud-bigquery
    # For now, return a stub to keep scaffold self-contained.
    return QueryResult(
        rows=[{"example": 1}],
        meta={"dry_run": False},
    )

