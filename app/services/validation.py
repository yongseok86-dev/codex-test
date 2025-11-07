from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging
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
    """Semantic-aware assertions using plan + semantic YAML.

    Checks:
    - Metric default_filters present
    - If intent=metric_over_time with grain=day|week|month, SQL groups by a date bucket
    - If plan has time_window, SQL contains a time predicate
    - If metric maps to a canonical entity, SQL references that entity's table
    """
    sem = load_semantic_root()
    metrics_def = sem.get("metrics_definitions.yaml", {}) or {}
    sem_model = sem.get("semantic.yml", {}) or {}
    metric = (plan or {}).get("metric") if plan else None
    intent = (plan or {}).get("intent") if plan else None
    grain = (plan or {}).get("grain") if plan else None
    slots = (plan or {}).get("slots", {}) if plan else {}
    # Validate group_by dims if provided in slots
    if isinstance(slots, dict) and slots.get("group_by"):
        try:
            g = slots.get("group_by") or []
            if isinstance(g, list):
                for dim in g:
                    if str(dim).lower() not in lowered:
                        return StepResult(name="assertions", ok=False, message=f"missing group_by dimension in SQL: {dim}")
        except Exception:
            pass

    lowered = sql.lower()
    try:
        # 1) Metric default filters
        if metric and isinstance(metrics_def, dict):
            items = metrics_def.get("metrics") or []
            if isinstance(items, list):
                for m in items:
                    if m.get("name") == metric:
                        for f in m.get("default_filters") or []:
                            if str(f).lower() not in lowered:
                                return StepResult(
                                    name="assertions", ok=False,
                                    message=f"missing default filter for metric '{metric}': {f}")

        # 2) Grouping by time bucket for over_time intents
        if intent == "metric_over_time" and grain:
            # Heuristic: SQL should contain GROUP BY and a date bucketing (DATE/FORMAT_TIMESTAMP, etc.)
            if "group by" not in lowered or not any(k in lowered for k in ["date(", "timestamp_trunc", "format_timestamp", "extract("]):
                return StepResult(name="assertions", ok=False, message="expected time bucketing and GROUP BY for over-time metric")

        # 3) Time window predicate presence when requested
        if isinstance(slots, dict) and slots.get("time_window"):
            if not any(tok in lowered for tok in [" where ", "_table_suffix", "timestamp" , "date(", "order_date", "event_date"]):
                return StepResult(name="assertions", ok=False, message="expected time filter for requested time window")

        # 4) Entity table presence heuristic for metric
        if metric and isinstance(sem_model, dict):
            entities = sem_model.get("entities") or []
            # naive: if metric name matches a measure on an entity, ensure entity table appears
            target_table = None
            for e in entities or []:
                for meas in (e.get("measures") or []):
                    if meas.get("name") == metric and e.get("table"):
                        target_table = str(e.get("table")).lower()
                        break
                if target_table:
                    break
            if target_table and target_table not in lowered:
                return StepResult(name="assertions", ok=False, message=f"expected entity table reference: {target_table}")

        return StepResult(name="assertions", ok=True)
    except Exception as e:
        return StepResult(name="assertions", ok=False, message=str(e))


def run_pipeline(sql: str, perform_execute: bool = False, plan: Optional[Dict[str, Any]] = None, logger: Optional[logging.Logger] = None) -> ValidationReport:
    steps: List[StepResult] = []

    # 1) Lint
    if logger:
        logger.info("stage=lint start")
    steps.append(lint_sql(sql))
    if logger:
        logger.info("stage=lint end ok=%s", steps[-1].ok)
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql)

    # 2) DRY RUN
    if logger:
        logger.info("stage=dry_run start")
    steps.append(dry_run(sql))
    if logger:
        logger.info("stage=dry_run end ok=%s bytes=%s", steps[-1].ok, steps[-1].meta.get("total_bytes_processed") if steps[-1].ok else None)
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql)

    # 3) EXPLAIN
    if logger:
        logger.info("stage=explain start")
    steps.append(explain(sql))
    if logger:
        logger.info("stage=explain end ok=%s", steps[-1].ok)
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql)

    # 4) SCHEMA
    if logger:
        logger.info("stage=schema start")
    sch = schema(sql)
    steps.append(sch)
    if logger:
        logger.info("stage=schema end ok=%s cols=%s", steps[-1].ok, len((sch.meta.get("schema") or [])) if steps[-1].ok else None)
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql)

    # 5) CANARY
    if logger:
        logger.info("stage=canary start")
    steps.append(canary(sql))
    if logger:
        logger.info("stage=canary end ok=%s rows=%s", steps[-1].ok, steps[-1].meta.get("rowcount") if steps[-1].ok else None)
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))

    # 6) DOMAIN ASSERTIONS
    if logger:
        logger.info("stage=assertions start")
    steps.append(domain_assertions(sql, plan=plan))
    if logger:
        logger.info("stage=assertions end ok=%s", steps[-1].ok)
    if not steps[-1].ok:
        return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))

    # 7) FINAL EXECUTION is handled by caller if desired.
    return ValidationReport(steps=steps, sql=sql, schema=sch.meta.get("schema"))
