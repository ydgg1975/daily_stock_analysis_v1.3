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


def _pick_first(payload: Dict[str, Any], candidates: Iterable[str]) -> Any:
    for key in candidates:
        if key in payload and not _is_missing_value(payload.get(key)):
            return payload.get(key)
    return None


def _pick_first_from_sources(sources: Iterable[Any], candidates: Iterable[str]) -> Any:
    for payload in sources:
        if not isinstance(payload, dict):
            continue
        value = _pick_first(payload, candidates)
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
    regular_fields = market_block.get("regular_fields") if isinstance(market_block.get("regular_fields"), list) else []
    regular_map = _build_field_map(regular_fields)
    session_value = time_ctx.get("session_label") or time_ctx.get("session_type")
    current_price = regular_map.get("当前价", _na("接口未返回"))
    change_amount = regular_map.get("涨跌额", _na("接口未返回"))
    change_pct = regular_map.get("涨跌幅", _na("接口未返回"))
    market_time = _format_text(
        time_ctx.get("market_timestamp_local") or time_ctx.get("market_timestamp_bjt") or time_ctx.get("market_timestamp"),
        reason="接口未返回",
    )
    tags = [
        {"label": "交易日", "value": _format_text(time_ctx.get("market_session_date"), reason="接口未返回")},
        {"label": "市场时间", "value": market_time},
        {"label": "会话类型", "value": _format_text(session_value, reason="接口未返回")},
        {"label": "新闻发布时间", "value": _format_text(time_ctx.get("news_published_at_bjt") or time_ctx.get("news_published_at"), reason="接口未返回")},
    ]
    return {
        "stock": title.get("stock"),
        "ticker": result.code,
        "score": result.sentiment_score,
        "current_price": current_price,
        "change_amount": change_amount,
        "change_pct": change_pct,
        "market_time": market_time,
        "market_session_date": _format_text(time_ctx.get("market_session_date"), reason="接口未返回"),
        "session_label": _format_text(session_value, reason="接口未返回"),
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

    latest_news = _normalize_inline_text(intel.get("latest_news") or intel.get("latest_news_notice"))
    return {
        "positive_catalysts": intel.get("positive_catalysts") or [],
        "risk_alerts": intel.get("risk_alerts") or [],
        "latest_news": [latest_news] if latest_news else [],
        "news_value_grade": _format_text(intel.get("news_value_grade"), reason="接口未返回"),
        "sentiment_summary": _format_text(intel.get("sentiment_summary"), reason="接口未返回"),
        "earnings_outlook": _derive_earnings_outlook(fundamentals, earnings),
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
        "理想买入点": "buy",
        "次优买入点": "secondary",
        "止损位": "risk",
        "目标位": "target",
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
            for item in (close_value, prev_close_value, open_value, high_value, low_value, volume_value)
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
    if session_kind == "completed":
        candidate_bundles = [
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
        ]
        candidate_bundles.sort(
            key=lambda item: (
                item.get("completeness", 0),
                3 if item.get("name") == "session_eod_context" else 2 if item.get("name") == "market_snapshot" else 1,
            ),
            reverse=True,
        )
        selected_bundle = next(
            (
                item
                for item in candidate_bundles
                if item.get("name") == "session_eod_context"
                and item.get("close") is not None
                and item.get("prev_close") is not None
            ),
            None,
        )
        if selected_bundle is None:
            selected_bundle = next(
                (item for item in candidate_bundles if item.get("close") is not None and item.get("prev_close") is not None),
                candidate_bundles[0],
            )
        close = selected_bundle.get("close")
        prev_close = selected_bundle.get("prev_close")
        regular_price = selected_bundle.get("close") if selected_bundle.get("close") is not None else selected_bundle.get("price")
        source_candidate = selected_bundle.get("source") or source_candidate
        provided_regular_change = selected_bundle.get("change_amount")
        provided_regular_pct = selected_bundle.get("change_pct")
        open_value = selected_bundle.get("open")
        high_value = selected_bundle.get("high")
        low_value = selected_bundle.get("low")
        volume = selected_bundle.get("volume")
        amount = selected_bundle.get("amount")
        amplitude_value = selected_bundle.get("amplitude")
        selected_bundle_name = str(selected_bundle.get("name") or "")
    elif session_kind == "extended":
        regular_price = close
        selected_bundle_name = "extended_regular_close"
    else:
        regular_price = live_price if live_price is not None else close
        selected_bundle_name = "intraday_snapshot"

    recovered_prev_close = _derive_prev_close_from_change(
        close if close is not None else regular_price,
        change_amount=provided_regular_change,
        change_pct=provided_regular_pct,
    )
    prev_close_recovered = False
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
        if prev_close is None or flat_placeholder or (session_kind == "completed" and hinted_conflict):
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
            "value": _join_list(intel.get("risk_alerts") or [], empty_reason="接口未返回"),
        },
        {
            "label": "利好催化",
            "value": _join_list(
                intel.get("positive_catalysts") or [intel.get("positive_catalysts_notice")],
                empty_reason="接口未返回",
            ),
        },
        {
            "label": "最新动态 / 重要公告",
            "value": _format_text(
                intel.get("latest_news") or intel.get("latest_news_notice"),
                reason="接口未返回",
            ),
        },
        {
            "label": "新闻价值分级",
            "value": _format_text(intel.get("news_value_grade"), reason="接口未返回"),
        },
    ]


def _build_battle_fields(
    *,
    result: AnalysisResult,
    dashboard: Dict[str, Any],
    market_regular_price: Optional[float],
) -> Tuple[List[Dict[str, str]], List[str], List[str]]:
    battle = dashboard.get("battle_plan") if isinstance(dashboard.get("battle_plan"), dict) else {}
    sniper = battle.get("sniper_points") if isinstance(battle.get("sniper_points"), dict) else {}
    position = battle.get("position_strategy") if isinstance(battle.get("position_strategy"), dict) else {}

    levels = _annotate_trade_levels(
        market_regular_price,
        sniper.get("ideal_buy"),
        sniper.get("secondary_buy"),
        sniper.get("stop_loss"),
        result.trend_prediction,
    )

    ideal = _clean_sniper_value(sniper.get("ideal_buy"))
    if levels.get("ideal_buy_tag") and not ideal.startswith("NA（"):
        ideal = f"{ideal}（{levels['ideal_buy_tag']}）"

    secondary = _clean_sniper_value(sniper.get("secondary_buy"))
    if levels.get("secondary_buy_tag") and not secondary.startswith("NA（"):
        secondary = f"{secondary}（{levels['secondary_buy_tag']}）"

    battle_fields = [
        {"label": "理想买入点", "value": ideal},
        {"label": "次优买入点", "value": secondary},
        {"label": "止损位", "value": _clean_sniper_value(sniper.get("stop_loss"))},
        {"label": "目标位", "value": _clean_sniper_value(sniper.get("take_profit"))},
        {"label": "仓位建议", "value": _format_number_token_text(position.get("suggested_position"), reason="字段待接入")},
        {"label": "建仓策略", "value": _format_text(position.get("entry_plan"), reason="字段待接入")},
        {"label": "风控策略", "value": _format_text(position.get("risk_control"), reason="字段待接入")},
    ]

    checklist = [str(item).strip() for item in (battle.get("action_checklist") or []) if str(item).strip()]
    if not checklist:
        checklist = [_na("字段待接入")]

    return battle_fields, checklist, levels.get("risk_warnings") or []


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
    battle_fields, checklist, risk_warnings = _build_battle_fields(
        result=result,
        dashboard=dashboard,
        market_regular_price=market_block.get("regular_price_numeric"),
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
    )
    info_fields = _build_info_fields(dashboard=dashboard, highlights=highlights)
    checklist_items = _build_checklist_items(checklist)
    table_sections = {
        "market": {
            "title": "行情表",
            "fields": market_block.get("regular_fields") or [],
            "note": "常规交易时段与扩展时段分开展示；涨跌额与涨跌幅优先按当前价和昨收重算。",
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
    summary_panel = _build_summary_panel(
        result=result,
        title=title_block,
        market_block=market_block,
    )
    decision_context = _build_decision_context(dashboard=dashboard)
    visual_blocks = _build_visual_blocks(
        result=result,
        market_block=market_block,
        technical_fields=technical_fields,
        highlights=highlights,
    )
    battle_plan_compact = _build_battle_plan_compact(battle_fields, risk_warnings)

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
        "highlights": highlights,
        "battle_fields": battle_fields,
        "battle_plan_compact": battle_plan_compact,
        "battle_warnings": risk_warnings,
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
