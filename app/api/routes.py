"""API router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from .routes_indices import router as indices_router
from .routes_instruments import router as instruments_router
from .routes_meta import router as meta_router
from .routes_overview import router as overview_router
from .routes_tools import router as tools_router
from .routes_watchlist import router as watchlist_router

api_router = APIRouter()
api_router.include_router(meta_router)
api_router.include_router(overview_router)
api_router.include_router(instruments_router)
api_router.include_router(watchlist_router)
api_router.include_router(indices_router)
api_router.include_router(tools_router)
