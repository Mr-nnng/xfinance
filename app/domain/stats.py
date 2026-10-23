"""Statistics, backtests, and chart downsampling. Pure functions only."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from .models import Bar, NumericSeries


@dataclass(frozen=True, slots=True)
class Purchase:
    date: date
    price: float
    amount: float
    units: float


@dataclass(frozen=True, slots=True)
class DcaPoint:
    date: date
    invested: float
    value: float
    units: float
    price: float


@dataclass(frozen=True, slots=True)
class DcaResult:
    purchases: tuple[Purchase, ...]
    points: tuple[DcaPoint, ...]
    invested: float
    final_value: float
    profit: float
    return_pct: float
    xirr: float | None
    max_drawdown: float


@dataclass(frozen=True, slots=True)
class CompoundPoint:
    year: int
    contributions: float
    value: float
    interest: float


@dataclass(frozen=True, slots=True)
class CompoundResult:
    final_value: float
    contributions: float
    interest: float
    points: tuple[CompoundPoint, ...]


def returns(values: Sequence[float]) -> list[float]:
    return [
        values[index] / values[index - 1] - 1.0
        for index in range(1, len(values))
        if values[index - 1] > 0
    ]


def correlation_matrix(
    series: Mapping[str, NumericSeries], window: int | None = None
) -> dict[str, dict[str, float]]:
    names = list(series)
    if window is not None and window > 1:
        series = {
            name: NumericSeries(value.dates[-window:], value.values[-window:])
            for name, value in series.items()
        }
    common = _common_dates(series)
    aligned = {
        name: [value for day, value in zip(value.dates, value.values) if day in common]
        for name, value in series.items()
    }
    return_series = {name: returns(values) for name, values in aligned.items()}
    result: dict[str, dict[str, float]] = {}
    for left in names:
        row: dict[str, float] = {}
        for right in names:
            row[right] = _pearson(return_series[left], return_series[right])
        result[left] = row
    return result


def _common_dates(series: Mapping[str, NumericSeries]) -> set[date]:
    sets = [set(value.dates) for value in series.values()]
    if not sets:
        return set()
    common = sets[0]
    for item in sets[1:]:
        common &= item
    return common


def _pearson(left: Sequence[float], right: Sequence[float]) -> float:
    count = min(len(left), len(right))
    if count < 2:
        return 0.0
    left_values = left[-count:]
    right_values = right[-count:]
    left_mean = sum(left_values) / count
    right_mean = sum(right_values) / count
    covariance = sum(
        (a - left_mean) * (b - right_mean)
        for a, b in zip(left_values, right_values)
    )
    left_var = sum((a - left_mean) ** 2 for a in left_values)
    right_var = sum((b - right_mean) ** 2 for b in right_values)
    denominator = math.sqrt(left_var * right_var)
    if denominator == 0:
        return 0.0
    return covariance / denominator


def dca_backtest(
    bars: Sequence[Bar],
    *,
    start: date,
    amount: float,
    day: int = 1,
    fee_pct: float = 0.0,
) -> DcaResult:
    if amount <= 0:
        raise ValueError("amount must be positive")
    if not 1 <= day <= 28:
        raise ValueError("day must be between 1 and 28")
    fee = max(fee_pct, 0.0) / 100.0
    window = [bar for bar in bars if bar.date >= start]
    if not window:
        return DcaResult((), (), 0.0, 0.0, 0.0, 0.0, None, 0.0)

    purchases: list[Purchase] = []
    scheduled: list[date] = []
    cursor = date(window[0].date.year, window[0].date.month, 1)
    last_month = date(window[-1].date.year, window[-1].date.month, 1)
    while cursor <= last_month:
        scheduled.append(cursor.replace(day=day))
        cursor = _next_month(cursor)

    consumed: set[date] = set()
    for target in scheduled:
        for bar in window:
            if bar.date >= target and bar.date not in consumed:
                net = amount * (1.0 - fee)
                units = net / bar.close if bar.close > 0 else 0.0
                if units > 0:
                    purchases.append(Purchase(bar.date, bar.close, amount, units))
                    consumed.add(bar.date)
                break

    units = 0.0
    invested = 0.0
    points: list[DcaPoint] = []
    for bar in window:
        for purchase in purchases:
            if purchase.date == bar.date:
                units += purchase.units
                invested += purchase.amount
        if units > 0:
            points.append(
                DcaPoint(
                    date=bar.date,
                    invested=invested,
                    value=units * bar.close,
                    units=units,
                    price=bar.close,
                )
            )

    final_value = units * window[-1].close
    profit = final_value - invested
    return_pct = (profit / invested * 100.0) if invested else 0.0
    cashflows = [(-purchase.amount, purchase.date) for purchase in purchases]
    cashflows.append((final_value, window[-1].date))
    rate = xirr(cashflows) if len(cashflows) > 1 and final_value > 0 else None
    peak = 0.0
    drawdown = 0.0
    for bar in window:
        peak = max(peak, bar.close)
        if peak > 0:
            drawdown = max(drawdown, (peak - bar.close) / peak)
    return DcaResult(
        purchases=tuple(purchases),
        points=tuple(points),
        invested=invested,
        final_value=final_value,
        profit=profit,
        return_pct=return_pct,
        xirr=rate,
        max_drawdown=drawdown * 100.0,
    )


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def xirr(cashflows: Sequence[tuple[float, date]], guess: float = 0.1) -> float | None:
    if len(cashflows) < 2:
        return None
    base = min(day for _, day in cashflows)

    def npv(rate: float) -> float:
        return sum(
            amount / (1.0 + rate) ** ((day - base).days / 365.0)
            for amount, day in cashflows
        )

    low, high = -0.9999, 10.0
    low_value, high_value = npv(low), npv(high)
    if low_value * high_value > 0:
        return None
    rate = guess
    for _ in range(200):
        value = npv(rate)
        if abs(value) < 1e-7:
            return rate
        if value * npv(low) > 0:
            low = rate
        else:
            high = rate
        rate = (low + high) / 2.0
        if abs(high - low) < 1e-9:
            break
    return rate


def compound(
    principal: float, monthly: float, annual_rate_pct: float, years: int
) -> CompoundResult:
    if years <= 0:
        raise ValueError("years must be positive")
    monthly_rate = annual_rate_pct / 100.0 / 12.0
    value = max(principal, 0.0)
    contributions = max(principal, 0.0)
    points: list[CompoundPoint] = []
    for month in range(1, years * 12 + 1):
        value += max(monthly, 0.0)
        contributions += max(monthly, 0.0)
        value *= 1.0 + monthly_rate
        if month % 12 == 0:
            points.append(
                CompoundPoint(month // 12, contributions, value, value - contributions)
            )
    return CompoundResult(
        final_value=value,
        contributions=contributions,
        interest=value - contributions,
        points=tuple(points),
    )


def rolling_percentile(
    values: Sequence[float], window: int
) -> list[float | None]:
    if window <= 1:
        raise ValueError("window must be greater than 1")
    out: list[float | None] = [None] * len(values)
    for index in range(len(values)):
        start = max(0, index - window + 1)
        sample = values[start : index + 1]
        if len(sample) < 2:
            continue
        out[index] = _rank_percentile(sample)
    return out


def percentile_of_last(values: Sequence[float], window: int) -> float | None:
    if len(values) < 2:
        return None
    sample = list(values[-window:]) if window > 1 else list(values)
    return _rank_percentile(sample)


def _rank_percentile(sample: Sequence[float]) -> float:
    """Mean-rank percentile with the current sample included.

    A valid observation never gets exactly 0. The minimum is about 1/(2n)%
    and the maximum is just below 100%, so 0 can stay reserved for missing data.
    """
    current = sample[-1]
    below = sum(1 for item in sample if item < current)
    equal = sum(1 for item in sample if item == current)
    if len(sample) < 2:
        return 50.0
    return (below + 0.5 * equal) / len(sample) * 100.0


def bucket_end_indices(length: int, target: int) -> list[int]:
    """Index of the last sample in each time bucket, about `target` buckets."""
    if target <= 0:
        raise ValueError("target must be positive")
    if length <= target:
        return list(range(length))
    size = math.ceil(length / target)
    return [min(start + size - 1, length - 1) for start in range(0, length, size)]


def downsample_bars(bars: Sequence[Bar], target: int = 320) -> tuple[list[Bar], list[int]]:
    indices = bucket_end_indices(len(bars), target)
    if len(indices) == len(bars):
        return list(bars), indices
    output: list[Bar] = []
    start = 0
    for end in indices:
        chunk = bars[start : end + 1]
        output.append(
            Bar(
                date=chunk[-1].date,
                open=chunk[0].open,
                high=max(item.high for item in chunk),
                low=min(item.low for item in chunk),
                close=chunk[-1].close,
                volume=sum(item.volume for item in chunk),
                amount=sum(item.amount for item in chunk),
            )
        )
        start = end + 1
    return output, indices


def lttb_indices(values: Sequence[float], threshold: int) -> list[int]:
    """Largest-triangle-three-buckets sampling; returns kept indices."""
    length = len(values)
    if threshold >= length or threshold <= 2:
        return list(range(length))
    sampled = [0]
    every = (length - 2) / (threshold - 2)
    anchor = 0
    for bucket in range(threshold - 2):
        average_start = math.floor((bucket + 1) * every) + 1
        average_end = math.floor((bucket + 2) * every) + 1
        average_end = min(average_end, length)
        average_x = (average_start + average_end - 1) / 2.0
        sample = values[average_start:average_end]
        average_y = sum(sample) / len(sample) if sample else values[-1]

        range_start = math.floor(bucket * every) + 1
        range_end = math.floor((bucket + 1) * every) + 1
        range_end = max(range_end, range_start + 1)
        anchor_x = float(anchor)
        anchor_y = values[anchor]
        max_area = -1.0
        chosen = range_start
        for index in range(range_start, range_end):
            area = abs(
                (anchor_x - average_x) * (values[index] - anchor_y)
                - (anchor_x - index) * (average_y - anchor_y)
            )
            if area > max_area:
                max_area = area
                chosen = index
        sampled.append(chosen)
        anchor = chosen
    sampled.append(length - 1)
    return sampled
