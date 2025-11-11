from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import time_series

router = APIRouter(prefix="/api/time-series", tags=["time-series"])


class TimeSeriesPoint(BaseModel):
    bucket: str
    total_quantity: int


class TimeSeriesResponse(BaseModel):
    series: list[TimeSeriesPoint]
    filters: dict[str, Any]
    stub: bool | None = None


@router.get("/purchases", response_model=TimeSeriesResponse)
async def purchases(
    product_id: str | None = Query(default=None, description="필터링할 상품 ID"),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    grain: str = Query(default="day", pattern="^(day|week|month)$"),
) -> Any:
    try:
        return time_series.fetch_product_series(product_id, start_date, end_date, grain)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="failed to fetch time series") from exc


class BubblePoint(BaseModel):
    time_bucket: str
    product_name: str
    total_quantity: int


class BubbleResponse(BaseModel):
    series: list[BubblePoint]
    filters: dict[str, Any]
    stub: bool | None = None


@router.get("/purchases/bubbles", response_model=BubbleResponse)
async def purchase_bubbles() -> Any:
    try:
        return time_series.fetch_bubble_series()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="failed to fetch bubble data") from exc
