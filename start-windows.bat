@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not defined UV_CACHE_DIR set "UV_CACHE_DIR=%CD%\.uvcache"
if not defined UV_PYTHON_INSTALL_DIR set "UV_PYTHON_INSTALL_DIR=%CD%\.uvpython"
if not defined npm_config_cache set "npm_config_cache=%CD%\.npmcache"

where uv >nul 2>nul
if errorlevel 1 (
  echo 没有找到 uv，正在用官方脚本安装...
  powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
  set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"
)
where uv >nul 2>nul
if errorlevel 1 goto :no_uv

echo 同步 Python 依赖...
uv sync
if errorlevel 1 goto :failed

if not exist "app\frontend-build\index.html" (
  where npm >nul 2>nul
  if errorlevel 1 goto :no_node
  echo 首次启动，构建前端...
  uv run python scripts\devserver.py --build-only
  if errorlevel 1 goto :failed
)

if defined XFINANCE_HOST (set "HOST=%XFINANCE_HOST%") else (set "HOST=127.0.0.1")
if defined XFINANCE_PORT (set "PORT=%XFINANCE_PORT%") else (set "PORT=28473")
if defined XFINANCE_DATA_MODE (set "DATA_MODE=%XFINANCE_DATA_MODE%") else (set "DATA_MODE=auto")
set "DATA_ARGS="
if defined XFINANCE_DATA_DIR set DATA_ARGS=--data-dir "%XFINANCE_DATA_DIR%"

echo.
echo 启动 xfinance：http://%HOST%:%PORT%
echo 按 Ctrl+C 停止。
echo.
uv run xfinance-app --host "%HOST%" --port "%PORT%" --data-mode "%DATA_MODE%" %DATA_ARGS% %*
if errorlevel 1 goto :failed
exit /b 0

:no_uv
echo.
echo 启动失败：uv 安装后仍不在 PATH 中，请重新打开此窗口。
goto :pause

:no_node
echo.
echo 启动失败：缺少前端构建，且没有 Node.js/npm。
echo 请安装 Node.js 20.19+ 或 22.12+ 后重试。
goto :pause

:failed
echo.
echo xfinance 启动失败。
:pause
pause
exit /b 1
