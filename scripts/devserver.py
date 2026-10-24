#!/usr/bin/env python3
"""Start FastAPI and Vite together with one command.

    uv run python scripts/devserver.py
    uv run python scripts/devserver.py --build-only
    uv run python scripts/devserver.py --backend-only
"""

from __future__ import annotations

import argparse
import signal
import socket
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "fastapi-vue"))

from buildutil import build_frontend, npm_executable
from devutil import fail, spawn, stop, wait_for_http


def port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
        return True


def _interrupt(_signum, _frame):
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, _interrupt)
    parser = argparse.ArgumentParser(description="xfinance 开发服务器")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=28473)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--data-mode", choices=["auto", "live", "demo"], default="auto")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--build", action="store_true", help="启动前构建前端")
    parser.add_argument("--build-only", action="store_true", help="只构建前端后退出")
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--frontend-only", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-install", action="store_true", help="不自动 npm install")
    args = parser.parse_args(argv)

    frontend = ROOT / "frontend"
    if not (frontend / "package.json").is_file():
        fail("frontend/package.json 不存在")

    if (args.build or args.build_only) and not args.frontend_only:
        build_frontend(ROOT, install=not args.no_install)

    if args.build_only:
        print("[dev] frontend built into app/frontend-build")
        return 0

    if not args.no_install and not (frontend / "node_modules").exists():
        print("[dev] installing frontend dependencies…", flush=True)
        from buildutil import install_frontend

        install_frontend(ROOT)

    backend = None
    vite = None
    try:
        if not args.frontend_only:
            if not port_free(args.host, args.backend_port):
                fail(f"后端端口 {args.host}:{args.backend_port} 已被占用")
            command = [
                sys.executable,
                "-m",
                "app",
                "--host",
                args.host,
                "--port",
                str(args.backend_port),
                "--data-mode",
                args.data_mode,
                "--no-browser",
            ]
            if args.data_dir:
                command += ["--data-dir", str(args.data_dir)]
            backend = spawn(command, cwd=ROOT, name="backend")
            if not wait_for_http(
                f"http://127.0.0.1:{args.backend_port}/api/health", timeout=45
            ):
                fail("后端启动超时。检查端口、依赖或 XFINANCE_DATA_DIR 权限。")
            print(
                f"[dev] backend ready: http://127.0.0.1:{args.backend_port}",
                flush=True,
            )

        if not args.backend_only:
            if not port_free(args.host, args.frontend_port):
                fail(f"前端端口 {args.host}:{args.frontend_port} 已被占用")
            vite = spawn(
                [
                    npm_executable(),
                    "run",
                    "dev",
                    "--",
                    "--host",
                    args.host,
                    "--port",
                    str(args.frontend_port),
                ],
                cwd=frontend,
                env={
                    "FASTAPI_URL": f"http://127.0.0.1:{args.backend_port}",
                },
                name="vite",
            )
            if not wait_for_http(
                f"http://127.0.0.1:{args.frontend_port}/", timeout=45
            ):
                fail("Vite 启动超时。检查 frontend/node_modules 与端口占用。")
            url = f"http://{args.host}:{args.frontend_port}"
            print(f"[dev] app ready: {url}", flush=True)
            if not args.no_browser:
                webbrowser.open(url)

        while True:
            if backend is not None and backend.poll() is not None:
                print("[dev] backend exited", file=sys.stderr)
                return backend.returncode or 1
            if vite is not None and vite.poll() is not None:
                print("[dev] vite exited", file=sys.stderr)
                return vite.returncode or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        stop(vite, "vite")
        stop(backend, "backend")


if __name__ == "__main__":
    raise SystemExit(main())
