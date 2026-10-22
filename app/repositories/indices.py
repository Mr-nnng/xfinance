"""Custom index persistence."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.models import StoredCustomIndex
from .models import CustomIndexRow


class NameTaken(Exception):
    pass


class CustomIndexRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[StoredCustomIndex]:
        rows = self.session.scalars(
            select(CustomIndexRow).order_by(CustomIndexRow.id)
        )
        return [self._to_domain(row) for row in rows]

    def get(self, index_id: int) -> StoredCustomIndex | None:
        row = self.session.get(CustomIndexRow, index_id)
        return self._to_domain(row) if row else None

    def get_by_name(self, name: str) -> StoredCustomIndex | None:
        row = self.session.scalar(
            select(CustomIndexRow).where(CustomIndexRow.name == name)
        )
        return self._to_domain(row) if row else None

    def create(self, name: str, expression: str) -> StoredCustomIndex:
        row = CustomIndexRow(name=name.strip(), expression=expression.strip())
        self.session.add(row)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise NameTaken(name) from error
        self.session.refresh(row)
        return self._to_domain(row)

    def delete(self, index_id: int) -> bool:
        row = self.session.get(CustomIndexRow, index_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.commit()
        return True

    @staticmethod
    def _to_domain(row: CustomIndexRow) -> StoredCustomIndex:
        return StoredCustomIndex(id=row.id, name=row.name, expression=row.expression)
