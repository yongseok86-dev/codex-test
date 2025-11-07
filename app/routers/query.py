from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
from pydantic import BaseModel

from app.config import settings
from app.deps import get_logger
from app.services import nlu, planner, sqlgen, validator, executor
from app.services.llm import generate_sql_via_llm, LLMNotConfigured
from app.deps import get_logger
from app.services.validation import run_pipeline


router = APIRouter(prefix="/api", tags=["query"])
logger = get_logger(__name__)


class QueryRequest(BaseModel):
    q: str
    limit: int | None = 100
    dry_run: bool | None = None
    use_llm: bool | None = None
    llm_provider: str | None = None  # 'openai' | 'claude' | 'gemini'
    materialize: bool | None = None
    conversation_id: str | None = None


class QueryResponse(BaseModel):
    sql: str
    dry_run: bool
    rows: list[dict] | None = None
    metadata: dict | None = None


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    logger = get_logger(__name__)
    if not req.q or len(req.q.strip()) < 2:
        raise HTTPException(status_code=400, detail="query text 'q' is required")

    # 0) Normalize
    from app.services import normalize, context
    norm_q, norm_meta = normalize.normalize(req.q)
    ctx = context.get_context(req.conversation_id or "")

    # 1) NLU
    intent, slots = nlu.extract(norm_q)
    # 2) Plan
    plan = planner.make_plan(intent=intent, slots=slots)
    plan["slots"] = slots
    # 3) SQL Generation (LLM or rule-based)
    if req.use_llm:
        try:
            sql = generate_sql_via_llm(norm_q, provider=req.llm_provider)
        except Exception as e:
            logger.warning(f"LLM provider failed, falling back to rule-based: {e}")
            sql = sqlgen.generate(plan, limit=req.limit)
    else:
        sql = sqlgen.generate(plan, limit=req.limit)

    # Optional: schema linking
    from app.services import linking, guard
    linking_info = linking.schema_link(norm_q)
    try:
        guard.parse_sql(sql)
    except Exception as e:
        logger.warning(f"SQL parse failed: {e}")
    # 4) Guardrails/Validation (lint + pipeline)
    validator.ensure_safe(sql)
    report = run_pipeline(sql, perform_execute=False, plan=plan)
    # If validation failed and LLM allowed, try one repair
    failed = next((s for s in report.steps if not s.ok), None)
    repaired = None
    if failed and req.use_llm and settings.llm_enable_repair:
        from app.services import repair
        fixed = repair.attempt_repair(norm_q, sql, failed.message, req.llm_provider)
        if fixed and fixed != sql:
            try:
                validator.ensure_safe(fixed)
                r2 = run_pipeline(fixed, perform_execute=False, plan=plan)
                if all(s.ok for s in r2.steps):
                    repaired = {"original_sql": sql, "fixed_sql": fixed, "failed_step": failed.name}
                    sql = fixed
                    report = r2
            except Exception:
                pass

    # 5) Execute (or DRY RUN) — after validations
    dry = settings.dry_run_only if req.dry_run is None else req.dry_run
    if dry:
        result = await executor.run(sql, dry_run=True)
    else:
        if req.materialize:
            result = await executor.materialize(sql)
        else:
            try:
                result = await executor.run(sql, dry_run=False)
            except Exception as e:
                # Try a repair loop on execution error
                if req.use_llm and settings.llm_enable_repair and settings.llm_repair_max_attempts > 0:
                    from app.services import repair
                    fixed = repair.attempt_repair(norm_q, sql, str(e), req.llm_provider)
                    if fixed and fixed != sql:
                        try:
                            validator.ensure_safe(fixed)
                            r2 = run_pipeline(fixed, perform_execute=False, plan=plan)
                            if all(s.ok for s in r2.steps):
                                sql = fixed
                                report = r2
                                result = await executor.run(sql, dry_run=False)
                        except Exception:
                            raise e
                else:
                    raise e

    logger.info(
        "query_executed",
        extra={"intent": intent, "slots": slots, "dry_run": dry},
    )

    meta = result.meta or {}
    meta["validation_steps"] = [s.__dict__ for s in report.steps]
    meta["linking"] = linking_info
    meta["normalized"] = norm_meta
    if repaired:
        meta["repair"] = repaired
    # Optional summary
    from app.services import summarize
    meta["summary"] = summarize.summarize(result.rows, meta)
    if settings.llm_enable_result_summary and req.use_llm:
        llm_sum = summarize.summarize_llm(norm_q, sql, meta, provider=req.llm_provider)
        if llm_sum:
            meta["nl_summary"] = llm_sum

    # Update context
    context.update_context(req.conversation_id or "", {"last_sql": sql, "last_plan": plan})

    return QueryResponse(sql=sql, dry_run=dry, rows=result.rows, metadata=meta)


@router.get("/query/stream")
async def query_stream(q: str, limit: int | None = 100, dry_run: bool | None = None, use_llm: bool | None = None, llm_provider: str | None = None):
    logger = get_logger(__name__)
    async def event_gen():
        def sse(event: str, data: dict):
            payload = json.dumps(data, ensure_ascii=False)
            return f"event: {event}\ndata: {payload}\n\n"

        if not q or len(q.strip()) < 2:
            yield sse("error", {"message": "query text 'q' is required"})
            return

        intent, slots = nlu.extract(q)
        yield sse("nlu", {"intent": intent, "slots": slots})

        plan = planner.make_plan(intent=intent, slots=slots)
        yield sse("plan", plan)

        if use_llm:
            try:
                sql = generate_sql_via_llm(q, provider=llm_provider)
                yield sse("sql", {"sql": sql, "source": "llm", "provider": llm_provider or ""})
            except Exception as e:
                logger.warning(f"LLM provider failed, fallback to rule-based: {e}")
                yield sse("info", {"message": "LLM provider failed; falling back to rule-based SQL."})
                sql = sqlgen.generate(plan, limit=limit)
                yield sse("sql", {"sql": sql, "source": "rule"})
        else:
            sql = sqlgen.generate(plan, limit=limit)
            yield sse("sql", {"sql": sql, "source": "rule"})

        try:
            validator.ensure_safe(sql)
            yield sse("validated", {"ok": True})
            # Run validation pipeline
            report = run_pipeline(sql, perform_execute=False, plan=plan)
            for step in report.steps:
                yield sse("check", {"name": step.name, "ok": step.ok, "message": step.message, "meta": step.meta})
        except Exception as e:
            yield sse("validated", {"ok": False, "error": str(e)})
            return

        d = settings.dry_run_only if dry_run is None else dry_run
        result = await executor.run(sql, dry_run=d)
        yield sse("result", {"sql": sql, "dry_run": d, "rows": result.rows, "metadata": result.meta})

    return StreamingResponse(event_gen(), media_type="text/event-stream")
