# -*- coding: utf-8 -*-
"""
===================================
选股过滤 Pipeline - 三层过滤 + 复合评分
===================================

设计目标：在股票进入 AI 分析流程前，先通过三层过滤筛选出最值得分析的候选股票。

三层结构：
1. MarketEnvironmentFilter   - 大盘环境过滤（判断当前市场值不值得做多）
2. StockPositionScorer       - 股票位置评估（判断股价在历史区间中的位置）
3. TechnicalSignalScorer     - 技术面 + 催化剂筛选（量价、板块、换手率）

总调度：StockFilterPipeline
- 接收自选股列表
- 按顺序执行三层过滤
- 输出复合评分排序后的候选队列
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd

from data_provider.base import DataFetcherManager
from data_provider.realtime_types import UnifiedRealtimeQuote

logger = logging.getLogger(__name__)


# =============================================================================
# 第一层：大盘环境过滤
# =============================================================================

@dataclass
class MarketEnvironmentResult:
    """大盘环境评估结果"""
    score: int                      # 总分（0-100）
    level: str                      # 等级：strong_bull / bull / neutral / bear / strong_bear
    recommendation: str             # 建议：full_position / half_position / no_new_position / skip_all
    index_trend_score: int          # 指数趋势分（0-40）
    breadth_score: int              # 市场广度分（0-40）
    volume_score: int               # 成交量分（0-20）
    # 诊断明细
    indices: List[Dict] = field(default_factory=list)      # 主要指数涨跌
    up_count: int = 0
    down_count: int = 0
    limit_up_count: int = 0
    limit_down_count: int = 0
    total_amount: float = 0.0
    # 板块
    top_sectors: List[Dict] = field(default_factory=list)
    bottom_sectors: List[Dict] = field(default_factory=list)


class MarketEnvironmentFilter:
    """
    第一层：大盘环境过滤

    根据 get_main_indices + get_market_stats 判断当前市场多空环境，
    决定仓位上限和是否开新仓。
    """

    def __init__(self, fetcher_manager: DataFetcherManager):
        self.fm = fetcher_manager

    def run(self) -> MarketEnvironmentResult:
        """执行大盘环境评估"""
        t0 = time.time()

        # 获取指数行情
        indices_data = self._fetch_indices()
        # 获取市场广度
        breadth_data = self._fetch_breadth()
        # 获取板块排行
        sector_data = self._fetch_sectors()

        # 计算三项子分
        idx_score = self._calc_index_trend_score(indices_data)
        breadth_score = self._calc_breadth_score(breadth_data)
        volume_score = self._calc_volume_score(breadth_data, indices_data)
        total = idx_score + breadth_score + volume_score

        # 确定等级和建议
        level, recommendation = self._get_level_and_recommendation(total)

        result = MarketEnvironmentResult(
            score=total,
            level=level,
            recommendation=recommendation,
            index_trend_score=idx_score,
            breadth_score=breadth_score,
            volume_score=volume_score,
            indices=indices_data,
            up_count=breadth_data.get("up_count", 0),
            down_count=breadth_data.get("down_count", 0),
            limit_up_count=breadth_data.get("limit_up_count", 0),
            limit_down_count=breadth_data.get("limit_down_count", 0),
            total_amount=breadth_data.get("total_amount", 0.0),
            top_sectors=sector_data[0],
            bottom_sectors=sector_data[1],
        )

        elapsed = time.time() - t0
        logger.info(
            f"[MarketEnv] score={total} level={level} rec={recommendation} "
            f"(idx={idx_score} breadth={breadth_score} vol={volume_score}) "
            f"elapsed={elapsed:.2f}s"
        )
        return result

    def _fetch_indices(self) -> List[Dict]:
        """获取主要指数"""
        try:
            result = self.fm.get_main_indices(region="cn")
            if result:
                return result
        except Exception as e:
            logger.warning(f"[MarketEnv] get_main_indices failed: {e}")
        return []

    def _fetch_breadth(self) -> Dict:
        """获取市场广度（涨跌家数等）"""
        try:
            result = self.fm.get_market_stats()
            if result:
                return result
        except Exception as e:
            logger.warning(f"[MarketEnv] get_market_stats failed: {e}")
        return {}

    def _fetch_sectors(self) -> Tuple[List[Dict], List[Dict]]:
        """获取板块涨跌榜"""
        try:
            top, bottom = self.fm.get_sector_rankings(n=5)
            return (top or [], bottom or [])
        except Exception as e:
            logger.warning(f"[MarketEnv] get_sector_rankings failed: {e}")
        return ([], [])

    def _calc_index_trend_score(self, indices: List[Dict]) -> int:
        """
        计算指数趋势分（满分40）
        需要沪深300近5日数据来判断均线排列
        """
        if not indices:
            return 10  # 无数据，默认低分

        score = 0
        # 找到沪深300
        hs300 = next((i for i in indices if "沪深300" in i.get("name", "")), None)
        sz50 = next((i for i in indices if "上证50" in i.get("name", "")), None)
        cyb = next((i for i in indices if "创业板" in i.get("name", "")), None)

        # 近20日涨幅
        for idx_info in [hs300, sz50, cyb]:
            if idx_info and idx_info.get("change_pct", 0) > 0:
                score += 5
            elif idx_info and idx_info.get("change_pct", 0) < -2:
                score -= 5

        # 额外：判断整体涨幅
        positive_count = sum(1 for i in indices if i.get("change_pct", 0) > 0)
        if positive_count >= 3:
            score += 10
        elif positive_count <= 1:
            score -= 10

        return max(0, min(40, score + 20))  # 基准20，加减分

    def _calc_breadth_score(self, breadth: Dict) -> int:
        """
        计算市场广度分（满分40）
        """
        up = breadth.get("up_count", 0)
        down = breadth.get("down_count", 0)
        limit_up = breadth.get("limit_up_count", 0)
        limit_down = breadth.get("limit_down_count", 0)

        score = 20  # 基准分

        # 涨跌家数比
        if up > down:
            score += 15
        elif down > up:
            score -= 15

        # 涨停家数
        if limit_up >= 20:
            score += 10
        elif limit_up >= 10:
            score += 5
        elif limit_up < 5:
            score -= 5

        # 跌停家数（少为好）
        if limit_down <= 5:
            score += 5
        elif limit_down >= 20:
            score -= 10

        return max(0, min(40, score))

    def _calc_volume_score(self, breadth: Dict, indices: List[Dict]) -> int:
        """
        计算成交量分（满分20）
        """
        total_amount = breadth.get("total_amount", 0)

        score = 10  # 基准分

        # 成交额判断（以万亿为单位）
        # 假设正常两市成交额在 0.8-1.5 万亿
        if total_amount > 1.5:  # 万亿
            score += 10
        elif total_amount > 1.0:
            score += 5
        elif total_amount < 0.5:
            score -= 5

        return max(0, min(20, score))

    def _get_level_and_recommendation(self, score: int) -> Tuple[str, str]:
        if score >= 70:
            return "strong_bull", "full_position"
        elif score >= 50:
            return "bull", "full_position"
        elif score >= 35:
            return "neutral", "half_position"
        elif score >= 20:
            return "bear", "no_new_position"
        else:
            return "strong_bear", "skip_all"


# =============================================================================
# 第二层：股票位置评估
# =============================================================================

@dataclass
class PositionResult:
    """股票位置评估结果"""
    stock_code: str
    score: int                      # 总分（0-100）
    position_pct: float             # 当前价在近1年高低点区间中的位置（%）
    ma_status: str                  # 均线状态：bullish / neutral / bearish
    relative_strength: float         # 相对大盘的超额收益（%）
    # 明细
    price_1y_high: float = 0.0
    price_1y_low: float = 0.0
    current_price: float = 0.0
    ma5: float = 0.0
    ma10: float = 0.0
    ma20: float = 0.0


class StockPositionScorer:
    """
    第二层：股票位置评估

    基于近1年日线数据，评估：
    1. 当前价在历史高低点区间的位置（估值位置）
    2. 均线排列状态（趋势方向）
    3. 相对大盘的超额收益（相对强弱）
    """

    def __init__(self, fetcher_manager: DataFetcherManager):
        self.fm = fetcher_manager

    def run(self, stock_code: str, index_code: str = "000300") -> PositionResult:
        """
        执行股票位置评估

        Args:
            stock_code: 股票代码
            index_code: 对标指数代码，默认沪深300
        """
        t0 = time.time()

        # 获取股票日线（近1年，约250交易日）
        df_stock = self._fetch_daily_data(stock_code, days=250)
        # 获取指数日线（同期）
        df_index = self._fetch_daily_data(index_code, days=250)

        # 计算各项分
        position_pct = self._calc_position_pct(df_stock)
        position_score = self._calc_position_score(position_pct)

        ma_status, ma5, ma10, ma20 = self._calc_ma_status(df_stock)
        ma_score = self._calc_ma_score(ma_status)

        rel_strength = self._calc_relative_strength(df_stock, df_index)
        rel_score = self._calc_rel_score(rel_strength)

        total = position_score + ma_score + rel_score

        current_price = float(df_stock["close"].iloc[-1]) if not df_stock.empty else 0.0

        result = PositionResult(
            stock_code=stock_code,
            score=total,
            position_pct=position_pct,
            ma_status=ma_status,
            relative_strength=rel_strength,
            price_1y_high=float(df_stock["high"].max()) if not df_stock.empty else 0.0,
            price_1y_low=float(df_stock["low"].min()) if not df_stock.empty else 0.0,
            current_price=current_price,
            ma5=ma5,
            ma10=ma10,
            ma20=ma20,
        )

        elapsed = time.time() - t0
        logger.debug(
            f"[Position] {stock_code} score={total} pos_pct={position_pct:.1f}% "
            f"ma={ma_status} rel={rel_strength:.2f}% elapsed={elapsed:.2f}s"
        )
        return result

    def _fetch_daily_data(self, code: str, days: int) -> pd.DataFrame:
        try:
            df, _ = self.fm.get_daily_data(code, days=days)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.warning(f"[Position] get_daily_data({code}) failed: {e}")
        return pd.DataFrame()

    def _calc_position_pct(self, df: pd.DataFrame) -> float:
        """计算当前价在近1年高低点区间的位置%"""
        if df.empty or "close" not in df.columns:
            return 50.0
        current = float(df["close"].iloc[-1])
        low = float(df["low"].min())
        high = float(df["high"].max())
        if high == low:
            return 50.0
        return (current - low) / (high - low) * 100.0

    def _calc_position_score(self, position_pct: float) -> int:
        """估值位置分（满分30）"""
        if position_pct < 20:
            return 30
        elif position_pct < 35:
            return 25
        elif position_pct < 50:
            return 20
        elif position_pct < 65:
            return 12
        elif position_pct < 80:
            return 6
        else:
            return 0  # 高位股不给分

    def _calc_ma_status(self, df: pd.DataFrame) -> Tuple[str, float, float, float]:
        """计算均线状态"""
        if df.empty or len(df) < 20:
            return "neutral", 0.0, 0.0, 0.0
        ma5 = float(df["ma5"].iloc[-1]) if "ma5" in df.columns else 0.0
        ma10 = float(df["ma10"].iloc[-1]) if "ma10" in df.columns else 0.0
        ma20 = float(df["ma20"].iloc[-1]) if "ma20" in df.columns else 0.0
        current = float(df["close"].iloc[-1])

        if current > ma20 and ma5 > ma10 > ma20:
            status = "bullish"
        elif current < ma20 and ma5 < ma10 < ma20:
            status = "bearish"
        elif current > ma20:
            status = "neutral"
        else:
            status = "neutral"
        return status, ma5, ma10, ma20

    def _calc_ma_score(self, ma_status: str) -> int:
        """均线分（满分30）"""
        if ma_status == "bullish":
            return 30
        elif ma_status == "neutral":
            return 15
        else:
            return 0

    def _calc_relative_strength(self, df_stock: pd.DataFrame, df_index: pd.DataFrame) -> float:
        """计算相对大盘的超额收益（N日，一般取20日）"""
        if df_stock.empty or df_index.empty:
            return 0.0
        n = min(20, len(df_stock), len(df_index))
        if n < 5:
            return 0.0

        stock_ret = (float(df_stock["close"].iloc[-1]) / float(df_stock["close"].iloc[-n]) - 1) * 100
        index_ret = (float(df_index["close"].iloc[-1]) / float(df_index["close"].iloc[-n]) - 1) * 100
        return stock_ret - index_ret

    def _calc_rel_score(self, rel_strength: float) -> int:
        """相对强弱分（满分40）"""
        if rel_strength > 8:
            return 40
        elif rel_strength > 3:
            return 30
        elif rel_strength > 0:
            return 20
        elif rel_strength > -5:
            return 10
        else:
            return 0


# =============================================================================
# 第三层：技术面 + 催化剂筛选
# =============================================================================

@dataclass
class SignalResult:
    """技术信号评估结果"""
    stock_code: str
    score: int                      # 总分（0-100）
    volume_price_score: int         # 量价配合分（0-30）
    sector_score: int               # 板块催化剂分（0-30）
    turnover_score: int             # 换手率分（0-20）
    fundamental_score: int          # 基本面信号分（0-20）
    # 明细
    volume_ratio: float = 0.0
    change_pct: float = 0.0
    turnover_rate: float = 0.0
    sector_name: str = ""
    sector_change_pct: float = 0.0
    pe: float = 0.0
    pb: float = 0.0


class TechnicalSignalScorer:
    """
    第三层：技术面 + 催化剂筛选

    基于实时行情 + 板块排名，评估：
    1. 量价配合（放量上涨是强势信号）
    2. 板块催化剂（是否在强势板块）
    3. 换手率与股性
    4. 基本面信号（PE/PB位置）
    """

    def __init__(self, fetcher_manager: DataFetcherManager):
        self.fm = fetcher_manager

    def run(self, stock_code: str, top_sectors: List[Dict] = None) -> SignalResult:
        """
        执行技术信号评估
        """
        t0 = time.time()

        # 获取实时行情
        quote = self._fetch_realtime_quote(stock_code)
        # 板块信息：通过实时行情的 name 字段关联（简化版，不做额外 API 调用）
        sector = getattr(quote, "name", "") or ""

        # 计算各项分
        vol_score, vol_ratio, chg_pct = self._calc_volume_price_score(quote)
        sec_score, sec_name, sec_chg = self._calc_sector_score(sector, top_sectors or [])
        turn_score, turn_rate = self._calc_turnover_score(quote)
        fund_score, pe, pb = self._calc_fundamental_score(quote)

        total = vol_score + sec_score + turn_score + fund_score

        result = SignalResult(
            stock_code=stock_code,
            score=total,
            volume_price_score=vol_score,
            sector_score=sec_score,
            turnover_score=turn_score,
            fundamental_score=fund_score,
            volume_ratio=vol_ratio,
            change_pct=chg_pct,
            turnover_rate=turn_rate,
            sector_name=sec_name,
            sector_change_pct=sec_chg,
            pe=pe,
            pb=pb,
        )

        elapsed = time.time() - t0
        logger.debug(
            f"[Signal] {stock_code} score={total} "
            f"(vol={vol_score} sec={sec_score} turn={turn_score} fund={fund_score}) "
            f"elapsed={elapsed:.2f}s"
        )
        return result

    def _fetch_realtime_quote(self, code: str):
        """获取实时行情"""
        try:
            quote = self.fm.get_realtime_quote(code)
            if quote is not None:
                return quote
        except Exception as e:
            logger.warning(f"[Signal] get_realtime_quote({code}) failed: {e}")
        # 返回一个空壳对象，所有 getattr 调用会走默认值
        from data_provider.realtime_types import UnifiedRealtimeQuote
        return UnifiedRealtimeQuote(code=code)

    def _calc_volume_price_score(self, quote) -> Tuple[int, float, float]:
        """量价配合分（满分30）"""
        vol_ratio = float(getattr(quote, "volume_ratio", 1.0) or 1.0)
        chg_pct = float(getattr(quote, "change_pct", 0.0) or 0.0)

        score = 15  # 基准分

        # 放量且上涨
        if vol_ratio > 1.5 and chg_pct > 2:
            score = 30
        elif vol_ratio > 1.5 and chg_pct > 0:
            score = 25
        elif vol_ratio > 1.2 and chg_pct > 2:
            score = 25
        elif vol_ratio > 1.2 and chg_pct > 0:
            score = 20
        # 缩量上涨（警惕）
        elif vol_ratio < 0.8 and chg_pct > 0:
            score = 10
        # 放量下跌（不参与）
        elif vol_ratio > 1.5 and chg_pct < -2:
            score = 0
        # 下跌
        elif chg_pct < -2:
            score = 0
        elif chg_pct < 0:
            score = 5

        return score, vol_ratio, chg_pct

    def _calc_sector_score(self, sector: str, top_sectors: List[Dict]) -> Tuple[int, str, float]:
        """板块催化剂分（满分30）"""
        if not top_sectors:
            return 15, sector, 0.0

        # top_sectors 里每项是 dict，包含 name 和 change_pct
        # 领涨板块的 change_pct 是正数，可以用来给全局股票做参考
        best_sector_change = float(top_sectors[0].get("change_pct", 0.0)) if top_sectors else 0.0

        score = 15  # 基准分

        # 全市场领涨板块涨幅大，说明市场情绪好，提高整体分数
        if best_sector_change > 3:
            score = 25
        elif best_sector_change > 1.5:
            score = 20

        return score, sector, best_sector_change

    def _calc_turnover_score(self, quote) -> Tuple[int, float]:
        """换手率分（满分20）"""
        turnover = float(getattr(quote, "turnover_rate", 0.0) or 0.0)

        if 3 <= turnover <= 10:
            score = 20
        elif 1 <= turnover < 3:
            score = 15
        elif turnover > 10:
            score = 10  # 过于活跃
        else:
            score = 5   # 不活跃

        return score, turnover

    def _calc_fundamental_score(self, quote) -> Tuple[int, float, float]:
        """基本面信号分（满分20）"""
        pe = float(getattr(quote, "pe_ratio", 0.0) or 0.0)
        pb = float(getattr(quote, "pb_ratio", 0.0) or 0.0)

        score = 10  # 基准分

        if pe > 0:
            if pe < 15:
                score += 10
            elif pe < 25:
                score += 5
            elif pe > 60:
                score -= 5

        if pb > 0:
            if pb < 2:
                score += 5
            elif pb > 8:
                score -= 5

        return max(0, min(20, score)), pe, pb


# =============================================================================
# 总调度：选股过滤 Pipeline
# =============================================================================

@dataclass
class FilteredStock:
    """过滤后的股票结果"""
    stock_code: str
    stock_name: str = ""

    # 各项分
    market_score: int = 0           # 大盘环境分（所有股票相同）
    market_level: str = ""           # 大盘等级
    position_score: int = 0          # 位置分
    signal_score: int = 0            # 技术分

    # 复合总分
    composite_score: float = 0.0    # 加权总分

    # 各层明细
    position_pct: float = 0.0       # 位置%
    ma_status: str = ""
    relative_strength: float = 0.0
    volume_ratio: float = 0.0
    sector_name: str = ""
    change_pct: float = 0.0

    # 建议
    recommendation: str = ""         # analyze / cautious / skip
    reason: str = ""                 # 简要原因


class StockFilterPipeline:
    """
    选股过滤 Pipeline 总调度

    接收自选股列表，按三层顺序执行过滤与评分，
    输出按复合评分排序的候选队列。
    """

    def __init__(self, fetcher_manager: DataFetcherManager):
        self.fm = fetcher_manager
        self.market_filter = MarketEnvironmentFilter(fetcher_manager)
        self.position_scorer = StockPositionScorer(fetcher_manager)
        self.signal_scorer = TechnicalSignalScorer(fetcher_manager)

    def run(
        self,
        stock_codes: List[str],
        index_code: str = "000300",
    ) -> Tuple[List[FilteredStock], MarketEnvironmentResult]:
        """
        执行选股过滤

        Args:
            stock_codes: 自选股列表
            index_code: 对标指数，默认沪深300

        Returns:
            Tuple[过滤后的股票列表（按复合评分降序）, 大盘环境结果]
        """
        logger.info(f"[FilterPipeline] 开始过滤 {len(stock_codes)} 只股票")
        t0 = time.time()

        # === 第一层：大盘环境 ===
        market_result = self.market_filter.run()

        # === 根据大盘环境决定是否继续 ===
        if market_result.recommendation == "skip_all":
            logger.warning("[FilterPipeline] 大盘极弱（strong_bear），跳过全部分析")
            return [], market_result

        # === 第二+三层：逐只股票评估 ===
        results: List[FilteredStock] = []

        for code in stock_codes:
            try:
                stock_name = self._get_stock_name(code)
                fs = self._evaluate_stock(
                    code, stock_name, index_code, market_result
                )
                if fs.recommendation != "skip":
                    results.append(fs)
            except Exception as e:
                logger.warning(f"[FilterPipeline] {code} 评估失败: {e}")
                continue

        # === 复合评分排序 ===
        results.sort(key=lambda x: x.composite_score, reverse=True)

        elapsed = time.time() - t0
        passed = len(results)
        logger.info(
            f"[FilterPipeline] 完成: {passed}/{len(stock_codes)} 通过过滤 "
            f"(大盘={market_result.level} score={market_result.score}) "
            f"elapsed={elapsed:.2f}s"
        )

        # 打印前3名
        for i, r in enumerate(results[:3]):
            logger.info(
                f"  #{i+1} {r.stock_code}({r.stock_name}) "
                f"composite={r.composite_score:.1f} "
                f"(pos={r.position_score} sig={r.signal_score})"
            )

        return results, market_result

    def _evaluate_stock(
        self,
        code: str,
        name: str,
        index_code: str,
        market_result: MarketEnvironmentResult,
    ) -> FilteredStock:
        """评估单只股票"""
        # 位置分
        pos = self.position_scorer.run(code, index_code)
        # 技术分
        sig = self.signal_scorer.run(code, market_result.top_sectors)

        # 复合评分：大盘分×0.25 + 位置分×0.35 + 技术分×0.40
        composite = (
            market_result.score * 0.25
            + pos.score * 0.35
            + sig.score * 0.40
        )

        # 建议
        recommendation, reason = self._get_recommendation(
            composite, pos, sig, market_result
        )

        return FilteredStock(
            stock_code=code,
            stock_name=name,
            market_score=market_result.score,
            market_level=market_result.level,
            position_score=pos.score,
            signal_score=sig.score,
            composite_score=round(composite, 1),
            position_pct=round(pos.position_pct, 1),
            ma_status=pos.ma_status,
            relative_strength=round(pos.relative_strength, 2),
            volume_ratio=round(sig.volume_ratio, 2),
            sector_name=sig.sector_name,
            change_pct=round(sig.change_pct, 2),
            recommendation=recommendation,
            reason=reason,
        )

    def _get_recommendation(
        self,
        composite: float,
        pos: PositionResult,
        sig: SignalResult,
        market: MarketEnvironmentResult,
    ) -> Tuple[str, str]:
        """根据评分给出建议"""
        # 大盘极弱，跳过
        if market.recommendation == "skip_all":
            return "skip", "大盘极弱，不新开仓"

        # 高位股降权
        if pos.position_pct > 80:
            if composite < 50:
                return "skip", f"位置偏高({pos.position_pct:.0f}%)，总分不足"
            else:
                return "cautious", f"位置偏高({pos.position_pct:.0f}%)，控制仓位"

        # 大盘中性时降低预期
        if market.recommendation == "neutral" and composite < 45:
            return "skip", "大盘震荡，总分偏低"

        # 大盘弱时严格
        if market.recommendation == "no_new_position" and composite < 55:
            return "skip", "大盘偏弱，不新开仓"

        if composite >= 60:
            return "analyze", "优先分析"
        elif composite >= 45:
            return "analyze", "可分析"
        else:
            return "skip", "总分偏低"

    def _get_stock_name(self, code: str) -> str:
        """获取股票名称"""
        try:
            name = self.fm.get_stock_name(code)
            return name if name else code
        except Exception:
            return code
