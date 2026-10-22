"""Core domain types. No framework imports belong in this package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

Kind = Literal["stock", "etf", "lof", "index", "fx", "commodity", "yield"]
Timeframe = Literal["1d", "1w", "1m"]
Adjust = Literal["none", "qfq", "hfq"]
ChartType = Literal["candlestick", "line"]


@dataclass(frozen=True, slots=True)
class Bar:
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float = 0.0


@dataclass(frozen=True, slots=True)
class SeriesMeta:
    symbol: str
    name: str
    kind: Kind
    market: str
    currency: str
    unit: str
    chart: ChartType = "candlestick"
    quotable: bool = True

    @property
    def is_price_series(self) -> bool:
        return self.kind != "yield"


@dataclass(frozen=True, slots=True)
class Level:
    price: float
    volume: float


@dataclass(frozen=True, slots=True)
class Snapshot:
    symbol: str
    name: str
    last: float
    prev_close: float
    open: float
    high: float
    low: float
    volume: float
    amount: float
    ts: datetime
    bids: tuple[Level, ...] = ()
    asks: tuple[Level, ...] = ()
    source: str = "demo"

    @property
    def change(self) -> float:
        return self.last - self.prev_close

    @property
    def change_pct(self) -> float:
        if self.prev_close == 0:
            return 0.0
        return (self.last / self.prev_close - 1.0) * 100.0


@dataclass(frozen=True, slots=True)
class NumericSeries:
    dates: tuple[date, ...]
    values: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class QuotePoint:
    date: date
    value: float


@dataclass(frozen=True, slots=True)
class ResultSet:
    """What a service hands back: payload plus provenance."""

    data: object
    source: str
    cached: bool = False


@dataclass(frozen=True, slots=True)
class StoredCustomIndex:
    id: int
    name: str
    expression: str
