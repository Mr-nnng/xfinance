#!/usr/bin/env bash
# xfinance one-click launcher for Linux.

set -euo pipefail
cd "$(dirname "$0")"

export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.uvcache}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$PWD/.uvpython}"
export npm_config_cache="${npm_config_cache:-$PWD/.npmcache}"

pause_on_error() {
  if [ -t 0 ]; then
    echo
    read -r -p "启动失败，按回车关闭窗口..." _
  fi
}

fail() {
  echo
  echo "启动失败：$*" >&2
  pause_on_error
  exit 1
}

if ! command -v uv >/dev/null 2>&1; then
  echo "没有找到 uv，正在用官方脚本安装..."
  command -v curl >/dev/null 2>&1 || fail "缺少 curl，无法自动安装 uv。请先安装 uv：https://docs.astral.sh/uv/"
  curl -LsSf https://astral.sh/uv/install.sh | sh || fail "uv 安装失败"
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

command -v uv >/dev/null 2>&1 || fail "uv 安装后仍不在 PATH 中，请重新打开终端后再试"

echo "同步 Python 依赖..."
uv sync || fail "uv sync 失败"

if [ ! -f "app/frontend-build/index.html" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    fail "缺少前端构建，且没有 Node.js/npm。请安装 Node.js 20.19+ 或 22.12+ 后重试。"
  fi
  echo "首次启动，构建前端..."
  uv run python scripts/devserver.py --build-only || fail "前端构建失败"
fi

HOST="${XFINANCE_HOST:-127.0.0.1}"
PORT="${XFINANCE_PORT:-8000}"
DATA_MODE="${XFINANCE_DATA_MODE:-auto}"
ARGS=(--host "$HOST" --port "$PORT" --data-mode "$DATA_MODE")
if [ -n "${XFINANCE_DATA_DIR:-}" ]; then
  ARGS+=(--data-dir "$XFINANCE_DATA_DIR")
fi

echo
echo "启动 xfinance：http://$HOST:$PORT"
echo "按 Ctrl+C 停止。"
echo
set +e
uv run xfinance-app "${ARGS[@]}" "$@"
status=$?
set -e
if [ "$status" -ne 0 ] && [ "$status" -ne 130 ]; then
  echo
  echo "xfinance 退出，状态码 $status。" >&2
  pause_on_error
fi
exit "$status"
