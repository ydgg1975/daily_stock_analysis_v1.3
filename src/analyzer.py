# -*- coding: utf-8 -*-

"""

===================================

Aguwatchlistguzhinenganalysisxitong - AIanalysisceng

===================================



zhize竊?
1. fengzhuang LLM diaoyongluoji竊늯ongguo LiteLLM tongyidiaoyong Gemini/Anthropic/OpenAI deng竊?
2. jiehejishumianhexiaoximianshengchenganalysisbaogao

3. jiexi LLM xiangyingweijiegouhua AnalysisResult

"""



import json

import logging

import math

import re

import time

from dataclasses import dataclass

from typing import Optional, Dict, Any, List, Tuple, Callable



from json_repair import repair_json

try:
    import litellm
    from litellm import Router
except ModuleNotFoundError:
    litellm = None
    Router = None



from src.agent.llm_adapter import get_thinking_extra_body

from src.agent.skills.defaults import CORE_TRADING_SKILL_POLICY_ZH

from src.config import (

    Config,

    extra_litellm_params,

    get_api_keys_for_model,

    get_config,

    get_configured_llm_models,

    resolve_news_window_days,

)

from src.llm.generation_params import apply_litellm_generation_params

from src.llm.errors import call_litellm_with_param_recovery

from src.storage import persist_llm_usage

from src.data.stock_mapping import STOCK_NAME_MAP

from src.report_language import (

    get_signal_level,

    get_no_data_text,

    get_placeholder_text,

    get_unknown_text,

    infer_decision_type_from_advice,

    localize_chip_health,

    localize_confidence_level,

    normalize_report_language,

)

from src.schemas.report_schema import AnalysisReportSchema

from src.market_context import get_market_role, get_market_guidelines



logger = logging.getLogger(__name__)





def _normalize_risk_warning_values(value: Any) -> List[str]:

    """Normalize arbitrary risk_warning values into a flat list of text alerts."""

    if value is None:

        return []

    if isinstance(value, str):

        text = value.strip()

        return [text] if text else []

    if isinstance(value, (list, tuple, set)):

        normalized: List[str] = []

        for item in value:

            normalized.extend(_normalize_risk_warning_values(item))

        return normalized

    if isinstance(value, dict):

        if not value:

            return []

        try:

            dumped = json.dumps(value, ensure_ascii=False)

            text = dumped.strip()

        except (TypeError, ValueError):

            text = str(value).strip()

        return [text] if text else []

    text = str(value).strip()

    return [text] if text else []





class _LiteLLMStreamError(RuntimeError):

    """Internal error wrapper that records whether any text was streamed."""



    def __init__(self, message: str, *, partial_received: bool = False):

        super().__init__(message)

        self.partial_received = partial_received





class _AllModelsFailedError(Exception):

    """Raised when every model in the fallback chain fails.



    This includes both LLM call errors and JSON parse errors (when a

    ``response_validator`` is provided to :meth:`GeminiAnalyzer._call_litellm`).



    The ``last_response_text`` attribute holds the raw text from the last model

    that *did* return a response (but whose JSON could not be validated), so

    callers can still attempt a best-effort text fallback.



    ``last_model`` and ``last_usage`` record the model name and token usage

    from the last attempt so callers can persist usage even on fallback.

    """



    def __init__(

        self,

        message: str,

        *,

        last_response_text: Optional[str] = None,

        last_model: Optional[str] = None,

        last_usage: Optional[Dict[str, Any]] = None,

    ):

        super().__init__(message)

        self.last_response_text = last_response_text

        self.last_model = last_model

        self.last_usage = last_usage or {}





def check_content_integrity(result: "AnalysisResult") -> Tuple[bool, List[str]]:

    """

    Check mandatory fields for report content integrity.

    Returns (pass, missing_fields). Module-level for use by pipeline (agent weak mode).

    """

    missing: List[str] = []



    def _is_blank_text(value: Any) -> bool:

        if value is None:

            return True

        if isinstance(value, str):

            return not value.strip()

        return True



    def _is_invalid_risk_alerts(value: Any) -> bool:

        return not isinstance(value, list)



    def _is_invalid_stop_loss(value: Any) -> bool:

        if value is None:

            return True

        if isinstance(value, (list, tuple, dict)):

            return True

        if isinstance(value, str):

            return not value.strip()

        return False



    if result.sentiment_score is None:

        missing.append("sentiment_score")

    advice = result.operation_advice

    if not advice or not isinstance(advice, str) or _is_blank_text(advice):

        missing.append("operation_advice")

    summary = result.analysis_summary

    if not summary or not isinstance(summary, str) or _is_blank_text(summary):

        missing.append("analysis_summary")

    dash = result.dashboard if isinstance(result.dashboard, dict) else {}

    core = dash.get("core_conclusion")

    core = core if isinstance(core, dict) else {}

    if _is_blank_text(core.get("one_sentence")):

        missing.append("dashboard.core_conclusion.one_sentence")

    intel = dash.get("intelligence")

    intel = intel if isinstance(intel, dict) else None

    if intel is None or _is_invalid_risk_alerts(intel.get("risk_alerts")):

        missing.append("dashboard.intelligence.risk_alerts")

    if result.decision_type in ("buy", "hold"):

        battle = dash.get("battle_plan")

        battle = battle if isinstance(battle, dict) else {}

        sp = battle.get("sniper_points")

        sp = sp if isinstance(sp, dict) else {}

        stop_loss = sp.get("stop_loss")

        if _is_invalid_stop_loss(stop_loss):

            missing.append("dashboard.battle_plan.sniper_points.stop_loss")

    return len(missing) == 0, missing





def apply_placeholder_fill(result: "AnalysisResult", missing_fields: List[str]) -> None:

    """Fill missing mandatory fields with placeholders (in-place). Module-level for pipeline."""



    def _is_blank_text(value: Any) -> bool:

        if value is None:

            return True

        if isinstance(value, str):

            return not value.strip()

        return True



    def _is_invalid_risk_alerts(value: Any) -> bool:

        return not isinstance(value, list)



    def _is_invalid_stop_loss(value: Any) -> bool:

        if value is None:

            return True

        if isinstance(value, (list, tuple, dict)):

            return True

        if isinstance(value, str):

            return not value.strip()

        return False



    placeholder = get_placeholder_text(getattr(result, "report_language", "zh"))

    for field in missing_fields:

        if field == "sentiment_score":

            result.sentiment_score = 50

        elif field == "operation_advice":

            if _is_blank_text(result.operation_advice):

                result.operation_advice = placeholder

        elif field == "analysis_summary":

            if _is_blank_text(result.analysis_summary):

                result.analysis_summary = placeholder

        elif field == "dashboard.core_conclusion.one_sentence":

            if not result.dashboard:

                result.dashboard = {}

            core = result.dashboard.get("core_conclusion")

            if not isinstance(core, dict):

                core = {}

                result.dashboard["core_conclusion"] = core

            fallback_sentence = (

                result.analysis_summary

                or result.operation_advice

                or placeholder

            )

            if _is_blank_text(core.get("one_sentence")):

                result.dashboard["core_conclusion"]["one_sentence"] = fallback_sentence

        elif field == "dashboard.intelligence.risk_alerts":

            if not result.dashboard:

                result.dashboard = {}

            intelligence = result.dashboard.get("intelligence")

            if not isinstance(intelligence, dict):

                intelligence = {}

                result.dashboard["intelligence"] = intelligence

            if _is_invalid_risk_alerts(intelligence.get("risk_alerts")):

                risk_warning_values = _normalize_risk_warning_values(result.risk_warning)

                intelligence["risk_alerts"] = risk_warning_values

        elif field == "dashboard.battle_plan.sniper_points.stop_loss":

            if not result.dashboard:

                result.dashboard = {}

            battle_plan = result.dashboard.get("battle_plan")

            if not isinstance(battle_plan, dict):

                battle_plan = {}

                result.dashboard["battle_plan"] = battle_plan

            sniper_points = battle_plan.get("sniper_points")

            if not isinstance(sniper_points, dict):

                sniper_points = {}

                battle_plan["sniper_points"] = sniper_points

            if _is_invalid_stop_loss(sniper_points.get("stop_loss")):

                sniper_points["stop_loss"] = placeholder





# ---------- chip_structure fallback (Issue #589) ----------



_CHIP_KEYS: tuple = ("profit_ratio", "avg_cost", "concentration", "chip_health")





def _is_value_placeholder(v: Any) -> bool:

    """True if value is empty or placeholder (N/A, shujuqueshi, etc.)."""

    if v is None:

        return True

    if isinstance(v, (int, float)) and v == 0:

        return True

    s = str(v).strip().lower()

    return s in ("", "n/a", "na", "shujuqueshi", "weizhi", "data unavailable", "unknown", "tbd")





_RISK_WARNING_PLACEHOLDER_TEXTS = {

    "",

    "n/a",

    "na",

    "none",

    "null",

    "unknown",

    "tbd",

    "none",

    "daibuchong",

    "shujuqueshi",

    "weizhi",

    "wu",

}



_STRUCTURAL_RISK_PHRASE_HINTS = (

    "zhongdalikong",

    "zhongdafengxian",

    "guanjianfengxian",

    "jianchi",

    "gaoweijianchi",

    "tuishi",

    "tuishifengxian",

    "tingpai",

    "zhongdawenxun",

    "chufa",

    "xianshou",

    "weigui",

    "weiguifengxian",

    "susong",

    "wenxun",

    "jianguan",

    "caiwu",

    "shenji",

    "baolei",

    "baolei",

    "weiyue",

    "weiyuefengxian",

    "liudongxingweiji",

    "zhaiwu",

    "qingsuan",

    "pochan",

    "zhongdabianlian",

    "major risk",

    "material adverse",

    "suspension",

    "delisting",

    "regulatory",

    "downgrade",

    "liquidity",

    "default",

)



_CAPITAL_FLOW_UNAVAILABLE_STATUS = {

    "not_supported",

    "not supported",

    "unsupported",

    "unavailable",

    "not_available",

    "not available",

    "none",

    "na",

    "n/a",

    "null",

    "missing",

}





def _is_meaningful_text(value: Any) -> bool:

    text = str(value).strip() if value is not None else ""

    if not text:

        return False

    lowered = text.strip().lower()

    return lowered not in _RISK_WARNING_PLACEHOLDER_TEXTS





def _safe_float(v: Any, default: float = 0.0) -> float:

    """Safely convert to float; return default on failure. Private helper for chip fill."""

    if v is None:

        return default

    if isinstance(v, (int, float)):

        try:

            return default if math.isnan(float(v)) else float(v)

        except (ValueError, TypeError):

            return default

    try:

        return float(str(v).strip())

    except (TypeError, ValueError):

        return default





_BULLISH_TREND_HINTS: Tuple[str, ...] = (

    "duotoupailie",

    "chixushangzhang",

    "qushixiangshang",

    "shangshengqushi",

    "xiangshangfasan",

    "bullish",

    "uptrend",

)

_WEAK_BULLISH_TREND_HINTS: Tuple[str, ...] = ("ruoshiduotou",)

_BEARISH_TREND_HINTS: Tuple[str, ...] = (

    "kongtoupailie",

    "chixuxiadie",

    "qushixiangxia",

    "xiajiangqushi",

    "xiangxiafasan",

    "bearish",

    "downtrend",

)

_WEAK_BEARISH_TREND_HINTS: Tuple[str, ...] = ("ruoshikongtou",)

_NEGATION_TOKENS: Tuple[str, ...] = (

    "bushi",

    "bingfei",

    "bingwei",

    "meiyou",

    "shangbu",

    "shangwei",

    "wei",

    "wu",

    "bushu",

    "fei",

    "not ",

    "no ",

)

_NEGATION_BREAK_CHARS: Tuple[str, ...] = (",", ".", ";", ":", "!", "?", "\n")
_NEGATION_LOOKBACK_CHARS = 16

_NEGATION_MAX_GAP_CHARS = 8

_NEGATION_SCOPE_BREAK_TOKENS: Tuple[str, ...] = (

    "ershi",

    "danshi",

    "dan",

    "faner",

    "fandao",

    "zhuanwei",

    "zhuancheng",

    "gaiwei",

    "gaicheng",

    " but ",

    " instead ",

    " rather ",

)

_SINGLE_CHAR_NEGATION_GAP_PREFIXES: Tuple[str, ...] = (

    "xingcheng",

    "chuxian",

    "jinru",

    "zhuanwei",

    "zhuancheng",

    "goucheng",

    "chengxian",

    "xianshi",

    "shuyu",

    "shi",

    "you",

    "neng",

    "jian",

    "zhan",

    "shou",

    "po",

)





def _normalize_prompt_reason_items(items: Any) -> List[str]:

    """Normalize prompt reason/risk items into a clean string list."""

    if not isinstance(items, list):

        return []

    normalized: List[str] = []

    for item in items:

        text = str(item).strip()

        if text:

            normalized.append(text)

    return normalized





def _contains_trend_hint(text: str, hints: Tuple[str, ...]) -> bool:

    """Return True when text contains a non-negated strong trend hint."""

    lowered = text.strip().lower()



    def _has_negation_scope_break(gap: str) -> bool:

        normalized_gap = gap.lower()

        for token in _NEGATION_SCOPE_BREAK_TOKENS:

            token_index = normalized_gap.find(token)

            if token_index > 0:

                return True

        return False



    def _is_valid_negation_gap(token: str, gap: str) -> bool:

        if not gap:

            return True

        if token not in {"wei", "wu", "fei"}:

            return True

        return any(gap.startswith(prefix) for prefix in _SINGLE_CHAR_NEGATION_GAP_PREFIXES)



    def _is_negated_match(index: int) -> bool:

        prefix = lowered[max(0, index - _NEGATION_LOOKBACK_CHARS):index]

        for token in _NEGATION_TOKENS:

            token_index = prefix.rfind(token)

            if token_index < 0:

                continue

            gap = prefix[token_index + len(token):]

            if any(char in gap for char in _NEGATION_BREAK_CHARS):

                continue

            stripped_gap = gap.strip()

            if len(stripped_gap) > _NEGATION_MAX_GAP_CHARS:

                continue

            if _has_negation_scope_break(stripped_gap):

                continue

            if not _is_valid_negation_gap(token, stripped_gap):

                continue

            return True

        return False



    for hint in hints:

        keyword = hint.lower()

        start = 0

        while True:

            index = lowered.find(keyword, start)

            if index < 0:

                break

            if not _is_negated_match(index):

                return True

            start = index + len(keyword)

    return False





def _infer_trend_direction(trend: Dict[str, Any]) -> str:

    """Infer the final trend direction from trend_status and ma_alignment."""

    combined = " ".join(

        str(trend.get(key, "")).strip()

        for key in ("trend_status", "ma_alignment")

        if str(trend.get(key, "")).strip()

    )

    if not combined:

        return "neutral"

    lowered = combined.lower()

    normalized = lowered.replace(" ", "")

    has_bullish = (

        _contains_trend_hint(combined, _BULLISH_TREND_HINTS + _WEAK_BULLISH_TREND_HINTS)

        or "ma5>ma10>ma20" in normalized

        or (

            "ma5>ma10" in normalized

            and any(pattern in normalized for pattern in ("ma10?쨗a20", "ma10<=ma20"))

        )

    )

    has_bearish = (

        _contains_trend_hint(combined, _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS)

        or "ma5<ma10<ma20" in normalized

        or (

            "ma5<ma10" in normalized

            and any(pattern in normalized for pattern in ("ma10?쩷a20", "ma10>=ma20"))

        )

    )

    if has_bullish and not has_bearish:

        return "bullish"

    if has_bearish and not has_bullish:

        return "bearish"

    return "neutral"





def _filter_conflicting_trend_items(items: List[str], conflict_hints: Tuple[str, ...]) -> List[str]:

    """Drop reasons that directly conflict with the final trend direction."""

    return [item for item in items if not _contains_trend_hint(item, conflict_hints)]





def _sanitize_trend_analysis_for_prompt(

    trend: Any,

    *,

    volume_change_ratio: Any = None,

) -> Dict[str, Any]:

    """Clean prompt-only trend hints on a derived copy without touching runtime/provider config."""

    trend_dict = dict(trend) if isinstance(trend, dict) else {}

    signal_reasons = _normalize_prompt_reason_items(trend_dict.get("signal_reasons"))

    risk_factors = _normalize_prompt_reason_items(trend_dict.get("risk_factors"))

    prompt_notes: List[str] = []

    trend_direction = _infer_trend_direction(trend_dict)



    if trend_direction == "bearish":

        filtered_signal_reasons = _filter_conflicting_trend_items(

            signal_reasons,

            _BULLISH_TREND_HINTS + _WEAK_BULLISH_TREND_HINTS,

        )

        if len(filtered_signal_reasons) != len(signal_reasons):

            prompt_notes.append("현재 기술적 구조가 약세이므로 약세 판단과 직접 충돌하는 강세 근거를 제거했습니다.")
        signal_reasons = filtered_signal_reasons

        prompt_notes.append(

            "뉴스, 실적, 정책 촉매가 강세라면 사건 기반 기대감으로만 표현하고 기술적 확인 전 확정 매수로 쓰지 마세요."
        )

    elif trend_direction == "bullish":

        filtered_signal_reasons = _filter_conflicting_trend_items(

            signal_reasons,

            _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS,

        )

        if len(filtered_signal_reasons) != len(signal_reasons):

            prompt_notes.append("현재 기술적 구조가 강세이므로 강세 판단과 직접 충돌하는 약세 근거를 제거했습니다.")
        signal_reasons = filtered_signal_reasons

        filtered_risk_factors = _filter_conflicting_trend_items(

            risk_factors,

            _BEARISH_TREND_HINTS + _WEAK_BEARISH_TREND_HINTS,

        )

        if len(filtered_risk_factors) != len(risk_factors):

            prompt_notes.append("현재 기술적 구조가 강세이므로 강세 판단과 직접 충돌하는 약세 위험 설명을 제거했습니다.")
        risk_factors = filtered_risk_factors



    parsed_volume_change = _safe_float(volume_change_ratio, default=math.nan)

    if math.isfinite(parsed_volume_change) and parsed_volume_change > 10:

        prompt_notes.append(

            f"거래량이 전일 대비 약 {parsed_volume_change:.2f}배입니다. 이상 데이터 또는 일회성 거래량 급증일 수 있으므로 거래량 신호를 보수적으로 해석하세요."
        )



    trend_dict["signal_reasons"] = signal_reasons

    trend_dict["risk_factors"] = risk_factors

    trend_dict["prompt_consistency_notes"] = prompt_notes

    trend_dict["prompt_trend_direction"] = trend_direction

    return trend_dict





def _derive_chip_health(profit_ratio: float, concentration_90: float, language: str = "zh") -> str:

    """Derive chip_health from profit_ratio and concentration_90."""

    if profit_ratio >= 0.9:

        return localize_chip_health("jingti", language)  # huolipanjigao

    if concentration_90 >= 0.25:

        return localize_chip_health("jingti", language)  # choumafensan

    if concentration_90 < 0.15 and 0.3 <= profit_ratio < 0.9:

        return localize_chip_health("jiankang", language)  # jizhongqiehuolibilishizhong

    return localize_chip_health("yiban", language)





def _build_chip_structure_from_data(chip_data: Any, language: str = "zh") -> Dict[str, Any]:

    """Build chip_structure dict from ChipDistribution or dict."""

    if hasattr(chip_data, "profit_ratio"):

        pr = _safe_float(chip_data.profit_ratio)

        ac = chip_data.avg_cost

        c90 = _safe_float(chip_data.concentration_90)

    else:

        d = chip_data if isinstance(chip_data, dict) else {}

        pr = _safe_float(d.get("profit_ratio"))

        ac = d.get("avg_cost")

        c90 = _safe_float(d.get("concentration_90"))

    chip_health = _derive_chip_health(pr, c90, language=language)

    return {

        "profit_ratio": f"{pr:.1%}",

        "avg_cost": ac if (ac is not None and _safe_float(ac) != 0.0) else "N/A",

        "concentration": f"{c90:.2%}",

        "chip_health": chip_health,

    }





def fill_chip_structure_if_needed(result: "AnalysisResult", chip_data: Any) -> None:

    """When chip_data exists, fill chip_structure placeholder fields from chip_data (in-place)."""

    if not result or not chip_data:

        return

    try:

        if not result.dashboard:

            result.dashboard = {}

        dash = result.dashboard

        # Use `or {}` rather than setdefault so that an explicit `null` from LLM is also replaced

        dp = dash.get("data_perspective") or {}

        dash["data_perspective"] = dp

        cs = dp.get("chip_structure") or {}

        filled = _build_chip_structure_from_data(

            chip_data,

            language=getattr(result, "report_language", "zh"),

        )

        # Start from a copy of cs to preserve any extra keys the LLM may have added

        merged = dict(cs)

        for k in _CHIP_KEYS:

            if _is_value_placeholder(merged.get(k)):

                merged[k] = filled[k]

        if merged != cs:

            dp["chip_structure"] = merged

            logger.info("[chip_structure] Filled placeholder chip fields from data source (Issue #589)")

    except Exception as e:

        logger.warning("[chip_structure] Fill failed, skipping: %s", e)





_PRICE_POS_KEYS = ("ma5", "ma10", "ma20", "bias_ma5", "bias_status", "current_price", "support_level", "resistance_level")





def fill_price_position_if_needed(

    result: "AnalysisResult",

    trend_result: Any = None,

    realtime_quote: Any = None,

) -> None:

    """Fill missing price_position fields from trend_result / realtime data (in-place)."""

    if not result:

        return

    try:

        if not result.dashboard:

            result.dashboard = {}

        dash = result.dashboard

        dp = dash.get("data_perspective") or {}

        dash["data_perspective"] = dp

        pp = dp.get("price_position") or {}



        computed: Dict[str, Any] = {}

        if trend_result:

            tr = trend_result if isinstance(trend_result, dict) else (

                trend_result.__dict__ if hasattr(trend_result, "__dict__") else {}

            )

            computed["ma5"] = tr.get("ma5")

            computed["ma10"] = tr.get("ma10")

            computed["ma20"] = tr.get("ma20")

            computed["bias_ma5"] = tr.get("bias_ma5")

            computed["current_price"] = tr.get("current_price")

            support_levels = tr.get("support_levels") or []

            resistance_levels = tr.get("resistance_levels") or []

            if support_levels:

                computed["support_level"] = support_levels[0]

            if resistance_levels:

                computed["resistance_level"] = resistance_levels[0]

        if realtime_quote:

            rq = realtime_quote if isinstance(realtime_quote, dict) else (

                realtime_quote.to_dict() if hasattr(realtime_quote, "to_dict") else {}

            )

            if _is_value_placeholder(computed.get("current_price")):

                computed["current_price"] = rq.get("price")



        filled = False

        for k in _PRICE_POS_KEYS:

            if _is_value_placeholder(pp.get(k)) and not _is_value_placeholder(computed.get(k)):

                pp[k] = computed[k]

                filled = True

        if filled:

            dp["price_position"] = pp

            logger.info("[price_position] Filled placeholder fields from computed data")

    except Exception as e:

        logger.warning("[price_position] Fill failed, skipping: %s", e)





def stabilize_decision_with_structure(

    result: "AnalysisResult",

    trend_result: Any = None,

    fundamental_context: Optional[Dict[str, Any]] = None,

) -> None:

    """

    Calibrate aggressive buy/sell advice with price levels and capital flow.



    The LLM can overreact to one-day price movement.  This guard keeps the

    public `decision_type` enum stable while allowing richer neutral wording

    such as zhendang/xipanguancha when support, resistance, and fund flow do not confirm

    an immediate buy/sell action.

    """

    if not result:

        return



    try:

        language = normalize_report_language(getattr(result, "report_language", "zh"))

        dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}

        data_perspective = dashboard.get("data_perspective") if isinstance(dashboard, dict) else {}

        if not isinstance(data_perspective, dict):

            data_perspective = {}

        price_position = data_perspective.get("price_position")

        if not isinstance(price_position, dict):

            price_position = {}



        trend_dict = _as_dict_for_decision_guard(trend_result)

        current_price = _first_numeric_value(

            getattr(result, "current_price", None),

            price_position.get("current_price"),

            trend_dict.get("current_price"),

        )

        support = _first_numeric_value(

            price_position.get("support_level"),

            _first_list_value(trend_dict.get("support_levels")),

        )

        resistance = _first_numeric_value(

            price_position.get("resistance_level"),

            _first_list_value(trend_dict.get("resistance_levels")),

        )

        decision_type = infer_decision_type_from_advice(

            getattr(result, "decision_type", ""),

            default=getattr(result, "decision_type", "hold") or "hold",

        )

        decision_type = decision_type if decision_type in {"buy", "hold", "sell"} else "hold"

        advice_decision_type = infer_decision_type_from_advice(

            getattr(result, "operation_advice", ""),

            default="",

        )



        flow_bias, flow_reason = _capital_flow_bias_with_status(fundamental_context)

        if flow_bias == "unavailable":

            if isinstance(fundamental_context, dict) and "capital_flow" in fundamental_context:

                if decision_type == "buy" or advice_decision_type == "buy":

                    _downgrade_buy_without_capital_flow(

                        result,

                        language,

                        current_price=current_price,

                        support=support,

                        resistance=resistance,

                        flow_status=flow_reason,

                    )

                else:

                    _set_decision_stability_unavailable(

                        result,

                        language,

                        current_price=current_price,

                        support=support,

                        resistance=resistance,

                        flow_status=flow_reason,

                    )

            return



        if current_price is None:

            return



        broke_support = support is not None and current_price < support * 0.985

        near_support = support is not None and not broke_support and current_price <= support * 1.03

        breakout = resistance is not None and current_price > resistance * 1.01

        near_resistance = (

            resistance is not None

            and not breakout

            and current_price >= resistance * 0.97

        )

        mid_range = (

            support is not None

            and resistance is not None

            and support * 1.03 < current_price < resistance * 0.97

        )



        has_significant_risk = _has_structural_risk_alert(result)



        if decision_type == "buy":

            if near_resistance and flow_bias != "inflow":

                _downgrade_to_structural_hold(

                    result,

                    language,

                    advice_key="range",

                    reason_key="buy_near_resistance",

                    current_price=current_price,

                    support=support,

                    resistance=resistance,

                    flow_bias=flow_bias,

                )

            elif flow_bias == "outflow" and not breakout:

                _downgrade_to_structural_hold(

                    result,

                    language,

                    advice_key="range",

                    reason_key="buy_with_outflow",

                    current_price=current_price,

                    support=support,

                    resistance=resistance,

                    flow_bias=flow_bias,

                )

            elif mid_range and flow_bias == "neutral":

                _downgrade_to_structural_hold(

                    result,

                    language,

                    advice_key="range",

                    reason_key="hold_mid_range",

                    current_price=current_price,

                    support=support,

                    resistance=resistance,

                    flow_bias=flow_bias,

                )

        elif decision_type == "sell":

            if near_support and (flow_bias != "outflow") and not has_significant_risk:

                _downgrade_to_structural_hold(

                    result,

                    language,

                    advice_key="shakeout",

                    reason_key="sell_near_support",

                    current_price=current_price,

                    support=support,

                    resistance=resistance,

                    flow_bias=flow_bias,

                )

            elif flow_bias == "inflow" and not broke_support and not has_significant_risk:

                _downgrade_to_structural_hold(

                    result,

                    language,

                    advice_key="hold",

                    reason_key="sell_with_inflow",

                    current_price=current_price,

                    support=support,

                    resistance=resistance,

                    flow_bias=flow_bias,

                )

        elif decision_type == "hold":

            change_pct = _first_numeric_value(getattr(result, "change_pct", None))

            if change_pct is not None and change_pct < 0 and near_support and flow_bias != "outflow":

                _set_structural_hold_wording(

                    result,

                    language,

                    advice_key="shakeout",

                    reason_key="hold_shakeout",

                    current_price=current_price,

                    support=support,

                    resistance=resistance,

                    flow_bias=flow_bias,

                )

            elif mid_range and flow_bias == "neutral":

                _set_structural_hold_wording(

                    result,

                    language,

                    advice_key="range",

                    reason_key="hold_mid_range",

                    current_price=current_price,

                    support=support,

                    resistance=resistance,

                    flow_bias=flow_bias,

                )

        _sync_stability_dashboard_fields(result)

    except Exception as exc:

        logger.warning("[decision_stability] skipped: %s", exc)





def _has_structural_risk_alert(result: "AnalysisResult") -> bool:

    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}



    risk_text = getattr(result, "risk_warning", "")

    if _is_significant_structural_risk(risk_text):

        return True



    intelligence = dashboard.get("intelligence") if isinstance(dashboard, dict) else None

    if isinstance(intelligence, dict):

        risk_alerts = intelligence.get("risk_alerts")

        if isinstance(risk_alerts, str):

            if _is_significant_structural_risk(risk_alerts):

                return True

        elif isinstance(risk_alerts, (list, tuple, set)):

            if any(_is_significant_structural_risk(item) for item in risk_alerts):

                return True



    core_conclusion = dashboard.get("core_conclusion") if isinstance(dashboard, dict) else None

    if isinstance(core_conclusion, dict):

        signal_type = str(core_conclusion.get("signal_type", "")).strip()

        if _is_significant_structural_risk(signal_type):

            return True

    return False





def _is_significant_structural_risk(value: Any) -> bool:

    text = str(value or "").strip()

    if not _is_meaningful_text(text):

        return False



    normalized = text.lower()

    if any(keyword in normalized for keyword in _STRUCTURAL_RISK_PHRASE_HINTS):

        return True



    return "zhongda" in text and "fengxian" in normalized





def _sync_stability_dashboard_fields(result: "AnalysisResult") -> None:

    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}

    result.dashboard = dashboard

    dashboard["sentiment_score"] = getattr(result, "sentiment_score", None)

    dashboard["operation_advice"] = getattr(result, "operation_advice", None)

    dashboard["decision_type"] = getattr(result, "decision_type", None)





def _as_dict_for_decision_guard(value: Any) -> Dict[str, Any]:

    if isinstance(value, dict):

        return value

    if hasattr(value, "to_dict"):

        try:

            converted = value.to_dict()

            return converted if isinstance(converted, dict) else {}

        except Exception:

            return {}

    if hasattr(value, "__dict__"):

        return dict(value.__dict__)

    return {}





def _first_list_value(value: Any) -> Any:

    if isinstance(value, (list, tuple)) and value:

        return value[0]

    return value





def _coerce_numeric_value(value: Any) -> Optional[float]:

    if isinstance(value, bool) or value is None:

        return None

    if isinstance(value, (int, float)):

        if math.isfinite(float(value)):

            return float(value)

        return None

    text = str(value).replace(",", "").replace("%", "").strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL"}:

        return None

    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)

    if not match:

        return None

    try:

        return float(match.group(0))

    except ValueError:

        return None





def _first_numeric_value(*values: Any) -> Optional[float]:

    for value in values:

        if isinstance(value, (list, tuple)):

            nested = _first_numeric_value(*value)

            if nested is not None:

                return nested

            continue

        numeric = _coerce_numeric_value(value)

        if numeric is not None:

            return numeric

    return None





def _capital_flow_bias(fundamental_context: Optional[Dict[str, Any]]) -> str:

    return _capital_flow_bias_with_status(fundamental_context)[0]





def _capital_flow_bias_with_status(

    fundamental_context: Optional[Dict[str, Any]],

) -> tuple[str, str]:

    if not isinstance(fundamental_context, dict):

        return "unavailable", "invalid_context"

    block = fundamental_context.get("capital_flow")

    if not isinstance(block, dict):

        return "unavailable", "capital_flow_block_missing"

    status = str(block.get("status") or "").strip().lower()

    normalized_status = status.replace("-", " ").replace("_", " ").strip()

    if normalized_status in _CAPITAL_FLOW_UNAVAILABLE_STATUS or "not supported" in normalized_status:

        return "unavailable", status or "not_supported"

    data = block.get("data") if isinstance(block.get("data"), dict) else block

    stock_flow = data.get("stock_flow") if isinstance(data, dict) else None

    if not isinstance(stock_flow, dict) or not stock_flow:

        return "unavailable", "empty_stock_flow"



    def _flow_direction(value: Optional[float]) -> Optional[str]:

        if value is None or value == 0:

            return None

        return "inflow" if value > 0 else "outflow"



    numeric_values = [

        _coerce_numeric_value(stock_flow.get("main_net_inflow")),

        _coerce_numeric_value(stock_flow.get("inflow_5d")),

        _coerce_numeric_value(stock_flow.get("inflow_10d")),

    ]

    if all(value is None for value in numeric_values):

        return "unavailable", "missing_or_na_flow_fields"



    ordered_signals = [

        _flow_direction(value) for value in numeric_values

    ]

    directions = {signal for signal in ordered_signals if signal is not None}

    if not directions or len(directions) > 1:

        return "neutral", "conflict_or_missing"

    for signal in ordered_signals:

        if signal is not None:

            return signal, "ok"

    return "neutral", "neutral"





def _capital_flow_status_for_stability(reason: str, language: str) -> str:

    normalized = str(reason or "").strip().lower()

    if "not_supported" in normalized or "unsupported" in normalized or "not available" in normalized:

        return "marketzijinliufuwuzanbuzhichi" if language == "zh" else "Capital flow source unsupported"

    if "empty_stock_flow" in normalized or "missing" in normalized:

        return "zijinliushujuqueshi" if language == "zh" else "capital flow data unavailable"

    return "zijinliushujubukeyong" if language == "zh" else "capital flow unavailable"





def _set_decision_stability_unavailable(

    result: "AnalysisResult",

    language: str,

    *,

    current_price: Optional[float],

    support: Optional[float],

    resistance: Optional[float],

    flow_status: str,

) -> None:

    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}

    result.dashboard = dashboard

    dashboard["decision_stability"] = {

        "applied": False,

        "reason": "zijinliubukeyong竊똷eishiyongzijinliujiaozhun" if language == "zh" else "Capital flow unavailable; stability calibration not applied",

        "capital_flow_status": _capital_flow_status_for_stability(flow_status, language),

        "current_price": current_price,

        "support": support,

        "resistance": resistance,

        "capital_flow_bias": "unavailable",

    }

    _sync_stability_dashboard_fields(result)





def _bound_hold_watch_sentiment_score(result: "AnalysisResult") -> None:

    try:

        score = int(getattr(result, "sentiment_score", 50))

    except (TypeError, ValueError):

        score = 50

    result.sentiment_score = min(59, max(45, score))





def _apply_hold_watch_dashboard(

    result: "AnalysisResult",

    language: str,

    *,

    advice: str,

    reason: str,

    current_price: Optional[float],

    support: Optional[float],

    resistance: Optional[float],

    flow_bias: str,

    no_position: str,

    has_position: str,

    capital_flow_status: Optional[str] = None,

) -> None:

    result.operation_advice = advice



    dashboard = result.dashboard if isinstance(result.dashboard, dict) else {}

    result.dashboard = dashboard

    core = dashboard.get("core_conclusion")

    if not isinstance(core, dict):

        core = {}

        dashboard["core_conclusion"] = core

    core["signal_type"] = "보유/관망" if language == "zh" else "Hold / Watch"
    core["one_sentence"] = f"{advice}: {reason}"


    position_advice = core.get("position_advice")

    if not isinstance(position_advice, dict):

        position_advice = {}

        core["position_advice"] = position_advice

    position_advice["no_position"] = no_position

    position_advice["has_position"] = has_position



    stability = {

        "applied": True,

        "reason": reason,

        "current_price": current_price,

        "support": support,

        "resistance": resistance,

        "capital_flow_bias": flow_bias,

    }

    if capital_flow_status is not None:

        stability["capital_flow_status"] = capital_flow_status

    dashboard["decision_stability"] = stability



    if reason and reason not in str(result.risk_warning or ""):

        sep = "; "
        result.risk_warning = f"{result.risk_warning}{sep}{reason}" if result.risk_warning else reason

    result.buy_reason = reason or result.buy_reason





def _downgrade_buy_without_capital_flow(

    result: "AnalysisResult",

    language: str,

    *,

    current_price: Optional[float],

    support: Optional[float],

    resistance: Optional[float],

    flow_status: str,

) -> None:

    status_text = _capital_flow_status_for_stability(flow_status, language)

    if language == "zh":

        advice = "보유/관망"
        reason = f"{status_text}; 매수 판단에 자금 흐름 확인이 부족하므로 관망으로 처리합니다."
        no_position = "미보유자는 추격 매수하지 말고 자금 흐름 회복, 지지 확인, 유효 돌파를 기다리세요."
        has_position = "보유자는 핵심 지지선을 위험 관리 기준으로 삼고 자금 흐름 회복 전까지 비중을 조절하세요."
        confidence = "낮음"
    else:

        advice = "Hold and watch"

        reason = f"{status_text}; the buy call lacks capital-flow confirmation, so treat it as watch-only."

        no_position = "Do not chase; wait for capital-flow recovery, support confirmation, or a valid breakout."

        has_position = "Use key support as the risk line and keep position size controlled until capital flow recovers."

        confidence = "Low"



    result.decision_type = "hold"

    result.confidence_level = confidence

    _bound_hold_watch_sentiment_score(result)

    _apply_hold_watch_dashboard(

        result,

        language,

        advice=advice,

        reason=reason,

        current_price=current_price,

        support=support,

        resistance=resistance,

        flow_bias="unavailable",

        no_position=no_position,

        has_position=has_position,

        capital_flow_status=status_text,

    )

    _sync_stability_dashboard_fields(result)

    logger.info("[decision_stability] Downgraded buy because capital flow is unavailable: %s", flow_status)





def _downgrade_to_structural_hold(

    result: "AnalysisResult",

    language: str,

    *,

    advice_key: str,

    reason_key: str,

    current_price: float,

    support: Optional[float],

    resistance: Optional[float],

    flow_bias: str,

) -> None:

    result.decision_type = "hold"

    _bound_hold_watch_sentiment_score(result)

    _set_structural_hold_wording(

        result,

        language,

        advice_key=advice_key,

        reason_key=reason_key,

        current_price=current_price,

        support=support,

        resistance=resistance,

        flow_bias=flow_bias,

    )





def _set_structural_hold_wording(

    result: "AnalysisResult",

    language: str,

    *,

    advice_key: str,

    reason_key: str,

    current_price: float,

    support: Optional[float],

    resistance: Optional[float],

    flow_bias: str,

) -> None:

    advice = {

        "zh": {

            "range": "zhendangguanwang",

            "shakeout": "xipanguancha",

            "hold": "chiyouguancha",

        },

        "en": {

            "range": "Range-bound watch",

            "shakeout": "Shakeout watch",

            "hold": "Hold and watch",

        },

    }[language].get(advice_key, "보유/관망" if language == "zh" else "Hold and watch")
    reason_templates = {

        "zh": {

            "buy_near_resistance": "가격이 저항선에 가깝고 주도 자금 유입이 확인되지 않아 단기 반등만 보고 추격 매수하기 어렵습니다.",
            "buy_with_outflow": "주도 자금 유출이 매수 판단과 충돌하므로 지지 확인 또는 자금 회복을 기다려야 합니다.",
            "sell_near_support": "가격이 지지선에 가깝고 자금의 지속 이탈이 확인되지 않아 당일 하락만으로 즉시 매도하기 어렵습니다.",
            "sell_with_inflow": "주도 자금 유입이 매도 판단과 충돌하므로 우선 보유 관찰하며 지지 이탈 여부를 확인합니다.",
            "hold_shakeout": "가격이 지지선 부근까지 조정됐지만 자금 이탈이 확인되지 않아 흔들기 가능성을 열어두고 관찰합니다.",
            "hold_mid_range": "가격이 지지와 저항 사이에 있고 자금 흐름도 명확하지 않아 횡보 관망이 더 적절합니다.",
        },

        "en": {

            "buy_near_resistance": "Price is near resistance without confirmed main-force inflow, so chasing the rebound is not actionable.",

            "buy_with_outflow": "Main-force outflow conflicts with a buy call; wait for support confirmation or capital inflow.",

            "sell_near_support": "Price is near support without sustained outflow, so a one-day drop is not enough to sell.",

            "sell_with_inflow": "Main-force inflow conflicts with a sell call; hold and watch for support failure.",

            "hold_shakeout": "Price pulled back near support without confirmed outflow, which is better treated as a shakeout watch.",

            "hold_mid_range": "Price is between support and resistance with neutral fund flow, so range-bound watch is more actionable.",

        },

    }

    reason = reason_templates[language].get(reason_key, "")

    result.operation_advice = advice

    if language == "zh" and "횡보" not in str(result.trend_prediction) and advice_key == "range":
        result.trend_prediction = "횡보"
    elif language == "en" and advice_key == "range":

        result.trend_prediction = "Sideways"



    if language == "zh":

        no_position = "미보유자는 추격 매수나 공포 매도를 피하고 지지 확인, 거래량 동반 돌파, 자금 재유입을 기다리세요."
        has_position = "보유자는 핵심 지지선을 위험 관리 기준으로 삼고 지지 이탈 전에는 관찰과 분할 비중 조절을 우선하세요."
    else:

        no_position = "Do not chase or panic; wait for support confirmation, breakout, or renewed inflow."

        has_position = "Use key support as the risk line and manage position size unless support fails."

    _apply_hold_watch_dashboard(

        result,

        language,

        advice=advice,

        reason=reason,

        current_price=current_price,

        support=support,

        resistance=resistance,

        flow_bias=flow_bias,

        no_position=no_position,

        has_position=has_position,

    )

    logger.info("[decision_stability] Applied structural hold calibration: %s", reason_key)





def get_stock_name_multi_source(

    stock_code: str,

    context: Optional[Dict] = None,

    data_manager = None

) -> str:

    """

    duolaiyuanhuoqustockzhongwenmingcheng



    huoqucelve竊늏nyouxianji竊됵폏

    1. congchuanrude context zhonghuoqu竊늭ealtime shuju竊?
    2. congjingtaiyingshebiao STOCK_NAME_MAP huoqu

    3. cong DataFetcherManager huoqu竊늛eshujuyuan竊?
    4. fanhuimorenmingcheng竊늛upiao+daima竊?


    Args:

        stock_code: stockdaima

        context: analysisshangxiawen竊늟exuan竊?
        data_manager: DataFetcherManager shili竊늟exuan竊?


    Returns:

        stockzhongwenmingcheng

    """

    # 1. congshangxiawenhuoqu竊늮hishixinginputju竊?
    if context:

        # youxiancong stock_name ziduanhuoqu

        if context.get('stock_name'):

            name = context['stock_name']

            if name and not name.startswith('stock'):

                return name



        # qicicong realtime shujuhuoqu

        if 'realtime' in context and context['realtime'].get('name'):

            return context['realtime']['name']



    # 2. congjingtaiyingshebiaohuoqu

    if stock_code in STOCK_NAME_MAP:

        return STOCK_NAME_MAP[stock_code]



    # 3. congshujuyuanhuoqu

    if data_manager is None:

        try:

            from data_provider.base import DataFetcherManager

            data_manager = DataFetcherManager()

        except Exception as e:

            logger.debug(f"wufachushihua DataFetcherManager: {e}")



    if data_manager:

        try:

            name = data_manager.get_stock_name(stock_code)

            if name:

                # gengxinhuancun

                STOCK_NAME_MAP[stock_code] = name

                return name

        except Exception as e:

            logger.debug(f"congshujuyuanhuoqustockmingchengshibai: {e}")



    # 4. fanhuimorenmingcheng

    return f'stock{stock_code}'





@dataclass

class AnalysisResult:

    """

    AI analysisjieguoshujulei - jueceyibiaopanban



    fengzhuang Gemini fanhuideanalysisjieguo竊똟aohanjueceyibiaopanhexiangxianalysis

    """

    code: str

    name: str



    # ========== hexinzhibiao ==========

    sentiment_score: int  # zonghepingfen 0-100 (>70qiangliekanduo, >60kanduo, 40-60zhendang, <40kankong)

    trend_prediction: str  # qushiyuce竊쉛iangliekanduo/kanduo/zhendang/kankong/qiangliekankong

    operation_advice: str  # caozuojianyi竊쉖airu/jiacang/chiyou/jiancang/maichu/guanwang

    decision_type: str = "hold"  # jueceleixing竊쉇uy/hold/sell竊늶ongyutongji竊?
    confidence_level: str = "zhong"  # zhixindu竊쉍ao/zhong/di

    report_language: str = "zh"  # baogaoshuchuyuyan竊쉦h/en



    # ========== jueceyibiaopan (xinzeng) ==========

    dashboard: Optional[Dict[str, Any]] = None  # wanzhengdejueceyibiaopanshuju



    # ========== zoushianalysis ==========

    trend_analysis: str = ""  # zoushixingtaianalysis竊늷hichengwei?걓aliwei?걉ushixiandeng竊?
    short_term_outlook: str = ""  # duanqizhanwang竊?-3ri竊?
    medium_term_outlook: str = ""  # zhongqizhanwang竊?-2zhou竊?


    # ========== jishumiananalysis ==========

    technical_analysis: str = ""  # jishuzhibiaozongheanalysis

    ma_analysis: str = ""  # junxiananalysis竊늕uotou/kongtoupailie竊똨incha/sichadeng竊?
    volume_analysis: str = ""  # liangnenganalysis竊늗angliang/suoliang竊똺hulidongxiangdeng竊?
    pattern_analysis: str = ""  # Kxianxingtaianalysis



    # ========== jibenmiananalysis ==========

    fundamental_analysis: str = ""  # jibenmianzongheanalysis

    sector_position: str = ""  # bankuaidiweihehangyequshi

    company_highlights: str = ""  # gongsiliangdian/fengxiandian



    # ========== qingxumian/xiaoximiananalysis ==========

    news_summary: str = ""  # jinqizhongyaoxinwen/gonggaozhaiyao

    market_sentiment: str = ""  # shicquotexuanalysis

    hot_topics: str = ""  # relatedredianhuati



    # ========== zongheanalysis ==========

    analysis_summary: str = ""  # zongheanalysiszhaiyao

    key_points: str = ""  # hexinkandian竊?-5geyaodian竊?
    risk_warning: str = ""  # fengxiantishi

    buy_reason: str = ""  # mairu/maichuliyou



    # ========== yuanshuju ==========

    market_snapshot: Optional[Dict[str, Any]] = None  # dangriquotekuaizhao竊늷hanshiyong竊?
    raw_response: Optional[str] = None  # yuanshixiangying竊늯iaoshiyong竊?
    search_performed: bool = False  # shifouzhixinglelianwangsousuo

    data_sources: str = ""  # shujulaiyuanshuoming

    success: bool = True

    error_message: Optional[str] = None



    # ========== jiageshuju竊늗enxishikuaizhao竊?=========

    current_price: Optional[float] = None  # analysisshidegujia

    change_pct: Optional[float] = None     # analysisshidezhangdiefu(%)



    # ========== modelbiaoji竊뉹ssue #528竊?=========

    model_used: Optional[str] = None  # analysisshiyongde LLM model竊늳anzhengming竊똱u gemini/gemini-2.0-flash竊?


    # ========== lishiduibi竊늃eport Engine P0竊?=========

    query_id: Optional[str] = None  # bencianalysis query_id竊똹ongyulishiduibishipaichubencirecord



    def to_dict(self) -> Dict[str, Any]:

        """zhuanhuanweizidian"""

        return {

            'code': self.code,

            'name': self.name,

            'sentiment_score': self.sentiment_score,

            'trend_prediction': self.trend_prediction,

            'operation_advice': self.operation_advice,

            'decision_type': self.decision_type,

            'confidence_level': self.confidence_level,

            'report_language': self.report_language,

            'dashboard': self.dashboard,  # jueceyibiaopanshuju

            'trend_analysis': self.trend_analysis,

            'short_term_outlook': self.short_term_outlook,

            'medium_term_outlook': self.medium_term_outlook,

            'technical_analysis': self.technical_analysis,

            'ma_analysis': self.ma_analysis,

            'volume_analysis': self.volume_analysis,

            'pattern_analysis': self.pattern_analysis,

            'fundamental_analysis': self.fundamental_analysis,

            'sector_position': self.sector_position,

            'company_highlights': self.company_highlights,

            'news_summary': self.news_summary,

            'market_sentiment': self.market_sentiment,

            'hot_topics': self.hot_topics,

            'analysis_summary': self.analysis_summary,

            'key_points': self.key_points,

            'risk_warning': self.risk_warning,

            'buy_reason': self.buy_reason,

            'market_snapshot': self.market_snapshot,

            'search_performed': self.search_performed,

            'success': self.success,

            'error_message': self.error_message,

            'current_price': self.current_price,

            'change_pct': self.change_pct,

            'model_used': self.model_used,

        }



    def get_core_conclusion(self) -> str:

        """핵심 결론을 한 문장으로 반환합니다."""

        if self.dashboard and 'core_conclusion' in self.dashboard:

            return self.dashboard['core_conclusion'].get('one_sentence', self.analysis_summary)

        return self.analysis_summary



    def get_position_advice(self, has_position: bool = False) -> str:

        """보유 여부에 맞는 포지션 조언을 반환합니다."""

        if self.dashboard and 'core_conclusion' in self.dashboard:

            pos_advice = self.dashboard['core_conclusion'].get('position_advice', {})

            if has_position:

                return pos_advice.get('has_position', self.operation_advice)

            return pos_advice.get('no_position', self.operation_advice)

        return self.operation_advice



    def get_sniper_points(self) -> Dict[str, str]:

        """분석 결과의 주요 가격 포인트를 반환합니다."""

        if self.dashboard and 'battle_plan' in self.dashboard:

            return self.dashboard['battle_plan'].get('sniper_points', {})

        return {}



    def get_checklist(self) -> List[str]:

        """huoqujianchaqingdan"""

        if self.dashboard and 'battle_plan' in self.dashboard:

            return self.dashboard['battle_plan'].get('action_checklist', [])

        return []



    def get_risk_alerts(self) -> List[str]:

        """huoqufengxianjingbao"""

        if self.dashboard and 'intelligence' in self.dashboard:

            return self.dashboard['intelligence'].get('risk_alerts', [])

        return []



    def get_emoji(self) -> str:

        """투자 의견에 맞는 아이콘을 반환합니다."""

        _, emoji, _ = get_signal_level(

            self.operation_advice,

            self.sentiment_score,

            self.report_language,

        )

        return emoji



    def get_confidence_stars(self) -> str:

        """신뢰도 등급을 별 표시로 반환합니다."""

        star_map = {

            "gao": "★★★",

            "high": "★★★",

            "zhong": "★★",

            "medium": "★★",

            "di": "★",

            "low": "★",

        }

        return star_map.get(str(self.confidence_level or "").strip().lower(), "★★")





class GeminiAnalyzer:

    """

    Gemini AI analysisqi



    zhize竊?
    1. diaoyong Google Gemini API jinxingstockanalysis

    2. jieheyuxiansousuodexinwenhejishumianshujushengchenganalysisbaogao

    3. jiexi AI fanhuide JSON geshijieguo



    shiyongfangshi竊?
        analyzer = GeminiAnalyzer()

        result = analyzer.analyze(context, news_context)

    """



    # ========================================

    # xitongtishici - jueceyibiaopan v2.0

    # ========================================

    # shuchugeshishengji竊쉉ongjiandanxinhaoshengjiweijueceyibiaopan

    # hexinmokuai竊쉎exinjielun + shujutoushi + yuqingqingbao + zuozhanjihua

    # ========================================



    LEGACY_DEFAULT_SYSTEM_PROMPT = """당신은 {market_placeholder} 주식 분석 전문가입니다.

{guidelines_placeholder}

""" + CORE_TRADING_SKILL_POLICY_ZH + """

반드시 JSON만 출력하세요. 사용자에게 보이는 문구는 한국어로 작성합니다.

필수 최상위 필드:
- stock_name
- sentiment_score: 0부터 100 사이의 정수
- trend_prediction: 강한 강세 / 강세 / 횡보 / 약세 / 강한 약세
- operation_advice: 강력 매수 / 매수 / 보유 / 관망 / 비중 축소 / 매도 / 강력 매도
- decision_type: buy / hold / sell
- confidence_level: 높음 / 보통 / 낮음
- dashboard: core_conclusion, data_perspective, intelligence, battle_plan, checklist 포함

가격, 거래량, 자금 흐름, 뉴스, 리스크를 함께 판단하고 단일 지표만으로 매수/매도 결론을 내리지 마세요.
투자 조언이 아니라 참고용 분석임을 전제로 보수적으로 작성하세요.
"""

    SYSTEM_PROMPT = """당신은 {market_placeholder} 주식 분석 전문가입니다.

{guidelines_placeholder}

{default_skill_policy_section}

{skills_section}

반드시 JSON만 출력하세요. 사용자에게 보이는 문구는 한국어로 작성합니다.

필수 최상위 필드:
- stock_name
- sentiment_score: 0부터 100 사이의 정수
- trend_prediction: 강한 강세 / 강세 / 횡보 / 약세 / 강한 약세
- operation_advice: 강력 매수 / 매수 / 보유 / 관망 / 비중 축소 / 매도 / 강력 매도
- decision_type: buy / hold / sell
- confidence_level: 높음 / 보통 / 낮음
- dashboard: core_conclusion, data_perspective, intelligence, battle_plan, checklist 포함

가격, 거래량, 자금 흐름, 뉴스, 리스크를 함께 판단하고 단일 지표만으로 매수/매도 결론을 내리지 마세요.
투자 조언이 아니라 참고용 분석임을 전제로 보수적으로 작성하세요.
"""



    TEXT_SYSTEM_PROMPT = """nishiyiweizhuanyedestockanalysiszhushou??


- huidabixujiyuyonghutigongdeshujuyushangxiawen

- ruoxinxibuzu竊똹aomingquezhichubuquedingxing

- buyaobianzaojiage?갷aibaohuoxinwenshishi

"""



    def __init__(

        self,

        api_key: Optional[str] = None,

        *,

        config: Optional[Config] = None,

        skills: Optional[List[str]] = None,

        skill_instructions: Optional[str] = None,

        default_skill_policy: Optional[str] = None,

        use_legacy_default_prompt: Optional[bool] = None,

    ):

        """Initialize LLM Analyzer via LiteLLM.



        Args:

            api_key: Ignored (kept for backward compatibility). Keys are loaded from config.

        """

        self._config_override = config

        self._requested_skills = list(skills) if skills is not None else None

        self._skill_instructions_override = skill_instructions

        self._default_skill_policy_override = default_skill_policy

        self._use_legacy_default_prompt_override = use_legacy_default_prompt

        self._resolved_prompt_state: Optional[Dict[str, Any]] = None

        self._router = None

        self._legacy_router_model_list: List[Dict[str, Any]] = []

        self._litellm_available = False

        self._init_litellm()

        if not self._litellm_available:

            logger.warning("No LLM configured (LITELLM_MODEL / API keys), AI analysis will be unavailable")



    def _get_runtime_config(self) -> Config:

        """Return the runtime config, honoring injected overrides for tests/pipeline."""

        return getattr(self, "_config_override", None) or get_config()



    def _get_skill_prompt_sections(self) -> tuple[str, str, bool]:

        """Resolve skill instructions + default baseline + prompt mode."""

        skill_instructions = getattr(self, "_skill_instructions_override", None)

        default_skill_policy = getattr(self, "_default_skill_policy_override", None)

        use_legacy_default_prompt = getattr(self, "_use_legacy_default_prompt_override", None)



        if skill_instructions is not None and default_skill_policy is not None:

            return (

                skill_instructions,

                default_skill_policy,

                bool(use_legacy_default_prompt) if use_legacy_default_prompt is not None else False,

            )



        resolved_state = getattr(self, "_resolved_prompt_state", None)

        if resolved_state is None:

            from src.agent.factory import resolve_skill_prompt_state



            prompt_state = resolve_skill_prompt_state(

                self._get_runtime_config(),

                skills=getattr(self, "_requested_skills", None),

            )

            resolved_state = {

                "skill_instructions": prompt_state.skill_instructions,

                "default_skill_policy": prompt_state.default_skill_policy,

                "use_legacy_default_prompt": bool(getattr(prompt_state, "use_legacy_default_prompt", False)),

            }

            self._resolved_prompt_state = resolved_state



        return (

            skill_instructions if skill_instructions is not None else resolved_state.get("skill_instructions", ""),

            default_skill_policy if default_skill_policy is not None else resolved_state.get("default_skill_policy", ""),

            (

                use_legacy_default_prompt

                if use_legacy_default_prompt is not None

                else bool(resolved_state.get("use_legacy_default_prompt", False))

            ),

        )



    def _get_analysis_system_prompt(self, report_language: str, stock_code: str = "") -> str:

        """Build the analyzer system prompt with output-language guidance."""

        lang = normalize_report_language(report_language)

        market_role = get_market_role(stock_code, lang)

        market_guidelines = get_market_guidelines(stock_code, lang)

        skill_instructions, default_skill_policy, use_legacy_default_prompt = self._get_skill_prompt_sections()

        if use_legacy_default_prompt:

            base_prompt = self.LEGACY_DEFAULT_SYSTEM_PROMPT.replace(

                "{market_placeholder}", market_role

            ).replace(

                "{guidelines_placeholder}", market_guidelines

            )

        else:

            skills_section = ""

            if skill_instructions:

                skills_section = f"## jihuodejiaoyijineng\n\n{skill_instructions}\n"

            default_skill_policy_section = ""

            if default_skill_policy:

                default_skill_policy_section = f"{default_skill_policy}\n"

            base_prompt = (

                self.SYSTEM_PROMPT.replace("{market_placeholder}", market_role)

                .replace("{guidelines_placeholder}", market_guidelines)

                .replace("{default_skill_policy_section}", default_skill_policy_section)

                .replace("{skills_section}", skills_section)

            )

        if lang == "en":

            return base_prompt + """



## Output Language (highest priority)



- Keep all JSON keys unchanged.

- `decision_type` must remain `buy|hold|sell`.

- All human-readable JSON values must be written in English.

- Use the common English company name when you are confident; otherwise keep the original listed company name instead of inventing one.

- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, nested dashboard text, checklist items, and all narrative summaries.

"""

        return base_prompt + """



## shuchuyuyan竊늷uigaoyouxianji竊?


- suoyou JSON jianmingbaochibubian??
- `decision_type` bixubaochiwei `buy|hold|sell`??
- suoyoumianxiangyonghuderenleikeduwenbenzhibixushiyongzhongwen??
"""



    def _has_channel_config(self, config: Config) -> bool:

        """Check if multi-channel config (channels / YAML / legacy model_list) is active."""

        return bool(config.llm_model_list) and not all(

            e.get('model_name', '').startswith('__legacy_') for e in config.llm_model_list

        )



    @staticmethod

    def _legacy_router_provider_alias(model: str) -> str:

        provider = model.split("/", 1)[0] if "/" in model else "openai"

        return f"__legacy_{provider}__"



    @staticmethod

    def _build_legacy_router_model_list_from_config(

        model: str,

        model_list: List[Dict[str, Any]],

    ) -> List[Dict[str, Any]]:

        """Build legacy-router candidates from configured legacy llm_model_list entries."""

        if not model:

            return []

        target_model = model

        target_legacy_alias = GeminiAnalyzer._legacy_router_provider_alias(model)

        legacy_entries: List[Dict[str, Any]] = []

        for entry in model_list or []:

            if not isinstance(entry, dict):

                continue

            model_name = str(entry.get("model_name") or "").strip()

            if model_name != target_legacy_alias:

                continue



            params = entry.get("litellm_params")

            if not isinstance(params, dict):

                continue



            api_key = str(params.get("api_key") or "").strip()

            if not api_key or len(api_key) < 8:

                continue



            deployed_params = dict(params)

            deployed_params["model"] = target_model

            deployed_params["api_key"] = api_key

            legacy_entries.append({

                "model_name": target_model,

                "litellm_params": deployed_params,

            })



        return legacy_entries



    def _init_litellm(self) -> None:

        """Initialize litellm Router from channels / YAML / legacy keys."""

        config = self._get_runtime_config()

        if litellm is None:
            logger.warning("Analyzer LLM: litellm package is not installed")
            return

        litellm_model = config.litellm_model

        if not litellm_model:

            logger.warning("Analyzer LLM: LITELLM_MODEL not configured")

            return



        self._litellm_available = True



        # --- Channel / YAML path: build Router from pre-built model_list ---

        if self._has_channel_config(config):

            model_list = config.llm_model_list

            try:

                self._router = Router(

                    model_list=model_list,

                    routing_strategy="simple-shuffle",

                    num_retries=2,

                )

            except TypeError:

                logger.debug("Analyzer LLM: Router constructor signature not compatible; fallback to direct mode")

                self._router = None

            else:

                unique_models = list(dict.fromkeys(

                    e['litellm_params']['model'] for e in model_list

                ))

                logger.info(

                    f"Analyzer LLM: Router initialized from channels/YAML ??"

                    f"{len(model_list)} deployment(s), models: {unique_models}"

                )

                return



        # --- Legacy path: build Router for multi-key, or use single key ---

        keys = get_api_keys_for_model(litellm_model, config)

        legacy_model_list = self._build_legacy_router_model_list_from_config(

            litellm_model,

            config.llm_model_list,

        )

        if len(legacy_model_list) <= 1 and keys:

            extra_params = extra_litellm_params(litellm_model, config)

            configured_model_list = [

                {

                    "model_name": litellm_model,

                    "litellm_params": {

                        "model": litellm_model,

                        "api_key": k,

                        **extra_params,

                    },

                }

                for k in keys

            ]

            if not legacy_model_list:

                legacy_model_list = configured_model_list

            elif len(legacy_model_list) < len(configured_model_list):

                legacy_model_list = configured_model_list



        if len(legacy_model_list) > 1:

            self._legacy_router_model_list = legacy_model_list

            try:

                self._router = Router(

                    model_list=legacy_model_list,

                    routing_strategy="simple-shuffle",

                    num_retries=2,

                )

            except TypeError:

                logger.debug("Analyzer LLM: Legacy Router constructor signature not compatible; using legacy model_list fallback")

                self._router = None

            else:

                logger.info(

                    f"Analyzer LLM: Legacy Router initialized with {len(legacy_model_list)} keys "

                    f"for {litellm_model}"

                )

                return



        if keys:

            logger.info(f"Analyzer LLM: litellm initialized (model={litellm_model})")

        else:

            logger.info(

                f"Analyzer LLM: litellm initialized (model={litellm_model}, "

                f"API key from environment)"

            )



    def is_available(self) -> bool:

        """Check if LiteLLM is properly configured with at least one API key."""

        return self._router is not None or self._litellm_available



    def _dispatch_litellm_completion(

        self,

        model: str,

        call_kwargs: Dict[str, Any],

        *,

        config: Config,

        use_channel_router: bool,

        router_model_names: set[str],

    ) -> Any:

        """Dispatch a LiteLLM completion through router or direct fallback."""

        effective_kwargs = dict(call_kwargs)

        if use_channel_router and self._router and model in router_model_names:

            return self._router.completion(**effective_kwargs)

        if self._router and model == config.litellm_model and not use_channel_router:

            return self._router.completion(**effective_kwargs)



        keys = get_api_keys_for_model(model, config)

        if keys:

            effective_kwargs["api_key"] = keys[0]

        effective_kwargs.update(extra_litellm_params(model, config))

        return litellm.completion(**effective_kwargs)



    def _normalize_usage(self, usage_obj: Any) -> Dict[str, Any]:

        """Normalize usage objects from LiteLLM responses/chunks."""

        if not usage_obj:

            return {}



        def _get_value(key: str) -> int:

            if isinstance(usage_obj, dict):

                return int(usage_obj.get(key) or 0)

            return int(getattr(usage_obj, key, 0) or 0)



        return {

            "prompt_tokens": _get_value("prompt_tokens"),

            "completion_tokens": _get_value("completion_tokens"),

            "total_tokens": _get_value("total_tokens"),

        }



    @staticmethod

    def _get_response_field(obj: Any, key: str) -> Any:

        """Read a field from dict-like or object-like LiteLLM payloads."""

        if isinstance(obj, dict):

            return obj.get(key)

        return getattr(obj, key, None)



    def _extract_text_blocks(self, blocks: Any) -> str:

        """Extract text from OpenAI-compatible content block lists."""

        if not blocks:

            return ""



        parts: List[str] = []

        for block in blocks:

            if isinstance(block, str):

                parts.append(block)

                continue



            text = None

            if isinstance(block, dict):

                text = block.get("text")

                if text is None:

                    text = block.get("content")

            else:

                text = getattr(block, "text", None)

                if text is None:

                    text = getattr(block, "content", None)



            if isinstance(text, str) and text:

                parts.append(text)



        return "".join(parts).strip()



    def _extract_completion_text(self, response: Any) -> str:

        """Extract text from non-stream LiteLLM completion responses."""

        choices = self._get_response_field(response, "choices")

        if not choices:

            return ""



        choice = choices[0]

        message = self._get_response_field(choice, "message")



        content_blocks = self._get_response_field(choice, "content_blocks")

        if content_blocks is None and message is not None:

            content_blocks = self._get_response_field(message, "content_blocks")

        block_text = self._extract_text_blocks(content_blocks)

        if block_text:

            return block_text



        content = None

        if message is not None:

            content = self._get_response_field(message, "content")

        if content is None:

            content = self._get_response_field(choice, "content")



        if isinstance(content, list):

            return self._extract_text_blocks(content)

        if isinstance(content, str):

            return content.strip()

        return str(content).strip() if content is not None else ""



    def _extract_stream_text(self, chunk: Any) -> str:

        """Extract provider-agnostic text delta from a LiteLLM streaming chunk."""

        choices = chunk.get("choices") if isinstance(chunk, dict) else getattr(chunk, "choices", None)

        if not choices:

            return ""



        choice = choices[0]

        delta = choice.get("delta") if isinstance(choice, dict) else getattr(choice, "delta", None)

        message = choice.get("message") if isinstance(choice, dict) else getattr(choice, "message", None)



        content: Any = None

        if isinstance(delta, dict):

            content = delta.get("content")

        elif isinstance(delta, str):

            content = delta

        elif delta is not None:

            content = getattr(delta, "content", None)



        if content is None:

            if isinstance(message, dict):

                content = message.get("content")

            elif message is not None:

                content = getattr(message, "content", None)



        if isinstance(content, list):

            parts: List[str] = []

            for item in content:

                if isinstance(item, str):

                    parts.append(item)

                elif isinstance(item, dict):

                    text = item.get("text")

                    if isinstance(text, str):

                        parts.append(text)

            return "".join(parts)



        return content if isinstance(content, str) else ""



    def _consume_litellm_stream(

        self,

        stream_response: Any,

        *,

        model: str,

        progress_callback: Optional[Callable[[int], None]] = None,

    ) -> Tuple[str, Dict[str, Any]]:

        """Consume a LiteLLM stream into a single text payload."""

        chunks: List[str] = []

        usage: Dict[str, Any] = {}

        chars_received = 0

        next_emit_at = 1



        try:

            for chunk in stream_response:

                chunk_usage = chunk.get("usage") if isinstance(chunk, dict) else getattr(chunk, "usage", None)

                normalized_usage = self._normalize_usage(chunk_usage)

                if normalized_usage:

                    usage = normalized_usage



                delta_text = self._extract_stream_text(chunk)

                if not delta_text:

                    continue



                chunks.append(delta_text)

                chars_received += len(delta_text)

                if progress_callback and chars_received >= next_emit_at:

                    progress_callback(chars_received)

                    next_emit_at = chars_received + 160

        except Exception as exc:

            raise _LiteLLMStreamError(

                f"{model} stream interrupted: {exc}",

                partial_received=chars_received > 0,

            ) from exc



        response_text = "".join(chunks).strip()

        if not response_text:

            raise _LiteLLMStreamError(

                f"{model} stream returned empty response",

                partial_received=False,

            )



        if progress_callback and chars_received > 0:

            progress_callback(chars_received)



        return response_text, usage



    def _call_litellm(

        self,

        prompt: str,

        generation_config: dict,

        *,

        system_prompt: Optional[str] = None,

        stream: bool = False,

        stream_progress_callback: Optional[Callable[[int], None]] = None,

        response_validator: Optional[Callable[[str], None]] = None,

    ) -> Tuple[str, str, Dict[str, Any]]:

        """Call LLM via litellm with fallback across configured models.



        When channels/YAML are configured, every model goes through the Router

        (which handles per-model key selection, load balancing, and retries).

        In legacy mode, the primary model may use the Router while fallback

        models fall back to direct litellm.completion().



        Args:

            prompt: User prompt text.

            generation_config: Dict with optional keys: temperature, max_output_tokens, max_tokens.

            response_validator: Optional callable that accepts the raw response text and raises

                an exception if the response is unacceptable (e.g. not valid JSON).  When it

                raises, the current model is treated as failed and the next fallback model is

                tried.  If all models fail validation, :class:`_AllModelsFailedError` is raised

                with ``last_response_text`` set to the last raw response received.



        Returns:

            Tuple of (response text, model_used, usage). On success model_used is the full model

            name and usage is a dict with prompt_tokens, completion_tokens, total_tokens.

        """

        config = self._get_runtime_config()

        max_tokens = (

            generation_config.get('max_output_tokens')

            or generation_config.get('max_tokens')

            or 8192

        )

        requested_temperature = generation_config.get('temperature', 0.7)



        models_to_try = [config.litellm_model] + (config.litellm_fallback_models or [])

        models_to_try = [m for m in models_to_try if m]



        use_channel_router = self._has_channel_config(config)



        last_error = None

        last_response_text: Optional[str] = None

        last_model: Optional[str] = None

        last_usage: Dict[str, Any] = {}

        effective_system_prompt = system_prompt or self.TEXT_SYSTEM_PROMPT

        router_model_names = set(get_configured_llm_models(config.llm_model_list))

        for model in models_to_try:

            recovery_model_list = config.llm_model_list

            legacy_router_model_list = getattr(self, "_legacy_router_model_list", None) or []

            if legacy_router_model_list and model == config.litellm_model and not use_channel_router:

                recovery_model_list = legacy_router_model_list



            try:

                model_short = model.split("/")[-1] if "/" in model else model

                extra = get_thinking_extra_body(model_short)

                call_kwargs: Dict[str, Any] = {

                    "model": model,

                    "messages": [

                        {"role": "system", "content": effective_system_prompt},

                        {"role": "user", "content": prompt},

                    ],

                    "max_tokens": max_tokens,

                }

                if extra:

                    call_kwargs["extra_body"] = extra

                uses_router = (

                    (use_channel_router and self._router and model in router_model_names)

                    or (self._router and model == config.litellm_model and not use_channel_router)

                )

                if not uses_router:

                    try:

                        keys = get_api_keys_for_model(model, config)

                    except AttributeError:

                        keys = []

                    if keys:

                        call_kwargs["api_key"] = keys[0]

                    try:

                        call_kwargs.update(extra_litellm_params(model, config))

                    except AttributeError:

                        pass

                call_kwargs = apply_litellm_generation_params(

                    call_kwargs,

                    model,

                    requested_temperature,

                    model_list=recovery_model_list,

                )



                _stream_text: Optional[str] = None

                _stream_usage: Dict[str, Any] = {}



                if stream:

                    try:

                        stream_response = call_litellm_with_param_recovery(

                            lambda kwargs: self._dispatch_litellm_completion(

                                model,

                                kwargs,

                                config=config,

                                use_channel_router=use_channel_router,

                                router_model_names=router_model_names,

                            ),

                            model=model,

                            call_kwargs={**call_kwargs, "stream": True},

                            model_list=recovery_model_list,

                            cache_recovery=False,

                            logger=logger,

                        )

                        _stream_text, _stream_usage = self._consume_litellm_stream(

                            stream_response,

                            model=model,

                            progress_callback=stream_progress_callback,

                        )

                    except _LiteLLMStreamError as exc:

                        if exc.partial_received:

                            logger.warning(

                                "[LiteLLM] %s stream failed after partial output, retrying non-stream for same model: %s",

                                model,

                                exc,

                            )

                        else:

                            logger.warning(

                                "[LiteLLM] %s stream unavailable before first chunk, falling back to non-stream: %s",

                                model,

                                exc,

                            )

                        last_error = exc

                    except Exception as exc:

                        logger.warning(

                            "[LiteLLM] %s stream request failed before first chunk, falling back to non-stream: %s",

                            model,

                            exc,

                        )



                if _stream_text is not None:

                    last_response_text = _stream_text

                    last_model = model

                    last_usage = _stream_usage

                    if response_validator is not None:

                        response_validator(_stream_text)

                    return _stream_text, model, _stream_usage



                response = call_litellm_with_param_recovery(

                    lambda kwargs: self._dispatch_litellm_completion(

                        model,

                        kwargs,

                        config=config,

                        use_channel_router=use_channel_router,

                        router_model_names=router_model_names,

                    ),

                    model=model,

                    call_kwargs=call_kwargs,

                    model_list=recovery_model_list,

                    logger=logger,

                )



                content = self._extract_completion_text(response)

                if content:

                    usage = self._normalize_usage(self._get_response_field(response, "usage"))

                    last_response_text = content

                    last_model = model

                    last_usage = usage

                    if response_validator is not None:

                        response_validator(content)

                    return (content, model, usage)

                raise ValueError("LLM returned empty response")



            except Exception as e:

                logger.warning(f"[LiteLLM] {model} failed: {e}")

                last_error = e

                continue



        raise _AllModelsFailedError(

            f"All LLM models failed (tried {len(models_to_try)} model(s)). Last error: {last_error}",

            last_response_text=last_response_text,

            last_model=last_model,

            last_usage=last_usage,

        )



    def generate_text(

        self,

        prompt: str,

        max_tokens: int = 2048,

        temperature: float = 0.7,

    ) -> Optional[str]:

        """Public entry point for free-form text generation.



        External callers (e.g. MarketAnalyzer) must use this method instead of

        calling _call_litellm() directly or accessing private attributes such as

        _litellm_available, _router, _model, _use_openai, or _use_anthropic.



        Args:

            prompt:      Text prompt to send to the LLM.

            max_tokens:  Maximum tokens in the response (default 2048).

            temperature: Sampling temperature (default 0.7).



        Returns:

            Response text, or None if the LLM call fails (error is logged).

        """

        try:

            result = self._call_litellm(

                prompt,

                generation_config={"max_tokens": max_tokens, "temperature": temperature},

            )

            if isinstance(result, tuple):

                text, model_used, usage = result

                persist_llm_usage(usage, model_used, call_type="market_review")

                return text

            return result

        except Exception as exc:

            logger.error("[generate_text] LLM call failed: %s", exc)

            return None



    def analyze(

        self, 

        context: Dict[str, Any],

        news_context: Optional[str] = None,

        progress_callback: Optional[Callable[[int, str], None]] = None,

        stream_progress_callback: Optional[Callable[[int], None]] = None,

    ) -> AnalysisResult:

        """

        analysisdanzhistock

        

        liucheng竊?
        1. geshihuashurushuju竊늞ishumian + xinwen竊?
        2. diaoyong Gemini API竊늕airetryhemodelqiehuan竊?
        3. jiexi JSON xiangying

        4. fanhuijiegouhuajieguo

        

        Args:

            context: cong storage.get_analysis_context() huoqudeshangxiawenshuju

            news_context: yuxiansousuodexinwenneirong竊늟exuan竊?
            

        Returns:

            AnalysisResult duixiang

        """

        def _emit_progress(progress: int, message: str) -> None:

            if progress_callback is None:

                return

            try:

                progress_callback(progress, message)

            except Exception as exc:

                logger.debug("[analyzer] progress callback skipped: %s", exc)



        code = context.get('code', 'Unknown')

        config = self._get_runtime_config()

        report_language = normalize_report_language(getattr(config, "report_language", "zh"))

        system_prompt = self._get_analysis_system_prompt(report_language, stock_code=code)

        

        # qingqiuqianzengjiayanshi竊늗angzhilianxuqingqiuchufaxianliu竊?
        request_delay = config.gemini_request_delay

        if request_delay > 0:

            logger.debug(f"[LLM] qingqiuqiandengdai {request_delay:.1f} miao...")

            _emit_progress(65, f"{code}竊숷LM qingqiuqiandengdai {request_delay:.1f} miao")

            time.sleep(request_delay)

        

        # youxiancongshangxiawenhuoqustockmingcheng竊늶ou main.py chuanru竊?
        name = context.get('stock_name')

        if not name or name.startswith('stock'):

            # fallback竊쉉ong realtime zhonghuoqu

            if 'realtime' in context and context['realtime'].get('name'):

                name = context['realtime']['name']

            else:

                # zuihoucongyingshebiaohuoqu

                name = STOCK_NAME_MAP.get(code, f'stock{code}')

        

        # ruguomodelbukeyong竊똣anhuimorenjieguo

        if not self.is_available():

            return AnalysisResult(

                code=code,

                name=name,

                sentiment_score=50,

                trend_prediction='Sideways' if report_language == "en" else '횡보',

                operation_advice='Hold' if report_language == "en" else '보유',

                confidence_level='Low' if report_language == "en" else '낮음',

                analysis_summary='AI analysis is unavailable because no API key is configured.' if report_language == "en" else 'AI 분석 기능을 사용할 수 없습니다. API 키가 설정되지 않았습니다.',

                risk_warning='Configure an LLM API key (GEMINI_API_KEY/ANTHROPIC_API_KEY/OPENAI_API_KEY) and retry.' if report_language == "en" else 'LLM API 키를 설정한 뒤 다시 시도하세요. (GEMINI_API_KEY/ANTHROPIC_API_KEY/OPENAI_API_KEY)',

                success=False,

                error_message='LLM API key is not configured' if report_language == "en" else 'LLM API 키가 설정되지 않았습니다.',

                model_used=None,

                report_language=report_language,

            )

        

        try:

            # geshihuashuru竊늒aohanjishumianshujuhexinwen竊?
            prompt = self._format_prompt(context, name, news_context, report_language=report_language)

            

            config = self._get_runtime_config()

            model_name = config.litellm_model or "unknown"

            logger.info(f"========== AI analysis {name}({code}) ==========")

            logger.info(f"[LLMconfig] model: {model_name}")

            logger.info(f"[LLMconfig] Prompt changdu: {len(prompt)} zifu")

            logger.info(f"[LLMconfig] shifoubaohanxinwen: {'shi' if news_context else 'fou'}")



            # recordwanzheng prompt daorizhi竊뉹NFOjibierecordzhaiyao竊똃EBUGrecordwanzheng竊?
            prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt

            logger.info(f"[LLM Prompt yulan]\n{prompt_preview}")

            logger.debug(f"=== wanzheng Prompt ({len(prompt)}zifu) ===\n{prompt}\n=== End Prompt ===")



            # shezhishengchengconfig

            generation_config = {

                "temperature": config.llm_temperature,

                "max_output_tokens": 8192,

            }



            logger.info(f"[LLMdiaoyong] kaishidiaoyong {model_name}...")

            _emit_progress(68, f"{name}竊숷LM yijieshouqingqiu竊똡engdaixiangying")



            # shiyong litellm diaoyong竊늷hichiwanzhengxingjiaoyanretry竊?
            current_prompt = prompt

            retry_count = 0

            max_retries = config.report_integrity_retry if config.report_integrity_enabled else 0



            while True:

                start_time = time.time()

                try:

                    response_text, model_used, llm_usage = self._call_litellm(

                        current_prompt,

                        generation_config,

                        system_prompt=system_prompt,

                        stream=True,

                        stream_progress_callback=stream_progress_callback,

                        response_validator=self._validate_json_response,

                    )

                except _AllModelsFailedError as exc:

                    if exc.last_response_text is not None:

                        logger.warning(

                            "[LLM JSON] %s(%s): all models returned invalid JSON, using text fallback",

                            name,

                            code,

                        )

                        response_text = exc.last_response_text

                        model_used = exc.last_model

                        llm_usage = exc.last_usage

                    else:

                        raise

                elapsed = time.time() - start_time



                # recordxiangyingxinxi

                logger.info(

                    f"[LLMfanhui] {model_name} xiangyingchenggong, haoshi {elapsed:.2f}s, xiangyingchangdu {len(response_text)} zifu"

                )

                response_preview = response_text[:300] + "..." if len(response_text) > 300 else response_text

                logger.info(f"[LLMfanhui yulan]\n{response_preview}")

                logger.debug(

                    f"=== {model_name} wanzhengxiangying ({len(response_text)}zifu) ===\n{response_text}\n=== End Response ==="

                )

                # Keep parser/retry progress monotonic so task progress/message never "goes backward".

                parse_progress = min(99, 93 + retry_count * 2)

                _emit_progress(parse_progress, f"{name}竊숷LM fanhuiwancheng竊똺hengzaijiexi JSON")



                # jiexixiangying

                result = self._parse_response(response_text, code, name)

                result.raw_response = response_text

                result.search_performed = bool(news_context)

                result.market_snapshot = self._build_market_snapshot(context)

                result.model_used = model_used

                result.report_language = report_language



                # neirongwanzhengxingjiaoyan竊늟exuan竊?
                if not config.report_integrity_enabled:

                    break

                pass_integrity, missing_fields = self._check_content_integrity(result)

                if pass_integrity:

                    break

                if retry_count < max_retries:

                    current_prompt = self._build_integrity_retry_prompt(

                        prompt,

                        response_text,

                        missing_fields,

                        report_language=report_language,

                    )

                    retry_count += 1

                    logger.info(

                        "[LLM integrity] required fields missing %s, retry %d",

                        missing_fields,

                        retry_count,

                    )

                    retry_progress = min(99, 92 + retry_count * 2)

                    _emit_progress(

                        retry_progress,

                        f"{name}: 보고서 필드가 불완전하여 보강 재시도 중 ({retry_count}/{max_retries})",

                    )

                else:

                    self._apply_placeholder_fill(result, missing_fields)

                    logger.warning(

                        "[LLM integrity] required fields missing %s, filled placeholders and continued",

                        missing_fields,

                    )

                    break



            persist_llm_usage(llm_usage, model_used, call_type="analysis", stock_code=code)



            logger.info(f"[LLMjiexi] {name}({code}) analysiswancheng: {result.trend_prediction}, pingfen {result.sentiment_score}")



            return result

            

        except Exception as e:

            logger.error(f"AI analysis {name}({code}) shibai: {e}")

            return AnalysisResult(

                code=code,

                name=name,

                sentiment_score=50,

                trend_prediction='Sideways' if report_language == "en" else 'zhendang',

                operation_advice='Hold' if report_language == "en" else 'chiyou',

                confidence_level='Low' if report_language == "en" else 'di',

                analysis_summary=(f'Analysis failed: {str(e)[:100]}' if report_language == "en" else f'analysisguochengchucuo: {str(e)[:100]}'),

                risk_warning='Analysis failed. Please retry later or review manually.' if report_language == "en" else 'analysisshibai竊똰inglaterretryhuoshoudonganalysis',

                success=False,

                error_message=str(e),

                model_used=None,

                report_language=report_language,

            )

    

    def _format_prompt(
        self,
        context: Dict[str, Any],
        name: str,
        news_context: Optional[str] = None,
        report_language: str = "ko",
    ) -> str:
        """분석 입력 데이터를 한국어 LLM 프롬프트로 구성합니다."""
        code = context.get("code", "Unknown")
        report_language = normalize_report_language(report_language)
        _, _, use_legacy_default_prompt = self._get_skill_prompt_sections()

        stock_name = context.get("stock_name", name)
        if not stock_name or stock_name == f"stock{code}":
            stock_name = STOCK_NAME_MAP.get(code, f"stock{code}")

        today = context.get("today", {}) or {}
        unknown_text = get_unknown_text(report_language)
        no_data_text = get_no_data_text(report_language)

        prompt_parts = [
            "# 주식 분석 요청",
            "",
            "## 기본 정보",
            f"- 종목 코드: {code}",
            f"- 종목명: {stock_name}",
            f"- 분석일: {context.get('date', unknown_text)}",
            "",
            "## 당일 시세",
            f"- 종가: {today.get('close', 'N/A')}",
            f"- 시가: {today.get('open', 'N/A')}",
            f"- 고가: {today.get('high', 'N/A')}",
            f"- 저가: {today.get('low', 'N/A')}",
            f"- 등락률: {today.get('pct_chg', 'N/A')}%",
            f"- 거래량: {self._format_volume(today.get('volume'))}",
            f"- 거래대금: {self._format_amount(today.get('amount'))}",
            "",
            "## 이동평균과 기술 지표",
            f"- MA5: {today.get('ma5', 'N/A')}",
            f"- MA10: {today.get('ma10', 'N/A')}",
            f"- MA20: {today.get('ma20', 'N/A')}",
            f"- 이동평균 상태: {context.get('ma_status', unknown_text)}",
            f"- RSI: {today.get('rsi', 'N/A')}",
            f"- MACD: {today.get('macd', 'N/A')}",
        ]

        realtime = context.get("realtime") or {}
        if isinstance(realtime, dict) and realtime:
            prompt_parts.extend([
                "",
                "## 실시간 보강 데이터",
                f"- 현재가: {realtime.get('price', 'N/A')}",
                f"- 거래량 비율: {realtime.get('volume_ratio', 'N/A')}",
                f"- 회전율: {realtime.get('turnover_rate', 'N/A')}%",
                f"- 동적 PER: {realtime.get('pe_ratio', 'N/A')}",
                f"- PBR: {realtime.get('pb_ratio', 'N/A')}",
                f"- 총시가총액: {self._format_amount(realtime.get('total_mv'))}",
                f"- 유통시가총액: {self._format_amount(realtime.get('circ_mv'))}",
                f"- 60일 등락률: {realtime.get('change_60d', 'N/A')}%",
            ])

        chip_context = context.get("chip_context") or context.get("chip_distribution")
        if chip_context:
            prompt_parts.extend(["", "## 수급/칩 분포 데이터", str(chip_context)])

        if news_context:
            prompt_parts.extend([
                "",
                "## 최신 뉴스와 공시",
                news_context,
                "",
                "뉴스는 날짜가 명확하고 최근성 있는 항목만 반영하세요.",
            ])
        else:
            prompt_parts.extend(["", "## 최신 뉴스와 공시", no_data_text])

        market_snapshot = self._build_market_snapshot(context)
        if market_snapshot:
            prompt_parts.extend(["", "## 시장 환경", json.dumps(market_snapshot, ensure_ascii=False, default=str)])

        prompt_parts.extend([
            "",
            "## 분석 지침",
            "- 가격, 거래량, 추세, 수급, 뉴스, 리스크를 함께 판단하세요.",
            "- 단일 지표만으로 매수 또는 매도 결론을 내리지 마세요.",
            "- 불확실한 데이터는 추정하지 말고 보수적으로 표시하세요.",
            "- 사용자에게 보이는 모든 문구는 한국어로 작성하세요.",
            "- 반드시 JSON만 출력하세요.",
            "",
            "필수 필드: stock_name, sentiment_score, trend_prediction, operation_advice, decision_type, confidence_level, dashboard",
        ])

        prompt_body = "\n".join(prompt_parts)
        market_placeholder = get_market_placeholder(report_language)
        guidelines_placeholder = get_guidelines_placeholder(report_language)
        default_skill_policy_section, skills_section, _ = self._get_skill_prompt_sections()

        system_prompt = self.LEGACY_DEFAULT_SYSTEM_PROMPT if use_legacy_default_prompt else self.SYSTEM_PROMPT
        try:
            system_prompt = system_prompt.format(
                market_placeholder=market_placeholder,
                guidelines_placeholder=guidelines_placeholder,
                default_skill_policy_section=default_skill_policy_section,
                skills_section=skills_section,
            )
        except Exception:
            system_prompt = "당신은 한국어로 답하는 주식 분석 전문가입니다. 반드시 JSON만 출력하세요."

        return f"{system_prompt}\n\n{prompt_body}"
    def _format_volume(self, volume: Optional[float]) -> str:

        """geshihuachengjiaoliangxianshi"""

        if volume is None:

            return 'N/A'

        if volume >= 1e8:

            return f"{volume / 1e8:.2f} yigu"

        elif volume >= 1e4:

            return f"{volume / 1e4:.2f} wangu"

        else:

            return f"{volume:.0f} gu"

    

    def _format_amount(self, amount: Optional[float]) -> str:

        """geshihuachengjiaoexianshi"""

        if amount is None:

            return 'N/A'

        if amount >= 1e8:

            return f"{amount / 1e8:.2f} yiyuan"

        elif amount >= 1e4:

            return f"{amount / 1e4:.2f} wanyuan"

        else:

            return f"{amount:.0f} yuan"



    def _format_percent(self, value: Optional[float]) -> str:

        """geshihuabaifenbixianshi"""

        if value is None:

            return 'N/A'

        try:

            return f"{float(value):.2f}%"

        except (TypeError, ValueError):

            return 'N/A'



    def _format_price(self, value: Optional[float]) -> str:

        """geshihuajiagexianshi"""

        if value is None:

            return 'N/A'

        try:

            return f"{float(value):.2f}"

        except (TypeError, ValueError):

            return 'N/A'



    def _build_market_snapshot(self, context: Dict[str, Any]) -> Dict[str, Any]:

        """당일 시세 요약 정보를 구성합니다."""

        today = context.get('today', {}) or {}

        realtime = context.get('realtime', {}) or {}

        yesterday = context.get('yesterday', {}) or {}



        prev_close = yesterday.get('close')

        close = today.get('close')

        high = today.get('high')

        low = today.get('low')



        amplitude = None

        change_amount = None

        if prev_close not in (None, 0) and high is not None and low is not None:

            try:

                amplitude = (float(high) - float(low)) / float(prev_close) * 100

            except (TypeError, ValueError, ZeroDivisionError):

                amplitude = None

        if prev_close is not None and close is not None:

            try:

                change_amount = float(close) - float(prev_close)

            except (TypeError, ValueError):

                change_amount = None



        snapshot = {

            "date": context.get('date', 'weizhi'),

            "close": self._format_price(close),

            "open": self._format_price(today.get('open')),

            "high": self._format_price(high),

            "low": self._format_price(low),

            "prev_close": self._format_price(prev_close),

            "pct_chg": self._format_percent(today.get('pct_chg')),

            "change_amount": self._format_price(change_amount),

            "amplitude": self._format_percent(amplitude),

            "volume": self._format_volume(today.get('volume')),

            "amount": self._format_amount(today.get('amount')),

        }



        if realtime:

            snapshot.update({

                "price": self._format_price(realtime.get('price')),

                "volume_ratio": realtime.get('volume_ratio', 'N/A'),

                "turnover_rate": self._format_percent(realtime.get('turnover_rate')),

                "source": getattr(realtime.get('source'), 'value', realtime.get('source', 'N/A')),

            })



        return snapshot



    def _check_content_integrity(self, result: AnalysisResult) -> Tuple[bool, List[str]]:

        """Delegate to module-level check_content_integrity."""

        return check_content_integrity(result)



    def _build_integrity_complement_prompt(self, missing_fields: List[str], report_language: str = "zh") -> str:

        """Build complement instruction for missing mandatory fields."""

        report_language = normalize_report_language(report_language)

        if report_language == "en":

            lines = ["### Completion requirements: fill the missing mandatory fields below and output the full JSON again:"]

            for f in missing_fields:

                if f == "sentiment_score":

                    lines.append("- sentiment_score: integer score from 0 to 100")

                elif f == "operation_advice":

                    lines.append("- operation_advice: localized action advice")

                elif f == "analysis_summary":

                    lines.append("- analysis_summary: concise analysis summary")

                elif f == "dashboard.core_conclusion.one_sentence":

                    lines.append("- dashboard.core_conclusion.one_sentence: one-line decision")

                elif f == "dashboard.intelligence.risk_alerts":

                    lines.append("- dashboard.intelligence.risk_alerts: risk alert list (can be empty)")

                elif f == "dashboard.battle_plan.sniper_points.stop_loss":

                    lines.append("- dashboard.battle_plan.sniper_points.stop_loss: stop-loss level")

            return "\n".join(lines)



        lines = ["### 보강 요청: 아래 누락 필드를 채워 전체 JSON을 다시 출력하세요."]

        for f in missing_fields:

            if f == "sentiment_score":

                lines.append("- sentiment_score: 0부터 100 사이의 종합 점수")

            elif f == "operation_advice":

                lines.append("- operation_advice: 매수/비중 확대/보유/비중 축소/매도/관망 중 하나")

            elif f == "analysis_summary":

                lines.append("- analysis_summary: 종합 분석 요약")

            elif f == "dashboard.core_conclusion.one_sentence":

                lines.append("- dashboard.core_conclusion.one_sentence: 한 문장 핵심 결론")

            elif f == "dashboard.intelligence.risk_alerts":

                lines.append("- dashboard.intelligence.risk_alerts: 리스크 경고 목록, 없으면 빈 배열")

            elif f == "dashboard.battle_plan.sniper_points.stop_loss":

                lines.append("- dashboard.battle_plan.sniper_points.stop_loss: 손절 기준")

        return "\n".join(lines)



    def _build_integrity_retry_prompt(

        self,

        base_prompt: str,

        previous_response: str,

        missing_fields: List[str],

        report_language: str = "zh",

    ) -> str:

        """Build retry prompt using the previous response as the complement baseline."""

        complement = self._build_integrity_complement_prompt(missing_fields, report_language=report_language)

        previous_output = previous_response.strip()

        if normalize_report_language(report_language) == "en":

            prefix = "### The previous output is below. Complete the missing fields based on that output and return the full JSON again. Do not omit existing fields:"

        else:

            prefix = "### 이전 출력은 아래와 같습니다. 누락 필드를 보강하고 기존 필드를 생략하지 않은 전체 JSON을 다시 출력하세요."

        return "\n\n".join([

            base_prompt,

            prefix,

            previous_output,

            complement,

        ])



    def _apply_placeholder_fill(self, result: AnalysisResult, missing_fields: List[str]) -> None:

        """Delegate to module-level apply_placeholder_fill."""

        apply_placeholder_fill(result, missing_fields)



    def _parse_response(

        self, 

        response_text: str, 

        code: str, 

        name: str

    ) -> AnalysisResult:

        """

        jiexi Gemini xiangying竊늞ueceyibiaopanban竊?
        

        changshicongxiangyingzhongtiqu JSON geshideanalysisjieguo竊똟aohan dashboard ziduan

        ruguojiexishibai竊똠hangshizhinengtiquhuofanhuimorenjieguo

        """

        try:

            report_language = normalize_report_language(

                getattr(self._get_runtime_config(), "report_language", "zh")

            )

            # qinglixiangyingwenben竊쉤ichu markdown daimakuaibiaoji

            cleaned_text = response_text

            if '```json' in cleaned_text:

                cleaned_text = cleaned_text.replace('```json', '').replace('```', '')

            elif '```' in cleaned_text:

                cleaned_text = cleaned_text.replace('```', '')

            

            # changshizhaodao JSON neirong

            json_start = cleaned_text.find('{')

            json_end = cleaned_text.rfind('}') + 1

            

            if json_start >= 0 and json_end > json_start:

                json_str = cleaned_text[json_start:json_end]

                

                # changshixiufuchangjiande JSON wenti

                json_str = self._fix_json_string(json_str)

                

                data = json.loads(json_str)



                # Schema validation (lenient: on failure, continue with raw dict)

                try:

                    AnalysisReportSchema.model_validate(data)

                except Exception as e:

                    logger.warning(

                        "LLM report schema validation failed, continuing with raw dict: %s",

                        str(e)[:100],

                    )



                # tiqu dashboard shuju

                dashboard = data.get('dashboard', None)



                # youxianshiyong AI fanhuidestockmingcheng竊늭uguoyuanmingchengwuxiaohuobaohandaima竊?
                ai_stock_name = data.get('stock_name')

                if ai_stock_name and (name.startswith('stock') or name == code or 'Unknown' in name):

                    name = ai_stock_name



                # jiexisuoyouziduan竊똲hiyongmorenzhifangzhiqueshi

                # jiexi decision_type竊똱uguomeiyouzegenju operation_advice tuiduan

                decision_type = data.get('decision_type', '')

                if not decision_type:

                    op = data.get('operation_advice', 'Hold' if report_language == "en" else 'chiyou')

                    decision_type = infer_decision_type_from_advice(op, default='hold')

                

                return AnalysisResult(

                    code=code,

                    name=name,

                    # hexinzhibiao

                    sentiment_score=int(data.get('sentiment_score', 50)),

                    trend_prediction=data.get('trend_prediction', 'Sideways' if report_language == "en" else 'zhendang'),

                    operation_advice=data.get('operation_advice', 'Hold' if report_language == "en" else 'chiyou'),

                    decision_type=decision_type,

                    confidence_level=localize_confidence_level(

                        data.get('confidence_level', 'Medium' if report_language == "en" else 'zhong'),

                        report_language,

                    ),

                    report_language=report_language,

                    # jueceyibiaopan

                    dashboard=dashboard,

                    # zoushianalysis

                    trend_analysis=data.get('trend_analysis', ''),

                    short_term_outlook=data.get('short_term_outlook', ''),

                    medium_term_outlook=data.get('medium_term_outlook', ''),

                    # jishumian

                    technical_analysis=data.get('technical_analysis', ''),

                    ma_analysis=data.get('ma_analysis', ''),

                    volume_analysis=data.get('volume_analysis', ''),

                    pattern_analysis=data.get('pattern_analysis', ''),

                    # jibenmian

                    fundamental_analysis=data.get('fundamental_analysis', ''),

                    sector_position=data.get('sector_position', ''),

                    company_highlights=data.get('company_highlights', ''),

                    # qingxumian/xiaoximian

                    news_summary=data.get('news_summary', ''),

                    market_sentiment=data.get('market_sentiment', ''),

                    hot_topics=data.get('hot_topics', ''),

                    # zonghe

                    analysis_summary=data.get('analysis_summary', 'Analysis completed' if report_language == "en" else 'analysiswancheng'),

                    key_points=data.get('key_points', ''),

                    risk_warning=data.get('risk_warning', ''),

                    buy_reason=data.get('buy_reason', ''),

                    # yuanshuju

                    search_performed=data.get('search_performed', False),

                    data_sources=data.get('data_sources', 'Technical data' if report_language == "en" else 'jishumianshuju'),

                    success=True,

                )

            else:

                # meiyouzhaodao JSON竊똟iaojiweishibai

                logger.warning(f"wufacongxiangyingzhongtiqu JSON竊똟iaojiweijiexishibai")

                return self._parse_text_response(response_text, code, name)

                

        except json.JSONDecodeError as e:

            logger.warning(f"JSON jiexishibai: {e}竊똟iaojiweijiexishibai")

            return self._parse_text_response(response_text, code, name)

    

    def _fix_json_string(self, json_str: str) -> str:

        """xiufuchangjiande JSON geshiwenti"""

        import re

        

        # yichuzhushi

        json_str = re.sub(r'//.*?\n', '\n', json_str)

        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

        

        # xiufuweisuidouhao

        json_str = re.sub(r',\s*}', '}', json_str)

        json_str = re.sub(r',\s*]', ']', json_str)

        

        # quebaobuerzhishixiaoxie

        json_str = json_str.replace('True', 'true').replace('False', 'false')

        

        # fix by json-repair

        json_str = repair_json(json_str)

        

        return json_str



    def _validate_json_response(self, text: str) -> None:

        """Validate that *text* contains a parseable JSON object.



        Used as the ``response_validator`` argument to :meth:`_call_litellm` so

        that a JSON-less or unparseable reply from the primary model is treated

        as a model failure and triggers fallback to the next configured model.



        Raises:

            ValueError: if no JSON object is found in *text*.

            json.JSONDecodeError: if the extracted JSON cannot be parsed (after

                :meth:`_fix_json_string` attempts repair).

        """

        cleaned = text

        if "```json" in cleaned:

            cleaned = cleaned.replace("```json", "").replace("```", "")

        elif "```" in cleaned:

            cleaned = cleaned.replace("```", "")



        json_start = cleaned.find("{")

        json_end = cleaned.rfind("}") + 1



        if json_start < 0 or json_end <= json_start:

            raise ValueError("No JSON object found in LLM response")



        json_str = cleaned[json_start:json_end]

        json_str = self._fix_json_string(json_str)

        json.loads(json_str)

    

    def _parse_text_response(self, response_text: str, code: str, name: str) -> AnalysisResult:
        """JSON 파싱 실패 시 텍스트 응답에서 최소 분석 결과를 구성합니다."""
        report_language = normalize_report_language(
            getattr(self._get_runtime_config(), "report_language", "ko")
        )
        text_lower = (response_text or "").lower()
        positive_keywords = ["매수", "상승", "강세", "돌파", "호재", "bullish", "buy"]
        negative_keywords = ["매도", "하락", "약세", "이탈", "악재", "bearish", "sell"]
        positive_count = sum(1 for kw in positive_keywords if kw in text_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in text_lower)

        sentiment_score = 50
        trend = "Sideways" if report_language == "en" else "횡보"
        advice = "Hold" if report_language == "en" else "보유"
        decision_type = "hold"
        if positive_count > negative_count + 1:
            sentiment_score = 65
            trend = "Bullish" if report_language == "en" else "강세"
            advice = "Buy" if report_language == "en" else "매수"
            decision_type = "buy"
        elif negative_count > positive_count + 1:
            sentiment_score = 35
            trend = "Bearish" if report_language == "en" else "약세"
            advice = "Sell" if report_language == "en" else "매도"
            decision_type = "sell"

        summary = response_text[:500] if response_text else (
            "No analysis result" if report_language == "en" else "분석 결과가 없습니다."
        )
        return AnalysisResult(
            code=code,
            name=name,
            sentiment_score=sentiment_score,
            trend_prediction=trend,
            operation_advice=advice,
            decision_type=decision_type,
            confidence_level="Low" if report_language == "en" else "낮음",
            analysis_summary=summary,
            key_points="JSON parsing failed; treat this as best-effort output." if report_language == "en" else "JSON 파싱에 실패해 참고용 텍스트 결과로 처리했습니다.",
            risk_warning="The result may be inaccurate. Cross-check with other information." if report_language == "en" else "결과가 부정확할 수 있으니 다른 정보와 함께 확인하세요.",
            raw_response=response_text,
            success=False,
            error_message="LLM response is not valid JSON; analysis result will not be persisted",
            report_language=report_language,
        )


    def batch_analyze(
        self,
        contexts: List[Dict[str, Any]],
        delay_between: float = 2.0,
    ) -> List[AnalysisResult]:
        """여러 종목을 순차 분석합니다."""
        results = []
        for i, context in enumerate(contexts):
            if i > 0:
                logger.debug("%s초 뒤 다음 분석을 진행합니다.", delay_between)
                time.sleep(delay_between)
            results.append(self.analyze(context))
        return results


def get_analyzer() -> GeminiAnalyzer:
    """LLM 분석기 인스턴스를 반환합니다."""
    return GeminiAnalyzer()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_context = {
        "code": "600519",
        "date": "2026-01-09",
        "today": {
            "open": 1800.0,
            "high": 1850.0,
            "low": 1780.0,
            "close": 1820.0,
            "volume": 10000000,
            "amount": 18200000000,
            "pct_chg": 1.5,
            "ma5": 1810.0,
            "ma10": 1800.0,
            "ma20": 1790.0,
            "volume_ratio": 1.2,
        },
        "ma_status": "정배열",
        "volume_change_ratio": 1.3,
        "price_change_ratio": 1.5,
    }
    analyzer = GeminiAnalyzer()
    if analyzer.is_available():
        print("=== AI 분석 테스트 ===")
        result = analyzer.analyze(test_context)
        print(f"분석 결과: {result.to_dict()}")
    else:
        print("LLM API 키가 없어 테스트를 건너뜁니다.")
