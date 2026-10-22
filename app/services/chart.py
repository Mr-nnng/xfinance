"""Chart assembly: convert, normalize, compute indicators, downsample."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta

from ..domain.catalog import (
    COMMODITY_SERIES,
    FX_SERIES,
    Numeraire,
    numeraire_by_id,
    series_meta,
)
from ..domain.indicators import bollinger, kdj, macd, rsi, sma
from ..domain.models import Bar, SeriesMeta
from ..domain.pricing import AsofSeries, FactorBook, quote_bars
from ..domain.stats import downsample_bars
from .errors import BadRequest, DataUnavailable

RANGES: dict[str, int | None] = {
    "1m": 31,
    "3m": 92,
    "6m": 183,
    "1y": 366,
    "3y": 1096,
    "5y": 1830,
    "max": None,
}
DEFAULT_INDICATORS = "ma:20,ma:60,boll:20"
MAX_POINTS = 320


class ChartService:
    def __init__(self, services) -> None:
        self.s = services

    # -- public --------------------------------------------------------

    def chart(
        self,
        raw_symbol: str,
        *,
        timeframe: str = "1d",
        adjust: str = "none",
        numeraire_id: str = "CNY",
        normalize: bool = False,
        range_key: str = "1y",
        indicators: str = DEFAULT_INDICATORS,
    ) -> dict:
        if timeframe not in {"1d", "1w", "1m"}:
            raise BadRequest("timeframe 只能是 1d / 1w / 1m")
        if adjust not in {"none", "qfq", "hfq"}:
            raise BadRequest("adjust 只能是 none / qfq / hfq")
        if range_key not in RANGES:
            raise BadRequest("range 不合法")
        spec = parse_indicator_spec(indicators)
        meta, native_bars, source = self.s.market.bars(
            raw_symbol, timeframe, adjust  # type: ignore[arg-type]
        )
        numeraire = numeraire_by_id(numeraire_id)
        base_bars, quote_error = self._quote(meta, native_bars, numeraire)
        if quote_error and meta.quotable:
            base_bars = list(native_bars)
        start_index = _range_start(base_bars, range_key)
        if normalize and meta.quotable and not quote_error:
            base = base_bars[start_index].close
            if base > 0:
                base_bars = [
                    Bar(
                        date=bar.date,
                        open=bar.open / base,
                        high=bar.high / base,
                        low=bar.low / base,
                        close=bar.close / base,
                        volume=bar.volume,
                        amount=bar.amount,
                    )
                    for bar in base_bars
                ]
        full_indicators = _compute_indicators(base_bars, spec)
        window_bars = base_bars[start_index:]
        if not window_bars:
            raise DataUnavailable("所选区间没有数据")
        sampled, local_indices = downsample_bars(window_bars, MAX_POINTS)
        indicators_payload = _slice_indicators(full_indicators, start_index, local_indices)
        window_first = window_bars[0].close
        window_last = window_bars[-1].close
        stats = {
            "first": window_first,
            "last": window_last,
            "change_pct": (window_last / window_first - 1) * 100 if window_first else 0.0,
            "high": max(bar.high for bar in window_bars),
            "low": min(bar.low for bar in window_bars),
            "points": len(window_bars),
            "native_last": native_bars[-1].close,
        }
        return {
            "meta": {
                "symbol": meta.symbol,
                "name": meta.name,
                "kind": meta.kind,
                "market": meta.market,
                "currency": meta.currency,
                "unit": meta.unit,
                "chart": meta.chart,
                "quotable": meta.quotable,
                "source": source,
                "timeframe": timeframe,
                "adjust": adjust,
                "range": range_key,
                "normalized": bool(normalize and meta.quotable and not quote_error),
                "quoted": meta.quotable and not quote_error,
                "quote_error": quote_error,
                "numeraire": {
                    "id": numeraire.id,
                    "label": numeraire.label,
                    "unit": numeraire.unit,
                    "group": numeraire.group,
                },
            },
            "bars": [
                {
                    "time": bar.date.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
                for bar in sampled
            ],
            "volume": [bar.volume for bar in sampled],
            "indicators": indicators_payload,
            "stats": stats,
        }

    def quoted_bars(
        self,
        meta: SeriesMeta,
        bars: list[Bar],
        numeraire_id: str,
    ) -> tuple[list[Bar], str | None, Numeraire]:
        numeraire = numeraire_by_id(numeraire_id)
        if not meta.quotable:
            return list(bars), None, numeraire
        converted, error = self._quote(meta, bars, numeraire)
        return (converted if converted else list(bars)), error, numeraire

    def _quote(
        self, meta: SeriesMeta, bars: list[Bar], numeraire: Numeraire
    ) -> tuple[list[Bar], str | None]:
        if not meta.quotable:
            return list(bars), None
        book, book_error = self._factor_book(meta, numeraire)
        if book is None:
            return [], book_error
        return quote_bars(bars, meta, numeraire, book)

    def _factor_book(
        self, meta: SeriesMeta, numeraire: Numeraire
    ) -> tuple[FactorBook | None, str | None]:
        needed: set[str] = set()
        if meta.currency != "USD":
            needed.add(f"USD{meta.currency}")
        if numeraire.kind == "fiat" and numeraire.series:
            needed.add(numeraire.series)
        if numeraire.kind == "asset" and numeraire.series:
            needed.add(numeraire.series)
            asset_meta = series_meta(numeraire.series)
            if asset_meta and asset_meta.currency != "USD":
                needed.add(f"USD{asset_meta.currency}")
        usd_per_currency: dict[str, AsofSeries] = {}
        asset_values: dict[str, tuple[AsofSeries, str]] = {}
        for symbol in needed:
            if symbol not in FX_SERIES and symbol not in COMMODITY_SERIES:
                return None, f"缺少 {symbol} 的计价序列"
            try:
                bars, _source = self.s.sync.ensure_series(symbol)
            except Exception as error:
                return None, str(error)
            if symbol in FX_SERIES:
                currency = FX_SERIES[symbol][1]
                usd_per_currency[currency] = AsofSeries.from_pairs(
                    {bar.date: 1.0 / bar.close for bar in bars if bar.close > 0}
                )
            else:
                commodity_meta = series_meta(symbol)
                if commodity_meta:
                    asset_values[symbol] = (
                        AsofSeries.from_bars(bars),
                        commodity_meta.currency,
                    )
        return FactorBook(usd_per_currency=usd_per_currency, asset_values=asset_values), None


def parse_indicator_spec(spec: str) -> dict[str, object]:
    parsed: dict[str, object] = {"ma": [], "boll": [], "macd": False, "rsi": [], "kdj": False}
    items = [item.strip() for item in spec.split(",") if item.strip()]
    for item in items:
        name, _, argument = item.partition(":")
        name = name.lower()
        if name in {"vol", "volume"}:
            continue
        if name == "ma":
            period = _period(argument, 20)
            if len(parsed["ma"]) >= 4:  # type: ignore[arg-type]
                raise BadRequest("MA 最多 4 条")
            parsed["ma"].append(period)  # type: ignore[union-attr]
        elif name == "boll":
            parsed["boll"] = [_period(argument, 20)]
        elif name == "macd":
            parsed["macd"] = True
        elif name == "rsi":
            parsed["rsi"] = [_period(argument, 14)]
        elif name == "kdj":
            parsed["kdj"] = True
        else:
            raise BadRequest(f"未知指标: {name}")
    return parsed


def _period(argument: str, default: int) -> int:
    if not argument:
        return default
    try:
        value = int(argument)
    except ValueError as error:
        raise BadRequest("指标周期必须是整数") from error
    if not 2 <= value <= 250:
        raise BadRequest("指标周期需在 2 到 250 之间")
    return value


def _range_start(bars: list[Bar], range_key: str) -> int:
    days = RANGES[range_key]
    if days is None or not bars:
        return 0
    cutoff = bars[-1].date - timedelta(days=days)
    for index, bar in enumerate(bars):
        if bar.date >= cutoff:
            return index
    return 0


def _compute_indicators(bars: list[Bar], spec: Mapping[str, object]) -> dict:
    closes = [bar.close for bar in bars]
    result: dict[str, object] = {}
    ma_periods = spec.get("ma") or []
    if ma_periods:
        result["ma"] = [
            {"period": period, "values": sma(closes, period)} for period in ma_periods
        ]
    boll_periods = spec.get("boll") or []
    if boll_periods:
        period = boll_periods[0]  # type: ignore[index]
        bands = bollinger(closes, period)
        result["boll"] = {"period": period, **bands}
    if spec.get("macd"):
        result["macd"] = macd(closes)
    rsi_periods = spec.get("rsi") or []
    if rsi_periods:
        period = rsi_periods[0]  # type: ignore[index]
        result["rsi"] = {"period": period, "values": rsi(closes, period)}
    if spec.get("kdj"):
        result["kdj"] = kdj(
            [bar.high for bar in bars], [bar.low for bar in bars], closes
        )
    return result


def _slice_indicators(
    indicators: dict, start_index: int, local_indices: list[int]
) -> dict:
    output: dict[str, object] = {}
    for name, value in indicators.items():
        if name == "ma":
            output["ma"] = [
                {
                    "period": item["period"],
                    "values": [item["values"][start_index + index] for index in local_indices],
                }
                for item in value
            ]
        elif name == "boll":
            output["boll"] = {
                "period": value["period"],
                **{
                    key: [value[key][start_index + index] for index in local_indices]
                    for key in ("mid", "upper", "lower")
                },
            }
        elif name == "macd":
            output["macd"] = {
                key: [value[key][start_index + index] for index in local_indices]
                for key in ("dif", "dea", "hist")
            }
        elif name == "rsi":
            output["rsi"] = {
                "period": value["period"],
                "values": [value["values"][start_index + index] for index in local_indices],
            }
        elif name == "kdj":
            output["kdj"] = {
                key: [value[key][start_index + index] for index in local_indices]
                for key in ("k", "d", "j")
            }
    return output
