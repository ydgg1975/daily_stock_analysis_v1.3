# -*- coding: utf-8 -*-
"""Tests for the bot /analyze command input parsing."""

import unittest
from unittest.mock import patch

from bot.commands.analyze import AnalyzeCommand


class AnalyzeCommandParsingTest(unittest.TestCase):
    def test_validate_args_accepts_stock_name(self):
        command = AnalyzeCommand()

        with patch("bot.commands.analyze.find_stock_reference", return_value=("002497", "雅化集团")):
            self.assertIsNone(command.validate_args(["雅化集团"]))
            self.assertEqual(command._resolve_code(["雅化集团"]), "002497")

    def test_validate_args_rejects_unknown_name_with_hint(self):
        command = AnalyzeCommand()

        with patch("bot.commands.analyze.find_stock_reference", return_value=None):
            error = command.validate_args(["雅化集团"])

        self.assertIn("股票名称", error)


if __name__ == "__main__":
    unittest.main()
