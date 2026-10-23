"""TDX (通达信 7709) adapter for A-share bars, snapshots, and the code table."""

from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from ...domain.models import Bar, Level, SeriesMeta, Snapshot, Timeframe
from .base import LiveProvider, ProviderError

_PERIOD: dict[str, str] = {"1d": "day", "1w": "week", "1m": "month"}
_CATEGORY: dict[str, str] = {
    "a_share": "stock",
    "b_share": "stock",
    "etf": "etf",
    "lof": "lof",
    "index": "index",
}


class TdxProvider(LiveProvider):
    source = "tdx"

    def __init__(self, timeout: float = 8.0) -> None:
        self.timeout = timeout
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        with self._lock:
            if self._client is None:
                from eltdx import TdxClient

                self._client = TdxClient(timeout=self.timeout)
            return self._client

    def _reset(self) -> None:
        with self._lock:
            client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception:  # pragma: no cover - best effort
                pass

    def _call(self, operation, *args, **kwargs):
        try:
            return operation(self._get_client(), *args, **kwargs)
        except Exception as error:  # pragma: no cover - network dependent
            logger.warning("TDX call failed: {}", error)
            self._reset()
            raise ProviderError(f"通达信行情源不可用: {error}") from error

    def bars(
        self, symbol: str, timeframe: Timeframe, adjust: str, count: int = 800
    ) -> list[Bar]:
        code = _tdx_code(symbol)
        period = _PERIOD[timeframe]
        adjust_mode = None if adjust in {"none", ""} else adjust

        def fetch(client):
            pages: list[list[Bar]] = []
            start = 0
            remaining = count
            while remaining > 0:
                size = min(remaining, 800)
                page = client.bars.get(
                    code,
                    period=period,
                    start=start,
                    count=size,
                    adjust=adjust_mode,
                )
                rows = [_to_bar(item) for item in page.bars]
                if not rows:
                    break
                pages.append(rows)
                start += len(rows)
                remaining -= len(rows)
                if len(rows) < size:
                    break
            merged = [bar for page in reversed(pages) for bar in page]
            merged.sort(key=lambda bar: bar.date)
            return merged

        return self._call(fetch)

    def snapshots(self, metas: list[SeriesMeta]) -> dict[str, Snapshot]:
        if not metas:
            return {}
        codes = [_tdx_code(meta.symbol) for meta in metas]
        raw = self._call(lambda client: client.helpers.full_quotes(codes))
        by_code: dict[str, Snapshot] = {}
        name_by_symbol = {_tdx_code(meta.symbol): meta for meta in metas}
        for quote in raw:
            meta = name_by_symbol.get(quote.full_code)
            if meta is None:
                continue
            last = float(quote.last_price or quote.pre_close_price or 0.0)
            if last <= 0:
                continue
            by_code[meta.symbol] = Snapshot(
                symbol=meta.symbol,
                name=meta.name,
                last=last,
                prev_close=float(quote.pre_close_price or last),
                open=float(quote.open_price or last),
                high=float(quote.high_price or last),
                low=float(quote.low_price or last),
                volume=float(quote.total_hand or 0.0),
                amount=float(quote.amount or 0.0),
                ts=_now(),
                bids=tuple(
                    Level(float(level.price), float(level.volume))
                    for level in quote.buy_levels
                ),
                asks=tuple(
                    Level(float(level.price), float(level.volume))
                    for level in quote.sell_levels
                ),
                source=self.source,
            )
        return by_code

    def securities(self) -> list[tuple[str, str, str, str, str]]:
        def fetch(client):
            rows = client.codes.all_markets()
            output: list[tuple[str, str, str, str, str]] = []
            for row in rows:
                kind = _CATEGORY.get(row.category)
                if kind is None and _is_lof(row):
                    kind = "lof"
                if kind is None:
                    continue
                output.append(
                    (
                        row.full_code.upper(),
                        row.name,
                        kind,
                        row.exchange.upper(),
                        row.board,
                    )
                )
            return output

        return self._call(fetch)

    def close(self) -> None:
        self._reset()


def _is_lof(row) -> bool:
    code = row.full_code[2:]
    exchange = row.exchange.lower()
    return (
        row.name.upper().endswith("LOF")
        or (exchange == "sz" and code.startswith("16"))
        or (exchange == "sh" and code.startswith("501"))
    )


def _tdx_code(symbol: str) -> str:
    return symbol.lower()


def _to_bar(item) -> Bar:
    volume = float(getattr(item, "volume_lots", 0.0) or 0.0)
    amount = float(getattr(item, "amount", 0.0) or 0.0)
    return Bar(
        date=item.time.date(),
        open=float(item.open),
        high=float(item.high),
        low=float(item.low),
        close=float(item.close),
        volume=volume,
        amount=amount,
    )


def _now() -> datetime:
    return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
