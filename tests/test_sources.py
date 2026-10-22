"""Offline parser tests for the external market data providers."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest

from app.infrastructure.external.frankfurter import FrankfurterProvider
from app.infrastructure.external.sge import SgeProvider
from app.infrastructure.external.sina import SinaProvider
from app.infrastructure.external.treasury import TreasuryProvider


class FakeResponse:
    def __init__(
        self,
        *,
        payload: Any = None,
        text: str = "",
        content: bytes = b"",
    ) -> None:
        self._payload = payload
        self.text = text
        self.content = content

    def raise_for_status(self) -> None:
        pass

    def json(self) -> Any:
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(url)
        return self.response


def test_frankfurter_builds_usd_cross_bars() -> None:
    payload = {
        "rates": {
            "2024-01-02": {"CNY": 7.1, "JPY": 140.0, "EUR": 0.91, "GBP": 0.79},
            "2024-01-03": {"CNY": 7.2, "JPY": 141.0, "EUR": 0.92, "GBP": 0.80},
        }
    }
    provider = FrankfurterProvider()
    provider.client = FakeClient(FakeResponse(payload=payload))

    series = provider.daily(end=date(2024, 1, 3), years=1)

    assert set(series) == {"USDCNY", "USDJPY", "USDEUR", "USDGBP"}
    cny = series["USDCNY"]
    assert [bar.date for bar in cny] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert [bar.close for bar in cny] == pytest.approx([7.1, 7.2])
    assert all(bar.open == bar.high == bar.low == bar.close for bar in cny)


def test_sina_commodity_daily_parses_jsonp_and_skips_invalid_rows() -> None:
    payload = [
        {
            "date": "2024-01-02",
            "open": "2030.0",
            "high": "2045.0",
            "low": "2025.0",
            "close": "2040.0",
            "volume": "123",
        },
        {
            "date": "2024-01-03",
            "open": "2040.0",
            "high": "2050.0",
            "low": "2030.0",
            "close": "2045.0",
            "volume": "321",
        },
        {"date": "2024-01-04"},
        {"date": "2024-01-05", "close": "not-a-number"},
        {"date": "bad-date", "close": "1"},
        {"date": "2024-01-06", "open": "bad", "close": "1"},
        {},
    ]
    body = f"var _GC=({json.dumps(payload)});"
    provider = SinaProvider()
    provider.client = FakeClient(FakeResponse(text=body))

    bars = provider.commodity_daily("XAUUSD")

    assert [bar.date for bar in bars] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert [(bar.open, bar.high, bar.low, bar.close) for bar in bars] == [
        (2030.0, 2045.0, 2025.0, 2040.0),
        (2040.0, 2050.0, 2030.0, 2045.0),
    ]
    assert [bar.volume for bar in bars] == [123.0, 321.0]


def _quote(code: str, fields: list[str]) -> str:
    return f'var hq_str_{code}="{",".join(fields)}";'


def test_sina_snapshots_maps_commodity_sge_and_fx_layouts() -> None:
    gc = [
        "2000.5",
        "0",
        "0",
        "0",
        "2010.0",
        "1990.0",
        "15:30:00",
        "1980.0",
        "1995.0",
        "12345",
        "0",
        "0",
        "2026-10-22",
        "COMEX黄金",
    ]
    au9999 = [
        "Au99.99",
        "",
        "",
        "950.5",
        "",
        "",
        "",
        "960.0",
        "940.0",
        "945.0",
        "",
        "",
        "",
        "",
        "1000",
        "2000000",
        "2026-10-22 15:30:00",
    ]
    usdcny = [
        "2026-10-22",
        "0",
        "0",
        "7.2000",
        "0",
        "7.1500",
        "7.2500",
        "7.1000",
        "7.2100",
        "美元人民币",
        "15:30:00",
    ]
    eurusd = [
        "2026-10-22",
        "0",
        "0",
        "1.2000",
        "0",
        "1.1800",
        "1.2600",
        "1.1700",
        "1.2500",
        "欧元美元",
        "15:30:00",
    ]
    text = "\n".join(
        _quote(code, fields)
        for code, fields in (
            ("hf_GC", gc),
            ("SGE_AU9999", au9999),
            ("USDCNY", usdcny),
            ("EURUSD", eurusd),
        )
    )
    provider = SinaProvider()
    provider.client = FakeClient(FakeResponse(content=text.encode("gb18030")))

    snapshots = provider.snapshots(["XAUUSD", "AU9999", "USDCNY", "USDEUR"])

    assert set(snapshots) == {"XAUUSD", "AU9999", "USDCNY", "USDEUR"}
    assert all(snapshot.source == "sina" for snapshot in snapshots.values())

    gold = snapshots["XAUUSD"]
    assert gold.last == pytest.approx(2000.5)
    assert gold.prev_close == pytest.approx(1980.0)

    sge = snapshots["AU9999"]
    assert sge.last == pytest.approx(950.5)
    assert sge.prev_close == pytest.approx(945.0)
    assert sge.change > 0

    cny = snapshots["USDCNY"]
    assert cny.last == pytest.approx(7.21)
    assert cny.prev_close == pytest.approx(7.2)

    eur = snapshots["USDEUR"]
    assert eur.last == pytest.approx(1.0 / 1.25)
    assert eur.prev_close == pytest.approx(1.0 / 1.2)
    assert eur.high == pytest.approx(1.0 / 1.17)
    assert eur.low == pytest.approx(1.0 / 1.26)
    assert eur.low <= eur.last <= eur.high


def test_sge_au9999_daily_normalizes_high_and_low() -> None:
    payload = {
        "time": [
            ["2024-01-02", "470.0", "475.0", "468.0", "472.0"],
            ["2024-01-03", "480.0", "478.0", "479.0", "479.5"],
        ]
    }
    provider = SgeProvider()
    provider.client = FakeClient(FakeResponse(payload=payload))

    bars = provider.au9999_daily()

    assert [bar.date for bar in bars] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert [(bar.high, bar.low) for bar in bars] == [(475.0, 468.0), (480.0, 478.0)]
    assert all(
        bar.low <= min(bar.open, bar.close) and bar.high >= max(bar.open, bar.close)
        for bar in bars
    )


def test_treasury_yields_merge_years_and_sort_dates() -> None:
    csv_text = (
        'Date,"1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"\n'
        '10/22/2024,"4.10","4.20","4.25","4.30","4.35","4.40","4.50","4.55"\n'
        '10/21/2024,"4.00","4.10","4.15","4.20","4.25","4.30","4.40","4.45"\n'
    )
    provider = TreasuryProvider()
    provider.client = FakeClient(FakeResponse(text=csv_text))

    series = provider.yields(end=date(2024, 12, 31), years=2)

    assert len(provider.client.calls) == 2
    assert {"UST1Y", "UST10Y", "UST30Y"} <= set(series)
    expected_closes = {
        "UST1Y": [4.00, 4.10],
        "UST10Y": [4.30, 4.40],
        "UST30Y": [4.45, 4.55],
    }
    for code, closes in expected_closes.items():
        bars = series[code]
        assert [bar.date for bar in bars] == [date(2024, 10, 21), date(2024, 10, 22)]
        assert [bar.close for bar in bars] == pytest.approx(closes)
    assert all(
        [bar.date for bar in bars] == sorted(bar.date for bar in bars)
        for bars in series.values()
    )
