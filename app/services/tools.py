"""Financial tools: DCA backtest, correlation matrix, compound interest."""

from __future__ import annotations

from datetime import date, timedelta

from ..domain.catalog import numeraire_by_id
from ..domain.models import NumericSeries, SeriesMeta
from ..domain.stats import (
    bucket_end_indices,
    compound,
    correlation_matrix,
    dca_backtest,
)
from .errors import BadRequest, DataUnavailable


class ToolsService:
    def __init__(self, services) -> None:
        self.s = services

    def dca(
        self,
        raw_symbol: str,
        *,
        start: date | None,
        amount: float,
        day: int,
        fee_pct: float,
        numeraire_id: str,
    ) -> dict:
        if amount <= 0:
            raise BadRequest("每期金额必须大于 0")
        if not 1 <= day <= 28:
            raise BadRequest("扣款日需在 1 到 28 之间")
        if not 0 <= fee_pct <= 5:
            raise BadRequest("费率需在 0 到 5 之间")
        meta, bars, source = self.s.market.daily(raw_symbol)
        if not meta.quotable:
            raise BadRequest("收益率序列不支持定投回测")
        numeraire = numeraire_by_id(numeraire_id)
        converted, error, numeraire = self.s.chart.quoted_bars(meta, bars, numeraire_id)
        if error:
            raise DataUnavailable(error)
        if start is None:
            start = converted[-1].date - timedelta(days=365 * 3)
        result = dca_backtest(
            converted, start=start, amount=amount, day=day, fee_pct=fee_pct
        )
        indices = bucket_end_indices(len(result.points), 320)
        points = [result.points[index] for index in indices]
        return {
            "meta": _meta_dict(meta),
            "numeraire": _numeraire_dict(numeraire),
            "source": source,
            "plan": {
                "start": start.isoformat(),
                "amount": amount,
                "day": day,
                "fee_pct": fee_pct,
            },
            "metrics": {
                "invested": result.invested,
                "final_value": result.final_value,
                "profit": result.profit,
                "return_pct": result.return_pct,
                "xirr_pct": (result.xirr * 100) if result.xirr is not None else None,
                "max_drawdown_pct": result.max_drawdown,
                "purchases": len(result.purchases),
            },
            "points": [
                {
                    "time": point.date.isoformat(),
                    "invested": point.invested,
                    "value": point.value,
                }
                for point in points
            ],
            "purchases": [
                {
                    "time": item.date.isoformat(),
                    "price": item.price,
                    "amount": item.amount,
                    "units": item.units,
                }
                for item in result.purchases
            ],
        }

    def correlation(
        self,
        symbols: list[str],
        *,
        window: int,
        numeraire_id: str,
    ) -> dict:
        cleaned = list(dict.fromkeys(symbol.strip() for symbol in symbols if symbol.strip()))
        if not 2 <= len(cleaned) <= 8:
            raise BadRequest("相关系数需要 2 到 8 个标的")
        if not 30 <= window <= 750:
            raise BadRequest("窗口需在 30 到 750 个交易日之间")
        numeraire = numeraire_by_id(numeraire_id)
        series: dict[str, NumericSeries] = {}
        metas: dict[str, dict] = {}
        series_by_code: dict[str, dict[date, float]] = {}
        sources: set[str] = set()
        for raw in cleaned:
            meta, bars, source = self.s.market.daily(raw)
            if not meta.quotable:
                raise BadRequest("收益率序列不参与相关性计算")
            converted, error, _ = self.s.chart.quoted_bars(meta, bars, numeraire_id)
            if error:
                raise DataUnavailable(error)
            series_by_code[meta.symbol] = {bar.date: bar.close for bar in converted}
            metas[meta.symbol] = _meta_dict(meta)
            sources.add(source)
        common = set.intersection(*(set(values) for values in series_by_code.values()))
        ordered = sorted(common)[-window:]
        if len(ordered) < 30:
            raise BadRequest("共同交易日不足 30 天，无法计算相关性")
        for symbol, lookup in series_by_code.items():
            values = [lookup[day] for day in ordered]
            series[symbol] = NumericSeries(tuple(ordered), tuple(values))
        matrix = correlation_matrix(series)
        return {
            "symbols": [metas[symbol] for symbol in series],
            "matrix": matrix,
            "window": len(ordered),
            "numeraire": _numeraire_dict(numeraire),
            "sources": sorted(sources),
            "start": ordered[0].isoformat(),
            "end": ordered[-1].isoformat(),
        }

    def compound(
        self,
        *,
        principal: float,
        monthly: float,
        annual_rate_pct: float,
        years: int,
    ) -> dict:
        if principal < 0 or monthly < 0:
            raise BadRequest("本金与月供不能为负")
        if not 1 <= years <= 60:
            raise BadRequest("年数需在 1 到 60 之间")
        if not -99 <= annual_rate_pct <= 100:
            raise BadRequest("年化收益率需在 -99% 到 100% 之间")
        result = compound(principal, monthly, annual_rate_pct, years)
        return {
            "final_value": result.final_value,
            "contributions": result.contributions,
            "interest": result.interest,
            "points": [
                {
                    "year": point.year,
                    "contributions": point.contributions,
                    "value": point.value,
                    "interest": point.interest,
                }
                for point in result.points
            ],
        }


def _meta_dict(meta: SeriesMeta) -> dict:
    return {
        "symbol": meta.symbol,
        "name": meta.name,
        "kind": meta.kind,
        "currency": meta.currency,
        "unit": meta.unit,
    }


def _numeraire_dict(numeraire) -> dict:
    return {
        "id": numeraire.id,
        "label": numeraire.label,
        "unit": numeraire.unit,
        "group": numeraire.group,
    }
