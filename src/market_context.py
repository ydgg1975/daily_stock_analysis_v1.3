# -*- coding: utf-8 -*-
"""LLM 프롬프트용 시장 감지와 시장별 안내 문구."""

import re
from typing import Optional


def detect_market(stock_code: Optional[str]) -> str:
    """종목 코드에서 시장을 감지한다."""
    if not stock_code:
        return "cn"

    code = stock_code.strip().upper()

    if re.match(r"^(KR|KS|KQ)\d{6}$", code) or re.match(r"^\d{6}\.(KS|KQ)$", code):
        return "kr"

    if re.match(r"^(CN|SH|SZ|BJ)\d{6}$", code) or re.match(r"^\d{6}\.(CN|SH|SZ|SS|BJ)$", code):
        return "cn"

    if code.startswith("HK") or code.endswith(".HK"):
        return "hk"
    if code.isdigit() and len(code) == 5:
        return "hk"

    if re.match(r"^[A-Z]{1,5}(\.[A-Z]{1,2})?$", code):
        return "us"

    return "cn"


_MARKET_ROLES = {
    "cn": {
        "zh": "China A-shares",
        "en": "China A-shares",
        "ko": "중국 A주",
    },
    "hk": {
        "zh": "Hong Kong stock",
        "en": "Hong Kong stock",
        "ko": "홍콩 주식",
    },
    "us": {
        "zh": "US stock",
        "en": "US stock",
        "ko": "미국 주식",
    },
    "kr": {
        "zh": "Korean stock",
        "en": "Korean stock",
        "ko": "한국 주식",
    },
}

_MARKET_GUIDELINES = {
    "cn": {
        "zh": "- This analysis covers China A-shares.\n- Consider daily price limits, T+1 settlement, liquidity, and policy factors.",
        "en": "- This analysis covers China A-shares.\n- Consider daily price limits, T+1 settlement, liquidity, and policy factors.",
        "ko": "- 이번 분석 대상은 중국 A주입니다.\n- 가격 제한, T+1 제도, 유동성, 정책 변수를 함께 고려하세요.",
    },
    "hk": {
        "zh": "- This analysis covers Hong Kong stocks.\n- Consider HKD FX, southbound flows, liquidity, and HKEX rules.",
        "en": "- This analysis covers Hong Kong stocks.\n- Consider HKD FX, southbound flows, liquidity, and HKEX rules.",
        "ko": "- 이번 분석 대상은 홍콩 주식입니다.\n- HKD 환율, 중국 본토 자금 흐름, 유동성, HKEX 규칙을 함께 고려하세요.",
    },
    "us": {
        "zh": "- This analysis covers US stocks.\n- Consider USD FX, Fed policy, sector rotation, earnings, and SEC rules.",
        "en": "- This analysis covers US stocks.\n- Consider USD FX, Fed policy, sector rotation, earnings, and SEC rules.",
        "ko": "- 이번 분석 대상은 미국 주식입니다.\n- USD 환율, 연준 정책, 섹터 로테이션, 실적, SEC 규제를 함께 고려하세요.",
    },
    "kr": {
        "zh": "- This analysis covers Korean stocks.\n- Consider KRW FX, KOSPI/KOSDAQ direction, foreign/institutional flows, earnings, and local policy.",
        "en": "- This analysis covers Korean stocks.\n- Consider KRW FX, KOSPI/KOSDAQ direction, foreign/institutional flows, earnings, and local policy.",
        "ko": "- 이번 분석 대상은 한국 주식입니다.\n- 원화 환율, KOSPI/KOSDAQ 흐름, 외국인/기관 수급, 실적, 국내 정책 변수를 함께 고려하세요.",
    },
}


def get_market_role(stock_code: Optional[str], lang: str = "zh") -> str:
    """LLM 프롬프트에 넣을 시장별 역할 이름을 반환한다."""
    market = detect_market(stock_code)
    lang_key = lang if lang in {"zh", "en", "ko"} else "zh"
    return _MARKET_ROLES.get(market, _MARKET_ROLES["cn"])[lang_key]


def get_market_guidelines(stock_code: Optional[str], lang: str = "zh") -> str:
    """LLM 프롬프트에 넣을 시장별 분석 지침을 반환한다."""
    market = detect_market(stock_code)
    lang_key = lang if lang in {"zh", "en", "ko"} else "zh"
    return _MARKET_GUIDELINES.get(market, _MARKET_GUIDELINES["cn"])[lang_key]
