from dataclasses import dataclass
from typing import Any, List

from app.config import settings

try:
    from google.cloud import bigquery  # type: ignore
except Exception:  # pragma: no cover - optional import
    bigquery = None  # type: ignore


@dataclass
class QueryResult:
    rows: List[dict] | None
    meta: dict


async def run(sql: str, dry_run: bool = True) -> QueryResult:
    # If BigQuery lib not available, return stub
    if bigquery is None:
        return QueryResult(rows=None, meta={"dry_run": True, "note": "bigquery client not installed"})

    client = bigquery.Client(project=settings.gcp_project)  # type: ignore
    job_config = bigquery.QueryJobConfig()
    job_config.maximum_bytes_billed = settings.maximum_bytes_billed
    job_config.labels = {"app": "nl2sql"}

    if dry_run:
        job_config.dry_run = True
        job = client.query(sql, job_config=job_config)
        meta = {
            "dry_run": True,
            "total_bytes_processed": getattr(job, "total_bytes_processed", None),
            "cache_hit": getattr(job, "cache_hit", None),
            "job_id": getattr(job, "job_id", None),
            "location": getattr(job, "location", None),
        }
        return QueryResult(rows=None, meta=meta)

    # Execute query
    job = client.query(sql, job_config=job_config)
    result_iter = job.result()
    rows = [dict(row) for row in result_iter]
    meta = {
        "dry_run": False,
        "job_id": job.job_id,
        "location": job.location,
        "total_bytes_processed": getattr(job, "total_bytes_processed", None),
        "billing_tier": getattr(job, "billing_tier", None),
    }
    return QueryResult(rows=rows, meta=meta)
