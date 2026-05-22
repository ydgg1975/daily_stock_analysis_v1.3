# -*- coding: utf-8 -*-
"""Vision model analysis for generated stock charts."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Optional

from src.services import image_stock_extractor as vision_core

logger = logging.getLogger(__name__)

CHART_VISION_PROMPT = """Analyze this stock chart image and return a compact JSON object only.

Focus on what is visually visible in the chart:
- trend: bullish|bearish|sideways|mixed
- pattern: short visual pattern name
- support_resistance: visible support/resistance notes
- risk_notes: array of 1-3 visible risks or uncertainties
- confidence: high|medium|low
- uncertainty: short note about what the image does not prove

Do not provide investment advice. Do not use markdown. Return JSON only.
"""


class ChartVisionAnalysisService:
    """Send generated chart images to a configured Vision LLM."""

    def analyze_chart_image(
        self,
        *,
        stock_code: str,
        image_content: str,
        image_format: str = "svg",
        numeric_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not image_content:
            return {
                "version": 1,
                "status": "degraded",
                "reason": "No chart image content was provided for Vision analysis.",
            }

        model = vision_core._resolve_vision_model()
        if not model:
            return {
                "version": 1,
                "status": "not_configured",
                "reason": "Vision model is not configured; numeric chart analysis was used instead.",
            }

        keys = vision_core._get_api_keys_for_model(model, vision_core.get_config())
        if not keys:
            return {
                "version": 1,
                "status": "not_configured",
                "reason": f"No API key found for vision model {model}; numeric chart analysis was used instead.",
                "model": model,
            }

        mime_type = self._mime_type(image_format)
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_content.encode('utf-8')).decode('ascii')}"
        prompt = CHART_VISION_PROMPT
        if numeric_metadata:
            prompt += "\nNumeric chart metadata for reference:\n"
            prompt += json.dumps(numeric_metadata, ensure_ascii=False, default=str)[:3000]

        try:
            if getattr(vision_core.litellm, "completion", None) is None:
                import litellm as litellm_module

                vision_core.litellm = litellm_module
            response = vision_core.litellm.completion(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                max_tokens=800,
                api_key=keys[0],
                timeout=vision_core.VISION_API_TIMEOUT,
            )
            raw = response.choices[0].message.content if response and response.choices else ""
            parsed = self._parse_json_object(raw)
            comparison = self.compare_with_numeric_analysis(parsed, numeric_metadata or {})
            evidence = self.build_evidence_summary(parsed, comparison)
            return {
                "version": 1,
                "status": "ok",
                "model": model,
                "stock_code": stock_code,
                "image_format": image_format,
                "analysis": parsed,
                "comparison": comparison,
                "evidence": evidence,
                "raw_text": raw,
            }
        except Exception as exc:
            logger.warning("Chart Vision analysis failed for %s: %s", stock_code, exc)
            return {
                "version": 1,
                "status": "degraded",
                "model": model,
                "reason": f"Vision chart analysis failed: {exc}",
            }

    @staticmethod
    def _mime_type(image_format: str) -> str:
        normalized = str(image_format or "").strip().lower()
        if normalized == "png":
            return "image/png"
        if normalized == "webp":
            return "image/webp"
        return "image/svg+xml"

    @staticmethod
    def _parse_json_object(raw: Any) -> Dict[str, Any]:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {"text": text}
        except json.JSONDecodeError:
            return {"text": text}

    @classmethod
    def compare_with_numeric_analysis(
        cls,
        vision_analysis: Dict[str, Any],
        numeric_metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare VLM chart reading with deterministic numeric chart metadata."""
        vision_signal = cls._normalize_signal(vision_analysis.get("trend"))
        numeric_signal = cls._numeric_signal(numeric_metadata)
        vision_pattern = str(vision_analysis.get("pattern") or "").strip().lower()
        numeric_pattern = str((numeric_metadata.get("pattern") or {}).get("name") or "").strip().lower()
        conflicts = []

        if vision_signal != "unknown" and numeric_signal != "unknown" and vision_signal != numeric_signal:
            conflicts.append({
                "type": "signal_mismatch",
                "vision_signal": vision_signal,
                "numeric_signal": numeric_signal,
                "message": "Vision trend and numeric chart signals disagree.",
            })

        pattern_match = False
        if vision_pattern and numeric_pattern:
            compact_vision = vision_pattern.replace("-", "_").replace(" ", "_")
            pattern_match = compact_vision in numeric_pattern or numeric_pattern in compact_vision
            if not pattern_match:
                conflicts.append({
                    "type": "pattern_mismatch",
                    "vision_pattern": vision_pattern,
                    "numeric_pattern": numeric_pattern,
                    "message": "Vision pattern label differs from numeric pattern detection.",
                })

        if conflicts:
            agreement = "conflict"
        elif vision_signal == "unknown":
            agreement = "vision_unclear"
        elif numeric_signal == "unknown":
            agreement = "numeric_unclear"
        elif pattern_match:
            agreement = "strong"
        else:
            agreement = "directional"

        return {
            "version": 1,
            "agreement": agreement,
            "vision_signal": vision_signal,
            "numeric_signal": numeric_signal,
            "vision_pattern": vision_pattern or None,
            "numeric_pattern": numeric_pattern or None,
            "conflicts": conflicts,
        }

    @classmethod
    def build_evidence_summary(
        cls,
        vision_analysis: Dict[str, Any],
        comparison: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Normalize Vision evidence and uncertainty for display/reporting."""
        evidence_items = []
        support_resistance = cls._clean_text(vision_analysis.get("support_resistance"))
        if support_resistance:
            evidence_items.append({
                "type": "support_resistance",
                "text": support_resistance,
            })

        pattern = cls._clean_text(vision_analysis.get("pattern"))
        if pattern:
            evidence_items.append({
                "type": "pattern",
                "text": pattern,
            })

        risk_notes = vision_analysis.get("risk_notes")
        if isinstance(risk_notes, list):
            for note in risk_notes[:3]:
                text = cls._clean_text(note)
                if text:
                    evidence_items.append({
                        "type": "risk_note",
                        "text": text,
                    })
        elif cls._clean_text(risk_notes):
            evidence_items.append({
                "type": "risk_note",
                "text": cls._clean_text(risk_notes),
            })

        uncertainty = cls._clean_text(vision_analysis.get("uncertainty"))
        confidence = cls._normalize_confidence(vision_analysis.get("confidence"))
        conflicts = list((comparison or {}).get("conflicts") or [])
        uncertainty_flags = []
        if uncertainty:
            uncertainty_flags.append(uncertainty)
        if confidence == "low":
            uncertainty_flags.append("Vision model reported low confidence.")
        if conflicts:
            uncertainty_flags.append("Vision and numeric chart analysis disagree.")

        return {
            "version": 1,
            "confidence": confidence,
            "evidence_items": evidence_items[:6],
            "uncertainty": uncertainty or None,
            "uncertainty_flags": uncertainty_flags[:5],
            "conflict_count": len(conflicts),
        }

    @staticmethod
    def _numeric_signal(metadata: Dict[str, Any]) -> str:
        visual = ChartVisionAnalysisService._normalize_signal(metadata.get("visual_signal"))
        indicator = ChartVisionAnalysisService._normalize_signal(metadata.get("indicator_signal"))
        if visual == indicator:
            return visual
        if visual != "unknown" and indicator in {"unknown", "neutral"}:
            return visual
        if indicator != "unknown" and visual in {"unknown", "neutral"}:
            return indicator
        if visual != "unknown":
            return visual
        return indicator

    @staticmethod
    def _normalize_signal(value: Any) -> str:
        text = str(value or "").strip().lower()
        if "bull" in text or "up" in text or "breakout" in text:
            return "bullish"
        if "bear" in text or "down" in text or "breakdown" in text:
            return "bearish"
        if text in {"sideways", "range", "range_bound", "neutral", "mixed"}:
            return "neutral"
        return "unknown"

    @staticmethod
    def _normalize_confidence(value: Any) -> str:
        text = str(value or "").strip().lower()
        if text in {"high", "medium", "low"}:
            return text
        return "medium"

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value or "").strip()
