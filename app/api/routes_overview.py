"""Overview endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from .deps import ServicesDep
from .envelope import ok

router = APIRouter(tags=["overview"])


@router.get("/overview")
def overview(services: ServicesDep) -> dict:
    payload = services.overview.overview()
    return ok(payload, source="+".join(payload["sources"]))
