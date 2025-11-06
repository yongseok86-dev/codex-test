from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.deps import get_logger
from app.services import nlu, planner, sqlgen, validator, executor


router = APIRouter(prefix="/api", tags=["query"])
logger = get_logger(__name__)


class QueryRequest(BaseModel):
    q: str
    limit: int | None = 100
    dry_run: bool | None = None


class QueryResponse(BaseModel):
    sql: str
    dry_run: bool
    rows: list[dict] | None = None
    metadata: dict | None = None


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    if not req.q or len(req.q.strip()) < 2:
        raise HTTPException(status_code=400, detail="query text 'q' is required")

    # 1) NLU
    intent, slots = nlu.extract(req.q)
    # 2) Plan
    plan = planner.make_plan(intent=intent, slots=slots)
    # 3) SQL Generation (BigQuery dialect)
    sql = sqlgen.generate(plan, limit=req.limit)
    # 4) Guardrails/Validation
    validator.ensure_safe(sql)

    # 5) Execute (or DRY RUN)
    dry = settings.dry_run_only if req.dry_run is None else req.dry_run
    result = await executor.run(sql, dry_run=dry)

    logger.info(
        "query_executed",
        extra={"intent": intent, "slots": slots, "dry_run": dry},
    )

    return QueryResponse(sql=sql, dry_run=dry, rows=result.rows, metadata=result.meta)

