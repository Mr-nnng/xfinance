from __future__ import annotations

import math

import pytest

from app.domain.indicators import bollinger, ema, kdj, macd, rsi, sma


def test_sma_warmup_and_values() -> None:
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_sma_rejects_bad_period() -> None:
    with pytest.raises(ValueError):
        sma([1], 0)


def test_ema_seeds_with_first_value() -> None:
    values = ema([10, 10, 10], 5)
    assert values == [10.0, 10.0, 10.0]
    rising = ema([1, 2, 3], 3)
    assert rising[2] is not None and rising[2] > rising[1] > rising[0]


def test_bollinger_bands_bracket_middle() -> None:
    values = bollinger([1, 2, 3, 4, 5], period=3, mult=2)
    for mid, upper, lower in zip(
        values["mid"], values["upper"], values["lower"]
    ):
        if mid is None:
            assert upper is None and lower is None
        else:
            assert upper > mid > lower
            assert upper - mid == pytest.approx(mid - lower)


def test_macd_histogram_relationship() -> None:
    values = [float(item) for item in range(1, 60)]
    result = macd(values)
    for dif, dea, hist in zip(result["dif"], result["dea"], result["hist"]):
        assert hist == pytest.approx((dif - dea) * 2)


def test_rsi_extremes() -> None:
    rising = [float(item) for item in range(1, 40)]
    falling = list(reversed(rising))
    assert rsi(rising, 14)[-1] == pytest.approx(100.0)
    assert rsi(falling, 14)[-1] == pytest.approx(0.0)


def test_rsi_flat_series_is_neutral() -> None:
    assert rsi([5.0] * 40, 14)[-1] == pytest.approx(50.0)


def test_kdj_warmup_and_bounds() -> None:
    closes = [float(item) for item in range(1, 40)]
    highs = [item + 1 for item in closes]
    lows = [item - 1 for item in closes]
    result = kdj(highs, lows, closes, 9)
    assert result["k"][7] is None
    assert result["k"][8] is not None
    for value in result["j"][9:]:
        assert math.isfinite(value)
