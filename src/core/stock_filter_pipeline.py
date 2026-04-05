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

        三层判断：
        1. 均线排列（满分20）：MA5/MA10/MA20 判断中期趋势方向
        2. 趋势持续性（满分10）：连续N日涨跌判断趋势惯性
        3. 趋势加速度（满分10）：今日vs昨日涨跌判断动力变化
        """
        score = 20  # 基准分

        # === Layer 1: 均线排列判断（满分20）===
        ma_score, ma_status = self._calc_ma_arrangement_score()
        score += ma_score

        # === Layer 2: 趋势持续性（满分10）===
        persistence_score = self._calc_trend_persistence_score()
        score += persistence_score

        # === Layer 3: 趋势加速度（满分10）===
        accel_score = self._calc_trend_acceleration_score()
        score += accel_score

        return max(0, min(40, score))

    def _calc_ma_arrangement_score(self) -> Tuple[int, str]:
        """
        Layer 1: 均线排列判断

        使用沪深300近20日均线判断趋势方向：
        - 多头排列（MA5>MA10>MA20）：上升趋势 -> +15
        - 空头排列（MA5<MA10<MA20）：下降趋势 -> -10
        - 价格在MA20之上/下：额外 +/-5
        """
        try:
            df, _ = self.fm.get_daily_data("000300", days=20)
            if df is None or df.empty or len(df) < 20:
                return 0, "unknown"

            ma5 = float(df["ma5"].iloc[-1])
            ma10 = float(df["ma10"].iloc[-1])
            ma20 = float(df["ma20"].iloc[-1])
            close = float(df["close"].iloc[-1])

            score = 0
            status = "neutral"

            # 均线多头排列
            if ma5 > ma10 > ma20:
                score += 15
                status = "bullish"
            # 均线空头排列
            elif ma5 < ma10 < ma20:
                score -= 10
                status = "bearish"
            # 部分多头/空头排列
            elif ma5 > ma20 and ma10 > ma20:
                score += 5
                status = "partial_bullish"
            elif ma5 < ma20 and ma10 < ma20:
                score -= 5
                status = "partial_bearish"

            # 价格相对MA20位置
            if close > ma20:
                score += 5
            elif close < ma20:
                score -= 5

            return score, status
        except Exception as e:
            logger.debug(f"[MarketEnv] 均线计算失败: {e}")
            return 0, "unknown"

    def _calc_trend_persistence_score(self) -> int:
        """
        Layer 2: 趋势持续性判断

        根据近5日涨跌序列判断趋势是否有持续性：
        - 连续3日同向涨跌 -> +8
        - 连续2日同向涨跌 -> +4
        - 震荡无方向 -> 0
        """
        try:
            df, _ = self.fm.get_daily_data("000300", days=5)
            if df is None or df.empty or "pct_chg" not in df.columns:
                return 0

            changes = df["pct_chg"].tolist()
            if len(changes) < 3:
                return 0

            # 取最近N日（倒序，最后一个是今日）
            recent = changes[-(min(5, len(changes))):]
            if len(recent) < 3:
                return 0

            # 判断连续同向
            positive_count = sum(1 for c in recent if c > 0)
            negative_count = sum(1 for c in recent if c < 0)

            # 连续3日同向
            if positive_count >= 3:
                return 8
            elif negative_count >= 3:
                return 8
            # 连续2日同向
            elif positive_count >= 2:
                return 4
            elif negative_count >= 2:
                return 4
            # 震荡
            else:
                return 0
        except Exception as e:
            logger.debug(f"[MarketEnv] 趋势持续性计算失败: {e}")
            return 0

    def _calc_trend_acceleration_score(self) -> int:
        """
        Layer 3: 趋势加速度判断

        对比近2日涨跌变化：
        - 上涨加速（今日涨幅 > 昨日涨幅）-> +8
        - 上涨减速（今日涨幅 < 昨日涨幅）-> +4
        - 下跌加速（跌幅扩大）-> +6（可能是见底信号）
        - 下跌减速（跌幅收窄）-> +2（可能是见顶信号）
        """
        try:
            df, _ = self.fm.get_daily_data("000300", days=3)
            if df is None or df.empty or "pct_chg" not in df.columns:
                return 0

            changes = df["pct_chg"].tolist()
            if len(changes) < 2:
                return 0

            today = changes[-1]
            yesterday = changes[-2]

            # 上涨行情
            if today > 0 and yesterday > 0:
                if today > yesterday:
                    return 8   # 上涨加速
                else:
                    return 4   # 上涨减速
            # 下跌行情
            elif today < 0 and yesterday < 0:
                if abs(today) > abs(yesterday):
                    return 6   # 下跌加速（可能是见底信号）
                else:
                    return 2   # 下跌减速（可能是见顶信号）
            # 今日跌昨日涨：转弱信号
            elif today < 0 and yesterday > 0:
                return -4
            # 今日涨昨日跌：转强信号
            elif today > 0 and yesterday < 0:
                return 4
            else:
                return 0
        except Exception as e:
            logger.debug(f"[MarketEnv] 趋势加速度计算失败: {e}")
            return 0

    def _calc_breadth_score(self, breadth: Dict) -> int:
        """
        计算市场广度分（满分40）

        动态阈值：根据涨停家数的绝对值和相对变化来判断
        """
        up = breadth.get("up_count", 0)
        down = breadth.get("down_count", 0)
        limit_up = breadth.get("limit_up_count", 0)
        limit_down = breadth.get("limit_down_count", 0)

        score = 20  # 基准分

        # 涨跌家数比（这个逻辑保持不变）
        if up > down:
            score += 15
        elif down > up:
            score -= 15

        # 涨停家数（动态阈值）
        # 牛市：涨停30+才算强势
        # 熊市：涨停10+就算强势
        # 根据市场整体氛围调整预期
        if limit_up >= 30:
            score += 10
        elif limit_up >= 20:
            score += 8
        elif limit_up >= 10:
            score += 5
        elif limit_up >= 5:
            score += 2
        elif limit_up >= 1:
            score += 0  # 有涨停但不突出
        else:
            score -= 3  # 没有涨停，市场偏弱

        # 跌停家数（少为好，但也要考虑市场背景）
        if limit_down == 0:
            score += 5
        elif limit_down <= 3:
            score += 3
        elif limit_down <= 10:
            score += 0
        elif limit_down <= 20:
            score -= 5
        else:
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
            return "strong_bull", "high_conviction_full_position"  # 强烈看多，满仓操作
        elif score >= 55:
            return "bull", "full_position"  # 正常看多
        elif score >= 40:
            return "neutral", "half_position"  # 中性，半仓
        elif score >= 25:
            return "bear", "no_new_position"  # 看空，不新开仓
        else:
            return "strong_bear", "skip_all"  # 强烈看空，空仓


# =============================================================================
# 第二层：股票位置评估
# =============================================================================

@dataclass
class PositionResult:
    """股票位置评估结果（Layer 2）"""
    stock_code: str
    score: int                      # 总分（0-100）

    # 四项子分
    ma20_slope_score: int = 0       # MA20斜率分（满分40）
    price_ma20_dist_score: int = 0  # 价格相对MA20距离分（满分30）
    ma60_direction_score: int = 0   # MA60方向分（满分20）
    rel_strength_score: int = 0      # 20日相对强弱分（满分10）

    # 原始数据（供参考）
    relative_strength: float = 0.0  # 近20日相对大盘超额收益（%）
    ma20_slope: float = 0.0         # MA20斜率（日均变化率%）
    ma60_direction: str = ""        # MA60方向：up / flat / down
    price_ma20_distance_pct: float = 0.0  # 价格相对MA20的距离%（正=在MA20之上）
    current_price: float = 0.0
    ma20: float = 0.0
    ma60: float = 0.0
    position_pct: float = 0.0       # 当前价在1年高低点区间位置（%）
    price_1y_high: float = 0.0
    price_1y_low: float = 0.0


class StockPositionScorer:
    """
    第二层：股票位置评估（Layer 2）

    评分体系（满分100）：
    - MA20 斜率（40）：趋势强度与方向
    - 价格相对MA20距离（30）：是否过热
    - MA60 方向（20）：中期趋势
    - 近20日相对强弱（10）：相对大盘超额收益
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

        # ---- 四项子分 ----
        ma20_slope = self._calc_ma20_slope(df_stock)
        ma20_slope_score = self._calc_ma20_slope_score(ma20_slope)

        ma20, ma60, price_ma20_dist = self._calc_price_ma20_distance(df_stock)
        price_ma20_dist_score = self._calc_price_ma20_dist_score(price_ma20_dist)

        ma60_direction = self._calc_ma60_direction(df_stock, ma60)
        ma60_dir_score = self._calc_ma60_direction_score(ma60_direction)

        rel_strength = self._calc_relative_strength(df_stock, df_index)
        rel_score = self._calc_rel_strength_score(rel_strength)

        total = ma20_slope_score + price_ma20_dist_score + ma60_dir_score + rel_score

        current_price = float(df_stock["close"].iloc[-1]) if not df_stock.empty else 0.0
        position_pct = self._calc_position_pct(df_stock)

        result = PositionResult(
            stock_code=stock_code,
            score=total,
            ma20_slope_score=ma20_slope_score,
            price_ma20_dist_score=price_ma20_dist_score,
            ma60_direction_score=ma60_dir_score,
            rel_strength_score=rel_score,
            relative_strength=rel_strength,
            ma20_slope=ma20_slope,
            ma60_direction=ma60_direction,
            price_ma20_distance_pct=price_ma20_dist,
            current_price=current_price,
            ma20=ma20,
            ma60=ma60,
            position_pct=position_pct,
            price_1y_high=float(df_stock["high"].max()) if not df_stock.empty else 0.0,
            price_1y_low=float(df_stock["low"].min()) if not df_stock.empty else 0.0,
        )

        elapsed = time.time() - t0
        logger.debug(
            f"[Position] {stock_code} score={total} "
            f"(slope={ma20_slope_score} dist={price_ma20_dist_score} "
            f"ma60={ma60_dir_score} rel={rel_score}) "
            f"slope={ma20_slope:.4f} dist={price_ma20_dist:.2f}% "
            f"ma60={ma60_direction} rel={rel_strength:.2f}% "
            f"elapsed={elapsed:.2f}s"
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
        """当前价在近1年高低点区间的位置%"""
        if df.empty or "close" not in df.columns:
            return 50.0
        current = float(df["close"].iloc[-1])
        low = float(df["low"].min())
        high = float(df["high"].max())
        if high == low:
            return 50.0
        return (current - low) / (high - low) * 100.0

    def _calc_ma20_slope(self, df: pd.DataFrame) -> float:
        """
        计算 MA20 斜率（日均变化率%）

        使用近20日MA20值做线性回归，得到每日平均变化率。
        正值=上升趋势，负值=下降趋势。
        """
        if df.empty or "ma20" not in df.columns:
            return 0.0
        ma20_series = df["ma20"].dropna()
        if len(ma20_series) < 5:
            return 0.0
        # 取最近20个MA20值（不够则全部）
        n = min(20, len(ma20_series))
        ma20_vals = ma20_series.iloc[-n:].values
        # 简单斜率：(最后值-第一值) / 第一值 / 天数 * 100 = 日均变化率%
        if ma20_vals[0] == 0:
            return 0.0
        slope = (ma20_vals[-1] - ma20_vals[0]) / ma20_vals[0] / n * 100
        return float(slope)

    def _calc_ma20_slope_score(self, slope: float) -> int:
        """
        MA20斜率分（满分40）

        阈值说明（基于日均变化率%）：
        - >0.05%/日：强势上升 → 40
        - >0.02%/日：温和上升 → 30
        - >0%/日：   轻微上升 → 20
        - 0%/日：    横盘     → 10
        - <0%/日：   下降趋势 → 0
        """
        if slope > 0.05:
            return 40
        elif slope > 0.02:
            return 30
        elif slope > 0:
            return 20
        elif slope > -0.02:
            return 10
        else:
            return 0

    def _calc_price_ma20_distance(
        self, df: pd.DataFrame
    ) -> Tuple[float, float, float]:
        """
        计算价格与MA20的距离

        Returns:
            Tuple(ma20, ma60, 距离%)
            距离% = (当前价 - MA20) / MA20 * 100，正=在MA20之上
        """
        if df.empty or "ma20" not in df.columns:
            return 0.0, 0.0, 0.0
        ma20_col = df["ma20"].dropna()
        if ma20_col.empty:
            return 0.0, 0.0, 0.0
        ma20 = float(ma20_col.iloc[-1])
        current = float(df["close"].iloc[-1])

        ma60 = 0.0
        if "ma60" in df.columns:
            ma60_col = df["ma60"].dropna()
            if not ma60_col.empty:
                ma60 = float(ma60_col.iloc[-1])

        if ma20 == 0:
            distance_pct = 0.0
        else:
            distance_pct = (current - ma20) / ma20 * 100.0

        return ma20, ma60, float(distance_pct)

    def _calc_price_ma20_dist_score(self, dist_pct: float) -> int:
        """
        价格相对MA20距离分（满分30）

        原则：价格在MA20之上5%内最健康（顺势但不过热），过远则回调风险大
        - 0%~5%：最佳，低位启动或回调确认 → 30
        - 5%~10%：正常，趋势健康 → 25
        - 0%~-3%：略低于MA20，弱势但未破坏 → 20
        - 10%~15%：偏热，谨慎 → 15
        - >15%：过热，回调风险高 → 5
        - <-3%：跌破MA20，趋势破坏 → 0
        """
        if dist_pct < -3:
            return 0
        elif dist_pct < 0:
            return 20
        elif dist_pct <= 5:
            return 30
        elif dist_pct <= 10:
            return 25
        elif dist_pct <= 15:
            return 15
        else:
            return 5

    def _calc_ma60_direction(self, df: pd.DataFrame, ma60: float) -> str:
        """
        MA60方向：up / flat / down

        通过近20日MA60变化率判断。
        """
        if df.empty or "ma60" not in df.columns or ma60 == 0:
            return "flat"
        ma60_col = df["ma60"].dropna()
        if len(ma60_col) < 20:
            return "flat"
        ma60_20d_ago = float(ma60_col.iloc[-20])
        if ma60_20d_ago == 0:
            return "flat"
        change_pct = (ma60 - ma60_20d_ago) / ma60_20d_ago * 100
        if change_pct > 1:
            return "up"
        elif change_pct < -1:
            return "down"
        return "flat"

    def _calc_ma60_direction_score(self, direction: str) -> int:
        """MA60方向分（满分20）"""
        if direction == "up":
            return 20
        elif direction == "flat":
            return 10
        return 0

    def _calc_relative_strength(
        self, df_stock: pd.DataFrame, df_index: pd.DataFrame
    ) -> float:
        """近20日相对大盘超额收益（%）"""
        if df_stock.empty or df_index.empty:
            return 0.0
        n = min(20, len(df_stock), len(df_index))
        if n < 5:
            return 0.0
        stock_ret = (
            float(df_stock["close"].iloc[-1]) / float(df_stock["close"].iloc[-n]) - 1
        ) * 100
        index_ret = (
            float(df_index["close"].iloc[-1]) / float(df_index["close"].iloc[-n]) - 1
        ) * 100
        return stock_ret - index_ret

    def _calc_rel_strength_score(self, rel_strength: float) -> int:
        """近20日相对强弱分（满分10）"""
        if rel_strength > 5:
            return 10
        elif rel_strength > 0:
            return 7
        elif rel_strength > -5:
            return 3
        return 0


# =============================================================================
# 第三层：技术面 + 催化剂筛选
# =============================================================================

@dataclass
class SignalResult:
    """技术信号评估结果（Layer 3）"""
    stock_code: str
    score: int                      # 总分（0-100）

    # 四项子分
    sector_strength_score: int = 0   # 板块强度分（0-40）
    volume_price_score: int = 0     # 量价行为分（0-40）
    turnover_score: int = 0         # 换手率分（0-20）
    restart_score: int = 0          # 再启动结构分（0-20）

    # 原始数据
    volume_ratio: float = 0.0
    change_pct: float = 0.0
    zdf60: float = 0.0              # 60日涨跌幅（%），板块动量代理指标
    turnover_rate: float = 0.0
    close_strength_pct: float = 0.0  # 收盘强度：close在高点的%
    ma20_slope: float = 0.0         # MA20斜率（日均变化率%）
    ma20_crossed: bool = False      # 近期是否上穿MA20
    volume_spike: bool = False       # 近期是否放量


class TechnicalSignalScorer:
    """
    第三层：技术面评估（Layer 3）

    评分体系（满分100）：
    1. 板块强度（40）：是否处于强势板块
    2. 量价行为（40）：放量、上涨、收盘强
    3. 换手率（20）：5%-15% 最健康
    4. 再启动结构（20）：近期是否出现启动信号
    """

    def __init__(self, fetcher_manager: DataFetcherManager):
        self.fm = fetcher_manager

    def run(self, stock_code: str, top_sectors: List[Dict] = None) -> SignalResult:
        """执行技术信号评估"""
        t0 = time.time()

        # 获取实时行情
        quote = self._fetch_realtime_quote(stock_code)

        # 获取日线数据（用于再启动结构判断）
        df = self._fetch_daily_data(stock_code, days=30)

        # ---- 四项子分 ----
        # change_60d 可能来自 ZhituFetcher（直接），也可能为 0（用 Tushare 等）
        zdf60_from_quote = float(getattr(quote, "change_60d", 0.0) or 0.0)
        if zdf60_from_quote == 0.0:
            # DataFetcherManager 未使用 ZhituFetcher，降级尝试直接调 Zhitu
            zdf60 = self._fetch_zdf60(stock_code)
        else:
            zdf60 = zdf60_from_quote
        sec_score = self._calc_sector_strength(quote, top_sectors or [], zdf60)

        vp_score, vol_ratio, chg_pct, close_str = self._calc_volume_price_score(quote)
        turn_score, turn_rate = self._calc_turnover_score(quote)
        restart_score, ma20_slope, ma20_crossed, vol_spike = self._calc_restart_structure(df, quote)

        total = sec_score + vp_score + turn_score + restart_score

        result = SignalResult(
            stock_code=stock_code,
            score=total,
            sector_strength_score=sec_score,
            volume_price_score=vp_score,
            turnover_score=turn_score,
            restart_score=restart_score,
            volume_ratio=vol_ratio,
            change_pct=chg_pct,
            zdf60=zdf60,
            turnover_rate=turn_rate,
            close_strength_pct=close_str,
            ma20_slope=ma20_slope,
            ma20_crossed=ma20_crossed,
            volume_spike=vol_spike,
        )

        elapsed = time.time() - t0
        logger.debug(
            f"[Signal] {stock_code} score={total} "
            f"(sec={sec_score} vp={vp_score} turn={turn_score} restart={restart_score}) "
            f"elapsed={elapsed:.2f}s"
        )
        return result

    def _fetch_realtime_quote(self, code: str):
        """获取实时行情（通过 DataFetcherManager）"""
        try:
            quote = self.fm.get_realtime_quote(code)
            if quote is not None:
                return quote
        except Exception as e:
            logger.warning(f"[Signal] get_realtime_quote({code}) failed: {e}")
        from data_provider.realtime_types import UnifiedRealtimeQuote
        return UnifiedRealtimeQuote(code=code)

    def _fetch_zdf60(self, code: str) -> float:
        """
        通过 ZhituFetcher 直接获取 60 日涨跌幅（zdf60）。

        原因：DataFetcherManager 可能优先使用 TushareFetcher，
        而 Tushare 不提供此字段。ZhituFetcher 提供 zdf60，
        可作为板块动量的代理指标。
        """
        try:
            from data_provider.zhitu_fetcher import ZhituFetcher
            zhitu = ZhituFetcher()
            quote = zhitu.get_realtime_quote(code)
            if quote is not None:
                zdf60 = float(getattr(quote, "change_60d", 0.0) or 0.0)
                if zdf60 != 0.0:
                    return zdf60
        except Exception:
            pass
        return 0.0

    def _fetch_daily_data(self, code: str, days: int) -> pd.DataFrame:
        """获取日线数据"""
        try:
            df, _ = self.fm.get_daily_data(code, days=days)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            logger.debug(f"[Signal] get_daily_data({code}) failed: {e}")
        return pd.DataFrame()

    # -------------------------------------------------------------------------
    # 子项 1：板块强度（40）
    # -------------------------------------------------------------------------
    def _calc_sector_strength(
        self, quote, top_sectors: List[Dict], zdf60: float
    ) -> int:
        """
        板块强度分（满分40）

        数据来源：智图实时行情的 zdf60（60日涨跌幅），作为板块动量的代理指标。

        原理：
        - 强势板块的成分股在60日内普遍有较高涨幅
        - 若某只股票zdf60排名靠前，且市场整体板块动量也强，则该股大概率处于主线上

        评分逻辑：
        - 主线（40）：zdf60 > 15% 且 领涨板块涨幅 > 3%
        - 次主线（25）：zdf60 > 8% 且 领涨板块涨幅 > 1.5%
        - 轮动（10）：zdf60 > 0%，或 领涨板块涨幅 > 3%（但zdf60一般）
        - 其他（0）：zdf60 ≤ 0
        """
        chg_pct = float(getattr(quote, "change_pct", 0.0) or 0.0)

        # 领涨板块的平均涨幅（衡量市场整体板块动量）
        if top_sectors:
            top_avg_chg = sum(float(s.get("change_pct", 0.0)) for s in top_sectors) / len(top_sectors)
        else:
            top_avg_chg = 0.0
        top_best_chg = float(top_sectors[0].get("change_pct", 0.0)) if top_sectors else 0.0

        strong_market = top_best_chg > 3.0    # 市场主线明确
        active_market = top_avg_chg > 1.5     # 板块轮动活跃

        # ---- 主线判断 ----
        if strong_market and zdf60 > 15:
            return 40
        if active_market and zdf60 > 8:
            return 40

        # ---- 次主线判断 ----
        if strong_market and zdf60 > 5:
            return 25
        if active_market and zdf60 > 3:
            return 25

        # ---- 轮动判断 ----
        # 有板块行情（即使股票自身zdf60一般，说明在参与板块轮动）
        if (strong_market or active_market) and zdf60 > 0:
            return 10

        # 股票自身有趋势（但不依赖板块）
        if zdf60 > 10:
            return 10

        return 0

    # -------------------------------------------------------------------------
    # 子项 2：量价行为（40）
    # -------------------------------------------------------------------------
    def _calc_volume_price_score(
        self, quote
    ) -> Tuple[int, float, float, float]:
        """
        量价行为分（满分40）

        三个条件（每个满足得1分）：
        1. 放量上涨：vol_ratio > 1.5 且 chg_pct > 1
        2. 收盘强：close 在日内高点的 97% 以上（收盘价距高点 < 3%）
        3. 涨幅合理：0 < chg_pct < 9%（不过热不衰退）

        得分：3项→40，2项→25，1项→10，0项→0
        """
        vol_ratio = float(getattr(quote, "volume_ratio", 1.0) or 1.0)
        chg_pct = float(getattr(quote, "change_pct", 0.0) or 0.0)
        price = float(getattr(quote, "price", 0.0) or 0.0)
        high = float(getattr(quote, "high", 0.0) or 0.0)

        # 收盘强度
        close_strength_pct = 0.0
        if high > 0 and price > 0:
            close_strength_pct = (price / high) * 100.0

        cond1 = vol_ratio > 1.5 and chg_pct > 1      # 放量上涨
        cond2 = close_strength_pct >= 97.0              # 收盘强
        cond3 = 0 < chg_pct < 9                        # 涨幅合理

        n_met = sum([cond1, cond2, cond3])

        if n_met >= 3:
            score = 40
        elif n_met == 2:
            score = 25
        elif n_met == 1:
            score = 10
        else:
            score = 0

        return score, vol_ratio, chg_pct, close_strength_pct

    # -------------------------------------------------------------------------
    # 子项 3：换手率（20）
    # -------------------------------------------------------------------------
    def _calc_turnover_score(self, quote) -> Tuple[int, float]:
        """
        换手率分（满分20）

        - 5%–15%：最健康，量价配合良好 → 20
        - 3%–5% 或 15%–25%：偏弱或偏强 → 10
        - 其他 → 0
        """
        turnover = float(getattr(quote, "turnover_rate", 0.0) or 0.0)

        if 5.0 <= turnover <= 15.0:
            score = 20
        elif (3.0 <= turnover < 5.0) or (15.0 < turnover <= 25.0):
            score = 10
        else:
            score = 0

        return score, turnover

    # -------------------------------------------------------------------------
    # 子项 4：再启动结构（20）
    # -------------------------------------------------------------------------
    def _calc_restart_structure(
        self, df: pd.DataFrame, quote
    ) -> Tuple[int, float, bool, bool]:
        """
        再启动结构分（满分20）

        信号条件（满足任一即算启动确认）：
        1. 价格上穿 MA20：今日收盘 > MA20，且昨日收盘 < MA20
        2. MA20 拐头向上：近5日 MA20 斜率由负转正

        注意：此接口仅用于判断结构，不重复 Layer 2 的斜率评分。
        """
        if df.empty or "ma20" not in df.columns:
            return 0, 0.0, False, False

        ma20_col = df["ma20"].dropna()
        if len(ma20_col) < 5:
            return 0, 0.0, False, False

        price = float(getattr(quote, "price", 0.0) or 0.0)
        close_series = df["close"]

        # MA20 值
        ma20_vals = ma20_col.iloc[-5:].values  # 最近5个MA20值
        ma20_now = float(ma20_col.iloc[-1])
        ma20_1d_ago = float(ma20_col.iloc[-2]) if len(ma20_col) >= 2 else ma20_now
        ma20_5d_ago = float(ma20_col.iloc[-5]) if len(ma20_col) >= 5 else ma20_now
        close_now = float(close_series.iloc[-1])
        close_1d_ago = float(close_series.iloc[-2]) if len(close_series) >= 2 else close_now

        # 收盘价相对MA20
        price_above_ma20 = close_now > ma20_now
        price_was_below_ma20 = close_1d_ago <= ma20_1d_ago
        ma20_crossed = price_above_ma20 and price_was_below_ma20

        # 近5日MA20斜率（判断是否拐头向上）
        if ma20_5d_ago == 0:
            ma20_slope = 0.0
        else:
            ma20_slope = (ma20_now - ma20_5d_ago) / ma20_5d_ago * 100.0
        ma20_turning_up = ma20_slope > 0 and ma20_1d_ago <= ma20_5d_ago

        # 放量信号（近3日平均成交量 > 近20日平均的1.5倍）
        vol_spike = False
        if "volume" in df.columns and len(df) >= 20:
            vol_recent = float(df["volume"].iloc[-3:].mean())
            vol_ma20 = float(df["volume"].iloc[-20:].mean())
            if vol_ma20 > 0 and vol_recent / vol_ma20 > 1.5:
                vol_spike = True

        # 任一启动信号 → 20分
        if ma20_crossed or (ma20_turning_up and vol_spike):
            return 20, ma20_slope, ma20_crossed, vol_spike

        return 0, ma20_slope, ma20_crossed, vol_spike


# =============================================================================
# 总调度：选股过滤 Pipeline
# =============================================================================

# 动态权重映射：根据大盘等级调整各层权重
DYNAMIC_WEIGHTS = {
    "strong_bull": {"market": 0.20, "position": 0.35, "signal": 0.45},
    "bull": {"market": 0.30, "position": 0.35, "signal": 0.35},
    "neutral": {"market": 0.40, "position": 0.30, "signal": 0.30},
    "bear": {"market": 0.50, "position": 0.30, "signal": 0.20},
}


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
    ma20_slope: float = 0.0        # MA20日均变化率%
    ma60_direction: str = ""       # MA60方向：up / flat / down
    relative_strength: float = 0.0
    volume_ratio: float = 0.0
    sector_name: str = ""
    change_pct: float = 0.0

    # Gate 结果
    gate_passed: bool = True        # 是否通过所有 Gate
    gate_results: Dict[str, bool] = field(default_factory=dict)  # 各Gate通过情况
    gate_reason: str = ""           # 未通过Gate的原因

    # 动态权重
    weights: Dict[str, float] = field(default_factory=dict)  # 使用的动态权重

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
        # 获取动态权重
        weights = DYNAMIC_WEIGHTS.get(market_result.level, DYNAMIC_WEIGHTS["neutral"])

        # === Hard Gate 检查 ===
        gate_results = {}
        gate_reason = ""

        # Gate 1: 大盘环境可接受（非 skip_all 或 strong_bear）
        gate1_pass = market_result.recommendation not in ("skip_all",)
        gate_results["gate1_market"] = gate1_pass
        if not gate1_pass:
            gate_reason = f"Gate1:大盘极弱({market_result.level} score={market_result.score})"

        # Gate 2: MA20趋势向上
        pos = self.position_scorer.run(code, index_code)
        gate_results["gate2_ma20"] = pos.ma20_slope >= 0
        if not gate_results["gate2_ma20"]:
            gate_reason = f"Gate2:MA20向下(slope={pos.ma20_slope:.4f}%)"

        # Gate 3: 回调结构健康（通过位置和技术信号判断）
        gate3_passed, gate3_reason = self._check_callback_structure(pos, market_result)
        gate_results["gate3_structure"] = gate3_passed
        if not gate3_passed:
            gate_reason = f"Gate3:{gate3_reason}"

        # 如果任何 Gate 未通过，返回跳过的结果
        if not all(gate_results.values()):
            return FilteredStock(
                stock_code=code,
                stock_name=name,
                market_score=market_result.score,
                market_level=market_result.level,
                position_score=pos.score,
                signal_score=0,
                composite_score=0.0,
                position_pct=round(pos.position_pct, 1),
                ma20_slope=pos.ma20_slope,
                ma60_direction=pos.ma60_direction,
                relative_strength=round(pos.relative_strength, 2),
                gate_passed=False,
                gate_results=gate_results,
                gate_reason=gate_reason,
                weights=weights,
                recommendation="skip",
                reason=gate_reason,
            )

        # 技术分
        sig = self.signal_scorer.run(code, market_result.top_sectors)

        # 复合评分：使用动态权重
        composite = (
            market_result.score * weights["market"]
            + pos.score * weights["position"]
            + sig.score * weights["signal"]
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
            relative_strength=round(pos.relative_strength, 2),
            volume_ratio=round(sig.volume_ratio, 2),
            sector_name="",
            change_pct=round(sig.change_pct, 2),
            ma60_direction=pos.ma60_direction,
            gate_passed=True,
            gate_results=gate_results,
            weights=weights,
            recommendation=recommendation,
            reason=reason,
        )

    def _check_callback_structure(
        self,
        pos: PositionResult,
        market_result: MarketEnvironmentResult,
    ) -> Tuple[bool, str]:
        """
        检查回调结构是否健康

        Returns:
            Tuple[是否通过, 原因]
        """
        # 条件1: 股票不能在高位(>80%)
        if pos.position_pct > 85:
            return False, f"位置偏高({pos.position_pct:.0f}%)"

        # 条件2: 近期没有异常放量下跌
        # 通过 change_pct 判断，跌幅过大且量能异常视为结构破坏
        # 注: sig.change_pct 在这里不可用，使用相对强弱作为代理
        if pos.relative_strength < -10:
            return False, f"相对强弱偏弱({pos.relative_strength:.1f}%)"

        # 条件3: 相对大盘不能太弱
        if pos.relative_strength < -15:
            return False, f"相对大盘过于弱势"

        return True, "结构健康"

    def _get_recommendation(
        self,
        composite: float,
        pos: PositionResult,
        sig: SignalResult,
        market: MarketEnvironmentResult,
    ) -> Tuple[str, str]:
        """根据评分给出建议（Hard Gate 已通过）"""
        # 高位股降权
        if pos.position_pct > 80:
            return "cautious", f"位置偏高({pos.position_pct:.0f}%)，控制仓位"

        # 根据复合评分给出建议
        if composite >= 55:
            return "analyze", "优先分析"
        elif composite >= 40:
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
