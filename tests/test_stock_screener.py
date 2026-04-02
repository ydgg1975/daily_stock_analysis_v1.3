# -*- coding: utf-8 -*-
"""
候选股票筛选服务单元测试
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

pd = pytest.importorskip("pandas")

class TestFilterAndRank:
    """测试通用筛选排序逻辑"""

    def _make_df(self, rows):
        return pd.DataFrame(rows)

    def test_basic_filtering(self):
        from src.services.stock_screener import _filter_and_rank
        df = self._make_df([
            {"代码": "600519", "名称": "贵州茅台", "最新价": 1800, "涨跌幅": 2.5, "成交额": 5e9},
            {"代码": "000001", "名称": "平安银行", "最新价": 12.5, "涨跌幅": -0.5, "成交额": 1e9},
            {"代码": "300999", "名称": "ST某股", "最新价": 3.5, "涨跌幅": 0, "成交额": 1e7},
        ])
        result = _filter_and_rank(
            df, market="a_share",
            price_col="最新价", name_col="名称", code_col="代码",
            change_pct_col="涨跌幅", amount_col="成交额",
            pe_col=None, cap_col=None,
            price_min=None, price_max=None,
            min_amount=5e7, top_n=10, exclude_st=True,
        )
        codes = [r["code"] for r in result]
        # ST 股被排除
        assert "300999" not in codes
        # 成交额过滤后保留两只
        assert "600519" in codes
        assert "000001" in codes

    def test_price_range_filter(self):
        from src.services.stock_screener import _filter_and_rank
        df = self._make_df([
            {"代码": "600519", "名称": "贵州茅台", "最新价": 1800, "涨跌幅": 0, "成交额": 5e9},
            {"代码": "000001", "名称": "平安银行", "最新价": 12.5, "涨跌幅": 0, "成交额": 1e9},
            {"代码": "600036", "名称": "招商银行", "最新价": 35, "涨跌幅": 0, "成交额": 2e9},
        ])
        result = _filter_and_rank(
            df, market="a_share",
            price_col="最新价", name_col="名称", code_col="代码",
            change_pct_col="涨跌幅", amount_col="成交额",
            pe_col=None, cap_col=None,
            price_min=10, price_max=50,
            min_amount=0, top_n=10, exclude_st=False,
        )
        codes = [r["code"] for r in result]
        assert "600519" not in codes  # 1800 > 50
        assert "000001" in codes  # 12.5 in range
        assert "600036" in codes  # 35 in range

    def test_sort_by_amount(self):
        from src.services.stock_screener import _filter_and_rank
        df = self._make_df([
            {"代码": "A", "名称": "A", "最新价": 10, "涨跌幅": 0, "成交额": 100},
            {"代码": "B", "名称": "B", "最新价": 20, "涨跌幅": 0, "成交额": 300},
            {"代码": "C", "名称": "C", "最新价": 30, "涨跌幅": 0, "成交额": 200},
        ])
        result = _filter_and_rank(
            df, market="a_share",
            price_col="最新价", name_col="名称", code_col="代码",
            change_pct_col="涨跌幅", amount_col="成交额",
            pe_col=None, cap_col=None,
            price_min=None, price_max=None,
            min_amount=0, top_n=10, exclude_st=False,
        )
        # 按成交额降序
        assert result[0]["code"] == "B"
        assert result[1]["code"] == "C"
        assert result[2]["code"] == "A"

    def test_top_n_limit(self):
        from src.services.stock_screener import _filter_and_rank
        rows = [
            {"代码": f"00{i:04d}", "名称": f"Stock{i}", "最新价": 10 + i, "涨跌幅": 0, "成交额": 1e8 + i}
            for i in range(20)
        ]
        df = self._make_df(rows)
        result = _filter_and_rank(
            df, market="a_share",
            price_col="最新价", name_col="名称", code_col="代码",
            change_pct_col="涨跌幅", amount_col="成交额",
            pe_col=None, cap_col=None,
            price_min=None, price_max=None,
            min_amount=0, top_n=5, exclude_st=False,
        )
        assert len(result) == 5

    def test_empty_dataframe(self):
        from src.services.stock_screener import _filter_and_rank
        result = _filter_and_rank(
            pd.DataFrame(), market="a_share",
            price_col="最新价", name_col="名称", code_col="代码",
            change_pct_col="涨跌幅", amount_col="成交额",
            pe_col=None, cap_col=None,
            price_min=None, price_max=None,
            min_amount=0, top_n=10, exclude_st=False,
        )
        assert result == []

    def test_none_dataframe(self):
        from src.services.stock_screener import _filter_and_rank
        result = _filter_and_rank(
            None, market="a_share",
            price_col="最新价", name_col="名称", code_col="代码",
            change_pct_col="涨跌幅", amount_col="成交额",
            pe_col=None, cap_col=None,
            price_min=None, price_max=None,
            min_amount=0, top_n=10, exclude_st=False,
        )
        assert result == []


class TestScreen:
    """测试 screen 主函数"""

    def test_unsupported_market_skipped(self, monkeypatch):
        from src.services import stock_screener
        # screen 对不支持的市场应不崩溃
        result = stock_screener.screen(markets=["mars"], price_min=None, price_max=None)
        assert result == []
