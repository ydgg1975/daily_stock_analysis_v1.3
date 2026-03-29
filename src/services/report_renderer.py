# -*- coding: utf-8 -*-
"""
===================================
Report Engine - Jinja2 Report Renderer
===================================

Single-source report rendering pipeline:
1. Build a standard report payload from AnalysisResult
2. Enforce quote/session normalization and consistency checks
3. Render platform-specific templates (markdown/wechat/brief)
"""

from __future__ import annotations

import logging
import math
import re
from datetime import date as calendar_date, datetime, time as clock_time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from data_provider.us_index_mapping import is_us_stock_code
from src.analyzer import AnalysisResult
from src.config import get_config
from src.report_language import (
    get_localized_stock_name,
    get_report_labels,
    get_standard_report_field_label,
    get_signal_level,
    localize_chip_health,
    localize_confidence_level,
    localize_operation_advice,
    localize_sentiment_status,
    localize_trend_prediction,
    normalize_report_language,
)

logger = logging.getLogger(__name__)

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_NUMERIC_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])-?\d+(?:\.\d+)?(?![A-Za-z0-9])")

_ALLOWED_MISSING_REASONS = {
    "当前数据源未提供",
    "当前市场暂不支持",
    "接口未返回",
    "字段待接入",
    "上游映射缺失",
    "口径冲突，待校正",
    "样本不足",
}

_MISSING_MARKERS = {
    "",
    "n/a",
    "na",
    "none",
    "null",
    "nan",
    "数据缺失",
    "-",
    "--",
}

_HIGH_VALUE_NEWS_KEYWORDS = (
    "财报",
    "指引",
    "监管",
    "诉讼",
    "出口限制",
    "合作",
    "订单",
    "供应链",
    "竞争格局",
    "earnings",
    "guidance",
    "regulation",
    "lawsuit",
    "export",
    "partnership",
    "order",
    "supply chain",
    "antitrust",
)

_LOW_VALUE_NEWS_KEYWORDS = (
    "发布会",
    "活动",
    "亮相",
    "品牌曝光",
    "采访",
    "路演",
    "conference",
    "event",
    "appearance",
    "marketing",
    "branding",
)

_MEDIA_INTERPRETATION_KEYWORDS = (
    "解读",
    "媒体",
    "观点",
    "评论",
    "分析师",
    "研报",
    "commentary",
    "analyst",
    "opinion",
    "note",
    "market reaction",
)

_ANNOUNCEMENT_NEWS_KEYWORDS = (
    "公告",
    "发布",
    "披露",
    "申报",
    "press release",
    "announced",
    "announce",
    "filed",
    "8-k",
    "合作",
    "订单",
    "指引",
    "guidance",
)

_NEGATIVE_NEWS_HINTS = (
    "担忧",
    "下滑",
    "放缓",
    "风险",
    "承压",
    "监管",
    "诉讼",
    "negative",
    "risk",
    "slowdown",
    "pressure",
    "lawsuit",
)

_POSITIVE_NEWS_HINTS = (
    "利好",
    "上调",
    "改善",
    "回暖",
    "合作",
    "订单",
    "positive",
    "beat",
    "raised",
    "improved",
    "rebound",
)

_STALE_EARNINGS_NEWS_KEYWORDS = (
    "财报",
    "业绩",
    "earnings",
    "guidance",
    "季度",
    "q1",
    "q2",
    "q3",
    "q4",
)


def _now_shanghai():
    from datetime import datetime

    return datetime.now(_SHANGHAI_TZ)


def _iso_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return None
    text = str(value).strip()
    return text or None


def _to_shanghai_iso(value: Any) -> Optional[str]:
    raw = _iso_or_none(value)
    if not raw:
        return None
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(_SHANGHAI_TZ).isoformat()


def _format_bjt_datetime(value: Any) -> Optional[str]:
    raw = _iso_or_none(value)
    if not raw:
        return None
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_SHANGHAI_TZ)
    return dt.astimezone(_SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _parse_aware_datetime(value: Any) -> Optional[Any]:
    raw = _iso_or_none(value)
    if not raw:
        return None
    from datetime import datetime

    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt


def _format_local_datetime(value: Any) -> Optional[str]:
    dt = _parse_aware_datetime(value)
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z").strip()


def _market_session_date_from_timestamp(value: Any) -> Optional[str]:
    dt = _parse_aware_datetime(value)
    if dt is None:
        return None
    return dt.date().isoformat()


def _normalize_missing_reason(reason: Optional[str]) -> str:
    raw = str(reason or "").strip()
    if not raw:
        return "接口未返回"
    if raw.startswith("NA（") and raw.endswith("）"):
        raw = raw[3:-1].strip()
    lowered = raw.lower()
    if lowered in _MISSING_MARKERS:
        return "接口未返回"
    if raw in _ALLOWED_MISSING_REASONS:
        return raw
    if "冲突" in raw:
        return "口径冲突，待校正"
    return "接口未返回"


def _na(reason: str = "接口未返回") -> str:
    normalized = _normalize_missing_reason(reason)
    return f"NA（{normalized}）"


def _normalize_missing_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return _na("接口未返回")
    if text.startswith("NA（") and text.endswith("）"):
        return _na(text[3:-1])
    if text.lower() in _MISSING_MARKERS:
        return _na("接口未返回")
    return _na(text)


def _is_missing_value(value: Any, *, zero_is_missing: bool = False) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return True
        if text.lower() in _MISSING_MARKERS:
            return True
        try:
            parsed = float(text.rstrip("%"))
        except (TypeError, ValueError):
            return False
        if math.isnan(parsed):
            return True
        if zero_is_missing and parsed == 0:
            return True
        return False
    if isinstance(value, bool):
        return False
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return False
    if math.isnan(parsed):
        return True
    if zero_is_missing and parsed == 0:
        return True
    return False


def _to_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        parsed = float(value)
        return None if math.isnan(parsed) else parsed
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("NA（"):
        return None
    lowered = text.lower()
    if lowered in _MISSING_MARKERS:
        return None
    cleaned = text.replace(",", "")
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1]
    try:
        parsed = float(cleaned)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


def _extract_first_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _to_float(value)
    text = str(value)
    match = _NUMERIC_TOKEN_RE.search(text)
    if not match:
        return None
    return _to_float(match.group(0))


def _format_decimal(value: Any, *, digits: int = 2, reason: str = "接口未返回") -> str:
    number = _to_float(value)
    if number is None:
        return _na(reason)
    return f"{number:.{digits}f}"


def _format_signed_number(value: Any, *, digits: int = 0, reason: str = "接口未返回") -> str:
    number = _to_float(value)
    if number is None:
        return _na(reason)
    if digits <= 0:
        rendered = f"{abs(number):.0f}"
    else:
        rendered = f"{abs(number):.{digits}f}"
    return f"+{rendered}" if number > 0 else (f"-{rendered}" if number < 0 else rendered)


def _format_price(value: Any, *, reason: str = "接口未返回") -> str:
    return _format_decimal(value, digits=2, reason=reason)


def _format_nonzero_price(value: Any, *, reason: str = "接口未返回") -> str:
    if _is_missing_value(value, zero_is_missing=True):
        return _na(reason)
    return _format_price(value, reason=reason)


def _format_amount(value: Any, *, reason: str = "接口未返回") -> str:
    number = _to_float(value)
    if number is None:
        return _na(reason)
    abs_num = abs(number)
    if abs_num >= 1_0000_0000:
        return f"{number / 1_0000_0000:.2f}亿"
    if abs_num >= 1_0000:
        return f"{number / 1_0000:.2f}万"
    return f"{number:.2f}"


def _format_volume(value: Any, *, reason: str = "接口未返回") -> str:
    number = _to_float(value)
    if number is None:
        return _na(reason)
    abs_num = abs(number)
    if abs_num >= 1_0000_0000:
        return f"{number / 1_0000_0000:.2f}亿"
    if abs_num >= 1_0000:
        return f"{number / 1_0000:.2f}万"
    return f"{number:.0f}"


def _format_percent(
    value: Any,
    *,
    reason: str = "接口未返回",
    from_ratio: bool = False,
) -> str:
    if isinstance(value, str) and value.strip().endswith("%"):
        number = _to_float(value)
        if number is None:
            return _na(reason)
        return f"{number:.2f}%"

    number = _to_float(value)
    if number is None:
        return _na(reason)

    if from_ratio and abs(number) <= 10:
        number *= 100
    return f"{number:.2f}%"


def _format_text(value: Any, *, reason: str = "接口未返回") -> str:
    if value is None:
        return _na(reason)
    text = str(value).strip()
    if not text:
        return _na(reason)
    if text.lower() in _MISSING_MARKERS:
        return _na(reason)
    if text.startswith("NA（") and text.endswith("）"):
        return _normalize_missing_text(text)
    return text


def _format_number_token_text(value: Any, *, reason: str = "字段待接入") -> str:
    text = _format_text(value, reason=reason)
    if text.startswith("NA（"):
        return text
    return _NUMERIC_TOKEN_RE.sub(lambda m: f"{float(m.group(0)):.2f}", text)


def _pick_first(payload: Dict[str, Any], candidates: Iterable[str], *, zero_is_missing: bool = False) -> Any:
    for key in candidates:
        if key in payload and not _is_missing_value(payload.get(key), zero_is_missing=zero_is_missing):
            return payload.get(key)
    return None


def _pick_first_from_sources(
    sources: Iterable[Any],
    candidates: Iterable[str],
    *,
    zero_is_missing: bool = False,
) -> Any:
    for payload in sources:
        if not isinstance(payload, dict):
            continue
        value = _pick_first(payload, candidates, zero_is_missing=zero_is_missing)
        if value is not None:
            return value
    return None


def _metric_node_value(metrics: Any, key: str, *, zero_is_missing: bool = False) -> Any:
    if not isinstance(metrics, dict):
        return None
    node = metrics.get(key)
    if isinstance(node, dict):
        status = str(node.get("status") or "").strip().lower()
        if status and status not in {"ok", "available"}:
            return None
        value = node.get("value")
        if _is_missing_value(value, zero_is_missing=zero_is_missing):
            return None
        return value
    return node


def _metric_node_reason(metrics: Any, key: str, default: str = "接口未返回") -> str:
    if not isinstance(metrics, dict):
        return default
    node = metrics.get(key)
    if not isinstance(node, dict):
        return default
    status = str(node.get("status") or "").strip().lower()
    if status == "insufficient_history":
        return "样本不足"
    if status in {"data_unavailable", "provider_unavailable"}:
        return "当前数据源未提供"
    return default


def _pick_first_number_from_sources(
    sources: Iterable[Any],
    candidates: Iterable[str],
    *,
    zero_is_missing: bool = False,
) -> Any:
    for payload in sources:
        if not isinstance(payload, dict):
            continue
        for key in candidates:
            if key not in payload:
                continue
            value = payload.get(key)
            if _is_missing_value(value, zero_is_missing=zero_is_missing):
                continue
            return value
    return None


def _first_quarter_metric(quarterly_series: Any, *keys: str) -> Any:
    if not isinstance(quarterly_series, list):
        return None
    for item in quarterly_series:
        if not isinstance(item, dict):
            continue
        value = _pick_first(item, keys)
        if value is not None:
            return value
    return None


def _normalize_session_type(session_type: Any) -> Tuple[str, str]:
    text = str(session_type or "").strip().lower().replace("-", "_")
    if "pre" in text:
        return "extended", "盘前"
    if "after" in text or "post" in text:
        return "extended", "盘后"
    if "last_completed" in text or "completed_session" in text or "closed" in text:
        return "completed", "上一已收盘交易日"
    if "intraday" in text or "snapshot" in text:
        return "intraday", "盘中快照"
    return "regular", "常规交易时段"


def _describe_price_basis(
    session_kind: str,
    *,
    session_label: str,
    market_session_date: Optional[str],
) -> Dict[str, str]:
    reference_session = (
        f"{market_session_date} regular session"
        if market_session_date
        else "latest available session"
    )
    if session_kind == "intraday":
        return {
            "price_label": "Analysis Price",
            "price_basis": "Intraday snapshot",
            "price_basis_detail": "Captured from a market snapshot during the current session, not streaming tick-by-tick data.",
            "reference_session": reference_session,
            "price_context_note": "Entry, stop, target, support and resistance are anchored to the same intraday snapshot shown above.",
        }
    if session_kind == "extended":
        return {
            "price_label": "Analysis Price",
            "price_basis": "Regular-session close",
            "price_basis_detail": "The analysis stays anchored to the regular-session close. Extended-hours pricing is shown separately.",
            "reference_session": reference_session,
            "price_context_note": "The report stays anchored to the regular close so pre-market or after-hours moves do not overwrite the trading plan baseline.",
        }
    if session_kind == "completed":
        return {
            "price_label": "Analysis Price",
            "price_basis": "Last close",
            "price_basis_detail": "Based on the most recent completed trading session.",
            "reference_session": reference_session,
            "price_context_note": "The trading plan is anchored to the last completed session close and does not pretend to be live pricing.",
        }
    return {
        "price_label": "Analysis Price",
        "price_basis": "Session reference",
        "price_basis_detail": f"Based on the best available quote from {session_label or 'the current session'}.",
        "reference_session": reference_session,
        "price_context_note": "The report’s key trading levels use the same reference price shown above.",
    }


def _humanize_quote_source(raw_source: Any) -> str:
    text = str(raw_source or "").strip()
    if not text:
        return "Upstream quote feed"

    lowered = text.lower()
    if "yfinance" in lowered or lowered in {"yf"}:
        return "YFinance"
    if "akshare" in lowered:
        return "AkShare"
    if "tushare" in lowered:
        return "Tushare"
    if "tickflow" in lowered:
        return "TickFlow"
    if "alpha" in lowered and "vantage" in lowered:
        return "Alpha Vantage"
    if "fmp" in lowered:
        return "FMP"

    words = re.split(r"[_\-\s]+", text)
    return " ".join(word.upper() if len(word) <= 3 else word.capitalize() for word in words if word)


def _describe_market_feed(
    raw_source: Any,
    *,
    session_kind: str,
    selected_bundle_name: str,
) -> str:
    provider = _humanize_quote_source(raw_source)
    if session_kind == "intraday":
        descriptor = "intraday snapshot"
    elif session_kind == "completed":
        descriptor = "last-close feed"
    elif session_kind == "extended":
        descriptor = "regular-session reference"
    elif "realtime" in selected_bundle_name or "snapshot" in selected_bundle_name:
        descriptor = "session snapshot"
    else:
        descriptor = "session reference"
    return f"{provider} · {descriptor}"


def _build_social_digest(
    raw_social_context: Any,
    *,
    company_sentiment: str,
    industry_sentiment: str,
    regulatory_sentiment: str,
    scenario_label: str,
    volume_status: str,
) -> Dict[str, Any]:
    raw_text = str(raw_social_context or "").strip()
    lowered = raw_text.lower()

    def _extract(pattern: str) -> Optional[float]:
        match = re.search(pattern, lowered)
        if not match:
            return None
        try:
            return float(match.group(1).replace(",", ""))
        except Exception:
            return None

    sources: List[str] = []
    if "reddit" in lowered:
        sources.append("Reddit")
    if " twitter" in lowered or " x " in lowered or "\nx" in lowered or "x trending" in lowered:
        sources.append("X / Twitter")
    if "stocktwits" in lowered:
        sources.append("Stocktwits")
    if "polymarket" in lowered:
        sources.append("Polymarket")

    buzz_score = _extract(r"buzz score:\s*([+-]?\d+(?:\.\d+)?)")
    sentiment_score = _extract(r"sentiment score:\s*([+-]?\d+(?:\.\d+)?)")
    mention_count = _extract(r"mentions:\s*([0-9,]+)")
    if mention_count is None:
        mention_count = _extract(r"mention count:\s*([0-9,]+)")

    quoted_focus = [
        re.sub(r"\s+", " ", match).strip()
        for match in re.findall(r"\"([^\"]{16,180})\"", raw_text)
    ]
    focus_items = unique_meaningful_items(quoted_focus, 2)
    focus_text = "、".join(focus_items) if focus_items else ""

    if sentiment_score is not None and sentiment_score >= 0.25:
        tone = "bullish"
        tone_text = "tone leans bullish"
    elif sentiment_score is not None and sentiment_score <= -0.25:
        tone = "bearish"
        tone_text = "tone leans bearish"
    elif regulatory_sentiment == "negative":
        tone = "bearish"
        tone_text = "tone is cautious because regulation remains a drag"
    elif (company_sentiment == "positive" or industry_sentiment == "positive") and sentiment_score is None:
        tone = "bullish"
        tone_text = "tone is constructive"
    elif company_sentiment == "negative" or industry_sentiment == "negative":
        tone = "bearish"
        tone_text = "tone is defensive"
    else:
        tone = "mixed"
        tone_text = "tone is mixed"

    if (
        (buzz_score is not None and buzz_score >= 68)
        or (mention_count is not None and mention_count >= 120)
        or "trending" in lowered
    ):
        attention = "discussion appears elevated"
    elif (
        (buzz_score is not None and buzz_score >= 45)
        or (mention_count is not None and mention_count >= 35)
        or "top mentions" in lowered
        or "放量" in volume_status
    ):
        attention = "attention is event-driven"
    else:
        attention = "retail attention is muted"

    if not focus_text:
        if scenario_label and "突破" in scenario_label:
            focus_text = "突破确认与追价风险"
        elif scenario_label and "回踩" in scenario_label:
            focus_text = "回踩承接与均线防守"
        elif "放量" in volume_status:
            focus_text = "量能是否能继续放大"
        else:
            focus_text = "估值、结构确认与下一步催化"

    if raw_text:
        synthesis = (
            f"综合 {' / '.join(sources) if sources else '零售讨论源'} 的讨论语义：{attention}，{tone_text}，"
            f"当前关注点集中在 {focus_text}。该卡片为 LLM 综合讨论摘要，不等同于已核实硬新闻。"
        )
    else:
        synthesis = (
            f"暂无可直接展示的零售讨论抓取，当前以市场语境补位：{attention}，{tone_text}，"
            f"关注点偏向 {focus_text}。该卡片为 LLM 综合讨论摘要，不等同于已核实硬新闻。"
        )

    return {
        "social_synthesis": synthesis,
        "social_attention": attention,
        "social_tone": tone,
        "social_narrative_focus": focus_text,
        "social_sources": sources,
    }


def _coerce_session_type(code: str, session_type: Any, market_timestamp: Any) -> Any:
    normalized = str(session_type or "").strip()
    if not normalized:
        return session_type
    lowered = normalized.lower().replace("-", "_")
    if any(token in lowered for token in ("pre", "after", "post", "last_completed", "completed_session", "closed")):
        return session_type

    dt = _parse_aware_datetime(market_timestamp)
    if dt is None:
        return session_type

    if is_us_stock_code(code):
        local_dt = dt.astimezone(ZoneInfo("America/New_York")) if dt.tzinfo is not None else dt
        current_time = local_dt.timetz().replace(tzinfo=None)
        if current_time >= clock_time(16, 0):
            return "last_completed_session"
        if current_time < clock_time(9, 30):
            return "last_completed_session"
        return "intraday_snapshot"

    return session_type


def _compute_change(current: Optional[float], prev_close: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if current is None or prev_close in (None, 0):
        return None, None
    change = current - prev_close
    pct = (change / prev_close) * 100
    return change, pct


def _numbers_nearly_equal(a: Optional[float], b: Optional[float], tolerance: float = 0.01) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tolerance


def _has_meaningful_change(value: Optional[float], *, tolerance: float = 0.005) -> bool:
    return value is not None and math.isfinite(value) and abs(value) > tolerance


def _derive_prev_close_from_change(
    close: Optional[float],
    *,
    change_amount: Optional[float] = None,
    change_pct: Optional[float] = None,
) -> Optional[float]:
    if close is None or not math.isfinite(close):
        return None
    if change_amount is not None and math.isfinite(change_amount) and (
        abs(change_amount) > 0.005 or not _has_meaningful_change(change_pct)
    ):
        derived = close - change_amount
        if derived > 0:
            return derived
    if change_pct is not None and math.isfinite(change_pct):
        denominator = 1 + (change_pct / 100.0)
        if abs(denominator) > 1e-9:
            derived = close / denominator
            if math.isfinite(derived) and derived > 0:
                return derived
    return None


def _compute_amplitude_pct(
    high: Optional[float],
    low: Optional[float],
    prev_close: Optional[float],
) -> Optional[float]:
    if high is None or low is None or prev_close in (None, 0):
        return None
    return ((high - low) / abs(prev_close)) * 100


def _conflict(a: Optional[float], b: Optional[float], tolerance: float = 0.05) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) > tolerance


def _material_quote_conflict(
    computed: Optional[float],
    provided: Optional[float],
    *,
    percent: bool = False,
) -> bool:
    if computed is None or provided is None:
        return False
    if computed == provided:
        return False
    if computed != 0 and provided != 0 and ((computed > 0) != (provided > 0)):
        return True

    diff = abs(computed - provided)
    if percent:
        baseline = max(abs(computed), 1.0)
        return diff > 1.0 and (diff / baseline) > 0.35

    baseline = max(abs(computed), 1.0)
    return diff > 0.5 and (diff / baseline) > 0.25


def _normalize_inline_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().strip("-")


def _build_field_map(fields: Optional[List[Dict[str, Any]]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for item in fields or []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        if label:
            mapping[label] = value
    return mapping


def _format_field_source(source: Optional[str]) -> Optional[str]:
    text = str(source or "").strip().lower().replace("-", "_")
    if not text:
        return None
    mapping = {
        "fmp_technical_indicator": "FMP API",
        "fmp_historical_price": "FMP History",
        "fmp": "FMP",
        "fmp_quote": "FMP Quote",
        "fmp_profile": "FMP Profile",
        "fmp_quarterly": "FMP Statements",
        "fmp_latest_quarter": "FMP Latest Quarter",
        "fmp_ratios_ttm": "FMP Ratios TTM",
        "fmp_income_statement": "FMP Statements",
        "finnhub": "Finnhub",
        "yfinance": "Yahoo",
        "yfinance_quarterly": "Yahoo Statements",
        "fundamental_context": "Context",
        "alpha_vantage": "Alpha Vantage",
        "alpha_vantage_fallback": "Alpha Vantage",
        "alpha_vantage_overview": "Alpha Vantage",
        "local_from_ohlcv": "Local OHLCV",
        "derived_local": "本地派生",
    }
    return mapping.get(text, str(source))


def _format_field_basis(basis: Optional[str]) -> Optional[str]:
    text = str(basis or "").strip().lower().replace("-", "_")
    if not text:
        return None
    mapping = {
        "ttm": "TTM",
        "ttm_yoy": "TTM同比",
        "consensus": "一致预期",
        "latest": "最新值",
        "latest_quarter": "最新季度",
        "latest_quarter_yoy": "最新季度同比",
        "latest_quarter_qoq": "最新季度环比",
        "rolling_52w": "52周滚动",
        "provider_reported_total": "Provider口径",
        "provider_reported_growth": "Provider口径",
        "ttm_pending_validation": "TTM待复核",
    }
    return mapping.get(text, str(basis))


def _format_field_status(status: Optional[str]) -> Optional[str]:
    text = str(status or "").strip().lower().replace("-", "_")
    if not text:
        return None
    mapping = {
        "ok": "已就绪",
        "insufficient_history": "样本不足",
        "data_unavailable": "缺失",
        "derived": "派生",
    }
    return mapping.get(text, str(status))


def _checklist_status(raw: str) -> Tuple[str, str, str]:
    text = str(raw or "").strip()
    if text.startswith("✅"):
        return "pass", "✅", text[1:].strip(" ：:-") or text
    if text.startswith("⚠️"):
        return "warn", "⚠️", text[2:].strip(" ：:-") or text
    if text.startswith("❌"):
        return "fail", "❌", text[1:].strip(" ：:-") or text
    if text.startswith("NA（"):
        return "na", "•", text
    return "info", "•", text


def _build_checklist_items(checklist: Optional[List[str]]) -> List[Dict[str, str]]:
    items = [str(item).strip() for item in (checklist or []) if str(item).strip()]
    if not items:
        items = [_na("字段待接入")]
    normalized: List[Dict[str, str]] = []
    for raw in items:
        status, icon, text = _checklist_status(raw)
        normalized.append({
            "status": status,
            "icon": icon,
            "text": text,
        })
    return normalized


def _build_summary_panel(
    *,
    result: AnalysisResult,
    title: Dict[str, Any],
    market_block: Dict[str, Any],
) -> Dict[str, Any]:
    time_ctx = market_block.get("time_context") if isinstance(market_block.get("time_context"), dict) else {}
    regular_metrics = market_block.get("regular_metrics") if isinstance(market_block.get("regular_metrics"), dict) else {}
    session_value = time_ctx.get("session_label") or time_ctx.get("session_type")
    price_label = _format_text(time_ctx.get("price_label"), reason="字段待接入")
    price_basis = _format_text(time_ctx.get("price_basis"), reason="字段待接入")
    price_basis_detail = _format_text(time_ctx.get("price_basis_detail"), reason="字段待接入")
    current_price = _format_price(regular_metrics.get("price"))
    change_amount = _format_price(regular_metrics.get("change_amount"))
    change_pct = _format_percent(regular_metrics.get("change_pct"))
    market_time = _format_text(
        time_ctx.get("market_timestamp_local") or time_ctx.get("market_timestamp_bjt") or time_ctx.get("market_timestamp"),
        reason="接口未返回",
    )
    report_generated_at = _format_text(
        time_ctx.get("report_generated_at_bjt") or time_ctx.get("report_generated_at"),
        reason="接口未返回",
    )
    reference_session = _format_text(time_ctx.get("reference_session"), reason="接口未返回")
    tags = [
        {"label": "Basis", "value": price_basis},
        {"label": "Session", "value": reference_session},
        {"label": "As of", "value": market_time},
        {"label": "Report", "value": report_generated_at},
    ]
    return {
        "stock": title.get("stock"),
        "ticker": result.code,
        "score": result.sentiment_score,
        "current_price": current_price,
        "price_label": price_label,
        "price_basis": price_basis,
        "price_basis_detail": price_basis_detail,
        "change_amount": change_amount,
        "change_pct": change_pct,
        "market_time": market_time,
        "market_session_date": _format_text(time_ctx.get("market_session_date"), reason="接口未返回"),
        "session_label": _format_text(session_value, reason="接口未返回"),
        "reference_session": reference_session,
        "snapshot_time": market_time,
        "report_generated_at": report_generated_at,
        "price_context_note": _format_text(time_ctx.get("price_context_note"), reason="字段待接入"),
        "operation_advice": title.get("operation_advice"),
        "trend_prediction": title.get("trend_prediction"),
        "one_sentence": title.get("one_sentence"),
        "time_sensitivity": title.get("time_sensitivity"),
        "tags": tags,
    }


def _build_decision_context(
    *,
    dashboard: Dict[str, Any],
) -> Dict[str, Any]:
    payload = dashboard.get("decision_context") if isinstance(dashboard.get("decision_context"), dict) else {}
    score_breakdown_payload = payload.get("score_breakdown") if isinstance(payload.get("score_breakdown"), list) else []
    score_breakdown: List[Dict[str, Any]] = []
    for item in score_breakdown_payload:
        if not isinstance(item, dict):
            continue
        score_breakdown.append(
            {
                "label": _format_text(item.get("label"), reason="字段待接入"),
                "score": _to_float(item.get("score")),
                "note": _format_text(item.get("note"), reason="字段待接入"),
                "tone": str(item.get("tone") or "default"),
            }
        )
    return {
        "short_term_view": _format_text(payload.get("short_term_view"), reason="字段待接入"),
        "composite_view": _format_text(payload.get("composite_view"), reason="字段待接入"),
        "adjustment_reason": _format_text(payload.get("adjustment_reason"), reason="字段待接入"),
        "change_reason": _format_text(payload.get("change_reason"), reason="字段待接入"),
        "previous_score": _format_decimal(payload.get("previous_score"), digits=0, reason="接口未返回"),
        "score_change": _format_signed_number(payload.get("score_change"), reason="接口未返回"),
        "score_breakdown": score_breakdown,
    }


def _label_with_basis(base_label: str, basis: Optional[str]) -> str:
    suffix_map = {
        "ttm": "TTM",
        "ttm_yoy": "TTM同比",
        "consensus": "一致预期",
        "latest": "最新值",
        "latest_quarter": "最新季度",
        "latest_quarter_yoy": "最新季度同比",
        "latest_quarter_qoq": "最新季度环比",
        "rolling_52w": "52周滚动",
        "provider_reported_growth": "Provider口径",
        "provider_reported_total": "Provider口径",
        "ttm_pending_validation": "TTM待复核",
    }
    suffix = suffix_map.get(str(basis or "").strip())
    if not suffix:
        return base_label
    if f"({suffix})" in base_label:
        return base_label
    return f"{base_label}({suffix})"


def _derive_earnings_outlook(
    fundamentals: Optional[Dict[str, Any]],
    earnings: Optional[Dict[str, Any]],
) -> str:
    fundamentals_payload = fundamentals if isinstance(fundamentals, dict) else {}
    earnings_payload = earnings if isinstance(earnings, dict) else {}
    normalized = fundamentals_payload.get("normalized") if isinstance(fundamentals_payload.get("normalized"), dict) else {}
    field_periods = fundamentals_payload.get("field_periods") if isinstance(fundamentals_payload.get("field_periods"), dict) else {}
    metrics = earnings_payload.get("derived_metrics") if isinstance(earnings_payload.get("derived_metrics"), dict) else {}

    ttm_rev = _to_float(normalized.get("revenueGrowth"))
    ttm_net = _to_float(normalized.get("netIncomeGrowth"))
    latest_rev_yoy = _to_float(metrics.get("yoy_revenue_growth"))
    latest_net_yoy = _to_float(metrics.get("yoy_net_income_change"))

    ttm_basis = field_periods.get("revenueGrowth")
    net_basis = field_periods.get("netIncomeGrowth")

    ttm_part = None
    if ttm_rev is not None or ttm_net is not None:
        ttm_texts: List[str] = []
        if ttm_rev is not None:
            ttm_texts.append(f"营收{_format_percent(ttm_rev, from_ratio=True)}")
        if ttm_net is not None:
            ttm_texts.append(f"净利润{_format_percent(ttm_net, from_ratio=True)}")
        label = "TTM口径" if ttm_basis == "ttm_yoy" or net_basis == "ttm_yoy" else "基础面口径"
        ttm_part = f"{label}仍承压（{'，'.join(ttm_texts)}）"

    latest_part = None
    if latest_rev_yoy is not None or latest_net_yoy is not None:
        latest_texts: List[str] = []
        if latest_rev_yoy is not None:
            latest_texts.append(f"营收同比{_format_percent(latest_rev_yoy, from_ratio=True)}")
        if latest_net_yoy is not None:
            latest_texts.append(f"净利润同比{_format_percent(latest_net_yoy, from_ratio=True)}")
        latest_part = f"最新季度同比口径为{'、'.join(latest_texts)}"

    if ttm_part and latest_part:
        if (ttm_rev is not None and latest_rev_yoy is not None and (ttm_rev >= 0) != (latest_rev_yoy >= 0)) or (
            ttm_net is not None and latest_net_yoy is not None and (ttm_net >= 0) != (latest_net_yoy >= 0)
        ):
            return f"{ttm_part}；{latest_part}，两者口径不同，需分开解读。"
        return f"{ttm_part}；{latest_part}。"
    if latest_part:
        return f"{latest_part}。"
    if ttm_part:
        return f"{ttm_part}。"
    narratives = earnings_payload.get("narrative_insights") if isinstance(earnings_payload.get("narrative_insights"), list) else []
    for item in narratives:
        text = str(item).strip()
        if text:
            return text if text.endswith("。") else f"{text}。"
    return _na("接口未返回")


def _build_highlights(
    dashboard: Dict[str, Any],
    *,
    fundamentals: Optional[Dict[str, Any]] = None,
    earnings: Optional[Dict[str, Any]] = None,
    market_block: Optional[Dict[str, Any]] = None,
    technical_fields: Optional[List[Dict[str, str]]] = None,
    trade_setup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    time_context = structured.get("time_context") if isinstance(structured.get("time_context"), dict) else {}
    sentiment = structured.get("sentiment_analysis") if isinstance(structured.get("sentiment_analysis"), dict) else {}

    intel = _grade_intel_block(dashboard.get("intelligence") or {})
    latest_news_text = _normalize_inline_text(intel.get("latest_news"))
    reference_date = (
        time_context.get("market_session_date")
        or time_context.get("report_generated_at")
        or time_context.get("market_timestamp")
    )
    published_at = sentiment.get("news_published_at") or time_context.get("news_published_at")

    def _is_market_commentary(text: str) -> bool:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return False
        if not any(keyword in lowered for keyword in _MEDIA_INTERPRETATION_KEYWORDS):
            return False
        return not any(keyword in lowered for keyword in _ANNOUNCEMENT_NEWS_KEYWORDS)

    if latest_news_text and _is_stale_earnings_recap(
        latest_news_text,
        published_at=published_at,
        reference_date=reference_date,
    ):
        catalysts = [str(item).strip() for item in (intel.get("positive_catalysts") or []) if str(item).strip()]
        if latest_news_text not in catalysts and _classify_news_value(latest_news_text) != "低价值":
            catalysts.append(latest_news_text)
        intel["positive_catalysts"] = catalysts[:4]
        intel["latest_news"] = ""
        intel["latest_news_notice"] = "未发现高价值新增动态"

    if latest_news_text and _is_market_commentary(latest_news_text):
        lowered = latest_news_text.lower()
        if any(token in lowered for token in _NEGATIVE_NEWS_HINTS):
            risk_alerts = [str(item).strip() for item in (intel.get("risk_alerts") or []) if str(item).strip()]
            if latest_news_text not in risk_alerts:
                risk_alerts.append(latest_news_text)
            intel["risk_alerts"] = risk_alerts[:4]
        elif any(token in lowered for token in _POSITIVE_NEWS_HINTS):
            catalysts = [str(item).strip() for item in (intel.get("positive_catalysts") or []) if str(item).strip()]
            if latest_news_text not in catalysts:
                catalysts.append(latest_news_text)
            intel["positive_catalysts"] = catalysts[:4]
        elif not _normalize_inline_text(intel.get("sentiment_summary")):
            intel["sentiment_summary"] = latest_news_text
        intel["latest_news"] = ""
        intel["latest_news_notice"] = "未发现高价值新增动态"

    technical_map = _build_field_map(technical_fields or [])
    market_metrics = market_block.get("regular_metrics") if isinstance(market_block, dict) else {}
    fundamentals_payload = fundamentals if isinstance(fundamentals, dict) else {}
    normalized_fundamentals = (
        fundamentals_payload.get("normalized")
        if isinstance(fundamentals_payload.get("normalized"), dict)
        else {}
    )
    trade_ctx = trade_setup if isinstance(trade_setup, dict) else {}

    def _append_unique(bucket: List[str], text: str) -> None:
        normalized_text = _normalize_inline_text(text)
        if normalized_text and normalized_text not in bucket:
            bucket.append(normalized_text)

    bullish_factors: List[str] = []
    bearish_factors: List[str] = []
    neutral_factors: List[str] = []

    for item in intel.get("positive_catalysts") or []:
        _append_unique(bullish_factors, str(item))
    for item in intel.get("risk_alerts") or []:
        _append_unique(bearish_factors, str(item))

    current_price = _to_float(
        _pick_first_from_sources(
            (market_metrics, market_block or {}),
            ("price", "current_price", "regular_price_numeric", "close"),
            zero_is_missing=True,
        )
    )
    ma20 = _extract_first_number(technical_map.get("MA20"))
    ma5 = _extract_first_number(technical_map.get("MA5"))
    support = _extract_first_number(technical_map.get("支撑位"))
    resistance = _extract_first_number(technical_map.get("压力位"))
    high_52w = _to_float(
        _pick_first_from_sources(
            (normalized_fundamentals, market_block or {}),
            ("fiftyTwoWeekHigh", "high_52w", "52week_high"),
            zero_is_missing=True,
        )
    )
    trailing_pe = _to_float(normalized_fundamentals.get("trailingPE"))
    forward_pe = _to_float(normalized_fundamentals.get("forwardPE"))
    company_sentiment = str(sentiment.get("company_sentiment") or "").strip().lower()
    industry_sentiment = str(sentiment.get("industry_sentiment") or "").strip().lower()
    regulatory_sentiment = str(sentiment.get("regulatory_sentiment") or "").strip().lower()
    confidence_text = localize_confidence_level(
        sentiment.get("overall_confidence") or sentiment.get("confidence"),
        "zh",
    )
    confidence_suffix = f"置信度{confidence_text if confidence_text and not confidence_text.startswith('NA（') else '中'}。"
    volume_status = _normalize_inline_text(technical_map.get(get_standard_report_field_label("volume_judgment", "zh"))).lower()
    ma20_position = _normalize_inline_text(technical_map.get(get_standard_report_field_label("ma20_position", "zh")))
    earnings_outlook = _derive_earnings_outlook(fundamentals, earnings)
    scenario_label = _normalize_inline_text(trade_ctx.get("scenario_label"))
    support_text = _normalize_inline_text(trade_ctx.get("support_text"))
    resistance_text = _normalize_inline_text(trade_ctx.get("resistance_text"))
    has_company_specific_catalyst = bool(intel.get("positive_catalysts"))
    has_company_specific_risk = bool(intel.get("risk_alerts"))
    social_context = (
        intel.get("social_context")
        or sentiment.get("social_context")
        or sentiment.get("social_summary")
    )
    social_digest = _build_social_digest(
        social_context,
        company_sentiment=company_sentiment,
        industry_sentiment=industry_sentiment,
        regulatory_sentiment=regulatory_sentiment,
        scenario_label=scenario_label,
        volume_status=volume_status,
    )

    if earnings_outlook and not earnings_outlook.startswith("NA（"):
        if any(token in earnings_outlook for token in ("改善", "增长", "回升", "同向改善")):
            _append_unique(
                bullish_factors,
                f"业绩预期：{earnings_outlook.rstrip('。')}，有助于维持基本面支撑；方向偏多；{confidence_suffix}",
            )
        elif any(token in earnings_outlook for token in ("承压", "回落", "下滑", "不足")):
            _append_unique(
                bearish_factors,
                f"业绩预期：{earnings_outlook.rstrip('。')}，基本面缓冲有限；方向偏空；{confidence_suffix}",
            )

    if current_price is not None and ma20 is not None:
        if current_price >= ma20:
            structure_text = support_text or f"{support:.2f}" if support is not None else f"{ma20:.2f}"
            _append_unique(
                bullish_factors,
                f"技术结构：价格仍位于 MA20 上方，防守位在 {structure_text} 一带；若回踩企稳，趋势延续概率更高；方向偏多；{confidence_suffix}",
            )
        else:
            _append_unique(
                bearish_factors,
                f"技术结构：价格已落到 MA20 下方，说明趋势确认不足；若不能快速收复均线，回撤风险仍在；方向偏空；{confidence_suffix}",
            )

    if scenario_label and resistance_text and scenario_label.startswith("突破"):
        _append_unique(
            bullish_factors,
            f"触发条件：放量站上 {resistance_text} 才算真正突破，届时才具备追随性催化；方向偏多；{confidence_suffix}",
        )
    elif scenario_label and support_text and scenario_label.startswith("回踩"):
        _append_unique(
            bullish_factors,
            f"执行节奏：更适合等回踩 {support_text} 附近出现承接，再按计划试仓；方向偏多；{confidence_suffix}",
        )
    elif scenario_label and "观望" in scenario_label:
        _append_unique(
            neutral_factors,
            f"交易状态：当前更接近等待区，先等结构重新确认再行动；方向中性；{confidence_suffix}",
        )

    if trailing_pe is not None and trailing_pe >= 30:
        _append_unique(
            bearish_factors,
            f"估值约束：TTM PE 约 {trailing_pe:.1f}，估值容错率偏低；若催化不能继续兑现，波动放大的概率上升；方向偏空；{confidence_suffix}",
        )
    elif forward_pe is not None and forward_pe >= 28:
        _append_unique(
            bearish_factors,
            f"估值约束：前瞻 PE 约 {forward_pe:.1f}，市场已计入较多乐观预期；方向偏空；{confidence_suffix}",
        )

    if current_price is not None and high_52w is not None and high_52w > 0:
        distance_52w = (high_52w - current_price) / high_52w * 100
        if 0 <= distance_52w <= 8:
            _append_unique(
                neutral_factors,
                f"高位语境：当前距 52 周高点约 {distance_52w:.1f}%，上方空间存在，但也意味着突破前容易反复；方向中性；{confidence_suffix}",
            )

    if company_sentiment == "positive" or industry_sentiment == "positive":
        _append_unique(
            bullish_factors,
            "情绪与叙事：公司/行业层面的风险偏好偏积极，利于强势结构延续；方向偏多；置信度中。",
        )
    if regulatory_sentiment == "negative":
        _append_unique(
            bearish_factors,
            "监管语境：监管情绪偏负面，短线估值和风险偏好都可能受压制；方向偏空；置信度中。",
        )
    elif company_sentiment in {"neutral", ""} and industry_sentiment in {"neutral", ""}:
        _append_unique(
            neutral_factors,
            "消息面偏安静，缺少新的公司级催化，短线更依赖板块风险偏好和技术位置。方向中性；置信度中。",
        )

    if "缩量" in volume_status:
        _append_unique(
            neutral_factors,
            "量能语境：当前量能偏缩，说明追价意愿一般，更适合等待确认而不是主观放大仓位。方向中性；置信度中。",
        )
    elif "放量" in volume_status:
        _append_unique(
            bullish_factors,
            "量能语境：近期量能较前期改善，若与关键价位共振，更容易形成有效延续。方向偏多；置信度中。",
        )

    if not has_company_specific_catalyst:
        _append_unique(
            neutral_factors,
            "暂无新的公司级催化落地；当前可参考的驱动更多来自行业景气、盈利预期和技术结构。",
        )
    if not has_company_specific_risk and ma20_position and "下方" in ma20_position:
        _append_unique(
            bearish_factors,
            "暂无新的硬风险公告，但技术位置本身已经成为当前的主要风险来源。",
        )

    latest_news_items: List[str] = []
    latest_news = _normalize_inline_text(intel.get("latest_news") or intel.get("latest_news_notice"))
    if latest_news:
        latest_news_items.append(latest_news)
    if not latest_news_items:
        latest_news_items.append(
            "暂无新的公司级公告/催化，当前优先跟踪行业情绪、盈利预期与技术位是否出现新的确认信号。"
        )
        if scenario_label:
            latest_news_items.append(f"当前执行语境：{scenario_label}。")
        if support_text and resistance_text:
            latest_news_items.append(f"关键结构位：支撑关注 {support_text}，压力关注 {resistance_text}。")

    sentiment_summary_text = _normalize_inline_text(intel.get("sentiment_summary"))
    if not sentiment_summary_text:
        bullish_lead = bullish_factors[0] if bullish_factors else "暂无明显偏多增量"
        bearish_lead = bearish_factors[0] if bearish_factors else "暂无明显偏空增量"
        neutral_lead = neutral_factors[0] if neutral_factors else "当前更偏等待确认"
        sentiment_summary_text = (
            f"偏多因素：{bullish_lead} 偏空因素：{bearish_lead} "
            f"中性/混合：{neutral_lead}"
        )

    positive_items = unique_meaningful_items(
        [*intel.get("positive_catalysts", []), *bullish_factors],
        4,
    )
    risk_items = unique_meaningful_items(
        [*intel.get("risk_alerts", []), *bearish_factors],
        4,
    )
    neutral_items = unique_meaningful_items(
        [
            *neutral_factors,
            f"零售讨论：{social_digest['social_attention']}，{social_digest['social_narrative_focus']}。",
        ],
        4,
    )

    return {
        "positive_catalysts": positive_items,
        "risk_alerts": risk_items,
        "latest_news": latest_news_items[:3],
        "news_value_grade": _format_text(intel.get("news_value_grade"), reason="接口未返回"),
        "sentiment_summary": _format_text(sentiment_summary_text, reason="接口未返回"),
        "earnings_outlook": earnings_outlook,
        "bullish_factors": positive_items,
        "bearish_factors": risk_items,
        "neutral_factors": neutral_items,
        "social_synthesis": _format_text(social_digest.get("social_synthesis"), reason="字段待接入"),
        "social_attention": _format_text(social_digest.get("social_attention"), reason="字段待接入"),
        "social_tone": _format_text(social_digest.get("social_tone"), reason="字段待接入"),
        "social_narrative_focus": _format_text(social_digest.get("social_narrative_focus"), reason="字段待接入"),
        "social_sources": social_digest.get("social_sources") or [],
    }


def _build_visual_blocks(
    *,
    result: AnalysisResult,
    market_block: Dict[str, Any],
    technical_fields: List[Dict[str, str]],
    highlights: Dict[str, Any],
) -> Dict[str, Any]:
    field_map = _build_field_map(technical_fields)
    current_price = _to_float(market_block.get("regular_price_numeric"))
    ma20 = _extract_first_number(field_map.get("MA20"))
    ma60 = _extract_first_number(field_map.get("MA60"))
    trend_strength_value = _extract_first_number(field_map.get("趋势强度"))

    def _distance(base: Optional[float], value: Optional[float]) -> Optional[float]:
        if value in (None, 0) or base is None:
            return None
        return round((base - value) / abs(value) * 100, 2)

    return {
        "score": {
            "value": result.sentiment_score,
            "max": 100,
        },
        "trend_strength": {
            "value": trend_strength_value,
            "max": 100,
            "label": field_map.get("多头/空头排列"),
        },
        "price_position": {
            "current_price": current_price,
            "ma20": ma20,
            "ma60": ma60,
            "distance_to_ma20_pct": _distance(current_price, ma20),
            "distance_to_ma60_pct": _distance(current_price, ma60),
            "vs_ma20": "上方" if current_price is not None and ma20 is not None and current_price >= ma20 else (
                "下方" if current_price is not None and ma20 is not None else _na("接口未返回")
            ),
            "vs_ma60": "上方" if current_price is not None and ma60 is not None and current_price >= ma60 else (
                "下方" if current_price is not None and ma60 is not None else _na("接口未返回")
            ),
        },
        "risk_opportunity": {
            "positive_count": len(highlights.get("positive_catalysts") or []),
            "risk_count": len(highlights.get("risk_alerts") or []),
            "latest_news_count": len(highlights.get("latest_news") or []),
        },
    }


def _build_battle_plan_compact(
    battle_fields: List[Dict[str, str]],
    warnings: List[str],
) -> Dict[str, Any]:
    cards: List[Dict[str, str]] = []
    notes: List[Dict[str, str]] = []
    tone_map = {
        "交易场景": "info",
        "关键动作": "info",
        "理想买入点": "buy",
        "次优买入点": "secondary",
        "止损位": "risk",
        "目标一区": "target",
        "目标二区": "target",
        "目标位": "target",
        "关键支撑": "info",
        "关键压力": "warning",
        "仓位建议": "position",
    }
    for item in battle_fields:
        if not isinstance(item, dict):
            continue
        payload = {
            "label": str(item.get("label") or "").strip(),
            "value": str(item.get("value") or "").strip(),
            "tone": tone_map.get(str(item.get("label") or "").strip(), "note"),
        }
        if payload["label"] in tone_map:
            cards.append(payload)
        else:
            notes.append(payload)
    return {
        "cards": cards,
        "notes": notes,
        "warnings": warnings or [],
    }


def _meaningful_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text or text.startswith("NA（"):
        return None
    return text


def _pick_first_nonempty(items: Iterable[Any], *, default: Optional[str] = None) -> Optional[str]:
    for item in items or []:
        text = _meaningful_text(item)
        if text:
            return text
    return default


def unique_meaningful_items(items: Iterable[Any], limit: int) -> List[str]:
    seen: set[str] = set()
    normalized: List[str] = []
    for item in items or []:
        text = _meaningful_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _extract_missing_reason(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if text.startswith("NA（") and text.endswith("）"):
        return text[3:-1].strip()
    return None


def _build_decision_panel(
    *,
    battle_fields: List[Dict[str, str]],
    position_advice: Dict[str, Any],
    risk_warnings: List[str],
    decision_context: Dict[str, Any],
    trade_setup: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    battle_map = _build_field_map(battle_fields)
    execution_reminders = [str(item).strip() for item in (risk_warnings or []) if str(item).strip()]
    change_reason = _meaningful_text(decision_context.get("change_reason"))
    if change_reason and change_reason not in execution_reminders:
        execution_reminders.append(change_reason)

    trade_ctx = trade_setup if isinstance(trade_setup, dict) else {}

    return {
        "setup_type": battle_map.get("交易场景", _format_text(trade_ctx.get("scenario_label"), reason="字段待接入")),
        "confidence": _format_text(trade_ctx.get("confidence_label"), reason="字段待接入"),
        "key_action": battle_map.get("关键动作", _format_text(trade_ctx.get("key_action"), reason="字段待接入")),
        "analysis_price": _to_float(trade_ctx.get("analysis_price")),
        "support": battle_map.get("关键支撑", _format_text(trade_ctx.get("support_text"), reason="字段待接入")),
        "support_level": _to_float(trade_ctx.get("support_level")),
        "resistance": battle_map.get("关键压力", _format_text(trade_ctx.get("resistance_text"), reason="字段待接入")),
        "resistance_level": _to_float(trade_ctx.get("resistance_level")),
        "ideal_entry": battle_map.get("理想买入点", _na("字段待接入")),
        "ideal_entry_center": _to_float(trade_ctx.get("ideal_entry_center")),
        "backup_entry": battle_map.get("次优买入点", _na("字段待接入")),
        "backup_entry_center": _to_float(trade_ctx.get("backup_entry_center")),
        "stop_loss": battle_map.get("止损位", _na("字段待接入")),
        "stop_loss_level": _to_float(trade_ctx.get("stop_loss_level")),
        "target": battle_map.get("目标位", _na("字段待接入")),
        "target_one": battle_map.get("目标一区", _format_text(trade_ctx.get("target_one"), reason="字段待接入")),
        "target_one_level": _to_float(trade_ctx.get("target_one_level")),
        "target_two": battle_map.get("目标二区", _format_text(trade_ctx.get("target_two"), reason="字段待接入")),
        "target_two_level": _to_float(trade_ctx.get("target_two_level")),
        "target_zone": _format_text(trade_ctx.get("target_zone"), reason="字段待接入"),
        "stop_reason": _format_text(trade_ctx.get("stop_reason"), reason="字段待接入"),
        "target_reason": _format_text(trade_ctx.get("target_reason"), reason="字段待接入"),
        "market_structure": _format_text(trade_ctx.get("market_structure"), reason="字段待接入"),
        "atr_proxy": _to_float(trade_ctx.get("atr_proxy")),
        "position_sizing": battle_map.get("仓位建议", _na("字段待接入")),
        "build_strategy": battle_map.get("建仓策略", _na("字段待接入")),
        "risk_control_strategy": battle_map.get("风控策略", _na("字段待接入")),
        "no_position_advice": _format_text(position_advice.get("no_position") or trade_ctx.get("no_position_advice"), reason="字段待接入"),
        "holder_advice": _format_text(position_advice.get("has_position") or trade_ctx.get("holder_advice"), reason="字段待接入"),
        "execution_reminders": execution_reminders,
    }


def _build_reason_layer(
    *,
    highlights: Dict[str, Any],
    checklist: List[str],
    decision_context: Dict[str, Any],
) -> Dict[str, Any]:
    top_risk = _pick_first_nonempty(highlights.get("risk_alerts") or [], default=_na("接口未返回"))
    top_catalyst = _pick_first_nonempty(highlights.get("positive_catalysts") or [], default=_na("接口未返回"))
    latest_update = _pick_first_nonempty(highlights.get("latest_news") or [], default=_na("接口未返回"))
    sentiment_summary = _format_text(highlights.get("sentiment_summary"), reason="接口未返回")
    checklist_summary = _summarize_checklist(checklist)

    core_reasons: List[str] = []
    seen: set[str] = set()
    for candidate in (
        decision_context.get("composite_view"),
        decision_context.get("short_term_view"),
        top_catalyst,
        top_risk,
        latest_update,
        sentiment_summary,
        checklist_summary,
    ):
        text = _meaningful_text(candidate)
        if not text:
            continue
        normalized = text.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        core_reasons.append(text)
        if len(core_reasons) >= 3:
            break

    return {
        "core_reasons": core_reasons,
        "top_risk": top_risk,
        "top_catalyst": top_catalyst,
        "latest_key_update": latest_update,
        "sentiment_summary": sentiment_summary,
        "checklist_summary": checklist_summary,
        "news_value_tier": _format_text(highlights.get("news_value_grade"), reason="接口未返回"),
    }


def _build_coverage_notes(
    *,
    market_block: Dict[str, Any],
    technical_fields: List[Dict[str, str]],
    fundamental_fields: List[Dict[str, str]],
    earnings_fields: List[Dict[str, str]],
) -> Dict[str, Any]:
    all_fields: List[Dict[str, str]] = []
    for bucket in (
        market_block.get("regular_fields") or [],
        market_block.get("extended_fields") or [],
        technical_fields or [],
        fundamental_fields or [],
        earnings_fields or [],
    ):
        if isinstance(bucket, list):
            all_fields.extend([item for item in bucket if isinstance(item, dict)])

    data_sources: List[str] = []
    for field in all_fields:
        source = _meaningful_text(field.get("source"))
        if source and source not in data_sources:
            data_sources.append(source)

    coverage_gaps: List[str] = []
    missing_field_notes: List[str] = []
    conflict_notes: List[str] = [str(item).strip() for item in (market_block.get("consistency_warnings") or []) if str(item).strip()]

    for field in all_fields:
        label = str(field.get("label") or "").strip()
        value = field.get("value")
        status = _meaningful_text(field.get("status"))
        missing_reason = _extract_missing_reason(value)
        if missing_reason:
            if label and label not in coverage_gaps:
                coverage_gaps.append(label)
            note = f"{label}：{missing_reason}" if label else missing_reason
            if note not in missing_field_notes:
                missing_field_notes.append(note)
        if status and ("待复核" in status or "冲突" in status):
            note = f"{label}：{status}" if label else status
            if note not in conflict_notes:
                conflict_notes.append(note)

    return {
        "data_sources": data_sources[:6],
        "coverage_gaps": coverage_gaps[:8],
        "conflict_notes": conflict_notes[:8],
        "missing_field_notes": missing_field_notes[:8],
        "method_notes": [
            "已收盘场景优先使用单一 EOD / official close 口径锁定 close、prev_close、涨跌与成交量。",
            "标准技术指标优先使用 API 原始值，API 缺失时才回退本地历史计算。",
            "策略型字段如支撑/压力、趋势强度、执行位继续由本地逻辑派生。",
        ],
    }


def _clean_sniper_value(value: Any) -> str:
    if value is None:
        return _na("字段待接入")
    if isinstance(value, (int, float)):
        return f"{float(value):.2f}"
    text = str(value).strip()
    if not text or text.lower() in _MISSING_MARKERS:
        return _na("字段待接入")
    prefixes = (
        "理想买入点：",
        "次优买入点：",
        "止损位：",
        "目标位：",
        "理想买入点:",
        "次优买入点:",
        "止损位:",
        "目标位:",
        "Ideal Entry:",
        "Secondary Entry:",
        "Stop Loss:",
        "Target:",
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
            break
    return _NUMERIC_TOKEN_RE.sub(lambda m: f"{float(m.group(0)):.2f}", text)


def _join_list(values: Iterable[Any], *, empty_reason: str = "接口未返回") -> str:
    cleaned = [str(v).strip() for v in values if str(v).strip()]
    if not cleaned:
        return _na(empty_reason)
    return "；".join(cleaned)


def _classify_news_value(text: str) -> str:
    payload = text.lower()
    if any(keyword.lower() in payload for keyword in _HIGH_VALUE_NEWS_KEYWORDS):
        return "高价值"
    if any(keyword.lower() in payload for keyword in _LOW_VALUE_NEWS_KEYWORDS):
        return "低价值"
    return "中价值"


def _grade_intel_block(intel: Any) -> Dict[str, Any]:
    block = dict(intel) if isinstance(intel, dict) else {}

    def _rank(items: Any, limit: int = 4) -> List[str]:
        values = [str(item).strip() for item in (items or []) if str(item).strip()]
        if not values:
            return []
        high = [v for v in values if _classify_news_value(v) == "高价值"]
        if high:
            return high[:limit]
        medium = [v for v in values if _classify_news_value(v) == "中价值"]
        if medium:
            return medium[:limit]
        return []

    risk_alerts = _rank(block.get("risk_alerts"))
    catalysts = _rank(block.get("positive_catalysts"))

    latest_news = _normalize_inline_text(block.get("latest_news"))
    latest_grade = _classify_news_value(latest_news) if latest_news else "中价值"
    if latest_news and latest_grade == "低价值":
        latest_news = ""

    block["risk_alerts"] = risk_alerts
    block["positive_catalysts"] = catalysts
    block["latest_news"] = latest_news

    if not catalysts:
        block["positive_catalysts_notice"] = "未发现高价值新增催化"
    if not latest_news:
        block["latest_news_notice"] = "未发现高价值新增动态"

    grades = []
    for item in risk_alerts + catalysts:
        grades.append(_classify_news_value(item))
    if latest_news:
        grades.append(latest_grade)

    if "高价值" in grades:
        block["news_value_grade"] = "高价值优先"
    elif "中价值" in grades:
        block["news_value_grade"] = "中价值为主"
    else:
        block["news_value_grade"] = "低价值已降权"

    return block


def _extract_embedded_date(text: str) -> Optional[calendar_date]:
    payload = str(text or "").strip()
    if not payload:
        return None
    match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", payload)
    if not match:
        return None
    try:
        return calendar_date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _parse_reference_date(value: Any) -> Optional[calendar_date]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return calendar_date.fromisoformat(text[:10])
    except ValueError:
        return None


def _is_stale_earnings_recap(
    text: str,
    *,
    published_at: Any = None,
    reference_date: Any = None,
    stale_days: int = 10,
) -> bool:
    payload = str(text or "").strip()
    if not payload:
        return False
    lowered = payload.lower()
    if not any(keyword in lowered for keyword in _STALE_EARNINGS_NEWS_KEYWORDS):
        return False
    event_date = _parse_reference_date(published_at) or _extract_embedded_date(payload)
    base_date = _parse_reference_date(reference_date)
    if event_date is None or base_date is None:
        return False
    return (base_date - event_date).days >= stale_days


def _summarize_earnings(earnings: Optional[Dict[str, Any]]) -> str:
    payload = earnings if isinstance(earnings, dict) else {}
    metrics = payload.get("derived_metrics") if isinstance(payload.get("derived_metrics"), dict) else {}

    yoy_rev = _to_float(metrics.get("yoy_revenue_growth"))
    yoy_net = _to_float(metrics.get("yoy_net_income_change"))
    qoq_rev = _to_float(metrics.get("qoq_revenue_growth"))
    qoq_net = _to_float(metrics.get("qoq_net_income_change"))

    if yoy_rev is not None and yoy_net is not None:
        if yoy_rev >= 0 and yoy_net >= 0:
            return "最新季度同比口径：营收与利润同向改善。"
        if yoy_rev >= 0 and yoy_net < 0:
            return "最新季度同比口径：营收同比增长，但利润端仍承压。"
        if yoy_rev < 0 and yoy_net < 0:
            return "最新季度同比口径：营收与利润同步回落。"
    if qoq_rev is not None and qoq_net is not None:
        if qoq_rev >= 0 and qoq_net >= 0:
            return "最新季度环比口径：营收与利润边际改善。"
        if qoq_rev >= 0 and qoq_net < 0:
            return "最新季度环比口径：营收回升，但利润改善不足。"

    narratives = payload.get("narrative_insights") if isinstance(payload.get("narrative_insights"), list) else []
    for item in narratives:
        text = str(item).strip()
        if text:
            return text if text.endswith("。") else f"{text}。"
    return _na("接口未返回")


def _summarize_sentiment(sentiment: Optional[Dict[str, Any]]) -> str:
    payload = sentiment if isinstance(sentiment, dict) else {}
    if not payload:
        return _na("接口未返回")

    company = str(payload.get("company_sentiment") or "").strip()
    industry = str(payload.get("industry_sentiment") or "").strip()
    regulatory = str(payload.get("regulatory_sentiment") or "").strip()

    if regulatory == "negative":
        return "监管情绪偏负面，短线需优先控制风险。"
    if company == "positive":
        return "公司情绪偏积极。"
    if company == "negative":
        return "公司情绪偏谨慎。"
    if industry == "positive":
        return "行业情绪偏积极。"
    if industry == "negative":
        return "行业情绪偏谨慎。"
    return "情绪中性。"


def _summarize_volume_judgment(volume_analysis: Optional[Dict[str, Any]]) -> str:
    payload = volume_analysis if isinstance(volume_analysis, dict) else {}
    status = _normalize_inline_text(payload.get("volume_status")).lower()
    ratio = _to_float(payload.get("volume_ratio"))
    meaning = _normalize_inline_text(payload.get("volume_meaning"))
    has_ratio = not _is_missing_value(ratio, zero_is_missing=True)

    if any(token in status for token in ("缺失", "missing", "unavailable")):
        return _na("接口未返回")
    if "放量" in status or (has_ratio and ratio is not None and ratio >= 1.2):
        return "放量，短线资金参与度提升。"
    if "缩量" in status or (has_ratio and ratio is not None and ratio < 0.8):
        return "缩量，追价意愿偏弱。"
    if "正常" in status or "平量" in status or has_ratio:
        return "平量，资金参与度常态。"
    if meaning:
        return meaning if meaning.endswith(("。", "!", "?")) else f"{meaning}。"
    return _na("接口未返回")


def _annotate_trade_levels(
    current_price: Any,
    ideal_buy: Any,
    secondary_buy: Any,
    stop_loss: Any,
    trend_prediction: Any,
) -> Dict[str, Any]:
    current = _extract_first_number(current_price)
    ideal = _extract_first_number(ideal_buy)
    secondary = _extract_first_number(secondary_buy)
    stop = _extract_first_number(stop_loss)
    trend = str(trend_prediction or "").lower()

    bullish = any(token in trend for token in ("看多", "bull", "long", "up"))

    def _entry_tag(level: Optional[float]) -> Optional[str]:
        if current is None or level is None:
            return None
        return "突破买点" if level > current else "回踩买点"

    warnings: List[str] = []
    if bullish and current is not None and stop is not None and stop > current:
        warnings.append("做多语境下止损位不能高于当前价")
    if current is not None and stop is not None and current < stop:
        warnings.append("当前价已跌破关键防守位，请勿继续沿用原风控文案")

    return {
        "ideal_buy_tag": _entry_tag(ideal),
        "secondary_buy_tag": _entry_tag(secondary),
        "risk_warnings": warnings,
    }


def _build_market_block(
    result: AnalysisResult,
    *,
    language: str,
    dashboard: Dict[str, Any],
    labels: Dict[str, str],
) -> Dict[str, Any]:
    snapshot = result.market_snapshot if isinstance(result.market_snapshot, dict) else {}
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    time_context = structured.get("time_context") if isinstance(structured.get("time_context"), dict) else {}
    realtime_context = structured.get("realtime_context") if isinstance(structured.get("realtime_context"), dict) else {}
    market_context = structured.get("market_context") if isinstance(structured.get("market_context"), dict) else {}
    today_context = market_context.get("today") if isinstance(market_context.get("today"), dict) else {}
    yesterday_context = market_context.get("yesterday") if isinstance(market_context.get("yesterday"), dict) else {}
    data_persp = dashboard.get("data_perspective") if isinstance(dashboard.get("data_perspective"), dict) else {}
    price_data = data_persp.get("price_position") if isinstance(data_persp.get("price_position"), dict) else {}
    volume_analysis = data_persp.get("volume_analysis") if isinstance(data_persp.get("volume_analysis"), dict) else {}
    quote_sources = (realtime_context, today_context, snapshot)
    regular_sources = (today_context, realtime_context, snapshot)
    prev_close_sources = (yesterday_context, realtime_context, today_context, snapshot)

    market_timestamp = _pick_first_from_sources(
        (time_context, realtime_context, snapshot),
        ("market_timestamp", "timestamp", "quote_time"),
    )
    raw_session_type = _pick_first(snapshot, ("session_type", "session")) or time_context.get("session_type")
    session_type = _coerce_session_type(result.code, raw_session_type, market_timestamp)
    session_kind, session_label = _normalize_session_type(session_type)

    def _build_quote_bundle(
        *,
        name: str,
        primary: Optional[Dict[str, Any]],
        secondary: Optional[Dict[str, Any]] = None,
        prefer_close_as_price: bool = False,
    ) -> Dict[str, Any]:
        primary_obj = primary if isinstance(primary, dict) else {}
        secondary_obj = secondary if isinstance(secondary, dict) else {}
        close_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                (
                    "close",
                    "regular_close",
                    "regular_close_price",
                    "regular_market_price",
                    "regularMarketPrice",
                    "regular_price",
                    "last_close",
                ),
                zero_is_missing=True,
            )
        )
        price_value = close_value if prefer_close_as_price else _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                (
                    "price",
                    "current_price",
                    "currentPrice",
                    "last_price",
                    "lastPrice",
                    "regularMarketPrice",
                    "regular_market_price",
                    "close",
                ),
                zero_is_missing=True,
            )
        )
        open_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                ("open", "open_price", "openPrice", "regularMarketOpen"),
                zero_is_missing=True,
            )
        )
        high_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                ("high", "dayHigh", "day_high", "regularMarketDayHigh"),
                zero_is_missing=True,
            )
        )
        low_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                ("low", "dayLow", "day_low", "regularMarketDayLow"),
                zero_is_missing=True,
            )
        )
        volume_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                ("volume", "turnover_volume", "lastVolume", "last_volume", "regularMarketVolume", "marketVolume"),
                zero_is_missing=True,
            )
        )
        amount_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                ("amount", "turnover", "turnover_amount", "last_amount", "trading_value", "trade_value"),
                zero_is_missing=True,
            )
        )
        amplitude_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                ("amplitude", "swing", "swing_pct", "amplitude_pct", "amplitudePercent"),
            )
        )
        prev_close_value = _to_float(
            _pick_first_number_from_sources(
                (secondary_obj,),
                ("close", "prev_close", "yesterday_close"),
                zero_is_missing=True,
            )
            or _pick_first_number_from_sources(
                (primary_obj,),
                (
                    "prev_close",
                    "pre_close",
                    "preClose",
                    "previous_close",
                    "previousClose",
                    "regular_previous_close",
                    "regularMarketPreviousClose",
                    "chartPreviousClose",
                    "yesterday_close",
                ),
                zero_is_missing=True,
            )
        )
        change_amount_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                (
                    "regular_change",
                    "regular_change_amount",
                    "regularMarketChange",
                    "change_amount",
                    "change",
                ),
            )
        )
        change_pct_value = _to_float(
            _pick_first_number_from_sources(
                (primary_obj,),
                (
                    "regular_change_pct",
                    "regular_change_percent",
                    "regularMarketChangePercent",
                    "pct_chg",
                    "change_pct",
                    "changePercent",
                    "changePercentage",
                    "percent_change",
                ),
            )
        )
        source_value = _pick_first_from_sources(
            (primary_obj, secondary_obj),
            ("source", "provider", "data_source"),
        )
        completeness = sum(
            1
            for item in (price_value, close_value, prev_close_value, open_value, high_value, low_value, volume_value)
            if item is not None
        )
        return {
            "name": name,
            "price": price_value if price_value is not None else close_value,
            "close": close_value,
            "prev_close": prev_close_value,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "volume": volume_value,
            "amount": amount_value,
            "amplitude": amplitude_value,
            "change_amount": change_amount_value,
            "change_pct": change_pct_value,
            "source": source_value,
            "completeness": completeness,
        }

    def _select_quote_bundle(
        candidates: List[Dict[str, Any]],
        *,
        preferred_names: Tuple[str, ...],
        require_close: bool = False,
    ) -> Dict[str, Any]:
        preference_order = {name: index for index, name in enumerate(preferred_names)}

        def _matches_requirement(item: Dict[str, Any]) -> bool:
            if require_close:
                return item.get("close") is not None and item.get("prev_close") is not None
            return (
                item.get("price") is not None
                and item.get("open") is not None
                and item.get("high") is not None
                and item.get("low") is not None
            ) or item.get("price") is not None or item.get("close") is not None

        preferred_matches = sorted(
            [
                item
                for item in candidates
                if str(item.get("name") or "") in preference_order and _matches_requirement(item)
            ],
            key=lambda item: (
                preference_order.get(str(item.get("name") or ""), len(preferred_names)),
                -int(item.get("completeness", 0)),
            ),
        )
        if preferred_matches:
            return preferred_matches[0]

        preference_rank = {name: len(preferred_names) - index for index, name in enumerate(preferred_names)}
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.get("completeness", 0),
                1 if item.get("price") is not None else 0,
                1 if item.get("close") is not None else 0,
                preference_rank.get(str(item.get("name") or ""), 0),
            ),
            reverse=True,
        )
        if not ordered:
            return {}
        if require_close:
            selected = next(
                (item for item in ordered if item.get("close") is not None and item.get("prev_close") is not None),
                None,
            )
            if selected is None:
                selected = next((item for item in ordered if item.get("close") is not None), None)
            return selected or ordered[0]

        selected = next(
            (
                item for item in ordered
                if item.get("price") is not None
                and item.get("open") is not None
                and item.get("high") is not None
                and item.get("low") is not None
            ),
            None,
        )
        if selected is None:
            selected = next((item for item in ordered if item.get("price") is not None or item.get("close") is not None), None)
        return selected or ordered[0]

    close = _to_float(
        _pick_first_number_from_sources(
            regular_sources,
            (
                "close",
                "regular_close",
                "regular_close_price",
                "regular_market_price",
                "regularMarketPrice",
                "regular_price",
                "last_close",
            ),
            zero_is_missing=True,
        )
    )
    live_price = _to_float(
        _pick_first_number_from_sources(
            quote_sources,
            (
                "price",
                "current_price",
                "currentPrice",
                "last_price",
                "lastPrice",
                "regularMarketPrice",
                "regular_market_price",
            ),
            zero_is_missing=True,
        )
    )

    provided_regular_change = _to_float(
        _pick_first_number_from_sources(
            (today_context, realtime_context, snapshot),
            (
                "regular_change",
                "regular_change_amount",
                "regularMarketChange",
                "change_amount",
                "change",
            ),
        )
    )
    provided_regular_pct = _to_float(
        _pick_first_number_from_sources(
            (today_context, realtime_context, snapshot),
            (
                "regular_change_pct",
                "regular_change_percent",
                "regularMarketChangePercent",
                "pct_chg",
                "change_pct",
                "changePercent",
                "changePercentage",
                "percent_change",
            ),
        )
    )
    prev_close = _to_float(
        _pick_first_number_from_sources(
            (yesterday_context,),
            ("close", "prev_close", "yesterday_close"),
            zero_is_missing=True,
        )
        or _pick_first_number_from_sources(
            (realtime_context, today_context, snapshot),
            (
                "prev_close",
                "pre_close",
                "preClose",
                "previous_close",
                "previousClose",
                "regular_previous_close",
                "regularMarketPreviousClose",
                "chartPreviousClose",
                "yesterday_close",
            ),
            zero_is_missing=True,
        )
    )
    open_value = _to_float(
        _pick_first_number_from_sources(
            regular_sources,
            ("open", "open_price", "openPrice", "regularMarketOpen"),
            zero_is_missing=True,
        )
    )
    high_value = _to_float(
        _pick_first_number_from_sources(
            regular_sources,
            ("high", "dayHigh", "day_high", "regularMarketDayHigh"),
            zero_is_missing=True,
        )
    )
    low_value = _to_float(
        _pick_first_number_from_sources(
            regular_sources,
            ("low", "dayLow", "day_low", "regularMarketDayLow"),
            zero_is_missing=True,
        )
    )
    volume = _pick_first_from_sources(
        regular_sources,
        ("volume", "turnover_volume", "lastVolume", "last_volume", "regularMarketVolume", "marketVolume"),
    )
    amount = _pick_first_from_sources(
        regular_sources,
        ("amount", "turnover", "turnover_amount", "last_amount", "trading_value", "trade_value"),
    )
    amplitude_value = _pick_first_number_from_sources(
        regular_sources,
        ("amplitude", "swing", "swing_pct", "amplitude_pct", "amplitudePercent"),
    )

    source_candidate = _pick_first_from_sources(quote_sources, ("source", "provider", "data_source"))
    selected_bundle: Dict[str, Any]
    if session_kind == "completed":
        selected_bundle = _select_quote_bundle(
            [
                _build_quote_bundle(
                    name="session_eod_context",
                    primary=today_context,
                    secondary=yesterday_context,
                    prefer_close_as_price=True,
                ),
                _build_quote_bundle(
                    name="market_snapshot",
                    primary=snapshot,
                    secondary=yesterday_context,
                    prefer_close_as_price=True,
                ),
                _build_quote_bundle(
                    name="realtime_quote",
                    primary=realtime_context,
                    secondary=yesterday_context,
                    prefer_close_as_price=True,
                ),
            ],
            preferred_names=("session_eod_context", "market_snapshot", "realtime_quote"),
            require_close=True,
        )
        regular_price = selected_bundle.get("close") if selected_bundle.get("close") is not None else selected_bundle.get("price")
    elif session_kind == "extended":
        selected_bundle = _select_quote_bundle(
            [
                _build_quote_bundle(
                    name="session_regular_context",
                    primary=today_context,
                    secondary=yesterday_context,
                    prefer_close_as_price=True,
                ),
                _build_quote_bundle(
                    name="market_snapshot",
                    primary=snapshot,
                    secondary=yesterday_context,
                    prefer_close_as_price=True,
                ),
                _build_quote_bundle(
                    name="realtime_quote",
                    primary=realtime_context,
                    secondary=yesterday_context,
                    prefer_close_as_price=True,
                ),
            ],
            preferred_names=("session_regular_context", "market_snapshot", "realtime_quote"),
            require_close=True,
        )
        regular_price = selected_bundle.get("close") if selected_bundle.get("close") is not None else close
    else:
        selected_bundle = _select_quote_bundle(
            [
                _build_quote_bundle(
                    name="realtime_quote",
                    primary=realtime_context,
                    secondary=yesterday_context,
                    prefer_close_as_price=False,
                ),
                _build_quote_bundle(
                    name="session_intraday_context",
                    primary=today_context,
                    secondary=yesterday_context,
                    prefer_close_as_price=False,
                ),
                _build_quote_bundle(
                    name="market_snapshot",
                    primary=snapshot,
                    secondary=yesterday_context,
                    prefer_close_as_price=False,
                ),
            ],
            preferred_names=("realtime_quote", "session_intraday_context", "market_snapshot"),
            require_close=False,
        )
        regular_price = (
            selected_bundle.get("price")
            if selected_bundle.get("price") is not None
            else selected_bundle.get("close")
            if selected_bundle.get("close") is not None
            else live_price
            if live_price is not None
            else close
        )

    if selected_bundle:
        close = selected_bundle.get("close") if selected_bundle.get("close") is not None else close
        prev_close = selected_bundle.get("prev_close") if selected_bundle.get("prev_close") is not None else prev_close
        source_candidate = selected_bundle.get("source") or source_candidate
        provided_regular_change = (
            selected_bundle.get("change_amount")
            if selected_bundle.get("change_amount") is not None
            else provided_regular_change
        )
        provided_regular_pct = (
            selected_bundle.get("change_pct")
            if selected_bundle.get("change_pct") is not None
            else provided_regular_pct
        )
        open_value = selected_bundle.get("open") if selected_bundle.get("open") is not None else open_value
        high_value = selected_bundle.get("high") if selected_bundle.get("high") is not None else high_value
        low_value = selected_bundle.get("low") if selected_bundle.get("low") is not None else low_value
        volume = selected_bundle.get("volume") if selected_bundle.get("volume") is not None else volume
        amount = selected_bundle.get("amount") if selected_bundle.get("amount") is not None else amount
        amplitude_value = selected_bundle.get("amplitude") if selected_bundle.get("amplitude") is not None else amplitude_value

    selected_bundle_name = str(selected_bundle.get("name") or "")

    recovered_prev_close = _derive_prev_close_from_change(
        close if close is not None else regular_price,
        change_amount=provided_regular_change,
        change_pct=provided_regular_pct,
    )
    prev_close_recovered = False
    authoritative_prev_close = (
        selected_bundle.get("prev_close") is not None
        and selected_bundle_name in {"session_eod_context", "session_regular_context"}
    )
    if recovered_prev_close is not None:
        flat_placeholder = (
            session_kind == "completed"
            and close is not None
            and prev_close is not None
            and _numbers_nearly_equal(prev_close, close)
            and (_has_meaningful_change(provided_regular_change) or _has_meaningful_change(provided_regular_pct))
        )
        computed_from_existing = _compute_change(close if close is not None else regular_price, prev_close)
        hinted_conflict = _material_quote_conflict(computed_from_existing[0], provided_regular_change) or _material_quote_conflict(
            computed_from_existing[1],
            provided_regular_pct,
            percent=True,
        )
        should_replace_prev_close = prev_close is None or flat_placeholder
        if session_kind == "completed" and hinted_conflict and not authoritative_prev_close:
            should_replace_prev_close = True
        if should_replace_prev_close:
            prev_close = recovered_prev_close
            prev_close_recovered = True

    regular_change, regular_change_pct = _compute_change(regular_price, prev_close)

    regular_conflict = _material_quote_conflict(regular_change, provided_regular_change) or _material_quote_conflict(
        regular_change_pct,
        provided_regular_pct,
        percent=True,
    )

    extended_price_candidates = (
        "extended_price",
        "pre_market_price",
        "premarket_price",
        "preMarketPrice",
        "after_hours_price",
        "post_market_price",
        "postMarketPrice",
    )
    extended_price = _to_float(
        _pick_first_number_from_sources(quote_sources, extended_price_candidates, zero_is_missing=True)
    )
    if extended_price is None and session_kind == "extended":
        extended_price = live_price

    extended_change, extended_change_pct = _compute_change(extended_price, prev_close)

    provided_extended_change = _to_float(
        _pick_first_number_from_sources(
            quote_sources,
            (
                "extended_change",
                "pre_market_change",
                "preMarketChange",
                "after_hours_change",
                "postMarketChange",
                "change_amount",
                "change",
            ),
        )
    )
    provided_extended_pct = _to_float(
        _pick_first_number_from_sources(
            quote_sources,
            (
                "extended_change_pct",
                "pre_market_change_pct",
                "preMarketChangePercent",
                "after_hours_change_pct",
                "postMarketChangePercent",
                "pct_chg",
                "change_pct",
                "changePercent",
                "percent_change",
            ),
        )
    )

    extended_conflict = _material_quote_conflict(extended_change, provided_extended_change) or _material_quote_conflict(
        extended_change_pct,
        provided_extended_pct,
        percent=True,
    )

    if regular_change is not None:
        regular_change_text = _format_price(regular_change)
        regular_change_pct_text = _format_percent(regular_change_pct)
    elif provided_regular_change is not None or provided_regular_pct is not None:
        regular_change_text = _format_price(provided_regular_change, reason="接口未返回")
        regular_change_pct_text = _format_percent(provided_regular_pct, reason="接口未返回")
    else:
        regular_change_text = _na("接口未返回")
        regular_change_pct_text = _na("接口未返回")

    if extended_price is None:
        extended_price_text = _na("当前数据源未提供")
        extended_change_text = _na("当前数据源未提供")
        extended_change_pct_text = _na("当前数据源未提供")
    else:
        extended_price_text = _format_price(extended_price)
        if extended_change is not None:
            extended_change_text = _format_price(extended_change)
            extended_change_pct_text = _format_percent(extended_change_pct)
        elif provided_extended_change is not None or provided_extended_pct is not None:
            extended_change_text = _format_price(provided_extended_change, reason="当前数据源未提供")
            extended_change_pct_text = _format_percent(provided_extended_pct, reason="当前数据源未提供")
        else:
            extended_change_text = _na("当前数据源未提供")
            extended_change_pct_text = _na("当前数据源未提供")

    extended_timestamp = _pick_first_from_sources(
        (snapshot, realtime_context, time_context),
        (
            "extended_timestamp",
            "pre_market_timestamp",
            "preMarketTime",
            "after_hours_timestamp",
            "postMarketTime",
        ),
    )
    extended_timestamp_text = _format_text(extended_timestamp, reason="当前数据源未提供")
    if _is_missing_value(amount) and regular_price is not None and not _is_missing_value(volume):
        amount = round(regular_price * float(volume), 2)

    volume_ratio = _pick_first_number_from_sources(
        (realtime_context, price_data, volume_analysis, snapshot),
        ("volume_ratio", "volumeRatio", "volume_ratio_5d"),
        zero_is_missing=True,
    )
    if _is_missing_value(volume_ratio, zero_is_missing=True):
        volume_ratio = None

    turnover_rate = _pick_first_number_from_sources(
        (realtime_context, volume_analysis, snapshot),
        ("turnover_rate", "turnoverRate"),
        zero_is_missing=True,
    )
    if _is_missing_value(turnover_rate, zero_is_missing=True):
        turnover_rate = None

    avg_price = _pick_first_number_from_sources(
        (realtime_context, price_data, today_context, snapshot),
        ("avg_price", "average_price", "avgPrice"),
        zero_is_missing=True,
    )
    vwap = _pick_first_number_from_sources(
        (realtime_context, price_data, today_context, snapshot),
        ("vwap", "VWAP"),
        zero_is_missing=True,
    )

    if _is_missing_value(amplitude_value):
        amplitude_value = _compute_amplitude_pct(high_value, low_value, prev_close)

    consistency_warnings: List[str] = []
    if prev_close_recovered:
        consistency_warnings.append("上一已收盘交易日缺少可靠昨收，已按收盘口径还原昨收并重算涨跌")
    if session_kind == "completed" and selected_bundle_name not in {"session_eod_context", "extended_regular_close"}:
        consistency_warnings.append("上一已收盘交易日缺少完整 EOD 行情源，本次已锁定单一 fallback 行情源并按同口径重算")
    if regular_conflict:
        consistency_warnings.append("常规时段多源涨跌口径存在较大偏差，已优先采用当前价与昨收重算结果")
    if extended_conflict:
        consistency_warnings.append("扩展时段多源涨跌口径存在较大偏差，已优先采用扩展价格与昨收重算结果")
    if session_kind == "extended" and close is None:
        consistency_warnings.append("当前处于扩展时段，但缺少 regular close，常规口径字段可能不完整")
    explicit_session_date = _iso_or_none(time_context.get("market_session_date"))
    if explicit_session_date and market_timestamp and explicit_session_date != _market_session_date_from_timestamp(market_timestamp):
        consistency_warnings.append("接口返回的参考交易日与行情时间戳不一致，已优先采用时间戳推导出的会话日期")

    has_market_snapshot = any(
        value is not None
        for value in (
            regular_price,
            prev_close,
            high_value,
            low_value,
            _to_float(volume),
            _to_float(amount),
        )
    )
    source = source_candidate if has_market_snapshot else None
    market_session_date = _market_session_date_from_timestamp(market_timestamp) or _iso_or_none(time_context.get("market_session_date"))
    price_semantics = _describe_price_basis(
        session_kind,
        session_label=session_label,
        market_session_date=market_session_date,
    )

    regular_fields = [
        {"label": labels["current_price_label"], "value": _format_price(regular_price)},
        {"label": labels["prev_close_label"], "value": _format_price(prev_close)},
        {
            "label": labels["open_label"],
            "value": _format_price(open_value),
        },
        {
            "label": labels["high_label"],
            "value": _format_price(high_value),
        },
        {
            "label": labels["low_label"],
            "value": _format_price(low_value),
        },
        {"label": labels["close_label"], "value": _format_price(close)},
        {"label": labels["change_amount_label"], "value": regular_change_text},
        {"label": labels["change_pct_label"], "value": regular_change_pct_text},
        {
            "label": labels["amplitude_label"],
            "value": _format_percent(amplitude_value),
        },
        {"label": labels["volume_label"], "value": _format_volume(volume, reason="当前数据源未提供")},
        {"label": labels["amount_label"], "value": _format_amount(amount, reason="当前数据源未提供")},
        {
            "label": labels["volume_ratio_label"],
            "value": _format_decimal(volume_ratio, reason="当前数据源未提供"),
        },
        {
            "label": labels["turnover_rate_label"],
            "value": _format_percent(turnover_rate, reason="字段待接入"),
        },
        {
            "label": get_standard_report_field_label("average_price", language),
            "value": _format_nonzero_price(avg_price, reason="字段待接入"),
        },
        {
            "label": get_standard_report_field_label("vwap", language),
            "value": _format_nonzero_price(vwap, reason="字段待接入"),
        },
        {"label": labels["source_label"], "value": _format_text(source, reason="上游映射缺失")},
        {
            "label": get_standard_report_field_label("session_type", language),
            "value": _format_text(session_label, reason="接口未返回"),
        },
    ]

    display_source = _describe_market_feed(
        source,
        session_kind=session_kind,
        selected_bundle_name=selected_bundle_name,
    )
    open_display_label = (
        "Regular Open"
        if session_kind == "extended"
        else "Session Open"
        if session_kind in {"intraday", "regular"}
        else "Open"
    )
    high_display_label = (
        "Regular High"
        if session_kind == "extended"
        else "Session High"
        if session_kind in {"intraday", "regular"}
        else "High"
    )
    low_display_label = (
        "Regular Low"
        if session_kind == "extended"
        else "Session Low"
        if session_kind in {"intraday", "regular"}
        else "Low"
    )
    should_show_close = (
        session_kind not in {"intraday", "regular"}
        and close is not None
        and regular_price is not None
        and not _numbers_nearly_equal(close, regular_price, tolerance=max(0.01, abs(regular_price) * 0.0005))
    )
    if session_kind in {"intraday", "regular"}:
        should_show_close = False
    display_fields = [
        {"label": price_semantics.get("price_label") or "Analysis Price", "value": _format_price(regular_price)},
        {"label": "Prev Close", "value": _format_price(prev_close)},
        {"label": open_display_label, "value": _format_price(open_value)},
        {"label": high_display_label, "value": _format_price(high_value)},
        {"label": low_display_label, "value": _format_price(low_value)},
    ]
    if should_show_close:
        display_fields.append(
            {
                "label": "Reference Close" if session_kind in {"intraday", "regular"} else "Close",
                "value": _format_price(close),
            }
        )
    display_fields.extend(
        [
            {"label": "Change", "value": regular_change_text},
            {"label": "Change %", "value": regular_change_pct_text},
            {"label": "Volume", "value": _format_volume(volume, reason="当前数据源未提供")},
            {"label": "Turnover", "value": _format_amount(amount, reason="当前数据源未提供")},
            {
                "label": "Volume Ratio",
                "value": _format_decimal(volume_ratio, reason="当前数据源未提供"),
            },
            {
                "label": "Turnover Rate",
                "value": _format_percent(turnover_rate, reason="字段待接入"),
            },
            {
                "label": "Avg Price",
                "value": _format_nonzero_price(avg_price, reason="字段待接入"),
            },
            {
                "label": "VWAP",
                "value": _format_nonzero_price(vwap, reason="字段待接入"),
            },
            {
                "label": "Market Feed",
                "value": display_source,
            },
        ]
    )

    extended_fields = [
        {
            "label": "盘前价",
            "value": _format_price(
                _pick_first_from_sources(quote_sources, ("pre_market_price", "premarket_price", "preMarketPrice")),
                reason="当前数据源未提供",
            ),
        },
        {
            "label": "盘后价",
            "value": _format_price(
                _pick_first_from_sources(quote_sources, ("after_hours_price", "post_market_price", "postMarketPrice")),
                reason="当前数据源未提供",
            ),
        },
        {"label": "扩展时段价格", "value": extended_price_text},
        {"label": "扩展时段涨跌额", "value": extended_change_text},
        {"label": "扩展时段涨跌幅", "value": extended_change_pct_text},
        {"label": "扩展时段时间", "value": extended_timestamp_text},
        {"label": "会话标签", "value": _format_text(session_label, reason="接口未返回")},
    ]

    return {
        "regular_fields": regular_fields,
        "display_fields": display_fields,
        "extended_fields": extended_fields,
        "consistency_warnings": consistency_warnings,
        "regular_price_numeric": regular_price,
        "regular_metrics": {
            "price": regular_price,
            "prev_close": prev_close,
            "change_amount": regular_change,
            "change_pct": regular_change_pct,
            "open": _to_float(open_value),
            "high": high_value,
            "low": low_value,
            "close": close,
            "amplitude": _to_float(amplitude_value),
            "volume": _to_float(volume),
            "amount": _to_float(amount),
            "volume_ratio": _to_float(volume_ratio),
            "turnover_rate": _to_float(turnover_rate),
            "average_price": _to_float(avg_price),
            "vwap": _to_float(vwap),
        },
        "time_context": {
            "market_timestamp": _iso_or_none(market_timestamp),
            "market_timestamp_local": _format_local_datetime(market_timestamp),
            "market_timestamp_bjt": _format_bjt_datetime(market_timestamp),
            "market_session_date": market_session_date,
            "report_generated_at": _iso_or_none(time_context.get("report_generated_at")),
            "report_generated_at_bjt": _format_bjt_datetime(time_context.get("report_generated_at")),
            "news_published_at": _iso_or_none(time_context.get("news_published_at")),
            "news_published_at_bjt": _format_bjt_datetime(time_context.get("news_published_at")),
            "session_type": _iso_or_none(session_type) or str(session_type or ""),
            "session_label": session_label,
            "session_kind": session_kind,
            "price_label": price_semantics.get("price_label"),
            "price_basis": price_semantics.get("price_basis"),
            "price_basis_detail": price_semantics.get("price_basis_detail"),
            "reference_session": price_semantics.get("reference_session"),
            "price_context_note": price_semantics.get("price_context_note"),
            "source_display": display_source,
            "raw_source": _iso_or_none(source_candidate) or str(source_candidate or ""),
        },
    }


def _build_technical_fields(
    *,
    language: str,
    dashboard: Dict[str, Any],
    market_regular_price: Optional[float],
) -> List[Dict[str, str]]:
    field_language = "zh"
    labels = get_report_labels(field_language)
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    data_persp = dashboard.get("data_perspective") if isinstance(dashboard.get("data_perspective"), dict) else {}
    trend_data = data_persp.get("trend_status") if isinstance(data_persp.get("trend_status"), dict) else {}
    price_data = data_persp.get("price_position") if isinstance(data_persp.get("price_position"), dict) else {}
    volume_analysis = data_persp.get("volume_analysis") if isinstance(data_persp.get("volume_analysis"), dict) else {}
    alpha_data = data_persp.get("alpha_vantage") if isinstance(data_persp.get("alpha_vantage"), dict) else {}
    technical_nodes = structured.get("technicals") if isinstance(structured.get("technicals"), dict) else {}
    trend_analysis = structured.get("trend_analysis") if isinstance(structured.get("trend_analysis"), dict) else {}
    market_context = structured.get("market_context") if isinstance(structured.get("market_context"), dict) else {}
    today_context = market_context.get("today") if isinstance(market_context.get("today"), dict) else {}
    realtime_context = structured.get("realtime_context") if isinstance(structured.get("realtime_context"), dict) else {}

    ma5_value = _pick_first_number_from_sources(
        (today_context, price_data),
        ("ma5", "MA5", "ma_5", "moving_average_5"),
        zero_is_missing=True,
    )
    if _is_missing_value(ma5_value, zero_is_missing=True):
        ma5_value = _metric_node_value(technical_nodes, "ma5", zero_is_missing=True)

    ma10_value = _pick_first_number_from_sources(
        (today_context, price_data),
        ("ma10", "MA10", "ma_10", "moving_average_10"),
        zero_is_missing=True,
    )
    if _is_missing_value(ma10_value, zero_is_missing=True):
        ma10_value = _metric_node_value(technical_nodes, "ma10", zero_is_missing=True)

    ma20_value = _pick_first_number_from_sources(
        (today_context, price_data),
        ("ma20", "MA20", "ma_20", "moving_average_20"),
        zero_is_missing=True,
    )
    if _is_missing_value(ma20_value, zero_is_missing=True):
        ma20_value = _metric_node_value(technical_nodes, "ma20", zero_is_missing=True)
    if _is_missing_value(ma20_value, zero_is_missing=True):
        ma20_value = _pick_first_number_from_sources((alpha_data,), ("sma20",), zero_is_missing=True)

    ma60_value = _pick_first_number_from_sources(
        (today_context, price_data),
        ("ma60", "MA60", "ma_60", "moving_average_60"),
        zero_is_missing=True,
    )
    if _is_missing_value(ma60_value, zero_is_missing=True):
        ma60_value = _metric_node_value(technical_nodes, "ma60", zero_is_missing=True)
    if _is_missing_value(ma60_value, zero_is_missing=True):
        ma60_value = _pick_first_number_from_sources((alpha_data,), ("sma60",), zero_is_missing=True)

    rsi14_value = _pick_first(alpha_data, ("rsi14",))
    if _is_missing_value(rsi14_value):
        rsi14_value = _metric_node_value(technical_nodes, "rsi14")

    vwap_value = _pick_first_number_from_sources(
        (realtime_context, price_data, today_context),
        ("vwap", "VWAP"),
        zero_is_missing=True,
    )
    if _is_missing_value(vwap_value, zero_is_missing=True):
        vwap_value = _metric_node_value(technical_nodes, "vwap", zero_is_missing=True)

    ma5_reason = _metric_node_reason(technical_nodes, "ma5")
    ma10_reason = _metric_node_reason(technical_nodes, "ma10")
    ma20_reason = _metric_node_reason(technical_nodes, "ma20")
    ma60_reason = _metric_node_reason(technical_nodes, "ma60")
    vwap_reason = _metric_node_reason(technical_nodes, "vwap", default="接口未返回")

    current_price_for_bias = market_regular_price
    if current_price_for_bias is None:
        current_price_for_bias = _pick_first_number_from_sources(
            (today_context, price_data, realtime_context),
            ("price", "current_price", "currentPrice", "close"),
            zero_is_missing=True,
        )

    ma20_numeric = _to_float(ma20_value)
    ma5_numeric = _to_float(ma5_value)

    ma20_position = _na("接口未返回")
    if market_regular_price is not None and ma20_numeric is not None:
        ma20_position = "当前位于 MA20 上方" if market_regular_price >= ma20_numeric else "当前位于 MA20 下方"

    bias_value = None
    raw_bias = _pick_first(price_data, ("bias_ma5",))
    if ma5_numeric not in (None, 0) and current_price_for_bias is not None:
        if not _is_missing_value(raw_bias):
            bias_value = raw_bias
        else:
            current_numeric = _to_float(current_price_for_bias)
            if current_numeric is not None:
                bias_value = ((current_numeric - ma5_numeric) / ma5_numeric) * 100

    alignment_text = _normalize_inline_text(trend_data.get("ma_alignment")) or _normalize_inline_text(
        trend_analysis.get("ma_alignment")
    )
    bullish = trend_data.get("is_bullish")
    if alignment_text:
        alignment = alignment_text
    elif bullish is True:
        alignment = "多头排列"
    elif bullish is False:
        alignment = "空头/震荡"
    else:
        alignment = _na("接口未返回")

    trend_strength = _pick_first_number_from_sources(
        (trend_data, trend_analysis),
        ("trend_score", "trend_strength"),
        zero_is_missing=True,
    )
    trend_strength_text = (
        f"{_format_decimal(trend_strength)}/100"
        if not _is_missing_value(trend_strength, zero_is_missing=True)
        else _na("接口未返回")
    )

    alpha_ma20_value = _pick_first_number_from_sources((alpha_data,), ("sma20",), zero_is_missing=True)
    alpha_ma60_value = _pick_first_number_from_sources((alpha_data,), ("sma60",), zero_is_missing=True)
    alpha_rsi14_value = _pick_first(alpha_data, ("rsi14",))

    def _resolve_fallback_source(metric_name: str, value: Any, *, alpha_value: Any = None) -> Optional[str]:
        if _is_missing_value(value, zero_is_missing=metric_name != "rsi14"):
            return None
        numeric_value = _to_float(value)
        numeric_alpha = _to_float(alpha_value)
        if numeric_value is not None and numeric_alpha is not None and abs(numeric_value - numeric_alpha) < 0.0001:
            return "alpha_vantage"
        if metric_name in {"ma5", "ma10", "ma20", "ma60", "vwap"}:
            return "local_from_ohlcv"
        return None

    def _metric_meta(name: str, *, fallback_source: Optional[str] = None, fallback_status: Optional[str] = None) -> Dict[str, Optional[str]]:
        node = technical_nodes.get(name) if isinstance(technical_nodes.get(name), dict) else {}
        raw_source = node.get("source") or fallback_source
        raw_status = node.get("status") or fallback_status
        return {
            "source": _format_field_source(raw_source),
            "status": _format_field_status(raw_status),
        }

    ma5_meta = _metric_meta("ma5", fallback_source=_resolve_fallback_source("ma5", ma5_value), fallback_status="ok" if not _is_missing_value(ma5_value, zero_is_missing=True) else "data_unavailable")
    ma10_meta = _metric_meta("ma10", fallback_source=_resolve_fallback_source("ma10", ma10_value), fallback_status="ok" if not _is_missing_value(ma10_value, zero_is_missing=True) else "data_unavailable")
    ma20_meta = _metric_meta("ma20", fallback_source=_resolve_fallback_source("ma20", ma20_value, alpha_value=alpha_ma20_value), fallback_status="ok" if not _is_missing_value(ma20_value, zero_is_missing=True) else "data_unavailable")
    ma60_meta = _metric_meta("ma60", fallback_source=_resolve_fallback_source("ma60", ma60_value, alpha_value=alpha_ma60_value), fallback_status="ok" if not _is_missing_value(ma60_value, zero_is_missing=True) else "data_unavailable")
    rsi14_meta = _metric_meta("rsi14", fallback_source=_resolve_fallback_source("rsi14", rsi14_value, alpha_value=alpha_rsi14_value), fallback_status="ok" if not _is_missing_value(rsi14_value) else "data_unavailable")
    vwap_meta = _metric_meta("vwap", fallback_source=_resolve_fallback_source("vwap", vwap_value), fallback_status="ok" if not _is_missing_value(vwap_value, zero_is_missing=True) else "data_unavailable")

    return [
        {"label": "MA5", "value": _format_nonzero_price(ma5_value, reason=ma5_reason), **ma5_meta},
        {"label": "MA10", "value": _format_nonzero_price(ma10_value, reason=ma10_reason), **ma10_meta},
        {"label": "MA20", "value": _format_nonzero_price(ma20_value, reason=ma20_reason), **ma20_meta},
        {"label": "MA60", "value": _format_nonzero_price(ma60_value, reason=ma60_reason), **ma60_meta},
        {
            "label": get_standard_report_field_label("rsi14", field_language),
            "value": _format_decimal(rsi14_value, reason="字段待接入"),
            **rsi14_meta,
        },
        {
            "label": get_standard_report_field_label("vwap", field_language),
            "value": _format_nonzero_price(vwap_value, reason=vwap_reason),
            **vwap_meta,
        },
        {
            "label": "支撑位",
            "value": _format_nonzero_price(
                _pick_first_number_from_sources(
                    (price_data,),
                    ("support_level", "support"),
                    zero_is_missing=True,
                ),
                reason="接口未返回",
            ),
            "source": "本地派生",
            "status": "派生",
        },
        {
            "label": "压力位",
            "value": _format_nonzero_price(
                _pick_first_number_from_sources(
                    (price_data,),
                    ("resistance_level", "resistance"),
                    zero_is_missing=True,
                ),
                reason="接口未返回",
            ),
            "source": "本地派生",
            "status": "派生",
        },
        {
            "label": get_standard_report_field_label("bias_ma5", field_language),
            "value": _format_percent(bias_value, reason=ma5_reason),
            "source": "本地派生",
            "status": "派生",
        },
        {
            "label": labels["trend_strength_label"],
            "value": trend_strength_text,
            "source": "本地派生",
            "status": "派生",
        },
        {
            "label": get_standard_report_field_label("ma_alignment", field_language),
            "value": alignment,
            "source": "本地派生",
            "status": "派生",
        },
        {
            "label": get_standard_report_field_label("ma20_position", field_language),
            "value": ma20_position,
            "source": "本地派生",
            "status": "派生",
        },
        {
            "label": get_standard_report_field_label("volume_judgment", field_language),
            "value": _summarize_volume_judgment(volume_analysis),
            "source": "本地派生",
            "status": "派生",
        },
    ]


def _build_fundamental_fields(
    *,
    language: str,
    dashboard: Dict[str, Any],
    market_snapshot: Dict[str, Any],
) -> List[Dict[str, str]]:
    field_language = "zh"
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    fundamentals = structured.get("fundamentals") if isinstance(structured.get("fundamentals"), dict) else {}
    normalized = fundamentals.get("normalized") if isinstance(fundamentals.get("normalized"), dict) else {}
    field_periods = fundamentals.get("field_periods") if isinstance(fundamentals.get("field_periods"), dict) else {}
    field_sources = fundamentals.get("field_sources") if isinstance(fundamentals.get("field_sources"), dict) else {}
    fundamental_context = structured.get("fundamental_context") if isinstance(structured.get("fundamental_context"), dict) else {}
    valuation_data = (
        fundamental_context.get("valuation", {}).get("data")
        if isinstance(fundamental_context.get("valuation"), dict)
        else {}
    )
    valuation_data = valuation_data if isinstance(valuation_data, dict) else {}
    earnings_context = (
        fundamental_context.get("earnings", {}).get("data")
        if isinstance(fundamental_context.get("earnings"), dict)
        else {}
    )
    earnings_context = earnings_context if isinstance(earnings_context, dict) else {}
    financial_report = earnings_context.get("financial_report") if isinstance(earnings_context.get("financial_report"), dict) else {}
    earnings_analysis = structured.get("earnings_analysis") if isinstance(structured.get("earnings_analysis"), dict) else {}
    quarterly_series = earnings_analysis.get("quarterly_series") if isinstance(earnings_analysis.get("quarterly_series"), list) else []
    realtime_context = structured.get("realtime_context") if isinstance(structured.get("realtime_context"), dict) else {}

    def _n(*keys: str) -> Any:
        return _pick_first_from_sources((normalized, valuation_data, financial_report), keys)

    market_cap = _n("marketCap", "totalMarketCap", "total_mv", "market_cap") or _pick_first_from_sources(
        (market_snapshot, realtime_context),
        ("total_mv", "marketCap", "market_cap"),
    )
    float_market_cap = _n("floatMarketCap", "circulatingMarketCap", "circ_mv", "float_market_cap") or _pick_first_from_sources(
        (market_snapshot, realtime_context),
        ("circ_mv", "floatMarketCap", "float_market_cap"),
    )
    shares = _n("sharesOutstanding", "totalShares", "shares_outstanding") or _pick_first_from_sources(
        (market_snapshot, realtime_context),
        ("sharesOutstanding", "shares_outstanding", "totalShares"),
    )
    float_shares = _n("floatShares", "float_shares") or _pick_first_from_sources(
        (market_snapshot, realtime_context),
        ("floatShares", "float_shares"),
    )
    price_to_book = _n("priceToBook", "pb", "pb_ratio") or _pick_first_from_sources(
        (market_snapshot, realtime_context),
        ("pb_ratio", "priceToBook"),
    )
    beta = _n("beta", "Beta")
    high_52w = _n("fiftyTwoWeekHigh", "high52w", "week52_high", "52week_high") or _pick_first_from_sources(
        (market_snapshot, realtime_context),
        ("high_52w", "fiftyTwoWeekHigh", "52week_high"),
    )
    low_52w = _n("fiftyTwoWeekLow", "low52w", "week52_low", "52week_low") or _pick_first_from_sources(
        (market_snapshot, realtime_context),
        ("low_52w", "fiftyTwoWeekLow", "52week_low"),
    )
    revenue = _n("revenue", "totalRevenue", "revenue_ttm") or _pick_first(financial_report, ("revenue", "total_revenue"))
    net_income = (
        _n("netIncome", "net_income", "net_profit")
        or _pick_first(financial_report, ("netIncome", "net_income", "net_profit", "netProfit"))
        or _first_quarter_metric(quarterly_series, "netIncome", "net_income")
    )
    free_cashflow = _n("freeCashflow", "freeCashFlow", "free_cashflow")
    operating_cashflow = _n("operatingCashflow", "operatingCashFlow", "operating_cashflow")

    def _field_meta(field_name: str, default_basis: Optional[str] = None) -> Dict[str, Optional[str]]:
        return {
            "source": _format_field_source(field_sources.get(field_name)),
            "status": _format_field_basis(field_periods.get(field_name) or default_basis),
        }

    def _field_reason(field_name: str, default_reason: str) -> str:
        basis = str(field_periods.get(field_name) or "").strip().lower().replace("-", "_")
        if basis == "ttm_pending_validation":
            return "口径冲突，待校正"
        return default_reason

    def _display_value(field_name: str, value: Any) -> Any:
        basis = str(field_periods.get(field_name) or "").strip().lower().replace("-", "_")
        if basis == "ttm_pending_validation":
            return None
        return value

    return [
        {"label": _label_with_basis(get_standard_report_field_label("market_cap", field_language), field_periods.get("marketCap")), "value": _format_amount(market_cap, reason="接口未返回"), **_field_meta("marketCap", "latest")},
        {"label": _label_with_basis(get_standard_report_field_label("float_market_cap", field_language), "latest"), "value": _format_amount(float_market_cap, reason="字段待接入"), **_field_meta("floatMarketCap", "latest")},
        {"label": _label_with_basis(get_standard_report_field_label("shares_outstanding", field_language), field_periods.get("sharesOutstanding")), "value": _format_volume(shares, reason="字段待接入"), **_field_meta("sharesOutstanding", "latest")},
        {"label": _label_with_basis(get_standard_report_field_label("float_shares", field_language), field_periods.get("floatShares")), "value": _format_volume(float_shares, reason="字段待接入"), **_field_meta("floatShares", "latest")},
        {"label": get_standard_report_field_label("trailing_pe", field_language), "value": _format_decimal(_n("trailingPE"), reason="接口未返回"), **_field_meta("trailingPE", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("forward_pe", field_language), field_periods.get("forwardPE") or "consensus"), "value": _format_decimal(_n("forwardPE"), reason="接口未返回"), **_field_meta("forwardPE", "consensus")},
        {"label": _label_with_basis(get_standard_report_field_label("price_to_book", field_language), field_periods.get("priceToBook") or "latest"), "value": _format_decimal(price_to_book, reason="字段待接入"), **_field_meta("priceToBook", "latest")},
        {"label": get_standard_report_field_label("beta", field_language), "value": _format_decimal(beta, reason="字段待接入"), **_field_meta("beta", "latest")},
        {"label": get_standard_report_field_label("fifty_two_week_high", field_language), "value": _format_price(high_52w, reason="字段待接入"), **_field_meta("fiftyTwoWeekHigh", "rolling_52w")},
        {"label": get_standard_report_field_label("fifty_two_week_low", field_language), "value": _format_price(low_52w, reason="字段待接入"), **_field_meta("fiftyTwoWeekLow", "rolling_52w")},
        {"label": get_standard_report_field_label("historical_high", field_language), "value": _format_price(_n("historicalHigh", "allTimeHigh"), reason="当前数据源未提供"), **_field_meta("historicalHigh")},
        {"label": get_standard_report_field_label("historical_low", field_language), "value": _format_price(_n("historicalLow", "allTimeLow"), reason="当前数据源未提供"), **_field_meta("historicalLow")},
        {"label": _label_with_basis(get_standard_report_field_label("revenue", field_language), field_periods.get("totalRevenue") or "ttm"), "value": _format_amount(revenue, reason="接口未返回"), **_field_meta("totalRevenue", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("net_income", field_language), field_periods.get("netIncome") or "ttm"), "value": _format_amount(net_income, reason="接口未返回"), **_field_meta("netIncome", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("free_cash_flow", field_language), field_periods.get("freeCashflow") or "ttm"), "value": _format_amount(_display_value("freeCashflow", free_cashflow), reason=_field_reason("freeCashflow", "接口未返回")), **_field_meta("freeCashflow", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("operating_cash_flow", field_language), field_periods.get("operatingCashflow") or "ttm"), "value": _format_amount(_display_value("operatingCashflow", operating_cashflow), reason=_field_reason("operatingCashflow", "接口未返回")), **_field_meta("operatingCashflow", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("roe", field_language), field_periods.get("returnOnEquity") or "ttm"), "value": _format_percent(_display_value("returnOnEquity", _n("returnOnEquity", "roe")), from_ratio=True, reason=_field_reason("returnOnEquity", "接口未返回")), **_field_meta("returnOnEquity", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("roa", field_language), field_periods.get("returnOnAssets") or "ttm"), "value": _format_percent(_display_value("returnOnAssets", _n("returnOnAssets", "roa")), from_ratio=True, reason=_field_reason("returnOnAssets", "接口未返回")), **_field_meta("returnOnAssets", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("gross_margins", field_language), field_periods.get("grossMargins") or "ttm"), "value": _format_percent(_n("grossMargins"), from_ratio=True, reason="接口未返回"), **_field_meta("grossMargins", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("operating_margins", field_language), field_periods.get("operatingMargins") or "ttm"), "value": _format_percent(_n("operatingMargins"), from_ratio=True, reason="接口未返回"), **_field_meta("operatingMargins", "ttm")},
        {"label": _label_with_basis(get_standard_report_field_label("debt_to_equity", field_language), field_periods.get("debtToEquity") or "latest"), "value": _format_decimal(_n("debtToEquity"), reason="接口未返回"), **_field_meta("debtToEquity", "latest")},
        {"label": get_standard_report_field_label("current_ratio", field_language), "value": _format_decimal(_n("currentRatio"), reason="接口未返回"), **_field_meta("currentRatio", "latest")},
    ]


def _build_earnings_sentiment_fields(*, language: str, dashboard: Dict[str, Any]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    field_language = "zh"
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    earnings = structured.get("earnings_analysis") if isinstance(structured.get("earnings_analysis"), dict) else {}
    metrics = earnings.get("derived_metrics") if isinstance(earnings.get("derived_metrics"), dict) else {}
    earnings_sources = earnings.get("field_sources") if isinstance(earnings.get("field_sources"), dict) else {}
    quarterly_source = _format_field_source(earnings_sources.get("quarterly_series"))

    sentiment = structured.get("sentiment_analysis") if isinstance(structured.get("sentiment_analysis"), dict) else {}
    intel = dashboard.get("intelligence") if isinstance(dashboard.get("intelligence"), dict) else {}

    earnings_fields = [
        {"label": _label_with_basis(get_standard_report_field_label("earnings_summary", field_language), "latest_quarter"), "value": _summarize_earnings(earnings), "source": quarterly_source, "status": _format_field_basis("latest_quarter")},
        {"label": _label_with_basis(get_standard_report_field_label("revenue_growth_qoq", field_language), "latest_quarter_qoq"), "value": _format_percent(metrics.get("qoq_revenue_growth"), from_ratio=True, reason="接口未返回"), "source": quarterly_source, "status": _format_field_basis("latest_quarter_qoq")},
        {"label": _label_with_basis(get_standard_report_field_label("revenue_growth_yoy", field_language), "latest_quarter_yoy"), "value": _format_percent(metrics.get("yoy_revenue_growth"), from_ratio=True, reason="接口未返回"), "source": quarterly_source, "status": _format_field_basis("latest_quarter_yoy")},
        {"label": _label_with_basis(get_standard_report_field_label("net_income_change_qoq", field_language), "latest_quarter_qoq"), "value": _format_percent(metrics.get("qoq_net_income_change"), from_ratio=True, reason="接口未返回"), "source": quarterly_source, "status": _format_field_basis("latest_quarter_qoq")},
        {"label": _label_with_basis(get_standard_report_field_label("net_income_change_yoy", field_language), "latest_quarter_yoy"), "value": _format_percent(metrics.get("yoy_net_income_change"), from_ratio=True, reason="接口未返回"), "source": quarterly_source, "status": _format_field_basis("latest_quarter_yoy")},
    ]

    sentiment_fields = [
        {"label": get_standard_report_field_label("sentiment_summary", field_language), "value": _format_text(intel.get("sentiment_summary") or _summarize_sentiment(sentiment), reason="接口未返回")},
        {"label": get_standard_report_field_label("company_sentiment", field_language), "value": _format_text(localize_sentiment_status(sentiment.get("company_sentiment"), field_language), reason="接口未返回")},
        {"label": get_standard_report_field_label("industry_sentiment", field_language), "value": _format_text(localize_sentiment_status(sentiment.get("industry_sentiment"), field_language), reason="接口未返回")},
        {"label": get_standard_report_field_label("regulatory_sentiment", field_language), "value": _format_text(localize_sentiment_status(sentiment.get("regulatory_sentiment"), field_language), reason="接口未返回")},
        {
            "label": get_standard_report_field_label("confidence", field_language),
            "value": _format_text(
                localize_confidence_level(
                    sentiment.get("overall_confidence") or sentiment.get("confidence"),
                    field_language,
                ),
                reason="接口未返回",
            ),
        },
    ]

    return earnings_fields, sentiment_fields


def _build_info_fields(*, dashboard: Dict[str, Any], highlights: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    intel = _grade_intel_block(dashboard.get("intelligence") or {})
    highlight_payload = highlights if isinstance(highlights, dict) else {}
    return [
        {
            "label": "舆情情绪",
            "value": _format_text(
                highlight_payload.get("sentiment_summary") or intel.get("sentiment_summary"),
                reason="接口未返回",
            ),
        },
        {
            "label": "业绩预期",
            "value": _format_text(highlight_payload.get("earnings_outlook"), reason="接口未返回"),
        },
        {
            "label": "风险警报",
            "value": _join_list(
                highlight_payload.get("risk_alerts") or intel.get("risk_alerts") or [],
                empty_reason="接口未返回",
            ),
        },
        {
            "label": "利好催化",
            "value": _join_list(
                highlight_payload.get("positive_catalysts")
                or intel.get("positive_catalysts")
                or [intel.get("positive_catalysts_notice")],
                empty_reason="接口未返回",
            ),
        },
        {
            "label": "最新动态 / 重要公告",
            "value": _format_text(
                _pick_first_nonempty(highlight_payload.get("latest_news") or [])
                or intel.get("latest_news")
                or intel.get("latest_news_notice"),
                reason="接口未返回",
            ),
        },
        {
            "label": "新闻价值分级",
            "value": _format_text(intel.get("news_value_grade"), reason="接口未返回"),
        },
    ]


def _dedupe_numeric_levels(values: Iterable[Any], *, tolerance: Optional[float] = None) -> List[float]:
    levels: List[float] = []
    for value in values:
        numeric = _extract_first_number(value)
        if numeric is None:
            continue
        if any(abs(numeric - existing) <= (tolerance or max(abs(existing) * 0.0025, 0.12)) for existing in levels):
            continue
        levels.append(numeric)
    return levels


def _format_trade_level(level: Optional[float], *, reason: Optional[str] = None) -> str:
    if level is None:
        return _na("字段待接入")
    base = f"{level:.2f}"
    if reason:
        return f"{base}（{reason}）"
    return base


def _format_trade_range(center: Optional[float], volatility: float, *, reason: Optional[str] = None) -> str:
    if center is None:
        return _na("字段待接入")
    band = max(volatility * 0.22, center * 0.0025)
    lower = max(0.01, center - band)
    upper = center + band
    text = f"{lower:.2f}-{upper:.2f}"
    if reason:
        return f"{text}（{reason}）"
    return text


def _trade_confidence_label(score: int) -> str:
    if score >= 75:
        return "高"
    if score >= 55:
        return "中"
    return "低"


def _should_preserve_trade_text(value: Any) -> bool:
    text = _normalize_inline_text(value)
    if not text:
        return False
    upper_text = text.upper()
    return any(
        token in upper_text
        for token in ("MA", "ATR", "VWAP", "RSI", "MACD", "BOLL", "ADX", "EMA", "SMA")
    ) or any(
        token in text
        for token in ("均线", "支撑", "压力", "前高", "前低", "回踩", "突破", "缩量", "放量", "止损", "仓位")
    )


def _build_trade_setup(
    *,
    result: AnalysisResult,
    dashboard: Dict[str, Any],
    market_block: Dict[str, Any],
    technical_fields: List[Dict[str, str]],
) -> Dict[str, Any]:
    battle = dashboard.get("battle_plan") if isinstance(dashboard.get("battle_plan"), dict) else {}
    sniper = battle.get("sniper_points") if isinstance(battle.get("sniper_points"), dict) else {}
    position_strategy = battle.get("position_strategy") if isinstance(battle.get("position_strategy"), dict) else {}
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    fundamentals = structured.get("fundamentals") if isinstance(structured.get("fundamentals"), dict) else {}
    fundamentals_normalized = fundamentals.get("normalized") if isinstance(fundamentals.get("normalized"), dict) else {}
    market_metrics = market_block.get("regular_metrics") if isinstance(market_block.get("regular_metrics"), dict) else {}
    technical_map = _build_field_map(technical_fields or [])
    data_perspective = dashboard.get("data_perspective") if isinstance(dashboard.get("data_perspective"), dict) else {}
    price_position = data_perspective.get("price_position") if isinstance(data_perspective.get("price_position"), dict) else {}
    volume_analysis = data_perspective.get("volume_analysis") if isinstance(data_perspective.get("volume_analysis"), dict) else {}
    trend_status = data_perspective.get("trend_status") if isinstance(data_perspective.get("trend_status"), dict) else {}

    current_price = _to_float(
        _pick_first_from_sources(
            (market_metrics, price_position, result.market_snapshot if isinstance(result.market_snapshot, dict) else {}),
            ("price", "current_price", "regular_price_numeric", "close"),
            zero_is_missing=True,
        )
    )
    prev_close = _to_float(_pick_first_from_sources((market_metrics,), ("prev_close", "prevClose"), zero_is_missing=True))
    day_high = _to_float(_pick_first_from_sources((market_metrics, result.market_snapshot if isinstance(result.market_snapshot, dict) else {}), ("high",), zero_is_missing=True))
    day_low = _to_float(_pick_first_from_sources((market_metrics, result.market_snapshot if isinstance(result.market_snapshot, dict) else {}), ("low",), zero_is_missing=True))
    ma5 = _extract_first_number(price_position.get("ma5")) or _extract_first_number(technical_map.get("MA5"))
    ma10 = _extract_first_number(price_position.get("ma10")) or _extract_first_number(technical_map.get("MA10"))
    ma20 = _extract_first_number(price_position.get("ma20")) or _extract_first_number(technical_map.get("MA20"))
    ma60 = _extract_first_number(price_position.get("ma60")) or _extract_first_number(technical_map.get("MA60"))
    support = _extract_first_number(price_position.get("support_level")) or _extract_first_number(technical_map.get("支撑位"))
    resistance = _extract_first_number(price_position.get("resistance_level")) or _extract_first_number(technical_map.get("压力位"))
    high_52w = _to_float(
        _pick_first_from_sources(
            (fundamentals_normalized, result.market_snapshot if isinstance(result.market_snapshot, dict) else {}),
            ("fiftyTwoWeekHigh", "high_52w", "52week_high"),
            zero_is_missing=True,
        )
    )
    low_52w = _to_float(
        _pick_first_from_sources(
            (fundamentals_normalized, result.market_snapshot if isinstance(result.market_snapshot, dict) else {}),
            ("fiftyTwoWeekLow", "low_52w", "52week_low"),
            zero_is_missing=True,
        )
    )
    trailing_pe = _to_float(fundamentals_normalized.get("trailingPE"))
    forward_pe = _to_float(fundamentals_normalized.get("forwardPE"))
    volume_ratio = _to_float(volume_analysis.get("volume_ratio"))
    volume_judgment = _normalize_inline_text(technical_map.get(get_standard_report_field_label("volume_judgment", "zh"))).lower()
    trend_strength = _to_float(trend_status.get("trend_score"))
    trend_prediction = _normalize_inline_text(result.trend_prediction).lower()
    ma_alignment = _normalize_inline_text(technical_map.get(get_standard_report_field_label("ma_alignment", "zh"))).lower()
    bias_ma5 = _to_float(price_position.get("bias_ma5")) or _extract_first_number(technical_map.get(get_standard_report_field_label("bias_ma5", "zh")))

    support_levels = sorted(
        [
            level for level in _dedupe_numeric_levels(
                [
                    sniper.get("ideal_buy"),
                    sniper.get("secondary_buy"),
                    support,
                    ma5,
                    ma10,
                    ma20,
                    ma60,
                    day_low,
                    low_52w if current_price is not None and low_52w is not None and low_52w >= current_price * 0.78 else None,
                ],
                tolerance=(current_price or 0) * 0.003 if current_price else None,
            )
            if current_price is None or level <= current_price * 1.02
        ],
        reverse=True,
    )
    resistance_levels = sorted(
        [
            level for level in _dedupe_numeric_levels(
                [
                    sniper.get("take_profit"),
                    resistance,
                    day_high,
                    high_52w,
                ],
                tolerance=(current_price or 0) * 0.003 if current_price else None,
            )
            if current_price is None or level >= current_price * 0.985
        ]
    )

    nearest_support = support_levels[0] if support_levels else None
    secondary_support = support_levels[1] if len(support_levels) > 1 else None
    nearest_resistance = next((level for level in resistance_levels if current_price is None or level > current_price * 1.003), resistance_levels[0] if resistance_levels else None)
    second_resistance = next((level for level in resistance_levels if nearest_resistance is not None and level > nearest_resistance + max((current_price or nearest_resistance) * 0.004, 0.2)), None)

    volatility_inputs = [
        abs(day_high - day_low) if day_high is not None and day_low is not None else None,
        abs(current_price - prev_close) * 1.1 if current_price is not None and prev_close is not None else None,
        abs(current_price) * abs(_to_float(market_metrics.get("amplitude")) or 0) / 100 * 0.55 if current_price is not None else None,
        abs(current_price) * 0.012 if current_price is not None else None,
    ]
    atr_proxy = max([value for value in volatility_inputs if value is not None] or [1.0])
    if current_price is not None:
        atr_proxy = min(max(atr_proxy, current_price * 0.006), current_price * 0.08)

    bullish_structure = bool(
        (trend_status.get("is_bullish") is True)
        or ("多头" in ma_alignment)
        or ("bull" in trend_prediction)
        or ("看多" in trend_prediction)
    )
    weak_structure = bool(
        (current_price is not None and ma20 is not None and current_price < ma20)
        or ("空头" in ma_alignment)
        or ("bear" in trend_prediction)
        or ("看空" in trend_prediction)
    )
    overextended = bool(bias_ma5 is not None and bias_ma5 >= 4.8)
    volume_confirm = bool(("放量" in volume_judgment) or (volume_ratio is not None and volume_ratio >= 1.05))
    near_resistance = bool(current_price is not None and nearest_resistance is not None and current_price >= nearest_resistance * 0.992)
    near_support = bool(current_price is not None and nearest_support is not None and current_price <= nearest_support * 1.02)

    scenario = "no_trade"
    scenario_label = "观望 / 等待确认"
    confidence_score = 42
    if current_price is None:
        scenario_label = "数据不足 / 暂不交易"
        confidence_score = 20
    elif weak_structure and not bullish_structure:
        scenario_label = "观望 / 趋势未确认"
        confidence_score = 30
    elif bullish_structure and near_resistance and volume_confirm and not overextended:
        scenario = "breakout"
        scenario_label = "突破跟随"
        confidence_score = 78 if (trend_strength or 0) >= 65 else 66
    elif bullish_structure and near_support:
        scenario = "pullback"
        scenario_label = "回踩买点"
        confidence_score = 74 if (trend_strength or 0) >= 60 else 62
    elif bullish_structure and not overextended:
        scenario = "continuation"
        scenario_label = "趋势延续 / 等回踩"
        confidence_score = 58 if (trend_strength or 0) >= 55 else 52
    elif overextended:
        scenario_label = "观望 / 不追高"
        confidence_score = 36

    if scenario == "breakout":
        ideal_center = (nearest_resistance or current_price) + max(atr_proxy * 0.18, (current_price or 0) * 0.003)
        backup_center = max(nearest_resistance or current_price, ma5 or current_price)
        invalidation_anchor = secondary_support or ma10 or ma20 or nearest_support or current_price
        stop_price = max(0.01, invalidation_anchor - max(atr_proxy * 0.45, invalidation_anchor * 0.004))
        target_one = second_resistance or high_52w or (ideal_center + max((ideal_center - stop_price) * 1.4, atr_proxy * 1.2))
        target_two = high_52w if high_52w and target_one and high_52w > target_one else (
            target_one + max((ideal_center - stop_price) * 1.0, atr_proxy * 1.3) if target_one is not None else None
        )
        key_action = f"只在放量站上 {nearest_resistance:.2f} 后跟进，不提前预判突破。"
        build_strategy = f"首笔等突破价上方确认，回踩 {backup_center:.2f} 不破时再考虑补第二笔。"
        risk_control = f"止损放在 {stop_price:.2f}，对应前高回踩失败 / MA10-MA20 防守失效。"
    elif scenario == "pullback":
        ideal_center = nearest_support or ma10 or ma20 or current_price
        backup_center = secondary_support or ma20 or (ideal_center - atr_proxy * 0.6 if ideal_center is not None else None)
        invalidation_anchor = secondary_support or ma20 or day_low or current_price
        stop_price = max(0.01, invalidation_anchor - max(atr_proxy * 0.38, invalidation_anchor * 0.004))
        target_one = nearest_resistance or day_high or (current_price + max((current_price - stop_price) * 1.3, atr_proxy * 1.1))
        target_two = second_resistance or high_52w or (target_one + max((current_price - stop_price) * 0.9, atr_proxy * 1.2) if target_one is not None else None)
        key_action = f"优先等回踩 {ideal_center:.2f} 一带出现承接后再试仓，避免离均线过远追价。"
        build_strategy = f"理想做法是回踩支撑簇小仓试错，若站回 MA5/MA10 再做第二笔。"
        risk_control = f"止损放在 {stop_price:.2f}，跌破近期支撑簇就视为回踩失败。"
    elif scenario == "continuation":
        ideal_center = ma5 or nearest_support or current_price
        backup_center = ma10 or ma20 or nearest_support
        invalidation_anchor = ma20 or secondary_support or nearest_support or current_price
        stop_price = max(0.01, invalidation_anchor - max(atr_proxy * 0.42, invalidation_anchor * 0.004))
        target_one = nearest_resistance or high_52w or (current_price + max((current_price - stop_price) * 1.2, atr_proxy))
        target_two = second_resistance or high_52w or (target_one + max((current_price - stop_price) * 0.8, atr_proxy * 1.1) if target_one is not None else None)
        key_action = "趋势未坏，但更适合等回踩均线再接，不建议在扩张段主动追高。"
        build_strategy = f"等靠近 {ideal_center:.2f} 的均线支撑后分批试仓，若继续偏离均线则只跟踪不追。"
        risk_control = f"若失守 {stop_price:.2f} 一带，说明趋势延续条件被破坏。"
    else:
        ideal_center = nearest_support or ma20
        backup_center = ma20 or secondary_support
        invalidation_anchor = backup_center or nearest_support or current_price
        stop_price = max(0.01, (invalidation_anchor or current_price or 1.0) - max(atr_proxy * 0.4, (current_price or invalidation_anchor or 1.0) * 0.004))
        target_one = nearest_resistance or high_52w
        target_two = second_resistance or high_52w
        wait_for = (
            f"放量站上 {nearest_resistance:.2f}" if nearest_resistance is not None
            else f"回踩 {nearest_support:.2f} 后企稳" if nearest_support is not None
            else "趋势重新确认"
        )
        key_action = f"当前暂无高确定性主动买点，先等待 {wait_for}。"
        build_strategy = "不在弱结构或高乖离区强行给出精确买点，优先等待更清晰的确认信号。"
        risk_control = f"已有仓位可把防守位先看在 {stop_price:.2f} 附近，失守则继续收缩风险。"

    target_one = target_one if target_one is None or current_price is None else min(target_one, current_price * 1.18 if high_52w is None else max(high_52w, current_price * 1.12))
    target_two = target_two if target_two is None or current_price is None else min(target_two, current_price * 1.22 if high_52w is None else max(high_52w, current_price * 1.18))

    stop_reason = (
        "跌破最近支撑 / MA 簇后，做多结构被技术性否定。"
        if scenario != "no_trade"
        else "仅供持仓者参考的防守位，不构成新的进场建议。"
    )
    target_reason = "目标优先锚定首个技术压力、前高或 52 周高点，避免脱离当前波动结构。"
    confidence_label = _trade_confidence_label(confidence_score)
    position_sizing = (
        "初始 25%-35%，确认后最多提高到 50%。"
        if scenario in {"breakout", "pullback"}
        else "初始 15%-25%，只在回踩确认后再考虑加仓。"
        if scenario == "continuation"
        else "暂无新开仓，已有仓位以控制回撤为主。"
    )

    support_text = _format_trade_level(nearest_support, reason="近期支撑 / MA 簇") if nearest_support is not None else _na("接口未返回")
    resistance_text = _format_trade_level(nearest_resistance, reason="前高 / 压力位") if nearest_resistance is not None else _na("接口未返回")
    ideal_entry_text = _format_trade_range(
        ideal_center,
        atr_proxy,
        reason="回踩支撑确认" if scenario != "breakout" else "突破确认带",
    )
    backup_entry_text = _format_trade_range(
        backup_center,
        atr_proxy,
        reason="更深一层支撑" if scenario != "breakout" else "突破后回踩不破",
    )
    stop_loss_text = _format_trade_level(stop_price, reason="技术失效位")
    target_one_text = _format_trade_level(target_one, reason="首个技术目标") if target_one is not None else _na("字段待接入")
    target_two_text = _format_trade_level(target_two, reason="更强压力 / 高位目标") if target_two is not None else _na("字段待接入")
    target_zone_text = (
        f"{_extract_first_number(target_one_text):.2f}-{_extract_first_number(target_two_text):.2f}（目标区间）"
        if target_one is not None and target_two is not None
        else target_one_text
    )

    raw_ideal_text = _normalize_inline_text(sniper.get("ideal_buy"))
    raw_backup_text = _normalize_inline_text(sniper.get("secondary_buy"))
    raw_stop_text = _normalize_inline_text(sniper.get("stop_loss"))
    raw_target_text = _normalize_inline_text(sniper.get("take_profit"))
    raw_position_text = _normalize_inline_text(position_strategy.get("suggested_position"))
    raw_build_text = _normalize_inline_text(position_strategy.get("entry_plan"))
    raw_risk_text = _normalize_inline_text(position_strategy.get("risk_control"))

    if _should_preserve_trade_text(raw_ideal_text):
        ideal_entry_text = _format_number_token_text(raw_ideal_text)
    if _should_preserve_trade_text(raw_backup_text):
        backup_entry_text = _format_number_token_text(raw_backup_text)
    if _should_preserve_trade_text(raw_stop_text):
        stop_loss_text = _format_number_token_text(raw_stop_text)
    if _should_preserve_trade_text(raw_target_text):
        target_one_text = _format_number_token_text(raw_target_text)
        target_zone_text = target_one_text
    if _should_preserve_trade_text(raw_position_text):
        position_sizing = _format_number_token_text(raw_position_text)
    if _should_preserve_trade_text(raw_build_text):
        build_strategy = _format_number_token_text(raw_build_text)
    if _should_preserve_trade_text(raw_risk_text):
        risk_control = _format_number_token_text(raw_risk_text)

    no_position_advice = (
        f"{key_action} 只有在结构确认后才值得开第一笔仓位。"
        if scenario != "no_trade"
        else key_action
    )
    holder_advice = (
        f"已有仓位就沿着 {stop_price:.2f} 做风控，目标先看 {target_one:.2f}" if target_one is not None
        else f"已有仓位先围绕 {stop_price:.2f} 收紧风控。"
    )
    execution_reminders = unique_meaningful_items(
        [
            key_action,
            build_strategy,
            risk_control,
            "若价格偏离 MA5 过大或未放量确认，不要为了给出动作而强行交易。",
        ],
        4,
    )
    checklist = unique_meaningful_items(
        [
            f"{'✅' if scenario != 'no_trade' else '⚠️'} 交易场景：{scenario_label}",
            f"{'✅' if bullish_structure and current_price is not None and (ma20 is None or current_price >= ma20) else '⚠️'} 趋势位置：{_format_text('价格位于 MA20 上方' if current_price is not None and ma20 is not None and current_price >= ma20 else '仍需等待趋势重新确认', reason='字段待接入')}",
            f"{'✅' if volume_confirm else '⚠️'} 量能确认：{_format_text('放量/量比支持' if volume_confirm else '量能仍需确认', reason='字段待接入')}",
            f"{'❌' if overextended else '✅'} 追价控制：{_format_text('当前乖离偏大，不宜追高' if overextended else '距离均线未明显失真', reason='字段待接入')}",
        ],
        4,
    )
    market_structure = "MA5/10/20/60 = "
    market_structure += f"{ma5:.2f}" if ma5 is not None else "NA"
    market_structure += " / "
    market_structure += f"{ma10:.2f}" if ma10 is not None else "NA"
    market_structure += " / "
    market_structure += f"{ma20:.2f}" if ma20 is not None else "NA"
    market_structure += " / "
    market_structure += f"{ma60:.2f}" if ma60 is not None else "NA"

    return {
        "scenario": scenario,
        "scenario_label": scenario_label,
        "confidence_label": confidence_label,
        "confidence_score": confidence_score,
        "analysis_price": current_price,
        "key_action": key_action,
        "support_text": support_text,
        "support_level": nearest_support,
        "resistance_text": resistance_text,
        "resistance_level": nearest_resistance,
        "ideal_entry": ideal_entry_text,
        "ideal_entry_center": ideal_center,
        "backup_entry": backup_entry_text,
        "backup_entry_center": backup_center,
        "stop_loss": stop_loss_text,
        "stop_loss_level": stop_price,
        "stop_reason": stop_reason,
        "target_one": target_one_text,
        "target_one_level": target_one,
        "target_two": target_two_text,
        "target_two_level": target_two,
        "target_zone": target_zone_text,
        "target_reason": target_reason,
        "position_sizing": position_sizing,
        "build_strategy": build_strategy,
        "risk_control": risk_control,
        "no_position_advice": no_position_advice,
        "holder_advice": holder_advice,
        "execution_reminders": execution_reminders,
        "checklist": checklist,
        "market_structure": market_structure,
        "atr_proxy": atr_proxy,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "overextended": overextended,
    }


def _build_battle_fields(
    *,
    result: AnalysisResult,
    dashboard: Dict[str, Any],
    market_block: Dict[str, Any],
    technical_fields: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[str], List[str], Dict[str, Any]]:
    battle = dashboard.get("battle_plan") if isinstance(dashboard.get("battle_plan"), dict) else {}
    trade_setup = _build_trade_setup(
        result=result,
        dashboard=dashboard,
        market_block=market_block,
        technical_fields=technical_fields,
    )

    battle_fields = [
        {"label": "交易场景", "value": trade_setup["scenario_label"]},
        {"label": "关键动作", "value": trade_setup["key_action"]},
        {"label": "理想买入点", "value": trade_setup["ideal_entry"]},
        {"label": "次优买入点", "value": trade_setup["backup_entry"]},
        {"label": "止损位", "value": trade_setup["stop_loss"]},
        {"label": "目标一区", "value": trade_setup["target_one"]},
        {"label": "目标二区", "value": trade_setup["target_two"]},
        {"label": "目标位", "value": trade_setup["target_zone"]},
        {"label": "关键支撑", "value": trade_setup["support_text"]},
        {"label": "关键压力", "value": trade_setup["resistance_text"]},
        {"label": "仓位建议", "value": trade_setup["position_sizing"]},
        {"label": "建仓策略", "value": trade_setup["build_strategy"]},
        {"label": "风控策略", "value": trade_setup["risk_control"]},
    ]

    checklist = [str(item).strip() for item in (battle.get("action_checklist") or []) if str(item).strip()]
    if not checklist:
        checklist = trade_setup["checklist"] or [_na("字段待接入")]

    return battle_fields, checklist, trade_setup["execution_reminders"] or [], trade_setup


def build_standard_report_payload(result: AnalysisResult, report_language: str = "zh") -> Dict[str, Any]:
    """Public helper: build the single standard report payload for all channels."""
    language = normalize_report_language(report_language or getattr(result, "report_language", "zh"))
    labels = get_report_labels(language)
    field_labels = get_report_labels("zh")

    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
    core = dashboard.get("core_conclusion") if isinstance(dashboard.get("core_conclusion"), dict) else {}
    position_advice = core.get("position_advice") if isinstance(core.get("position_advice"), dict) else {}

    stock_name = get_localized_stock_name(result.name, result.code, language)
    signal_text, signal_emoji, _ = get_signal_level(result.operation_advice, result.sentiment_score, language)

    market_block = _build_market_block(result, language="zh", dashboard=dashboard, labels=field_labels)
    technical_fields = _build_technical_fields(
        language=language,
        dashboard=dashboard,
        market_regular_price=market_block.get("regular_price_numeric"),
    )
    fundamental_fields = _build_fundamental_fields(
        language=language,
        dashboard=dashboard,
        market_snapshot=result.market_snapshot if isinstance(result.market_snapshot, dict) else {},
    )
    earnings_fields, sentiment_fields = _build_earnings_sentiment_fields(language=language, dashboard=dashboard)
    battle_fields, checklist, risk_warnings, trade_setup = _build_battle_fields(
        result=result,
        dashboard=dashboard,
        market_block=market_block,
        technical_fields=technical_fields,
    )
    title_block = {
        "stock": f"{stock_name} ({result.code})",
        "score": result.sentiment_score,
        "signal_emoji": signal_emoji,
        "signal_text": signal_text,
        "operation_advice": localize_operation_advice(result.operation_advice, language),
        "trend_prediction": localize_trend_prediction(result.trend_prediction, language),
        "one_sentence": _format_text(core.get("one_sentence") or result.analysis_summary, reason="接口未返回"),
        "time_sensitivity": _format_text(core.get("time_sensitivity"), reason="接口未返回"),
    }
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    highlights = _build_highlights(
        dashboard,
        fundamentals=structured.get("fundamentals") if isinstance(structured.get("fundamentals"), dict) else {},
        earnings=structured.get("earnings_analysis") if isinstance(structured.get("earnings_analysis"), dict) else {},
        market_block=market_block,
        technical_fields=technical_fields,
        trade_setup=trade_setup,
    )
    info_fields = _build_info_fields(dashboard=dashboard, highlights=highlights)
    checklist_items = _build_checklist_items(checklist)
    table_sections = {
        "market": {
            "title": "行情表",
            "fields": market_block.get("display_fields") or market_block.get("regular_fields") or [],
            "note": "主表以 Analysis Price 为中心展示同一会话的价格、涨跌与成交字段；若 Close 与 Analysis Price 等价则不重复展示。",
        },
        "technical": {
            "title": "技术面表",
            "fields": technical_fields,
            "note": "MA / RSI / VWAP 优先使用 FMP / Alpha API；API 缺失时再回退本地历史计算，策略型字段继续本地派生。",
        },
        "fundamental": {
            "title": "基本面表",
            "fields": fundamental_fields,
            "note": "估值与质量指标按 TTM / 最新值 / 一致预期分开展示，字段标签已注明口径。",
        },
        "earnings": {
            "title": "财报表",
            "fields": earnings_fields,
            "note": "财报表统一按最新季度 QoQ / YoY 口径展示，避免与基本面 TTM 混读。",
        },
    }
    decision_context = _build_decision_context(dashboard=dashboard)
    summary_panel = _build_summary_panel(
        result=result,
        title=title_block,
        market_block=market_block,
    )
    visual_blocks = _build_visual_blocks(
        result=result,
        market_block=market_block,
        technical_fields=technical_fields,
        highlights=highlights,
    )
    battle_plan_compact = _build_battle_plan_compact(battle_fields, risk_warnings)
    decision_panel = _build_decision_panel(
        battle_fields=battle_fields,
        position_advice=position_advice,
        risk_warnings=risk_warnings,
        decision_context=decision_context,
        trade_setup=trade_setup,
    )
    reason_layer = _build_reason_layer(
        highlights=highlights,
        checklist=checklist,
        decision_context=decision_context,
    )
    coverage_notes = _build_coverage_notes(
        market_block=market_block,
        technical_fields=technical_fields,
        fundamental_fields=fundamental_fields,
        earnings_fields=earnings_fields,
    )

    no_position = position_advice.get("no_position") or localize_operation_advice(result.operation_advice, language)
    has_position = position_advice.get("has_position") or labels["continue_holding"]

    return {
        "title": title_block,
        "summary_panel": summary_panel,
        "info_fields": info_fields,
        "position_advice": {
            "no_position": _format_text(no_position, reason="字段待接入"),
            "has_position": _format_text(has_position, reason="字段待接入"),
        },
        "market": market_block,
        "technical_fields": technical_fields,
        "fundamental_fields": fundamental_fields,
        "earnings_fields": earnings_fields,
        "sentiment_fields": sentiment_fields,
        "table_sections": table_sections,
        "visual_blocks": visual_blocks,
        "decision_context": decision_context,
        "decision_panel": decision_panel,
        "reason_layer": reason_layer,
        "highlights": highlights,
        "battle_fields": battle_fields,
        "battle_plan_compact": battle_plan_compact,
        "battle_warnings": risk_warnings,
        "coverage_notes": coverage_notes,
        "checklist": checklist,
        "checklist_items": checklist_items,
    }


def _summarize_checklist(checklist: List[str]) -> str:
    items = [str(item).strip() for item in (checklist or []) if str(item).strip()]
    if not items:
        return _na("字段待接入")
    failed = sum(1 for item in items if item.startswith("❌"))
    warned = sum(1 for item in items if item.startswith("⚠️"))
    if failed:
        return f"仍有{failed}项关键条件未满足，优先补齐买点确认与风控纪律。"
    if warned:
        return f"仍有{warned}项执行条件待确认，建议继续观察量价配合。"
    return "检查项基本通过。"


def _build_market_brief(result: AnalysisResult, data_perspective: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
    labels = get_report_labels("zh")
    market = _build_market_block(
        result,
        language="zh",
        dashboard=dashboard,
        labels=labels,
    )
    regular = {item["label"]: item["value"] for item in market["regular_fields"]}
    return {
        "current_price": regular.get(labels["current_price_label"], _na("接口未返回")),
        "change_pct": regular.get(labels["change_pct_label"], _na("接口未返回")),
        "high": regular.get(labels["high_label"], _na("接口未返回")),
        "low": regular.get(labels["low_label"], _na("接口未返回")),
        "volume": regular.get(labels["volume_label"], _na("接口未返回")),
        "volume_judgment": _summarize_volume_judgment(
            (data_perspective or {}).get("volume_analysis") if isinstance(data_perspective, dict) else {}
        ),
    }


def _build_technical_brief(data_perspective: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    payload = data_perspective if isinstance(data_perspective, dict) else {}
    price_data = payload.get("price_position") if isinstance(payload.get("price_position"), dict) else {}
    alpha_data = payload.get("alpha_vantage") if isinstance(payload.get("alpha_vantage"), dict) else {}

    ma20 = _pick_first(price_data, ("ma20",))
    if _is_missing_value(ma20):
        ma20 = _pick_first(alpha_data, ("sma20",))

    return {
        "ma5": _format_price(_pick_first(price_data, ("ma5",)), reason="字段待接入"),
        "ma10": _format_price(_pick_first(price_data, ("ma10",)), reason="字段待接入"),
        "ma20": _format_price(ma20, reason="字段待接入"),
        "support": _format_price(_pick_first(price_data, ("support_level",)), reason="字段待接入"),
        "resistance": _format_price(_pick_first(price_data, ("resistance_level",)), reason="字段待接入"),
        "ma20_position": _na("接口未返回"),
    }


def _normalize_market_snapshot(snapshot: Any) -> Dict[str, Any]:
    data = snapshot if isinstance(snapshot, dict) else {}
    pseudo_result = AnalysisResult(
        code=str(data.get("code") or "UNKNOWN"),
        name=str(data.get("name") or ""),
        sentiment_score=50,
        trend_prediction="",
        operation_advice="",
        analysis_summary="",
        dashboard={},
        market_snapshot=data,
    )
    labels = get_report_labels("zh")
    normalized = _build_market_block(pseudo_result, language="zh", dashboard={}, labels=labels)

    # Keep backward-compatible keys for template consumers.
    regular = {item["label"]: item["value"] for item in normalized["regular_fields"]}
    return {
        "close": regular.get(labels["close_label"]),
        "prev_close": regular.get(labels["prev_close_label"]),
        "open": regular.get(labels["open_label"]),
        "high": regular.get(labels["high_label"]),
        "low": regular.get(labels["low_label"]),
        "pct_chg": regular.get(labels["change_pct_label"]),
        "change_amount": regular.get(labels["change_amount_label"]),
        "amplitude": regular.get(labels["amplitude_label"]),
        "volume": regular.get(labels["volume_label"]),
        "amount": regular.get(labels["amount_label"]),
        "price": regular.get(labels["current_price_label"]),
        "volume_ratio": regular.get(labels["volume_ratio_label"]),
        "turnover_rate": regular.get(labels["turnover_rate_label"]),
        "source": regular.get(labels["source_label"]),
        "session_type": regular.get(get_standard_report_field_label("session_type", "zh")),
        "consistency_warnings": normalized.get("consistency_warnings") or [],
    }


def _resolve_templates_dir() -> Path:
    config = get_config()
    base_dir = Path(__file__).resolve().parent.parent.parent
    templates_dir = Path(config.report_templates_dir)
    if templates_dir.is_absolute():
        return templates_dir
    return base_dir / templates_dir


def render(
    platform: str,
    results: List[AnalysisResult],
    report_date: Optional[str] = None,
    summary_only: bool = False,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Render a report template with a single standard payload across channels."""
    try:
        from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
    except ImportError:
        logger.warning("jinja2 not installed, report renderer disabled")
        return None

    if report_date is None:
        report_date = _now_shanghai().strftime("%Y-%m-%d")

    templates_dir = _resolve_templates_dir()
    template_name = f"report_{platform}.j2"
    template_path = templates_dir / template_name
    if not template_path.exists():
        logger.debug("Report template not found: %s", template_path)
        return None

    report_language = normalize_report_language(
        (extra_context or {}).get("report_language")
        or next(
            (
                getattr(result, "report_language", None)
                for result in results
                if getattr(result, "report_language", None)
            ),
            None,
        )
        or getattr(get_config(), "report_language", "zh")
    )
    labels = get_report_labels(report_language)

    sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)
    enriched: List[Dict[str, Any]] = []
    for result in sorted_results:
        signal_text, signal_emoji, _ = get_signal_level(
            result.operation_advice,
            result.sentiment_score,
            report_language,
        )
        stock_name = get_localized_stock_name(result.name, result.code, report_language)
        enriched.append(
            {
                "result": result,
                "signal_text": signal_text,
                "signal_emoji": signal_emoji,
                "stock_name": stock_name,
                "localized_operation_advice": localize_operation_advice(
                    result.operation_advice,
                    report_language,
                ),
                "localized_trend_prediction": localize_trend_prediction(
                    result.trend_prediction,
                    report_language,
                ),
                "standard_report": build_standard_report_payload(result, report_language),
            }
        )

    buy_count = sum(1 for r in results if getattr(r, "decision_type", "") == "buy")
    sell_count = sum(1 for r in results if getattr(r, "decision_type", "") == "sell")
    hold_count = sum(1 for r in results if getattr(r, "decision_type", "") in ("hold", ""))

    now_sh = _now_shanghai()

    first_time_ctx: Dict[str, Any] = {}
    if results:
        dashboard = getattr(results[0], "dashboard", {}) or {}
        structured = dashboard.get("structured_analysis") if isinstance(dashboard, dict) else {}
        if isinstance(structured, dict):
            time_ctx = structured.get("time_context")
            if isinstance(time_ctx, dict):
                first_time_ctx = time_ctx

    report_generated_at = _iso_or_none((extra_context or {}).get("report_generated_at")) or _iso_or_none(
        first_time_ctx.get("report_generated_at")
    )
    if not report_generated_at:
        report_generated_at = now_sh.isoformat()

    market_timestamp = (extra_context or {}).get("market_timestamp") or first_time_ctx.get("market_timestamp")
    news_published_at = (extra_context or {}).get("news_published_at") or first_time_ctx.get("news_published_at")

    def failed_checks(checklist: List[str]) -> List[str]:
        return [c for c in (checklist or []) if str(c).startswith("❌") or str(c).startswith("⚠️")]

    context: Dict[str, Any] = {
        "report_date": report_date,
        "report_timestamp": now_sh.strftime("%Y-%m-%d %H:%M:%S"),
        "report_generated_at": report_generated_at,
        "report_generated_at_bjt": _format_bjt_datetime(report_generated_at),
        "market_timestamp": market_timestamp,
        "market_timestamp_bjt": _format_bjt_datetime(market_timestamp),
        "market_session_date": (extra_context or {}).get("market_session_date") or first_time_ctx.get("market_session_date"),
        "session_type": (extra_context or {}).get("session_type") or first_time_ctx.get("session_type"),
        "price_basis": (extra_context or {}).get("price_basis") or first_time_ctx.get("price_basis"),
        "news_published_at": news_published_at,
        "news_published_at_bjt": _format_bjt_datetime(news_published_at),
        "to_shanghai_iso": _to_shanghai_iso,
        "results": sorted_results,
        "enriched": enriched,
        "summary_only": summary_only,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "hold_count": hold_count,
        "labels": labels,
        "report_language": report_language,
        "display_value": _format_text,
        "display_percent": _format_percent,
        "na": _na,
        "normalize_market_snapshot": _normalize_market_snapshot,
        "annotate_trade_levels": _annotate_trade_levels,
        "grade_intel_block": _grade_intel_block,
        "is_missing_value": _is_missing_value,
        "failed_checks": failed_checks,
        "summarize_earnings": _summarize_earnings,
        "summarize_sentiment": _summarize_sentiment,
        "summarize_volume_judgment": _summarize_volume_judgment,
        "summarize_checklist": _summarize_checklist,
        "build_market_brief": _build_market_brief,
        "build_technical_brief": _build_technical_brief,
        "localize_operation_advice": localize_operation_advice,
        "localize_trend_prediction": localize_trend_prediction,
        "localize_chip_health": localize_chip_health,
        "is_us_stock_code": is_us_stock_code,
        "history_by_code": {},
    }

    if extra_context:
        safe_extra_context = dict(extra_context)
        safe_extra_context.pop("labels", None)
        safe_extra_context.pop("report_language", None)
        context.update(safe_extra_context)

    try:
        env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(default=False),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        template = env.get_template(template_name)
        return template.render(**context)
    except Exception as exc:
        logger.warning("Report render failed for %s: %s", template_name, exc)
        return None
