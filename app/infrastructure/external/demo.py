"""Deterministic offline data.

The demo source is a first-class data source, not a mock hidden inside live
code: it powers tests, first launch, and the fallback path in auto mode.
"""

from __future__ import annotations

import hashlib
import math
import random
import threading
from dataclasses import replace
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ...domain.catalog import (
    COMMODITY_SERIES,
    FEATURED,
    FX_SERIES,
    INDEX_SERIES,
    YIELD_TENORS,
    infer_meta,
    normalize_symbol,
    series_meta,
)
from ...domain.models import Bar, Level, SeriesMeta, Snapshot, Timeframe
from ...domain.series import resample_bars

_START = date(2021, 1, 4)
_BASE: dict[str, float] = {
    "SH000001": 3658.0,
    "SZ399001": 11357.0,
    "SZ399006": 2577.0,
    "SH000300": 4036.0,
    "SH000905": 6800.0,
    "SH000016": 2900.0,
    "USDCNY": 6.68,
    "USDJPY": 157.9,
    "USDEUR": 0.885,
    "USDGBP": 0.79,
    "XAUUSD": 4070.0,
    "XAGUSD": 55.2,
    "WTIUSD": 98.6,
    "BRENTUSD": 111.8,
    "AU9999": 880.3,
    "UST1Y": 4.52,
    "UST2Y": 4.81,
    "UST3Y": 4.89,
    "UST5Y": 4.95,
    "UST7Y": 5.03,
    "UST10Y": 5.13,
    "UST20Y": 5.47,
    "UST30Y": 5.42,
    "SH600519": 1318.0,
    "SH601318": 58.5,
    "SH600036": 42.0,
    "SH601899": 28.0,
    "SZ000001": 11.3,
    "SZ000858": 120.0,
    "SZ300750": 380.0,
    "SZ002594": 110.0,
    "SH510300": 4.1,
    "SH588000": 1.02,
    "SZ159915": 2.59,
    "SH501050": 1.0,
}

_FACTOR_CACHE: dict[tuple[date, date], tuple[list[float], list[float]]] = {}
_FACTOR_LOCK = threading.Lock()

_FACTOR_LOADING: dict[str, tuple[float, float]] = {
    "stock": (0.8, 0.08),
    "etf": (0.9, 0.05),
    "lof": (0.9, 0.05),
    "index": (0.96, 0.0),
    "fx": (0.0, 0.0),
    "commodity": (0.08, 0.8),
}

_VOL: dict[str, float] = {
    "index": 0.16,
    "stock": 0.30,
    "etf": 0.20,
    "lof": 0.20,
    "fx": 0.045,
    "commodity": 0.26,
    "yield": 0.02,
}


class DemoProvider:
    source = "demo"

    def __init__(self, *, as_of: date | None = None) -> None:
        self.as_of = as_of or date.today()
        self._cache: dict[tuple[str, str], list[Bar]] = {}
        self._lock = threading.Lock()

    def has_symbol(self, symbol: str) -> bool:
        return series_meta(symbol) is not None

    def bars(
        self,
        symbol: str,
        timeframe: Timeframe = "1d",
        adjust: str = "none",
        count: int | None = None,
    ) -> list[Bar]:
        daily = self.daily(symbol)
        values = daily if timeframe == "1d" else resample_bars(daily, timeframe)
        if count is not None and count > 0:
            values = values[-count:]
        return [replace(bar) for bar in values]

    def daily(self, symbol: str) -> list[Bar]:
        symbol = normalize_symbol(symbol)
        key = (symbol, "1d")
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return [replace(bar) for bar in cached]
            generated = self._generate(symbol)
            self._cache[key] = generated
            return [replace(bar) for bar in generated]

    def _latest_pair(self, symbol: str) -> tuple[Bar, Bar]:
        key = (normalize_symbol(symbol), "1d")
        with self._lock:
            bars = self._cache.get(key)
            if bars is None:
                bars = self._generate(symbol)
                self._cache[key] = bars
            last = bars[-1]
            return last, bars[-2] if len(bars) > 1 else last

    def snapshot(self, meta: SeriesMeta) -> Snapshot:
        last, previous = self._latest_pair(meta.symbol)
        rng = random.Random(_seed(meta.symbol) + 7)
        mid = last.close
        step = mid * 0.001
        if meta.quotable and meta.kind != "yield":
            bids = tuple(
                Level(price=round(mid - step * index, 4), volume=round(rng.uniform(5, 80), 1))
                for index in range(5)
            )
            asks = tuple(
                Level(price=round(mid + step * index, 4), volume=round(rng.uniform(5, 80), 1))
                for index in range(1, 6)
            )
        else:
            bids = ()
            asks = ()
        volume = last.volume if meta.quotable else 0.0
        return Snapshot(
            symbol=meta.symbol,
            name=meta.name,
            last=mid,
            prev_close=previous.close,
            open=last.open,
            high=last.high,
            low=last.low,
            volume=volume,
            amount=last.amount,
            ts=datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None),
            bids=bids,
            asks=asks,
            source=self.source,
        )

    def securities(self) -> list[tuple[str, str, str, str, str]]:
        rows: list[tuple[str, str, str, str, str]] = []
        for symbol, name in INDEX_SERIES.items():
            rows.append((symbol, name, "index", symbol[:2], "index"))
        for symbol, (name, kind) in FEATURED.items():
            rows.append((symbol, name, kind, symbol[:2], "main"))
        return rows

    def search(self, query: str, limit: int = 20) -> list[SeriesMeta]:
        text = query.strip().lower()
        if not text:
            return []
        candidates: list[SeriesMeta] = []
        for symbol, name in INDEX_SERIES.items():
            candidates.append(infer_meta(symbol, name))
        for symbol, (name, _kind) in FEATURED.items():
            candidates.append(infer_meta(symbol, name))
        for symbol, (name, _currency) in FX_SERIES.items():
            candidates.append(infer_meta(symbol, name))
        for symbol, (name, _unit, _currency) in COMMODITY_SERIES.items():
            candidates.append(infer_meta(symbol, name))
        for _column, symbol, name in YIELD_TENORS:
            candidates.append(infer_meta(symbol, name))
        return [
            meta
            for meta in candidates
            if text in meta.symbol.lower() or text in meta.name.lower()
        ][:limit]

    # -- generation ----------------------------------------------------

    def _generate(self, symbol: str) -> list[Bar]:
        meta = series_meta(symbol) or infer_meta(symbol)
        base = _BASE.get(symbol)
        if base is None:
            base = 8.0 + (_seed(symbol) % 5000) / 100.0
        volatility = _VOL.get(meta.kind, 0.25)
        rng = random.Random(_seed(symbol))
        days = _weekdays(_START, self.as_of)
        if not days:
            return []
        if meta.kind == "yield":
            return self._generate_yields(symbol, base, days, rng)
        equity_factor, commodity_factor = _factors(days)
        equity_beta, commodity_beta = _FACTOR_LOADING.get(meta.kind, (0.0, 0.0))
        factor_variance = (equity_beta * 0.012) ** 2 + (commodity_beta * 0.013) ** 2
        total_variance = (volatility / math.sqrt(252)) ** 2
        idio = math.sqrt(max(total_variance - factor_variance, 1e-6))
        values: list[Bar] = []
        price = base * 0.72
        for index, day in enumerate(days):
            regime = math.sin(index / 90.0 + (rng.random() - 0.5)) * 0.0004
            shock = (
                equity_beta * equity_factor[index]
                + commodity_beta * commodity_factor[index]
                + rng.gauss(0, idio)
            )
            previous = price
            price = max(0.01, previous * math.exp(0.00012 + regime + shock))
            open_ = previous * math.exp(rng.gauss(0, volatility / math.sqrt(252) * 0.25))
            high = max(open_, price) * math.exp(abs(rng.gauss(0, volatility / 350)))
            low = min(open_, price) * math.exp(-abs(rng.gauss(0, volatility / 350)))
            volume = (1_000_000 if meta.kind in {"stock", "etf", "lof"} else 0.0) * math.exp(
                rng.gauss(0, 0.45)
            )
            values.append(
                Bar(
                    date=day,
                    open=round(open_, 3),
                    high=round(high, 3),
                    low=round(low, 3),
                    close=round(price, 3),
                    volume=round(volume, 1),
                    amount=round(volume * price, 1),
                )
            )
        scale = base / values[-1].close if values[-1].close else 1.0
        scaled = [
            Bar(
                date=bar.date,
                open=round(bar.open * scale, 3),
                high=round(bar.high * scale, 3),
                low=round(bar.low * scale, 3),
                close=round(bar.close * scale, 3),
                volume=bar.volume,
                amount=bar.amount * scale,
            )
            for bar in values
        ]
        if meta.kind == "fx":
            scaled = [
                Bar(
                    date=bar.date,
                    open=bar.close,
                    high=bar.close,
                    low=bar.close,
                    close=bar.close,
                    volume=0.0,
                    amount=0.0,
                )
                for bar in scaled
            ]
        return scaled

    def _generate_yields(
        self, symbol: str, base: float, days: list[date], rng: random.Random
    ) -> list[Bar]:
        value = base
        rows: list[Bar] = []
        for _day in days:
            value += (base - value) * 0.02 + rng.gauss(0, 0.035)
            value = max(0.05, value)
            rows.append(
                Bar(
                    date=_day,
                    open=round(value, 3),
                    high=round(value, 3),
                    low=round(value, 3),
                    close=round(value, 3),
                )
            )
        return rows


def _factors(days: list[date]) -> tuple[list[float], list[float]]:
    key = (days[0], days[-1])
    with _FACTOR_LOCK:
        cached = _FACTOR_CACHE.get(key)
        if cached is not None:
            return cached
        rng = random.Random(20260101)
        equity: list[float] = []
        commodity: list[float] = []
        for index in range(len(days)):
            equity.append(rng.gauss(0, 0.012) + math.sin(index / 70.0) * 0.0004)
            commodity.append(rng.gauss(0, 0.013) + math.cos(index / 110.0) * 0.0005)
        _FACTOR_CACHE[key] = (equity, commodity)
        return _FACTOR_CACHE[key]


def _seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _weekdays(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days
