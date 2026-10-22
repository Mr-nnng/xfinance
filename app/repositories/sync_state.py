"""Sync bookkeeping: when was each cache key last refreshed."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import SyncStateRow, utcnow


class SyncStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def fetched_at(self, key: str) -> datetime | None:
        row = self.session.get(SyncStateRow, key)
        return row.fetched_at if row else None

    def note(self, key: str) -> str:
        row = self.session.get(SyncStateRow, key)
        return row.note if row else ""

    def is_fresh(self, key: str, ttl_seconds: int) -> bool:
        fetched = self.fetched_at(key)
        if fetched is None:
            return False
        return utcnow() - fetched < timedelta(seconds=ttl_seconds)

    def touch(self, key: str, note: str = "") -> None:
        row = self.session.get(SyncStateRow, key)
        now = utcnow()
        if row is None:
            self.session.add(SyncStateRow(key=key, fetched_at=now, note=note))
        else:
            row.fetched_at = now
            row.note = note
        self.session.commit()
