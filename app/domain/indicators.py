"""Technical indicators. Pure functions over closes/highs/lows."""

from __future__ import annotations

import math
from collections.abc import Sequence

Number = float | None


def sma(values: Sequence[float], period: int) -> list[Number]:
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[Number] = [None] * len(values)
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= period:
            total -= values[index - period]
        if index >= period - 1:
            out[index] = total / period
    return out


def ema(values: Sequence[float], period: int) -> list[Number]:
    if period <= 0:
        raise ValueError("period must be positive")
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    out: list[Number] = [values[0]]
    previous = values[0]
    for value in values[1:]:
        previous = alpha * value + (1 - alpha) * previous
        out.append(previous)
    return out


def rolling_std(values: Sequence[float], period: int) -> list[Number]:
    if period <= 0:
        raise ValueError("period must be positive")
    out: list[Number] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = values[index - period + 1 : index + 1]
        mean = sum(window) / period
        variance = sum((item - mean) ** 2 for item in window) / period
        out[index] = math.sqrt(variance)
    return out


def bollinger(
    values: Sequence[float], period: int = 20, mult: float = 2.0
) -> dict[str, list[Number]]:
    middle = sma(values, period)
    deviation = rolling_std(values, period)
    upper: list[Number] = []
    lower: list[Number] = []
    for mid, dev in zip(middle, deviation):
        if mid is None or dev is None:
            upper.append(None)
            lower.append(None)
        else:
            upper.append(mid + mult * dev)
            lower.append(mid - mult * dev)
    return {"mid": middle, "upper": upper, "lower": lower}


def macd(
    values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, list[Number]]:
    fast_line = ema(values, fast)
    slow_line = ema(values, slow)
    dif = [
        (a - b) if a is not None and b is not None else None
        for a, b in zip(fast_line, slow_line)
    ]
    dif_values = [item if item is not None else 0.0 for item in dif]
    dea = ema(dif_values, signal)
    hist = [
        ((d - e) * 2.0) if d is not None and e is not None else None
        for d, e in zip(dif, dea)
    ]
    return {"dif": dif, "dea": dea, "hist": hist}


def rsi(values: Sequence[float], period: int = 14) -> list[Number]:
    out: list[Number] = [None] * len(values)
    if len(values) <= period:
        return out
    gains = 0.0
    losses = 0.0
    for index in range(1, period + 1):
        change = values[index] - values[index - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    average_gain = gains / period
    average_loss = losses / period
    out[period] = _rsi_value(average_gain, average_loss)
    for index in range(period + 1, len(values)):
        change = values[index] - values[index - 1]
        average_gain = (average_gain * (period - 1) + max(change, 0.0)) / period
        average_loss = (average_loss * (period - 1) + max(-change, 0.0)) / period
        out[index] = _rsi_value(average_gain, average_loss)
    return out


def _rsi_value(average_gain: float, average_loss: float) -> float:
    if average_loss == 0:
        return 100.0 if average_gain > 0 else 50.0
    rs = average_gain / average_loss
    return 100.0 - 100.0 / (1.0 + rs)


def kdj(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 9,
) -> dict[str, list[Number]]:
    length = len(closes)
    k_values: list[Number] = [None] * length
    d_values: list[Number] = [None] * length
    j_values: list[Number] = [None] * length
    previous_k = 50.0
    previous_d = 50.0
    for index in range(length):
        if index < period - 1:
            continue
        window_high = max(highs[index - period + 1 : index + 1])
        window_low = min(lows[index - period + 1 : index + 1])
        span = window_high - window_low
        rsv = 50.0 if span == 0 else (closes[index] - window_low) / span * 100.0
        current_k = (2.0 * previous_k + rsv) / 3.0
        current_d = (2.0 * previous_d + current_k) / 3.0
        current_j = 3.0 * current_k - 2.0 * current_d
        k_values[index] = current_k
        d_values[index] = current_d
        j_values[index] = current_j
        previous_k, previous_d = current_k, current_d
    return {"k": k_values, "d": d_values, "j": j_values}
