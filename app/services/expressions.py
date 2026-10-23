"""Custom index expressions: validation, persistence, evaluation, charts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain.expression import (
    ExpressionError,
    Node,
    evaluate,
    parse,
    references,
)
from ..domain.expression import (
    validate as validate_syntax,
)
from ..domain.models import Bar, NumericSeries, StoredCustomIndex
from ..domain.stats import lttb_indices, percentile_of_last, rolling_percentile
from ..repositories.indices import NameTaken
from .chart import RANGES, _range_start
from .errors import BadRequest, DataUnavailable, NotFound

_NAME_RE = re.compile(r"^[^\s()+\-*/^,@]+$")
MAX_DEPTH = 3


@dataclass(frozen=True, slots=True)
class ResolvedExpression:
    series: NumericSeries
    references: tuple[dict[str, str], ...]
    basis: str


class ExpressionService:
    def __init__(self, services) -> None:
        self.s = services

    # -- persistence ---------------------------------------------------

    def list(self) -> list[StoredCustomIndex]:
        return self.s.indices.list()

    def create(self, name: str, expression: str) -> StoredCustomIndex:
        clean_name = name.strip()
        if not 1 <= len(clean_name) <= 40 or not _NAME_RE.match(clean_name):
            raise BadRequest("名称需为 1-40 个字符，且不能包含空格或运算符")
        if len(expression) > 512:
            raise BadRequest("表达式过长")
        self.validate(expression)
        try:
            record = self.s.indices.create(clean_name, expression)
        except NameTaken as error:
            raise BadRequest("名称已存在") from error
        self.s.app.expression_cache.clear()
        return record

    def delete(self, index_id: int) -> None:
        if not self.s.indices.delete(index_id):
            raise NotFound("自定义指数不存在")
        self.s.app.expression_cache.clear()

    def get(self, index_id: int) -> StoredCustomIndex:
        record = self.s.indices.get(index_id)
        if record is None:
            raise NotFound("自定义指数不存在")
        return record

    # -- validation ----------------------------------------------------

    def validate(self, expression: str) -> dict:
        try:
            node = parse(expression)
            refs = validate_syntax(expression)
        except ExpressionError as error:
            raise BadRequest(str(error)) from error
        if not refs:
            raise BadRequest("表达式至少需要引用一个标的")
        resolved = self._resolve(node, ())
        preview = [
            {"time": day.isoformat(), "value": value}
            for day, value in list(zip(resolved.series.dates, resolved.series.values))[-60:]
        ]
        return {
            "ok": True,
            "expression": expression,
            "basis": resolved.basis,
            "references": list(resolved.references),
            "last": resolved.series.values[-1] if resolved.series.values else None,
            "preview": preview,
        }

    # -- charts --------------------------------------------------------

    def chart(
        self,
        index_id: int,
        *,
        range_key: str = "1y",
        window: int = 60,
    ) -> dict:
        if range_key not in RANGES:
            raise BadRequest("range 不合法")
        if not 10 <= window <= 500:
            raise BadRequest("分位窗口需在 10 到 500 之间")
        record = self.get(index_id)
        cache_key = ("custom", record.id, range_key, window)
        cached = self.s.app.expression_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            node = parse(record.expression)
            resolved = self._resolve(node, (record.name,))
        except ExpressionError as error:
            raise BadRequest(str(error)) from error
        if not resolved.series.values:
            raise DataUnavailable("表达式没有可用数据")
        bars = [
            Bar(date=day, open=value, high=value, low=value, close=value)
            for day, value in zip(resolved.series.dates, resolved.series.values)
        ]
        percentiles = rolling_percentile(resolved.series.values, window)
        start_index = _range_start(bars, range_key)
        window_bars = bars[start_index:]
        values = resolved.series.values[start_index:]
        selected = lttb_indices(values, 320)
        sampled = [window_bars[index] for index in selected]
        percentile_values = [percentiles[start_index + index] for index in selected]
        first = values[0]
        last = values[-1]
        current_percentile = percentile_of_last(resolved.series.values, window)
        window_values = resolved.series.values[-window:]
        history_percentile = percentile_of_last(
            resolved.series.values, len(resolved.series.values)
        )
        payload = {
            "meta": {
                "id": record.id,
                "name": record.name,
                "expression": record.expression,
                "unit": "%" if resolved.basis == "%" else "比值",
                "basis": resolved.basis,
                "range": range_key,
                "window": window,
                "source": "expression",
                "chart": "line",
                "quotable": False,
            },
            "bars": [
                {
                    "time": bar.date.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                }
                for bar in sampled
            ],
            "percentile": percentile_values,
            "stats": {
                "first": first,
                "last": last,
                "change_pct": (last / first - 1) * 100 if first else 0.0,
                "high": max(values),
                "low": min(values),
                "percentile": current_percentile,
                "window_low": last <= min(window_values),
                "window_high": last >= max(window_values),
                "history_percentile": history_percentile,
                "points": len(values),
            },
            "references": list(resolved.references),
        }
        self.s.app.expression_cache.set(cache_key, payload, 10.0)
        return payload

    # -- evaluation ----------------------------------------------------

    def series(self, record: StoredCustomIndex) -> tuple[NumericSeries, str]:
        node = parse(record.expression)
        resolved = self._resolve(node, (record.name,))
        return resolved.series, resolved.basis

    def _resolve(
        self, node: Node, stack: tuple[str, ...]
    ) -> ResolvedExpression:
        if len(stack) > MAX_DEPTH:
            raise BadRequest("自定义指数嵌套超过 3 层")
        refs = references(node)
        if not refs:
            raise BadRequest("表达式至少需要引用一个标的")
        cache: dict[tuple[str, bool], NumericSeries] = {}
        info: dict[str, dict[str, str]] = {}
        kinds: set[str] = set()
        for ref in refs:
            key = (ref.symbol, ref.custom)
            if key in cache:
                continue
            if ref.custom:
                if ref.symbol in stack:
                    raise BadRequest(f"检测到循环引用: @{ref.symbol}")
                record = self.s.indices.get_by_name(ref.symbol)
                if record is None:
                    raise BadRequest(f"找不到自定义指数 @{ref.symbol}")
                resolved = self._resolve(parse(record.expression), stack + (record.name,))
                cache[key] = resolved.series
                info[f"@{ref.symbol}"] = {
                    "symbol": f"@{ref.symbol}",
                    "name": record.name,
                    "kind": "custom",
                    "expression": record.expression,
                }
                kinds.add("yield" if resolved.basis == "%" else "price")
                continue
            meta = self.s.market.meta(ref.symbol)
            _meta, bars, _source = self.s.market.daily(meta.symbol)
            kinds.add("yield" if meta.kind == "yield" else "price")
            closes = NumericSeries(
                tuple(bar.date for bar in bars), tuple(bar.close for bar in bars)
            )
            cache[key] = closes
            info[meta.symbol] = {
                "symbol": meta.symbol,
                "name": meta.name,
                "kind": meta.kind,
            }
        if "yield" in kinds and "price" in kinds:
            raise BadRequest("收益率序列不能与价格序列混用")
        basis = "%" if kinds == {"yield"} else "native"
        series = evaluate(node, lambda symbol, custom: cache[(symbol, custom)])
        return ResolvedExpression(series, tuple(info.values()), basis)

