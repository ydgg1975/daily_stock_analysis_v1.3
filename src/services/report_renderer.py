# -*- coding: utf-8 -*-
"""
===================================
Report Engine - Jinja2 Report Renderer
===================================

Renders reports from Jinja2 templates. Falls back to caller's logic on template
missing or render error. Template path is relative to project root.
Any expensive data preparation should be injected by the caller via extra_context.
"""

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

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
from data_provider.us_index_mapping import is_us_stock_code

logger = logging.getLogger(__name__)
_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


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
    if not text:
        return None
    return text


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




def _na(reason: str = "接口未返回") -> str:
    reason_text = str(reason or "接口未返回").strip()
    return f"NA（{reason_text}）"


def _normalize_missing_text(missing_text: str) -> str:
    text = (missing_text or "").strip()
    if not text or text in {"N/A", "NA", "数据缺失"}:
        return _na("接口未返回")
    if text.startswith("NA（"):
        return text
    return _na(text)


def _format_number(val: Any, style: str = "auto") -> str:
    num = float(val)
    abs_num = abs(num)
    if style in {"amount", "volume"}:
        if abs_num >= 1e8:
            return f"{num / 1e8:.2f}亿"
        if abs_num >= 1e4:
            return f"{num / 1e4:.2f}万"
    if abs_num >= 1000 and style in {"amount", "auto"}:
        return f"{num:,.2f}"
    return f"{num:.2f}"


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

def _escape_md(text: str) -> str:
    """Escape markdown special chars (*ST etc)."""
    if not text:
        return ""
    return text.replace("*", "\\*").replace("_", "\\_")


def _clean_sniper_value(val: Any) -> str:
    """Format sniper point value for display (strip label prefixes)."""
    if val is None:
        return _na("字段待接入")
    if isinstance(val, (int, float)):
        return str(val)
    s = str(val).strip() if val else ""
    if not s or s in {"N/A", "NA"}:
        return _na("字段待接入")
    prefixes = [
        "理想买入点：", "次优买入点：", "止损位：", "目标位：",
        "理想买入点:", "次优买入点:", "止损位:", "目标位:",
        "Ideal Entry:", "Secondary Entry:", "Stop Loss:", "Target:",
    ]
    for prefix in prefixes:
        if s.startswith(prefix):
            return s[len(prefix):]
    return s


def _is_missing_value(val: Any, zero_is_missing: bool = False) -> bool:
    if val is None:
        return True
    if isinstance(val, str):
        text = val.strip()
        if text in {"", "N/A", "None", "null", "nan"}:
            return True
        try:
            parsed = float(text.rstrip("%"))
            if math.isnan(parsed):
                return True
            if zero_is_missing and parsed == 0:
                return True
        except (TypeError, ValueError):
            pass
        return False
    try:
        parsed = float(val)
        if math.isnan(parsed):
            return True
        if zero_is_missing and parsed == 0:
            return True
    except (TypeError, ValueError):
        return False
    return False


def _display_value(
    val: Any,
    zero_is_missing: bool = False,
    missing_text: str = "NA（接口未返回）",
    style: str = "auto",
) -> str:
    if _is_missing_value(val, zero_is_missing=zero_is_missing):
        return _normalize_missing_text(missing_text)
    try:
        return _format_number(val, style=style)
    except (TypeError, ValueError):
        return str(val)


def _display_percent(
    val: Any,
    zero_is_missing: bool = False,
    missing_text: str = "NA（接口未返回）",
) -> str:
    if _is_missing_value(val, zero_is_missing=zero_is_missing):
        return _normalize_missing_text(missing_text)
    text = str(val).strip()
    if text.endswith("%"):
        try:
            return f"{float(text.rstrip('%')):.2f}%"
        except (TypeError, ValueError):
            return text
    try:
        return f"{float(text):.2f}%"
    except (TypeError, ValueError):
        return _normalize_missing_text(missing_text)


def _resolve_templates_dir() -> Path:
    """Resolve template directory relative to project root."""
    config = get_config()
    base = Path(__file__).resolve().parent.parent.parent
    templates_dir = Path(config.report_templates_dir)
    if not templates_dir.is_absolute():
        return base / templates_dir
    return templates_dir


def render(
    platform: str,
    results: List[AnalysisResult],
    report_date: Optional[str] = None,
    summary_only: bool = False,
    extra_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Render report using Jinja2 template.

    Args:
        platform: One of: markdown, wechat, brief
        results: List of AnalysisResult
        report_date: Report date string (default: today)
        summary_only: Whether to output summary only
        extra_context: Additional template context

    Returns:
        Rendered string, or None on error (caller should fallback).
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
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
            (getattr(result, "report_language", None) for result in results if getattr(result, "report_language", None)),
            None,
        )
        or getattr(get_config(), "report_language", "zh")
    )
    labels = get_report_labels(report_language)

    # Build template context with pre-computed signal levels (sorted by score)
    sorted_results = sorted(results, key=lambda x: x.sentiment_score, reverse=True)
    sorted_enriched = []
    for r in sorted_results:
        st, se, _ = get_signal_level(r.operation_advice, r.sentiment_score, report_language)
        rn = get_localized_stock_name(r.name, r.code, report_language)
        sorted_enriched.append({
            "result": r,
            "signal_text": st,
            "signal_emoji": se,
            "stock_name": _escape_md(rn),
            "localized_operation_advice": localize_operation_advice(r.operation_advice, report_language),
            "localized_trend_prediction": localize_trend_prediction(r.trend_prediction, report_language),
        })

    buy_count = sum(1 for r in results if getattr(r, "decision_type", "") == "buy")
    sell_count = sum(1 for r in results if getattr(r, "decision_type", "") == "sell")
    hold_count = sum(1 for r in results if getattr(r, "decision_type", "") in ("hold", ""))

    now_sh = _now_shanghai()
    first_time_ctx: Dict[str, Any] = {}
    if results:
        first_dashboard = getattr(results[0], "dashboard", None) or {}
        if isinstance(first_dashboard, dict):
            structured = first_dashboard.get("structured_analysis") or {}
            if isinstance(structured, dict):
                first_time_ctx = structured.get("time_context") or {}
                if not isinstance(first_time_ctx, dict):
                    first_time_ctx = {}

    report_generated_at = _iso_or_none(
        (extra_context or {}).get("report_generated_at")
    ) or _iso_or_none(first_time_ctx.get("report_generated_at")) or now_sh.isoformat()
    report_timestamp = now_sh.strftime("%Y-%m-%d %H:%M:%S")
    market_timestamp = (extra_context or {}).get("market_timestamp") or first_time_ctx.get("market_timestamp")
    news_published_at = (extra_context or {}).get("news_published_at") or first_time_ctx.get("news_published_at")

    def failed_checks(checklist: List[str]) -> List[str]:
        return [c for c in (checklist or []) if c.startswith("❌") or c.startswith("⚠️")]

    context: Dict[str, Any] = {
        "report_date": report_date,
        "report_timestamp": report_timestamp,
        "report_generated_at": report_generated_at,
        "report_generated_at_bjt": _format_bjt_datetime(report_generated_at) or report_timestamp,
        "market_timestamp": market_timestamp,
        "market_timestamp_bjt": _format_bjt_datetime(market_timestamp),
        "market_session_date": (extra_context or {}).get("market_session_date") or first_time_ctx.get("market_session_date"),
        "session_type": (extra_context or {}).get("session_type") or first_time_ctx.get("session_type"),
        "news_published_at": news_published_at,
        "news_published_at_bjt": _format_bjt_datetime(news_published_at),
        "to_shanghai_iso": _to_shanghai_iso,
        "results": sorted_results,
        "enriched": sorted_enriched,  # Sorted by sentiment_score desc
        "summary_only": summary_only,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "hold_count": hold_count,
        "labels": labels,
        "report_language": report_language,
        "escape_md": _escape_md,
        "clean_sniper": _clean_sniper_value,
        "display_value": _display_value,
        "display_percent": _display_percent,
        "na": _na,
        "is_missing_value": _is_missing_value,
        "failed_checks": failed_checks,
        "history_by_code": {},
        "localize_operation_advice": localize_operation_advice,
        "localize_trend_prediction": localize_trend_prediction,
        "localize_chip_health": localize_chip_health,
        "is_us_stock_code": is_us_stock_code,
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
        )
        template = env.get_template(template_name)
        return template.render(**context)
    except Exception as e:
        logger.warning("Report render failed for %s: %s", template_name, e)
        return None
