from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.deps import get_logger
from app.services import customer_flow

router = APIRouter(prefix="/api/network", tags=["network"])
logger = get_logger("api.network")


class CustomerFlowRequest(BaseModel):
    segment: str = Field(..., description="Segment identifier such as 'all' or 'new_customers'.")
    start_date: date | None = Field(None, description="Inclusive start date (YYYY-MM-DD).")
    end_date: date | None = Field(None, description="Inclusive end date (YYYY-MM-DD).")
    limit: int = Field(25, ge=5, le=200, description="Maximum number of edges to return.")
    min_edge_count: int = Field(3, ge=1, le=100, description="Drop edges with counts below this threshold.")


class SegmentOptionModel(BaseModel):
    id: str
    label: str
    description: str
    default: bool = False


class NetworkNodeModel(BaseModel):
    id: str
    label: str
    value: int


class NetworkLinkModel(BaseModel):
    source: str
    target: str
    value: int


class CustomerFlowResponse(BaseModel):
    segment: dict[str, Any]
    filters: dict[str, Any]
    nodes: list[NetworkNodeModel]
    links: list[NetworkLinkModel]
    summary: dict[str, Any]
    raw_edges: list[dict[str, Any]] | None = None
    data_source: dict[str, Any]


@router.get("/customer-flow/segments", response_model=list[SegmentOptionModel])
async def list_segments() -> list[dict[str, Any]]:
    """Expose available segment presets to the UI."""
    return customer_flow.segment_options()


@router.post("/customer-flow", response_model=CustomerFlowResponse)
async def build_customer_flow(req: CustomerFlowRequest) -> Any:
    """Fetch customer behavioral network data for the requested segment."""
    try:
        return customer_flow.fetch_customer_flow(
            segment_id=req.segment,
            start_date=req.start_date,
            end_date=req.end_date,
            limit=req.limit,
            min_edge_count=req.min_edge_count,
        )
    except customer_flow.SegmentNotFound as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("customer_flow_failed", extra={"segment": req.segment})
        raise HTTPException(status_code=500, detail="failed to build customer flow network") from exc
