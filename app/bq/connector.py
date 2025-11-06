from __future__ import annotations

from typing import Optional, Any
from app.config import settings

try:
    from google.cloud import bigquery  # type: ignore
except Exception:  # pragma: no cover
    bigquery = None  # type: ignore


def available() -> bool:
    return bigquery is not None


def client() -> Any:
    if bigquery is None:
        raise RuntimeError("google-cloud-bigquery is not installed")
    return bigquery.Client(project=settings.gcp_project)


def base_job_config(dry_run: bool = False) -> Any:
    if bigquery is None:
        raise RuntimeError("google-cloud-bigquery is not installed")
    cfg = bigquery.QueryJobConfig()
    cfg.dry_run = dry_run
    cfg.maximum_bytes_billed = settings.maximum_bytes_billed
    cfg.labels = {"app": "nl2sql"}
    return cfg


def run_query(sql: str, dry_run: bool = False) -> Any:
    c = client()
    cfg = base_job_config(dry_run=dry_run)
    return c.query(sql, job_config=cfg)

