"""Watchlist CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from .deps import ServicesDep
from .envelope import meta_dict, ok, snapshot_dict

router = APIRouter(tags=["watchlist"])


@router.get("/watchlist")
def watchlist(services: ServicesDep) -> dict:
    symbols = services.watchlist.symbols()
    metas = [services.market.meta(symbol) for symbol in symbols]
    snapshots, source = services.market.snapshots(symbols) if symbols else ({}, "local")
    cards = []
    for meta in metas:
        bars = services.bars.fetch(meta.symbol, "1d", "none")[-45:]
        cards.append(
            {
                "meta": meta_dict(meta),
                "snapshot": snapshot_dict(snapshots[meta.symbol])
                if meta.symbol in snapshots
                else None,
                "spark": [bar.close for bar in bars],
            }
        )
    return ok({"symbols": symbols, "cards": cards}, source=source)


@router.post("/watchlist/{symbol}", status_code=status.HTTP_201_CREATED)
def add(services: ServicesDep, symbol: str) -> dict:
    meta = services.market.meta(symbol)
    created = services.watchlist.add(meta.symbol)
    services.app.overview_cache.invalidate(("overview",))
    return ok(
        {"symbol": meta.symbol, "created": created, "symbols": services.watchlist.symbols()},
        source="local",
    )


@router.delete("/watchlist/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def remove(services: ServicesDep, symbol: str) -> Response:
    services.watchlist.remove(symbol.strip().upper())
    services.app.overview_cache.invalidate(("overview",))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
