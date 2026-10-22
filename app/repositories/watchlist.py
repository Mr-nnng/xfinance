"""Watchlist persistence."""

from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import WatchRow


class WatchlistRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def symbols(self) -> list[str]:
        return list(
            self.session.scalars(select(WatchRow.symbol).order_by(WatchRow.position))
        )

    def add(self, symbol: str) -> bool:
        row = self.session.get(WatchRow, symbol)
        if row is not None:
            return False
        next_position = (
            self.session.scalar(select(func.max(WatchRow.position))) or 0
        ) + 1
        self.session.add(WatchRow(symbol=symbol, position=next_position))
        self.session.commit()
        return True

    def remove(self, symbol: str) -> bool:
        result = self.session.execute(delete(WatchRow).where(WatchRow.symbol == symbol))
        self.session.commit()
        return bool(result.rowcount)
