"""Live-or-demo routing for every external series.

Services talk to this facade, never to a provider directly. Fallback is
explicit in the returned source label so the UI can say where data came from.
"""

from __future__ import annotations

from collections.abc import Callable

from loguru import logger

from ..config import Settings
from ..domain.catalog import COMMODITY_SERIES, FX_SERIES, YIELD_TENORS
from ..domain.models import Bar, SeriesMeta, Snapshot, Timeframe
from .external.base import (
    FetchedBars,
    FetchedSeries,
    FetchedSnapshots,
    ProviderError,
    SourceUnavailable,
)
from .external.cnbc import CnbcProvider
from .external.demo import DemoProvider
from .external.frankfurter import FrankfurterProvider
from .external.sge import SgeProvider
from .external.sina import SinaProvider
from .external.tdx import TdxProvider
from .external.treasury import TreasuryProvider


class ExternalSources:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mode = settings.data_mode
        self.demo = DemoProvider(as_of=settings.demo_as_of)
        self._live: dict[str, object] = {}

    # -- provenance helpers -------------------------------------------

    @property
    def use_live(self) -> bool:
        return self.mode in {"auto", "live"}

    def _provider(self, name: str, factory: Callable[[], object]):
        provider = self._live.get(name)
        if provider is None:
            provider = factory()
            self._live[name] = provider
        return provider

    # -- equities -----------------------------------------------------

    def equity_bars(
        self, symbol: str, timeframe: Timeframe, adjust: str, count: int = 1600
    ) -> FetchedBars:
        if self.mode == "demo":
            return FetchedBars(self.demo.bars(symbol, timeframe, adjust, count), "demo")
        provider = self._provider("tdx", lambda: TdxProvider(self.settings.upstream_timeout))
        try:
            bars = provider.bars(symbol, timeframe, adjust, count)
            if not bars:
                raise ProviderError(f"{symbol} 没有 K 线")
            return FetchedBars(bars, provider.source)
        except Exception as error:
            if self.mode == "live":
                raise SourceUnavailable(str(error)) from error
            logger.warning("TDX bars failed for {}: {}", symbol, error)
            return FetchedBars(
                self.demo.bars(symbol, timeframe, adjust, count), "demo"
            )

    def equity_snapshots(self, metas: list[SeriesMeta]) -> FetchedSnapshots:
        if not metas:
            return FetchedSnapshots({}, "demo")
        if self.mode == "demo":
            return FetchedSnapshots(
                {meta.symbol: self.demo.snapshot(meta) for meta in metas}, "demo"
            )
        provider = self._provider("tdx", lambda: TdxProvider(self.settings.upstream_timeout))
        try:
            snapshots = provider.snapshots(metas)
            if not snapshots:
                raise ProviderError("快照为空")
            return FetchedSnapshots(snapshots, provider.source)
        except Exception as error:
            if self.mode == "live":
                raise SourceUnavailable(str(error)) from error
            logger.warning("TDX snapshots failed: {}", error)
            return FetchedSnapshots(
                {meta.symbol: self.demo.snapshot(meta) for meta in metas}, "demo"
            )

    def securities(self) -> list[tuple[str, str, str, str, str]]:
        if self.mode == "demo":
            return self.demo.securities()
        provider = self._provider("tdx", lambda: TdxProvider(self.settings.upstream_timeout))
        try:
            return provider.securities()
        except Exception as error:
            if self.mode == "live":
                raise SourceUnavailable(str(error)) from error
            logger.warning("TDX code table failed: {}", error)
            return self.demo.securities()

    # -- fx / commodities / yields -----------------------------------

    def fx_daily(self, *, years: int = 6) -> FetchedSeries:
        demo = lambda: {
            symbol: self.demo.daily(symbol) for symbol in FX_SERIES
        }
        if self.mode == "demo":
            return FetchedSeries(demo(), "demo")
        provider = self._provider(
            "frankfurter", lambda: FrankfurterProvider(self.settings.upstream_timeout)
        )
        try:
            series = provider.daily(years=years)
            missing = [symbol for symbol in FX_SERIES if symbol not in series]
            if missing:
                raise ProviderError(f"缺少汇率: {', '.join(missing)}")
            return FetchedSeries(series, provider.source)
        except Exception as error:
            if self.mode == "live":
                raise SourceUnavailable(str(error)) from error
            logger.warning("Frankfurter unavailable: {}", error)
            return FetchedSeries(demo(), "demo")

    def global_daily(self, symbol: str) -> FetchedBars:
        if self.mode == "demo":
            return FetchedBars(self.demo.daily(symbol), "demo")
        provider = self._provider(
            "cnbc", lambda: CnbcProvider(self.settings.upstream_timeout)
        )
        try:
            return FetchedBars(provider.daily(symbol), "cnbc")
        except Exception as error:
            if self.mode == "live":
                raise SourceUnavailable(str(error)) from error
            logger.warning("CNBC unavailable for {}: {}", symbol, error)
            return FetchedBars(self.demo.daily(symbol), "demo")

    def commodity_daily(self, symbol: str) -> FetchedBars:
        if self.mode == "demo":
            return FetchedBars(self.demo.daily(symbol), "demo")
        if symbol == "AU9999":
            provider = self._provider("sge", lambda: SgeProvider(self.settings.upstream_timeout))
            operation = provider.au9999_daily
        elif symbol in COMMODITY_SERIES:
            provider = self._provider("sina", lambda: SinaProvider(self.settings.upstream_timeout))
            operation = lambda: provider.commodity_daily(symbol)
        else:
            raise SourceUnavailable(f"没有 {symbol} 的商品数据源")
        try:
            bars = operation()
            return FetchedBars(bars, provider.source)
        except Exception as error:
            if self.mode == "live":
                raise SourceUnavailable(str(error)) from error
            logger.warning("Commodity source failed for {}: {}", symbol, error)
            return FetchedBars(self.demo.daily(symbol), "demo")

    def yields_daily(self, *, years: int = 6) -> FetchedSeries:
        demo = lambda: {
            code: self.demo.daily(code) for _column, code, _name in YIELD_TENORS
        }
        if self.mode == "demo":
            return FetchedSeries(demo(), "demo")
        provider = self._provider(
            "treasury", lambda: TreasuryProvider(self.settings.upstream_timeout)
        )
        try:
            series = provider.yields(years=years)
            return FetchedSeries(series, provider.source)
        except Exception as error:
            if self.mode == "live":
                raise SourceUnavailable(str(error)) from error
            logger.warning("Treasury unavailable: {}", error)
            return FetchedSeries(demo(), "demo")

    def series_snapshots(self, symbols: list[str]) -> FetchedSnapshots:
        if self.mode == "demo":
            return FetchedSnapshots(
                {
                    symbol: self.demo.snapshot(_meta_for(symbol))
                    for symbol in symbols
                },
                "demo",
            )
        provider = self._provider("sina", lambda: SinaProvider(self.settings.upstream_timeout))
        try:
            snapshots = provider.snapshots(symbols)
            if not snapshots:
                raise ProviderError("快照为空")
            return FetchedSnapshots(snapshots, provider.source)
        except Exception as error:
            if self.mode == "live":
                raise SourceUnavailable(str(error)) from error
            logger.warning("Sina snapshots failed: {}", error)
            return FetchedSnapshots({}, "unavailable")

    def demo_snapshot(self, symbol: str) -> Snapshot:
        return self.demo.snapshot(_meta_for(symbol))

    def demo_bars(self, symbol: str) -> list[Bar]:
        return self.demo.daily(symbol)

    def close(self) -> None:
        for provider in self._live.values():
            try:
                provider.close()
            except Exception:  # pragma: no cover
                pass
        self._live.clear()


def _meta_for(symbol: str) -> SeriesMeta:
    from ..domain.catalog import infer_meta, series_meta

    return series_meta(symbol) or infer_meta(symbol, symbol)
