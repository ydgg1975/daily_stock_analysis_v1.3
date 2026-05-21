# -*- coding: utf-8 -*-
"""Vision LLM stock-code extraction helpers."""

from __future__ import annotations

import base64
import json
import logging
import random
import re
import sys
import time
from typing import List, Optional, Tuple

from src.config import Config, get_config

logger = logging.getLogger(__name__)


class _LiteLLMPlaceholder:
    """Provide a patchable placeholder before litellm is imported."""

    completion = None


# Keep a patchable module attribute while still avoiding a hard import at module load.
litellm = sys.modules.get("litellm") or _LiteLLMPlaceholder()

EXTRACT_PROMPT = """주식 시장 스크린샷 또는 이미지를 분석해, 이미지 안에 보이는 모든 종목 코드와 종목명을 추출하세요.

중요:
- 이미지에 종목명과 코드가 함께 보이면 둘 다 추출하세요.
- 관심 종목 목록, ETF 목록, 차트 캡션, 검색 결과처럼 여러 종목이 보이는 경우 각 종목을 개별 객체로 반환하세요.
- 출력은 유효한 JSON 배열만 반환하세요.
- markdown, 설명 문장, 코드 블록 표시는 반환하지 마세요.

각 배열 요소는 다음 형식을 사용합니다.
{"code":"종목 코드","name":"종목명","confidence":"high|medium|low"}

필드 규칙:
- code: 필수입니다. A주 6자리, 홍콩 주식 5자리, 미국 ticker, ETF 코드 등을 인식합니다.
- name: 이미지에 이름이 보이면 필수입니다. 이름이 실제로 보이지 않을 때만 생략할 수 있습니다.
- confidence: 필수입니다. high는 확실함, medium은 비교적 확실함, low는 불확실함을 의미합니다.

예시:
- A주: 600519 Kweichow Moutai, 300750 CATL
- 홍콩 주식: 00700 Tencent, 09988 Alibaba
- 미국 주식: AAPL Apple, TSLA Tesla
- ETF: 159887 Bank ETF, 512880 Securities ETF, 512000 Brokerage ETF, 512480 Semiconductor ETF

출력 예시:
[{"code":"600519","name":"Kweichow Moutai","confidence":"high"},{"code":"159887","name":"Bank ETF","confidence":"high"}]

금지:
- ["159887","512880"]처럼 코드 배열만 반환하지 마세요.
- JSON 배열 외의 텍스트를 함께 반환하지 마세요.
- 종목 코드를 찾지 못하면 []를 반환하세요.
"""

_VALID_CONFIDENCE = frozenset({"high", "medium", "low"})
_FAKE_CODES = frozenset({"CODE", "NAME", "HIGH", "LOW", "MEDIUM", "CONFIDENCE", "JSON"})

ALLOWED_MIME = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
MAX_SIZE_BYTES = 5 * 1024 * 1024
VISION_API_TIMEOUT = 60

_IMAGE_SIGNATURES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/gif": [b"GIF87a", b"GIF89a"],
    "image/webp": [b"RIFF"],
}


def _verify_image_magic_bytes(image_bytes: bytes, mime_type: str) -> None:
    """Verify actual file content matches declared MIME type."""
    if len(image_bytes) < 12:
        raise ValueError("이미지 파일이 너무 작거나 손상되었습니다.")
    if mime_type not in _IMAGE_SIGNATURES:
        raise ValueError(f"지원하지 않는 이미지 형식입니다: {mime_type}")
    if mime_type == "image/webp":
        if image_bytes[:4] != b"RIFF" or image_bytes[8:12] != b"WEBP":
            raise ValueError("파일 내용이 선언된 image/webp 형식과 일치하지 않습니다.")
        return
    for sig in _IMAGE_SIGNATURES[mime_type]:
        if image_bytes.startswith(sig):
            return
    raise ValueError(f"파일 내용이 선언된 {mime_type} 형식과 일치하지 않습니다.")


def _normalize_code(raw: str) -> Optional[str]:
    """Normalize and validate a single stock code."""
    s = raw.strip().upper()
    if not s:
        return None
    if s.isdigit() and len(s) in (5, 6):
        return s
    if re.match(r"^[A-Z]{1,5}(\.[A-Z])?$", s):
        return s
    for suffix in (".SH", ".SZ", ".SS"):
        if s.endswith(suffix):
            base = s[: -len(suffix)].strip()
            if base.isdigit() and len(base) in (5, 6):
                return base
    return None


def _strip_markdown_fence(text: str) -> str:
    cleaned = text.strip()
    for start in ("```json", "```"):
        if cleaned.startswith(start):
            cleaned = cleaned[len(start) :].strip()
            break
    end_idx = cleaned.rfind("```")
    if end_idx >= 0:
        cleaned = cleaned[:end_idx].strip()
    return cleaned


def _parse_codes_from_text(text: str) -> List[str]:
    """Parse stock codes from legacy LLM responses."""
    seen: set[str] = set()
    result: List[str] = []
    cleaned = _strip_markdown_fence(text)

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    c = _normalize_code(item)
                    if c and c not in seen and c not in _FAKE_CODES:
                        seen.add(c)
                        result.append(c)
            return result
    except json.JSONDecodeError:
        pass

    for m in re.finditer(r"\b([0-9]{5,6}|[A-Z]{1,5}(\.[A-Z])?)\b", text, re.IGNORECASE):
        c = _normalize_code(m.group(1))
        if c and c not in seen and c not in _FAKE_CODES:
            seen.add(c)
            result.append(c)

    return result


def _parse_items_from_text(text: str) -> List[Tuple[str, Optional[str], str]]:
    """Parse LLM response into items of (code, optional name, confidence)."""
    cleaned = _strip_markdown_fence(text)

    parsed_data = None
    try:
        parsed_data = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json

            parsed_data = repair_json(cleaned, return_objects=True)
            logger.debug("[ImageExtractor] json.loads failed, repaired malformed JSON response")
        except Exception:
            parsed_data = None

    if isinstance(parsed_data, list):
        seen: set[str] = set()
        result: List[Tuple[str, Optional[str], str]] = []
        for item in parsed_data:
            if not isinstance(item, dict):
                continue
            code_raw = item.get("code") if isinstance(item.get("code"), str) else None
            if not code_raw:
                continue
            code = _normalize_code(code_raw)
            if not code or code in seen or code in _FAKE_CODES:
                continue
            seen.add(code)
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                name = name.strip()
            else:
                name = None
            conf = item.get("confidence")
            if isinstance(conf, str) and conf.lower() in _VALID_CONFIDENCE:
                conf = conf.lower()
            else:
                conf = "medium"
            result.append((code, name, conf))
        if result:
            return result

    codes = _parse_codes_from_text(text)
    if not codes:
        logger.info("[ImageExtractor] no structured items or legacy codes found")
    return [(c, None, "medium") for c in codes]


def _resolve_vision_model() -> str:
    """Determine the litellm model to use for vision."""
    cfg = get_config()
    model = (cfg.vision_model or cfg.openai_vision_model or cfg.litellm_model or "").strip()
    if not model:
        if cfg.gemini_api_keys:
            model_name = cfg.gemini_model or "gemini-3.1-pro-preview"
            model = model_name if "/" in model_name else f"gemini/{model_name}"
        elif cfg.anthropic_api_keys:
            model = f"anthropic/{cfg.anthropic_model or 'claude-sonnet-4-6'}"
        elif cfg.openai_api_keys:
            model = f"openai/{cfg.openai_model or 'gpt-5.5'}"
        else:
            return ""
    return model


def _get_api_keys_for_model(model: str, cfg: Config) -> List[str]:
    """Return available API keys for the given litellm model."""
    if model.startswith("gemini/") or model.startswith("vertex_ai/"):
        return [k for k in cfg.gemini_api_keys if k and len(k) >= 8]
    if model.startswith("anthropic/"):
        return [k for k in cfg.anthropic_api_keys if k and len(k) >= 8]
    return [k for k in cfg.openai_api_keys if k and len(k) >= 8]


def _call_litellm_vision(image_b64: str, mime_type: str, api_key: Optional[str] = None) -> str:
    """Extract stock codes from an image using litellm."""
    global litellm
    cfg = get_config()
    model = _resolve_vision_model()
    if not model:
        raise ValueError("Vision API가 설정되지 않았습니다. LITELLM_MODEL 또는 API 키를 확인하세요.")

    keys = _get_api_keys_for_model(model, cfg)
    if not keys:
        raise ValueError(f"No API key found for vision model {model}")
    key = api_key if api_key and api_key in keys else random.choice(keys)

    data_url = f"data:{mime_type};base64,{image_b64}"
    call_kwargs: dict = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACT_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": 1024,
        "api_key": key,
        "timeout": VISION_API_TIMEOUT,
    }

    if not model.startswith(("gemini/", "anthropic/", "vertex_ai/")):
        if cfg.openai_base_url:
            call_kwargs["api_base"] = cfg.openai_base_url
        if cfg.openai_base_url and "aihubmix.com" in cfg.openai_base_url:
            call_kwargs["extra_headers"] = {"APP-Code": "GPIJ3886"}

    if getattr(litellm, "completion", None) is None:
        import litellm as litellm_module

        litellm = litellm_module
    response = litellm.completion(**call_kwargs)
    if response and response.choices and response.choices[0].message.content:
        return response.choices[0].message.content
    raise ValueError("LiteLLM vision returned empty response")


def extract_stock_codes_from_image(
    image_bytes: bytes,
    mime_type: str,
) -> Tuple[List[Tuple[str, Optional[str], str]], str]:
    """Extract stock codes and optional names from an image with a Vision LLM."""
    mime_type = (mime_type or "image/jpeg").strip().lower().split(";")[0].strip()
    if mime_type not in ALLOWED_MIME:
        raise ValueError(f"지원하지 않는 이미지 형식입니다: {mime_type}. 허용 형식: {list(ALLOWED_MIME)}")

    if not image_bytes:
        raise ValueError("이미지 내용이 비어 있습니다.")

    if len(image_bytes) > MAX_SIZE_BYTES:
        raise ValueError(f"Image too large (max {MAX_SIZE_BYTES // (1024 * 1024)}MB)")

    _verify_image_magic_bytes(image_bytes, mime_type)

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    model = _resolve_vision_model()
    keys = _get_api_keys_for_model(model, get_config())

    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            key = random.choice(keys) if keys else None
            raw = _call_litellm_vision(image_b64, mime_type, api_key=key)
            logger.debug("[ImageExtractor] raw LLM response:\n%s", raw)
            items = _parse_items_from_text(raw)
            logger.info(
                "[ImageExtractor] %s extracted %d items: %s%s",
                model,
                len(items),
                [(i[0], i[1]) for i in items[:5]],
                "..." if len(items) > 5 else "",
            )
            return items, raw
        except Exception as e:
            last_error = e
            if attempt < 2:
                delay = 2 ** attempt
                logger.warning("[ImageExtractor] attempt %d/3 failed; retry in %ss: %s", attempt + 1, delay, e)
                time.sleep(delay)

    raise ValueError(f"Vision API 호출에 실패했습니다. API 키와 네트워크를 확인하세요: {last_error}") from last_error
