"""Health, metadata, and static configuration endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import text

from .. import __version__
from ..domain.catalog import NUMERAIRES
from .deps import ServicesDep
from .envelope import numeraire_dict, ok

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(services: ServicesDep) -> dict:
    database_ok = True
    try:
        services.session.execute(text("select 1"))
    except Exception:
        database_ok = False
    build = services.settings.resolved_frontend_build / "index.html"
    return ok(
        {
            "status": "ok" if database_ok else "degraded",
            "version": __version__,
            "database": database_ok,
            "data_mode": services.settings.data_mode,
            "frontend_built": build.is_file(),
            "uptime_seconds": int(
                (datetime.now() - services.app.started_at).total_seconds()
            ),
        },
        source="local",
    )


@router.get("/meta/numeraires")
def numeraires(services: ServicesDep) -> dict:
    return ok([numeraire_dict(item) for item in NUMERAIRES], source="local")


@router.get("/meta/status")
def status(services: ServicesDep) -> dict:
    build = services.settings.resolved_frontend_build / "index.html"
    return ok(
        {
            "market": services.market.status(),
            "data_mode": services.settings.data_mode,
            "version": __version__,
            "frontend_built": build.is_file(),
        },
        source="local",
    )
