# -*- coding: utf-8 -*-
"""Unit tests for report language helpers."""

import unittest

from src.report_language import (
    get_bias_status_emoji,
    get_localized_stock_name,
    get_sentiment_label,
    get_signal_level,
    infer_decision_type_from_advice,
    localize_trend_prediction,
    localize_bias_status,
)


class ReportLanguageTestCase(unittest.TestCase):
    def test_get_signal_level_handles_compound_sell_advice(self) -> None:
        signal_text, emoji, signal_tag = get_signal_level("maichu/guanwang", 60, "zh")

        self.assertEqual(signal_text, "maichu")
        self.assertEqual(emoji, "🔴")
        self.assertEqual(signal_tag, "sell")

    def test_get_signal_level_handles_compound_buy_advice_in_english(self) -> None:
        signal_text, emoji, signal_tag = get_signal_level("Buy / Watch", 40, "en")

        self.assertEqual(signal_text, "Buy")
        self.assertEqual(emoji, "🟢")
        self.assertEqual(signal_tag, "buy")

    def test_get_localized_stock_name_replaces_placeholder_for_english(self) -> None:
        self.assertEqual(
            get_localized_stock_name("gupiaoAAPL", "AAPL", "en"),
            "Unnamed Stock",
        )

    def test_get_sentiment_label_preserves_higher_band_thresholds(self) -> None:
        self.assertEqual(get_sentiment_label(80, "en"), "Very Bullish")
        self.assertEqual(get_sentiment_label(60, "en"), "Bullish")
        self.assertEqual(get_sentiment_label(40, "zh"), "zhongxing")
        self.assertEqual(get_sentiment_label(20, "zh"), "beiguan")

    def test_localize_trend_prediction_preserves_fine_grain_zh_states(self) -> None:
        self.assertEqual(localize_trend_prediction("duotoupailie", "zh"), "duotoupailie")
        self.assertEqual(localize_trend_prediction("ruoshikongtou", "zh"), "ruoshikongtou")

    def test_localize_trend_prediction_still_translates_english_input_for_zh(self) -> None:
        self.assertEqual(localize_trend_prediction("bullish", "zh"), "kanduo")
        self.assertEqual(localize_trend_prediction("very bearish", "zh"), "qiangliekankong")

    def test_bias_status_helpers_support_english_values(self) -> None:
        self.assertEqual(localize_bias_status("Safe", "en"), "Safe")
        self.assertEqual(localize_bias_status("jingjie", "en"), "Caution")
        self.assertEqual(get_bias_status_emoji("Safe"), "✅")
        self.assertEqual(get_bias_status_emoji("Caution"), "⚠️")

    def test_infer_decision_type_from_advice_matches_chinese_phrases(self) -> None:
        self.assertEqual(infer_decision_type_from_advice("jianyimairu"), "buy")
        self.assertEqual(infer_decision_type_from_advice("jianyichiyou"), "hold")
        self.assertEqual(infer_decision_type_from_advice("jianyijiancang"), "sell")
        self.assertEqual(infer_decision_type_from_advice("jixuchiyou"), "hold")
        self.assertEqual(infer_decision_type_from_advice("jianyixipanguancha"), "hold")
        self.assertEqual(infer_decision_type_from_advice("xipanguancha", default=""), "hold")
        self.assertEqual(infer_decision_type_from_advice("guancha", default=""), "hold")
        self.assertEqual(infer_decision_type_from_advice("bujianyimairu"), "hold")
        self.assertEqual(
            infer_decision_type_from_advice("dangqianbudiepozhichengweijixuchiyou"),
            "hold",
        )
        self.assertEqual(
            infer_decision_type_from_advice("bupozhichenghourengkechiyou"),
            "hold",
        )


if __name__ == "__main__":
    unittest.main()
