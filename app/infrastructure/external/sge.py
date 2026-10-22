"""Shanghai Gold Exchange official daily bars for Au99.99."""

from __future__ import annotations

from datetime import date

import httpx
from loguru import logger

from ...domain.models import Bar
from .base import LiveProvider, ProviderError

_URL = "https://www.sge.com.cn/graph/Dailyhq/query?instid=Au99.99"
_HEADERS = {
    "Referer": "https://www.sge.com.cn/",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) xfinance/0.1",
}


class SgeProvider(LiveProvider):
    source = "sge"

    def __init__(self, timeout: float = 8.0) -> None:
        self.client = httpx.Client(timeout=timeout, headers=_HEADERS)

    def au9999_daily(self) -> list[Bar]:
        try:
            response = self.client.get(_URL)
            response.raise_for_status()
            payload = response.json()
        except Exception as error:  # pragma: no cover - network dependent
            logger.warning("SGE request failed: {}", error)
            raise ProviderError(f"上金所数据源不可用: {error}") from error
        rows = payload.get("time") or []
        bars: list[Bar] = []
        for row in rows:
            if len(row) < 5:
                continue
            try:
                day = date.fromisoformat(row[0])
                open_, close, low, high = (float(item) for item in row[1:5])
            except (TypeError, ValueError):
                continue
            bars.append(
                Bar(
                    date=day,
                    open=open_,
                    high=max(high, open_, close),
                    low=min(low, open_, close),
                    close=close,
                )
            )
        if not bars:
            raise ProviderError("上金所未返回 Au99.99 日线")
        return bars

    def close(self) -> None:
        self.client.close()
