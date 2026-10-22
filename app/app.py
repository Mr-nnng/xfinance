"""FastAPI application factory and static SPA hosting."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .api.errors import install_error_handlers
from .api.routes import api_router
from .config import Settings
from .infrastructure.sources import ExternalSources
from .repositories.db import make_engine, make_session_factory
from .repositories.migrate import upgrade_database
from .services.context import AppCore

FALLBACK_HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>xfinance</title>
<style>body{font-family:system-ui,sans-serif;background:#0b0e11;color:#e6e8ea;
display:grid;place-items:center;height:100vh;margin:0}main{max-width:36rem;padding:2rem}
code{background:#171c22;padding:.2rem .4rem;border-radius:4px}a{color:#f0b35b}</style>
</head><body><main><h1>xfinance API 正在运行</h1>
<p>没有找到前端构建产物。开发时运行 <code>uv run python scripts/devserver.py</code>，
或构建前端 <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>。</p>
<p>API 文档：<a href="/docs">/docs</a></p></main></body></html>"""


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    _configure_logging(settings.log_level)
    settings.ensure_dirs()
    upgrade_database(settings.resolved_database_url)
    engine = make_engine(settings.resolved_database_url)
    core = AppCore(
        settings=settings,
        engine=engine,
        session_factory=make_session_factory(engine),
        sources=ExternalSources(settings),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logger.info(
            "xfinance ready: mode={} data_dir={} db={}",
            settings.data_mode,
            settings.data_dir,
            settings.resolved_database_url,
        )
        yield
        core.sources.close()
        engine.dispose()

    app = FastAPI(
        title="xfinance",
        version="0.1.0",
        description="任意标的 × 任意硬通货",
        lifespan=lifespan,
    )
    app.state.core = core
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(api_router, prefix="/api")

    @app.middleware("http")
    async def cache_static_assets(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    build_dir = settings.resolved_frontend_build
    assets = build_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "not_found", "message": "接口不存在"}},
            )
        root = build_dir.resolve()
        candidate = (build_dir / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(
                candidate,
                headers={"Cache-Control": "public, max-age=3600"},
            )
        index = build_dir / "index.html"
        if index.is_file():
            response = HTMLResponse(index.read_text(encoding="utf-8"))
            response.headers["Cache-Control"] = "no-cache"
            return response
        if full_path in {"", "index.html"}:
            return HTMLResponse(FALLBACK_HTML)
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "页面不存在"}},
        )

    return app


def _configure_logging(level: str) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
    )
