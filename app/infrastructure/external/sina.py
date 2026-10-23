"""Sina Finance: global futures daily bars and realtime snapshots."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from loguru import logger

from ...domain.models import Bar, Level, Snapshot
from .base import LiveProvider, ProviderError

_QUOTE_URL = "https://hq.sinajs.cn/list={codes}"
_FUTURES_URL = (
    "https://stock.finance.sina.com.cn/futures/api/jsonp.php/"
    "var%20_{symbol}/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol={symbol}"
)
_HEADERS = {
    "Referer": "https://finance.sina.com.cn/",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) xfinance/0.1",
}
_FUTURES_CODES = {
    "XAUUSD": "GC",
    "XAGUSD": "SI",
    "WTIUSD": "CL",
    "BRENTUSD": "OIL",
}
_REALTIME_CODES = {
    "XAUUSD": "hf_GC",
    "XAGUSD": "hf_SI",
    "WTIUSD": "hf_CL",
    "BRENTUSD": "hf_OIL",
}
_FX_CODES = {
    "USDCNY": ("USDCNY", False),
    "USDJPY": ("USDJPY", False),
    "USDEUR": ("EURUSD", True),
    "USDGBP": ("GBPUSD", True),
    "USDCNH": ("fx_susdcnh", False),
}
_GLOBAL_CODES = {
    "SPX": "gb_$inx",
    "IXIC": "gb_$ixic",
    "DXY": "DINIW",
}
_HK_CODES = {"HK00883": "hk00883"}
_LINE_RE = re.compile(r'var hq_str_([A-Za-z0-9_$]+)="([^"]*)";')
_JSONP_RE = re.compile(r"^[^(]*\((.*)\)\s*;?\s*$", re.DOTALL)


class SinaProvider(LiveProvider):
    source = "sina"

    def __init__(self, timeout: float = 8.0) -> None:
        self.client = httpx.Client(timeout=timeout, headers=_HEADERS)

    def commodity_daily(self, symbol: str) -> list[Bar]:
        code = _FUTURES_CODES.get(symbol)
        if code is None:
            raise ProviderError(f"新浪不提供 {symbol} 日线")
        try:
            response = self.client.get(_FUTURES_URL.format(symbol=code))
            response.raise_for_status()
            match = _JSONP_RE.match(response.text)
            payload = json.loads(match.group(1) if match else response.text)
        except Exception as error:  # pragma: no cover - network dependent
            logger.warning("Sina futures request failed for {}: {}", symbol, error)
            raise ProviderError(f"新浪商品源不可用: {error}") from error
        bars: list[Bar] = []
        for row in payload:
            try:
                day = date.fromisoformat(row["date"])
                close = float(row["close"])
                open_ = float(row.get("open") or close)
                high = float(row.get("high") or close)
                low = float(row.get("low") or close)
                volume = float(row.get("volume") or 0.0)
            except (KeyError, TypeError, ValueError):
                continue
            bars.append(
                Bar(
                    date=day,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )
        if not bars:
            raise ProviderError(f"新浪未返回 {symbol} 日线")
        return bars

    def snapshots(self, symbols: list[str]) -> dict[str, Snapshot]:
        codes: list[str] = []
        for symbol in symbols:
            if symbol in _REALTIME_CODES:
                codes.append(_REALTIME_CODES[symbol])
            elif symbol in _FX_CODES:
                codes.append(_FX_CODES[symbol][0])
            elif symbol == "AU9999":
                codes.append("SGE_AU9999")
            elif symbol in _GLOBAL_CODES:
                codes.append(_GLOBAL_CODES[symbol])
            elif symbol in _HK_CODES:
                codes.append(_HK_CODES[symbol])
        if not codes:
            return {}
        try:
            response = self.client.get(_QUOTE_URL.format(codes=",".join(codes)))
            response.raise_for_status()
            text = response.content.decode("gb18030", errors="replace")
        except Exception as error:  # pragma: no cover - network dependent
            logger.warning("Sina quote request failed: {}", error)
            raise ProviderError(f"新浪快照源不可用: {error}") from error
        raw = {name: value for name, value in _LINE_RE.findall(text)}
        output: dict[str, Snapshot] = {}
        for symbol in symbols:
            if symbol in _REALTIME_CODES:
                snapshot = _parse_commodity(symbol, raw.get(_REALTIME_CODES[symbol]))
            elif symbol in _FX_CODES:
                code, invert = _FX_CODES[symbol]
                snapshot = _parse_fx(symbol, raw.get(code), invert)
            elif symbol == "AU9999":
                snapshot = _parse_sge(raw.get("SGE_AU9999"))
            elif symbol in _GLOBAL_CODES:
                code = _GLOBAL_CODES[symbol]
                if symbol == "DXY":
                    snapshot = _parse_dxy(raw.get(code))
                else:
                    snapshot = _parse_global_index(symbol, raw.get(code))
            elif symbol in _HK_CODES:
                snapshot = _parse_hk(symbol, raw.get(_HK_CODES[symbol]))
            else:
                snapshot = None
            if snapshot is not None:
                output[symbol] = snapshot
        return output

    def close(self) -> None:
        self.client.close()


def _parse_commodity(symbol: str, value: str | None) -> Snapshot | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) < 14:
        return None
    last = _float(parts, 0)
    previous = _float(parts, 7) or last
    if last is None or last <= 0:
        return None
    step = last * 0.001
    return Snapshot(
        symbol=symbol,
        name=parts[13] or symbol,
        last=last,
        prev_close=previous,
        open=_float(parts, 8) or last,
        high=_float(parts, 4) or last,
        low=_float(parts, 5) or last,
        volume=_float(parts, 9) or 0.0,
        amount=0.0,
        ts=_timestamp(parts[12] if len(parts) > 12 else "", parts[6] if len(parts) > 6 else ""),
        bids=tuple(Level(last - step * index, 0.0) for index in range(1, 6)),
        asks=tuple(Level(last + step * index, 0.0) for index in range(1, 6)),
        source="sina",
    )


def _parse_fx(symbol: str, value: str | None, invert: bool) -> Snapshot | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) < 9:
        return None
    last = _float(parts, 8)
    previous = _float(parts, 3)
    if last is None or last <= 0:
        return None
    source_open = _float(parts, 5)
    source_high = _float(parts, 6)
    source_low = _float(parts, 7)
    if invert:
        last = 1.0 / last
        previous = 1.0 / previous if previous else last
        open_ = _inverse(source_open, last)
        high = _inverse(source_low, last)
        low = _inverse(source_high, last)
    else:
        open_ = source_open or last
        high = source_high or last
        low = source_low or last
    high = max(high, open_, last)
    low = min(low, open_, last)
    return Snapshot(
        symbol=symbol,
        name=parts[9] if len(parts) > 9 else symbol,
        last=last,
        prev_close=previous or last,
        open=open_,
        high=high,
        low=low,
        volume=0.0,
        amount=0.0,
        ts=_timestamp(parts[10] if len(parts) > 10 else "", parts[0]),
        source="sina",
    )


def _parse_global_index(symbol: str, value: str | None) -> Snapshot | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) < 12:
        return None
    last = _float(parts, 1)
    change = _float(parts, 4)
    if last is None or last <= 0:
        return None
    previous = last - change if change is not None else last
    return Snapshot(
        symbol=symbol,
        name=parts[0] or symbol,
        last=last,
        prev_close=previous,
        open=_float(parts, 5) or last,
        high=_float(parts, 6) or last,
        low=_float(parts, 7) or last,
        volume=_float(parts, 10) or 0.0,
        amount=_float(parts, 11) or 0.0,
        ts=_timestamp(parts[3][:10], parts[3][11:19] if len(parts[3]) > 10 else ""),
        source="sina",
    )


def _parse_dxy(value: str | None) -> Snapshot | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) < 11:
        return None
    last = _float(parts, 1)
    if last is None or last <= 0:
        return None
    return Snapshot(
        symbol="DXY",
        name=parts[9] or "美元指数",
        last=last,
        prev_close=_float(parts, 3) or last,
        open=_float(parts, 5) or last,
        high=_float(parts, 6) or last,
        low=_float(parts, 7) or last,
        volume=0.0,
        amount=0.0,
        ts=_timestamp(parts[10], parts[0]),
        source="sina",
    )


def _parse_hk(symbol: str, value: str | None) -> Snapshot | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) < 19:
        return None
    last = _float(parts, 6)
    if last is None or last <= 0:
        return None
    day = parts[17].replace("/", "-")
    return Snapshot(
        symbol=symbol,
        name=parts[1] or symbol,
        last=last,
        prev_close=_float(parts, 3) or last,
        open=_float(parts, 2) or last,
        high=_float(parts, 4) or last,
        low=_float(parts, 5) or last,
        volume=_float(parts, 11) or 0.0,
        amount=_float(parts, 12) or 0.0,
        ts=_timestamp(day, parts[18]),
        source="sina",
    )


def _parse_sge(value: str | None) -> Snapshot | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) < 17:
        return None
    last = _float(parts, 3)
    previous = _float(parts, 9) or last
    if last is None or last <= 0:
        return None
    return Snapshot(
        symbol="AU9999",
        name="上金所 Au99.99",
        last=last,
        prev_close=previous,
        open=last,
        high=_float(parts, 7) or last,
        low=_float(parts, 8) or last,
        volume=_float(parts, 14) or 0.0,
        amount=_float(parts, 15) or 0.0,
        ts=_timestamp(parts[16][:10] if len(parts) > 16 else "", parts[16][11:19] if len(parts) > 16 else ""),
        source="sina",
    )


def _inverse(value: float | None, fallback: float) -> float:
    if value is None or value <= 0:
        return fallback
    return 1.0 / value


def _float(parts: list[str], index: int) -> float | None:
    if index >= len(parts):
        return None
    try:
        return float(parts[index])
    except (TypeError, ValueError):
        return None


def _timestamp(day: str, clock: str) -> datetime:
    try:
        return datetime.fromisoformat(f"{day}T{clock[:8]}")
    except ValueError:
        return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
