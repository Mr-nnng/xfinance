"""Runtime settings. Parsed once at the process boundary."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="XFINANCE_", env_file=".env", extra="ignore"
    )

    data_dir: Path = Field(default_factory=lambda: Path.home() / ".xfinance")
    database_url: str | None = None
    data_mode: Literal["auto", "live", "demo"] = "auto"

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    frontend_build: Path | None = None
    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    upstream_timeout: float = 8.0
    snapshot_ttl: float = 5.0
    commodity_snapshot_ttl: float = 10.0
    bars_ttl: int = 900
    adjusted_bars_ttl: int = 21_600
    series_ttl: int = 21_600
    securities_ttl: int = 43_200
    demo_as_of: date | None = None

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite+pysqlite:///{self.data_dir / 'xfinance.db'}"

    @property
    def resolved_frontend_build(self) -> Path:
        if self.frontend_build:
            return self.frontend_build
        return Path(__file__).resolve().parent / "frontend-build"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
