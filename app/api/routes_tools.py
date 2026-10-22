"""Financial tool endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .deps import ServicesDep
from .envelope import ok

router = APIRouter(tags=["tools"])


@router.get("/tools/dca")
def dca(
    services: ServicesDep,
    symbol: str = Query(min_length=2),
    start: date | None = None,
    amount: float = Query(1000, gt=0),
    day: int = Query(1, ge=1, le=28),
    fee: float = Query(0.0, ge=0, le=5),
    numeraire: str = Query("CNY"),
) -> dict:
    payload = services.tools.dca(
        symbol,
        start=start,
        amount=amount,
        day=day,
        fee_pct=fee,
        numeraire_id=numeraire,
    )
    return ok(payload, source=payload["source"])


@router.get("/tools/correlation")
def correlation(
    services: ServicesDep,
    symbols: str = Query(min_length=3),
    window: int = Query(120, ge=30, le=750),
    numeraire: str = Query("CNY"),
) -> dict:
    values = [item.strip() for item in symbols.split(",")]
    payload = services.tools.correlation(
        values, window=window, numeraire_id=numeraire
    )
    return ok(payload, source="+".join(payload["sources"]))


class CompoundIn(BaseModel):
    principal: float = Field(100000, ge=0)
    monthly: float = Field(0, ge=0)
    annual_rate_pct: float = Field(8, ge=-99, le=100)
    years: int = Field(10, ge=1, le=60)


@router.post("/tools/compound")
def compound(services: ServicesDep, payload: CompoundIn) -> dict:
    result = services.tools.compound(
        principal=payload.principal,
        monthly=payload.monthly,
        annual_rate_pct=payload.annual_rate_pct,
        years=payload.years,
    )
    return ok(result, source="local")
