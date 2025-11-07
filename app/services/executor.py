from dataclasses import dataclass
from typing import Any, List

from app.config import settings
from app.deps import get_logger

try:
    from google.cloud import bigquery  # type: ignore
except Exception:  # pragma: no cover - optional import
    bigquery = None  # type: ignore


@dataclass
class QueryResult:
    rows: List[dict] | None
    meta: dict


async def run(sql: str, dry_run: bool = True) -> QueryResult:
    logger = get_logger("pipeline.exec")
    logger.info("stage=execute mode=%s", "dry_run" if dry_run else "full")
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
        total_bytes = getattr(job, "total_bytes_processed", 0) or 0
        tb = total_bytes / float(1024 ** 4)
        cost = tb * float(settings.price_per_tb_usd)
        meta = {
            "dry_run": True,
            "total_bytes_processed": total_bytes,
            "estimated_tb": round(tb, 6),
            "estimated_cost_usd": round(cost, 6),
            "cache_hit": getattr(job, "cache_hit", None),
            "job_id": getattr(job, "job_id", None),
            "location": getattr(job, "location", None),
        }
        logger.info("stage=execute result bytes=%s cost=%s", total_bytes, meta["estimated_cost_usd"])
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
    logger.info("stage=execute result rows=%s job_id=%s", len(rows), meta["job_id"])
    return QueryResult(rows=rows, meta=meta)


async def materialize(sql: str) -> QueryResult:
    logger = get_logger("pipeline.exec")
    logger.info("stage=materialize start")
    if bigquery is None:
        return QueryResult(rows=None, meta={"materialized": False, "error": "bigquery client not installed"})
    dataset = getattr(settings, "bq_materialize_dataset", None)
    if not dataset:
        return QueryResult(rows=None, meta={"materialized": False, "error": "bq_materialize_dataset not configured"})
    client = bigquery.Client(project=settings.gcp_project)  # type: ignore
    table_name = f"mat_{abs(hash(sql)) & 0xFFFFFFFF:08x}"
    destination = f"{dataset}.{table_name}"
    job_config = bigquery.QueryJobConfig()
    job_config.destination = destination
    job_config.write_disposition = bigquery.WriteDisposition.WRITE_TRUNCATE
    job_config.create_disposition = bigquery.CreateDisposition.CREATE_IF_NEEDED
    job = client.query(sql, job_config=job_config)
    job.result()  # wait
    # Set expiration if configured
    expires_hours = int(getattr(settings, "bq_materialize_expiration_hours", 24))
    try:
        table = client.get_table(destination)
        from datetime import datetime, timedelta
        table.expires = datetime.utcnow() + timedelta(hours=expires_hours)
        client.update_table(table, ["expires"])  # type: ignore
    except Exception:
        pass
    logger.info("stage=materialize end table=%s", destination)
    return QueryResult(rows=None, meta={"materialized": True, "table": destination})
