# -*- coding: utf-8 -*-
"""
推荐选股服务单元测试
"""
import json
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

json_repair = pytest.importorskip("json_repair")

class TestRecommendationServiceParsing:
    """测试 LLM 响应解析逻辑"""

    def _get_service(self):
        from src.services.recommendation_service import RecommendationService
        return RecommendationService()

    def test_parse_valid_json(self):
        svc = self._get_service()
        candidates = [
            {"code": "600519", "name": "贵州茅台", "market": "a_share", "price": 1800},
            {"code": "000858", "name": "五粮液", "market": "a_share", "price": 150},
        ]
        raw = json.dumps({
            "stocks": [
                {"code": "600519", "name": "贵州茅台", "score": 85, "reason": "白酒龙头", "risk": "估值偏高"},
            ],
            "analysis_summary": "白酒板块表现强劲"
        })
        result = svc._parse_response(raw, candidates)
        assert len(result["stocks"]) == 1
        assert result["stocks"][0]["code"] == "600519"
        assert result["analysis_summary"] == "白酒板块表现强劲"

    def test_parse_json_in_code_block(self):
        svc = self._get_service()
        candidates = [
            {"code": "AAPL", "name": "Apple", "market": "us", "price": 180},
        ]
        raw = """Some analysis text.
```json
{
    "stocks": [
        {"code": "AAPL", "name": "Apple", "score": 90, "reason": "Strong earnings"}
    ],
    "analysis_summary": "US market bullish"
}
```
"""
        result = svc._parse_response(raw, candidates)
        assert len(result["stocks"]) == 1
        assert result["stocks"][0]["code"] == "AAPL"

    def test_filter_out_invalid_codes(self):
        svc = self._get_service()
        candidates = [
            {"code": "600519", "name": "贵州茅台", "market": "a_share", "price": 1800},
        ]
        raw = json.dumps({
            "stocks": [
                {"code": "600519", "name": "贵州茅台", "score": 85, "reason": "OK"},
                {"code": "999999", "name": "不存在", "score": 70, "reason": "Fake"},
            ],
            "analysis_summary": "Test"
        })
        result = svc._parse_response(raw, candidates)
        assert len(result["stocks"]) == 1
        assert result["stocks"][0]["code"] == "600519"

    def test_max_5_stocks(self):
        svc = self._get_service()
        candidates = [{"code": f"00{i:04d}", "name": f"S{i}", "market": "a_share", "price": 10} for i in range(10)]
        raw = json.dumps({
            "stocks": [{"code": f"00{i:04d}", "name": f"S{i}", "score": 80} for i in range(10)],
            "analysis_summary": "Test"
        })
        result = svc._parse_response(raw, candidates)
        assert len(result["stocks"]) <= 5

    def test_parse_malformed_json(self):
        svc = self._get_service()
        candidates = [{"code": "600519", "name": "贵州茅台", "market": "a_share", "price": 1800}]
        # Completely broken JSON
        raw = "This is not valid JSON at all {{{}"
        result = svc._parse_response(raw, candidates)
        assert "stocks" in result


class TestRecommendationServicePrompt:
    """测试 Prompt 构建"""

    def test_build_prompt_basic(self):
        from src.services.recommendation_service import RecommendationService
        svc = RecommendationService()
        candidates = [
            {"code": "600519", "name": "贵州茅台", "market": "a_share", "price": 1800,
             "change_pct": 2.5, "amount": 5e9, "pe": 35.2, "market_cap": 2.2e12},
        ]
        prompt = svc._build_prompt(
            markets=["a_share"],
            price_min=10,
            price_max=2000,
            user_context="关注白酒板块",
            news_context="白酒涨停",
            candidates=candidates,
        )
        assert "A股" in prompt
        assert "600519" in prompt
        assert "贵州茅台" in prompt
        assert "白酒板块" in prompt
        assert "白酒涨停" in prompt
        assert "10 ~ 2000" in prompt

    def test_format_amount(self):
        from src.services.recommendation_service import RecommendationService
        assert RecommendationService._format_amount(5e9) == "50.0亿"
        assert RecommendationService._format_amount(1e6) == "100万"
        assert RecommendationService._format_amount(500) == "500"
        assert RecommendationService._format_amount(None) == "-"

    def test_format_cap(self):
        from src.services.recommendation_service import RecommendationService
        assert RecommendationService._format_cap(2.2e12) == "2.2万亿"
        assert RecommendationService._format_cap(5e10) == "500亿"
        assert RecommendationService._format_cap(None) == "-"


class TestTaskManager:
    """测试任务管理器"""

    def test_singleton(self):
        from src.services.recommendation_service import RecommendationTaskManager
        mgr1 = RecommendationTaskManager.get_instance()
        mgr2 = RecommendationTaskManager.get_instance()
        assert mgr1 is mgr2

    def test_get_nonexistent_status(self):
        from src.services.recommendation_service import RecommendationTaskManager
        mgr = RecommendationTaskManager.get_instance()
        assert mgr.get_status("nonexistent_task_12345") is None
