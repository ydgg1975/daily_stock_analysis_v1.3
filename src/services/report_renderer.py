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
        return f"{float(val):.2f}"
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
            s = s[len(prefix):]
            break
    return _NUMERIC_TOKEN_RE.sub(lambda m: f"{float(m.group(0)):.2f}", s)


def _safe_float(val: Any) -> Optional[float]:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        try:
            parsed = float(val)
        except (TypeError, ValueError):
            return None
        return None if math.isnan(parsed) else parsed
    text = str(val).strip().replace(",", "")
    if not text or text in {"N/A", "None", "null", "nan", "数据缺失"}:
        return None
    if text.endswith("%"):
        text = text[:-1]
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(parsed) else parsed


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


def _display_value(val: Any, zero_is_missing: bool = False, missing_text: str = "N/A") -> str:
    if _is_missing_value(val, zero_is_missing=zero_is_missing):
        return missing_text
    return str(val)


def _display_number(
    val: Any,
    digits: int = 2,
    zero_is_missing: bool = False,
    missing_text: str = "N/A",
) -> str:
    if _is_missing_value(val, zero_is_missing=zero_is_missing):
        return missing_text
    num = _safe_float(val)
    if num is None:
        return str(val)
    return f"{num:.{digits}f}"


def _display_price(val: Any, digits: int = 2, missing_text: str = "数据缺失") -> str:
    return _display_number(val, digits=digits, missing_text=missing_text)


def _display_multiple(val: Any, digits: int = 1, missing_text: str = "数据缺失") -> str:
    if _is_missing_value(val):
        return missing_text
    num = _safe_float(val)
    if num is None:
        return str(val)
    return f"{num:.{digits}f} 倍"


def _currency_suffix(stock_code: Optional[str]) -> str:
    code = str(stock_code or "").strip()
    if is_us_stock_code(code):
        return "美元"
    if is_hk_stock_code(code):
        return "港元"
    return "元"


def _display_compact_money(
    val: Any,
    stock_code: Optional[str] = None,
    digits: int = 1,
    missing_text: str = "数据缺失",
) -> str:
    if _is_missing_value(val):
        return missing_text
    num = _safe_float(val)
    if num is None:
        return str(val)
    suffix = _currency_suffix(stock_code)
    abs_num = abs(num)
    if abs_num >= 1_0000_0000_0000:
        return f"{num / 1_0000_0000_0000:.{digits}f} 万亿{suffix}"
    if abs_num >= 1_0000_0000:
        return f"{num / 1_0000_0000:.{digits}f} 亿{suffix}"
    if abs_num >= 1_0000:
        return f"{num / 1_0000:.{digits}f} 万{suffix}"
    return f"{num:.2f} {suffix}"


def _display_compact_count(
    val: Any,
    digits: int = 2,
    missing_text: str = "数据缺失",
) -> str:
    if _is_missing_value(val):
        return missing_text
    if isinstance(val, str):
        text = val.strip()
        if not text:
            return missing_text
        if any(unit in text for unit in ("亿", "万", "K", "M", "B", "手")) and _safe_float(text) is None:
            return text
    num = _safe_float(val)
    if num is None:
        return str(val)
    abs_num = abs(num)
    if abs_num >= 1_0000_0000:
        return f"{num / 1_0000_0000:.{digits}f}亿"
    if abs_num >= 1_0000:
        return f"{num / 1_0000:.{digits}f}万"
    return f"{num:.0f}"


def _display_percent(
    val: Any,
    zero_is_missing: bool = False,
    missing_text: str = "数据缺失",
    *,
    ratio: bool = False,
    digits: int = 2,
) -> str:
    if _is_missing_value(val, zero_is_missing=zero_is_missing):
        return missing_text
    text = str(val).strip()
    if text.endswith("%"):
        num = _safe_float(text)
        return f"{num:.{digits}f}%" if num is not None else missing_text
    num = _safe_float(text)
    if num is None:
        return missing_text
    if ratio:
        num *= 100
    return f"{num:.{digits}f}%"


def _display_percent_or_text(
    val: Any,
    digits: int = 2,
    missing_text: str = "数据缺失",
) -> str:
    if _is_missing_value(val):
        return missing_text
    text = str(val).strip()
    if text.endswith("%"):
        num = _safe_float(text)
        return f"{num:.{digits}f}%" if num is not None else text
    num = _safe_float(text)
    if num is None:
        return text
    return f"{num:.{digits}f}%"


def _join_short_clauses(clauses: List[str]) -> str:
    cleaned = [str(item).strip(" ，。；;") for item in clauses if str(item).strip(" ，。；;")]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return f"{cleaned[0]}。"
    if len(cleaned) == 2:
        return f"{cleaned[0]}，{cleaned[1]}。"
    return f"{'、'.join(cleaned[:-1])}，{cleaned[-1]}。"


def _summarize_fundamentals(
    fundamentals: Optional[Dict[str, Any]],
    stock_code: Optional[str] = None,
) -> Dict[str, str]:
    payload = fundamentals if isinstance(fundamentals, dict) else {}
    profiles = payload.get("derived_profiles") if isinstance(payload.get("derived_profiles"), dict) else {}
    derived_insights = payload.get("derived_insights") if isinstance(payload.get("derived_insights"), list) else []
    normalized = payload.get("normalized") if isinstance(payload.get("normalized"), dict) else {}
    profile_copy = {
        "growth_profile": {
            "high_growth": "增长强劲",
            "stable_growth": "增长稳健",
            "negative_growth": "增长承压",
        },
        "profitability_profile": {
            "profitable": "盈利能力优秀",
            "near_breakeven_or_loss": "盈利能力承压",
            "gross_margin_positive": "毛利水平尚可",
        },
        "valuation_profile": {
            "valuation_high": "估值偏高",
            "valuation_low": "估值偏低",
            "valuation_neutral": "估值合理",
        },
        "cashflow_profile": {
            "cashflow_healthy": "现金流健康",
            "cashflow_pressure": "现金流承压",
        },
        "leverage_profile": {
            "high_leverage": "杠杆偏高",
            "leverage_controllable": "杠杆可控",
        },
    }
    clauses: List[str] = []
    for key in (
        "growth_profile",
        "profitability_profile",
        "valuation_profile",
        "cashflow_profile",
        "leverage_profile",
    ):
        phrase = profile_copy.get(key, {}).get(profiles.get(key))
        if phrase:
            clauses.append(phrase)
    if not clauses:
        insight_copy = {
            "valuation_high": "估值偏高",
            "valuation_low": "估值偏低",
            "valuation_neutral": "估值合理",
            "high_growth": "增长强劲",
            "stable_growth": "增长稳健",
            "negative_growth": "增长承压",
            "profitable": "盈利能力优秀",
            "near_breakeven_or_loss": "盈利能力承压",
            "gross_margin_positive": "毛利水平尚可",
            "cashflow_healthy": "现金流健康",
            "cashflow_pressure": "现金流承压",
            "high_leverage": "杠杆偏高",
            "leverage_controllable": "杠杆可控",
        }
        clauses.extend([insight_copy.get(item) for item in derived_insights if insight_copy.get(item)])
    conclusion = _join_short_clauses(clauses[:4])
    if not conclusion:
        conclusion = "基本面信息有限，当前更适合结合技术面信号判断。"

    metrics: List[str] = []

    revenue_growth = normalized.get("revenueGrowth")
    if not _is_missing_value(revenue_growth):
        metrics.append(f"营收增速 {_display_percent(revenue_growth, ratio=True, digits=1)}")

    forward_pe = normalized.get("forwardPE")
    trailing_pe = normalized.get("trailingPE")
    if not _is_missing_value(forward_pe):
        metrics.append(f"前瞻PE {_display_multiple(forward_pe, digits=1)}")
    elif not _is_missing_value(trailing_pe):
        metrics.append(f"TTM PE {_display_multiple(trailing_pe, digits=1)}")

    free_cashflow = normalized.get("freeCashflow")
    operating_cashflow = normalized.get("operatingCashflow")
    if not _is_missing_value(free_cashflow):
        metrics.append(f"自由现金流 {_display_compact_money(free_cashflow, stock_code=stock_code, digits=1)}")
    elif not _is_missing_value(operating_cashflow):
        metrics.append(f"经营现金流 {_display_compact_money(operating_cashflow, stock_code=stock_code, digits=1)}")

    debt_to_equity = normalized.get("debtToEquity")
    if not _is_missing_value(debt_to_equity):
        metrics.append(f"负债权益比 {_display_percent(debt_to_equity, digits=1)}")

    return_on_equity = normalized.get("returnOnEquity")
    if len(metrics) < 2 and not _is_missing_value(return_on_equity):
        metrics.append(f"ROE {_display_percent(return_on_equity, ratio=True, digits=1)}")

    total_revenue = normalized.get("totalRevenue")
    if len(metrics) < 2 and not _is_missing_value(total_revenue):
        metrics.append(f"营收规模 {_display_compact_money(total_revenue, stock_code=stock_code, digits=1)}")

    return {
        "conclusion": conclusion,
        "metrics": "、".join(metrics[:4]),
    }


def _summarize_earnings(earnings: Optional[Dict[str, Any]]) -> str:
    payload = earnings if isinstance(earnings, dict) else {}
    metrics = payload.get("derived_metrics") if isinstance(payload.get("derived_metrics"), dict) else {}
    flags = set(payload.get("summary_flags") or payload.get("earnings_flags") or [])
    narratives = payload.get("narrative_insights") if isinstance(payload.get("narrative_insights"), list) else []
    yoy_revenue = _safe_float(metrics.get("yoy_revenue_growth"))
    yoy_profit = _safe_float(metrics.get("yoy_net_income_change"))
    qoq_revenue = _safe_float(metrics.get("qoq_revenue_growth"))
    qoq_profit = _safe_float(metrics.get("qoq_net_income_change"))
    loss_status = metrics.get("loss_status")

    if loss_status == "loss":
        if "loss_narrowing" in flags:
            return "仍处亏损阶段，但亏损已有收窄迹象，后续需等待盈利拐点确认。"
        return "仍处亏损阶段，盈利修复节奏仍需继续观察。"
    if yoy_revenue is not None and yoy_profit is not None:
        if yoy_revenue > 0 and yoy_profit > 0:
            return "营收和利润延续增长，但短线走势仍需等待技术面确认。"
        if yoy_revenue > 0 and yoy_profit <= 0:
            return "营收保持增长，但利润释放仍待确认，短线更适合等待技术面配合。"
        if yoy_revenue <= 0 and yoy_profit <= 0:
            return "营收和利润动能同步转弱，短线更适合先观察业绩拐点。"
    if qoq_revenue is not None and qoq_profit is not None:
        if qoq_revenue > 0 and qoq_profit > 0:
            return "最新季度营收和利润边际改善，但仍需后续数据确认趋势延续。"
        if qoq_revenue > 0 and qoq_profit <= 0:
            return "营收环比回升，但利润改善暂未跟上，需继续关注利润兑现。"
    if "revenue_up_profit_not_following" in flags:
        return "营收端仍有韧性，但利润跟进不足，短线更适合等待确认信号。"
    if "continuous_loss" in flags:
        return "连续亏损尚未扭转，财报趋势偏弱，需优先关注盈利修复。"
    narrative_map = {
        "margins improving": "利润率改善，后续仍需观察趋势延续。",
        "财报趋势中性，建议结合下一季数据确认。": "财报趋势偏中性，建议继续跟踪后续数据。",
        "连续亏损，盈利质量偏弱": "连续亏损，盈利质量偏弱，需先观察修复进度。",
        "亏损收窄，边际改善": "亏损出现收窄，经营边际已有改善。",
        "存在增收不增利迹象": "营收改善但利润跟进不足，仍需观察兑现质量。",
    }
    for item in narratives:
        text = str(item).strip()
        if not text:
            continue
        mapped = narrative_map.get(text, text if any("\u4e00" <= ch <= "\u9fff" for ch in text) else "")
        if mapped:
            return mapped if mapped.endswith("。") else f"{mapped}。"
    return "财报数据暂不足以形成明确趋势判断，建议继续跟踪后续指引。"


def _summarize_sentiment(sentiment: Optional[Dict[str, Any]]) -> str:
    payload = sentiment if isinstance(sentiment, dict) else {}
    if not payload:
        return "市场情绪信息有限，先以技术面和成交验证为主。"

    relevance_type = payload.get("relevance_type")
    company_sentiment = payload.get("company_sentiment")
    industry_sentiment = payload.get("industry_sentiment")
    regulatory_sentiment = payload.get("regulatory_sentiment")

    if regulatory_sentiment == "negative":
        return "消息面存在监管扰动，市场整体偏谨慎，短线宜控制节奏。"
    if relevance_type and relevance_type != "company_specific":
        if industry_sentiment == "positive":
            return "消息更多反映行业背景，情绪边际回暖，但公司层面催化仍待验证。"
        if industry_sentiment == "negative":
            return "消息更多来自行业层面扰动，市场情绪偏谨慎，宜等待更明确催化。"
        return "缺少高相关度公司新闻，市场情绪以观望为主。"

    if company_sentiment == "positive":
        return "公司相关消息偏积极，市场情绪整体偏谨慎乐观。"
    if company_sentiment == "negative":
        return "公司相关消息偏谨慎，市场情绪仍以防守为主。"
    if company_sentiment == "neutral":
        return "消息面暂无明显方向性催化，市场情绪偏观望。"
    return "缺少高相关度公司新闻，市场情绪以观望为主。"


def _pick_first_present(*values: Any) -> Any:
    for value in values:
        if not _is_missing_value(value):
            return value
    return None


def _normalize_inline_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip().strip("-")


def _summarize_volume_judgment(volume_analysis: Optional[Dict[str, Any]]) -> str:
    payload = volume_analysis if isinstance(volume_analysis, dict) else {}
    status_raw = _normalize_inline_text(payload.get("volume_status"))
    status = status_raw.lower()
    ratio = _safe_float(payload.get("volume_ratio"))
    meaning = _normalize_inline_text(payload.get("volume_meaning"))

    if any(token in status for token in ("缺失", "missing", "unavailable")):
        return ""
    if "放量" in status or (ratio is not None and ratio >= 1.20):
        return "放量，短线资金参与度提升。"
    if "缩量" in status or (ratio is not None and ratio < 0.80):
        return "缩量，追价意愿偏弱。"
    if any(token in status for token in ("正常", "平量", "normal")) or ratio is not None:
        return "平量，资金参与度维持常态。"
    if meaning:
        return meaning if meaning.endswith(("。", "！", "？", ".", "!", "?")) else f"{meaning}。"
    return ""


def _build_market_brief(result: AnalysisResult, data_perspective: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    payload = data_perspective if isinstance(data_perspective, dict) else {}
    snapshot = getattr(result, "market_snapshot", None)
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    price_data = payload.get("price_position") if isinstance(payload.get("price_position"), dict) else {}
    volume_analysis = payload.get("volume_analysis") if isinstance(payload.get("volume_analysis"), dict) else {}

    current_price = _pick_first_present(snapshot.get("price"), snapshot.get("close"), price_data.get("current_price"))
    change_pct = _pick_first_present(snapshot.get("pct_chg"), snapshot.get("change_pct"), getattr(result, "change_pct", None))
    high = _pick_first_present(snapshot.get("high"))
    low = _pick_first_present(snapshot.get("low"))
    volume = _pick_first_present(snapshot.get("volume"))
    volume_judgment = _summarize_volume_judgment(volume_analysis)

    return {
        "current_price": _display_price(current_price) if current_price is not None else "",
        "change_pct": _display_percent(change_pct) if change_pct is not None else "",
        "high": _display_price(high) if high is not None else "",
        "low": _display_price(low) if low is not None else "",
        "volume": _display_compact_count(volume) if volume is not None else "",
        "volume_judgment": volume_judgment,
    }


def _build_technical_brief(data_perspective: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    payload = data_perspective if isinstance(data_perspective, dict) else {}
    price_data = payload.get("price_position") if isinstance(payload.get("price_position"), dict) else {}
    alpha_data = payload.get("alpha_vantage") if isinstance(payload.get("alpha_vantage"), dict) else {}

    current_price = _pick_first_present(price_data.get("current_price"))
    ma5 = _pick_first_present(price_data.get("ma5"))
    ma10 = _pick_first_present(price_data.get("ma10"))
    ma20_raw = _pick_first_present(price_data.get("ma20"), alpha_data.get("sma20"))
    support = _pick_first_present(price_data.get("support_level"))
    resistance = _pick_first_present(price_data.get("resistance_level"))

    ma20_position = ""
    current_num = _safe_float(current_price)
    ma20_num = _safe_float(ma20_raw)
    if current_num is not None and ma20_num is not None:
        if current_num >= ma20_num:
            ma20_position = "当前位于 MA20 上方，短线仍在中期支撑之上。"
        else:
            ma20_position = "当前位于 MA20 下方，短线仍需等待趋势修复。"

    return {
        "ma5": _display_price(ma5) if ma5 is not None else "",
        "ma10": _display_price(ma10) if ma10 is not None else "",
        "ma20": _display_price(ma20_raw) if ma20_raw is not None else "",
        "support": _display_price(support) if support is not None else "",
        "resistance": _display_price(resistance) if resistance is not None else "",
        "ma20_position": ma20_position,
    }


def _select_intel_highlight(intelligence: Optional[Dict[str, Any]], company_news_allowed: bool = True) -> str:
    payload = intelligence if isinstance(intelligence, dict) else {}
    risk_alerts = payload.get("risk_alerts") if isinstance(payload.get("risk_alerts"), list) else []
    catalysts = payload.get("positive_catalysts") if isinstance(payload.get("positive_catalysts"), list) else []
    latest_news = _normalize_inline_text(payload.get("latest_news"))

    if company_news_allowed and risk_alerts:
        return f"风险：{_normalize_inline_text(risk_alerts[0])}"
    if company_news_allowed and catalysts:
        return f"催化：{_normalize_inline_text(catalysts[0])}"
    if latest_news:
        return f"{'行业背景' if not company_news_allowed else '最新动态'}：{latest_news}"
    if risk_alerts:
        return f"风险：{_normalize_inline_text(risk_alerts[0])}"
    if catalysts:
        return f"催化：{_normalize_inline_text(catalysts[0])}"
    return ""


def _summarize_checklist(checklist: List[str]) -> str:
    items = [str(item).strip() for item in (checklist or []) if str(item).strip()]
    if not items:
        return ""
    fail_count = sum(1 for item in items if item.startswith("❌"))
    warn_count = sum(1 for item in items if item.startswith("⚠️"))
    themes: List[str] = []
    for item in items:
        if not item.startswith(("❌", "⚠️")):
            continue
        text = item.lower()
        theme = ""
        if any(token in text for token in ("ma", "支撑", "压力", "买点", "回踩", "突破")):
            theme = "买点确认"
        elif any(token in text for token in ("量", "成交", "volume")):
            theme = "量价配合"
        elif any(token in text for token in ("止损", "仓位", "风险", "纪律")):
            theme = "风控纪律"
        elif any(token in text for token in ("趋势", "均线")):
            theme = "趋势确认"
        if theme and theme not in themes:
            themes.append(theme)
    focus = "、".join(themes[:3]) if themes else "买点、量价配合和风控纪律"
    if fail_count:
        return f"仍有{fail_count}项关键条件未满足，重点补齐{focus}。"
    if warn_count:
        return f"仍有{warn_count}项执行条件待确认，重点留意{focus}。"
    return "执行条件基本齐备，可按计划分批执行并严守止损纪律。"


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


def _display_value(val: Any, zero_is_missing: bool = False, missing_text: str = "N/A") -> str:
    if _is_missing_value(val, zero_is_missing=zero_is_missing):
        return missing_text
    return str(val)


def _display_percent(val: Any, zero_is_missing: bool = False, missing_text: str = "数据缺失") -> str:
    if _is_missing_value(val, zero_is_missing=zero_is_missing):
        return missing_text
    text = str(val).strip()
    if text.endswith("%"):
        return text
    try:
        return f"{float(text):.2f}%"
    except (TypeError, ValueError):
        return missing_text


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




def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(str(value).strip().rstrip('%').replace(',', ''))
    except (TypeError, ValueError):
        return None


def _extract_first_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value)
    import re
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _normalize_market_snapshot(snapshot: Any) -> Dict[str, Any]:
    data = snapshot if isinstance(snapshot, dict) else {}
    normalized = dict(data)

    price = _to_float(data.get('price'))
    close = _to_float(data.get('close'))
    current = price if price is not None else close
    prev_close = _to_float(data.get('prev_close'))

    computed_change = (current - prev_close) if current is not None and prev_close not in (None, 0) else None
    computed_pct = (computed_change / prev_close * 100.0) if computed_change is not None and prev_close else None

    existing_change = _to_float(data.get('change_amount'))
    existing_pct = _to_float(data.get('pct_chg'))
    consistency_warnings: List[str] = []

    if existing_change is None and computed_change is not None:
        normalized['change_amount'] = computed_change
    elif existing_change is not None and computed_change is not None and abs(existing_change - computed_change) > 0.05:
        consistency_warnings.append('涨跌额口径不一致，已按当前价/昨收重算')
        normalized['change_amount'] = computed_change

    if existing_pct is None and computed_pct is not None:
        normalized['pct_chg'] = computed_pct
    elif existing_pct is not None and computed_pct is not None and abs(existing_pct - computed_pct) > 0.05:
        consistency_warnings.append('涨跌幅口径不一致，已按涨跌额/昨收重算')
        normalized['pct_chg'] = computed_pct

    if str(data.get('session_type', '')).lower() in {'pre_market', 'post_market', 'after_hours'}:
        consistency_warnings.append('盘前/盘后价格已标注，避免与常规收盘口径混用')

    normalized['consistency_warnings'] = consistency_warnings
    return normalized


def _annotate_trade_levels(current_price: Any, ideal_buy: Any, secondary_buy: Any, stop_loss: Any, trend_prediction: Any) -> Dict[str, Any]:
    cp = _extract_first_number(current_price)
    ib = _extract_first_number(ideal_buy)
    sb = _extract_first_number(secondary_buy)
    sl = _extract_first_number(stop_loss)
    trend = str(trend_prediction or '').lower()

    def _entry_tag(level: Optional[float]) -> Optional[str]:
        if cp is None or level is None:
            return None
        return '突破买点' if level > cp else '回踩买点'

    annotations = {
        'ideal_buy_tag': _entry_tag(ib),
        'secondary_buy_tag': _entry_tag(sb),
        'risk_warnings': [],
    }

    if cp is not None and sl is not None and ('看多' in trend or 'bull' in trend) and sl > cp:
        annotations['risk_warnings'].append('做多语境下止损位高于当前价，请检查风控参数')
    if cp is not None and sl is not None and cp < sl:
        annotations['risk_warnings'].append('当前价已跌破关键防守位，请立即评估止损执行')

    return annotations



def _grade_intel_block(intel: Any) -> Dict[str, Any]:
    block = dict(intel) if isinstance(intel, dict) else {}
    high_value_keywords = (
        "财报", "指引", "监管", "诉讼", "出口限制", "合作", "订单", "供应链", "竞争格局",
        "earnings", "guidance", "regulation", "lawsuit", "export", "partnership", "order", "supply chain",
    )
    low_value_keywords = (
        "发布会", "活动", "亮相", "品牌曝光", "采访", "conference", "event", "appearance", "marketing",
    )

    def _pick(items: Any, limit: int = 3) -> List[str]:
        arr = [str(x).strip() for x in (items or []) if str(x).strip()]
        high = [x for x in arr if any(k.lower() in x.lower() for k in high_value_keywords)]
        if high:
            return high[:limit]
        medium = [x for x in arr if not any(k.lower() in x.lower() for k in low_value_keywords)]
        return medium[:limit]

    block['risk_alerts'] = _pick(block.get('risk_alerts'))
    catalysts = _pick(block.get('positive_catalysts'))
    block['positive_catalysts'] = catalysts
    if not catalysts:
        block['positive_catalysts_notice'] = '未发现高价值新增催化'

    latest_news = str(block.get('latest_news') or '').strip()
    if latest_news and any(k.lower() in latest_news.lower() for k in low_value_keywords):
        block['latest_news'] = ''
        block['latest_news_notice'] = '未发现高价值新增动态'
    return block

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
        "normalize_market_snapshot": _normalize_market_snapshot,
        "annotate_trade_levels": _annotate_trade_levels,
        "grade_intel_block": _grade_intel_block,
        "is_missing_value": _is_missing_value,
        "failed_checks": failed_checks,
        "summarize_fundamentals": _summarize_fundamentals,
        "summarize_earnings": _summarize_earnings,
        "summarize_sentiment": _summarize_sentiment,
        "summarize_volume_judgment": _summarize_volume_judgment,
        "summarize_checklist": _summarize_checklist,
        "build_market_brief": _build_market_brief,
        "build_technical_brief": _build_technical_brief,
        "select_intel_highlight": _select_intel_highlight,
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
