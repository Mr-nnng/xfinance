"""Shared source errors and the provider surface."""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.models import Bar, Snapshot


class ProviderError(RuntimeError):
    pass


class SourceUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FetchedBars:
    bars: list[Bar]
    source: str


@dataclass(frozen=True, slots=True)
class FetchedSnapshots:
    snapshots: dict[str, Snapshot]
    source: str


@dataclass(frozen=True, slots=True)
class FetchedSeries:
    series: dict[str, list[Bar]]
    source: str


class LiveProvider:
    source = "live"

    def close(self) -> None:  # pragma: no cover - providers without resources
        pass
