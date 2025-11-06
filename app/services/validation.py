from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.semantic.loader import load_semantic_root

from app.services import validator
from app.bq import connector


@dataclass
class StepResult:
    name: str
    ok: bool
    message: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    steps: List[StepResult]
    sql: str
    schema: Optional[List[Dict[str, Any]]] = None


def lint_sql(sql: str) -> StepResult:
    issues = validator.lint(sql)
    ok = all(i.get("level") != "error" for i in issues)
    return StepResult(name="lint", ok=ok, meta={"issues": issues})


def dry_run(sql: str) -> StepResult:
    if not connector.available():
        return StepResult("dry_run", ok=True, message="bigquery client not installed", meta={})
    try:
        job = connector.run_query(sql, dry_run=True)
        total = getattr(job, "total_bytes_processed", 0) or 0
        return StepResult(
            name="dry_run",
            ok=True,
            meta={
                "total_bytes_processed": total,
            },
        )
    except Exception as e:
        return StepResult("dry_run", ok=False, message=str(e))


def explain(sql: str) -> StepResult:
    if not connector.available():
        return StepResult("explain", ok=True, message="bigquery client not installed")
    try:
        job = connector.run_query(f"EXPLAIN {sql}")
        rows = list(job.result())
        return StepResult(name="explain", ok=True, meta={"rows": [dict(r) for r in rows]})
    except Exception as e:
        return StepResult("explain", ok=False, message=str(e))


def schema(sql: str) -> StepResult:
    if not connector.available():
        return StepResult("schema", ok=True, message="bigquery client not installed")
    try:
        # LIMIT 0 to fetch schema cheaply
        wrapped = f"SELECT * FROM ({sql}) LIMIT 0"
        job = connector.run_query(wrapped, dry_run=False)
        _ = list(job.result())  # consume
        sch = []
        for f in job.schema or []:
            sch.append({"name": f.name, "type": f.field_type, "mode": f.mode})
        return StepResult(name="schema", ok=True, meta={"schema": sch})
    except Exception as e:
        return StepResult("schema", ok=False, message=str(e))


def canary(sql: str, limit_rows: int = 100) -> StepResult:
    if not connector.available():
        return StepResult("canary", ok=True, message="bigquery client not installed")
    try:
        canary_sql = f"SELECT * FROM ({sql}) LIMIT {int(limit_rows)}"
        job = connector.run_query(canary_sql, dry_run=False)
        rows = [dict(r) for r in job.result()]
        return StepResult(name="canary", ok=True, meta={"rowcount": len(rows)})
    except Exception as e:
        return StepResult("canary", ok=False, message=str(e))


def domain_assertions(sql: str, plan: Optional[Dict[str, Any]] = None) -> StepResult:
    sem = load_semantic_root()
    metrics_def = sem.get("metrics_definitions.yaml", {}) or {}
    metric = (plan or {}).get("metric") if plan else None
    try:
        if metric and isinstance(metrics_def, dict):
            items = metrics_def.get("metrics") or []
            if isinstance(items, list):
                for m in items:
                    if m.get("name") == metric:
                        # If default_filters exist, ensure tokens appear in SQL
                        filters = m.get("default_filters") or []
                        lowered = sql.lower()
                        for f in filters:
                            if str(f).lower() not in lowered:
                                return StepResult(
                                    name="assertions", ok=False,
                                    message=f"missing default filter for metric '{metric}': {f}")
        return StepResult(name="assertions", ok=True)
    except Exception as e:
        return StepResult(name="assertions", ok=False, message=str(e))


def run_pipeline(sql: str, perform_execute: bool = False, plan: Optional[Dict[str, Any]] = None) -> ValidationReport:
    steps: List[StepResult] = []

    # 1) Lint
    steps.append(lint_sql(sql))
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql)

    # 2) DRY RUN
    steps.append(dry_run(sql))
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql)

    # 3) EXPLAIN
    steps.append(explain(sql))
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql)

    # 4) SCHEMA
    sch = schema(sql)
    steps.append(sch)
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql)

    # 5) CANARY
    steps.append(canary(sql))
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))

    # 6) DOMAIN ASSERTIONS
    steps.append(domain_assertions(sql, plan=plan))
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))

    # 7) FINAL EXECUTION is handled by caller if desired.
    return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))
