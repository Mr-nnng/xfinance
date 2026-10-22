"""Process helpers for the dev orchestrator."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import NoReturn


def wait_for_http(url: str, timeout: float = 60.0, interval: float = 0.4) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(interval)
    return False


def npm_executable() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def spawn(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    name: str,
) -> subprocess.Popen:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    print(f"[dev] {name}: {' '.join(command)}", flush=True)
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=merged,
        stdout=None,
        stderr=None,
        start_new_session=(os.name != "nt"),
    )


def stop(process: subprocess.Popen | None, name: str) -> None:
    if process is None or process.poll() is not None:
        return
    print(f"[dev] stopping {name}", flush=True)
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            if os.name != "nt":
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


def fail(message: str) -> NoReturn:
    print(f"[dev] {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)
