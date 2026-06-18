# -*- coding: utf-8 -*-
"""Regression tests for optional pipeline service degradation logs."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.core.pipeline import StockAnalysisPipeline


def _make_config() -> SimpleNamespace:
    return SimpleNamespace(
        max_workers=2,
        save_context_snapshot=False,
        bocha_api_keys=[],
        tavily_api_keys=[],
        brave_api_keys=[],
        serpapi_keys=[],
        minimax_api_keys=[],
        searxng_base_urls=[],
        searxng_public_instances_enabled=False,
        news_max_age_days=7,
        news_strategy_profile="short",
        enable_realtime_quote=False,
        realtime_source_priority=[],
        enable_chip_distribution=False,
        social_sentiment_api_key="",
        social_sentiment_api_url="https://example.invalid/social",
    )


def _build_pipeline(config: SimpleNamespace) -> StockAnalysisPipeline:
    with patch("src.core.pipeline.get_db", return_value=MagicMock()), \
         patch("src.core.pipeline.DataFetcherManager", return_value=MagicMock()), \
         patch("src.core.pipeline.StockTrendAnalyzer", return_value=MagicMock()), \
         patch("src.core.pipeline.GeminiAnalyzer", return_value=MagicMock()), \
         patch("src.core.pipeline.NotificationService", return_value=MagicMock()):
        return StockAnalysisPipeline(config=config)


def test_search_service_init_failure_logs_traceback_and_failure_state(caplog):
    config = _make_config()
    social_service = MagicMock()
    social_service.is_available = False

    with patch("src.core.pipeline.SearchService", side_effect=RuntimeError("search init boom")), \
         patch("src.core.pipeline.SocialSentimentService", return_value=social_service), \
         caplog.at_level(logging.WARNING, logger="src.core.pipeline"):
        pipeline = _build_pipeline(config)

    assert pipeline.search_service is None

    init_failure_records = [
        record for record in caplog.records if "搜索服务初始化失败，将以无搜索模式运行" in record.message
    ]
    assert len(init_failure_records) == 1
    assert init_failure_records[0].exc_info is not None
    assert "搜索服务未启用（初始化失败或依赖缺失）" in caplog.text
    assert "搜索服务未启用（未配置搜索能力）" not in caplog.text


def test_social_sentiment_init_failure_logs_traceback(caplog):
    config = _make_config()
    search_service = MagicMock()
    search_service.is_available = False

    with patch("src.core.pipeline.SearchService", return_value=search_service), \
         patch("src.core.pipeline.SocialSentimentService", side_effect=RuntimeError("social init boom")), \
         caplog.at_level(logging.WARNING, logger="src.core.pipeline"):
        pipeline = _build_pipeline(config)

    assert pipeline.social_sentiment_service is None

    init_failure_records = [
        record for record in caplog.records if "社交舆情服务初始化失败，将跳过舆情分析" in record.message
    ]
    assert len(init_failure_records) == 1
    assert init_failure_records[0].exc_info is not None


def test_emit_progress_logs_context_when_callback_fails(caplog):
    pipeline = StockAnalysisPipeline.__new__(StockAnalysisPipeline)
    pipeline.query_id = "query-123"

    def _fail_callback(progress, message):
        raise RuntimeError(f"cannot send {progress}:{message}")

    pipeline.progress_callback = _fail_callback

    with caplog.at_level(logging.WARNING, logger="src.core.pipeline"):
        pipeline._emit_progress(55, "fetching news")

    records = [record for record in caplog.records if "progress callback failed" in record.message]
    assert len(records) == 1
    record = records[0]
    assert "progress=55" in record.message
    assert "message='fetching news'" in record.message
    assert "query_id=query-123" in record.message
    assert record.progress == 55
    assert record.progress_message == "fetching news"
    assert record.query_id == "query-123"


# ---------------------------------------------------------------------------
# Pre-trade review (optional, default-off) — pipeline-level resilience
# ---------------------------------------------------------------------------

def _build_pipeline_all_optional_mocked(config: SimpleNamespace) -> StockAnalysisPipeline:
    with patch("src.core.pipeline.get_db", return_value=MagicMock()), \
         patch("src.core.pipeline.DataFetcherManager", return_value=MagicMock()), \
         patch("src.core.pipeline.StockTrendAnalyzer", return_value=MagicMock()), \
         patch("src.core.pipeline.GeminiAnalyzer", return_value=MagicMock()), \
         patch("src.core.pipeline.NotificationService", return_value=MagicMock()), \
         patch("src.core.pipeline.SearchService", return_value=MagicMock(is_available=False)), \
         patch("src.core.pipeline.SocialSentimentService",
               return_value=MagicMock(is_available=False)):
        return StockAnalysisPipeline(config=config)


def test_pretrade_review_disabled_is_zero_impact():
    """Default config has no pretrade_review_* keys — the getattr-guard must leave the
    service unset (no network surface, no behavior change) when the feature is off."""
    pipeline = _build_pipeline_all_optional_mocked(_make_config())
    assert pipeline.pretrade_review_service is None


def test_pretrade_review_enabled_constructs_service():
    config = _make_config()
    config.pretrade_review_enabled = True
    config.pretrade_review_endpoint = "https://api.babyblueviper.com/review"
    config.pretrade_review_api_key = "test-key"
    config.pretrade_review_timeout = 8
    pipeline = _build_pipeline_all_optional_mocked(config)
    assert pipeline.pretrade_review_service is not None
    assert pipeline.pretrade_review_service.is_available


def test_pretrade_review_enabled_without_key_constructs_unavailable_service():
    """Enabled but unconfigured key must STILL construct the service (is_available=False) so the
    enabled path can surface a not_configured degrade — rather than leaving it indistinguishable
    from the feature being off. Never a hard failure during init."""
    config = _make_config()
    config.pretrade_review_enabled = True
    config.pretrade_review_api_key = None
    pipeline = _build_pipeline_all_optional_mocked(config)
    assert pipeline.pretrade_review_service is not None
    assert pipeline.pretrade_review_service.is_available is False
    assert pipeline._pretrade_review_enabled is True


class _Result:
    """Minimal stand-in for a finalized analysis result."""
    def __init__(self):
        self.decision_action = "BUY"
        self.operation_advice = "open long, 5% position"
        self.current_price = 1680
        self.name = "贵州茅台"


class _ReportType:
    value = "single"


def test_apply_pretrade_review_attaches_metadata_when_enabled():
    """The shared helper must attach result.pretrade_review when the service is available.
    This is the contract BOTH analyze_stock() and _analyze_with_agent() rely on, so the
    agent path is covered by exercising the same helper."""
    config = _make_config()
    config.pretrade_review_enabled = True
    config.pretrade_review_api_key = "k"
    pipeline = _build_pipeline_all_optional_mocked(config)
    pipeline.pretrade_review_service.review = MagicMock(
        return_value={"status": "ok", "verdict": "approve_with_concerns", "confidence": 0.75,
                      "issues": [], "proof": {}}
    )
    result = _Result()
    pipeline._apply_pretrade_review(result, "600519.SH", "贵州茅台", _ReportType())
    assert result.pretrade_review["status"] == "ok"
    assert result.pretrade_review["verdict"] == "approve_with_concerns"
    # the advisory must NOT touch the BUY/SELL conclusion
    assert result.decision_action == "BUY"


def test_apply_pretrade_review_noop_when_disabled():
    """Helper is a no-op (no attribute set, no network) when the feature is off."""
    pipeline = _build_pipeline_all_optional_mocked(_make_config())
    assert pipeline.pretrade_review_service is None
    result = _Result()
    pipeline._apply_pretrade_review(result, "600519.SH", "贵州茅台", _ReportType())
    assert not hasattr(result, "pretrade_review")


def test_apply_pretrade_review_never_raises_on_service_error():
    """A service exception degrades to review_unavailable; the helper never propagates it."""
    config = _make_config()
    config.pretrade_review_enabled = True
    config.pretrade_review_api_key = "k"
    pipeline = _build_pipeline_all_optional_mocked(config)
    pipeline.pretrade_review_service.review = MagicMock(side_effect=RuntimeError("boom"))
    result = _Result()
    pipeline._apply_pretrade_review(result, "600519.SH", "贵州茅台", _ReportType())
    assert result.pretrade_review == {"status": "review_unavailable", "reason": "exception"}


def test_apply_pretrade_review_enabled_without_key_attaches_not_configured():
    """The contract both reviewers flagged: enabled but no API key must attach an explicit
    review_unavailable/not_configured advisory — NOT silently omit the field — so a user can tell
    'enabled but misconfigured' from 'disabled'. Exercises the real service's not_configured path."""
    config = _make_config()
    config.pretrade_review_enabled = True
    config.pretrade_review_api_key = None
    pipeline = _build_pipeline_all_optional_mocked(config)
    result = _Result()
    pipeline._apply_pretrade_review(result, "600519.SH", "贵州茅台", _ReportType())
    assert result.pretrade_review == {"status": "review_unavailable", "reason": "not_configured"}


def test_apply_pretrade_review_enabled_but_service_init_failed_attaches_not_configured():
    """If the service failed to construct (service is None) but the feature is enabled, the helper
    must still surface review_unavailable/not_configured rather than silently dropping the field."""
    config = _make_config()
    config.pretrade_review_enabled = True
    config.pretrade_review_api_key = "k"
    pipeline = _build_pipeline_all_optional_mocked(config)
    pipeline.pretrade_review_service = None  # simulate an init failure under an enabled feature
    result = _Result()
    pipeline._apply_pretrade_review(result, "600519.SH", "贵州茅台", _ReportType())
    assert result.pretrade_review == {"status": "review_unavailable", "reason": "not_configured"}
