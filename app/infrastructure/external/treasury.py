"""US Treasury daily yield curve CSV."""

from __future__ import annotations

import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import httpx
from loguru import logger

from ...domain.catalog import YIELD_TENORS
from ...domain.models import Bar
from .base import LiveProvider, ProviderError

_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)
_HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) xfinance/0.1"}


class TreasuryProvider(LiveProvider):
    source = "treasury"

    def __init__(self, timeout: float = 12.0) -> None:
        self.client = httpx.Client(timeout=timeout, headers=_HEADERS)

    def yields(self, *, years: int = 6, end: date | None = None) -> dict[str, list[Bar]]:
        end = end or date.today()
        calendar = list(range(end.year - years + 1, end.year + 1))
        with ThreadPoolExecutor(max_workers=min(4, len(calendar))) as executor:
            tables = list(executor.map(self._fetch_year, calendar))
        merged: dict[str, dict[date, float]] = {code: {} for _column, code, _name in YIELD_TENORS}
        for table in tables:
            for day, row in table:
                for column, code, _name in YIELD_TENORS:
                    value = row.get(column)
                    if value in (None, ""):
                        continue
                    try:
                        merged[code][day] = float(value)
                    except (TypeError, ValueError):
                        continue
        output: dict[str, list[Bar]] = {}
        for code, points in merged.items():
            if not points:
                continue
            output[code] = [
                Bar(
                    date=day,
                    open=value,
                    high=value,
                    low=value,
                    close=value,
                )
                for day, value in sorted(points.items())
            ]
        if not output:
            raise ProviderError("美国财政部未返回收益率数据")
        return output

    def _fetch_year(self, year: int) -> list[tuple[date, dict[str, str]]]:
        try:
            response = self.client.get(_URL.format(year=year))
            response.raise_for_status()
        except Exception as error:  # pragma: no cover - network dependent
            logger.warning("Treasury request failed for {}: {}", year, error)
            raise ProviderError(f"美国财政部数据源不可用: {error}") from error
        reader = csv.DictReader(io.StringIO(response.text))
        rows: list[tuple[date, dict[str, str]]] = []
        for row in reader:
            raw = row.get("Date")
            if not raw:
                continue
            try:
                day = datetime.strptime(raw, "%m/%d/%Y").date()
            except ValueError:
                continue
            rows.append((day, row))
        return rows

    def close(self) -> None:
        self.client.close()
