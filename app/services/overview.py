"""Overview dashboard assembly."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from loguru import logger

from ..domain.catalog import (
    OVERVIEW_COMMODITIES,
    OVERVIEW_FX,
    OVERVIEW_INDICES,
    OVERVIEW_YIELDS,
)
from ..domain.models import SeriesMeta, Snapshot
from .context import Services

CARD_RANGE_DAYS = 45
CUSTOM_CARD_TTL = 10.0


class OverviewService:
    def __init__(self, services) -> None:
        self.s = services

    def overview(self) -> dict:
        cache = self.s.app.overview_cache
        cached = cache.get(("overview",))
        if cached is not None:
            return cached
        self.s.sync.seed_watchlist()
        watchlist = self.s.watchlist.symbols()[:12]
        index_metas = [self.s.market.meta(symbol) for symbol in OVERVIEW_INDICES]
        watch_metas = [self.s.market.meta(symbol) for symbol in watchlist]
        fx_metas = [self.s.market.meta(symbol) for symbol in OVERVIEW_FX]
        commodity_metas = [
            self.s.market.meta(symbol) for symbol in OVERVIEW_COMMODITIES
        ]
        yield_metas = [self.s.market.meta(symbol) for symbol in OVERVIEW_YIELDS]
        self._presync(index_metas + watch_metas, fx_metas + commodity_metas + yield_metas)

        all_metas = index_metas + watch_metas + fx_metas + commodity_metas
        try:
            snapshots, snapshot_source = self.s.market.snapshots(
                [meta.symbol for meta in all_metas]
            )
        except Exception as error:
            logger.warning("overview snapshots failed: {}", error)
            snapshots, snapshot_source = {}, "unavailable"

        indices = [
            self._price_card(meta, snapshots, snapshot_source) for meta in index_metas
        ]
        watch_cards = [
            self._price_card(meta, snapshots, snapshot_source) for meta in watch_metas
        ]
        fx_cards = [
            self._price_card(meta, snapshots, snapshot_source) for meta in fx_metas
        ]
        commodity_cards = [
            self._price_card(meta, snapshots, snapshot_source)
            for meta in commodity_metas
        ]
        yield_cards = [self._yield_card(meta) for meta in yield_metas]
        custom_cards = self.s.app.overview_cache.get(("custom_cards",))
        if custom_cards is None:
            custom_cards = self._custom_cards()
            self.s.app.overview_cache.set(("custom_cards",), custom_cards, CUSTOM_CARD_TTL)

        sources = {snapshot_source}
        for card in indices + watch_cards + fx_cards + commodity_cards + yield_cards:
            if card.get("source"):
                sources.add(str(card["source"]))
        payload = {
            "indices": indices,
            "watchlist": watch_cards,
            "fx": fx_cards,
            "commodities": commodity_cards,
            "yields": yield_cards,
            "custom_indices": custom_cards,
            "market": self.s.market.status(),
            "sources": sorted(source for source in sources if source),
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        cache.set(("overview",), payload, 5.0)
        return payload

    # -- cards ---------------------------------------------------------

    def _price_card(
        self, meta: SeriesMeta, snapshots: dict[str, Snapshot], source: str
    ) -> dict:
        snapshot = snapshots.get(meta.symbol)
        bars = self.s.bars.tail(meta.symbol, "1d", "none", CARD_RANGE_DAYS)
        if snapshot is None and bars:
            last = bars[-1]
            previous = bars[-2] if len(bars) > 1 else last
            snapshot = Snapshot(
                symbol=meta.symbol,
                name=meta.name,
                last=last.close,
                prev_close=previous.close,
                open=last.open,
                high=last.high,
                low=last.low,
                volume=last.volume,
                amount=last.amount,
                ts=datetime.now(),
                source="cache",
            )
        return {
            "meta": _meta_dict(meta),
            "snapshot": _snapshot_dict(snapshot) if snapshot else None,
            "spark": [bar.close for bar in bars],
            "source": snapshot.source if snapshot else source,
        }

    def _yield_card(self, meta: SeriesMeta) -> dict:
        bars = self.s.bars.tail(meta.symbol, "1d", "none", CARD_RANGE_DAYS)
        last = bars[-1].close if bars else 0.0
        previous = bars[-2].close if len(bars) > 1 else last
        return {
            "meta": _meta_dict(meta),
            "value": last,
            "prev": previous,
            "change_bp": (last - previous) * 100,
            "spark": [bar.close for bar in bars],
            "source": "cache",
        }

    def _custom_cards(self) -> list[dict]:
        cards: list[dict] = []
        for record in self.s.indices.list()[:8]:
            try:
                payload = self.s.expressions.chart(record.id, range_key="6m", window=60)
            except Exception as error:
                cards.append(
                    {
                        "id": record.id,
                        "name": record.name,
                        "expression": record.expression,
                        "error": str(error),
                    }
                )
                continue
            stats = payload["stats"]
            cards.append(
                {
                    "id": record.id,
                    "name": record.name,
                    "expression": record.expression,
                    "last": stats["last"],
                    "change_pct": stats["change_pct"],
                    "percentile": stats["percentile"],
                    "spark": [bar["close"] for bar in payload["bars"]],
                }
            )
        return cards

    # -- sync ----------------------------------------------------------

    def _presync(
        self, equity_metas: list[SeriesMeta], series_metas: list[SeriesMeta]
    ) -> None:
        jobs: list[tuple[str, str]] = []
        for meta in equity_metas:
            symbol = meta.symbol
            try:
                if not self.s.market.is_market_open(meta) and self.s.bars.last_date(
                    symbol, "1d", "none"
                ):
                    continue
                if not self.s.sync.is_fresh_equity(symbol):
                    jobs.append(("equity", symbol))
            except Exception:
                jobs.append(("equity", symbol))
        for meta in series_metas:
            symbol = meta.symbol
            try:
                if (
                    meta.kind != "yield"
                    and not self.s.market.is_market_open(meta)
                    and self.s.bars.last_date(symbol, "1d", "none")
                ):
                    continue
                if not self.s.sync.is_fresh_series(symbol):
                    jobs.append(("series", symbol))
            except Exception:
                jobs.append(("series", symbol))
        if not jobs:
            return

        def run(job: tuple[str, str]) -> None:
            kind, symbol = job
            services = Services(self.s.app, self.s.app.session())
            try:
                if kind == "equity":
                    services.sync.ensure_equity(symbol, "1d", "none")
                else:
                    services.sync.ensure_series(symbol)
            except Exception as error:
                logger.warning("overview presync failed for {}: {}", symbol, error)
            finally:
                services.close()

        with ThreadPoolExecutor(max_workers=min(6, len(jobs))) as executor:
            list(executor.map(run, jobs))


def _meta_dict(meta: SeriesMeta) -> dict:
    return {"symbol": meta.symbol, "name": meta.name, "unit": meta.unit}


def _snapshot_dict(snapshot: Snapshot) -> dict:
    return {
        "last": snapshot.last,
        "change": snapshot.change,
        "change_pct": snapshot.change_pct,
    }
