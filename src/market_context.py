# -*- coding: utf-8 -*-
"""
Market context detection for LLM prompts.

Detects the market (KR, US, HK, CN) from a stock code and returns
market-specific role descriptions so prompts are not hardcoded to a
single market.

Fixes: https://github.com/ZhuLinsen/daily_stock_analysis/issues/644
"""

import re
from typing import Optional

KNOWN_BARE_KR_CODES = {"000660", "005930"}


def detect_market(stock_code: Optional[str]) -> str:
    """Detect market from stock code.

    Returns:
        One of 'kr', 'us', 'hk', 'cn', or 'kr' as fallback.
    """
    if not stock_code:
        return "cn"

    code = stock_code.strip().upper()

    if code.endswith((".KS", ".KQ")):
        return "kr"
    if code.startswith(("KR", "KS", "KQ")) and code[2:].isdigit() and len(code[2:]) == 6:
        return "kr"
    if code in KNOWN_BARE_KR_CODES:
        return "kr"

    # HK stocks: HK00700, 00700.HK, or 5-digit pure numbers
    if code.startswith("HK") or code.endswith(".HK"):
        return "hk"
    lower = code.lower()
    if lower.endswith(".hk"):
        return "hk"
    # 5-digit pure numbers are HK (A-shares are 6-digit)
    if code.isdigit() and len(code) == 5:
        return "hk"

    # US stocks: 1-5 uppercase letters (AAPL, TSLA, GOOGL)
    # Also handles suffixed forms like BRK.B
    if re.match(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$', code):
        return "us"

    return "cn"


# -- Market-specific role descriptions --

_MARKET_ROLES = {
    "cn": {
        "zh": " A 股",
        "en": "China A-shares",
    },
    "hk": {
        "zh": "港股",
        "en": "Hong Kong stock",
    },
    "us": {
        "zh": "美股",
        "en": "US stock",
    },
    "kr": {
        "zh": "韩国股票",
        "en": "Korean stock",
    },
}

_MARKET_GUIDELINES = {
    "cn": {
        "zh": (
            "- 本次分析对象为 **A 股**（中国沪深交易所上市股票）。\n"
            "- 请关注 A 股特有的涨跌停机制（±10%/±20%/±30%）、T+1 交易制度及相关政策因素。"
        ),
        "en": (
            "- This analysis covers a **China A-share** (listed on Shanghai/Shenzhen exchanges).\n"
            "- Consider A-share-specific rules: daily price limits (±10%/±20%/±30%), T+1 settlement, and PRC policy factors."
        ),
    },
    "hk": {
        "zh": (
            "- 本次分析对象为 **港股**（香港交易所上市股票）。\n"
            "- 港股无涨跌停限制，支持 T+0 交易，需关注港币汇率、南北向资金流及联交所特有规则。"
        ),
        "en": (
            "- This analysis covers a **Hong Kong stock** (listed on HKEX).\n"
            "- HK stocks have no daily price limits, allow T+0 trading. Consider HKD FX, Southbound/Northbound flows, and HKEX-specific rules."
        ),
    },
    "us": {
        "zh": (
            "- 本次分析对象为 **美股**（美国交易所上市股票）。\n"
            "- 美股无涨跌停限制（但有熔断机制），支持 T+0 交易和盘前盘后交易，需关注美元汇率、美联储政策及 SEC 监管动态。"
        ),
        "en": (
            "- This analysis covers a **US stock** (listed on NYSE/NASDAQ).\n"
            "- US stocks have no daily price limits (but have circuit breakers), allow T+0 and pre/after-market trading. Consider USD FX, Fed policy, and SEC regulations."
        ),
    },
    "kr": {
        "zh": (
            "- 本次分析对象为 **韩国股票**（韩国交易所/KOSDAQ 上市股票）。\n"
            "- 请关注韩元汇率、韩国央行政策、半导体/出口周期、公司公告与外资资金流。不要套用中国 A 股的涨跌停和 T+1 规则。"
        ),
        "en": (
            "- This analysis covers a **Korean stock** listed on KRX/KOSDAQ.\n"
            "- Consider KRW FX, Bank of Korea policy, export cycles, company disclosures, and foreign investor flow. Do not apply China A-share price-limit or T+1 assumptions."
        ),
    },
}


def get_market_role(stock_code: Optional[str], lang: str = "zh") -> str:
    """Return market-specific role description for LLM prompt.

    Args:
        stock_code: The stock code being analyzed.
        lang: 'zh' or 'en'.

    Returns:
        Role string like 'A 股投资分析' or 'US stock investment analysis'.
    """
    market = detect_market(stock_code)
    lang_key = "en" if lang == "en" else "zh"
    return _MARKET_ROLES.get(market, _MARKET_ROLES["cn"])[lang_key]


def get_market_guidelines(stock_code: Optional[str], lang: str = "zh") -> str:
    """Return market-specific analysis guidelines for LLM prompt.

    Args:
        stock_code: The stock code being analyzed.
        lang: 'zh' or 'en'.

    Returns:
        Multi-line string with market-specific guidelines.
    """
    market = detect_market(stock_code)
    lang_key = "en" if lang == "en" else "zh"
    return _MARKET_GUIDELINES.get(market, _MARKET_GUIDELINES["cn"])[lang_key]
