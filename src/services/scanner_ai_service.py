# -*- coding: utf-8 -*-
"""Secondary AI interpretation layer for market scanner candidates."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from json_repair import repair_json

from src.config import get_config
from src.core.scanner_profile import ScannerMarketProfile

logger = logging.getLogger(__name__)


class ScannerAiInterpretationService:
    """Optional, bounded AI interpretation for deterministic scanner candidates."""

    SYSTEM_PROMPT = """
你是 WolfyStock 的盘前扫描二次解释层，只负责把规则型 Scanner 的结果翻译成更容易理解的交易语言。

硬规则：
1. deterministic score / rank 永远是主排序依据，你不能改动或暗示改写排序。
2. 你只能解释“为什么值得关注、像什么机会、主要风险是什么、盘前盘中该看什么”。
3. 不要输出自动交易指令，不要承诺收益，不要把 AI 结论写成硬性买卖信号。
4. 语言保持克制、可执行、面向日内/短线观察，不要写成长篇研报。
5. 如果提供了盘后结果，只补一段轻量复盘点评，说明“为什么兑现/为什么未兑现”。

输出要求：
- 必须返回严格 JSON。
- 不要输出 Markdown，不要输出代码块。
- 未知字段使用 null，不要编造数据。
""".strip()

    OPPORTUNITY_TYPES = {
        "趋势延续",
        "临界突破",
        "强势回踩",
        "板块联动",
        "高波动观察",
        "其他",
    }

    def __init__(
        self,
        *,
        config: Optional[Any] = None,
        analyzer_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.config = config or get_config()
        self._analyzer_factory = analyzer_factory
        self._analyzer: Optional[Any] = None

    def interpret_shortlist(
        self,
        *,
        profile: ScannerMarketProfile,
        candidates: Sequence[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Generate additive AI interpretations for the top scanner candidates."""

        normalized = [dict(candidate) for candidate in candidates]
        top_n = min(self._resolve_top_n(), len(normalized))
        diagnostics = {
            "enabled": self._is_enabled(),
            "status": "skipped",
            "top_n": top_n,
            "attempted_candidates": 0,
            "generated_candidates": 0,
            "failed_candidates": 0,
            "skipped_candidates": max(0, len(normalized) - top_n),
            "models_used": [],
            "fallback_used": False,
            "message": None,
        }

        if not normalized:
            diagnostics["message"] = "当前 shortlist 为空，无需生成 AI 解读。"
            return normalized, diagnostics

        if not self._is_enabled():
            payload = self._build_status_payload(
                status="disabled",
                message="Scanner AI 解读未启用，当前结果继续只展示规则型理由。",
            )
            for candidate in normalized:
                self._attach_payload(candidate, payload)
            diagnostics["status"] = "disabled"
            diagnostics["message"] = payload["message"]
            return normalized, diagnostics

        if profile.market != "cn":
            payload = self._build_status_payload(
                status="skipped",
                message="当前阶段 AI 解读仅用于 A 股 scanner profile。",
            )
            for candidate in normalized:
                self._attach_payload(candidate, payload)
            diagnostics["status"] = "skipped"
            diagnostics["message"] = payload["message"]
            return normalized, diagnostics

        analyzer = self._get_analyzer()
        if analyzer is None or not self._is_analyzer_available(analyzer):
            payload = self._build_status_payload(
                status="unavailable",
                message="AI provider 当前不可用，scanner 已自动回退为纯规则型结果。",
            )
            for candidate in normalized:
                self._attach_payload(candidate, payload)
            diagnostics["status"] = "unavailable"
            diagnostics["message"] = payload["message"]
            return normalized, diagnostics

        models_used: List[str] = []
        fallback_used = False

        for index, candidate in enumerate(normalized, start=1):
            if index > top_n:
                self._attach_payload(
                    candidate,
                    self._build_status_payload(
                        status="skipped",
                        message=f"为控制延迟与成本，本次仅对前 {top_n} 名生成 AI 解读。",
                    ),
                )
                continue

            diagnostics["attempted_candidates"] += 1
            payload = self._interpret_candidate(
                analyzer=analyzer,
                candidate=candidate,
                profile=profile,
            )
            self._attach_payload(candidate, payload)

            if payload.get("status") == "generated":
                diagnostics["generated_candidates"] += 1
            elif payload.get("status") == "failed":
                diagnostics["failed_candidates"] += 1

            model = str(payload.get("model") or "").strip()
            if model and model not in models_used:
                models_used.append(model)
            fallback_used = fallback_used or bool(payload.get("fallback_used"))

        diagnostics["models_used"] = models_used
        diagnostics["fallback_used"] = fallback_used
        if diagnostics["generated_candidates"] == diagnostics["attempted_candidates"] and diagnostics["attempted_candidates"] > 0:
            diagnostics["status"] = "completed"
            diagnostics["message"] = f"已为前 {diagnostics['generated_candidates']} 名候选生成 AI 解读。"
        elif diagnostics["generated_candidates"] > 0:
            diagnostics["status"] = "partial"
            diagnostics["message"] = "部分候选已生成 AI 解读，失败项已自动回退为规则型展示。"
        elif diagnostics["failed_candidates"] > 0:
            diagnostics["status"] = "failed"
            diagnostics["message"] = "AI 解读生成失败，scanner 已自动回退为纯规则型结果。"
        else:
            diagnostics["status"] = "skipped"
            diagnostics["message"] = "本次未生成 AI 解读。"
        return normalized, diagnostics

    def enrich_review_commentary(
        self,
        *,
        profile: ScannerMarketProfile,
        candidate: Dict[str, Any],
        realized_outcome: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate light post-close commentary when realized outcomes are available."""

        if not self._is_enabled():
            return None
        if profile.market != "cn":
            return None

        diagnostics = candidate.get("diagnostics") if isinstance(candidate.get("diagnostics"), dict) else {}
        full_payload = diagnostics.get("ai_interpretation") if isinstance(diagnostics.get("ai_interpretation"), dict) else {}
        review_status = str(realized_outcome.get("review_status") or "pending")
        if review_status == "pending":
            if full_payload.get("review_commentary_status") == "pending_review_data":
                return None
            full_payload["review_commentary_status"] = "pending_review_data"
            diagnostics["ai_interpretation"] = full_payload
            return full_payload

        if str(full_payload.get("status") or "") != "generated":
            return None
        if full_payload.get("review_commentary"):
            return None
        if str(full_payload.get("review_commentary_status") or "") in {"generated", "failed", "unavailable"}:
            return None

        analyzer = self._get_analyzer()
        if analyzer is None or not self._is_analyzer_available(analyzer):
            full_payload["review_commentary_status"] = "unavailable"
            full_payload["review_commentary_message"] = "AI provider 当前不可用，盘后 AI 复盘点评暂未生成。"
            diagnostics["ai_interpretation"] = full_payload
            return full_payload

        request = self._call_analyzer(
            analyzer=analyzer,
            prompt=self._build_review_commentary_prompt(
                candidate=candidate,
                realized_outcome=realized_outcome,
                full_payload=full_payload,
            ),
            max_tokens=260,
            temperature=0.2,
        )
        if request is None:
            full_payload["review_commentary_status"] = "failed"
            full_payload["review_commentary_message"] = "盘后 AI 复盘点评生成失败。"
            diagnostics["ai_interpretation"] = full_payload
            return full_payload

        parsed = self._extract_json_payload(request["text"])
        commentary = self._clean_text(parsed.get("review_commentary") if isinstance(parsed, dict) else None)
        if not commentary:
            full_payload["review_commentary_status"] = "failed"
            full_payload["review_commentary_message"] = "盘后 AI 复盘点评解析失败。"
            full_payload["review_attempt_trace"] = request.get("attempt_trace") or []
            diagnostics["ai_interpretation"] = full_payload
            return full_payload

        full_payload["review_commentary"] = commentary
        full_payload["review_commentary_status"] = "generated"
        full_payload["review_generated_at"] = datetime.now().isoformat()
        full_payload["review_attempt_trace"] = request.get("attempt_trace") or []
        diagnostics["ai_interpretation"] = full_payload
        return full_payload

    @staticmethod
    def public_payload_from_diagnostics(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return ScannerAiInterpretationService._build_status_payload(
                status="skipped",
                message="当前候选未生成 AI 解读。",
            )
        return {
            "available": bool(payload.get("status") == "generated"),
            "status": str(payload.get("status") or "skipped"),
            "summary": ScannerAiInterpretationService._clean_text(payload.get("summary")),
            "opportunity_type": ScannerAiInterpretationService._clean_text(payload.get("opportunity_type")),
            "risk_interpretation": ScannerAiInterpretationService._clean_text(payload.get("risk_interpretation")),
            "watch_plan": ScannerAiInterpretationService._clean_text(payload.get("watch_plan")),
            "review_commentary": ScannerAiInterpretationService._clean_text(payload.get("review_commentary")),
            "provider": ScannerAiInterpretationService._clean_text(payload.get("provider")),
            "model": ScannerAiInterpretationService._clean_text(payload.get("model")),
            "generated_at": ScannerAiInterpretationService._clean_text(payload.get("generated_at")),
            "message": ScannerAiInterpretationService._clean_text(payload.get("message")),
        }

    @staticmethod
    def _build_status_payload(
        *,
        status: str,
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "available": status == "generated",
            "status": status,
            "summary": None,
            "opportunity_type": None,
            "risk_interpretation": None,
            "watch_plan": None,
            "review_commentary": None,
            "provider": provider,
            "model": model,
            "generated_at": None,
            "message": message,
            "attempt_trace": [],
            "fallback_used": False,
            "review_commentary_status": "pending_review_data",
        }

    def _interpret_candidate(
        self,
        *,
        analyzer: Any,
        candidate: Dict[str, Any],
        profile: ScannerMarketProfile,
    ) -> Dict[str, Any]:
        request = self._call_analyzer(
            analyzer=analyzer,
            prompt=self._build_candidate_prompt(candidate=candidate, profile=profile),
            max_tokens=420,
            temperature=0.2,
        )
        if request is None:
            return self._build_status_payload(
                status="failed",
                message="AI 解读生成失败，当前候选继续只展示规则型解释。",
            )

        parsed = self._extract_json_payload(request["text"])
        if not isinstance(parsed, dict):
            payload = self._build_status_payload(
                status="failed",
                message="AI 解读返回不可解析内容，当前候选继续只展示规则型解释。",
                provider=request.get("provider"),
                model=request.get("model"),
            )
            payload["attempt_trace"] = request.get("attempt_trace") or []
            payload["fallback_used"] = self._has_fallback(request.get("attempt_trace") or [])
            return payload

        opportunity_type = self._clean_text(parsed.get("opportunity_type"))
        if opportunity_type not in self.OPPORTUNITY_TYPES:
            opportunity_type = "其他"

        payload = {
            "available": True,
            "status": "generated",
            "summary": self._clean_text(parsed.get("summary")),
            "opportunity_type": opportunity_type,
            "risk_interpretation": self._clean_text(parsed.get("risk_interpretation")),
            "watch_plan": self._clean_text(parsed.get("watch_plan")),
            "review_commentary": self._clean_text(parsed.get("review_commentary")),
            "provider": self._clean_text(request.get("provider")),
            "model": self._clean_text(request.get("model")),
            "generated_at": datetime.now().isoformat(),
            "message": None,
            "attempt_trace": request.get("attempt_trace") or [],
            "fallback_used": self._has_fallback(request.get("attempt_trace") or []),
            "review_commentary_status": "generated" if self._clean_text(parsed.get("review_commentary")) else "pending_review_data",
        }
        if not payload["summary"] or not payload["risk_interpretation"] or not payload["watch_plan"]:
            degraded_payload = self._build_status_payload(
                status="failed",
                message="AI 解读缺少关键字段，当前候选继续只展示规则型解释。",
                provider=payload.get("provider"),
                model=payload.get("model"),
            )
            degraded_payload["attempt_trace"] = payload["attempt_trace"]
            degraded_payload["fallback_used"] = payload["fallback_used"]
            return degraded_payload
        return payload

    def _call_analyzer(
        self,
        *,
        analyzer: Any,
        prompt: str,
        max_tokens: int,
        temperature: float,
    ) -> Optional[Dict[str, Any]]:
        if hasattr(analyzer, "generate_text_with_meta"):
            response = analyzer.generate_text_with_meta(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=self.SYSTEM_PROMPT,
                call_type="scanner_interpretation",
            )
            if isinstance(response, dict) and self._clean_text(response.get("text")):
                return response
            return None

        if hasattr(analyzer, "generate_text"):
            combined_prompt = f"{self.SYSTEM_PROMPT}\n\n{prompt}"
            text = analyzer.generate_text(
                combined_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if not self._clean_text(text):
                return None
            configured_model = str(getattr(self.config, "litellm_model", "") or "").strip()
            provider = configured_model.split("/", 1)[0] if "/" in configured_model else configured_model
            return {
                "text": text,
                "model": configured_model or None,
                "provider": provider or None,
                "usage": {},
                "attempt_trace": [],
            }
        return None

    def _get_analyzer(self) -> Optional[Any]:
        if self._analyzer is not None:
            return self._analyzer
        try:
            if self._analyzer_factory is not None:
                self._analyzer = self._analyzer_factory()
            else:
                from src.analyzer import GeminiAnalyzer

                self._analyzer = GeminiAnalyzer()
        except Exception as exc:
            logger.warning("Scanner AI analyzer init failed: %s", exc)
            self._analyzer = None
        return self._analyzer

    @staticmethod
    def _is_analyzer_available(analyzer: Any) -> bool:
        try:
            if hasattr(analyzer, "is_available") and callable(analyzer.is_available):
                return bool(analyzer.is_available())
            value = getattr(analyzer, "is_available", None)
            if value is not None:
                return bool(value)
        except Exception:
            return False
        return False

    def _build_candidate_prompt(
        self,
        *,
        candidate: Dict[str, Any],
        profile: ScannerMarketProfile,
    ) -> str:
        context = {
            "market": profile.market,
            "profile": profile.key,
            "symbol": candidate.get("symbol"),
            "name": candidate.get("name"),
            "rank": candidate.get("rank"),
            "deterministic_score": candidate.get("score"),
            "quality_hint": candidate.get("quality_hint"),
            "reason_summary": candidate.get("reason_summary"),
            "reasons": candidate.get("reasons") or [],
            "risk_notes": candidate.get("risk_notes") or [],
            "watch_context": candidate.get("watch_context") or [],
            "boards": candidate.get("boards") or [],
            "key_metrics": candidate.get("key_metrics") or [],
            "feature_signals": candidate.get("feature_signals") or [],
        }
        return (
            "请基于以下 deterministic scanner 候选生成二次解释。\n"
            "注意：不要修改排名，不要替换规则型理由。\n\n"
            f"候选上下文：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            "请返回 JSON，字段如下：\n"
            "{\n"
            '  "summary": "40~90字，说明今天为什么值得关注",\n'
            '  "opportunity_type": "趋势延续/临界突破/强势回踩/板块联动/高波动观察/其他",\n'
            '  "risk_interpretation": "40~90字，用交易员语言解释主要风险",\n'
            '  "watch_plan": "50~120字，说明盘前与开盘后优先观察什么",\n'
            '  "review_commentary": null\n'
            "}\n"
        )

    def _build_review_commentary_prompt(
        self,
        *,
        candidate: Dict[str, Any],
        realized_outcome: Dict[str, Any],
        full_payload: Dict[str, Any],
    ) -> str:
        context = {
            "symbol": candidate.get("symbol"),
            "name": candidate.get("name"),
            "rank": candidate.get("rank"),
            "deterministic_score": candidate.get("score"),
            "ai_summary": full_payload.get("summary"),
            "ai_opportunity_type": full_payload.get("opportunity_type"),
            "realized_outcome": realized_outcome,
        }
        return (
            "请为以下 scanner 候选补一段轻量盘后复盘点评，说明为什么这次机会兑现或未兑现。\n"
            "要求：只写 40~90 字，不重写整份分析，不改变原始排序。\n\n"
            f"上下文：\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            "请返回 JSON：\n"
            "{\n"
            '  "review_commentary": "一句轻量复盘点评"\n'
            "}\n"
        )

    @staticmethod
    def _extract_json_payload(text: Optional[str]) -> Optional[Dict[str, Any]]:
        content = (text or "").strip()
        if not content:
            return None
        candidates = [content]
        fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.IGNORECASE | re.DOTALL)
        candidates.extend(fenced)
        object_match = re.search(r"(\{.*\})", content, flags=re.DOTALL)
        if object_match:
            candidates.append(object_match.group(1))

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                try:
                    repaired = repair_json(candidate, return_objects=True)
                    if isinstance(repaired, dict):
                        return repaired
                except Exception:
                    continue
        return None

    def _resolve_top_n(self) -> int:
        raw_value = getattr(self.config, "scanner_ai_top_n", 3)
        try:
            value = int(raw_value)
        except Exception:
            value = 3
        return max(1, min(value, 10))

    def _is_enabled(self) -> bool:
        return bool(getattr(self.config, "scanner_ai_enabled", False))

    @staticmethod
    def _attach_payload(candidate: Dict[str, Any], payload: Dict[str, Any]) -> None:
        diagnostics = dict(candidate.get("_diagnostics") or {})
        diagnostics["ai_interpretation"] = dict(payload)
        candidate["_diagnostics"] = diagnostics
        candidate["ai_interpretation"] = ScannerAiInterpretationService.public_payload_from_diagnostics(payload)

    @staticmethod
    def _has_fallback(attempt_trace: Sequence[Dict[str, Any]]) -> bool:
        return any(str(item.get("result") or "") == "switched_to_fallback" for item in attempt_trace)

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
