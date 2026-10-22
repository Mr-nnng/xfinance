"""Bar-series helpers shared by live sources, demo data, and services."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from .models import Bar, Timeframe


def resample_bars(bars: Sequence[Bar], timeframe: Timeframe) -> list[Bar]:
    if timeframe == "1d":
        return list(bars)
    if not bars:
        return []
    groups: list[list[Bar]] = []
    current_key: tuple[int, int] | None = None
    for bar in bars:
        key = _week_key(bar.date) if timeframe == "1w" else (bar.date.year, bar.date.month)
        if key != current_key:
            groups.append([])
            current_key = key
        groups[-1].append(bar)
    return [_aggregate(group) for group in groups]


def _week_key(day: date) -> tuple[int, int]:
    iso = day.isocalendar()
    return (iso.year, iso.week)


def _aggregate(bars: list[Bar]) -> Bar:
    last = bars[-1]
    return Bar(
        date=last.date,
        open=bars[0].open,
        high=max(bar.high for bar in bars),
        low=min(bar.low for bar in bars),
        close=last.close,
        volume=sum(bar.volume for bar in bars),
        amount=sum(bar.amount for bar in bars),
    )
