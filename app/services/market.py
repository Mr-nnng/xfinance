"""Instrument discovery, bars, and snapshots."""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from loguru import logger

from ..domain.catalog import (
    COMMODITY_SERIES,
    FEATURED,
    FX_SERIES,
    INDEX_SERIES,
    YIELD_TENORS,
    infer_meta,
    normalize_symbol,
    series_meta,
)
from ..domain.models import Bar, SeriesMeta, Snapshot, Timeframe
from .errors import NotFound

_PRICE_KINDS = {"stock", "etf", "lof", "index"}
_SYMBOL_RE = re.compile(r"^(SH|SZ|BJ)\d{6}$")


class MarketService:
    def __init__(self, services) -> None:
        self.s = services

    # -- metadata ------------------------------------------------------

    def meta(self, raw_symbol: str) -> SeriesMeta:
        symbol = normalize_symbol(raw_symbol)
        known = series_meta(symbol)
        if known:
            return known
        stored = self.s.securities.get(symbol)
        if stored:
            return stored
        if not _SYMBOL_RE.match(symbol):
            raise NotFound(f"未知标的: {raw_symbol}")
        return infer_meta(symbol)

    def search(self, query: str, limit: int = 12) -> list[SeriesMeta]:
        text = query.strip()
        if not text:
            return []
        results: list[SeriesMeta] = []
        seen: set[str] = set()
        for meta in self._static_candidates():
            if (
                text.lower() in meta.symbol.lower() or text in meta.name
            ) and meta.symbol not in seen:
                seen.add(meta.symbol)
                results.append(meta)
        try:
            self.s.sync.ensure_securities()
        except Exception:
            pass
        for meta in self.s.securities.search(text, limit=limit * 2):
            if meta.symbol not in seen:
                seen.add(meta.symbol)
                results.append(meta)
        for meta in self.s.sources.demo.search(text, limit=limit):
            if meta.symbol not in seen:
                seen.add(meta.symbol)
                results.append(meta)
        results.sort(key=lambda meta: _rank(meta, text))
        return results[:limit]

    def _static_candidates(self) -> list[SeriesMeta]:
        candidates: list[SeriesMeta] = []
        for symbol, name in INDEX_SERIES.items():
            candidates.append(infer_meta(symbol, name))
        for symbol, (name, kind) in FEATURED.items():
            meta = series_meta(symbol) or infer_meta(symbol, name)
            candidates.append(
                SeriesMeta(
                    symbol=meta.symbol,
                    name=name,
                    kind=kind,  # type: ignore[arg-type]
                    market=meta.market,
                    currency=meta.currency,
                    unit=meta.unit,
                )
            )
        for symbol in FX_SERIES:
            meta = series_meta(symbol)
            if meta:
                candidates.append(meta)
        for symbol in COMMODITY_SERIES:
            meta = series_meta(symbol)
            if meta:
                candidates.append(meta)
        for _column, symbol, _name in YIELD_TENORS:
            meta = series_meta(symbol)
            if meta:
                candidates.append(meta)
        return candidates

    # -- bars ----------------------------------------------------------

    def bars(
        self, raw_symbol: str, timeframe: Timeframe = "1d", adjust: str = "none"
    ) -> tuple[SeriesMeta, list[Bar], str]:
        meta = self.meta(raw_symbol)
        if meta.kind in _PRICE_KINDS:
            bars, source = self.s.sync.ensure_equity(meta.symbol, timeframe, adjust)
        else:
            bars, source = self.s.sync.ensure_series(meta.symbol, timeframe=timeframe)
        if not bars:
            raise NotFound(f"{meta.symbol} 暂无 K 线数据")
        return meta, bars, source

    def daily(self, raw_symbol: str) -> tuple[SeriesMeta, list[Bar], str]:
        return self.bars(raw_symbol, "1d", "none")

    # -- snapshots -----------------------------------------------------

    def snapshot(self, raw_symbol: str) -> tuple[Snapshot, str]:
        snapshots, source = self.snapshots([raw_symbol])
        symbol = normalize_symbol(raw_symbol)
        snapshot = snapshots.get(symbol)
        if snapshot is None:
            raise NotFound(f"{symbol} 暂无快照")
        return snapshot, source

    def snapshots(self, raw_symbols: list[str]) -> tuple[dict[str, Snapshot], str]:
        metas = [self.meta(symbol) for symbol in raw_symbols]
        unique = {meta.symbol: meta for meta in metas}
        cached: dict[str, Snapshot] = {}
        missing: list[SeriesMeta] = []
        for symbol, meta in unique.items():
            value = self.s.app.snapshot_cache.get(("snapshot", symbol))
            if value is None:
                missing.append(meta)
            else:
                cached[symbol] = value
        sources: set[str] = {snapshot.source for snapshot in cached.values()}
        if missing:
            equity = [meta for meta in missing if meta.kind in _PRICE_KINDS]
            series = [meta for meta in missing if meta.kind not in _PRICE_KINDS]
            if equity:
                try:
                    fetched = self.s.sources.equity_snapshots(equity)
                    sources.add(fetched.source)
                    cached.update(fetched.snapshots)
                except Exception as error:
                    logger.warning("equity snapshots failed: {}", error)
            if series:
                try:
                    fetched = self.s.sources.series_snapshots(
                        [meta.symbol for meta in series]
                    )
                    sources.add(fetched.source)
                    cached.update(fetched.snapshots)
                except Exception as error:
                    logger.warning("series snapshots failed: {}", error)
        for meta in unique.values():
            if meta.symbol in cached:
                ttl = (
                    self.s.settings.snapshot_ttl
                    if meta.kind in _PRICE_KINDS
                    else self.s.settings.commodity_snapshot_ttl
                )
                self.s.app.snapshot_cache.set(("snapshot", meta.symbol), cached[meta.symbol], ttl)
        for meta in unique.values():
            if meta.symbol in cached:
                continue
            fallback = self._snapshot_from_bars(meta)
            if fallback is not None:
                cached[meta.symbol] = fallback
                sources.add("cache")
        return cached, "+".join(sorted(sources)) if sources else "unknown"

    def _snapshot_from_bars(self, meta: SeriesMeta) -> Snapshot | None:
        try:
            if meta.kind in _PRICE_KINDS:
                bars, _source = self.s.sync.ensure_equity(meta.symbol, "1d", "none")
            else:
                bars, _source = self.s.sync.ensure_series(meta.symbol)
        except Exception:
            return None
        if not bars:
            return None
        last = bars[-1]
        previous = bars[-2] if len(bars) > 1 else last
        return Snapshot(
            symbol=meta.symbol,
            name=meta.name,
            last=last.close,
            prev_close=previous.close,
            open=last.open,
            high=last.high,
            low=last.low,
            volume=last.volume,
            amount=last.amount,
            ts=datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None),
            source="cache",
        )

    @staticmethod
    def status() -> dict[str, object]:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        weekday = now.weekday() < 5
        minutes = now.hour * 60 + now.minute
        is_open = weekday and (
            (9 * 60 + 30 <= minutes <= 11 * 60 + 30)
            or (13 * 60 <= minutes <= 15 * 60)
        )
        midday = weekday and (11 * 60 + 30 < minutes < 13 * 60)
        if is_open:
            label = "交易中"
        elif midday:
            label = "午间休市"
        elif not weekday:
            label = "周末休市"
        else:
            label = "已收盘"
        return {
            "is_open": is_open,
            "label": label,
            "as_of": now.replace(tzinfo=None).isoformat(timespec="seconds"),
            "timezone": "Asia/Shanghai",
            "next_open": _next_open(now).isoformat(),
        }


def _next_open(now: datetime) -> datetime:
    """Next weekday session open in Asia/Shanghai. Holidays are not modeled."""
    tz = ZoneInfo("Asia/Shanghai")
    for offset in range(0, 8):
        day = (now + timedelta(days=offset)).date()
        if day.weekday() >= 5:
            continue
        for hour, minute in ((9, 30), (13, 0)):
            candidate = datetime.combine(day, time(hour, minute), tzinfo=tz)
            if candidate > now:
                return candidate
    return now + timedelta(days=1)


def _rank(meta: SeriesMeta, query: str) -> tuple[int, int, int]:
    text = query.lower()
    symbol = meta.symbol.lower()
    name = meta.name.lower()
    if symbol == text:
        position = 0
    elif symbol.startswith(text):
        position = 1
    elif name.startswith(text):
        position = 2
    elif text in name:
        position = 3
    else:
        position = 4
    kind_order = {"index": 0, "stock": 1, "etf": 2, "lof": 3}.get(meta.kind, 5)
    return (position, kind_order, len(meta.name))
