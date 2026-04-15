# -*- coding: utf-8 -*-
"""Tests for normalized provider credential resolution."""

from __future__ import annotations

import unittest

from data_provider.provider_credentials import get_provider_credentials


class ProviderCredentialsTestCase(unittest.TestCase):
    def test_resolves_twelve_data_as_single_key_provider(self) -> None:
        credentials = get_provider_credentials(
            "twelve_data",
            config={
                "twelve_data_api_keys": ["td-primary", "td-secondary"],
                "twelve_data_api_key": "legacy-td-key",
            },
        )

        self.assertEqual(credentials.provider, "twelve_data")
        self.assertEqual(credentials.auth_mode, "single_key")
        self.assertTrue(credentials.is_configured)
        self.assertFalse(credentials.is_partial)
        self.assertEqual(credentials.primary_api_key, "td-primary")
        self.assertEqual(credentials.api_keys, ("td-primary", "td-secondary", "legacy-td-key"))

    def test_resolves_alpaca_as_key_secret_provider(self) -> None:
        credentials = get_provider_credentials(
            "alpaca",
            config={
                "alpaca_api_key_id": "alpaca-key-id",
                "alpaca_api_secret_key": "alpaca-secret",
                "alpaca_data_feed": "sip",
            },
        )

        self.assertEqual(credentials.provider, "alpaca")
        self.assertEqual(credentials.auth_mode, "key_secret")
        self.assertTrue(credentials.is_configured)
        self.assertFalse(credentials.is_partial)
        self.assertEqual(credentials.key_id, "alpaca-key-id")
        self.assertEqual(credentials.secret_key, "alpaca-secret")
        self.assertEqual(credentials.extras["data_feed"], "sip")

    def test_marks_partial_alpaca_credentials_as_incomplete(self) -> None:
        credentials = get_provider_credentials(
            "alpaca",
            config={
                "alpaca_api_key_id": "alpaca-key-id",
                "alpaca_api_secret_key": "",
            },
        )

        self.assertFalse(credentials.is_configured)
        self.assertTrue(credentials.is_partial)
        self.assertEqual(credentials.missing_fields, ("secret_key",))


if __name__ == "__main__":
    unittest.main()
