"""Uniform JSON envelope for every endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def ok(data: Any, *, source: str = "local", cached: bool = False, **extra: Any) -> dict:
    meta = {
        "source": source,
        "cached": cached,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    meta.update(extra)
    return {"data": data, "meta": meta}


def meta_dict(meta) -> dict:
    return {
        "symbol": meta.symbol,
        "name": meta.name,
        "kind": meta.kind,
        "market": meta.market,
        "currency": meta.currency,
        "unit": meta.unit,
        "chart": meta.chart,
        "quotable": meta.quotable,
    }


def snapshot_dict(snapshot) -> dict:
    return {
        "symbol": snapshot.symbol,
        "name": snapshot.name,
        "last": snapshot.last,
        "prev_close": snapshot.prev_close,
        "change": snapshot.change,
        "change_pct": snapshot.change_pct,
        "open": snapshot.open,
        "high": snapshot.high,
        "low": snapshot.low,
        "volume": snapshot.volume,
        "amount": snapshot.amount,
        "ts": _local_iso(snapshot.ts),
        "source": snapshot.source,
        "bids": [
            {"price": level.price, "volume": level.volume} for level in snapshot.bids
        ],
        "asks": [
            {"price": level.price, "volume": level.volume} for level in snapshot.asks
        ],
    }


def _local_iso(value: datetime) -> str:
    from zoneinfo import ZoneInfo

    if value.tzinfo is None:
        value = value.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return value.isoformat(timespec="seconds")


def numeraire_dict(numeraire) -> dict:
    return {
        "id": numeraire.id,
        "label": numeraire.label,
        "group": numeraire.group,
        "unit": numeraire.unit,
    }
