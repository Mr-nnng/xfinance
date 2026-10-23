from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.models import SeriesMeta
from app.services.market import MarketService

SHANGHAI = ZoneInfo("Asia/Shanghai")


def _meta(market: str, kind: str = "stock") -> SeriesMeta:
    return SeriesMeta(
        symbol="SH600519",
        name="测试",
        kind=kind,  # type: ignore[arg-type]
        market=market,
        currency="CNY",
        unit="股",
    )


def test_market_open_is_per_instrument() -> None:
    stock = _meta("SH")
    fx = _meta("FX", "fx")
    global_market = _meta("GLOBAL", "commodity")
    yield_meta = _meta("UST", "yield")

    assert MarketService.is_market_open(
        stock, datetime(2026, 10, 23, 10, 0, tzinfo=SHANGHAI)
    )
    assert not MarketService.is_market_open(
        stock, datetime(2026, 10, 23, 12, 0, tzinfo=SHANGHAI)
    )
    assert not MarketService.is_market_open(
        stock, datetime(2026, 10, 23, 15, 1, tzinfo=SHANGHAI)
    )
    assert not MarketService.is_market_open(
        stock, datetime(2026, 10, 24, 10, 0, tzinfo=SHANGHAI)
    )
    assert MarketService.is_market_open(
        fx, datetime(2026, 10, 23, 23, 0, tzinfo=SHANGHAI)
    )
    assert not MarketService.is_market_open(
        fx, datetime(2026, 10, 24, 23, 0, tzinfo=SHANGHAI)
    )
    assert MarketService.is_market_open(
        global_market, datetime(2026, 10, 23, 23, 0, tzinfo=SHANGHAI)
    )
    assert not MarketService.is_market_open(
        yield_meta, datetime(2026, 10, 23, 10, 0, tzinfo=SHANGHAI)
    )
