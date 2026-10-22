"""Bar persistence: batch upsert and range reads."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..domain.models import Bar
from .models import BarRow

_COLUMNS = ("open", "high", "low", "close", "volume", "amount")


class BarsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self, symbol: str, timeframe: str, adjust: str, bars: list[Bar]
    ) -> int:
        if not bars:
            return 0
        payload = [
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "adjust": adjust,
                "date": bar.date,
                **{column: getattr(bar, column) for column in _COLUMNS},
            }
            for bar in bars
        ]
        for start in range(0, len(payload), 400):
            statement = sqlite_insert(BarRow).values(payload[start : start + 400])
            statement = statement.on_conflict_do_update(
                index_elements=["symbol", "timeframe", "adjust", "date"],
                set_={column: getattr(statement.excluded, column) for column in _COLUMNS},
            )
            self.session.execute(statement)
        self.session.commit()
        return len(payload)

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        adjust: str,
        *,
        start: date | None = None,
        limit: int | None = None,
    ) -> list[Bar]:
        statement = (
            select(BarRow)
            .where(
                BarRow.symbol == symbol,
                BarRow.timeframe == timeframe,
                BarRow.adjust == adjust,
            )
            .order_by(BarRow.date)
        )
        if start is not None:
            statement = statement.where(BarRow.date >= start)
        if limit is not None:
            statement = statement.limit(limit)
        return [self._to_bar(row) for row in self.session.scalars(statement)]

    def last_date(self, symbol: str, timeframe: str, adjust: str) -> date | None:
        return self.session.scalar(
            select(BarRow.date)
            .where(
                BarRow.symbol == symbol,
                BarRow.timeframe == timeframe,
                BarRow.adjust == adjust,
            )
            .order_by(BarRow.date.desc())
            .limit(1)
        )

    def count(self, symbol: str, timeframe: str, adjust: str) -> int:
        statement = select(BarRow).where(
            BarRow.symbol == symbol,
            BarRow.timeframe == timeframe,
            BarRow.adjust == adjust,
        )
        return len(self.session.scalars(statement).all())

    @staticmethod
    def _to_bar(row: BarRow) -> Bar:
        return Bar(
            date=row.date,
            open=row.open,
            high=row.high,
            low=row.low,
            close=row.close,
            volume=row.volume,
            amount=row.amount,
        )
