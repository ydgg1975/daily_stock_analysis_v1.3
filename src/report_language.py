# -*- coding: utf-8 -*-

"""Helpers for report output language selection and localization."""



from __future__ import annotations



import re

from typing import Any, Dict, Optional



SUPPORTED_REPORT_LANGUAGES = ("zh", "en")



_REPORT_LANGUAGE_ALIASES = {

    "zh-cn": "zh",

    "zh_cn": "zh",

    "zh-hans": "zh",

    "zh_hans": "zh",

    "zh-tw": "zh",

    "zh_tw": "zh",

    "cn": "zh",

    "chinese": "zh",

    "english": "en",

    "en-us": "en",

    "en_us": "en",

    "en-gb": "en",

    "en_gb": "en",

}



_OPERATION_ADVICE_CANONICAL_MAP = {

    "strong buy": "strong_buy",

    "strong_buy": "strong_buy",

    "강력매수": "strong_buy",

    "강력 매수": "strong_buy",

    "buy": "buy",

    "매수": "buy",

    "accumulate": "buy",

    "add position": "buy",

    "hold": "hold",

    "보유": "hold",

    "관찰": "watch",

    "watch": "watch",

    "wait": "watch",

    "wait and see": "watch",

    "reduce": "reduce",

    "비중축소": "reduce",

    "비중 축소": "reduce",

    "trim": "reduce",

    "sell": "sell",

    "매도": "sell",

    "강력매도": "strong_sell",

    "강력 매도": "strong_sell",

    "strong sell": "strong_sell",

    "strong_sell": "strong_sell",

}



_OPERATION_ADVICE_TRANSLATIONS = {

    "strong_buy": {"zh": "강력 매수", "en": "Strong Buy"},

    "buy": {"zh": "매수", "en": "Buy"},

    "hold": {"zh": "보유", "en": "Hold"},

    "watch": {"zh": "관망", "en": "Watch"},

    "reduce": {"zh": "비중 축소", "en": "Reduce"},

    "sell": {"zh": "매도", "en": "Sell"},

    "strong_sell": {"zh": "강력 매도", "en": "Strong Sell"},

}



_TREND_PREDICTION_CANONICAL_MAP = {

    "strong bullish": "strong_bullish",

    "very bullish": "strong_bullish",

    "강세": "bullish",

    "강한 강세": "strong_bullish",

    "bullish": "bullish",

    "uptrend": "bullish",

    "횡보": "sideways",

    "neutral": "sideways",

    "sideways": "sideways",

    "range-bound": "sideways",

    "약세": "bearish",

    "강한 약세": "strong_bearish",

    "bearish": "bearish",

    "downtrend": "bearish",

    "strong bearish": "strong_bearish",

    "very bearish": "strong_bearish",

}



_TREND_PREDICTION_TRANSLATIONS = {

    "strong_bullish": {"zh": "강한 강세", "en": "Strong Bullish"},

    "bullish": {"zh": "강세", "en": "Bullish"},

    "sideways": {"zh": "횡보", "en": "Sideways"},

    "bearish": {"zh": "약세", "en": "Bearish"},

    "strong_bearish": {"zh": "강한 약세", "en": "Strong Bearish"},

}



_CONFIDENCE_LEVEL_CANONICAL_MAP = {

    "high": "high",

    "높음": "high",

    "medium": "medium",

    "보통": "medium",

    "med": "medium",

    "low": "low",

    "낮음": "low",

}



_CONFIDENCE_LEVEL_TRANSLATIONS = {

    "high": {"zh": "높음", "en": "High"},

    "medium": {"zh": "보통", "en": "Medium"},

    "low": {"zh": "낮음", "en": "Low"},

}



_CHIP_HEALTH_CANONICAL_MAP = {

    "healthy": "healthy",

    "건전": "healthy",

    "average": "average",

    "보통": "average",

    "caution": "caution",

    "주의": "caution",

}



_CHIP_HEALTH_TRANSLATIONS = {

    "healthy": {"zh": "건전", "en": "Healthy"},

    "average": {"zh": "보통", "en": "Average"},

    "caution": {"zh": "주의", "en": "Caution"},

}



_BIAS_STATUS_CANONICAL_MAP = {

    "safe": "safe",

    "안전": "safe",

    "caution": "caution",

    "주의": "caution",

    "risk": "danger",

    "danger": "danger",

    "위험": "danger",

}



_BIAS_STATUS_TRANSLATIONS = {

    "safe": {"zh": "안전", "en": "Safe"},

    "caution": {"zh": "주의", "en": "Caution"},

    "danger": {"zh": "위험", "en": "Danger"},

}



_PLACEHOLDER_BY_LANGUAGE = {

    "zh": "보완 예정",

    "en": "TBD",

}



_UNKNOWN_BY_LANGUAGE = {

    "zh": "알 수 없음",

    "en": "Unknown",

}



_NO_DATA_BY_LANGUAGE = {

    "zh": "데이터 없음",

    "en": "Data unavailable",

}



_GENERIC_STOCK_NAME_BY_LANGUAGE = {

    "zh": "종목명 확인 필요",

    "en": "Unnamed Stock",

}



_REPORT_LABELS: Dict[str, Dict[str, str]] = {

    "zh": {

        "dashboard_title": "의사결정 대시보드",

        "brief_title": "의사결정 요약",

        "analyzed_prefix": "분석 완료",

        "stock_unit": "개 종목",

        "stock_unit_compact": "개",

        "buy_label": "매수",

        "watch_label": "관망",

        "sell_label": "매도",

        "summary_heading": "분석 결과 요약",

        "info_heading": "주요 정보 요약",

        "sentiment_summary_label": "시장 심리",

        "earnings_outlook_label": "실적 전망",

        "risk_alerts_label": "위험 경고",

        "positive_catalysts_label": "긍정 촉매",

        "latest_news_label": "최신 동향",

        "core_conclusion_heading": "핵심 결론",

        "one_sentence_label": "한 줄 판단",

        "time_sensitivity_label": "유효 기간",

        "default_time_sensitivity": "이번 주",

        "position_status_label": "보유 상태",

        "action_advice_label": "매매 의견",

        "no_position_label": "미보유자",

        "has_position_label": "보유자",

        "continue_holding": "계속 보유",

        "market_snapshot_heading": "당일 시세",

        "close_label": "종가",

        "prev_close_label": "전일 종가",

        "open_label": "시가",

        "high_label": "고가",

        "low_label": "저가",

        "change_pct_label": "등락률",

        "change_amount_label": "등락액",

        "amplitude_label": "진폭",

        "volume_label": "거래량",

        "amount_label": "거래대금",

        "current_price_label": "현재가",

        "volume_ratio_label": "거래량 비율",

        "turnover_rate_label": "회전율",

        "source_label": "시세 출처",

        "data_perspective_heading": "데이터 관점",

        "ma_alignment_label": "이동평균 배열",

        "bullish_alignment_label": "상승 배열",

        "yes_label": "예",

        "no_label": "아니오",

        "trend_strength_label": "추세 강도",

        "price_metrics_label": "가격 지표",

        "ma5_label": "MA5",

        "ma10_label": "MA10",

        "ma20_label": "MA20",

        "bias_ma5_label": "이격도(MA5)",

        "support_level_label": "지지선",

        "resistance_level_label": "저항선",

        "chip_label": "수급",

        "battle_plan_heading": "매매 계획",

        "ideal_buy_label": "이상적 매수 지점",

        "secondary_buy_label": "보조 매수 지점",

        "stop_loss_label": "손절선",

        "take_profit_label": "목표가",

        "suggested_position_label": "비중 제안",

        "entry_plan_label": "진입 전략",

        "risk_control_label": "위험 관리",

        "checklist_heading": "점검 목록",

        "failed_checks_heading": "통과하지 못한 점검",

        "history_compare_heading": "이전 신호 비교",

        "time_label": "시간",

        "score_label": "점수",

        "advice_label": "의견",

        "trend_label": "추세",

        "generated_at_label": "리포트 생성 시간",

        "report_time_label": "생성 시간",

        "no_results": "분석 결과 없음",

        "report_title": "주식 분석 리포트",

        "avg_score_label": "평균 점수",

        "action_points_heading": "매매 지점",

        "position_advice_heading": "보유 의견",

        "analysis_model_label": "분석 모델",

        "not_investment_advice": "AI 생성 내용은 참고용이며 투자 조언이 아닙니다.",

        "details_report_hint": "상세 리포트를 참고하세요",

    },

    "en": {

        "dashboard_title": "Decision Dashboard",

        "brief_title": "Decision Brief",

        "analyzed_prefix": "Analyzed",

        "stock_unit": "stocks",

        "stock_unit_compact": "stocks",

        "buy_label": "Buy",

        "watch_label": "Watch",

        "sell_label": "Sell",

        "summary_heading": "Summary",

        "info_heading": "Key Updates",

        "sentiment_summary_label": "Sentiment",

        "earnings_outlook_label": "Earnings Outlook",

        "risk_alerts_label": "Risk Alerts",

        "positive_catalysts_label": "Positive Catalysts",

        "latest_news_label": "Latest News",

        "core_conclusion_heading": "Core Conclusion",

        "one_sentence_label": "One-line Decision",

        "time_sensitivity_label": "Time Sensitivity",

        "default_time_sensitivity": "This week",

        "position_status_label": "Position",

        "action_advice_label": "Action",

        "no_position_label": "No Position",

        "has_position_label": "Holding",

        "continue_holding": "Continue holding",

        "market_snapshot_heading": "Market Snapshot",

        "close_label": "Close",

        "prev_close_label": "Prev Close",

        "open_label": "Open",

        "high_label": "High",

        "low_label": "Low",

        "change_pct_label": "Change %",

        "change_amount_label": "Change",

        "amplitude_label": "Amplitude",

        "volume_label": "Volume",

        "amount_label": "Turnover",

        "current_price_label": "Price",

        "volume_ratio_label": "Volume Ratio",

        "turnover_rate_label": "Turnover Rate",

        "source_label": "Source",

        "data_perspective_heading": "Data View",

        "ma_alignment_label": "MA Alignment",

        "bullish_alignment_label": "Bullish Alignment",

        "yes_label": "Yes",

        "no_label": "No",

        "trend_strength_label": "Trend Strength",

        "price_metrics_label": "Price Metrics",

        "ma5_label": "MA5",

        "ma10_label": "MA10",

        "ma20_label": "MA20",

        "bias_ma5_label": "Bias (MA5)",

        "support_level_label": "Support",

        "resistance_level_label": "Resistance",

        "chip_label": "Chip Structure",

        "battle_plan_heading": "Battle Plan",

        "ideal_buy_label": "Ideal Entry",

        "secondary_buy_label": "Secondary Entry",

        "stop_loss_label": "Stop Loss",

        "take_profit_label": "Target",

        "suggested_position_label": "Position Size",

        "entry_plan_label": "Entry Plan",

        "risk_control_label": "Risk Control",

        "checklist_heading": "Checklist",

        "failed_checks_heading": "Failed Checks",

        "history_compare_heading": "Historical Signal Comparison",

        "time_label": "Time",

        "score_label": "Score",

        "advice_label": "Advice",

        "trend_label": "Trend",

        "generated_at_label": "Generated At",

        "report_time_label": "Generated",

        "no_results": "No analysis results",

        "report_title": "Stock Analysis Report",

        "avg_score_label": "Avg Score",

        "action_points_heading": "Action Levels",

        "position_advice_heading": "Position Advice",

        "analysis_model_label": "Model",

        "not_investment_advice": "AI-generated content for reference only. Not investment advice.",

        "details_report_hint": "See detailed report:",

    },

}



_DECISION_INTENT_NEGATIONS = (

    "아님",

    "아닌",

    "없음",

    "하지 않음",

    "no ",

    "not ",

    " never",

)



_DECISION_INTENT_NEGATION_SCOPE_BREAK_CHARS = ".,;:!?,。;:！?"

_DECISION_INTENT_NEGATION_CONNECTORS = (

    "권장",

    "해야",

    "먼저",

    "지금",

    "잠시",

    "가능",

    "필요",

    "계속",

)





def _strip_decision_negation_connectors(text: str) -> str:

    """Remove common advisory connectors between a negation token and decision word."""

    suffix = text.strip()

    changed = True

    while changed:

        changed = False

        for connector in _DECISION_INTENT_NEGATION_CONNECTORS:

            if suffix.startswith(connector):

                suffix = suffix[len(connector):].strip()

                changed = True

                break

    return suffix





def normalize_report_language(value: Optional[str], default: str = "zh") -> str:

    """Normalize report language to a supported short code."""

    candidate = (value or default).strip().lower().replace(" ", "_")

    candidate = _REPORT_LANGUAGE_ALIASES.get(candidate, candidate)

    if candidate in SUPPORTED_REPORT_LANGUAGES:

        return candidate

    return default





def is_supported_report_language_value(value: Optional[str]) -> bool:

    """Return whether the raw value is a supported language code or alias."""

    candidate = (value or "").strip().lower().replace(" ", "_")

    if not candidate:

        return False

    return candidate in SUPPORTED_REPORT_LANGUAGES or candidate in _REPORT_LANGUAGE_ALIASES





def get_report_labels(language: Optional[str]) -> Dict[str, str]:

    """Return UI copy for the selected report language."""

    normalized = normalize_report_language(language)

    return _REPORT_LABELS[normalized]





def get_placeholder_text(language: Optional[str]) -> str:

    """Return placeholder text for missing localized content."""

    return _PLACEHOLDER_BY_LANGUAGE[normalize_report_language(language)]





def get_unknown_text(language: Optional[str]) -> str:

    """Return localized unknown text."""

    return _UNKNOWN_BY_LANGUAGE[normalize_report_language(language)]





def get_no_data_text(language: Optional[str]) -> str:

    """Return localized data unavailable text."""

    return _NO_DATA_BY_LANGUAGE[normalize_report_language(language)]





def _normalize_lookup_key(value: Any) -> str:

    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")





def _iter_lookup_candidates(value: Any) -> list[str]:

    raw_text = str(value or "").strip()

    if not raw_text:

        return []



    candidates = [raw_text]

    for part in re.split(r"[/|,,,]+", raw_text):

        normalized = part.strip()

        if normalized and normalized not in candidates:

            candidates.append(normalized)

    return candidates





def _canonicalize_lookup_value(value: Any, canonical_map: Dict[str, str]) -> Optional[str]:

    for candidate in _iter_lookup_candidates(value):

        canonical = canonical_map.get(_normalize_lookup_key(candidate))

        if canonical:

            return canonical

    return None





def _first_non_negated_position(text: str, token: str) -> Optional[int]:

    if not text or not token:

        return None



    normalized_text = text.lower().strip()

    if any(ch in normalized_text for ch in "abcdefghijklmnopqrstuvwxyz"):

        matches = list(re.finditer(rf"(?<![a-z0-9_]){re.escape(token)}(?![a-z0-9_])", normalized_text))

    else:

        matches = list(re.finditer(re.escape(token), normalized_text))



    for match in matches:

        prefix = normalized_text[: match.start()]

        if any(prefix.rstrip().endswith(neg) for neg in _DECISION_INTENT_NEGATIONS):

            continue

        lookback = prefix[-12:]

        negated = False

        for neg in _DECISION_INTENT_NEGATIONS:

            if not neg:

                continue

            neg_idx = lookback.rfind(neg)

            if neg_idx < 0:

                continue

            suffix = lookback[neg_idx + len(neg):]

            if not suffix:

                negated = True

                break

            if any(ch in suffix for ch in _DECISION_INTENT_NEGATION_SCOPE_BREAK_CHARS):

                continue

            normalized_suffix = _strip_decision_negation_connectors(suffix)

            if not normalized_suffix:

                negated = True

                break

            if any(ch in normalized_suffix for ch in _DECISION_INTENT_NEGATION_SCOPE_BREAK_CHARS):

                continue

            if len(normalized_suffix) > 6 and token not in normalized_suffix:

                continue

            if normalized_suffix.startswith(token):

                negated = True

                break

        if negated:

            continue

        else:

            return match.start()

    return None





def _is_placeholder_stock_name(value: Any, code: Any = None) -> bool:

    text = str(value or "").strip()

    if not text:

        return True



    lowered = text.lower()

    if lowered in {"n/a", "na", "none", "null", "unknown"}:

        return True

    if text in {"-", "--", "알 수 없음", "보완 예정"}:

        return True



    code_text = str(code or "").strip()

    if code_text and lowered == code_text.lower():

        return True



    return text.startswith("stock") or text.startswith("gupiao")





def _translate_from_map(

    value: Any,

    language: Optional[str],

    *,

    canonical_map: Dict[str, str],

    translations: Dict[str, Dict[str, str]],

) -> str:

    normalized_language = normalize_report_language(language)

    raw_text = str(value or "").strip()

    if not raw_text:

        return raw_text



    canonical = _canonicalize_lookup_value(raw_text, canonical_map)

    if canonical:

        return translations[canonical][normalized_language]

    return raw_text





def localize_operation_advice(value: Any, language: Optional[str]) -> str:

    """Translate operation advice between Chinese and English when recognized."""

    return _translate_from_map(

        value,

        language,

        canonical_map=_OPERATION_ADVICE_CANONICAL_MAP,

        translations=_OPERATION_ADVICE_TRANSLATIONS,

    )





def localize_trend_prediction(value: Any, language: Optional[str]) -> str:

    """Translate trend prediction between Chinese and English when recognized."""

    normalized_language = normalize_report_language(language)

    raw_text = str(value or "").strip()

    if not raw_text:

        return raw_text

    if normalized_language == "zh":

        if re.search(r"[\u4e00-\u9fff]", raw_text):

            return raw_text

    return _translate_from_map(

        value,

        normalized_language,

        canonical_map=_TREND_PREDICTION_CANONICAL_MAP,

        translations=_TREND_PREDICTION_TRANSLATIONS,

    )





def localize_confidence_level(value: Any, language: Optional[str]) -> str:

    """Translate confidence level between Chinese and English when recognized."""

    return _translate_from_map(

        value,

        language,

        canonical_map=_CONFIDENCE_LEVEL_CANONICAL_MAP,

        translations=_CONFIDENCE_LEVEL_TRANSLATIONS,

    )





def localize_chip_health(value: Any, language: Optional[str]) -> str:

    """Translate chip health labels between Chinese and English when recognized."""

    return _translate_from_map(

        value,

        language,

        canonical_map=_CHIP_HEALTH_CANONICAL_MAP,

        translations=_CHIP_HEALTH_TRANSLATIONS,

    )





def localize_bias_status(value: Any, language: Optional[str]) -> str:

    """Translate price bias status labels between Chinese and English when recognized."""

    return _translate_from_map(

        value,

        language,

        canonical_map=_BIAS_STATUS_CANONICAL_MAP,

        translations=_BIAS_STATUS_TRANSLATIONS,

    )





def get_bias_status_emoji(value: Any) -> str:

    """Return the stable alert emoji for a localized or canonical bias status."""

    canonical = _canonicalize_lookup_value(value, _BIAS_STATUS_CANONICAL_MAP)

    if canonical == "safe":

        return "??"

    if canonical == "caution":

        return "?좑툘"

    return "?슚"





def infer_decision_type_from_advice(value: Any, default: str = "hold") -> str:

    """Infer buy/hold/sell from human-readable operation advice."""

    canonical = _canonicalize_lookup_value(value, _OPERATION_ADVICE_CANONICAL_MAP)

    if canonical in {"strong_buy", "buy"}:

        return "buy"

    if canonical in {"reduce", "sell", "strong_sell"}:

        return "sell"

    if canonical in {"hold", "watch"}:

        return "hold"



    normalized_text = _normalize_lookup_key(value)

    best_position: Optional[int] = None

    best_canonical: Optional[str] = None

    for option, canonical in _OPERATION_ADVICE_CANONICAL_MAP.items():

        option_norm = _normalize_lookup_key(option)

        pos = _first_non_negated_position(normalized_text, option_norm)

        if pos is None:

            continue

        if best_position is None or pos < best_position:

            best_position = pos

            best_canonical = canonical



    if best_canonical in {"strong_buy", "buy"}:

        return "buy"

    if best_canonical in {"reduce", "sell", "strong_sell"}:

        return "sell"

    if best_canonical in {"hold", "watch"}:

        return "hold"



    return default





def get_signal_level(advice: Any, score: Any, language: Optional[str]) -> tuple[str, str, str]:

    """Return localized signal text, emoji, and stable color tag."""

    normalized_language = normalize_report_language(language)

    canonical = _canonicalize_lookup_value(advice, _OPERATION_ADVICE_CANONICAL_MAP)

    if canonical == "strong_buy":

        return (_OPERATION_ADVICE_TRANSLATIONS["strong_buy"][normalized_language], "?뮍", "strong_buy")

    if canonical == "buy":

        return (_OPERATION_ADVICE_TRANSLATIONS["buy"][normalized_language], "?윟", "buy")

    if canonical == "hold":

        return (_OPERATION_ADVICE_TRANSLATIONS["hold"][normalized_language], "?윞", "hold")

    if canonical == "watch":

        return (_OPERATION_ADVICE_TRANSLATIONS["watch"][normalized_language], "--", "watch")

    if canonical == "reduce":

        return (_OPERATION_ADVICE_TRANSLATIONS["reduce"][normalized_language], "?윝", "reduce")

    if canonical in {"sell", "strong_sell"}:

        return (_OPERATION_ADVICE_TRANSLATIONS["sell"][normalized_language], "?뵶", "sell")



    try:

        numeric_score = int(float(score))

    except (TypeError, ValueError):

        numeric_score = 50



    if numeric_score >= 80:

        return (_OPERATION_ADVICE_TRANSLATIONS["strong_buy"][normalized_language], "?뮍", "strong_buy")

    if numeric_score >= 65:

        return (_OPERATION_ADVICE_TRANSLATIONS["buy"][normalized_language], "?윟", "buy")

    if numeric_score >= 55:

        return (_OPERATION_ADVICE_TRANSLATIONS["hold"][normalized_language], "?윞", "hold")

    if numeric_score >= 45:

        return (_OPERATION_ADVICE_TRANSLATIONS["watch"][normalized_language], "--", "watch")

    if numeric_score >= 35:

        return (_OPERATION_ADVICE_TRANSLATIONS["reduce"][normalized_language], "?윝", "reduce")

    return (_OPERATION_ADVICE_TRANSLATIONS["sell"][normalized_language], "?뵶", "sell")





def get_localized_stock_name(value: Any, code: Any, language: Optional[str]) -> str:

    """Return a localized stock name placeholder when the original name is missing."""

    raw_text = str(value or "").strip()

    if not _is_placeholder_stock_name(raw_text, code):

        return raw_text

    return _GENERIC_STOCK_NAME_BY_LANGUAGE[normalize_report_language(language)]





def get_sentiment_label(score: int, language: Optional[str]) -> str:

    """Return localized sentiment label by score band."""

    normalized = normalize_report_language(language)

    if normalized == "en":

        if score >= 80:

            return "Very Bullish"

        if score >= 60:

            return "Bullish"

        if score >= 40:

            return "Neutral"

        if score >= 20:

            return "Bearish"

        return "Very Bearish"



    if score >= 80:

        return "jiduleguan"

    if score >= 60:

        return "leguan"

    if score >= 40:

        return "neutral"

    if score >= 20:

        return "beiguan"

    return "jidubeiguan"


