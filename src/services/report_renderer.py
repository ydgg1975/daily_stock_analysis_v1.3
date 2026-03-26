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
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

from data_provider.us_index_mapping import is_us_stock_code
from src.analyzer import AnalysisResult
from src.config import get_config
from src.report_language import (
    get_localized_stock_name,
    get_report_labels,
    get_signal_level,
    localize_chip_health,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)

logger = logging.getLogger(__name__)

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
_NUMERIC_TOKEN_RE = re.compile(r"-?\d+(?:\.\d+)?")

_ALLOWED_MISSING_REASONS = {
    "当前数据源未提供",
    "当前市场暂不支持",
    "接口未返回",
    "字段待接入",
    "上游映射缺失",
    "口径冲突，待校正",
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


def _format_price(value: Any, *, reason: str = "接口未返回") -> str:
    return _format_decimal(value, digits=2, reason=reason)


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

    if from_ratio and abs(number) <= 1:
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


def _normalize_session_type(session_type: Any) -> Tuple[str, str]:
    text = str(session_type or "").strip().lower().replace("-", "_")
    if "pre" in text:
        return "extended", "盘前"
    if "after" in text or "post" in text:
        return "extended", "盘后"
    return "regular", "常规交易时段"


def _compute_change(current: Optional[float], prev_close: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if current is None or prev_close in (None, 0):
        return None, None
    change = current - prev_close
    pct = (change / prev_close) * 100
    return change, pct


def _conflict(a: Optional[float], b: Optional[float], tolerance: float = 0.05) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) > tolerance


def _normalize_inline_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().strip("-")


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


def _summarize_earnings(earnings: Optional[Dict[str, Any]]) -> str:
    payload = earnings if isinstance(earnings, dict) else {}
    metrics = payload.get("derived_metrics") if isinstance(payload.get("derived_metrics"), dict) else {}

    yoy_rev = _to_float(metrics.get("yoy_revenue_growth"))
    yoy_net = _to_float(metrics.get("yoy_net_income_change"))
    qoq_rev = _to_float(metrics.get("qoq_revenue_growth"))
    qoq_net = _to_float(metrics.get("qoq_net_income_change"))

    if yoy_rev is not None and yoy_net is not None:
        if yoy_rev >= 0 and yoy_net >= 0:
            return "营收与利润同比同向改善。"
        if yoy_rev >= 0 and yoy_net < 0:
            return "营收同比增长，但利润端仍承压。"
        if yoy_rev < 0 and yoy_net < 0:
            return "营收与利润同比同步回落。"
    if qoq_rev is not None and qoq_net is not None:
        if qoq_rev >= 0 and qoq_net >= 0:
            return "季度环比数据边际改善。"
        if qoq_rev >= 0 and qoq_net < 0:
            return "季度营收环比回升，但利润改善不足。"

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

    if any(token in status for token in ("缺失", "missing", "unavailable")):
        return _na("接口未返回")
    if "放量" in status or (ratio is not None and ratio >= 1.2):
        return "放量，短线资金参与度提升。"
    if "缩量" in status or (ratio is not None and ratio < 0.8):
        return "缩量，追价意愿偏弱。"
    if "正常" in status or "平量" in status or ratio is not None:
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
    dashboard: Dict[str, Any],
    labels: Dict[str, str],
) -> Dict[str, Any]:
    snapshot = result.market_snapshot if isinstance(result.market_snapshot, dict) else {}
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    time_context = structured.get("time_context") if isinstance(structured.get("time_context"), dict) else {}
    data_persp = dashboard.get("data_perspective") if isinstance(dashboard.get("data_perspective"), dict) else {}
    volume_analysis = data_persp.get("volume_analysis") if isinstance(data_persp.get("volume_analysis"), dict) else {}

    session_type = _pick_first(snapshot, ("session_type", "session")) or time_context.get("session_type")
    session_kind, session_label = _normalize_session_type(session_type)

    prev_close = _to_float(_pick_first(snapshot, ("prev_close", "pre_close", "yesterday_close")))
    close = _to_float(_pick_first(snapshot, ("close", "regular_close", "regular_close_price")))
    live_price = _to_float(_pick_first(snapshot, ("price", "current_price", "last_price")))

    if session_kind == "extended":
        regular_price = close
    else:
        regular_price = live_price if live_price is not None else close

    regular_change, regular_change_pct = _compute_change(regular_price, prev_close)

    provided_regular_change = _to_float(_pick_first(snapshot, ("regular_change",)))
    provided_regular_pct = _to_float(_pick_first(snapshot, ("regular_change_pct",)))

    regular_conflict = _conflict(regular_change, provided_regular_change) or _conflict(
        regular_change_pct,
        provided_regular_pct,
    )

    extended_price_candidates = (
        "extended_price",
        "pre_market_price",
        "premarket_price",
        "after_hours_price",
        "post_market_price",
    )
    extended_price = _to_float(_pick_first(snapshot, extended_price_candidates))
    if extended_price is None and session_kind == "extended":
        extended_price = live_price

    extended_change, extended_change_pct = _compute_change(extended_price, prev_close)

    provided_extended_change = _to_float(
        _pick_first(snapshot, ("extended_change", "pre_market_change", "after_hours_change"))
    )
    provided_extended_pct = _to_float(
        _pick_first(snapshot, ("extended_change_pct", "pre_market_change_pct", "after_hours_change_pct"))
    )

    if provided_extended_change is None and session_kind == "extended":
        provided_extended_change = _to_float(_pick_first(snapshot, ("change_amount",)))
    if provided_extended_pct is None and session_kind == "extended":
        provided_extended_pct = _to_float(_pick_first(snapshot, ("pct_chg", "change_pct")))

    extended_conflict = _conflict(extended_change, provided_extended_change) or _conflict(
        extended_change_pct,
        provided_extended_pct,
    )

    if regular_change is None:
        regular_change_text = _na("接口未返回")
        regular_change_pct_text = _na("接口未返回")
    elif regular_conflict:
        regular_change_text = _na("口径冲突，待校正")
        regular_change_pct_text = _na("口径冲突，待校正")
    else:
        regular_change_text = _format_price(regular_change)
        regular_change_pct_text = _format_percent(regular_change_pct)

    if extended_price is None:
        extended_price_text = _na("当前数据源未提供")
        extended_change_text = _na("当前数据源未提供")
        extended_change_pct_text = _na("当前数据源未提供")
    elif extended_conflict:
        extended_price_text = _format_price(extended_price)
        extended_change_text = _na("口径冲突，待校正")
        extended_change_pct_text = _na("口径冲突，待校正")
    else:
        extended_price_text = _format_price(extended_price)
        extended_change_text = _format_price(extended_change)
        extended_change_pct_text = _format_percent(extended_change_pct)

    extended_timestamp = _pick_first(
        snapshot,
        (
            "extended_timestamp",
            "pre_market_timestamp",
            "after_hours_timestamp",
            "timestamp",
            "quote_time",
        ),
    )
    extended_timestamp_text = _format_text(extended_timestamp, reason="当前数据源未提供")

    amount = _pick_first(snapshot, ("amount", "turnover", "turnover_amount"))
    volume = _pick_first(snapshot, ("volume", "turnover_volume"))

    volume_ratio = _pick_first(snapshot, ("volume_ratio",))
    if _is_missing_value(volume_ratio):
        volume_ratio = volume_analysis.get("volume_ratio")

    turnover_rate = _pick_first(snapshot, ("turnover_rate",))
    if _is_missing_value(turnover_rate):
        turnover_rate = volume_analysis.get("turnover_rate")

    avg_price = _pick_first(snapshot, ("avg_price", "average_price", "avgPrice"))
    vwap = _pick_first(snapshot, ("vwap", "VWAP"))

    consistency_warnings: List[str] = []
    if regular_conflict:
        consistency_warnings.append("常规时段涨跌额/涨跌幅口径冲突，已标记 NA（口径冲突，待校正）")
    if extended_conflict:
        consistency_warnings.append("扩展时段涨跌额/涨跌幅口径冲突，已标记 NA（口径冲突，待校正）")
    if session_kind == "extended" and close is None:
        consistency_warnings.append("当前处于扩展时段，但缺少 regular close，常规口径字段可能不完整")

    source = _pick_first(snapshot, ("source", "provider", "data_source"))

    regular_fields = [
        {"label": labels["current_price_label"], "value": _format_price(regular_price)},
        {"label": labels["prev_close_label"], "value": _format_price(prev_close)},
        {"label": labels["open_label"], "value": _format_price(_pick_first(snapshot, ("open", "open_price")))},
        {"label": labels["high_label"], "value": _format_price(_pick_first(snapshot, ("high",)))},
        {"label": labels["low_label"], "value": _format_price(_pick_first(snapshot, ("low",)))},
        {"label": labels["close_label"], "value": _format_price(close)},
        {"label": labels["change_amount_label"], "value": regular_change_text},
        {"label": labels["change_pct_label"], "value": regular_change_pct_text},
        {
            "label": labels["amplitude_label"],
            "value": _format_percent(_pick_first(snapshot, ("amplitude", "swing"))),
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
        {"label": "均价", "value": _format_price(avg_price, reason="字段待接入")},
        {"label": "VWAP", "value": _format_price(vwap, reason="字段待接入")},
        {"label": labels["source_label"], "value": _format_text(source, reason="上游映射缺失")},
        {"label": "session 类型", "value": _format_text(session_type, reason="接口未返回")},
    ]

    extended_fields = [
        {"label": "盘前价", "value": _format_price(_pick_first(snapshot, ("pre_market_price", "premarket_price")), reason="当前数据源未提供")},
        {"label": "盘后价", "value": _format_price(_pick_first(snapshot, ("after_hours_price", "post_market_price")), reason="当前数据源未提供")},
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
    }


def _build_technical_fields(
    *,
    dashboard: Dict[str, Any],
    market_regular_price: Optional[float],
) -> List[Dict[str, str]]:
    data_persp = dashboard.get("data_perspective") if isinstance(dashboard.get("data_perspective"), dict) else {}
    trend_data = data_persp.get("trend_status") if isinstance(data_persp.get("trend_status"), dict) else {}
    price_data = data_persp.get("price_position") if isinstance(data_persp.get("price_position"), dict) else {}
    volume_analysis = data_persp.get("volume_analysis") if isinstance(data_persp.get("volume_analysis"), dict) else {}
    alpha_data = data_persp.get("alpha_vantage") if isinstance(data_persp.get("alpha_vantage"), dict) else {}

    ma20_value = _pick_first(price_data, ("ma20",))
    if _is_missing_value(ma20_value):
        ma20_value = _pick_first(alpha_data, ("sma20",))

    ma60_value = _pick_first(price_data, ("ma60",))
    if _is_missing_value(ma60_value):
        ma60_value = _pick_first(alpha_data, ("sma60",))

    ma20_numeric = _to_float(ma20_value)

    ma20_position = _na("接口未返回")
    if market_regular_price is not None and ma20_numeric is not None:
        ma20_position = "当前位于 MA20 上方" if market_regular_price >= ma20_numeric else "当前位于 MA20 下方"

    bullish = trend_data.get("is_bullish")
    if bullish is True:
        alignment = "多头排列"
    elif bullish is False:
        alignment = "空头/震荡"
    else:
        alignment = _na("接口未返回")

    trend_strength = trend_data.get("trend_score")
    trend_strength_text = (
        f"{_format_decimal(trend_strength)}/100"
        if not _is_missing_value(trend_strength)
        else _na("接口未返回")
    )

    return [
        {"label": "MA5", "value": _format_price(_pick_first(price_data, ("ma5",)), reason="字段待接入")},
        {"label": "MA10", "value": _format_price(_pick_first(price_data, ("ma10",)), reason="字段待接入")},
        {"label": "MA20", "value": _format_price(ma20_value, reason="字段待接入")},
        {"label": "MA60", "value": _format_price(ma60_value, reason="字段待接入")},
        {"label": "SMA20", "value": _format_price(_pick_first(alpha_data, ("sma20",)), reason="字段待接入")},
        {"label": "SMA60", "value": _format_price(_pick_first(alpha_data, ("sma60",)), reason="字段待接入")},
        {"label": "RSI14", "value": _format_decimal(_pick_first(alpha_data, ("rsi14",)), reason="字段待接入")},
        {"label": "VWAP", "value": _format_price(_pick_first(price_data, ("vwap", "VWAP")), reason="字段待接入")},
        {
            "label": "支撑位",
            "value": _format_price(_pick_first(price_data, ("support_level", "support")), reason="字段待接入"),
        },
        {
            "label": "压力位",
            "value": _format_price(_pick_first(price_data, ("resistance_level", "resistance")), reason="字段待接入"),
        },
        {"label": "乖离率", "value": _format_percent(_pick_first(price_data, ("bias_ma5",)), reason="字段待接入")},
        {"label": "趋势强度", "value": trend_strength_text},
        {"label": "多头/空头排列", "value": alignment},
        {"label": "当前位于 MA20 上下方", "value": ma20_position},
        {"label": "量价判断", "value": _summarize_volume_judgment(volume_analysis)},
    ]


def _build_fundamental_fields(
    *,
    dashboard: Dict[str, Any],
    market_snapshot: Dict[str, Any],
) -> List[Dict[str, str]]:
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    fundamentals = structured.get("fundamentals") if isinstance(structured.get("fundamentals"), dict) else {}
    normalized = fundamentals.get("normalized") if isinstance(fundamentals.get("normalized"), dict) else {}

    def _n(*keys: str) -> Any:
        return _pick_first(normalized, keys)

    market_cap = _n("marketCap", "totalMarketCap", "total_mv") or _pick_first(market_snapshot, ("total_mv",))
    float_market_cap = _n("floatMarketCap", "circulatingMarketCap", "circ_mv") or _pick_first(
        market_snapshot,
        ("circ_mv",),
    )
    shares = _n("sharesOutstanding", "totalShares")
    float_shares = _n("floatShares")

    return [
        {"label": "marketCap", "value": _format_amount(market_cap, reason="接口未返回")},
        {"label": "floatMarketCap", "value": _format_amount(float_market_cap, reason="字段待接入")},
        {"label": "totalShares / sharesOutstanding", "value": _format_volume(shares, reason="字段待接入")},
        {"label": "floatShares", "value": _format_volume(float_shares, reason="字段待接入")},
        {"label": "trailingPE", "value": _format_decimal(_n("trailingPE"), reason="接口未返回")},
        {"label": "forwardPE", "value": _format_decimal(_n("forwardPE"), reason="接口未返回")},
        {"label": "PB / priceToBook", "value": _format_decimal(_n("priceToBook", "pb"), reason="字段待接入")},
        {"label": "Beta", "value": _format_decimal(_n("beta"), reason="字段待接入")},
        {"label": "52w high", "value": _format_price(_n("fiftyTwoWeekHigh", "high52w") or _pick_first(market_snapshot, ("high_52w",)), reason="字段待接入")},
        {"label": "52w low", "value": _format_price(_n("fiftyTwoWeekLow", "low52w") or _pick_first(market_snapshot, ("low_52w",)), reason="字段待接入")},
        {"label": "historical high", "value": _format_price(_n("historicalHigh", "allTimeHigh"), reason="当前数据源未提供")},
        {"label": "historical low", "value": _format_price(_n("historicalLow", "allTimeLow"), reason="当前数据源未提供")},
        {"label": "revenue", "value": _format_amount(_n("revenue", "totalRevenue"), reason="接口未返回")},
        {"label": "revenueGrowth", "value": _format_percent(_n("revenueGrowth"), from_ratio=True, reason="接口未返回")},
        {"label": "netIncome", "value": _format_amount(_n("netIncome"), reason="接口未返回")},
        {"label": "netIncomeGrowth", "value": _format_percent(_n("netIncomeGrowth"), from_ratio=True, reason="字段待接入")},
        {"label": "freeCashFlow", "value": _format_amount(_n("freeCashflow", "freeCashFlow"), reason="接口未返回")},
        {"label": "operatingCashFlow", "value": _format_amount(_n("operatingCashflow", "operatingCashFlow"), reason="接口未返回")},
        {"label": "ROE", "value": _format_percent(_n("returnOnEquity", "roe"), from_ratio=True, reason="接口未返回")},
        {"label": "ROA", "value": _format_percent(_n("returnOnAssets", "roa"), from_ratio=True, reason="接口未返回")},
        {"label": "grossMargins", "value": _format_percent(_n("grossMargins"), from_ratio=True, reason="接口未返回")},
        {"label": "operatingMargins", "value": _format_percent(_n("operatingMargins"), from_ratio=True, reason="接口未返回")},
        {"label": "debtToEquity", "value": _format_percent(_n("debtToEquity"), reason="接口未返回")},
        {"label": "currentRatio", "value": _format_decimal(_n("currentRatio"), reason="接口未返回")},
    ]


def _build_earnings_sentiment_fields(*, dashboard: Dict[str, Any]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
    earnings = structured.get("earnings_analysis") if isinstance(structured.get("earnings_analysis"), dict) else {}
    metrics = earnings.get("derived_metrics") if isinstance(earnings.get("derived_metrics"), dict) else {}

    sentiment = structured.get("sentiment_analysis") if isinstance(structured.get("sentiment_analysis"), dict) else {}

    earnings_fields = [
        {"label": "财报趋势摘要", "value": _summarize_earnings(earnings)},
        {"label": "QoQ revenue growth", "value": _format_percent(metrics.get("qoq_revenue_growth"), from_ratio=True, reason="接口未返回")},
        {"label": "YoY revenue growth", "value": _format_percent(metrics.get("yoy_revenue_growth"), from_ratio=True, reason="接口未返回")},
        {"label": "QoQ net income change", "value": _format_percent(metrics.get("qoq_net_income_change"), from_ratio=True, reason="接口未返回")},
        {"label": "YoY net income change", "value": _format_percent(metrics.get("yoy_net_income_change"), from_ratio=True, reason="接口未返回")},
    ]

    sentiment_fields = [
        {"label": "情绪摘要", "value": _summarize_sentiment(sentiment)},
        {"label": "公司情绪", "value": _format_text(sentiment.get("company_sentiment"), reason="接口未返回")},
        {"label": "行业情绪", "value": _format_text(sentiment.get("industry_sentiment"), reason="接口未返回")},
        {"label": "监管情绪", "value": _format_text(sentiment.get("regulatory_sentiment"), reason="接口未返回")},
        {
            "label": "置信度",
            "value": _format_text(
                sentiment.get("overall_confidence") or sentiment.get("confidence"),
                reason="接口未返回",
            ),
        },
    ]

    return earnings_fields, sentiment_fields


def _build_info_fields(*, dashboard: Dict[str, Any]) -> List[Dict[str, str]]:
    intel = _grade_intel_block(dashboard.get("intelligence") or {})
    return [
        {
            "label": "舆情情绪",
            "value": _format_text(
                intel.get("sentiment_summary"),
                reason="接口未返回",
            ),
        },
        {
            "label": "业绩预期",
            "value": _format_text(intel.get("earnings_outlook"), reason="接口未返回"),
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

    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}
    core = dashboard.get("core_conclusion") if isinstance(dashboard.get("core_conclusion"), dict) else {}
    position_advice = core.get("position_advice") if isinstance(core.get("position_advice"), dict) else {}

    stock_name = get_localized_stock_name(result.name, result.code, language)
    signal_text, signal_emoji, _ = get_signal_level(result.operation_advice, result.sentiment_score, language)

    market_block = _build_market_block(result, dashboard=dashboard, labels=labels)
    technical_fields = _build_technical_fields(
        dashboard=dashboard,
        market_regular_price=market_block.get("regular_price_numeric"),
    )
    fundamental_fields = _build_fundamental_fields(
        dashboard=dashboard,
        market_snapshot=result.market_snapshot if isinstance(result.market_snapshot, dict) else {},
    )
    earnings_fields, sentiment_fields = _build_earnings_sentiment_fields(dashboard=dashboard)
    info_fields = _build_info_fields(dashboard=dashboard)
    battle_fields, checklist, risk_warnings = _build_battle_fields(
        result=result,
        dashboard=dashboard,
        market_regular_price=market_block.get("regular_price_numeric"),
    )

    no_position = position_advice.get("no_position") or localize_operation_advice(result.operation_advice, language)
    has_position = position_advice.get("has_position") or labels["continue_holding"]

    return {
        "title": {
            "stock": f"{stock_name} ({result.code})",
            "score": result.sentiment_score,
            "signal_emoji": signal_emoji,
            "signal_text": signal_text,
            "operation_advice": localize_operation_advice(result.operation_advice, language),
            "trend_prediction": localize_trend_prediction(result.trend_prediction, language),
            "one_sentence": _format_text(core.get("one_sentence") or result.analysis_summary, reason="接口未返回"),
            "time_sensitivity": _format_text(core.get("time_sensitivity"), reason="接口未返回"),
        },
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
        "battle_fields": battle_fields,
        "battle_warnings": risk_warnings,
        "checklist": checklist,
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
    labels = get_report_labels(normalize_report_language(getattr(result, "report_language", "zh")))
    market = _build_market_block(result, dashboard=dashboard, labels=labels)
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
    normalized = _build_market_block(pseudo_result, dashboard={}, labels=labels)

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
        "session_type": regular.get("session 类型"),
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
