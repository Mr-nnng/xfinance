"""Wiring for one request, plus process-wide state."""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..infrastructure.cache import TTLCache
from ..infrastructure.sources import ExternalSources
from ..repositories.bars import BarsRepository
from ..repositories.indices import CustomIndexRepository
from ..repositories.securities import SecuritiesRepository
from ..repositories.sync_state import SyncStateRepository
from ..repositories.watchlist import WatchlistRepository


@dataclass
class AppCore:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    sources: ExternalSources
    snapshot_cache: TTLCache = field(default_factory=lambda: TTLCache(1024))
    overview_cache: TTLCache = field(default_factory=lambda: TTLCache(8))
    expression_cache: TTLCache = field(default_factory=lambda: TTLCache(64))
    locks: dict[str, threading.Lock] = field(default_factory=dict)
    locks_guard: threading.Lock = field(default_factory=threading.Lock)
    started_at: datetime = field(default_factory=datetime.now)

    def lock_for(self, key: str) -> threading.Lock:
        with self.locks_guard:
            return self.locks.setdefault(key, threading.Lock())

    def session(self) -> Session:
        return self.session_factory()


class Services:
    """One HTTP request's repositories and services over a shared session."""

    def __init__(self, app: AppCore, session: Session) -> None:
        self.app = app
        self.session = session
        self.settings = app.settings
        self.sources = app.sources
        self.bars = BarsRepository(session)
        self.securities = SecuritiesRepository(session)
        self.watchlist = WatchlistRepository(session)
        self.indices = CustomIndexRepository(session)
        self.sync_state = SyncStateRepository(session)

        from .chart import ChartService
        from .expressions import ExpressionService
        from .market import MarketService
        from .overview import OverviewService
        from .sync import SyncService
        from .tools import ToolsService

        self.sync = SyncService(self)
        self.market = MarketService(self)
        self.chart = ChartService(self)
        self.expressions = ExpressionService(self)
        self.overview = OverviewService(self)
        self.tools = ToolsService(self)

    def close(self) -> None:
        self.session.close()


def iter_services(app: AppCore) -> Iterable[Services]:
    session = app.session()
    services = Services(app, session)
    try:
        yield services
    finally:
        services.close()
