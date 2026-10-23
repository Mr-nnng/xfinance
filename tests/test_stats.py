from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.models import Bar, NumericSeries
from app.domain.stats import (
    bucket_end_indices,
    compound,
    correlation_matrix,
    dca_backtest,
    downsample_bars,
    lttb_indices,
    percentile_of_last,
    returns,
    rolling_percentile,
    xirr,
)


def bars_for(prices: dict[date, float]) -> list[Bar]:
    return [
        Bar(day, price, price, price, price, 1000, price * 1000)
        for day, price in sorted(prices.items())
    ]


def test_returns_are_simple_returns() -> None:
    assert returns([100, 110, 99]) == pytest.approx([0.1, -0.1])


def prices_from_returns(start: float, moves: list[float]) -> tuple[float, ...]:
    prices = [start]
    for move in moves:
        prices.append(prices[-1] * (1 + move))
    return tuple(prices)


def test_correlation_perfect_and_inverse() -> None:
    dates = tuple(date(2026, 1, day) for day in range(1, 7))
    moves = [0.01, 0.02, -0.01, 0.03, 0.01]
    opposite = [-move for move in moves]
    up = NumericSeries(dates, prices_from_returns(100, moves))
    down = NumericSeries(dates, prices_from_returns(100, opposite))
    flat = NumericSeries(dates, (3, 3, 3, 3, 3, 3))
    matrix = correlation_matrix({"up": up, "down": down, "flat": flat})
    assert matrix["up"]["up"] == pytest.approx(1.0)
    assert matrix["up"]["down"] == pytest.approx(-1.0)
    assert matrix["up"]["flat"] == pytest.approx(0.0)


def test_correlation_uses_common_dates() -> None:
    left = NumericSeries(
        (date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4)),
        (1.0, 2.0, 4.0, 7.0),
    )
    right = NumericSeries(
        (date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 4), date(2026, 1, 5)),
        (2.0, 4.0, 7.0, 12.0),
    )
    matrix = correlation_matrix({"a": left, "b": right})
    assert matrix["a"]["b"] == pytest.approx(1.0)


def test_dca_buys_monthly_and_values_every_day() -> None:
    days = [
        date(2026, 1, 1),
        date(2026, 2, 2),
        date(2026, 3, 2),
        date(2026, 4, 1),
        date(2026, 4, 30),
    ]
    prices = dict(zip(days, [10.0, 20.0, 10.0, 20.0, 20.0]))
    result = dca_backtest(
        bars_for(prices), start=date(2026, 1, 1), amount=100, day=1
    )
    assert len(result.purchases) == 4
    assert result.invested == pytest.approx(400)
    assert result.final_value == pytest.approx(600)
    assert result.return_pct == pytest.approx(50)
    assert result.xirr is not None and result.xirr > 0


def test_dca_with_fee_reduces_units() -> None:
    bars = bars_for({date(2026, 1, 1): 10.0, date(2026, 1, 30): 10.0})
    result = dca_backtest(
        bars, start=date(2026, 1, 1), amount=100, day=1, fee_pct=1.0
    )
    assert result.purchases[0].units == pytest.approx(9.9)
    assert result.final_value == pytest.approx(99.0)


def test_dca_start_after_data_is_empty() -> None:
    bars = bars_for({date(2026, 1, 1): 10.0})
    result = dca_backtest(bars, start=date(2027, 1, 1), amount=100)
    assert result.invested == 0
    assert result.points == ()


def test_xirr_one_year_ten_percent() -> None:
    cashflows = [(-100.0, date(2025, 1, 1)), (110.0, date(2026, 1, 1))]
    rate = xirr(cashflows)
    assert rate == pytest.approx(0.1, abs=1e-3)


def test_compound_monthly_contributions() -> None:
    result = compound(1000, 100, 12, 1)
    assert result.contributions == pytest.approx(2200)
    assert result.final_value > result.contributions
    assert result.points[-1].interest == pytest.approx(
        result.final_value - result.contributions
    )


def test_compound_rejects_zero_years() -> None:
    with pytest.raises(ValueError):
        compound(1000, 0, 5, 0)


def test_rolling_percentile() -> None:
    values = [1.0, 2.0, 3.0, 0.0]
    result = rolling_percentile(values, 3)
    assert result[0] is None
    assert result[1] == pytest.approx(75.0)
    assert result[2] == pytest.approx(250.0 / 3.0)
    assert result[3] == pytest.approx(100.0 / 6.0)
    assert percentile_of_last(values, 3) == pytest.approx(100.0 / 6.0)


def test_bucket_indices_cover_every_sample() -> None:
    indices = bucket_end_indices(1000, 300)
    assert indices[0] == 3
    assert indices[-1] == 999
    assert len(indices) <= 300


def test_downsample_preserves_ohlc_shape() -> None:
    bars = [
        Bar(
            date(2026, 1, 1) + timedelta(days=index),
            10 + index,
            12 + index,
            9 + index,
            11 + index,
            10,
            100,
        )
        for index in range(1000)
    ]
    sampled, indices = downsample_bars(bars, 100)
    assert len(sampled) == len(indices) <= 100
    assert sampled[0].open == bars[0].open
    assert sampled[-1].close == bars[-1].close
    assert sampled[0].high == max(bar.high for bar in bars[: indices[0] + 1])


def test_lttb_keeps_endpoints() -> None:
    values = [float(index) for index in range(500)]
    kept = lttb_indices(values, 50)
    assert kept[0] == 0 and kept[-1] == 499
    assert len(kept) == 50
    assert kept == sorted(kept)
