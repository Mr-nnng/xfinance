"""Custom index CRUD, validation, and charts."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .deps import ServicesDep
from .envelope import ok

router = APIRouter(tags=["custom-indices"])


class CustomIndexIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    expression: str = Field(min_length=1, max_length=512)


class ExpressionIn(BaseModel):
    expression: str = Field(min_length=1, max_length=512)


@router.get("/custom-indices")
def list_indices(services: ServicesDep) -> dict:
    records = services.expressions.list()
    return ok(
        [
            {"id": item.id, "name": item.name, "expression": item.expression}
            for item in records
        ],
        source="local",
    )


@router.post("/custom-indices", status_code=201)
def create(services: ServicesDep, payload: CustomIndexIn) -> dict:
    record = services.expressions.create(payload.name, payload.expression)
    services.app.overview_cache.invalidate(("overview",))
    services.app.overview_cache.invalidate(("custom_cards",))
    return ok(
        {"id": record.id, "name": record.name, "expression": record.expression},
        source="local",
    )


@router.post("/custom-indices/validate")
def validate_expression(services: ServicesDep, payload: ExpressionIn) -> dict:
    return ok(services.expressions.validate(payload.expression), source="expression")


@router.get("/custom-indices/{index_id}")
def get_index(services: ServicesDep, index_id: int) -> dict:
    record = services.expressions.get(index_id)
    return ok(
        {"id": record.id, "name": record.name, "expression": record.expression},
        source="local",
    )


@router.get("/custom-indices/{index_id}/chart")
def index_chart(
    services: ServicesDep,
    index_id: int,
    range_key: str = Query("1y", alias="range"),
    window: int = Query(60, ge=10, le=500),
) -> dict:
    return ok(
        services.expressions.chart(index_id, range_key=range_key, window=window),
        source="expression",
    )


@router.delete("/custom-indices/{index_id}", status_code=204)
def delete_index(services: ServicesDep, index_id: int) -> None:
    services.expressions.delete(index_id)
    services.app.overview_cache.invalidate(("overview",))
    services.app.overview_cache.invalidate(("custom_cards",))
