"""CLI entry point: run the bundled FastAPI app with uvicorn."""

from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path

import uvicorn


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="xfinance-app", description="xfinance 个人股票查看器"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=28473)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument(
        "--data-mode",
        choices=["auto", "live", "demo"],
        default=None,
        help="auto 优先真实数据，失败时回退演示数据",
    )
    parser.add_argument("--reload", action="store_true", help="开发热重载")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--log-level", default="info")
    parser.add_argument("--version", action="store_true")
    args = parser.parse_args(argv)

    if args.version:
        from . import __version__

        print(__version__)
        return

    if args.data_dir:
        os.environ["XFINANCE_DATA_DIR"] = str(args.data_dir.expanduser().resolve())
    if args.data_mode:
        os.environ["XFINANCE_DATA_MODE"] = args.data_mode
    os.environ.setdefault("XFINANCE_LOG_LEVEL", args.log_level.upper())

    host = args.host
    browse_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    url = f"http://{browse_host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "app.app:create_app",
        factory=True,
        host=host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
