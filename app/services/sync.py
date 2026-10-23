"""On-demand synchronization from external sources into SQLite."""

from __future__ import annotations

from loguru import logger

from ..domain.catalog import (
    CNBC_SERIES,
    COMMODITY_SERIES,
    DEFAULT_WATCHLIST,
    FX_SERIES,
    YIELD_TENORS,
    series_meta,
)
from ..domain.models import Bar, SeriesMeta, Timeframe
from ..infrastructure.external.base import FetchedSeries
from .errors import DataUnavailable


class SyncService:
    def __init__(self, services) -> None:
        self.s = services

    def ensure_equity(
        self,
        symbol: str,
        timeframe: Timeframe = "1d",
        adjust: str = "none",
        *,
        count: int = 1600,
    ) -> tuple[list[Bar], str]:
        key = f"bars:{symbol}:{timeframe}:{adjust}"
        ttl = (
            self.s.settings.adjusted_bars_ttl
            if adjust != "none"
            else self.s.settings.bars_ttl
        )
        lock = self.s.app.lock_for(key)
        with lock:
            cached = self.s.bars.fetch(symbol, timeframe, adjust)
            if cached and self.s.sync_state.is_fresh(key, ttl):
                return cached, self.s.sync_state.note(key) or "cache"
            try:
                fetched = self.s.sources.equity_bars(symbol, timeframe, adjust, count)
                self.s.bars.upsert(symbol, timeframe, adjust, fetched.bars)
                self.s.sync_state.touch(key, fetched.source)
                return self.s.bars.fetch(symbol, timeframe, adjust), fetched.source
            except Exception as error:
                if cached:
                    logger.warning(
                        "using cached bars for {} {} {}: {}",
                        symbol,
                        timeframe,
                        adjust,
                        error,
                    )
                    return cached, self.s.sync_state.note(key) or "cache"
                raise DataUnavailable(str(error)) from error

    def is_fresh_equity(
        self, symbol: str, timeframe: Timeframe = "1d", adjust: str = "none"
    ) -> bool:
        key = f"bars:{symbol}:{timeframe}:{adjust}"
        ttl = (
            self.s.settings.adjusted_bars_ttl
            if adjust != "none"
            else self.s.settings.bars_ttl
        )
        return bool(self.s.bars.last_date(symbol, timeframe, adjust)) and (
            self.s.sync_state.is_fresh(key, ttl)
        )

    def ensure_series(
        self, symbol: str, *, timeframe: Timeframe = "1d"
    ) -> tuple[list[Bar], str]:
        meta = series_meta(symbol)
        if meta is None:
            raise DataUnavailable(f"{symbol} 不是可用的行情序列")
        if timeframe == "1d":
            return self._ensure_daily_series(symbol, meta)
        bars, source = self._ensure_daily_series(symbol, meta)
        from ..domain.series import resample_bars

        return resample_bars(bars, timeframe), source

    def _ensure_daily_series(self, symbol: str, meta: SeriesMeta) -> tuple[list[Bar], str]:
        group_key, loader = self._series_plan(symbol)
        lock = self.s.app.lock_for(group_key)
        with lock:
            cached = self.s.bars.fetch(symbol, "1d", "none")
            if cached and self.s.sync_state.is_fresh(group_key, self.s.settings.series_ttl):
                return cached, self.s.sync_state.note(group_key) or "cache"
            try:
                fetched: FetchedSeries = loader()
                for item_symbol, bars in fetched.series.items():
                    self.s.bars.upsert(item_symbol, "1d", "none", bars)
                self.s.sync_state.touch(group_key, fetched.source)
                loaded = self.s.bars.fetch(symbol, "1d", "none")
                if not loaded:
                    raise DataUnavailable(f"数据源未返回 {symbol}")
                return loaded, fetched.source
            except Exception as error:
                if cached:
                    logger.warning("using cached series for {}: {}", symbol, error)
                    return cached, self.s.sync_state.note(group_key) or "cache"
                raise DataUnavailable(str(error)) from error

    def _series_plan(self, symbol: str):
        if symbol in CNBC_SERIES:
            return (
                f"series:cnbc:{symbol}",
                lambda: _single(self.s.sources.global_daily(symbol), symbol),
            )
        if symbol in FX_SERIES:
            return "series:fx", lambda: self.s.sources.fx_daily()
        if any(code == symbol for _column, code, _name in YIELD_TENORS):
            return "series:yields", lambda: self.s.sources.yields_daily()
        if symbol in COMMODITY_SERIES:
            return (
                f"series:commodity:{symbol}",
                lambda: _single(self.s.sources.commodity_daily(symbol), symbol),
            )
        raise DataUnavailable(f"没有 {symbol} 的历史序列")

    def ensure_securities(self) -> int:
        key = "securities:v2"
        lock = self.s.app.lock_for(key)
        with lock:
            count = self.s.securities.count()
            if count and self.s.sync_state.is_fresh(key, self.s.settings.securities_ttl):
                return count
            try:
                rows = self.s.sources.securities()
                if rows:
                    count = self.s.securities.replace_all(rows)
                    self.s.sync_state.touch(
                        key, "demo" if self.s.settings.data_mode == "demo" else "tdx"
                    )
                return count
            except Exception as error:
                logger.warning("security table unavailable: {}", error)
                return count

    def is_fresh_series(self, symbol: str) -> bool:
        meta = series_meta(symbol)
        if meta is None:
            return False
        group_key, _loader = self._series_plan(symbol)
        return bool(self.s.bars.last_date(symbol, "1d", "none")) and (
            self.s.sync_state.is_fresh(group_key, self.s.settings.series_ttl)
        )

    def seed_watchlist(self) -> None:
        key = "watchlist:seeded:v2"
        if self.s.sync_state.fetched_at(key) is not None:
            return
        for symbol in DEFAULT_WATCHLIST:
            self.s.watchlist.add(symbol)
        self.s.sync_state.touch(key, "defaults")


def _single(fetched, symbol: str) -> FetchedSeries:
    return FetchedSeries({symbol: fetched.bars}, fetched.source)
