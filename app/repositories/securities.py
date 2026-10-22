"""Securities code table cache and search."""

from __future__ import annotations

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..domain.models import SeriesMeta
from .models import SecurityRow

_KIND_LABEL = {
    "a_share": "stock",
    "b_share": "stock",
    "etf": "etf",
    "lof": "lof",
    "index": "index",
}


class SecuritiesRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_all(self, rows: list[tuple[str, str, str, str, str]]) -> int:
        """rows: (symbol, name, kind, market, board)."""
        self.session.execute(delete(SecurityRow))
        self.session.bulk_insert_mappings(
            SecurityRow,
            [
                {
                    "symbol": symbol,
                    "name": name,
                    "kind": kind,
                    "market": market,
                    "board": board,
                }
                for symbol, name, kind, market, board in rows
            ],
        )
        self.session.commit()
        return len(rows)

    def search(self, query: str, limit: int = 20) -> list[SeriesMeta]:
        text = query.strip()
        if not text:
            return []
        pattern = f"%{text}%"
        statement = (
            select(SecurityRow)
            .where(
                or_(
                    SecurityRow.symbol.like(f"%{text.upper()}%"),
                    SecurityRow.name.like(pattern),
                )
            )
            .order_by(
                func.length(SecurityRow.name),
                SecurityRow.symbol,
            )
            .limit(limit)
        )
        return [self._to_meta(row) for row in self.session.scalars(statement)]

    def get(self, symbol: str) -> SeriesMeta | None:
        row = self.session.get(SecurityRow, symbol)
        return self._to_meta(row) if row else None

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(SecurityRow)) or 0

    @staticmethod
    def _to_meta(row: SecurityRow) -> SeriesMeta:
        kind = _KIND_LABEL.get(row.kind, "stock")
        return SeriesMeta(
            symbol=row.symbol,
            name=row.name,
            kind=kind,  # type: ignore[arg-type]
            market=row.market,
            currency="CNY",
            unit="份" if kind in {"etf", "lof"} else ("点" if kind == "index" else "股"),
            chart="candlestick",
        )
