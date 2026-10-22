from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.app import create_app
from app.config import Settings


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    root: Path = tmp_path_factory.mktemp("xfinance-api")
    settings = Settings(
        data_mode="demo",
        data_dir=root,
        database_url=f"sqlite+pysqlite:///{root / 'test.db'}",
        demo_as_of=date(2026, 10, 22),
    )
    return create_app(settings)


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as test_client:
        yield test_client
