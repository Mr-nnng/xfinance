from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.catalog import normalize_symbol, numeraire_by_id, series_meta
from app.domain.models import Bar, NumericSeries, SeriesMeta
from app.domain.pricing import AsofSeries, FactorBook, quote_bars


def make_bars(values: list[float], start: date = date(2026, 1, 5)) -> list[Bar]:
    bars: list[Bar] = []
    day = start
    for value in values:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        bars.append(
            Bar(
                date=day,
                open=value * 0.99,
                high=value * 1.02,
                low=value * 0.97,
                close=value,
                volume=1000,
                amount=value * 1000,
            )
        )
        day += timedelta(days=1)
    return bars


def stock_meta(currency: str = "CNY") -> SeriesMeta:
    return SeriesMeta(
        symbol="SH600519",
        name="贵州茅台",
        kind="stock",
        market="SH",
        currency=currency,
        unit="股",
    )


def book(
    cny_per_usd: float = 7.0,
    gold_usd: float = 2000.0,
    gold_cny_g: float = 500.0,
) -> FactorBook:
    day = date(2025, 1, 1)
    return FactorBook(
        usd_per_currency={
            "CNY": AsofSeries((day,), (1 / cny_per_usd,)),
            "JPY": AsofSeries((day,), (1 / 150.0,)),
            "EUR": AsofSeries((day,), (1 / 1.1,)),
        },
        asset_values={
            "XAUUSD": (AsofSeries((day,), (gold_usd,)), "USD"),
            "AU9999": (AsofSeries((day,), (gold_cny_g,)), "CNY"),
            "WTIUSD": (AsofSeries((day,), (100.0,)), "USD"),
        },
    )


def test_normalize_symbol() -> None:
    assert normalize_symbol("sh600519") == "SH600519"
    assert normalize_symbol("600519") == "SH600519"
    assert normalize_symbol("000001") == "SZ000001"
    assert normalize_symbol("600519.SH") == "SH600519"
    assert normalize_symbol("USDCNY") == "USDCNY"


def test_series_meta_for_fx_and_yield() -> None:
    fx = series_meta("USDCNY")
    assert fx is not None and fx.kind == "fx" and fx.chart == "line"
    yield_meta = series_meta("UST10Y")
    assert yield_meta is not None and not yield_meta.quotable
    assert series_meta("SH600519") is not None


def test_quote_stock_into_usd() -> None:
    bars = make_bars([100.0, 110.0])
    quoted, error = quote_bars(
        bars, stock_meta(), numeraire_by_id("USD"), book(cny_per_usd=7.0)
    )
    assert error is None
    assert quoted[0].close == pytest.approx(100 / 7)
    assert quoted[1].close == pytest.approx(110 / 7)


def test_quote_stock_into_gold_ounces() -> None:
    bars = make_bars([7000.0])
    quoted, _ = quote_bars(
        bars,
        stock_meta(),
        numeraire_by_id("XAU"),
        book(cny_per_usd=7.0, gold_usd=2000.0),
    )
    assert quoted[0].close == pytest.approx(1000 / 2000)


def test_quote_stock_into_cny_gold_grams() -> None:
    bars = make_bars([1000.0])
    quoted, _ = quote_bars(
        bars,
        stock_meta(),
        numeraire_by_id("XAU_CNY_G"),
        book(cny_per_usd=7.0, gold_cny_g=500.0),
    )
    assert quoted[0].close == pytest.approx(2.0)


def test_normalize_starts_at_one() -> None:
    bars = make_bars([50.0, 75.0, 100.0])
    quoted, _ = quote_bars(
        bars,
        stock_meta(),
        numeraire_by_id("CNY"),
        book(),
        normalize=True,
    )
    assert quoted[0].close == pytest.approx(1.0)
    assert quoted[-1].close == pytest.approx(2.0)
    assert quoted[1].open == pytest.approx(0.99 * 1.5)


def test_missing_factor_dates_are_skipped() -> None:
    bars = make_bars([100.0, 101.0])
    no_history = FactorBook(
        usd_per_currency={"CNY": AsofSeries((date(2026, 2, 1),), (1 / 7.0,))},
        asset_values={},
    )
    quoted, error = quote_bars(
        bars, stock_meta(), numeraire_by_id("USD"), no_history
    )
    assert quoted == []
    assert error is not None and "汇率" in error


def test_missing_numeraire_history_reports_reason() -> None:
    bars = make_bars([100.0])
    quoted, error = quote_bars(
        bars, stock_meta(), numeraire_by_id("BRENT"), book()
    )
    assert quoted == []
    assert error is not None and "布伦特" in error


def test_yield_is_not_converted() -> None:
    meta = SeriesMeta(
        symbol="UST10Y",
        name="美债 10 年期",
        kind="yield",
        market="UST",
        currency="%",
        unit="%",
        chart="line",
        quotable=False,
    )
    bars = make_bars([4.2])
    quoted, error = quote_bars(bars, meta, numeraire_by_id("XAU"), book())
    assert error is None
    assert quoted[0].close == pytest.approx(4.2)


def test_numeric_series_roundtrip() -> None:
    series = NumericSeries((date(2026, 1, 5),), (3.0,))
    assert series.values[0] == 3.0
