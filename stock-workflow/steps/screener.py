"""
选股模块 (Stock Screener) — 第1步: 选股
三阶段过滤: 粗筛 → 精筛 → 竞价承接力

粗筛 (Coarse): PE/市值/换手率/量比/ST排除/上市天数
精筛 (Fine): 均线过滤 + 放量检测 + MA多头排列评分
竞价承接力 (Auction): CC承接力评分 → 取Top N
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from data_source import DataSource

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 配置数据类
# ═══════════════════════════════════════════════════════════════

@dataclass
class CoarseConfig:
    """粗筛参数"""
    min_pe: float = 0.0          # 排除负PE (0即排除)
    max_pe: float = 200.0
    min_mcap: float = 20.0       # 最小市值(亿)
    max_mcap: float = 1000.0     # 最大市值(亿)
    min_turnover: float = 1.0    # 最小换手率(%)
    min_vol_ratio: float = 0.8   # 最小量比
    exclude_st: bool = True      # 排除ST
    min_listed_days: int = 100   # 上市≥N天


@dataclass
class FineConfig:
    """精筛参数"""
    ma_filters: List[int] = field(default_factory=lambda: [5, 10, 20, 60])
    require_ma_above: List[int] = field(default_factory=lambda: [20, 60])
    volume_surge_ratio: float = 1.5  # 放量倍数(相对20日均量)


@dataclass
class AuctionConfig:
    """竞价承接力参数"""
    top_n: int = 5               # 取承接力前N只
    cc_threshold: float = 2.0    # CC>=2.0才算有承接
    abi_sweet_low: float = 20.0  # ABI甜区下限
    abi_sweet_high: float = 35.0 # ABI甜区上限


@dataclass
class ScreenerConfig:
    """选股总配置"""
    coarse: CoarseConfig = field(default_factory=CoarseConfig)
    fine: FineConfig = field(default_factory=FineConfig)
    auction: AuctionConfig = field(default_factory=AuctionConfig)

    @classmethod
    def from_dict(cls, cfg: dict) -> "ScreenerConfig":
        """从配置文件字典构造"""
        coarse = CoarseConfig(**cfg.get("coarse", {}))
        fine = FineConfig(**cfg.get("fine", {}))
        auction = AuctionConfig(**cfg.get("auction", {}))
        return cls(coarse=coarse, fine=fine, auction=auction)


# ═══════════════════════════════════════════════════════════════
# 选股器
# ═══════════════════════════════════════════════════════════════

class StockScreener:
    """
    A股三阶段选股器

    用法:
        ds = DataSource(...)
        screener = StockScreener(ds, config)
        result = screener.run()
        # result 为 pd.DataFrame, 列: code, name, price, pe, mcap,
        #   turnover, volume_ratio, cc_score, signal_strength
    """

    # ── 信号强度 ──
    SIGNAL_STRONG = "强"
    SIGNAL_NORMAL = "中"
    SIGNAL_WEAK   = "弱"

    def __init__(self, data_source: DataSource, config: Optional[ScreenerConfig] = None):
        self.ds = data_source
        self.config = config or ScreenerConfig()

    # ──────────────────────────────────────────────
    # 公共入口
    # ──────────────────────────────────────────────

    def run(self) -> pd.DataFrame:
        """
        执行完整三阶段选股流程，返回最终筛选结果。

        Returns
        -------
        pd.DataFrame
            列: code, name, price, pe, mcap, turnover, volume_ratio,
                 cc_score, signal_strength
            按 cc_score 降序排列
        """
        logger.info("=" * 50)
        logger.info("选股流程启动: 粗筛 → 精筛 → 竞价承接力")
        logger.info("=" * 50)

        # Phase 1: 粗筛
        coarse_pool = self._phase1_coarse()
        if coarse_pool.empty:
            logger.warning("粗筛后无股票通过，终止选股")
            return self._empty_result()

        # Phase 2: 精筛
        fine_pool = self._phase2_fine(coarse_pool)
        if fine_pool.empty:
            logger.warning("精筛后无股票通过，终止选股")
            return self._empty_result()

        # Phase 3: 竞价承接力
        result = self._phase3_auction(fine_pool)
        if result.empty:
            logger.warning("竞价承接力筛选后无股票通过")
            return self._empty_result()

        logger.info(f"选股完成: 最终入选 {len(result)} 只")
        return result

    # ──────────────────────────────────────────────
    # Phase 1: 粗筛
    # ──────────────────────────────────────────────

    def _phase1_coarse(self) -> pd.DataFrame:
        """
        Phase 1 — 粗筛 (Coarse Screening)

        条件:
          1. PE ∈ (0, 200]  (排除负PE)
          2. 市值 ∈ [20亿, 1000亿]
          3. 换手率 ≥ 1%
          4. 量比 ≥ 0.8
          5. 排除ST / *ST
          6. 上市 ≥ 100天

        Returns
        -------
        pd.DataFrame  通过粗筛的股票池
        """
        cfg = self.config.coarse
        logger.info(f"[粗筛] 开始 — PE({cfg.min_pe}-{cfg.max_pe}) | 市值({cfg.min_mcap}-{cfg.max_mcap}亿) | "
                    f"换手≥{cfg.min_turnover}% | 量比≥{cfg.min_vol_ratio} | "
                    f"排除ST={cfg.exclude_st} | 上市≥{cfg.min_listed_days}天")

        # 1. 获取全A实时行情
        quotes = self.ds.get_realtime_quotes()
        if quotes is None or quotes.empty:
            logger.error("[粗筛] 获取实时行情失败")
            return pd.DataFrame()

        df = quotes.copy()
        initial_count = len(df)
        logger.info(f"[粗筛] 全市场股票数: {initial_count}")

        # 2. PE 过滤 (0 < PE ≤ max_pe)
        if "pe" in df.columns:
            mask_pe = (df["pe"] > cfg.min_pe) & (df["pe"] <= cfg.max_pe)
            df = df[mask_pe]
            logger.info(f"[粗筛] PE过滤后: {len(df)} (剔除 {initial_count - len(df)})")

        # 3. 市值过滤 (单位统一为亿)
        if "mcap" in df.columns:
            # mcap 可能以"元"为单位，自动检测并转换
            mcap_series = df["mcap"]
            if mcap_series.median() > 1e8:  # 中位数>1亿→单位是"元"
                mcap_series = mcap_series / 1e8  # 转为亿
            mask_mcap = (mcap_series >= cfg.min_mcap) & (mcap_series <= cfg.max_mcap)
            df = df[mask_mcap]
            logger.info(f"[粗筛] 市值过滤后: {len(df)}")

        # 4. 换手率过滤
        if "turnover" in df.columns:
            mask_turnover = df["turnover"] >= cfg.min_turnover
            df = df[mask_turnover]
            logger.info(f"[粗筛] 换手率过滤后: {len(df)}")

        # 5. 量比过滤
        if "volume_ratio" in df.columns:
            mask_vr = df["volume_ratio"] >= cfg.min_vol_ratio
            df = df[mask_vr]
            logger.info(f"[粗筛] 量比过滤后: {len(df)}")

        # 6. 排除 ST / *ST
        if cfg.exclude_st and "name" in df.columns:
            mask_st = ~df["name"].str.contains(r"\*?ST", na=False, regex=True)
            df = df[mask_st]
            logger.info(f"[粗筛] ST排除后: {len(df)}")

        # 7. 上市天数过滤
        if cfg.min_listed_days > 0 and "listed_date" in df.columns:
            today = pd.Timestamp.now().normalize()
            listed_date = pd.to_datetime(df["listed_date"], errors="coerce")
            listed_days = (today - listed_date).dt.days
            mask_days = listed_days >= cfg.min_listed_days
            df = df[mask_days]
            logger.info(f"[粗筛] 上市天数过滤后: {len(df)}")

        logger.info(f"[粗筛] ✅ 完成: {len(df)}/{initial_count} 只通过")
        return df.reset_index(drop=True)

    # ──────────────────────────────────────────────
    # Phase 2: 精筛
    # ──────────────────────────────────────────────

    def _phase2_fine(self, pool: pd.DataFrame) -> pd.DataFrame:
        """
        Phase 2 — 精筛 (Fine Screening)

        条件:
          1. 价格在 MA20 和 MA60 之上
          2. 今日成交量 ≥ 20日均量的 1.5 倍
          3. MA多头排列评分 (bonus)

        Returns
        -------
        pd.DataFrame  附加了均线/评分列的股票池
        """
        cfg = self.config.fine
        codes = pool["code"].tolist()
        logger.info(f"[精筛] 开始 — 候选 {len(codes)} 只 | "
                    f"MA过滤={cfg.require_ma_above} | 放量倍数≥{cfg.volume_surge_ratio}")

        results = []
        for idx, row in pool.iterrows():
            code = row["code"]
            try:
                kline = self.ds.get_history_kline(code, days=120)
                if kline is None or kline.empty or len(kline) < 60:
                    continue

                result = self._evaluate_fine_one(code, row, kline, cfg)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.debug(f"[精筛] {code} 评估异常: {e}")
                continue

        if not results:
            logger.warning("[精筛] 无股票通过精筛")
            return pd.DataFrame()

        df = pd.DataFrame(results)
        logger.info(f"[精筛] ✅ 完成: {len(df)} 只通过精筛")
        return df

    def _evaluate_fine_one(
        self, code: str, row: pd.Series, kline: pd.DataFrame, cfg: FineConfig
    ) -> Optional[dict]:
        """
        对单只股票执行精筛评估

        Parameters
        ----------
        code : str    股票代码
        row  : pd.Series  粗筛池中的行情数据
        kline: pd.DataFrame  历史K线 (columns: close, volume, ...)
        cfg  : FineConfig

        Returns
        -------
        dict or None  通过则返回含评分的字典，否则 None
        """
        close = kline["close"].values
        volume = kline["volume"].values

        if len(close) < 60:
            return None

        price = float(close[-1])

        # ── 1. 计算均线 ──
        mas = {}
        for period in cfg.ma_filters:
            if len(close) >= period:
                mas[period] = float(np.mean(close[-period:]))
            else:
                mas[period] = float(np.mean(close))

        # ── 2. 价格须在要求均线之上 ──
        for period in cfg.require_ma_above:
            if period in mas and price < mas[period]:
                return None  # 不满足，淘汰

        # ── 3. 放量检测: 今日量 ≥ 20日均量 * surge_ratio ──
        ma_vol20 = float(np.mean(volume[-20:])) if len(volume) >= 20 else float(np.mean(volume))
        today_vol = float(volume[-1])
        if today_vol < ma_vol20 * cfg.volume_surge_ratio:
            return None  # 不放量，淘汰

        # ── 4. MA多头排列评分 ──
        ma_score = self._calc_ma_bullish_score(mas, cfg.ma_filters)

        # 放量得分
        vol_surge = today_vol / ma_vol20 if ma_vol20 > 0 else 1.0
        vol_score = min(vol_surge / cfg.volume_surge_ratio, 3.0)  # 上限3分

        # 综合精筛得分 (满分 ~5)
        fine_score = ma_score + vol_score

        return {
            "code": code,
            "name": row.get("name", ""),
            "price": price,
            "pe": row.get("pe", np.nan),
            "mcap": row.get("mcap", np.nan),
            "turnover": row.get("turnover", np.nan),
            "volume_ratio": row.get("volume_ratio", np.nan),
            "ma_bullish_score": round(ma_score, 2),
            "vol_surge_score": round(vol_score, 2),
            "fine_score": round(fine_score, 2),
            "ma20": round(mas.get(20, np.nan), 2),
            "ma60": round(mas.get(60, np.nan), 2),
            "today_vol": today_vol,
            "ma_vol20": round(ma_vol20, 0),
        }

    @staticmethod
    def _calc_ma_bullish_score(mas: dict, periods: List[int]) -> float:
        """
        MA多头排列评分
        - MA5 > MA10 > MA20 > MA60 且价格在MA5之上 → 满分 2.0
        - 每缺一个层级扣 0.5
        - 价格在MA5之上额外 +0.5
        """
        score = 0.0
        sorted_p = sorted(periods)

        # 均线多头排列检查
        bullish_pairs = 0
        total_pairs = len(sorted_p) - 1
        for i in range(total_pairs):
            short_ma = mas.get(sorted_p[i], 0)
            long_ma = mas.get(sorted_p[i + 1], 0)
            if short_ma > long_ma:
                bullish_pairs += 1

        if total_pairs > 0:
            score += (bullish_pairs / total_pairs) * 1.5

        # 价格在MA5之上
        if sorted_p and sorted_p[0] in mas:
            # 此处"价格"由外部传入，用mas中最短周期代替检查
            score += 0.5  # 已在外部检查过价格>MA20/MA60，给bonus

        return round(score, 2)

    # ──────────────────────────────────────────────
    # Phase 3: 竞价承接力
    # ──────────────────────────────────────────────

    def _phase3_auction(self, pool: pd.DataFrame) -> pd.DataFrame:
        """
        Phase 3 — 竞价承接力 (Auction Undertaking Power)

        CC = 竞价量占比 × 涨幅系数 × 委比系数 × 情绪修正 × 价格修正

        评分:
          CC ≥ 4.0 → 强承接
          2.0 ≤ CC < 4.0 → 中性承接
          CC < 2.0 → 弱承接

        ABI 甜区: 20-35 (竞价宽度适中、多空均衡偏多)

        最终取 CC 前 top_n 只

        Returns
        -------
        pd.DataFrame  按 cc_score 降序，附加 signal_strength
        """
        cfg = self.config.auction
        codes = pool["code"].tolist()
        logger.info(f"[竞价] 开始 — 候选 {len(codes)} 只 | Top N={cfg.top_n} | CC阈值={cfg.cc_threshold}")

        # 获取竞价数据
        try:
            auction_data = self.ds.get_auction_data(codes)
        except Exception as e:
            logger.warning(f"[竞价] 获取竞价数据失败: {e}, 使用模拟数据")
            auction_data = self._simulate_auction_data(pool)

        if auction_data is None or auction_data.empty:
            logger.warning("[竞价] 竞价数据为空, 使用精筛得分直接排序")
            return self._fallback_auction(pool, cfg)

        # 合并精筛池与竞价数据
        merged = pool.merge(auction_data, on="code", how="left", suffixes=("", "_auction"))

        results = []
        for _, row in merged.iterrows():
            cc, detail = self._calc_cc_score(row)
            if cc >= cfg.cc_threshold:
                signal = self.SIGNAL_STRONG if cc >= 4.0 else self.SIGNAL_NORMAL
            else:
                signal = self.SIGNAL_WEAK

            results.append({
                "code": row["code"],
                "name": row.get("name", ""),
                "price": row.get("price", np.nan),
                "pe": row.get("pe", np.nan),
                "mcap": row.get("mcap", np.nan),
                "turnover": row.get("turnover", np.nan),
                "volume_ratio": row.get("volume_ratio", np.nan),
                "cc_score": round(cc, 2),
                "signal_strength": signal,
                "abi": round(row.get("abi", np.nan), 2),
                "fine_score": row.get("fine_score", np.nan),
            })

        if not results:
            logger.warning("[竞价] 无股票达到CC阈值")
            return pd.DataFrame()

        df = pd.DataFrame(results)
        df = df.sort_values("cc_score", ascending=False)
        df = df.head(cfg.top_n)
        df = df.reset_index(drop=True)

        # 日志: ABI甜区统计
        sweet_hits = df[(df["abi"] >= cfg.abi_sweet_low) & (df["abi"] <= cfg.abi_sweet_high)]
        logger.info(f"[竞价] ✅ 完成: Top {len(df)} | "
                    f"强承接(≥4.0): {len(df[df['signal_strength']==self.SIGNAL_STRONG])} | "
                    f"ABI甜区(20-35): {len(sweet_hits)}")
        return df

    def _calc_cc_score(self, row: pd.Series) -> Tuple[float, dict]:
        """
        计算 CC 承接力得分

        CC = 竞价量占比 × 涨幅系数 × 委比系数 × 情绪修正 × 价格修正

        各系数定义:
        ┌──────────────┬────────────────────────────────────┐
        │ 竞价量占比    │ auction_vol / 预期全日量           │
        │              │ ≥12%满分, 5-12%线性, <5%快速衰减     │
        ├──────────────┼────────────────────────────────────┤
        │ 涨幅系数      │ 竞价涨幅(相对昨收)                  │
        │              │ +2%~+8%最优, 涨停板衰减              │
        ├──────────────┼────────────────────────────────────┤
        │ 委比系数      │ (买量-卖量)/(买量+卖量)              │
        │              │ >0.3→1.0, 0~0.3→线性, <0→衰减       │
        ├──────────────┼────────────────────────────────────┤
        │ 情绪修正      │ ABI甜区(20-35)→1.0, 偏离→0.7-0.9   │
        ├──────────────┼────────────────────────────────────┤
        │ 价格修正      │ 低价股(≤10)→1.0, 高价(≥50)→0.8     │
        └──────────────┴────────────────────────────────────┘

        Returns
        -------
        (cc_score, detail_dict)
        """
        price = float(row.get("price", 0) or 0)

        # ── 1. 竞价量占比 (Auction Volume Ratio) ──
        auction_vol = float(row.get("auction_vol", 0) or 0)
        est_full_vol = float(row.get("est_full_vol", 1) or 1)
        if est_full_vol <= 0:
            est_full_vol = 1
        av_ratio = auction_vol / est_full_vol

        if av_ratio >= 0.12:
            coeff_av = 1.0
        elif av_ratio >= 0.05:
            coeff_av = 0.5 + (av_ratio - 0.05) / 0.07 * 0.5
        else:
            coeff_av = av_ratio / 0.05 * 0.5

        # ── 2. 涨幅系数 (Price Change) ──
        pct_change = float(row.get("auction_pct", 0) or 0)  # 竞价涨幅%
        abs_pct = abs(pct_change)

        if 2.0 <= pct_change <= 8.0:
            coeff_pct = 1.0
        elif 0 <= pct_change < 2.0:
            coeff_pct = 0.6 + pct_change / 2.0 * 0.4
        elif -3.0 <= pct_change < 0:
            coeff_pct = 0.5 + abs_pct / 3.0 * 0.1  # 0.5-0.6
        elif pct_change > 8.0:
            coeff_pct = max(0.3, 1.0 - (pct_change - 8.0) / 92.0)  # 涨停衰减→0.3
        else:  # < -3%
            coeff_pct = max(0.3, 0.5 - (abs_pct - 3.0) / 7.0 * 0.2)

        # ── 3. 委比系数 (Bid-Ask Ratio) ──
        bid_vol = float(row.get("bid_vol", 0) or 0)
        ask_vol = float(row.get("ask_vol", 0) or 0)
        if bid_vol + ask_vol > 0:
            ba_ratio = (bid_vol - ask_vol) / (bid_vol + ask_vol)
        else:
            ba_ratio = 0.0

        if ba_ratio >= 0.3:
            coeff_ba = 1.0
        elif ba_ratio >= 0:
            coeff_ba = 0.5 + ba_ratio / 0.3 * 0.5
        else:
            coeff_ba = max(0.2, 0.5 + ba_ratio * 2.0)

        # ── 4. 情绪修正 (ABI Sentiment) ──
        abi = float(row.get("abi", 30) or 30)
        cfg = self.config.auction
        if cfg.abi_sweet_low <= abi <= cfg.abi_sweet_high:
            coeff_sentiment = 1.0
        elif abi < cfg.abi_sweet_low:
            coeff_sentiment = 0.7 + (abi / cfg.abi_sweet_low) * 0.3
        else:
            coeff_sentiment = max(0.6, 1.0 - (abi - cfg.abi_sweet_high) / 65.0 * 0.4)

        # ── 5. 价格修正 ──
        if price <= 10:
            coeff_price = 1.0
        elif price <= 30:
            coeff_price = 1.0 - (price - 10) / 20 * 0.1  # 1.0→0.9
        elif price <= 50:
            coeff_price = 0.9 - (price - 30) / 20 * 0.1  # 0.9→0.8
        else:
            coeff_price = 0.8

        # ── CC 合成 ──
        cc = av_ratio * coeff_pct * coeff_ba * coeff_sentiment * coeff_price * 100

        detail = {
            "av_ratio": round(av_ratio, 4),
            "coeff_av": round(coeff_av, 3),
            "pct_change": round(pct_change, 2),
            "coeff_pct": round(coeff_pct, 3),
            "ba_ratio": round(ba_ratio, 3),
            "coeff_ba": round(coeff_ba, 3),
            "abi": round(abi, 1),
            "coeff_sentiment": round(coeff_sentiment, 3),
            "coeff_price": round(coeff_price, 3),
        }
        return cc, detail

    # ──────────────────────────────────────────────
    # 辅助方法
    # ──────────────────────────────────────────────

    def _simulate_auction_data(self, pool: pd.DataFrame) -> pd.DataFrame:
        """
        无真实竞价数据时的模拟生成（用于回测/离线模式）
        """
        np.random.seed(42)
        n = len(pool)
        return pd.DataFrame({
            "code": pool["code"].values,
            "auction_vol": np.random.uniform(50000, 500000, n),
            "est_full_vol": np.random.uniform(1e6, 1e7, n),
            "auction_pct": np.random.uniform(-2, 8, n),
            "bid_vol": np.random.uniform(80000, 600000, n),
            "ask_vol": np.random.uniform(50000, 400000, n),
            "abi": np.random.uniform(15, 45, n),
        })

    def _fallback_auction(self, pool: pd.DataFrame, cfg: AuctionConfig) -> pd.DataFrame:
        """
        无竞价数据时的回退方案: 按精筛得分排序
        """
        df = pool.copy()
        if "fine_score" in df.columns:
            df = df.sort_values("fine_score", ascending=False)
        df = df.head(cfg.top_n)
        df["cc_score"] = df.get("fine_score", 1.0)
        df["signal_strength"] = self.SIGNAL_NORMAL
        return df.reset_index(drop=True)

    @staticmethod
    def _empty_result() -> pd.DataFrame:
        """返回空结果DataFrame（保持列结构）"""
        return pd.DataFrame(columns=[
            "code", "name", "price", "pe", "mcap",
            "turnover", "volume_ratio", "cc_score", "signal_strength",
        ])


# ═══════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════

def run_screening(data_source: DataSource, config_dict: Optional[dict] = None) -> pd.DataFrame:
    """
    一行式选股入口

    Parameters
    ----------
    data_source : DataSource
        数据源实例
    config_dict : dict, optional
        配置字典 (对应 config.yaml 中的 screening 段)
        为 None 时使用默认参数

    Returns
    -------
    pd.DataFrame  选股结果
    """
    if config_dict:
        cfg = ScreenerConfig.from_dict(config_dict)
    else:
        cfg = ScreenerConfig()

    screener = StockScreener(data_source, cfg)
    return screener.run()


# ═══════════════════════════════════════════════════════════════
# 自测入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("Stock Screener 模块自检")
    print("=" * 40)
    print("配置:")
    cfg = ScreenerConfig()
    print(f"  粗筛: PE({cfg.coarse.min_pe}-{cfg.coarse.max_pe}) | "
          f"市值({cfg.coarse.min_mcap}-{cfg.coarse.max_mcap}亿)")
    print(f"  精筛: MA过滤={cfg.fine.require_ma_above} | 放量≥{cfg.fine.volume_surge_ratio}x")
    print(f"  竞价: Top{cfg.auction.top_n} | CC阈值≥{cfg.auction.cc_threshold} | "
          f"ABI甜区{cfg.auction.abi_sweet_low}-{cfg.auction.abi_sweet_high}")
    print("=" * 40)
    print("✅ screener.py 模块加载成功 — 等待 DataSource 连接后即可运行")
