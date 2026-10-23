"""CNBC chart history for global indices, Hong Kong and offshore CNY."""

from __future__ import annotations

from datetime import date

import httpx
from loguru import logger

from ...domain.models import Bar
from .base import LiveProvider, ProviderError

_URL = "https://ts-api.cnbc.com/harmony/app/charts/1Y.json"
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) xfinance/0.1"}
_SYMBOLS = {
    "SPX": ".SPX",
    "IXIC": ".IXIC",
    "DXY": ".DXY",
    "HK00883": "883.HK",
    "USDCNH": "CNH=",
}


class CnbcProvider(LiveProvider):
    source = "cnbc"

    def __init__(self, timeout: float = 8.0) -> None:
        self.client = httpx.Client(timeout=timeout, headers=_HEADERS)

    def daily(self, symbol: str) -> list[Bar]:
        code = _SYMBOLS.get(symbol)
        if code is None:
            raise ProviderError(f"CNBC 不提供 {symbol} 日线")
        try:
            response = self.client.get(
                _URL, params={"symbol": code, "frequency": "1D"}
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:  # pragma: no cover - network dependent
            logger.warning("CNBC request failed for {}: {}", symbol, error)
            raise ProviderError(f"CNBC 数据源不可用: {error}") from error
        bars: list[Bar] = []
        for row in payload.get("barData", {}).get("priceBars", []):
            try:
                raw = str(row["tradeTime"])[:8]
                day = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
                close = float(row["close"])
                bars.append(
                    Bar(
                        date=day,
                        open=float(row.get("open") or close),
                        high=float(row.get("high") or close),
                        low=float(row.get("low") or close),
                        close=close,
                        volume=float(row.get("volume") or 0.0),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        bars.sort(key=lambda bar: bar.date)
        if not bars:
            raise ProviderError(f"CNBC 未返回 {symbol} 日线")
        return bars

    def close(self) -> None:
        self.client.close()
