#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Server酱 Turbo 推送模块 — 限流 + 多渠道 fallback
==================================================
API:  https://sctapi.ftqq.com/{token}.send
文档: https://sct.ftqq.com/

支持格式:
  - text:    纯文本消息
  - markdown: Markdown 格式化消息

限流: 最多 5 次/分钟 (Server酱免费版限制)
Fallback: 企业微信 Webhook / 钉钉 Webhook (可选)
"""

from __future__ import annotations

import time
import threading
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict

import requests

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════════

SCT_API = "https://sctapi.ftqq.com/{token}.send"
MAX_PUSHES_PER_MINUTE = 5
WINDOW_SECONDS = 60


# ═══════════════════════════════════════════════════════════════════════
# 限流器
# ═══════════════════════════════════════════════════════════════════════

class RateLimiter:
    """滑动窗口限流器 — 线程安全"""

    def __init__(self, max_calls: int = MAX_PUSHES_PER_MINUTE, window: float = WINDOW_SECONDS):
        self._max = max_calls
        self._window = window
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """
        尝试获取一次发送许可。

        Returns
        -------
        bool  True=允许发送, False=已达上限需等待
        """
        with self._lock:
            now = time.time()
            # 清理窗口外的旧记录
            while self._timestamps and now - self._timestamps[0] > self._window:
                self._timestamps.popleft()

            if len(self._timestamps) < self._max:
                self._timestamps.append(now)
                return True
            return False

    def wait_until_available(self, timeout: float = 65.0) -> bool:
        """
        阻塞等待直到有发送配额。

        Returns
        -------
        bool  True=获得配额, False=超时
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.acquire():
                return True
            time.sleep(0.5)
        return False

    @property
    def remaining(self) -> int:
        """剩余可用发送次数"""
        with self._lock:
            now = time.time()
            while self._timestamps and now - self._timestamps[0] > self._window:
                self._timestamps.popleft()
            return max(0, self._max - len(self._timestamps))


# ═══════════════════════════════════════════════════════════════════════
# Notifier 主类
# ═══════════════════════════════════════════════════════════════════════

class Notifier:
    """
    Server酱 Turbo 推送器

    用法:
        nf = Notifier(token="SCT...")
        nf.send_text("标题", "内容")
        nf.send_markdown("## 标题", "**粗体** 内容")

        # 股票预警模板
        nf.stop_loss_alert("600519", -5.2)
        nf.take_profit_alert("000858", +12.3)
        nf.buy_signal_alert("688017", "首板横盘起爆", 85)
        nf.daily_summary({...})
    """

    def __init__(
        self,
        token: str = "",
        wechat_webhook: str = "",
        dingtalk_webhook: str = "",
        dry_run: bool = False,
    ):
        """
        Parameters
        ----------
        token : str
            Server酱 Turbo Token (SCT开头)
        wechat_webhook : str
            企业微信机器人 Webhook (可选 fallback)
        dingtalk_webhook : str
            钉钉机器人 Webhook (可选 fallback)
        dry_run : bool
            True=模拟模式, 不实际发送
        """
        self.token = token
        self.wechat_webhook = wechat_webhook
        self.dingtalk_webhook = dingtalk_webhook
        self.dry_run = dry_run

        self._limiter = RateLimiter()
        self._stats = {
            "sent": 0,
            "blocked": 0,
            "errors": 0,
            "fallback_wechat": 0,
            "fallback_dingtalk": 0,
            "last_send": None,
        }

    # ── 核心发送方法 ─────────────────────────────────────────────────

    def send_text(self, title: str, content: str = "") -> bool:
        """
        发送纯文本消息 (Server酱 text 格式)

        Parameters
        ----------
        title : str
            消息标题 (必填, 最多256字符)
        content : str
            消息正文 (选填, 支持 \\n 换行)

        Returns
        -------
        bool  True=发送成功
        """
        title = title[:256]
        return self._send(title=title, desp=content)

    def send_markdown(self, title: str, content: str = "") -> bool:
        """
        发送 Markdown 消息 (Server酱 markdown 格式)

        Parameters
        ----------
        title : str
            消息标题 (必填, 最多256字符)
        content : str
            Markdown 格式正文 (支持 ## ### **bold** `code` 等)

        Returns
        -------
        bool  True=发送成功
        """
        title = title[:256]
        # 构造符合 Server酱 markdown 格式的消息体
        md_content = (
            f"# {title}\n\n"
            f"{content}\n\n"
            f"---\n"
            f"*发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )
        return self._send(title=title, desp=md_content)

    def _send(self, title: str, desp: str = "") -> bool:
        """
        底层发送 — 含限流检查 + fallback 逻辑

        Returns
        -------
        bool  True=至少一个渠道发送成功
        """
        # 限流检查
        if not self._limiter.acquire():
            logger.warning(f"[Notify] 已达分钟限流({MAX_PUSHES_PER_MINUTE}次/分), 消息丢弃: {title[:40]}...")
            self._stats["blocked"] += 1
            return False

        # 模拟模式
        if self.dry_run:
            logger.info(f"[Notify-DRY] 模拟推送: [{title}]")
            self._stats["sent"] += 1
            self._stats["last_send"] = time.time()
            return True

        # 尝试 Server酱
        sent = self._push_sct(title, desp)
        if sent:
            return True

        # Fallback: 企业微信
        if self.wechat_webhook:
            sent = self._push_wechat(title, desp)
            if sent:
                self._stats["fallback_wechat"] += 1
                return True

        # Fallback: 钉钉
        if self.dingtalk_webhook:
            sent = self._push_dingtalk(title, desp)
            if sent:
                self._stats["fallback_dingtalk"] += 1
                return True

        logger.error(f"[Notify] 所有渠道发送失败: {title[:40]}")
        self._stats["errors"] += 1
        return False

    def _push_sct(self, title: str, desp: str) -> bool:
        """Server酱 Turbo 发送"""
        if not self.token:
            logger.debug("[Notify] 未配置 SCT Token, 跳过 Server酱")
            return False

        url = SCT_API.format(token=self.token)
        payload = {"title": title, "desp": desp}

        try:
            resp = requests.post(url, data=payload, timeout=15)
            result = resp.json()
            if result.get("code") == 0:
                logger.info(f"[Notify-SCT] ✅ 推送成功: {title[:40]}")
                self._stats["sent"] += 1
                self._stats["last_send"] = time.time()
                return True
            else:
                logger.warning(f"[Notify-SCT] ❌ 推送失败: {result.get('message', 'unknown')} | title={title[:40]}")
                return False
        except requests.RequestException as e:
            logger.error(f"[Notify-SCT] 网络异常: {e}")
            return False
        except Exception as e:
            logger.error(f"[Notify-SCT] 未知错误: {e}")
            return False

    def _push_wechat(self, title: str, desp: str) -> bool:
        """企业微信 Webhook fallback"""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"**{title}**\n{desp}"
            }
        }
        try:
            resp = requests.post(self.wechat_webhook, json=payload, timeout=10)
            if resp.status_code == 200 and resp.json().get("errcode") == 0:
                logger.info(f"[Notify-WeChat] ✅ Fallback 推送成功: {title[:40]}")
                self._stats["sent"] += 1
                self._stats["last_send"] = time.time()
                return True
            else:
                logger.warning(f"[Notify-WeChat] ❌ Fallback 推送失败: {resp.text[:100]}")
                return False
        except Exception as e:
            logger.error(f"[Notify-WeChat] 异常: {e}")
            return False

    def _push_dingtalk(self, title: str, desp: str) -> bool:
        """钉钉 Webhook fallback"""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"### {title}\n\n{desp}"
            }
        }
        try:
            resp = requests.post(self.dingtalk_webhook, json=payload, timeout=10)
            if resp.status_code == 200 and resp.json().get("errcode") == 0:
                logger.info(f"[Notify-DingTalk] ✅ Fallback 推送成功: {title[:40]}")
                self._stats["sent"] += 1
                self._stats["last_send"] = time.time()
                return True
            else:
                logger.warning(f"[Notify-DingTalk] ❌ Fallback 推送失败: {resp.text[:100]}")
                return False
        except Exception as e:
            logger.error(f"[Notify-DingTalk] 异常: {e}")
            return False

    # ── 股票预警模板 ─────────────────────────────────────────────────

    def stop_loss_alert(self, stock: str, loss_pct: float) -> bool:
        """
        止损预警

        Parameters
        ----------
        stock : str
            股票代码/名称
        loss_pct : float
            亏损百分比 (负数)

        Returns
        -------
        bool  发送是否成功
        """
        emoji = "🚨" if abs(loss_pct) >= 5 else "⚠️"
        title = f"{emoji} 止损预警: {stock}"
        content = (
            f"**股票**: {stock}\n"
            f"**亏损幅度**: {loss_pct:+.2f}%\n"
            f"**触发时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"> 已触发止损条件，请立即检查持仓！"
        )
        return self.send_markdown(title, content)

    def take_profit_alert(self, stock: str, profit_pct: float) -> bool:
        """
        止盈预警

        Parameters
        ----------
        stock : str
            股票代码/名称
        profit_pct : float
            盈利百分比

        Returns
        -------
        bool  发送是否成功
        """
        emoji = "🎉" if profit_pct >= 10 else "📈"
        title = f"{emoji} 止盈预警: {stock}"
        content = (
            f"**股票**: {stock}\n"
            f"**盈利幅度**: {profit_pct:+.2f}%\n"
            f"**触发时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"> 已触发止盈条件，建议评估是否锁定利润。"
        )
        return self.send_markdown(title, content)

    def buy_signal_alert(self, stock: str, signal: str, score: float) -> bool:
        """
        买入信号预警

        Parameters
        ----------
        stock : str
            股票代码/名称
        signal : str
            信号类型 (如 "首板横盘起爆")
        score : float
            信号评分 (0-100)

        Returns
        -------
        bool  发送是否成功
        """
        if score >= 80:
            emoji = "🔥"
            strength = "强信号"
        elif score >= 60:
            emoji = "📊"
            strength = "中信号"
        else:
            emoji = "👀"
            strength = "弱信号"

        title = f"{emoji} 买入信号: {stock}"
        content = (
            f"**股票**: {stock}\n"
            f"**信号类型**: {signal}\n"
            f"**评分**: {score:.0f}/100 ({strength})\n"
            f"**触发时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"> 系统检测到买入信号，请评估后决策。"
        )
        return self.send_markdown(title, content)

    def daily_summary(self, summary: dict) -> bool:
        """
        每日复盘汇总

        Parameters
        ----------
        summary : dict
            {
                "date": "2026-06-17",
                "total_signals": 8,
                "buy_signals": 3,
                "stop_loss_alerts": 1,
                "take_profit_alerts": 2,
                "positions": [...],
                "pnl": +12345.67,
                "pnl_pct": +1.23,
                "top_picks": [...],
                "market_comment": "整体偏强...",
            }

        Returns
        -------
        bool  发送是否成功
        """
        date = summary.get("date", datetime.now().strftime("%Y-%m-%d"))
        total_signals = summary.get("total_signals", 0)
        buy_signals = summary.get("buy_signals", 0)
        stop_alerts = summary.get("stop_loss_alerts", 0)
        profit_alerts = summary.get("take_profit_alerts", 0)
        pnl = summary.get("pnl", 0)
        pnl_pct = summary.get("pnl_pct", 0)

        pnl_emoji = "🟢" if pnl > 0 else ("🔴" if pnl < 0 else "⚪")

        title = f"📋 每日复盘 {date}"
        content = f"## 今日概览\n\n"

        # 收益
        content += f"| 指标 | 数值 |\n|------|------|\n"
        content += f"| 当日收益 | {pnl_emoji} {pnl:+,.2f} ({pnl_pct:+.2f}%) |\n"
        content += f"| 买入信号 | {buy_signals} 只 |\n"
        content += f"| 止损触发 | {stop_alerts} 次 |\n"
        content += f"| 止盈触发 | {profit_alerts} 次 |\n"
        content += f"| 总信号数 | {total_signals} |\n\n"

        # 持仓
        positions = summary.get("positions", [])
        if positions:
            content += "## 当前持仓\n\n"
            content += "| 股票 | 成本 | 现价 | 盈亏% | 策略 |\n"
            content += "|------|------|------|-------|------|\n"
            for pos in positions[:10]:
                content += (
                    f"| {pos.get('stock', '-')} "
                    f"| {pos.get('cost', 0):.2f} "
                    f"| {pos.get('price', 0):.2f} "
                    f"| {pos.get('pnl_pct', 0):+.2f}% "
                    f"| {pos.get('strategy', '-')} |\n"
                )
            if len(positions) > 10:
                content += f"| ... | ... | ... | ... | (共{len(positions)}只) |\n"
        content += "\n"

        # Top Picks
        top_picks = summary.get("top_picks", [])
        if top_picks:
            content += "## 明日关注\n\n"
            for i, pick in enumerate(top_picks[:5], 1):
                content += (
                    f"{i}. **{pick.get('stock', '-')}** "
                    f"— {pick.get('signal', '-')} "
                    f"(评分{pick.get('score', 0):.0f})\n"
                )
            content += "\n"

        # 市场点评
        comment = summary.get("market_comment", "")
        if comment:
            content += f"---\n> {comment}\n"

        return self.send_markdown(title, content)

    # ── 状态属性 ─────────────────────────────────────────────────────

    @property
    def stats(self) -> dict:
        """发送统计"""
        return {
            **self._stats,
            "rate_limit_remaining": self._limiter.remaining,
        }

    @property
    def configured(self) -> bool:
        """是否至少配置了一个通知渠道"""
        return bool(self.token or self.wechat_webhook or self.dingtalk_webhook)

    def __repr__(self) -> str:
        return (
            f"Notifier(sct={'✓' if self.token else '✗'}, "
            f"wechat={'✓' if self.wechat_webhook else '✗'}, "
            f"dingtalk={'✓' if self.dingtalk_webhook else '✗'}, "
            f"dry_run={self.dry_run}, "
            f"remaining={self._limiter.remaining}/{MAX_PUSHES_PER_MINUTE})"
        )


# ═══════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════

def create_notifier_from_config(config: dict, dry_run: bool = False) -> Notifier:
    """
    从 config.yaml 的 notify 段创建 Notifier 实例

    Parameters
    ----------
    config : dict
        完整配置字典 (需包含 'notify' 键)
    dry_run : bool
        模拟模式

    Returns
    -------
    Notifier
    """
    ncfg = config.get("notify", {})
    return Notifier(
        token=ncfg.get("sct_token", ""),
        wechat_webhook=ncfg.get("wechat_webhook", ""),
        dingtalk_webhook=ncfg.get("dingtalk_webhook", ""),
        dry_run=dry_run,
    )


# ═══════════════════════════════════════════════════════════════════════
# 自测入口
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("  Server酱 Turbo 推送模块 - 自测")
    print("=" * 60)

    # 创建 Notifier (模拟模式)
    nf = Notifier(dry_run=True)
    print(f"\n{nf}")

    # 测试各模板
    print("\n── 止损预警 ──")
    nf.stop_loss_alert("600519 贵州茅台", -5.2)

    print("\n── 止盈预警 ──")
    nf.take_profit_alert("000858 五粮液", +12.3)

    print("\n── 买入信号 ──")
    nf.buy_signal_alert("688017 绿的谐波", "首板横盘起爆", 85)

    print("\n── 每日汇总 ──")
    nf.daily_summary({
        "date": "2026-06-17",
        "total_signals": 8,
        "buy_signals": 3,
        "stop_loss_alerts": 1,
        "take_profit_alerts": 2,
        "pnl": +12345.67,
        "pnl_pct": +1.23,
        "positions": [
            {"stock": "600519", "cost": 1500.00, "price": 1520.50, "pnl_pct": 1.37, "strategy": "首板起爆"},
            {"stock": "000858", "cost": 120.00, "price": 118.50, "pnl_pct": -1.25, "strategy": "涨停回踩"},
        ],
        "top_picks": [
            {"stock": "688017", "signal": "首板横盘起爆", "score": 85},
            {"stock": "300476", "signal": "涨停回踩", "score": 72},
        ],
        "market_comment": "今日大盘窄幅震荡，科技股活跃，消费股回调。",
    })

    print(f"\n统计: {nf.stats}")
    print(f"\n✅ pusher.py 自测完成")
