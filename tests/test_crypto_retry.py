# -*- coding: utf-8 -*-
"""Tests for retry/backoff in crypto_launch_fetcher."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from unittest.mock import patch, MagicMock
import requests
from data_provider.crypto_launch_fetcher import CryptoLaunchFetcher, NormalizedLaunch


@pytest.mark.not_network
class TestRetryBackoff:

    def setup_method(self):
        self.fetcher = CryptoLaunchFetcher()

    @patch("data_provider.crypto_launch_fetcher.requests.get")
    @patch("data_provider.crypto_launch_fetcher.time.sleep")
    def test_discover_retries_on_failure_then_succeeds(self, mock_sleep, mock_get):
        fail_resp = MagicMock()
        fail_resp.raise_for_status.side_effect = requests.RequestException("timeout")
        success_resp = MagicMock()
        success_resp.raise_for_status.return_value = None
        success_resp.json.return_value = {"data": []}
        mock_get.side_effect = [fail_resp, fail_resp, success_resp]

        result = self.fetcher.discover(
            ["bsc"], timeout_sec=5,
            max_retries=2, initial_backoff_sec=1.0, backoff_multiplier=2.0,
        )
        assert "bsc" in result
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    @patch("data_provider.crypto_launch_fetcher.requests.get")
    @patch("data_provider.crypto_launch_fetcher.time.sleep")
    def test_discover_exhausts_retries(self, mock_sleep, mock_get):
        fail_resp = MagicMock()
        fail_resp.raise_for_status.side_effect = requests.RequestException("timeout")
        mock_get.return_value = fail_resp

        result = self.fetcher.discover(
            ["bsc"], max_retries=2, initial_backoff_sec=0.5, backoff_multiplier=2.0,
        )
        assert "bsc" not in result
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("data_provider.crypto_launch_fetcher.requests.get")
    def test_discover_no_retry_by_default(self, mock_get):
        fail_resp = MagicMock()
        fail_resp.raise_for_status.side_effect = requests.RequestException("fail")
        mock_get.return_value = fail_resp

        result = self.fetcher.discover(["bsc"])
        assert mock_get.call_count == 1

    @patch("data_provider.crypto_launch_fetcher.requests.get")
    @patch("data_provider.crypto_launch_fetcher.time.sleep")
    def test_enrich_retries_on_failure(self, mock_sleep, mock_get):
        launch = NormalizedLaunch(chain_id="bsc", pair_address="0xabc")
        fail_resp = MagicMock()
        fail_resp.raise_for_status.side_effect = requests.RequestException("err")
        success_resp = MagicMock()
        success_resp.raise_for_status.return_value = None
        success_resp.json.return_value = {"pairs": []}
        mock_get.side_effect = [fail_resp, success_resp]

        self.fetcher.enrich(
            [launch], timeout_sec=5,
            max_retries=1, initial_backoff_sec=0.5, backoff_multiplier=2.0,
        )
        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1
