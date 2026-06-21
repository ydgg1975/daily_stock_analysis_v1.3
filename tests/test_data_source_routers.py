from types import SimpleNamespace

from src.data_sources import MarketDataRouter, NewsDataRouter


class _FakeQuote:
    code = "600519"
    name = "测试股票"
    source = SimpleNamespace(value="akshare_sina")
    price = 12.3
    change_pct = 1.2
    provider_timestamp = None

    def has_basic_data(self):
        return True


class _FailingFetcherManager:
    def get_realtime_quote(self, stock_code, *, log_final_failure=True):
        raise RuntimeError("provider timeout")


class _QuoteFetcherManager:
    def get_realtime_quote(self, stock_code, *, log_final_failure=True):
        return _FakeQuote()


def test_market_data_router_returns_insufficient_bundle_on_realtime_failure():
    router = MarketDataRouter(_FailingFetcherManager())

    bundle = router.get_realtime_quote("600519")

    assert bundle.realtime_quote is None
    assert bundle.status.value == "failed"
    assert "数据不足" in (bundle.insufficient_reason or "")
    assert bundle.attempts[0].error_message == "provider timeout"


def test_market_data_router_marks_quote_source_and_timestamp():
    router = MarketDataRouter(_QuoteFetcherManager())

    bundle = router.get_realtime_quote("600519")

    assert bundle.realtime_quote is not None
    assert bundle.source_name == "akshare_sina"
    assert bundle.status.value == "ok"
    assert bundle.to_context_metadata()["source_name"] == "akshare_sina"


class _SearchService:
    is_available = True

    def search_comprehensive_intel(self, stock_code, stock_name, max_searches=5):
        return {
            "latest_news": SimpleNamespace(
                success=True,
                provider="Anspire",
                results=[SimpleNamespace(title="新闻1"), SimpleNamespace(title="新闻2")],
            ),
            "announcements": SimpleNamespace(
                success=True,
                provider="SerpAPI",
                results=[SimpleNamespace(title="公告1")],
            ),
        }

    def format_intel_report(self, responses, stock_name):
        return f"【{stock_name} 情报搜索结果】\n1. 新闻1"


def test_news_data_router_records_sources_and_result_count():
    router = NewsDataRouter(_SearchService(), max_items_per_stock=8)

    bundle = router.search_stock_intel(stock_code="600519", stock_name="贵州茅台")

    assert bundle.status.value == "ok"
    assert bundle.result_count == 3
    assert bundle.source_name == "Anspire, SerpAPI"
    assert "贵州茅台" in bundle.context_text


def test_news_data_router_disabled_is_explicit():
    router = NewsDataRouter(_SearchService(), enabled=False)

    bundle = router.search_stock_intel(stock_code="600519", stock_name="贵州茅台")

    assert bundle.status.value == "disabled"
    assert bundle.context_text == ""
    assert "新闻增强已关闭" in (bundle.insufficient_reason or "")
