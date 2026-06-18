# -*- coding: utf-8 -*-
"""
===================================
Pre-Trade Review Service (optional, advisory-only)
===================================

Sends a proposed trade action to an external capital-aware ``/review`` endpoint
and returns an advisory verdict (``approve`` / ``approve_with_concerns`` /
``reject``) plus an issues list and an independently-verifiable signed proof.

OPTIONAL and DEFAULT-OFF. Requires ``PRE_TRADE_REVIEW_ENABLED=true`` and
``PRE_TRADE_REVIEW_API_KEY``. This service NEVER alters the analysis BUY/SELL
conclusion — it only appends advisory metadata. On any error, timeout, non-2xx
status, or invalid response it returns ``{"status": "review_unavailable", ...}``
and NEVER raises, so the analysis pipeline never blocks on it.

Privacy: only the explicitly-passed ``action`` / ``context`` strings are sent.
No account credentials, balances, or positions are required — ``context`` can be
coarse (e.g. "equity ~100k CNY, position 5%") or omitted entirely.

Default endpoint: https://api.babyblueviper.com/review (configurable via
``PRE_TRADE_REVIEW_ENDPOINT``). The returned proof is verifiable by anyone, with
no auth, at POST /verify-proof — so an end user can confirm the verdict is
genuine without trusting either project.
"""

import logging
from typing import Any, Dict, Optional

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

_TRANSIENT_EXCEPTIONS = (
    requests.exceptions.SSLError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)

# A conformant verdict must be one of these; anything else is treated as a malformed
# response and degraded to review_unavailable (the contract is a real advisory or nothing).
_VALID_VERDICTS = frozenset({"approve", "approve_with_concerns", "reject"})

_DEFAULT_ENDPOINT = "https://api.babyblueviper.com/review"
_DEFAULT_TIMEOUT = 8  # seconds — short on purpose; advisory must never stall the pipeline


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type(_TRANSIENT_EXCEPTIONS),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _post_with_retry(url: str, *, headers: Dict[str, str], json: Dict[str, Any],
                     timeout: int = _DEFAULT_TIMEOUT) -> requests.Response:
    """POST with retry on transient network errors only."""
    return requests.post(url, headers=headers, json=json, timeout=timeout)


class PreTradeReviewService:
    """
    Optional, advisory-only pre-trade review.

    Usage::

        svc = PreTradeReviewService(api_key="...", endpoint="https://api.babyblueviper.com/review")
        if svc.is_available:
            advisory = svc.review(
                action="OPEN long 600519.SH at 1680 CNY, position 5% of portfolio",
                context="signal: MA cross + sentiment positive; equity ~100k CNY",
            )
            # advisory == {"status": "ok", "verdict": "approve_with_concerns",
            #              "confidence": 0.75, "issues": [...], "proof": {...}}
            # or {"status": "review_unavailable", "reason": "..."} on any failure.
    """

    def __init__(self, api_key: Optional[str] = None, endpoint: str = _DEFAULT_ENDPOINT,
                 timeout: int = _DEFAULT_TIMEOUT, sign: bool = True):
        self._api_key = (api_key or "").strip() or None
        self._endpoint = (endpoint or _DEFAULT_ENDPOINT).rstrip("/")
        try:
            self._timeout = int(timeout) if timeout else _DEFAULT_TIMEOUT
        except (TypeError, ValueError):
            self._timeout = _DEFAULT_TIMEOUT
        self._sign = bool(sign)

    @property
    def is_available(self) -> bool:
        """True only when an API key is configured (gates all network calls)."""
        return self._api_key is not None

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key or ''}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def review(self, action: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Request an advisory verdict on a proposed action. NEVER raises.

        Returns either::

            {"status": "ok", "verdict": ..., "confidence": ..., "issues": [...], "proof": {...}}

        or, on any failure (unconfigured, empty action, timeout, non-2xx,
        invalid response)::

            {"status": "review_unavailable", "reason": "<short reason>"}
        """
        if not self.is_available:
            return {"status": "review_unavailable", "reason": "not_configured"}
        if not action or not str(action).strip():
            return {"status": "review_unavailable", "reason": "empty_action"}

        # Canonical /review contract: the thing to review is `artifact`; `artifact_type=trade`
        # selects the capital-scale-aware risk-manager review for a proposed entry/exit.
        payload: Dict[str, Any] = {
            "artifact": str(action),
            "artifact_type": "trade",
            "sign": self._sign,
        }
        if context:
            payload["context"] = str(context)

        try:
            resp = _post_with_retry(self._endpoint, headers=self._headers,
                                    json=payload, timeout=self._timeout)
        except _TRANSIENT_EXCEPTIONS as exc:
            logger.warning("Pre-trade review endpoint network error: %s", exc)
            return {"status": "review_unavailable", "reason": "network_error"}
        except Exception as exc:  # never let the advisory layer break the pipeline
            logger.warning("Pre-trade review endpoint unexpected error: %s", exc)
            return {"status": "review_unavailable", "reason": "unexpected_error"}

        if resp.status_code != 200:
            logger.warning("Pre-trade review endpoint returned HTTP %s", resp.status_code)
            return {"status": "review_unavailable", "reason": f"http_{resp.status_code}"}

        try:
            data = resp.json()
        except Exception:
            logger.warning("Pre-trade review endpoint returned a non-JSON response")
            return {"status": "review_unavailable", "reason": "invalid_response"}

        verdict = data.get("verdict") if isinstance(data, dict) else None
        if not verdict:
            logger.warning("Pre-trade review response missing 'verdict'")
            return {"status": "review_unavailable", "reason": "invalid_response"}
        # Validate the verdict is one of the known values — a malformed/garbage verdict
        # must not be surfaced as a valid advisory.
        if not isinstance(verdict, str) or verdict.lower() not in _VALID_VERDICTS:
            logger.warning("Pre-trade review returned an unrecognized verdict: %r", verdict)
            return {"status": "review_unavailable", "reason": "invalid_verdict"}

        # issues, when present, must be a list; proof, when present, must be an object —
        # otherwise the response is malformed and we don't pass it through as a real advisory.
        issues = data.get("issues")
        if issues is not None and not isinstance(issues, list):
            logger.warning("Pre-trade review 'issues' is not a list")
            return {"status": "review_unavailable", "reason": "invalid_response"}
        proof = data.get("proof")
        if proof is not None and not isinstance(proof, dict):
            logger.warning("Pre-trade review 'proof' is not an object")
            return {"status": "review_unavailable", "reason": "invalid_response"}

        return {
            "status": "ok",
            "verdict": verdict.lower(),
            "confidence": data.get("confidence"),
            "issues": issues or [],
            "proof": proof,
            "endpoint": self._endpoint,
        }
