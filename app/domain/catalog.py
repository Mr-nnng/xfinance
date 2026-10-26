"""Instrument catalog and numeraire registry.

Everything that answers "what can I look at, and what can I price it in"
lives here, as data rather than branch chains in services.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .models import SeriesMeta

NumeraireKind = Literal["unit", "fiat", "asset"]


@dataclass(frozen=True, slots=True)
class Numeraire:
    id: str
    label: str
    group: str
    unit: str
    kind: NumeraireKind
    series: str | None = None
    currency: str = "USD"


NUMERAIRES: tuple[Numeraire, ...] = (
    Numeraire("CNY", "人民币", "法币", "元", "fiat", series="USDCNY", currency="CNY"),
    Numeraire("USD", "美元", "法币", "美元", "unit"),
    Numeraire("JPY", "日元", "法币", "日元", "fiat", series="USDJPY", currency="JPY"),
    Numeraire("EUR", "欧元", "法币", "欧元", "fiat", series="USDEUR", currency="EUR"),
    Numeraire("GBP", "英镑", "法币", "英镑", "fiat", series="USDGBP", currency="GBP"),
    Numeraire("HKD", "港币", "法币", "港币", "fiat", series="USDHKD", currency="HKD"),
    Numeraire("XAU", "黄金", "贵金属", "盎司", "asset", series="XAUUSD", currency="USD"),
    Numeraire(
        "XAU_CNY_G",
        "上金所金",
        "贵金属",
        "克",
        "asset",
        series="AU9999",
        currency="CNY",
    ),
    Numeraire("XAG", "白银", "贵金属", "盎司", "asset", series="XAGUSD", currency="USD"),
    Numeraire("WTI", "WTI 原油", "能源", "桶", "asset", series="WTIUSD", currency="USD"),
    Numeraire(
        "BRENT", "布伦特原油", "能源", "桶", "asset", series="BRENTUSD", currency="USD"
    ),
)

NUMERAIRE_BY_ID: dict[str, Numeraire] = {item.id: item for item in NUMERAIRES}

FX_SERIES: dict[str, tuple[str, str]] = {
    "USDCNY": ("美元/人民币", "CNY"),
    "USDJPY": ("美元/日元", "JPY"),
    "USDEUR": ("美元/欧元", "EUR"),
    "USDGBP": ("美元/英镑", "GBP"),
    "USDHKD": ("美元/港币", "HKD"),
}

COMMODITY_SERIES: dict[str, tuple[str, str, str]] = {
    "XAUUSD": ("COMEX 黄金", "美元/盎司", "USD"),
    "XAGUSD": ("COMEX 白银", "美元/盎司", "USD"),
    "WTIUSD": ("WTI 原油", "美元/桶", "USD"),
    "BRENTUSD": ("布伦特原油当月连续", "美元/桶", "USD"),
    "AU9999": ("黄金9999", "元/克", "CNY"),
}

# Offshore CNY has no ECB/Frankfurter series; it comes from a separate provider.
CNH_SERIES: dict[str, tuple[str, str]] = {
    "USDCNH": ("美元兑离岸人民币", "CNY"),
}

US_INDEX_SERIES: dict[str, str] = {
    "DJI": "道琼斯",
    "SPX": "标普500",
    "IXIC": "纳斯达克",
}

GLOBAL_INDEX_SERIES: dict[str, str] = {
    "DXY": "美元指数",
}

HK_SERIES: dict[str, tuple[str, str]] = {
    "HK00883": ("中国海洋石油", "stock"),
    "HSI": ("恒生指数", "index"),
}

INVERSE_FX_SERIES: dict[str, tuple[str, str, str]] = {
    "EURUSD": ("欧元/美元", "USDEUR", "USD"),
    "GBPUSD": ("英镑/美元", "USDGBP", "USD"),
}

CNBC_SERIES: frozenset[str] = frozenset(
    {"DJI", "SPX", "IXIC", "DXY", "HSI", "HK00883", "USDCNH"}
)

# Treasury CSV column -> (display name, symbol)
YIELD_TENORS: tuple[tuple[str, str, str], ...] = (
    ("1 Yr", "UST1Y", "美债 1 年期"),
    ("2 Yr", "UST2Y", "美债 2 年期"),
    ("3 Yr", "UST3Y", "美债 3 年期"),
    ("5 Yr", "UST5Y", "美债 5 年期"),
    ("7 Yr", "UST7Y", "美债 7 年期"),
    ("10 Yr", "UST10Y", "美债 10 年期"),
    ("20 Yr", "UST20Y", "美债 20 年期"),
    ("30 Yr", "UST30Y", "美债 30 年期"),
)

INDEX_SERIES: dict[str, str] = {
    "SH000001": "上证指数",
    "SZ399001": "深证成指",
    "SZ399006": "创业板指",
    "SH000300": "沪深300",
    "SH000905": "中证500",
    "SH000016": "上证50",
}

FEATURED: dict[str, tuple[str, str]] = {
    "SH600519": ("贵州茅台", "stock"),
    "SH601318": ("中国平安", "stock"),
    "SH600036": ("招商银行", "stock"),
    "SH601899": ("紫金矿业", "stock"),
    "SZ000001": ("平安银行", "stock"),
    "SZ000858": ("五粮液", "stock"),
    "SZ300750": ("宁德时代", "stock"),
    "SZ002594": ("比亚迪", "stock"),
    "SH510300": ("沪深300ETF", "etf"),
    "SH588000": ("科创50ETF", "etf"),
    "SZ159915": ("创业板ETF", "etf"),
    "SH501050": ("华夏上证50LOF", "lof"),
    "SH600900": ("长江电力", "stock"),
    "SH600938": ("中国海油", "stock"),
    "SZ160723": ("嘉实原油LOF", "lof"),
}

DEFAULT_WATCHLIST: tuple[str, ...] = (
    "SH000001",
    "SZ399001",
    "SZ399006",
    "SPX",
    "IXIC",
    "SH600036",
    "SH600900",
    "SZ160723",
    "HK00883",
    "SH600938",
    "UST3Y",
    "UST5Y",
    "UST30Y",
    "UST20Y",
    "UST10Y",
    "AU9999",
    "WTIUSD",
    "BRENTUSD",
    "XAUUSD",
    "USDCNH",
    "USDJPY",
    "DXY",
)

OVERVIEW_INDICES: tuple[str, ...] = (
    "SH000001",
    "SZ399001",
    "SZ399006",
    "SH000016",
    "SPX",
    "IXIC",
    "DJI",
    "HSI",
)
OVERVIEW_FX: tuple[str, ...] = (
    "DXY",
    "EURUSD",
    "USDJPY",
    "GBPUSD",
    "USDCNY",
    "USDCNH",
    "USDHKD",
)
OVERVIEW_COMMODITIES: tuple[str, ...] = (
    "XAUUSD",
    "XAGUSD",
    "WTIUSD",
    "BRENTUSD",
    "AU9999",
)
OVERVIEW_YIELDS: tuple[str, ...] = ("UST1Y", "UST5Y", "UST10Y", "UST30Y")


def series_meta(symbol: str) -> SeriesMeta | None:
    """Static metadata for non-equity series and known indices."""
    if symbol in CNH_SERIES:
        name, quote_currency = CNH_SERIES[symbol]
        return SeriesMeta(
            symbol=symbol,
            name=name,
            kind="fx",
            market="FX",
            currency=quote_currency,
            unit=quote_currency,
            chart="candlestick",
        )
    if symbol in US_INDEX_SERIES:
        return SeriesMeta(
            symbol=symbol,
            name=US_INDEX_SERIES[symbol],
            kind="index",
            market="US",
            currency="USD",
            unit="点",
            chart="candlestick",
        )
    if symbol in GLOBAL_INDEX_SERIES:
        return SeriesMeta(
            symbol=symbol,
            name=GLOBAL_INDEX_SERIES[symbol],
            kind="index",
            market="GLOBAL",
            currency="USD",
            unit="点",
            chart="candlestick",
        )
    if symbol in HK_SERIES:
        name, kind = HK_SERIES[symbol]
        return SeriesMeta(
            symbol=symbol,
            name=name,
            kind=kind,  # type: ignore[arg-type]
            market="HK",
            currency="HKD",
            unit="点" if kind == "index" else "股",
            chart="candlestick",
        )
    if symbol in INVERSE_FX_SERIES:
        name, _base, currency = INVERSE_FX_SERIES[symbol]
        return SeriesMeta(
            symbol=symbol,
            name=name,
            kind="fx",
            market="FX",
            currency=currency,
            unit=currency,
            chart="line",
        )
    if symbol in FX_SERIES:
        name, quote_currency = FX_SERIES[symbol]
        return SeriesMeta(
            symbol=symbol,
            name=name,
            kind="fx",
            market="FX",
            currency=quote_currency,
            unit=quote_currency,
            chart="line",
        )
    if symbol in COMMODITY_SERIES:
        name, unit, currency = COMMODITY_SERIES[symbol]
        return SeriesMeta(
            symbol=symbol,
            name=name,
            kind="commodity",
            market="GLOBAL",
            currency=currency,
            unit=unit,
            chart="candlestick",
        )
    for column, code, label in YIELD_TENORS:
        if code == symbol:
            return SeriesMeta(
                symbol=code,
                name=label,
                kind="yield",
                market="UST",
                currency="%",
                unit="%",
                chart="line",
                quotable=False,
            )
    if symbol in INDEX_SERIES:
        return SeriesMeta(
            symbol=symbol,
            name=INDEX_SERIES[symbol],
            kind="index",
            market=symbol[:2],
            currency="CNY",
            unit="点",
        )
    if symbol in FEATURED:
        name, kind = FEATURED[symbol]
        return SeriesMeta(
            symbol=symbol,
            name=name,
            kind=kind,  # type: ignore[arg-type]
            market=symbol[:2],
            currency="CNY",
            unit="份" if kind in {"etf", "lof"} else "股",
        )
    return None


def infer_meta(symbol: str, name: str | None = None) -> SeriesMeta:
    """Best-effort metadata for an equity symbol discovered at runtime."""
    known = series_meta(symbol)
    if known:
        return known
    if symbol.startswith("HK") and len(symbol) == 7 and symbol[2:].isdigit():
        return SeriesMeta(
            symbol=symbol,
            name=name or symbol,
            kind="stock",
            market="HK",
            currency="HKD",
            unit="股",
        )
    market = symbol[:2] if symbol[:2] in {"SH", "SZ", "BJ"} else "SH"
    return SeriesMeta(
        symbol=symbol,
        name=name or symbol,
        kind="stock",
        market=market,
        currency="CNY",
        unit="股",
    )


def market_of(symbol: str) -> str:
    return symbol[:2] if symbol[:2] in {"SH", "SZ", "BJ"} else ""


def normalize_symbol(raw: str) -> str:
    value = raw.strip().upper().replace(" ", "")
    if not value:
        return value
    if "." in value:
        code, _, market = value.partition(".")
        if market in {"SH", "SZ", "BJ"} and len(code) == 6 and code.isdigit():
            return f"{market}{code}"
        if market == "HK" and len(code) == 5 and code.isdigit():
            return f"HK{code}"
    if value[:2] in {"SH", "SZ", "BJ"} and len(value) == 8 and value[2:].isdigit():
        return value
    if value.isdigit() and len(value) == 6:
        return f"{'SH' if value[0] in '569' else 'SZ'}{value}"
    if value.isdigit() and len(value) == 5:
        return f"HK{value}"
    return value


def numeraire_by_id(raw: str | None) -> Numeraire:
    if not raw:
        return NUMERAIRE_BY_ID["CNY"]
    return NUMERAIRE_BY_ID.get(raw.upper(), NUMERAIRE_BY_ID["CNY"])
