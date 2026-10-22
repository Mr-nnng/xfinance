"""Numeraire conversion as pure functions.

A numeraire is worth some amount of USD on a given day. A price is worth some
amount of USD on that day. Their ratio is the quote the chart plots.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from .catalog import Numeraire
from .models import Bar, SeriesMeta


@dataclass(frozen=True, slots=True)
class AsofSeries:
    dates: tuple[date, ...]
    values: tuple[float, ...]

    @classmethod
    def from_pairs(cls, pairs: Mapping[date, float]) -> AsofSeries:
        ordered = sorted((day, value) for day, value in pairs.items() if value > 0)
        return cls(
            dates=tuple(day for day, _ in ordered),
            values=tuple(value for _, value in ordered),
        )

    @classmethod
    def from_bars(cls, bars: list[Bar]) -> AsofSeries:
        ordered = sorted(
            ((bar.date, bar.close) for bar in bars if bar.close > 0),
            key=lambda item: item[0],
        )
        return cls(
            dates=tuple(day for day, _ in ordered),
            values=tuple(value for _, value in ordered),
        )

    def at(self, day: date) -> float | None:
        index = bisect_right(self.dates, day) - 1
        if index < 0:
            return None
        return self.values[index]


@dataclass(frozen=True, slots=True)
class FactorBook:
    """USD value of one unit of each currency and each priced asset series."""

    usd_per_currency: Mapping[str, AsofSeries]
    asset_values: Mapping[str, tuple[AsofSeries, str]]

    def currency_usd(self, day: date, currency: str) -> float | None:
        if currency == "USD":
            return 1.0
        series = self.usd_per_currency.get(currency)
        return series.at(day) if series else None

    def numeraire_usd(self, day: date, numeraire: Numeraire) -> float | None:
        if numeraire.kind == "unit":
            return 1.0
        if numeraire.kind == "fiat":
            return self.currency_usd(day, numeraire.currency)
        if not numeraire.series:
            return None
        entry = self.asset_values.get(numeraire.series)
        if entry is None:
            return None
        values, currency = entry
        native = values.at(day)
        if native is None:
            return None
        rate = self.currency_usd(day, currency)
        if rate is None:
            return None
        return native * rate


def numeraire_value_usd(
    day: date, numeraire: Numeraire, book: FactorBook
) -> float | None:
    value = book.numeraire_usd(day, numeraire)
    if value is None or value <= 0:
        return None
    return value


def quote_price(
    price: float, currency: str, day: date, numeraire: Numeraire, book: FactorBook
) -> float | None:
    rate = book.currency_usd(day, currency)
    denominator = numeraire_value_usd(day, numeraire, book)
    if rate is None or denominator is None or denominator <= 0:
        return None
    return price * rate / denominator


def quote_bars(
    bars: list[Bar],
    meta: SeriesMeta,
    numeraire: Numeraire,
    book: FactorBook,
    *,
    normalize: bool = False,
) -> tuple[list[Bar], str | None]:
    """Convert OHLC into numeraire units. Returns bars and a failure reason."""
    if not meta.quotable:
        return list(bars), None
    state = NumeraireState(meta, numeraire, book)
    converted: list[Bar] = []
    for bar in bars:
        open_ = state.price(bar.open, bar.date)
        high = state.price(bar.high, bar.date)
        low = state.price(bar.low, bar.date)
        close = state.price(bar.close, bar.date)
        if open_ is None or high is None or low is None or close is None:
            continue
        converted.append(
            Bar(
                date=bar.date,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=bar.volume,
                amount=bar.amount,
            )
        )
    if not converted:
        return [], state.error or "计价所需的历史序列不可用"
    if normalize:
        base = converted[0].close
        if base > 0:
            converted = [
                Bar(
                    date=bar.date,
                    open=bar.open / base,
                    high=bar.high / base,
                    low=bar.low / base,
                    close=bar.close / base,
                    volume=bar.volume,
                    amount=bar.amount,
                )
                for bar in converted
            ]
    return converted, None


@dataclass(slots=True)
class NumeraireState:
    meta: SeriesMeta
    numeraire: Numeraire
    book: FactorBook
    error: str | None = None

    def price(self, value: float, day: date) -> float | None:
        rate = self.book.currency_usd(day, self.meta.currency)
        if rate is None:
            self.error = f"缺少 {self.meta.currency} 汇率历史"
            return None
        denominator = self.book.numeraire_usd(day, self.numeraire)
        if denominator is None or denominator <= 0:
            self.error = f"缺少 {self.numeraire.label} 的历史序列"
            return None
        return value * rate / denominator


def rebase(values: list[float]) -> list[float]:
    if not values:
        return values
    base = values[0]
    if base == 0:
        return values
    return [value / base for value in values]
