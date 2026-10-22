"""ECB reference rates through Frankfurter."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
from loguru import logger

from ...domain.models import Bar
from .base import LiveProvider, ProviderError

_ENDPOINT = "https://api.frankfurter.dev/v1"
_SYMBOLS = ("CNY", "JPY", "EUR", "GBP")
_SERIES = {currency: f"USD{currency}" for currency in _SYMBOLS}


class FrankfurterProvider(LiveProvider):
    source = "frankfurter"

    def __init__(self, timeout: float = 8.0) -> None:
        self.client = httpx.Client(
            timeout=timeout, follow_redirects=True, headers={"User-Agent": "xfinance/0.1"}
        )

    def daily(self, *, years: int = 6, end: date | None = None) -> dict[str, list[Bar]]:
        end = end or date.today()
        start = end - timedelta(days=365 * years)
        url = f"{_ENDPOINT}/{start.isoformat()}..{end.isoformat()}"
        try:
            response = self.client.get(
                url, params={"base": "USD", "symbols": ",".join(_SYMBOLS)}
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as error:  # pragma: no cover - network dependent
            logger.warning("Frankfurter request failed: {}", error)
            raise ProviderError(f"ECB 汇率源不可用: {error}") from error
        rates = payload.get("rates") or {}
        result: dict[str, list[Bar]] = {symbol: [] for symbol in _SERIES.values()}
        for raw_date, values in sorted(rates.items()):
            day = date.fromisoformat(raw_date)
            for currency, symbol in _SERIES.items():
                value = values.get(currency)
                if value is None:
                    continue
                result[symbol].append(
                    Bar(
                        date=day,
                        open=float(value),
                        high=float(value),
                        low=float(value),
                        close=float(value),
                    )
                )
        return {symbol: bars for symbol, bars in result.items() if bars}

    def close(self) -> None:
        self.client.close()
