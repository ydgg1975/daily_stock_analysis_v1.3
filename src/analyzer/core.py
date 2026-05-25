# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - AI分析核心
===================================

职责：
1. 封装 LLM 调用逻辑（通过 LiteLLM 统一调用 Gemini/Anthropic/OpenAI 等）
2. 解析 LLM 响应为结构化 AnalysisResult
"""

import json
import logging
import math
import re
import sys
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable

import litellm
from json_repair import repair_json
from litellm import Router

from src.agent.llm_adapter import (
    get_thinking_extra_body,
    resolve_fallback_litellm_wire_models,
    register_fallback_model_pricing,
)
from src.config import (
    Config,
    extra_litellm_params,
    get_api_keys_for_model,
    get_config,
    get_configured_llm_models,
    normalize_litellm_temperature,
    resolve_litellm_wire_model,
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
    localize_confidence_level,
    normalize_report_language,
)
from src.schemas.report_schema import AnalysisReportSchema
from src.market_context import get_market_role, get_market_guidelines

# 서브모듈 임포트
from src.analyzer.prompts import LEGACY_DEFAULT_SYSTEM_PROMPT, SYSTEM_PROMPT, TEXT_SYSTEM_PROMPT
from src.analyzer.validators import check_content_integrity, apply_placeholder_fill
from src.analyzer.stabilizer import (
    stabilize_decision_with_structure,
    normalize_chip_structure_availability,
    _safe_float,
    _sanitize_trend_analysis_for_prompt,
)

logger = logging.getLogger(__name__)


def _normalize_text_list(value: Any) -> List[str]:
    """Normalize arbitrary LLM output into a compact list of text values."""
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        lines = [line.strip(" -•\t") for line in text.splitlines()]
        return [line for line in lines if line]
    if isinstance(value, (list, tuple, set)):
        normalized: List[str] = []
        for item in value:
            normalized.extend(_normalize_text_list(item))
        return normalized
    if isinstance(value, dict):
        normalized = []
        for key, item_value in value.items():
            children = _normalize_text_list(item_value)
            if children:
                normalized.extend(f"{key}: {child}" for child in children)
        return normalized
    text = str(value).strip()
    return [text] if text else []


class _LiteLLMStreamError(RuntimeError):
    """Internal error wrapper that records whether any text was streamed."""

    def __init__(self, message: str, *, partial_received: bool = False):
        super().__init__(message)
        self.partial_received = partial_received


class _AllModelsFailedError(Exception):
    """Raised when every model in the fallback chain fails."""

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


def get_stock_name_multi_source(
    stock_code: str,
    context: Optional[Dict] = None,
    data_manager = None
) -> str:
    """多来源获取股票中文名称"""
    if context:
        if context.get('stock_name'):
            name = context['stock_name']
            if name and not name.startswith('股票'):
                return name

        if 'realtime' in context and context['realtime'].get('name'):
            return context['realtime']['name']

    if stock_code in STOCK_NAME_MAP:
        return STOCK_NAME_MAP[stock_code]

    if data_manager is None:
        try:
            from data_provider.base import DataFetcherManager
            data_manager = DataFetcherManager()
        except Exception as e:
            logger.debug(f"无法初始化 DataFetcherManager: {e}")

    if data_manager:
        try:
            name = data_manager.get_stock_name(stock_code)
            if name:
                STOCK_NAME_MAP[stock_code] = name
                return name
        except Exception as e:
            logger.debug(f"从数据源获取股票名称失败: {e}")

    return f'股票{stock_code}'


@dataclass
class AnalysisResult:
    """AI 分析结果数据类 - 决策仪表盘版"""
    code: str
    name: str
    sentiment_score: int
    trend_prediction: str
    operation_advice: str
    decision_type: str = "hold"
    confidence_level: str = "中"
    report_language: str = "zh"
    dashboard: Optional[Dict[str, Any]] = None
    trend_analysis: str = ""
    short_term_outlook: str = ""
    medium_term_outlook: str = ""
    technical_analysis: str = ""
    ma_analysis: str = ""
    volume_analysis: str = ""
    pattern_analysis: str = ""
    fundamental_analysis: str = ""
    sector_position: str = ""
    company_highlights: str = ""
    news_summary: str = ""
    market_sentiment: str = ""
    hot_topics: str = ""
    analysis_summary: str = ""
    key_points: str = ""
    risk_warning: str = ""
    buy_reason: str = ""
    evidence_points: Optional[List[str]] = None
    counter_evidence: Optional[List[str]] = None
    data_limitations: Optional[List[str]] = None
    confidence_reason: str = ""
    analysis_confidence: Optional[Dict[str, Any]] = None
    thesis_tracking: Optional[Dict[str, Any]] = None
    evidence_graph: Optional[Dict[str, Any]] = None
    stock_risk_report: Optional[Dict[str, Any]] = None
    chart_analysis_report: Optional[Dict[str, Any]] = None
    event_monitoring_report: Optional[Dict[str, Any]] = None
    market_snapshot: Optional[Dict[str, Any]] = None
    raw_response: Optional[str] = None
    search_performed: bool = False
    data_sources: str = ""
    success: bool = True
    error_message: Optional[str] = None
    current_price: Optional[float] = None
    change_pct: Optional[float] = None
    model_used: Optional[str] = None
    query_id: Optional[str] = None
    fundamental_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'code': self.code,
            'name': self.name,
            'sentiment_score': self.sentiment_score,
            'trend_prediction': self.trend_prediction,
            'operation_advice': self.operation_advice,
            'decision_type': self.decision_type,
            'confidence_level': self.confidence_level,
            'report_language': self.report_language,
            'dashboard': self.dashboard,
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
            'evidence_points': self.evidence_points or [],
            'counter_evidence': self.counter_evidence or [],
            'data_limitations': self.data_limitations or [],
            'confidence_reason': self.confidence_reason,
            'analysis_confidence': self.analysis_confidence,
            'thesis_tracking': self.thesis_tracking,
            'evidence_graph': self.evidence_graph,
            'stock_risk_report': self.stock_risk_report,
            'chart_analysis_report': self.chart_analysis_report,
            'event_monitoring_report': self.event_monitoring_report,
            'market_snapshot': self.market_snapshot,
            'search_performed': self.search_performed,
            'data_sources': self.data_sources,
            'success': self.success,
            'error_message': self.error_message,
            'current_price': self.current_price,
            'change_pct': self.change_pct,
            'model_used': self.model_used,
        }

    def get_core_conclusion(self) -> str:
        if self.dashboard and 'core_conclusion' in self.dashboard:
            return self.dashboard['core_conclusion'].get('one_sentence', self.analysis_summary)
        return self.analysis_summary

    def get_position_advice(self, has_position: bool = False) -> str:
        if self.dashboard and 'core_conclusion' in self.dashboard:
            pos_advice = self.dashboard['core_conclusion'].get('position_advice', {})
            if has_position:
                return pos_advice.get('has_position', self.operation_advice)
            return pos_advice.get('no_position', self.operation_advice)
        return self.operation_advice

    def get_sniper_points(self) -> Dict[str, str]:
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('sniper_points', {})
        return {}

    def get_checklist(self) -> List[str]:
        if self.dashboard and 'battle_plan' in self.dashboard:
            return self.dashboard['battle_plan'].get('action_checklist', [])
        return []

    def get_risk_alerts(self) -> List[str]:
        if self.dashboard and 'intelligence' in self.dashboard:
            return self.dashboard['intelligence'].get('risk_alerts', [])
        return []

    def get_emoji(self) -> str:
        _, emoji, _ = get_signal_level(
            self.operation_advice,
            self.sentiment_score,
            self.report_language,
        )
        return emoji

    def get_confidence_stars(self) -> str:
        star_map = {
            "高": "⭐⭐⭐",
            "high": "⭐⭐⭐",
            "중": "⭐⭐",
            "중(Medium)": "⭐⭐",
            "中": "⭐⭐",
            "medium": "⭐⭐",
            "저": "⭐",
            "저(Low)": "⭐",
            "低": "⭐",
            "low": "⭐",
        }
        return star_map.get(str(self.confidence_level or "").strip().lower(), "⭐⭐")


class GeminiAnalyzer:
    """Gemini AI 분석기"""
    LEGACY_DEFAULT_SYSTEM_PROMPT = LEGACY_DEFAULT_SYSTEM_PROMPT
    SYSTEM_PROMPT = SYSTEM_PROMPT
    TEXT_SYSTEM_PROMPT = TEXT_SYSTEM_PROMPT

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
        package = sys.modules.get("src.analyzer")
        package_get_config = getattr(package, "get_config", get_config)
        return getattr(self, "_config_override", None) or package_get_config()

    @staticmethod
    def _package_attr(name: str, default: Any) -> Any:
        package = sys.modules.get("src.analyzer")
        return getattr(package, name, default)

    def _get_skill_prompt_sections(self) -> tuple[str, str, bool]:
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
                skills_section = f"## 激活的交易技能\n\n{skill_instructions}\n"
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

## 输出语言（最高优先级）

- 所有 JSON 键名保持不变。
- `decision_type` 必须保持为 `buy|hold|sell`。
- 所有面向用户的人类可读文本值必须使用中文。
"""

    def _has_channel_config(self, config: Config) -> bool:
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
        config = self._get_runtime_config()
        litellm_model = config.litellm_model
        if not litellm_model:
            logger.warning("Analyzer LLM: LITELLM_MODEL not configured")
            return

        self._litellm_available = True

        if self._has_channel_config(config):
            model_list = config.llm_model_list
            try:
                router_cls = self._package_attr("Router", Router)
                self._router = router_cls(
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
                    f"Analyzer LLM: Router initialized from channels/YAML — "
                    f"{len(model_list)} deployment(s), models: {unique_models}"
                )
                return

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
                router_cls = self._package_attr("Router", Router)
                self._router = router_cls(
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
        wire_models = resolve_fallback_litellm_wire_models(model, config.llm_model_list)
        register_fallback_model_pricing(wire_models)
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
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def _extract_text_blocks(self, blocks: Any) -> str:
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
                        recovery_call = self._package_attr(
                            "call_litellm_with_param_recovery",
                            call_litellm_with_param_recovery,
                        )
                        stream_response = recovery_call(
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

                recovery_call = self._package_attr(
                    "call_litellm_with_param_recovery",
                    call_litellm_with_param_recovery,
                )
                response = recovery_call(
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
        try:
            result = self._call_litellm(
                prompt,
                generation_config={"max_tokens": max_tokens, "temperature": temperature},
            )
            if isinstance(result, tuple):
                text, model_used, usage = result
                persist_usage = self._package_attr("persist_llm_usage", persist_llm_usage)
                persist_usage(usage, model_used, call_type="market_review")
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

        request_delay = config.gemini_request_delay
        if request_delay > 0:
            logger.debug(f"[LLM] 请求前等待 {request_delay:.1f} 秒...")
            _emit_progress(65, f"{code}：LLM 请求前等待 {request_delay:.1f} 秒")
            time.sleep(request_delay)

        name = context.get('stock_name')
        if not name or name.startswith('股票'):
            if 'realtime' in context and context['realtime'].get('name'):
                name = context['realtime']['name']
            else:
                name = STOCK_NAME_MAP.get(code, f'股票{code}')

        if not self.is_available():
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='Sideways' if report_language == "en" else '震荡',
                operation_advice='Hold' if report_language == "en" else '持有',
                confidence_level='Low' if report_language == "en" else '低',
                analysis_summary='AI analysis is unavailable because no API key is configured.' if report_language == "en" else 'AI 분석 기능을 사용할 수 없습니다. API Key가 설정되지 않았습니다.',
                risk_warning='Configure an LLM API key (GEMINI_API_KEY/ANTHROPIC_API_KEY/OPENAI_API_KEY) and retry.' if report_language == "en" else 'LLM API Key를 설정한 뒤 다시 시도하세요.',
                success=False,
                error_message='LLM API key is not configured' if report_language == "en" else 'LLM API Key가 설정되지 않았습니다',
                model_used=None,
                report_language=report_language,
            )

        try:
            prompt = self._format_prompt(context, name, news_context, report_language=report_language)

            config = self._get_runtime_config()
            model_name = config.litellm_model or "unknown"
            logger.info(f"========== AI 分析 {name}({code}) ==========")
            logger.info(f"[LLM配置] 模型: {model_name}")
            logger.info(f"[LLM配置] Prompt 长度: {len(prompt)} 字符")
            logger.info(f"[LLM配置] 是否包含新闻: {'是' if news_context else '否'}")

            prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
            logger.info(f"[LLM Prompt 预览]\n{prompt_preview}")
            logger.debug(f"=== 完整 Prompt ({len(prompt)}字符) ===\n{prompt}\n=== End Prompt ===")

            generation_config = {
                "temperature": config.llm_temperature,
                "max_output_tokens": 8192,
            }

            logger.info(f"[LLM调用] 开始调用 {model_name}...")
            _emit_progress(68, f"{name}: LLM 요청을 보냈고 응답을 기다리는 중")

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

                logger.info(
                    f"[LLM返回] {model_name} 响应成功, 耗时 {elapsed:.2f}s, 响应长度 {len(response_text)} 字符"
                )
                response_preview = response_text[:300] + "..." if len(response_text) > 300 else response_text
                logger.info(f"[LLM返回 预览]\n{response_preview}")
                logger.debug(
                    f"=== {model_name} 完整响应 ({len(response_text)}字符) ===\n{response_text}\n=== End Response ==="
                )
                parse_progress = min(99, 93 + retry_count * 2)
                _emit_progress(parse_progress, f"{name}: LLM 응답을 받아 JSON을 파싱하는 중")

                result = self._parse_response(response_text, code, name)
                result.raw_response = response_text
                result.search_performed = bool(news_context)
                result.market_snapshot = self._build_market_snapshot(context)
                result.model_used = model_used
                result.report_language = report_language
                normalize_chip_structure_availability(result, context.get("chip"))

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
                        "[LLM完整性] 必填字段缺失 %s，第 %d 次补全重试",
                        missing_fields,
                        retry_count,
                    )
                    retry_progress = min(99, 92 + retry_count * 2)
                    _emit_progress(
                        retry_progress,
                        f"{name}: 리포트 필드가 부족해 보완 재시도 중 ({retry_count}/{max_retries})",
                    )
                else:
                    self._apply_placeholder_fill(result, missing_fields)
                    logger.warning(
                        "[LLM完整性] 必填字段缺失 %s，已占位补全，不阻塞流程",
                        missing_fields,
                    )
                    break

            persist_usage = self._package_attr("persist_llm_usage", persist_llm_usage)
            persist_usage(llm_usage, model_used, call_type="analysis", stock_code=code)

            logger.info(f"[LLM解析] {name}({code}) 分析完成: {result.trend_prediction}, 评分 {result.sentiment_score}")

            return result

        except Exception as e:
            logger.error(f"AI 分析 {name}({code}) 失败: {e}")
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction='Sideways' if report_language == "en" else '震荡',
                operation_advice='Hold' if report_language == "en" else '持有',
                confidence_level='Low' if report_language == "en" else '低',
                analysis_summary=(f'Analysis failed: {str(e)[:100]}' if report_language == "en" else f'分析过程出错: {str(e)[:100]}'),
                risk_warning='Analysis failed. Please retry later or review manually.' if report_language == "en" else '분석에 실패했습니다. 잠시 후 다시 시도하거나 수동으로 확인하세요.',
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
        report_language: str = "zh",
    ) -> str:
        code = context.get('code', 'Unknown')
        report_language = normalize_report_language(report_language)
        _, _, use_legacy_default_prompt = self._get_skill_prompt_sections()

        stock_name = context.get('stock_name', name)
        if not stock_name or stock_name == f'股票{code}':
            stock_name = STOCK_NAME_MAP.get(code, f'股票{code}')

        today = context.get('today', {}) or {}
        unknown_text = get_unknown_text(report_language)
        no_data_text = get_no_data_text(report_language)

        prompt = f"""# 决策仪表盘分析请求

## 📊 股票基础信息
| 项目 | 数据 |
|------|------|
| 股票代码 | **{code}** |
| 股票名称 | **{stock_name}** |
| 分析日期 | {context.get('date', unknown_text)} |

---

## 📈 技术面数据

### 今日行情
| 指标 | 数值 |
|------|------|
| 收盘价 | {today.get('close', 'N/A')} 元 |
| 开盘价 | {today.get('open', 'N/A')} 元 |
| 最高价 | {today.get('high', 'N/A')} 元 |
| 最低价 | {today.get('low', 'N/A')} 元 |
| 涨跌幅 | {today.get('pct_chg', 'N/A')}% |
| 成交量 | {self._format_volume(today.get('volume'))} |
| 成交额 | {self._format_amount(today.get('amount'))} |

### 均线系统（关键判断指标）
| 均线 | 数值 | 说明 |
|------|------|------|
| MA5 | {today.get('ma5', 'N/A')} | 原始数据 |
| MA10 | {today.get('ma10', 'N/A')} | |
| MA20 | {today.get('ma20', 'N/A')} | |
| 均线形态 | {context.get('ma_status', unknown_text)} | |
"""

        if 'realtime' in context:
            rt = context['realtime']
            prompt += f"""
### 实时行情增强数据
| 指标 | 数值 | 解读 |
|------|------|------|
| 当前价格 | {rt.get('price', 'N/A')} 元 | |
| **量比** | **{rt.get('volume_ratio', 'N/A')}** | {rt.get('volume_ratio_desc', '')} |
| **换手率** | **{rt.get('turnover_rate', 'N/A')}%** | |
| 市盈率(动态) | {rt.get('pe_ratio', 'N/A')} | |
| 市净率 | {rt.get('pb_ratio', 'N/A')} | |
| 总市值 | {self._format_amount(rt.get('total_mv'))} | |
| 流通市值 | {self._format_amount(rt.get('circ_mv'))} | |
| 60日涨跌幅 | {rt.get('change_60d', 'N/A')}% | |
"""

        fundamental_context = context.get("fundamental_context") if isinstance(context, dict) else None
        earnings_block = (
            fundamental_context.get("earnings", {})
            if isinstance(fundamental_context, dict)
            else {}
        )
        earnings_data = (
            earnings_block.get("data", {})
            if isinstance(earnings_block, dict)
            else {}
        )
        financial_report = (
            earnings_data.get("financial_report", {})
            if isinstance(earnings_data, dict)
            else {}
        )
        dividend_metrics = (
            earnings_data.get("dividend", {})
            if isinstance(earnings_data, dict)
            else {}
        )
        if isinstance(financial_report, dict) or isinstance(dividend_metrics, dict):
            financial_report = financial_report if isinstance(financial_report, dict) else {}
            dividend_metrics = dividend_metrics if isinstance(dividend_metrics, dict) else {}
            ttm_yield = dividend_metrics.get("ttm_dividend_yield_pct", "N/A")
            ttm_cash = dividend_metrics.get("ttm_cash_dividend_per_share", "N/A")
            ttm_count = dividend_metrics.get("ttm_event_count", "N/A")
            report_date = financial_report.get("report_date", "N/A")
            prompt += f"""
### 财报与分红（价值投资口径）
| 指标 | 数值 | 说明 |
|------|------|------|
| 最近报告期 | {report_date} | |
| 营业收入 | {financial_report.get('revenue', 'N/A')} | |
| 归母净利润 | {financial_report.get('net_profit_parent', 'N/A')} | |
| 经营现金流 | {financial_report.get('operating_cash_flow', 'N/A')} | |
| ROE | {financial_report.get('roe', 'N/A')} | |
| 近12个月每股现金分红 | {ttm_cash} | |
| TTM 股息率 | {ttm_yield} | |
| TTM 分红事件数 | {ttm_count} | |

> 若上述字段为 N/A 或缺失，请明确写“数据缺失，无法判断”，禁止编造。
"""

        capital_flow_block = (
            fundamental_context.get("capital_flow", {})
            if isinstance(fundamental_context, dict)
            else {}
        )
        capital_flow_data = (
            capital_flow_block.get("data", {})
            if isinstance(capital_flow_block, dict)
            else {}
        )
        stock_flow = (
            capital_flow_data.get("stock_flow", {})
            if isinstance(capital_flow_data, dict)
            else {}
        )
        sector_flow = (
            capital_flow_data.get("sector_rankings", {})
            if isinstance(capital_flow_data, dict)
            else {}
        )
        has_capital_flow = (
            isinstance(stock_flow, dict)
            and any(v is not None for v in stock_flow.values())
        ) or (
            isinstance(sector_flow, dict)
            and (sector_flow.get("top") or sector_flow.get("bottom"))
        )
        if has_capital_flow:
            top_sectors = sector_flow.get("top", []) if isinstance(sector_flow, dict) else []
            bottom_sectors = sector_flow.get("bottom", []) if isinstance(sector_flow, dict) else []
            top_sector_text = "、".join(
                str(item.get("name", "")).strip()
                for item in top_sectors[:3]
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            ) or "N/A"
            bottom_sector_text = "、".join(
                str(item.get("name", "")).strip()
                for item in bottom_sectors[:3]
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            ) or "N/A"
            prompt += f"""
### 主力资金流向（操作建议过滤器）
| 指标 | 数值 | 决策含义 |
|------|------|----------|
| 主力净流入 | {stock_flow.get('main_net_inflow', 'N/A')} | |
| 5日净流入 | {stock_flow.get('inflow_5d', 'N/A')} | |
| 10日净流入 | {stock_flow.get('inflow_10d', 'N/A')} | |
| 资金流入靠前板块 | {top_sector_text} | |
| 资金流出靠前板块 | {bottom_sector_text} | |

> 资金流向只能作为价格位置的过滤器：接近压力且主力流出时不得追买；接近支撑且未放量跌破时，优先判断为持有观察、震荡或洗盘观察。
"""

        if 'chip' in context:
            chip = context['chip']
            profit_ratio = chip.get('profit_ratio', 0)
            prompt += f"""
### 筹码分布数据（效率指标）
| 指标 | 数值 | 健康标准 |
|------|------|----------|
| **获利比例** | **{profit_ratio:.1%}** | |
| 平均成本 | {chip.get('avg_cost', 'N/A')} 元 | |
| 90%筹码集中度 | {chip.get('concentration_90', 0):.2%} | |
| 70%筹码集中度 | {chip.get('concentration_70', 0):.2%} | |
| 筹码状态 | {chip.get('chip_status', unknown_text)} | |
"""

        if 'trend_analysis' in context:
            trend = _sanitize_trend_analysis_for_prompt(
                context['trend_analysis'],
                volume_change_ratio=context.get('volume_change_ratio'),
            )
            consistency_notes = trend.get('prompt_consistency_notes', [])
            if use_legacy_default_prompt:
                bias_warning = "🚨 超过5%，严禁追高！" if trend.get('bias_ma5', 0) > 5 else "✅ 安全范围"
                prompt += f"""
### 趋势分析预判（基于交易理念）
| 指标 | 数值 | 判定 |
|------|------|------|
| 趋势状态 | {trend.get('trend_status', unknown_text)} | |
| 均线排列 | {trend.get('ma_alignment', unknown_text)} | |
| 趋势强度 | {trend.get('trend_strength', 0)}/100 | |
| **乖离率(MA5)** | **{trend.get('bias_ma5', 0):+.2f}%** | {bias_warning} |
| 乖离率(MA10) | {trend.get('bias_ma10', 0):+.2f}% | |
| 量能状态 | {trend.get('volume_status', unknown_text)} | {trend.get('volume_trend', '')} |
| 系统信号 | {trend.get('buy_signal', unknown_text)} | |
| 系统评分 | {trend.get('signal_score', 0)}/100 | |

#### 系统分析理由
**买入理由**：
{chr(10).join('- ' + r for r in trend.get('signal_reasons', ['无'])) if trend.get('signal_reasons') else '- 无'}

**风险因素**：
{chr(10).join('- ' + r for r in trend.get('risk_factors', ['无'])) if trend.get('risk_factors') else '- 无'}
"""
                if consistency_notes:
                    prompt += f"""

**一致性约束**：
{chr(10).join('- ' + note for note in consistency_notes)}
"""
            else:
                bias_warning = (
                    "🚨 偏离较大，需谨慎评估追高风险"
                    if trend.get('bias_ma5', 0) > 5
                    else "✅ 位置相对可控"
                )
                prompt += f"""
### 技术与结构分析（供激活技能判断参考）
| 指标 | 数值 | 说明 |
|------|------|------|
| 趋势状态 | {trend.get('trend_status', unknown_text)} | |
| 均线排列 | {trend.get('ma_alignment', unknown_text)} | |
| 趋势强度 | {trend.get('trend_strength', 0)}/100 | |
| **价格位置(MA5)** | **{trend.get('bias_ma5', 0):+.2f}%** | {bias_warning} |
| 价格位置(MA10) | {trend.get('bias_ma10', 0):+.2f}% | |
| 量能状态 | {trend.get('volume_status', unknown_text)} | |
| 系统信号 | {trend.get('buy_signal', unknown_text)} | |
| 系统评分 | {trend.get('signal_score', 0)}/100 | |

#### 系统分析理由
**支持因素**：
{chr(10).join('- ' + r for r in trend.get('signal_reasons', ['无'])) if trend.get('signal_reasons') else '- 无'}

**风险因素**：
{chr(10).join('- ' + r for r in trend.get('risk_factors', ['无'])) if trend.get('risk_factors') else '- 无'}
"""
                if consistency_notes:
                    prompt += f"""

**一致性约束**：
{chr(10).join('- ' + note for note in consistency_notes)}
"""

        if 'yesterday' in context:
            volume_change = context.get('volume_change_ratio', 'N/A')
            prompt += f"""
### 量价变化
- 成交量较昨日变化：{volume_change}倍
- 价格较昨日变化：{context.get('price_change_ratio', 'N/A')}%
"""
            parsed_volume_change = _safe_float(volume_change, default=math.nan)
            if math.isfinite(parsed_volume_change) and parsed_volume_change > 10:
                prompt += """
- ⚠️ 量能异常提示：成交量较昨日放大超过10倍，可能受异常数据或一次性冲量影响，必须降权解读，不能机械视为强确认信号
"""

        news_window_days: Optional[int] = None
        context_window = context.get("news_window_days")
        try:
            if context_window is not None:
                parsed_window = int(context_window)
                if parsed_window > 0:
                    news_window_days = parsed_window
        except (TypeError, ValueError):
            news_window_days = None

        if news_window_days is None:
            prompt_config = self._get_runtime_config()
            news_window_days = resolve_news_window_days(
                news_max_age_days=getattr(prompt_config, "news_max_age_days", 3),
                news_strategy_profile=getattr(prompt_config, "news_strategy_profile", "short"),
            )
        prompt += """
---

## 📰 舆情情报
"""
        if news_context:
            prompt += f"""
以下是 **{stock_name}({code})** 近{news_window_days}日的新闻搜索结果，请重点提取：
1. 🚨 **风险警报**：减持、处罚、利空
2. 🎯 **利好催化**：业绩、合同、政策
3. 📊 **业绩预期**：年报预告、业绩快报
4. 🕒 **时间规则（强制）**：
   - 输出到 `risk_alerts` / `positive_catalysts` / `latest_news` 的每一条都必须带具体日期（YYYY-MM-DD）
   - 超出近{news_window_days}日窗口的新闻一律忽略
   - 时间未知、无法确定发布日期的新闻一律忽略

```
{news_context}
```
"""
        else:
            prompt += """
未搜索到该股票近期的相关新闻。请主要依据技术面数据进行分析。
"""

        if context.get('data_missing'):
            prompt += """
⚠️ **数据缺失警告**
由于接口限制，当前无法获取完整的实时行情和技术指标数据。
请 **忽略上述表格中的 N/A 数据**，重点依据 **【📰 舆情情报】** 中的新闻进行基本面和情绪面 analysis。
在回答技术面问题（如均线、乖离率）时，请直接说明“数据缺失，无法判断”，**严禁编造数据**。
"""

        prompt += f"""
---

## ✅ 分析任务

请为 **{stock_name}({code})** 生成【决策仪表盘】，严格按照 JSON 格式输出。
"""
        if context.get('is_index_etf'):
            prompt += """
> ⚠️ **指数/ETF 分析约束**：该标的为指数跟踪型 ETF 或市场指数。
> - 风险分析仅关注：**指数走势、跟踪误差、市场流动性**
> - 严禁将基金公司的诉讼、声誉、高管变动纳入风险警报
> - 业绩预期基于**指数成分股整体表现**，而非基金公司财报
> - `risk_alerts` 中不得出现基金管理人相关的公司经营风险

"""
        prompt += f"""
### ⚠️ 重要：输出正确的股票名称格式
正确的股票名称格式为“股票名称（股票代码）”，例如“贵州茅台（600519）”。
如果上方显示的股票名称为"股票{code}"或不正确，请在分析开头**明确输出该股票的正确中文全称**。
"""
        if use_legacy_default_prompt:
            prompt += f"""

### 重点关注（必须明确回答）：
1. ❓ 是否满足 MA5>MA10>MA20 多头排列？
2. ❓ 当前乖离率是否在安全范围内（<5%）？—— 超过5%必须标注"严禁追高"
3. ❓ 量能是否配合（缩量回调/放量突破）？
4. ❓ 筹码结构是否健康？
5. ❓ 消息面有无重大利空？（减持、处罚、业绩变脸等）
"""
        else:
            prompt += f"""

### 重点关注（必须明确回答）：
1. ❓ 当前结构是否满足激活技能的关键触发条件？
2. ❓ 当前入场位置与风险回报是否合理？若偏离过大，请明确说明等待条件
3. ❓ 量能、波动与筹码结构是否支持当前结论？
4. ❓ 消息面有无重大利空或与技能结论冲突的信息？
5. ❓ 若结论成立，具体触发条件、止损位、观察点分别是什么？
"""
        prompt += f"""

### 决策仪表盘要求：
- **股票名称**：必须输出正确的中文全称（如"贵州茅台"而非"股票{code}"）
- **核心结论**：一句话说清该买/该卖/该等
- **持仓分类建议**：空仓者怎么做 vs 持仓者怎么做
- **具体狙击点位**：买入价、止损价、目标价（精确到分）
- **检查清单**：每项用 ✅/⚠️/❌ 标记
- **消息面时间合规**：`latest_news`、`risk_alerts`、`positive_catalysts` 不得包含超出近{news_window_days}日或时间未知的信息
- **技术面一致性**：严禁把“空头排列”和“多头排列”等互斥结论同时当作有效依据；若基本面/事件面与技术面冲突，必须明确写“事件先行、技术待确认”或“基本面偏多，但技术面尚未确认”

请输出完整的 JSON 格式决策仪表盘。"""

        if report_language == "en":
            prompt += """

### Output language requirements (highest priority)
- Keep every JSON key exactly as defined above; do not translate keys.
- `decision_type` must remain `buy`, `hold`, or `sell`.
- All human-readable JSON values must be in English.
- This includes `stock_name`, `trend_prediction`, `operation_advice`, `confidence_level`, all nested dashboard text, checklist items, and every summary field.
- Use the common English company name when you are confident. If not, keep the listed company name rather than inventing one.
- When data is missing, explain it in English instead of Chinese.
"""
        else:
            prompt += f"""

### 输出语言要求（最高优先级）
- 所有 JSON 键名必须保持不变，不要翻译键名。
- `decision_type` 必须保持为 `buy`、`hold`、`sell`。
- 所有面向用户的人类可读文本值必须使用中文。
- 当数据缺失时，请使用中文直接说明“{no_data_text}，无法判断”。
"""

        return prompt

    def _format_volume(self, volume: Optional[float]) -> str:
        if volume is None:
            return 'N/A'
        if volume >= 1e8:
            return f"{volume / 1e8:.2f} 亿股"
        elif volume >= 1e4:
            return f"{volume / 1e4:.2f} 万股"
        else:
            return f"{volume:.0f} 股"

    def _format_amount(self, amount: Optional[float]) -> str:
        if amount is None:
            return 'N/A'
        if amount >= 1e8:
            return f"{amount / 1e8:.2f} 亿元"
        elif amount >= 1e4:
            return f"{amount / 1e4:.2f} 万元"
        else:
            return f"{amount:.0f} 元"

    def _format_percent(self, value: Optional[float]) -> str:
        if value is None:
            return 'N/A'
        try:
            return f"{float(value):.2f}%"
        except (TypeError, ValueError):
            return 'N/A'

    def _format_price(self, value: Optional[float]) -> str:
        if value is None:
            return 'N/A'
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return 'N/A'

    def _build_market_snapshot(self, context: Dict[str, Any]) -> Dict[str, Any]:
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
            "date": context.get('date', '未知'),
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
        return check_content_integrity(result)

    def _build_integrity_complement_prompt(self, missing_fields: List[str], report_language: str = "zh") -> str:
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

        lines = ["### 补全要求：请在上方分析基础上补充以下必填内容，并输出完整 JSON："]
        for f in missing_fields:
            if f == "sentiment_score":
                lines.append("- sentiment_score: 0-100 综合评分")
            elif f == "operation_advice":
                lines.append("- operation_advice: 买入/加仓/持有/减仓/卖出/观望")
            elif f == "analysis_summary":
                lines.append("- analysis_summary: 综合分析摘要")
            elif f == "dashboard.core_conclusion.one_sentence":
                lines.append("- dashboard.core_conclusion.one_sentence: 一句话决策")
            elif f == "dashboard.intelligence.risk_alerts":
                lines.append("- dashboard.intelligence.risk_alerts: 风险警报列表（可为空数组）")
            elif f == "dashboard.battle_plan.sniper_points.stop_loss":
                lines.append("- dashboard.battle_plan.sniper_points.stop_loss: 止损价")
        return "\n".join(lines)

    def _build_integrity_retry_prompt(
        self,
        base_prompt: str,
        previous_response: str,
        missing_fields: List[str],
        report_language: str = "zh",
    ) -> str:
        complement = self._build_integrity_complement_prompt(missing_fields, report_language=report_language)
        previous_output = previous_response.strip()
        if normalize_report_language(report_language) == "en":
            prefix = "### The previous output is below. Complete the missing fields based on that output and return the full JSON again. Do not omit existing fields:"
        else:
            prefix = "### 上一次输出如下，请在该输出基础上补齐缺失字段，并重新输出完整 JSON。不要省略已有字段："
        return "\n\n".join([
            base_prompt,
            prefix,
            previous_output,
            complement,
        ])

    def _apply_placeholder_fill(self, result: AnalysisResult, missing_fields: List[str]) -> None:
        apply_placeholder_fill(result, missing_fields)

    def _parse_response(
        self,
        response_text: str,
        code: str,
        name: str
    ) -> AnalysisResult:
        try:
            report_language = normalize_report_language(
                getattr(self._get_runtime_config(), "report_language", "zh")
            )
            cleaned_text = response_text
            if '```json' in cleaned_text:
                cleaned_text = cleaned_text.replace('```json', '').replace('```', '')
            elif '```' in cleaned_text:
                cleaned_text = cleaned_text.replace('```', '')

            json_start = cleaned_text.find('{')
            json_end = cleaned_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = cleaned_text[json_start:json_end]
                json_str = self._fix_json_string(json_str)
                data = json.loads(json_str)

                try:
                    AnalysisReportSchema.model_validate(data)
                except Exception as e:
                    logger.warning(
                        "LLM report schema validation failed, continuing with raw dict: %s",
                        str(e)[:100],
                    )

                dashboard = data.get('dashboard', None)
                ai_stock_name = data.get('stock_name')
                if ai_stock_name and (name.startswith('股票') or name == code or 'Unknown' in name):
                    name = ai_stock_name

                decision_type = data.get('decision_type', '')
                if not decision_type:
                    op = data.get('operation_advice', 'Hold' if report_language == "en" else '持有')
                    decision_type = infer_decision_type_from_advice(op, default='hold')

                return AnalysisResult(
                    code=code,
                    name=name,
                    sentiment_score=int(data.get('sentiment_score', 50)),
                    trend_prediction=data.get('trend_prediction', 'Sideways' if report_language == "en" else '震荡'),
                    operation_advice=data.get('operation_advice', 'Hold' if report_language == "en" else '持有'),
                    decision_type=decision_type,
                    confidence_level=localize_confidence_level(
                        data.get('confidence_level', 'Medium' if report_language == "en" else '中'),
                        report_language,
                    ),
                    report_language=report_language,
                    dashboard=dashboard,
                    trend_analysis=data.get('trend_analysis', ''),
                    short_term_outlook=data.get('short_term_outlook', ''),
                    medium_term_outlook=data.get('medium_term_outlook', ''),
                    technical_analysis=data.get('technical_analysis', ''),
                    ma_analysis=data.get('ma_analysis', ''),
                    volume_analysis=data.get('volume_analysis', ''),
                    pattern_analysis=data.get('pattern_analysis', ''),
                    fundamental_analysis=data.get('fundamental_analysis', ''),
                    sector_position=data.get('sector_position', ''),
                    company_highlights=data.get('company_highlights', ''),
                    news_summary=data.get('news_summary', ''),
                    market_sentiment=data.get('market_sentiment', ''),
                    hot_topics=data.get('hot_topics', ''),
                    analysis_summary=data.get('analysis_summary', 'Analysis completed' if report_language == "en" else '分析完成'),
                    key_points=data.get('key_points', ''),
                    risk_warning=data.get('risk_warning', ''),
                    buy_reason=data.get('buy_reason', ''),
                    evidence_points=_normalize_text_list(data.get('evidence_points')),
                    counter_evidence=_normalize_text_list(data.get('counter_evidence')),
                    data_limitations=_normalize_text_list(data.get('data_limitations')),
                    confidence_reason=str(data.get('confidence_reason', '') or ''),
                    analysis_confidence=data.get('analysis_confidence') if isinstance(data.get('analysis_confidence'), dict) else None,
                    evidence_graph=data.get('evidence_graph') if isinstance(data.get('evidence_graph'), dict) else None,
                    search_performed=data.get('search_performed', False),
                    data_sources=data.get('data_sources', 'Technical data' if report_language == "en" else '技术面数据'),
                    success=True,
                )
            else:
                logger.warning(f"无法从响应中提取 JSON，标记为解析失败")
                return self._parse_text_response(response_text, code, name)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}，标记为解析失败")
            return self._parse_text_response(response_text, code, name)

    def _fix_json_string(self, json_str: str) -> str:
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        json_str = json_str.replace('True', 'true').replace('False', 'false')
        json_str = repair_json(json_str)
        return json_str

    def _validate_json_response(self, text: str) -> None:
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

    def _parse_text_response(
        self,
        response_text: str,
        code: str,
        name: str
    ) -> AnalysisResult:
        report_language = normalize_report_language(
            getattr(self._get_runtime_config(), "report_language", "zh")
        )
        sentiment_score = 50
        trend = 'Sideways' if report_language == "en" else '震荡'
        advice = 'Hold' if report_language == "en" else '持有'

        text_lower = response_text.lower()
        positive_keywords = ['看多', '买入', '上涨', '突破', '强势', '利好', '加仓', 'bullish', 'buy']
        negative_keywords = ['看空', '卖出', '下跌', '跌破', '弱势', '利空', '减仓', 'bearish', 'sell']

        positive_count = sum(1 for kw in positive_keywords if kw in text_lower)
        negative_count = sum(1 for kw in negative_keywords if kw in text_lower)

        if positive_count > negative_count + 1:
            sentiment_score = 65
            trend = 'Bullish' if report_language == "en" else '看多'
            advice = 'Buy' if report_language == "en" else '买入'
            decision_type = 'buy'
        elif negative_count > positive_count + 1:
            sentiment_score = 35
            trend = 'Bearish' if report_language == "en" else '看空'
            advice = 'Sell' if report_language == "en" else '卖出'
            decision_type = 'sell'
        else:
            decision_type = 'hold'

        summary = response_text[:500] if response_text else ('No analysis result' if report_language == "en" else '无分析结果')

        return AnalysisResult(
            code=code,
            name=name,
            sentiment_score=sentiment_score,
            trend_prediction=trend,
            operation_advice=advice,
            decision_type=decision_type,
            confidence_level='Low' if report_language == "en" else '低',
            analysis_summary=summary,
            key_points='JSON parsing failed; treat this as best-effort output.' if report_language == "en" else 'JSON解析失败，仅供参考',
            risk_warning='The result may be inaccurate. Cross-check with other information.' if report_language == "en" else '分析结果可能不准确，建议结合其他信息判断',
            raw_response=response_text,
            success=False,
            error_message='LLM response is not valid JSON; analysis result will not be persisted',
            report_language=report_language,
        )

    def batch_analyze(
        self,
        contexts: List[Dict[str, Any]],
        delay_between: float = 2.0
    ) -> List[AnalysisResult]:
        results = []
        for i, context in enumerate(contexts):
            if i > 0:
                logger.debug(f"等待 {delay_between} 秒后继续...")
                time.sleep(delay_between)

            result = self.analyze(context)
            results.append(result)
        return results


def get_analyzer() -> GeminiAnalyzer:
    return GeminiAnalyzer()
