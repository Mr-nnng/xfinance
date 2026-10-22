"""Instrument search, metadata, snapshots, and charts."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..domain.catalog import normalize_symbol
from ..services.chart import DEFAULT_INDICATORS
from .deps import ServicesDep
from .envelope import meta_dict, ok, snapshot_dict

router = APIRouter(tags=["instruments"])


@router.get("/search")
def search(
    services: ServicesDep,
    q: str = Query(min_length=1, max_length=40),
    limit: int = Query(12, ge=1, le=30),
) -> dict:
    results = services.market.search(q, limit=limit)
    return ok([meta_dict(item) for item in results], source="search")


@router.get("/instruments/{symbol}")
def instrument(services: ServicesDep, symbol: str) -> dict:
    meta = services.market.meta(symbol)
    payload = meta_dict(meta)
    payload["watched"] = normalize_symbol(symbol) in services.watchlist.symbols()
    return ok(payload, source="local")


@router.get("/instruments/{symbol}/snapshot")
def snapshot(services: ServicesDep, symbol: str) -> dict:
    value, source = services.market.snapshot(symbol)
    return ok(snapshot_dict(value), source=source, cached=source == "cache")


@router.get("/instruments/{symbol}/chart")
def chart(
    services: ServicesDep,
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1d|1w|1m)$"),
    adjust: str = Query("none", pattern="^(none|qfq|hfq)$"),
    numeraire: str = Query("CNY"),
    normalize: bool = False,
    range_key: str = Query("1y", alias="range"),
    indicators: str = Query(DEFAULT_INDICATORS),
) -> dict:
    payload = services.chart.chart(
        symbol,
        timeframe=timeframe,
        adjust=adjust,
        numeraire_id=numeraire,
        normalize=normalize,
        range_key=range_key,
        indicators=indicators,
    )
    return ok(
        payload,
        source=payload["meta"]["source"],
        cached=payload["meta"]["source"] == "cache",
        quote_error=payload["meta"].get("quote_error"),
    )
