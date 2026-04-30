# -*- coding: utf-8 -*-
"""
Exa AI Search 搜索引擎测试套件

测试覆盖范围:
1. 配置加载测试 - 验证 exa_api_keys 是否正确从环境变量加载
2. 服务初始化测试 - 验证 SearchService 是否正确初始化 ExaSearchProvider
3. API 调用测试 - 通过 mock 验证返回结果解析
4. 错误处理测试 - 验证无效 Key、配额耗尽、网络异常的降级处理
5. 内容字段回退测试 - 验证 highlights / summary / text 任一缺失时仍能生成可读 snippet

运行方式:
```bash
# Linux/Mac
export EXA_API_KEYS="your_test_api_key"
python -m pytest tests/test_exa_search.py -v
```
"""

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
load_dotenv()

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock newspaper before search_service import (optional dependency)
if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np


def _install_fake_exa_module(client_factory):
    """Install a fake ``exa_py`` module so the lazy import inside the
    provider resolves to ``client_factory`` regardless of whether the real
    SDK is installed locally.
    """
    fake_module = MagicMock()
    fake_module.Exa = client_factory
    sys.modules["exa_py"] = fake_module


from src.config import Config
from src.search_service import (
    ExaSearchProvider,
    SearchService,
    reset_search_service,
)


def _make_result(**fields):
    """Build a duck-typed Exa result object."""
    defaults = {
        "title": "",
        "url": "",
        "text": None,
        "highlights": None,
        "summary": None,
        "published_date": None,
    }
    defaults.update(fields)
    return SimpleNamespace(**defaults)


class TestExaConfigLoading(unittest.TestCase):
    """Test Exa configuration loading from environment variables."""

    def setUp(self):
        self._original_exa_keys = os.environ.get('EXA_API_KEYS')
        if 'EXA_API_KEYS' in os.environ:
            del os.environ['EXA_API_KEYS']
        Config._Config__instance = None
        reset_search_service()

    def tearDown(self):
        if self._original_exa_keys is not None:
            os.environ['EXA_API_KEYS'] = self._original_exa_keys
        elif 'EXA_API_KEYS' in os.environ:
            del os.environ['EXA_API_KEYS']
        Config._Config__instance = None
        reset_search_service()

    def test_exa_keys_loaded_from_env(self):
        with patch.dict(os.environ, {'EXA_API_KEYS': 'key1,key2,key3'}):
            config = Config._load_from_env()
            self.assertEqual(len(config.exa_api_keys), 3)
            self.assertEqual(config.exa_api_keys, ['key1', 'key2', 'key3'])

    def test_exa_keys_single_key(self):
        with patch.dict(os.environ, {'EXA_API_KEYS': 'single_key_test'}):
            config = Config._load_from_env()
            self.assertEqual(config.exa_api_keys, ['single_key_test'])

    def test_exa_keys_empty_env(self):
        with patch.dict(os.environ, {'EXA_API_KEYS': ''}):
            config = Config._load_from_env()
            self.assertEqual(config.exa_api_keys, [])

    def test_exa_keys_whitespace_handling(self):
        with patch.dict(os.environ, {'EXA_API_KEYS': ' key1 , key2 , key3 '}):
            config = Config._load_from_env()
            self.assertEqual(config.exa_api_keys, ['key1', 'key2', 'key3'])


class TestExaSearchProvider(unittest.TestCase):
    """Exa Search Provider 单元测试"""

    def setUp(self):
        self.test_api_key = "exa-test-placeholder-key-12345"
        self.provider = ExaSearchProvider([self.test_api_key])
        self._original_exa_module = sys.modules.get("exa_py")

    def tearDown(self):
        if self._original_exa_module is not None:
            sys.modules["exa_py"] = self._original_exa_module
        elif "exa_py" in sys.modules:
            del sys.modules["exa_py"]

    def test_provider_initialization(self):
        provider = ExaSearchProvider(["key1", "key2"])
        self.assertEqual(provider.name, "Exa")
        self.assertEqual(len(provider._api_keys), 2)
        self.assertTrue(provider.is_available)

    def test_provider_unavailable_without_keys(self):
        provider = ExaSearchProvider([])
        self.assertFalse(provider.is_available)

    def test_extract_domain(self):
        cases = [
            ("https://www.bloomberg.com/article", "bloomberg.com"),
            ("https://finance.sina.com.cn/stock/", "finance.sina.com.cn"),
            ("invalid_url", "未知来源"),
            ("", "未知来源"),
        ]
        for url, expected in cases:
            self.assertEqual(ExaSearchProvider._extract_domain(url), expected)

    def test_search_success_response_with_highlights(self):
        """Successful response with highlights should produce snippets."""
        fake_client = MagicMock()
        fake_client.headers = {}
        fake_response = MagicMock()
        fake_response.results = [
            _make_result(
                title="Apple Q2 Earnings Beat Expectations",
                url="https://www.bloomberg.com/news/apple-q2",
                highlights=[
                    "Apple reported revenue of $94.8B",
                    "iPhone sales rose 6% year-over-year",
                ],
                text="Full article text here",
                summary="Apple beat Wall Street estimates this quarter.",
                published_date="2025-05-02T14:30:00.000Z",
            ),
            _make_result(
                title="Tech sector rallies on AI optimism",
                url="https://www.reuters.com/markets/tech",
                highlights=["Nasdaq up 1.5% on AI demand"],
                published_date="2025-05-01T09:00:00.000Z",
            ),
        ]
        fake_client.search_and_contents.return_value = fake_response

        client_factory = MagicMock(return_value=fake_client)
        _install_fake_exa_module(client_factory)

        response = self.provider.search("AAPL earnings", max_results=5, days=7)

        self.assertTrue(response.success)
        self.assertEqual(response.provider, "Exa")
        self.assertEqual(len(response.results), 2)

        first = response.results[0]
        self.assertEqual(first.title, "Apple Q2 Earnings Beat Expectations")
        self.assertEqual(first.source, "bloomberg.com")
        self.assertIn("Apple reported revenue", first.snippet)
        self.assertIn("iPhone sales", first.snippet)
        self.assertEqual(first.published_date, "2025-05-02T14:30:00.000Z")

        client_factory.assert_called_once_with(api_key=self.test_api_key)
        # Integration tracking header should be set on the SDK client.
        self.assertEqual(
            fake_client.headers.get("x-exa-integration"),
            "daily-stock-analysis",
        )
        call_kwargs = fake_client.search_and_contents.call_args.kwargs
        self.assertEqual(call_kwargs["category"], "news")
        self.assertEqual(call_kwargs["type"], "auto")
        self.assertIn("start_published_date", call_kwargs)

    def test_snippet_falls_back_to_summary_when_highlights_missing(self):
        item = _make_result(
            title="t",
            url="https://example.com/a",
            highlights=[],
            summary="A concise summary of the article.",
            text="Long text body would go here.",
        )
        snippet = ExaSearchProvider._build_snippet(item)
        self.assertEqual(snippet, "A concise summary of the article.")

    def test_snippet_falls_back_to_text_when_summary_missing(self):
        item = _make_result(
            title="t",
            url="https://example.com/a",
            highlights=None,
            summary=None,
            text="Long text body that should be used as fallback.",
        )
        snippet = ExaSearchProvider._build_snippet(item)
        self.assertEqual(snippet, "Long text body that should be used as fallback.")

    def test_snippet_truncates_long_content(self):
        long_text = "A" * 1000
        item = _make_result(text=long_text)
        snippet = ExaSearchProvider._build_snippet(item)
        self.assertTrue(snippet.endswith("..."))
        self.assertLessEqual(len(snippet), ExaSearchProvider._SNIPPET_MAX_CHARS + 3)

    def test_snippet_empty_when_all_content_missing(self):
        item = _make_result()
        self.assertEqual(ExaSearchProvider._build_snippet(item), "")

    def test_search_handles_invalid_api_key_error(self):
        fake_client = MagicMock()
        fake_client.headers = {}
        fake_client.search_and_contents.side_effect = Exception("401 Unauthorized: invalid api key")

        client_factory = MagicMock(return_value=fake_client)
        _install_fake_exa_module(client_factory)

        response = self.provider.search("AAPL", max_results=3)
        self.assertFalse(response.success)
        self.assertEqual(response.provider, "Exa")
        self.assertEqual(len(response.results), 0)
        self.assertIn("API KEY", response.error_message)

    def test_search_handles_rate_limit_error(self):
        fake_client = MagicMock()
        fake_client.headers = {}
        fake_client.search_and_contents.side_effect = Exception("429 rate limit exceeded")

        client_factory = MagicMock(return_value=fake_client)
        _install_fake_exa_module(client_factory)

        response = self.provider.search("AAPL", max_results=3)
        self.assertFalse(response.success)
        self.assertIn("配额", response.error_message)

    def test_search_disabled_when_sdk_missing(self):
        """If exa_py is not installed, search returns a structured failure."""
        # Replace exa_py module with one whose attribute access raises ImportError
        class _NoExa:
            def __getattr__(self, name):
                raise ImportError("exa_py not installed")

        sys.modules["exa_py"] = _NoExa()

        response = self.provider.search("AAPL", max_results=3)
        self.assertFalse(response.success)
        self.assertIn("exa-py", response.error_message)


class TestExaSearchService(unittest.TestCase):
    """SearchService 中 Exa 集成测试"""

    def setUp(self):
        Config._Config__instance = None
        reset_search_service()

    def test_search_service_registers_exa_provider(self):
        service = SearchService(
            exa_keys=["test_key"],
            anspire_keys=[],
            bocha_keys=[],
            tavily_keys=[],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        exa_providers = [p for p in service._providers if isinstance(p, ExaSearchProvider)]
        self.assertEqual(len(exa_providers), 1)
        self.assertEqual(exa_providers[0].name, "Exa")

    def test_search_service_omits_exa_when_unconfigured(self):
        service = SearchService(
            exa_keys=[],
            tavily_keys=["tavily_key"],
            bocha_keys=[],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short",
        )

        exa_providers = [p for p in service._providers if isinstance(p, ExaSearchProvider)]
        self.assertEqual(len(exa_providers), 0)


class TestExaIntegration(unittest.TestCase):
    """Exa 集成测试（需要真实 API Key）"""

    @unittest.skipIf(
        not os.environ.get("EXA_API_KEYS"),
        "未设置 EXA_API_KEYS 环境变量，跳过集成测试"
    )
    @pytest.mark.network
    def test_real_api_call_general_search(self):
        api_keys = [k.strip() for k in os.getenv('EXA_API_KEYS', '').split(',') if k.strip()]
        provider = ExaSearchProvider(api_keys)
        response = provider.search("AAPL stock price", max_results=3, days=7)

        print(f"\n=== Exa 真实 API 测试结果 ===")
        print(f"搜索状态：{'成功' if response.success else '失败'}")
        print(f"结果数量：{len(response.results)}")
        if response.error_message:
            print(f"错误信息：{response.error_message}")

        self.assertTrue(response.success, f"搜索失败：{response.error_message}")
        self.assertGreater(len(response.results), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
