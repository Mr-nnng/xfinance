"""SQLite engine and session plumbing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str, *, echo: bool = False) -> Engine:
    if database_url.startswith("sqlite"):
        path = _sqlite_path(database_url)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        database_url,
        echo=echo,
        future=True,
        connect_args={"check_same_thread": False, "timeout": 20}
        if database_url.startswith("sqlite")
        else {},
    )
    if database_url.startswith("sqlite"):
        _install_sqlite_pragmas(engine)
    return engine


def _sqlite_path(database_url: str) -> Path | None:
    marker = ":///"
    if marker not in database_url:
        return None
    raw = database_url.split(marker, 1)[1]
    if not raw or raw == ":memory:":
        return None
    return Path(raw).expanduser()


def _install_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=20000")
        cursor.close()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
