from __future__ import annotations

from contextlib import nullcontext
from datetime import date

from app.domain.models import Bar
from app.services.sync import SyncService


class FakeApp:
    def lock_for(self, _key):
        return nullcontext()


class FakeSettings:
    adjusted_bars_ttl = 3600
    bars_ttl = 60
    series_ttl = 60
    data_mode = "live"


class FakeBars:
    def __init__(self, bars):
        self._bars = bars

    def fetch(self, _symbol, _timeframe, _adjust):
        return list(self._bars)

    def upsert(self, *_args):
        return 0


class FakeSyncState:
    def __init__(self, note):
        self._note = note

    def is_fresh(self, _key, _ttl):
        return False

    def note(self, _key):
        return self._note

    def touch(self, *_args):
        return None


class FakeSources:
    source_name = "demo"

    def fx_daily(self):
        raise RuntimeError("upstream down")

    def equity_bars(self, *_args, **_kwargs):
        raise RuntimeError("upstream down")


class FakeServices:
    def __init__(self, note):
        self.app = FakeApp()
        self.settings = FakeSettings()
        self.bars = FakeBars([Bar(date(2026, 10, 22), 1.0, 1.0, 1.0, 1.0)])
        self.sync_state = FakeSyncState(note)
        self.sources = FakeSources()


def test_series_falls_back_to_cached_bars_with_source() -> None:
    service = SyncService(FakeServices("frankfurter"))
    bars, source = service.ensure_series("USDCNY")
    assert len(bars) == 1
    assert source == "frankfurter"


def test_equity_falls_back_to_cached_bars_with_source() -> None:
    service = SyncService(FakeServices("tdx"))
    bars, source = service.ensure_equity("SH600519")
    assert len(bars) == 1
    assert source == "tdx"
