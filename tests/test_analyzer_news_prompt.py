# -*- coding: utf-8 -*-
"""Tests for analyzer news prompt hard constraints (Issue #697)."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    from tests.litellm_stub import ensure_litellm_stub

    ensure_litellm_stub()

from src.analyzer import (
    GeminiAnalyzer,
    _BULLISH_TREND_HINTS,
    _contains_trend_hint,
    _infer_trend_direction,
    _sanitize_trend_analysis_for_prompt,
)


class AnalyzerNewsPromptTestCase(unittest.TestCase):
    def test_contains_trend_hint_treats_non_adjacent_negation_as_negated(self) -> None:
        self.assertFalse(_contains_trend_hint("shangweixingchengshangshengqushi，jixuguancha。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("weixingchengshangshengqushi，jixuguancha。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("bingweixingchengshangshengqushi，jixuguancha。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("meiyouxingchengduotoupailie，jixuguancha。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("dangqianwuduotoupailie，rengxuguancha。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("shangbushuyushangshengqushi，fantanrengdaiqueren。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("dangqianfeiduotoupailie，rengxuguancha。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("This is not a bullish trend yet.", _BULLISH_TREND_HINTS))

    def test_contains_trend_hint_scans_later_non_negated_occurrences(self) -> None:
        self.assertTrue(
            _contains_trend_hint(
                "bushiduotoupailie，houxufanglianghouzaicichuxianduotoupailiexinhao。",
                _BULLISH_TREND_HINTS,
            )
        )

    def test_contains_trend_hint_keeps_contrast_clause_target_hint(self) -> None:
        self.assertTrue(_contains_trend_hint("bushikongtouershiduotoupailie，qushixiufu。", _BULLISH_TREND_HINTS))
        self.assertFalse(_contains_trend_hint("weizhuanweishangshengqushi，fantanrengdaiqueren。", _BULLISH_TREND_HINTS))

    def test_contains_trend_hint_ignores_single_character_prefixes_in_common_words(self) -> None:
        self.assertTrue(_contains_trend_hint("feichangmingxiandeduotoupailie，qushirengzaiyanxu。", _BULLISH_TREND_HINTS))
        self.assertTrue(_contains_trend_hint("weilaishangshengqushiruofangliangjiangjinyibuqueren。", _BULLISH_TREND_HINTS))
        self.assertEqual(
            _infer_trend_direction({"trend_status": "feichangmingxiandeduotoupailie", "ma_alignment": "weilaishangshengqushizhubumingque"}),
            "bullish",
        )

    def test_infer_trend_direction_recognizes_weak_bullish_and_bearish_states(self) -> None:
        self.assertEqual(
            _infer_trend_direction({"trend_status": "ruoshiduotou", "ma_alignment": "ruoshiduotou，MA5>MA10 dan MA10≤MA20"}),
            "bullish",
        )
        self.assertEqual(
            _infer_trend_direction({"trend_status": "ruoshikongtou", "ma_alignment": "ruoshikongtou，MA5<MA10 dan MA10≥MA20"}),
            "bearish",
        )

    def test_infer_trend_direction_ignores_negated_bullish_hints(self) -> None:
        self.assertEqual(
            _infer_trend_direction({"trend_status": "weixingchengshangshengqushi", "ma_alignment": "dangqianfeiduotoupailie"}),
            "neutral",
        )
        self.assertEqual(
            _infer_trend_direction({"trend_status": "meiyouxingchengduotoupailie", "ma_alignment": "dangqianwushangshengqushi"}),
            "neutral",
        )

    def test_infer_trend_direction_keeps_contrast_clause_final_direction(self) -> None:
        self.assertEqual(
            _infer_trend_direction({"trend_status": "bushikongtouershiduotoupailie", "ma_alignment": ""}),
            "bullish",
        )

    def test_analysis_prompt_resolves_shared_skill_prompt_state_by_default(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        fake_state = SimpleNamespace(
            skill_instructions="### jineng 1: boduandixi\n- guanzhuzhichengqueren",
            default_skill_policy="",
        )
        with patch("src.agent.factory.resolve_skill_prompt_state", return_value=fake_state):
            prompt = analyzer._get_analysis_system_prompt("zh", stock_code="600519")

        self.assertIn("### jineng 1: boduandixi", prompt)
        self.assertNotIn("zhuanzhuyuqushijiaoyi", prompt)

    def test_analysis_prompt_uses_injected_skill_sections_instead_of_hardcoded_trend_baseline(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### jineng 1: chanlun\n- guanzhuzhongshuyubeichi",
                default_skill_policy="",
            )

        prompt = analyzer._get_analysis_system_prompt("zh", stock_code="600519")

        self.assertIn("### jineng 1: chanlun", prompt)
        self.assertNotIn("zhuanzhuyuqushijiaoyi", prompt)
        self.assertNotIn("duotoupailie：MA5 > MA10 > MA20", prompt)

    def test_analysis_prompt_keeps_injected_default_policy_for_implicit_default_run(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### jineng 1: morenduotouqushi",
                default_skill_policy="## morenjinengjixian（bixuyangezunshou）\n- **duotoupailiebixutiaojian**：MA5 > MA10 > MA20",
                use_legacy_default_prompt=True,
            )

        prompt = analyzer._get_analysis_system_prompt("zh", stock_code="600519")

        self.assertIn("zhuanzhuyuqushijiaoyi", prompt)
        self.assertIn("duotoupailiebixutiaojian", prompt)
        self.assertIn("duotoupailie：MA5 > MA10 > MA20", prompt)

    def test_analysis_prompt_contains_actionability_guardrails(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        prompt = analyzer._get_analysis_system_prompt("zh", stock_code="002812")

        self.assertIn("kecaozuoxingyuwendingxingyueshu", prompt)
        self.assertIn("budejinyinweidanrizhangdie", prompt)
        self.assertIn("zhicheng/yaliwei", prompt)
        self.assertIn("xipanguancha", prompt)

    def test_prompt_contains_time_constraints(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "guizhoumaotai",
            "date": "2026-03-16",
            "today": {},
            "fundamental_context": {
                "earnings": {
                    "data": {
                        "financial_report": {"report_date": "2025-12-31", "revenue": 1000},
                        "dividend": {"ttm_cash_dividend_per_share": 1.2, "ttm_dividend_yield_pct": 2.4},
                    }
                }
            },
        }
        fake_cfg = SimpleNamespace(
            news_max_age_days=30,
            news_strategy_profile="medium",  # 7 days
        )
        with patch("src.analyzer.get_config", return_value=fake_cfg):
            prompt = analyzer._format_prompt(context, "guizhoumaotai", news_context="news")

        self.assertIn("jin7ridexinwensousuojieguo", prompt)
        self.assertIn("meiyitiaodoubixudaijutiriqi（YYYY-MM-DD）", prompt)
        self.assertIn("chaochujin7richuangkoudexinwenyilvhulve", prompt)
        self.assertIn("shijianweizhi、wufaquedingfaburiqidexinwenyilvhulve", prompt)
        self.assertIn("caibaoyufenhong（jiazhitouzikoujing）", prompt)
        self.assertIn("jinzhibianzao", prompt)

    def test_prompt_includes_capital_flow_as_operation_filter(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "002812",
            "stock_name": "enjiegufen",
            "date": "2026-04-01",
            "today": {"close": 32.8, "ma5": 31.2, "ma10": 30.5, "ma20": 29.8},
            "fundamental_context": {
                "capital_flow": {
                    "status": "ok",
                    "data": {
                        "stock_flow": {
                            "main_net_inflow": -1200000,
                            "inflow_5d": -3600000,
                            "inflow_10d": -5200000,
                        },
                        "sector_rankings": {
                            "top": [{"name": "dianchi"}],
                            "bottom": [{"name": "huagong"}],
                        },
                    },
                }
            },
        }

        prompt = analyzer._format_prompt(context, "enjiegufen", news_context=None)

        self.assertIn("zhulizijinliuxiang（caozuojianyiguolvqi）", prompt)
        self.assertIn("zhulijingliuru", prompt)
        self.assertIn("-1200000", prompt)
        self.assertIn("jiejinyaliqiezhuliliuchushibudezhuimai", prompt)
        self.assertIn("xipanguancha", prompt)

    def test_prompt_prefers_context_news_window_days(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer()

        context = {
            "code": "600519",
            "stock_name": "guizhoumaotai",
            "date": "2026-03-16",
            "today": {},
            "news_window_days": 1,
        }
        fake_cfg = SimpleNamespace(
            news_max_age_days=30,
            news_strategy_profile="long",  # 30 days if fallback is used
        )
        with patch("src.analyzer.get_config", return_value=fake_cfg):
            prompt = analyzer._format_prompt(context, "guizhoumaotai", news_context="news")

        self.assertIn("jin1ridexinwensousuojieguo", prompt)
        self.assertIn("chaochujin1richuangkoudexinwenyilvhulve", prompt)

    def test_format_prompt_omits_legacy_trend_checks_for_nondefault_skill_mode(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### jineng 1: chanlun\n- guanzhuzhongshuyubeichi",
                default_skill_policy="",
                use_legacy_default_prompt=False,
            )

        context = {
            "code": "600519",
            "stock_name": "guizhoumaotai",
            "date": "2026-03-16",
            "today": {"close": 100, "ma5": 99, "ma10": 98, "ma20": 97},
            "trend_analysis": {
                "trend_status": "zhendangpianqiang",
                "ma_alignment": "zhanhehoufasan",
                "trend_strength": 61,
                "bias_ma5": 1.2,
                "bias_ma10": 2.4,
                "volume_status": "pingliang",
                "volume_trend": "liangnengwenhe",
                "buy_signal": "guancha",
                "signal_score": 58,
                "signal_reasons": ["jiegoudaiqueren"],
                "risk_factors": ["wubeichiqueren"],
            },
        }
        prompt = analyzer._format_prompt(context, "guizhoumaotai", news_context=None)

        self.assertIn("dangqianjiegoushifoumanzujihuojinengdeguanjianchufatiaojian", prompt)
        self.assertNotIn("shifoumanzu MA5>MA10>MA20 duotoupailie", prompt)
        self.assertNotIn("chaoguo5%bixubiaozhu\"yanjinzhuigao\"", prompt)
        self.assertNotIn("MA5>MA10>MA20weiduotou", prompt)

    def test_format_prompt_removes_bullish_reasons_when_final_trend_is_bearish(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### jineng 1: chanlun\n- guanzhuzhongshuyubeichi",
                default_skill_policy="",
                use_legacy_default_prompt=False,
            )

        context = {
            "code": "603259",
            "stock_name": "yaomingkangde",
            "date": "2026-04-28",
            "today": {"close": 58.6, "ma5": 57.2, "ma10": 58.8, "ma20": 60.4},
            "yesterday": {"close": 57.8},
            "volume_change_ratio": 12.4,
            "trend_analysis": {
                "trend_status": "kongtoupailie",
                "ma_alignment": "kongtoupailie MA5<MA10<MA20",
                "trend_strength": 34,
                "bias_ma5": 2.1,
                "bias_ma10": -0.8,
                "volume_status": "fangliang",
                "volume_trend": "fangliangzhendang",
                "buy_signal": "guancha",
                "signal_score": 41,
                "signal_reasons": ["duotoupailie，chixushangzhang", "shijiancuihuacunzaidanjishudaiqueren"],
                "risk_factors": ["diepoMA20，qushichengya"],
            },
        }

        prompt = analyzer._format_prompt(
            context,
            "yaomingkangde",
            news_context="2026-04-27 yijibaochaoyuqi，dingdanzengzhang。",
        )

        self.assertIn("kongtoupailie MA5<MA10<MA20", prompt)
        self.assertNotIn("duotoupailie，chixushangzhang", prompt)
        self.assertIn("shijiancuihuacunzaidanjishudaiqueren", prompt)
        self.assertIn("shijianxianxing、jishudaiqueren", prompt)
        self.assertIn("liangnengyichangtishi", prompt)
        self.assertIn("jishumianyizhixing", prompt)

    def test_format_prompt_removes_bearish_risks_when_final_trend_is_bullish(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### jineng 1: chanlun\n- guanzhuzhongshuyubeichi",
                default_skill_policy="",
                use_legacy_default_prompt=False,
            )

        context = {
            "code": "600519",
            "stock_name": "guizhoumaotai",
            "date": "2026-04-28",
            "today": {"close": 1688.0, "ma5": 1675.0, "ma10": 1660.0, "ma20": 1640.0},
            "trend_analysis": {
                "trend_status": "duotoupailie",
                "ma_alignment": "duotoupailie MA5>MA10>MA20",
                "trend_strength": 78,
                "bias_ma5": 1.8,
                "bias_ma10": 3.2,
                "volume_status": "pingliang",
                "volume_trend": "liangjiapeihe",
                "buy_signal": "pianqiang",
                "signal_score": 73,
                "signal_reasons": ["duotoupailie，chixushangzhang", "kongtoupailie，chixuxiadie"],
                "risk_factors": ["kongtoupailie，chixuxiadie", "caibaopiluqianbodongkenengfangda"],
            },
        }

        prompt = analyzer._format_prompt(context, "guizhoumaotai", news_context=None)

        self.assertIn("duotoupailie MA5>MA10>MA20", prompt)
        self.assertIn("caibaopiluqianbodongkenengfangda", prompt)
        self.assertNotIn("kongtoupailie，chixuxiadie\n", prompt)
        self.assertNotIn("kongtoupailie，chixuxiadie", prompt)
        self.assertIn("yitichuyuduotouzhupanduanzhijiechongtudekongtoujiegouliyou", prompt)
        self.assertIn("yitichuyuduotouzhupanduanzhijiechongtudekongtoujiegoufengxianbiaoshu", prompt)

    def test_format_prompt_removes_bullish_reasons_when_final_trend_is_weak_bearish(self) -> None:
        with patch.object(GeminiAnalyzer, "_init_litellm", return_value=None):
            analyzer = GeminiAnalyzer(
                skill_instructions="### jineng 1: chanlun\n- guanzhuzhongshuyubeichi",
                default_skill_policy="",
                use_legacy_default_prompt=False,
            )

        context = {
            "code": "300750",
            "stock_name": "ningdeshidai",
            "date": "2026-04-28",
            "today": {"close": 178.5, "ma5": 176.0, "ma10": 180.2, "ma20": 179.9},
            "trend_analysis": {
                "trend_status": "ruoshikongtou",
                "ma_alignment": "ruoshikongtou，MA5<MA10 dan MA10≥MA20",
                "trend_strength": 43,
                "bias_ma5": 1.4,
                "bias_ma10": -0.9,
                "volume_status": "pingliang",
                "volume_trend": "liangnengyiban",
                "buy_signal": "guancha",
                "signal_score": 45,
                "signal_reasons": ["ruoshiduotouxiufu", "duotoupailie，chixushangzhang", "shijiancuihuacunzaidanjishudaiqueren"],
                "risk_factors": ["MA10 yazhirengzai"],
            },
        }

        prompt = analyzer._format_prompt(
            context,
            "ningdeshidai",
            news_context="2026-04-27 xinchanpinfabu，shichangqingxuhuinuan。",
        )

        self.assertIn("ruoshikongtou，MA5<MA10 dan MA10≥MA20", prompt)
        self.assertNotIn("ruoshiduotouxiufu", prompt)
        self.assertNotIn("duotoupailie，chixushangzhang", prompt)
        self.assertIn("shijiancuihuacunzaidanjishudaiqueren", prompt)
        self.assertIn("yitichuyukongtouzhupanduanzhijiechongtudekanduojiegouliyou", prompt)

    def test_sanitize_trend_analysis_for_prompt_returns_derived_copy_only(self) -> None:
        original = {
            "trend_status": "kongtoupailie",
            "ma_alignment": "kongtoupailie MA5<MA10<MA20",
            "signal_reasons": ["duotoupailie，chixushangzhang", "shijiancuihuacunzaidanjishudaiqueren"],
            "risk_factors": ["diepoMA20，qushichengya"],
        }

        sanitized = _sanitize_trend_analysis_for_prompt(original, volume_change_ratio=12.4)

        self.assertEqual(
            original["signal_reasons"],
            ["duotoupailie，chixushangzhang", "shijiancuihuacunzaidanjishudaiqueren"],
        )
        self.assertNotIn("prompt_consistency_notes", original)
        self.assertNotIn("prompt_trend_direction", original)
        self.assertNotIn("duotoupailie，chixushangzhang", sanitized["signal_reasons"])
        self.assertEqual(sanitized["prompt_trend_direction"], "bearish")


if __name__ == "__main__":
    unittest.main()
