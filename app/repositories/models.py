"""ORM tables. Shapes mirror the domain, not the transport."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class BarRow(Base):
    __tablename__ = "bars"

    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(4), primary_key=True)
    adjust: Mapped[str] = mapped_column(String(6), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    amount: Mapped[float] = mapped_column(Float, default=0.0)


class SecurityRow(Base):
    __tablename__ = "securities"

    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    market: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    board: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class WatchRow(Base):
    __tablename__ = "watchlist"

    symbol: Mapped[str] = mapped_column(String(24), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CustomIndexRow(Base):
    __tablename__ = "custom_indices"
    __table_args__ = (UniqueConstraint("name", name="uq_custom_indices_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    expression: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class SyncStateRow(Base):
    __tablename__ = "sync_state"

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    note: Mapped[str] = mapped_column(String(128), nullable=False, default="")
