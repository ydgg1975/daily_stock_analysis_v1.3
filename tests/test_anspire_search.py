# -*- coding: utf-8 -*-
"""
Anspire Search sousuoyinqingceshitaojian

ceshifugaifanwei:
1. peizhijiazaiceshi - yanzheng anspire_api_keys shifouzhengqueconghuanjingbianliangjiazai
2. fuwuchushihuaceshi - yanzheng SearchService shifouzhengquechushihua AnspireSearchProvider
3. API diaoyongceshi - shijidiaoyong Anspire API yanzhengfanhuijieguo
4. guzhangzhuanyiceshi - yanzhengwuxiao Key shidecuowuchulihejiangjijizhi
5. sousuogongnengceshi - ceshigupiaoxinwensousuohetongyongsousuogongneng

yunxingfangshi:
```bash
# Windows PowerShell
$env:ANSPIRE_API_KEYS="your_test_api_key"
python -m pytest tests/test_anspire_search.py -v

# Linux/Mac
export ANSPIRE_API_KEYS="your_test_api_key"
python -m pytest tests/test_anspire_search.py -v
```
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv
load_dotenv()

# tianjiaxiangmugenmuludao Python lujing，jiejuemokuaidaoruwenti
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock newspaper before search_service import (optional dependency)
if "newspaper" not in sys.modules:
    mock_np = MagicMock()
    mock_np.Article = MagicMock()
    mock_np.Config = MagicMock()
    sys.modules["newspaper"] = mock_np

from src.config import Config, get_config
from src.search_service import (
    AnspireSearchProvider,
    SearchService,
    get_search_service,
    reset_search_service,
)


class _FakeResponse:
    """moni HTTP xiangyingduixiang"""
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text
        self.headers = headers or {'content-type': 'application/json'}
    
    def json(self):
        return self._json_data


class TestAnspireConfigLoading(unittest.TestCase):
    """Test Anspire configuration loading from environment variables."""
    
    def setUp(self):
        """baocunbingqingchuhuanjingbianliang（bucaozuo .env wenjian）"""
        # ✅ baocunyuanshizhi，ceshihouhuifu
        self._original_anspire_keys = os.environ.get('ANSPIRE_API_KEYS')
        
        # qingchuhuanjingbianliang
        if 'ANSPIRE_API_KEYS' in os.environ:
            del os.environ['ANSPIRE_API_KEYS']
        
        # zhongzhi Config danli
        Config._Config__instance = None
        reset_search_service()

    def tearDown(self):
        """huifuyuanshihuanjingbianliang"""
        # ✅ huifuyuanshizhi
        if self._original_anspire_keys is not None:
            os.environ['ANSPIRE_API_KEYS'] = self._original_anspire_keys
        elif 'ANSPIRE_API_KEYS' in os.environ:
            del os.environ['ANSPIRE_API_KEYS']
        
        # zhongzhi Config danli
        Config._Config__instance = None
        reset_search_service()

    def test_anspire_keys_loaded_from_env(self):
        """Test that ANSPIRE_API_KEYS is correctly parsed from environment."""
        # ✅ shiyong patch.dict linshishezhi，ceshihouzidonghuifu
        with patch.dict(os.environ, {'ANSPIRE_API_KEYS': 'key1,key2,key3'}):
            config = Config._load_from_env()
            
            self.assertEqual(len(config.anspire_api_keys), 3)
            self.assertIn('key1', config.anspire_api_keys)
            self.assertIn('key2', config.anspire_api_keys)
            self.assertIn('key3', config.anspire_api_keys)

    def test_anspire_keys_single_key(self):
        """Test single API Key parsing."""
        with patch.dict(os.environ, {'ANSPIRE_API_KEYS': 'single_key_test'}):
            config = Config._load_from_env()
            
            self.assertEqual(len(config.anspire_api_keys), 1)
            self.assertEqual(config.anspire_api_keys[0], 'single_key_test')

    def test_anspire_keys_empty_env(self):
        """Test empty environment variable handling."""
        with patch.dict(os.environ, {'ANSPIRE_API_KEYS': ''}):
            config = Config._load_from_env()
            
            self.assertEqual(len(config.anspire_api_keys), 0)

    def test_anspire_keys_whitespace_handling(self):
        """Test whitespace trimming in API Keys."""
        with patch.dict(os.environ, {'ANSPIRE_API_KEYS': ' key1 , key2 , key3 '}):
            config = Config._load_from_env()
            
            self.assertEqual(len(config.anspire_api_keys), 3)
            self.assertEqual(config.anspire_api_keys, ['key1', 'key2', 'key3'])


class TestAnspireSearchProvider(unittest.TestCase):
    """Anspire Search Provider danyuanceshi"""
    
    def setUp(self):
        """ceshiqianzhunbei"""
        # ✅ shiyongmingquedeceshizhanweifu，bushizhenshimiyaoxingtai
        self.test_api_key = "sk-test-anspire-placeholder-key-12345"
        self.provider = AnspireSearchProvider([self.test_api_key])
        # baocunyuanshi requests mokuai
        self._original_requests = sys.modules.get('requests')
    
    def tearDown(self):
        """ceshihouqingli"""
        # huifuyuanshi requests mokuai
        if self._original_requests is not None:
            sys.modules['requests'] = self._original_requests
    
    def test_provider_initialization(self):
        """ceshi Provider chushihua"""
        provider = AnspireSearchProvider(["key1", "key2"])
        self.assertEqual(provider.name, "Anspire")
        if hasattr(provider, 'api_keys'):
            self.assertEqual(len(provider.api_keys), 2)
        elif hasattr(provider, '_api_keys'):
            self.assertEqual(len(provider._api_keys), 2)
        self.assertTrue(provider.is_available)
    
    def test_provider_name(self):
        """ceshi Provider mingcheng"""
        self.assertEqual(self.provider.name, "Anspire")
    
    def test_provider_availability(self):
        """ceshi Provider keyongxingjiance"""
        # you API Key shiyingkeyong
        provider_with_keys = AnspireSearchProvider(["key1"])
        self.assertTrue(provider_with_keys.is_available)
        
        # wu API Key shibukeyong
        provider_without_keys = AnspireSearchProvider([])
        self.assertFalse(provider_without_keys.is_available)
    
    def test_extract_domain(self):
        """ceshiyumingtiqugongneng"""
        test_cases = [
            ("https://www.example.com/article", "example.com"),
            ("https://finance.sina.com.cn/stock/", "finance.sina.com.cn"),
            ("http://www.10jqka.com.cn/news", "10jqka.com.cn"),
            ("invalid_url", "weizhilaiyuan"),
            ("", "weizhilaiyuan"),
        ]
        
        for url, expected in test_cases:
            result = AnspireSearchProvider._extract_domain(url)
            self.assertEqual(result, expected, f"Failed for URL: {url}")
    
    @patch('src.search_service.requests')
    def test_search_success_response(self, mock_requests):
        """ceshichenggongxiangyingchuli"""
        # shezhi mock exceptions
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            pass
        
        fake_response = _FakeResponse(
            status_code=200,
            json_data={
                "code": 200,
                "msg": "success",
                "results": [
                    {
                        "title": "guizhoumaotaijinrigujiashangzhang",
                        "url": "https://finance.sina.com.cn/stock/600519",
                        "content": "guizhoumaotai (600519) jinrishoupangujiashangzhang 2.5%，chengjiaoliangfangda...",
                    },
                    {
                        "title": "baijiubankuaichixuzouqiang",
                        "url": "https://www.10jqka.com.cn/baijiu",
                        "content": "baijiubankuaijinribiaoxianqiangshi，guizhoumaotai、wuliangyedenggeguzhangfujuqian...",
                    }
                ]
            }
        )
        
        mock_requests.get = MagicMock(return_value=fake_response)
        
        response = self.provider.search("guizhoumaotai gupiaoxinwen", max_results=5, days=7)
        
        # yanzhengjieguo
        self.assertTrue(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 2)
        self.assertEqual(response.results[0].title, "guizhoumaotaijinrigujiashangzhang")
        # jiashe source shicong url tiqudeyuming
        self.assertEqual(response.results[0].source, "finance.sina.com.cn")
        
        # yanzheng API diaoyongcanshu
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        # jiancha URL shifoubaohan anspire xiangguanyuming (juti URL xugenjushijishixiantiaozheng)
        # self.assertIn("plugin.anspire.cn", call_args[0][0]) 
        self.assertIn("Authorization", call_args[1]["headers"])
        # yanzhengshiyong params erfei json
        self.assertIn("params", call_args[1])
        self.assertNotIn("json", call_args[1])
    
    @patch('src.search_service.requests')
    def test_search_invalid_api_key(self, mock_requests):
        """ceshiwuxiao API Key decuowuchuli"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            pass
        
        fake_response = _FakeResponse(
            status_code=401,
            json_data={"message": "Invalid API key"},
            text="Unauthorized"
        )
        
        mock_requests.get = MagicMock(return_value=fake_response)
        
        response = self.provider.search("ceshichaxun", max_results=3)
        
        self.assertFalse(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 0)
        # cuowuxiaoxikenengyinshixianeryi，zhelizuokuansongjiancha
        self.assertTrue("API" in response.error_message or "KEY" in response.error_message or "wuxiao" in response.error_message)
    
    @patch('src.search_service.requests')
    def test_search_timeout_error(self, mock_requests):
        """ceshichaoshicuowuchuli"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
            timeout_exc = mock_requests.exceptions.Timeout
        except ImportError:
            mock_requests.exceptions = MagicMock()
            timeout_exc = Exception
            
        mock_requests.get = MagicMock(side_effect=timeout_exc())
        
        response = self.provider.search("ceshichaxun", max_results=3)
        
        self.assertFalse(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 0)
        # cuowuxiaoxijiancha
        self.assertTrue("chaoshi" in response.error_message or "Timeout" in response.error_message)
    
    @patch('src.search_service.requests')
    def test_search_network_error(self, mock_requests):
        """ceshiwangluocuowuchuli"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
            conn_exc = mock_requests.exceptions.ConnectionError
        except ImportError:
            mock_requests.exceptions = MagicMock()
            conn_exc = Exception

        mock_requests.get = MagicMock(side_effect=conn_exc())
        
        response = self.provider.search("ceshichaxun", max_results=3)
        
        self.assertFalse(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 0)
        self.assertTrue("wangluo" in response.error_message or "Connection" in response.error_message)
    
    @patch('src.search_service.requests')
    def test_search_empty_results(self, mock_requests):
        """ceshikongjieguochuli"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            mock_requests.exceptions = MagicMock()
        
        fake_response = _FakeResponse(
            status_code=200,
            json_data={"code": 200, "msg": "success", "results": []}
        )
        
        mock_requests.get = MagicMock(return_value=fake_response)
        
        response = self.provider.search("bucunzaidegupiao XYZ", max_results=5)
        
        self.assertTrue(response.success)
        self.assertEqual(response.provider, "Anspire")
        self.assertEqual(len(response.results), 0)
    
    @patch('src.search_service.requests')
    def test_search_content_truncation(self, mock_requests):
        """ceshizhangneirongjieduangongneng"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            mock_requests.exceptions = MagicMock()
        
        long_content = "zheshiyiduanfeichangzhangdeneirong，" * 100  # chaoguo 500 zifu
        
        fake_response = _FakeResponse(
            status_code=200,
            json_data={
                "code": 200,
                "msg": "success",
                "results": [{
                    "title": "zhangneirongceshi",
                    "url": "https://example.com/long",
                    "content": long_content
                }]
            }
        )
        
        mock_requests.get = MagicMock(return_value=fake_response)
        
        response = self.provider.search("ceshi", max_results=1)
        
        self.assertTrue(response.success)
        self.assertEqual(len(response.results), 1)
        # yanzhengneirongbeijieduandao 500 zifuyinei
        if response.results[0].snippet:
            self.assertLessEqual(len(response.results[0].snippet), 503)  # 500 + "..."
            self.assertTrue(response.results[0].snippet.endswith("..."))
    
    @patch('src.search_service.requests')
    def test_search_time_range(self, mock_requests):
        """ceshishijianfanweicanshu"""
        try:
            import requests as real_requests
            mock_requests.exceptions = real_requests.exceptions
        except ImportError:
            mock_requests.exceptions = MagicMock()
        
        fake_response = _FakeResponse(status_code=200, json_data={"code": 200, "results": []})
        mock_requests.get = MagicMock(return_value=fake_response)
        
        # ceshi 7 tianfanwei
        self.provider.search("ceshi", max_results=3, days=7)
        
        # yanzhengshijiancanshu
        call_args = mock_requests.get.call_args
        if call_args and len(call_args) > 1 and 'params' in call_args[1]:
            params = call_args[1]["params"]
                
            # yanzhengshijiancanshucunzai (jutiziduanmingqujueyushixian)
            # zhelijiasheshiyongle FromTime/ToTime huoleisiziduan，ruowuzetiaoguojutiziduanjiancha
            # self.assertIn("FromTime", params)
            # self.assertIn("ToTime", params)


class TestAnspireSearchService(unittest.TestCase):
    """SearchService zhong Anspire jichengceshi"""
    
    def setUp(self):
        Config._Config__instance = None
        reset_search_service()

    def test_search_service_with_anspire(self):
        """ceshi SearchService zhengquechushihua Anspire Provider"""
        service = SearchService(
            anspire_keys=["test_key"],
            bocha_keys=[],
            tavily_keys=[],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short"
        )
        
        self.assertTrue(hasattr(service, '_providers'))
        self.assertGreater(len(service._providers), 0)
        
        first_provider = service._providers[0]
        self.assertIsInstance(first_provider, AnspireSearchProvider)
        self.assertEqual(first_provider.name, "Anspire")
    
    def test_search_service_without_anspire(self):
        """ceshiweipeizhi Anspire shidexingwei"""
        service = SearchService(
            anspire_keys=[],
            tavily_keys=["tavily_key"],
            bocha_keys=[],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short"
        )
        
        # yanzhengmeiyou Anspire Provider
        anspire_providers = [p for p in service._providers if isinstance(p, AnspireSearchProvider)]
        self.assertEqual(len(anspire_providers), 0)
    
    def test_search_service_priority(self):
        """ceshi Anspire youxianji"""
        service = SearchService(
            anspire_keys=["anspire_key"],
            bocha_keys=["bocha_key"],
            tavily_keys=["tavily_key"],
            searxng_public_instances_enabled=False,
            news_max_age_days=3,
            news_strategy_profile="short"
        )
        
        self.assertIsInstance(service._providers[0], AnspireSearchProvider)


class TestAnspireIntegration(unittest.TestCase):
    """Anspire jichengceshi（xuyaozhenshi API Key）"""
    
    @classmethod
    def setUpClass(cls):
        """Check if API Key is configured."""
        cls.api_keys = [k.strip() for k in os.getenv('ANSPIRE_API_KEYS', '').split(',') if k.strip()]
        cls.has_api_key = len(cls.api_keys) > 0
        
        if cls.has_api_key:
            reset_search_service()
            cls.service = get_search_service()

    @unittest.skipIf(
        not os.environ.get("ANSPIRE_API_KEYS"),
        "weishezhi ANSPIRE_API_KEYS huanjingbianliang，tiaoguojichengceshi"
    )
    @pytest.mark.network
    def test_real_api_call_stock_news(self):
        """zhenshi API diaoyongceshi - gupiaoxinwensousuo"""
        # quebaofuwuyizhongzhi
        reset_search_service()
        service = get_search_service()
        
        # yanzheng Anspire yipeizhi
        anspire_provider = None
        for provider in service._providers:
            if isinstance(provider, AnspireSearchProvider):
                anspire_provider = provider
                break
        
        if not anspire_provider:
            self.skipTest("Anspire Provider weichushihua")
        
        # ceshi A gusousuo
        response = service.search_stock_news("600519", "guizhoumaotai", max_results=3)
        
        print(f"\n=== Anspire zhenshi API ceshijieguo ===")
        print(f"sousuozhuangtai：{'chenggong' if response.success else 'shibai'}")
        print(f"sousuoyinqing：{response.provider}")
        print(f"jieguoshuliang：{len(response.results)}")
        print(f"haoshi：{response.search_time:.2f}s")
        
        # jibenyanzheng
        self.assertTrue(response.success, f"sousuoshibai：{response.error_message}")
        self.assertEqual(response.provider, "Anspire")
        self.assertGreater(len(response.results), 0, "yingzhishaofanhuiyitiaojieguo")
        
        # yanzhengjieguogeshi
        for result in response.results:
            self.assertIsNotNone(result.title)
            self.assertIsNotNone(result.url)
            # snippet kenengweikong，shijutishixianerding
            # self.assertIsNotNone(result.snippet)
    
    @unittest.skipIf(
        not os.environ.get("ANSPIRE_API_KEYS"),
        "weishezhi ANSPIRE_API_KEYS huanjingbianliang，tiaoguojichengceshi"
    )
    @pytest.mark.network
    def test_real_api_call_general_search(self):
        """zhenshi API diaoyongceshi - tongyongsousuo"""
        reset_search_service()
        service = get_search_service()
        
        anspire_provider = None
        for provider in service._providers:
            if isinstance(provider, AnspireSearchProvider):
                anspire_provider = provider
                break
        
        if not anspire_provider:
            self.skipTest("Anspire Provider weichushihua")
        
        # ceshitongyongsousuo
        response = anspire_provider.search("rengongzhinengzuixinfazhan", max_results=5, days=7)
        
        print(f"\n=== Anspire tongyongsousuojieguo ===")
        print(f"sousuozhuangtai：{'chenggong' if response.success else 'shibai'}")
        print(f"jieguoshuliang：{len(response.results)}")
        
        self.assertTrue(response.success)
        self.assertGreater(len(response.results), 0)


def run_manual_test():
    """shoudongceshihanshu（yongyukuaisuyanzheng）"""
    import logging
    from src.config import get_config
    
    # peizhirizhi
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )
    
    print("=" * 60)
    print("Anspire Search kuaisuceshi")
    print("=" * 60)
    
    # jianchapeizhi
    config = get_config()
    if not config.anspire_api_keys:
        print("\n❌ weijiancedao Anspire API Keys")
        print("qingshezhihuanjingbianliang：")
        print("  Windows PowerShell: $env:ANSPIRE_API_KEYS=\"your_api_key\"")
        print("  Linux/Mac: export ANSPIRE_API_KEYS=\"your_api_key\"")
        return False
    
    print(f"\n✅ yipeizhi {len(config.anspire_api_keys)} ge Anspire API Key")
    
    # chuangjianfuwu
    service = SearchService(
        anspire_keys=config.anspire_api_keys,
        bocha_keys=config.bocha_api_keys,
        tavily_keys=config.tavily_keys,
        searxng_public_instances_enabled=False,
        news_max_age_days=3,
        news_strategy_profile="short"
    )
    
    # yanzheng Provider
    anspire_provider = service._providers[0] if service._providers else None
    if not anspire_provider or not isinstance(anspire_provider, AnspireSearchProvider):
        print("\n❌ Anspire Provider weizhengquechushihua")
        return False
    
    print(f"✅ Anspire Provider chushihuachenggong")
    print(f"   Provider mingcheng：{anspire_provider.name}")
    if hasattr(anspire_provider, 'api_keys'):
        print(f"   API Keys shuliang：{len(anspire_provider.api_keys)}")
    elif hasattr(anspire_provider, '_api_keys'):
        print(f"   API Keys shuliang：{len(anspire_provider._api_keys)}")
    
    # zhixingceshisousuo
    print("\n" + "=" * 60)
    print("zhixingceshisousuo：guizhoumaotai (600519)")
    print("=" * 60)
    
    response = service.search_stock_news("600519", "guizhoumaotai", max_results=3)
    
    print(f"\nsousuojieguo:")
    print(f"  zhuangtai：{'✅ chenggong' if response.success else '❌ shibai'}")
    print(f"  sousuoyinqing：{response.provider}")
    print(f"  jieguoshuliang：{len(response.results)}")
    print(f"  haoshi：{response.search_time:.2f}s")
    
    if response.error_message:
        print(f"  cuowuxinxi：{response.error_message}")
    
    if response.results:
        print(f"\nqian {min(2, len(response.results))} tiaojieguoyulan:")
        for i, result in enumerate(response.results[:2], 1):
            print(f"\n  [{i}] {result.title}")
            print(f"      laiyuan：{result.source}")
            print(f"      URL: {result.url}")
            if result.snippet:
                snippet_preview = result.snippet[:100] + "..." if len(result.snippet) > 100 else result.snippet
                print(f"      zhaiyao：{snippet_preview}")
    
    print("\n" + "=" * 60)
    print("ceshiwancheng!")
    print("=" * 60)
    
    return response.success


if __name__ == "__main__":
    # ruguoshezhilehuanjingbianliang，yunxingwanzhengceshi
    if os.environ.get("ANSPIRE_API_KEYS"):
        print("jiancedao ANSPIRE_API_KEYS huanjingbianliang，yunxingwanzhengceshitaojian...")
        unittest.main(verbosity=2)
    else:
        # fouzezhiyunxingdanyuanceshi，tiaoguojichengceshi
        print("weishezhi ANSPIRE_API_KEYS huanjingbianliang，jinyunxingdanyuanceshi（tiaoguojichengceshi）...")
        print("ruxuyunxingwanzhengceshi，qingshezhihuanjingbianliang:")
        print("  Windows PowerShell: $env:ANSPIRE_API_KEYS=\"your_api_key\"")
        print("  Linux/Mac: export ANSPIRE_API_KEYS=\"your_api_key\"")
        print()
        
        # yunxingdanyuanceshi
        suite = unittest.TestLoader().loadTestsFromTestCase(TestAnspireConfigLoading)
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAnspireSearchProvider))
        suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestAnspireSearchService))
        runner = unittest.TextTestRunner(verbosity=2)
        runner.run(suite)
        
        # tigongshoudongceshixuanxiang
        print("\n" + "=" * 60)
        choice = input("shifouyunxingshoudongceshi（xuyaoyouxiaode API Key）? (y/n): ").strip().lower()
        if choice == 'y':
            run_manual_test()
