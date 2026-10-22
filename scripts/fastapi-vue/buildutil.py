"""Build the Vue app into app/frontend-build.

Usable from the Hatch build hook, the dev server, or directly:

    uv run python scripts/fastapi-vue/buildutil.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
OUT_DIR = ROOT / "app" / "frontend-build"


def npm_executable() -> str:
    return "npm.cmd" if shutil.which("npm.cmd") else "npm"


def build_frontend(
    root: str | Path = ROOT, *, install: bool = True, log: bool = True
) -> list[Path]:
    root = Path(root)
    frontend = root / "frontend"
    out_dir = root / "app" / "frontend-build"
    package_json = frontend / "package.json"
    if not package_json.exists():
        return []
    if install:
        install_frontend(root, log=log)
    _run(
        [
            npm_executable(),
            "run",
            "build",
            "--",
            "--outDir",
            str(out_dir),
            "--emptyOutDir",
        ],
        frontend,
        log,
    )
    if not (out_dir / "index.html").is_file():
        raise RuntimeError(f"frontend build did not produce {out_dir / 'index.html'}")
    return sorted(path for path in out_dir.rglob("*") if path.is_file())


def install_frontend(root: str | Path = ROOT, *, log: bool = True) -> None:
    frontend = Path(root) / "frontend"
    if (frontend / "node_modules").exists():
        return
    _run([npm_executable(), "install", "--no-audit", "--no-fund"], frontend, log)


def _run(command: list[str], cwd: Path, log: bool) -> None:
    if log:
        print(f"[build] {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


if __name__ == "__main__":
    files = build_frontend()
    print(f"built {len(files)} files into {OUT_DIR}")
    sys.exit(0 if files else 1)
