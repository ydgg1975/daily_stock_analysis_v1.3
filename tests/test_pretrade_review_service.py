# -*- coding: utf-8 -*-
"""Resilience tests for the optional, advisory-only PreTradeReviewService.

Covers the paths the pipeline relies on: the service must NEVER raise and must
degrade to {"status": "review_unavailable", ...} when unconfigured, given an
empty action, on timeout/network error, on a non-2xx status, on a non-JSON body,
and on a response missing the verdict. Only a well-formed 200 yields status "ok".
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import requests

from src.services.pretrade_review_service import PreTradeReviewService


def _resp(status_code=200, json_obj=None, raise_on_json=False):
    def _json():
        if raise_on_json:
            raise ValueError("not json")
        return json_obj if json_obj is not None else {}
    return SimpleNamespace(status_code=status_code, json=_json)


class TestPreTradeReviewServiceResilience(unittest.TestCase):
    def test_not_configured_returns_unavailable_without_network(self):
        svc = PreTradeReviewService(api_key=None)
        self.assertFalse(svc.is_available)
        out = svc.review(action="OPEN long 600519 at 1680")
        self.assertEqual(out["status"], "review_unavailable")
        self.assertEqual(out["reason"], "not_configured")

    def test_empty_action_returns_unavailable(self):
        svc = PreTradeReviewService(api_key="k")
        self.assertTrue(svc.is_available)
        self.assertEqual(svc.review(action="")["reason"], "empty_action")
        self.assertEqual(svc.review(action="   ")["reason"], "empty_action")

    def test_ok_passes_verdict_through(self):
        svc = PreTradeReviewService(api_key="k")
        payload = {"verdict": "approve_with_concerns", "confidence": 0.75,
                   "issues": [{"severity": "medium", "msg": "x"}], "proof": {"sig": "..."}}
        with patch("src.services.pretrade_review_service._post_with_retry",
                   return_value=_resp(200, payload)) as post:
            out = svc.review(action="OPEN long 600519 at 1680", context="equity ~100k")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["verdict"], "approve_with_concerns")
        self.assertEqual(out["confidence"], 0.75)
        self.assertEqual(len(out["issues"]), 1)
        self.assertIn("proof", out)
        # sends the CANONICAL /review contract: artifact (not action) + artifact_type=trade
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent["artifact"], "OPEN long 600519 at 1680")
        self.assertEqual(sent["artifact_type"], "trade")
        self.assertNotIn("action", sent)
        self.assertEqual(sent["context"], "equity ~100k")

    def test_non_2xx_returns_unavailable(self):
        svc = PreTradeReviewService(api_key="k")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   return_value=_resp(500, {})):
            out = svc.review(action="a")
        self.assertEqual(out["status"], "review_unavailable")
        self.assertEqual(out["reason"], "http_500")

    def test_invalid_json_returns_unavailable(self):
        svc = PreTradeReviewService(api_key="k")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   return_value=_resp(200, raise_on_json=True)):
            out = svc.review(action="a")
        self.assertEqual(out["reason"], "invalid_response")

    def test_missing_verdict_returns_unavailable(self):
        svc = PreTradeReviewService(api_key="k")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   return_value=_resp(200, {"confidence": 0.5})):
            out = svc.review(action="a")
        self.assertEqual(out["reason"], "invalid_response")

    def test_unrecognized_verdict_returns_unavailable(self):
        """A truthy-but-invalid verdict must NOT pass as a valid advisory."""
        svc = PreTradeReviewService(api_key="k")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   return_value=_resp(200, {"verdict": "looks_fine_to_me"})):
            out = svc.review(action="a")
        self.assertEqual(out["status"], "review_unavailable")
        self.assertEqual(out["reason"], "invalid_verdict")

    def test_valid_verdict_is_normalized_lowercase(self):
        svc = PreTradeReviewService(api_key="k")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   return_value=_resp(200, {"verdict": "REJECT"})):
            out = svc.review(action="a")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["verdict"], "reject")

    def test_malformed_issues_or_proof_returns_unavailable(self):
        svc = PreTradeReviewService(api_key="k")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   return_value=_resp(200, {"verdict": "approve", "issues": "not-a-list"})):
            self.assertEqual(svc.review(action="a")["reason"], "invalid_response")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   return_value=_resp(200, {"verdict": "approve", "proof": "not-an-object"})):
            self.assertEqual(svc.review(action="a")["reason"], "invalid_response")

    def test_timeout_returns_unavailable_and_never_raises(self):
        svc = PreTradeReviewService(api_key="k")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   side_effect=requests.exceptions.Timeout("slow")):
            out = svc.review(action="a")
        self.assertEqual(out["reason"], "network_error")

    def test_unexpected_error_returns_unavailable(self):
        svc = PreTradeReviewService(api_key="k")
        with patch("src.services.pretrade_review_service._post_with_retry",
                   side_effect=RuntimeError("boom")):
            out = svc.review(action="a")
        self.assertEqual(out["reason"], "unexpected_error")


if __name__ == "__main__":
    unittest.main()
