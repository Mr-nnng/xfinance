from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.market import _next_open

SHANGHAI = ZoneInfo("Asia/Shanghai")


def test_next_open_handles_preopen_lunch_and_weekend() -> None:
    assert _next_open(datetime(2026, 10, 23, 8, 0, tzinfo=SHANGHAI)) == datetime(
        2026, 10, 23, 9, 30, tzinfo=SHANGHAI
    )
    assert _next_open(datetime(2026, 10, 23, 10, 0, tzinfo=SHANGHAI)) == datetime(
        2026, 10, 23, 13, 0, tzinfo=SHANGHAI
    )
    assert _next_open(datetime(2026, 10, 23, 16, 0, tzinfo=SHANGHAI)) == datetime(
        2026, 10, 26, 9, 30, tzinfo=SHANGHAI
    )
