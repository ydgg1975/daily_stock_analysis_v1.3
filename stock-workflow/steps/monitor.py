#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Step 4: 监控模块 (Monitor) — 实时轮询 + 告警
───────────────────────────────────────────────
功能:
  1. 实时价格轮询 (可配置间隔, 默认30秒)
  2. 仅交易时段运行 (09:30-11:30, 13:00-15:00)
  3. 后台线程, 线程安全
  4. 告警触发: 止损/止盈/破位/放量
  5. Start / Pause / Resume / Stop 控制
  6. 移动止盈跟踪
  7. 批量获取行情 (get_quote)

兼容接口:
  - Monitor(positions, data_source, config)  # 新版
  - Monitor(data_source, positions, config, on_alert)  # 旧版兼容

使用方式:
    from steps.monitor import Monitor
    mon = Monitor(positions=plans, data_source=ds, config=cfg)
    mon.on_stop_loss = lambda e: send_alert(e)
    mon.start()
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, time as dt_time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from data_source import DataSource

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

class MonitorStatus(Enum):
    """监控器状态"""
    IDLE    = "idle"
    RUNNING = "running"
    PAUSED  = "paused"
    STOPPED = "stopped"


@dataclass
class AlertEvent:
    """告警事件 (新版)"""
    type: str                        # stop_loss / take_profit / breakout / volume_surge / trailing
    stock_code: str
    stock_name: str
    message: str
    price: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "message": self.message,
            "price": self.price,
            "timestamp": self.timestamp,
        }


@dataclass
class Alert:
    """告警事件 (旧版兼容)"""
    stock: str
    alert_type: str
    message: str
    severity: str = "info"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class PositionSnapshot:
    """持仓快照 — 用于跟踪状态变化"""
    stock_code: str
    stock_name: str
    entry_price: float
    position_size: int
    stop_loss: float
    take_profit: float
    current_price: float = 0.0
    profit_pct: float = 0.0
    trailing_stop: float = 0.0
    alerted_stop_loss: bool = False
    alerted_take_profit: bool = False

    @property
    def is_stop_loss_hit(self) -> bool:
        if self.current_price <= 0 or self.stop_loss <= 0:
            return False
        effective_stop = max(self.stop_loss, self.trailing_stop)
        return self.current_price <= effective_stop

    @property
    def is_take_profit_hit(self) -> bool:
        if self.current_price <= 0 or self.take_profit <= 0:
            return False
        return self.current_price >= self.take_profit


# ═══════════════════════════════════════════════════════════════
# 主类: Monitor
# ═══════════════════════════════════════════════════════════════

class Monitor:
    """
    实时价格监控器 — 后台线程轮询, 自动告警。

    告警回调:
        on_stop_loss(event)    → 止损触发
        on_take_profit(event)  → 止盈触发
        on_breakout(event)     → 破位告警
        on_volume_surge(event) → 放量告警
        on_trailing(event)     → 移动止盈生效
        on_alert(event)        → 所有告警兜底

    参数:
        positions:   持仓计划列表 [dict]
        data_source: DataSource 实例
        config:      配置字典 (config.yaml)
    """

    TRADING_HOURS_DEFAULT = {
        "morning_start": "09:30", "morning_end": "11:30",
        "afternoon_start": "13:00", "afternoon_end": "15:00",
    }

    def __init__(
        self,
        positions_or_ds: Any = None,
        data_source_or_positions: Any = None,
        config: Optional[Dict[str, Any]] = None,
        on_alert: Optional[Callable] = None,
    ):
        """
        智能构造器 — 兼容新旧两种调用方式:
            Monitor(positions_list, data_source, config)       # 新版
            Monitor(data_source, positions_list, config, cb)   # 旧版
        """
        # 自动检测参数顺序
        if isinstance(positions_or_ds, DataSource) or (
            hasattr(positions_or_ds, "get_quote") and not isinstance(positions_or_ds, list)
        ):
            # 旧版: Monitor(data_source, positions, config, on_alert)
            ds = positions_or_ds
            positions = data_source_or_positions if isinstance(data_source_or_positions, list) else []
            cfg = config if isinstance(config, dict) else {}
            self.on_alert = on_alert if callable(on_alert) else None
        else:
            # 新版: Monitor(positions, data_source, config)
            positions = positions_or_ds if isinstance(positions_or_ds, list) else []
            ds = data_source_or_positions
            cfg = config if isinstance(config, dict) else {}
            self.on_alert = None

        self._ds = ds
        self._cfg = cfg

        # ── 监控参数 ──
        mon = self._cfg.get("monitor", {})
        self.interval = mon.get("interval", 30)
        trading_hours = mon.get("trading_hours", self.TRADING_HOURS_DEFAULT)
        self._trading_hours = {**self.TRADING_HOURS_DEFAULT, **trading_hours}

        # ── 告警开关 ──
        alerts_cfg = mon.get("alerts", {})
        self.alert_stop_loss    = alerts_cfg.get("stop_loss", True)
        self.alert_take_profit  = alerts_cfg.get("take_profit", True)
        self.alert_breakout     = alerts_cfg.get("breakout", True)
        self.alert_volume_surge = alerts_cfg.get("volume_surge", True)

        # ── 移动止盈规则 ──
        self._trailing_rules = [
            (20.0, "10pct"), (10.0, "5pct"), (5.0, "cost"),
        ]

        # ── 持仓快照 ──
        self._snapshots: Dict[str, PositionSnapshot] = {}
        self._init_snapshots(positions)
        self._snap_lock = threading.Lock()

        # ── 线程控制 ──
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()

        # ── 状态 ──
        self._status = MonitorStatus.IDLE
        self._status_lock = threading.Lock()
        self._last_check_time: Optional[str] = None
        self._check_count: int = 0

        # ── 告警回调 ──
        self.on_stop_loss:    Optional[Callable[[AlertEvent], None]] = None
        self.on_take_profit:  Optional[Callable[[AlertEvent], None]] = None
        self.on_breakout:     Optional[Callable[[AlertEvent], None]] = None
        self.on_volume_surge: Optional[Callable[[AlertEvent], None]] = None
        self.on_trailing:     Optional[Callable[[AlertEvent], None]] = None

        # ── 告警历史 ──
        self._alert_history: List[AlertEvent] = []
        self._alerted_keys: set = set()

        # ── 旧版兼容 ──
        self.positions = positions  # 原始持仓列表
        self.config = mon           # monitor 配置 dict
        self._running = False
        self._alerts: List[Alert] = []

    # ── 初始化快照 ──────────────────────────────────────

    def _init_snapshots(self, positions: List[Dict[str, Any]]):
        for item in positions:
            code = item.get("stock_code", item.get("code", item.get("stock", "")))
            if not code:
                continue
            snap = PositionSnapshot(
                stock_code=code,
                stock_name=item.get("stock_name", item.get("name", "")),
                entry_price=float(item.get("entry_price", 0) or 0),
                position_size=int(item.get("position_size", item.get("shares", 0)) or 0),
                stop_loss=float(item.get("stop_loss", 0) or 0),
                take_profit=float(item.get("take_profit", 0) or 0),
            )
            self._snapshots[code] = snap
        if self._snapshots:
            logger.info(f"[监控] 初始化 {len(self._snapshots)} 只持仓快照")

    # ── 公共控制方法 ────────────────────────────────────

    def start(self, background: bool = True):
        """启动监控"""
        with self._status_lock:
            if self._status == MonitorStatus.RUNNING:
                logger.warning("[监控] 已在运行")
                return
            self._status = MonitorStatus.RUNNING
            self._stop_event.clear()
            self._pause_event.set()

        if background:
            self._thread = threading.Thread(
                target=self._run_loop, name="MonitorThread", daemon=True,
            )
            self._thread.start()
            logger.info("[监控] ✅ 后台已启动")
        else:
            self._run_loop()

    def stop(self):
        """停止监控"""
        with self._status_lock:
            if self._status == MonitorStatus.STOPPED:
                return
            self._status = MonitorStatus.STOPPED

        self._stop_event.set()
        self._pause_event.set()
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("[监控] ⏹ 已停止")

    def pause(self):
        """暂停监控"""
        with self._status_lock:
            if self._status != MonitorStatus.RUNNING:
                logger.warning(f"[监控] 无法暂停, 当前{self._status.value}")
                return
            self._status = MonitorStatus.PAUSED
        self._pause_event.clear()
        logger.info("[监控] ⏸ 已暂停")

    def resume(self):
        """恢复监控"""
        with self._status_lock:
            if self._status != MonitorStatus.PAUSED:
                logger.warning(f"[监控] 无法恢复, 当前{self._status.value}")
                return
            self._status = MonitorStatus.RUNNING
        self._pause_event.set()
        logger.info("[监控] ▶ 已恢复")

    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        with self._status_lock:
            status_val = self._status.value
        with self._snap_lock:
            positions_info = []
            for code, snap in self._snapshots.items():
                positions_info.append({
                    "stock_code": snap.stock_code,
                    "stock_name": snap.stock_name,
                    "entry_price": snap.entry_price,
                    "current_price": snap.current_price,
                    "profit_pct": round(snap.profit_pct, 2),
                    "stop_loss": snap.stop_loss,
                    "trailing_stop": snap.trailing_stop,
                    "take_profit": snap.take_profit,
                    "alerted_stop_loss": snap.alerted_stop_loss,
                    "alerted_take_profit": snap.alerted_take_profit,
                })
        return {
            "status": status_val,
            "positions": len(self._snapshots),
            "interval_sec": self.interval,
            "check_count": self._check_count,
            "last_check": self._last_check_time,
            "positions_detail": positions_info,
            "alert_count": len(self._alert_history),
        }

    def update_positions(self, positions: List[Dict[str, Any]]):
        """更新持仓列表"""
        with self._snap_lock:
            new_codes = set()
            for item in positions:
                code = item.get("stock_code", item.get("code", item.get("stock", "")))
                if not code:
                    continue
                new_codes.add(code)
                if code in self._snapshots:
                    snap = self._snapshots[code]
                    snap.stop_loss = float(item.get("stop_loss", snap.stop_loss) or snap.stop_loss)
                    snap.take_profit = float(item.get("take_profit", snap.take_profit) or snap.take_profit)
                else:
                    self._snapshots[code] = PositionSnapshot(
                        stock_code=code,
                        stock_name=item.get("stock_name", item.get("name", "")),
                        entry_price=float(item.get("entry_price", 0) or 0),
                        position_size=int(item.get("position_size", item.get("shares", 0)) or 0),
                        stop_loss=float(item.get("stop_loss", 0) or 0),
                        take_profit=float(item.get("take_profit", 0) or 0),
                    )
            removed = [c for c in self._snapshots if c not in new_codes]
            for c in removed:
                del self._snapshots[c]
            if removed:
                logger.info(f"[监控] 移除 {len(removed)} 只: {removed}")

    # ── 旧版兼容属性 ────────────────────────────────────

    @property
    def alerts(self) -> List[Alert]:
        return self._alerts.copy()

    @property
    def running(self) -> bool:
        return self._running or self._status == MonitorStatus.RUNNING

    # ── 主循环 ──────────────────────────────────────────

    def _run_loop(self):
        """后台轮询主循环"""
        logger.info(
            f"[监控] 轮询开始 — 间隔{self.interval}s | "
            f"{self._trading_hours['morning_start']}-{self._trading_hours['morning_end']}, "
            f"{self._trading_hours['afternoon_start']}-{self._trading_hours['afternoon_end']}"
        )
        self._running = True

        while not self._stop_event.is_set():
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            try:
                if self._is_trading_time():
                    self._poll_prices()
            except Exception as e:
                logger.error(f"[监控] 轮询异常: {e}", exc_info=True)

            self._stop_event.wait(timeout=self.interval)

        self._running = False
        logger.info("[监控] 线程退出")

    # ── 交易时段判断 ────────────────────────────────────

    def _is_trading_time(self) -> bool:
        now = datetime.now()
        t = now.time()
        if now.weekday() >= 5:
            return False
        try:
            ms = dt_time.fromisoformat(self._trading_hours["morning_start"])
            me = dt_time.fromisoformat(self._trading_hours["morning_end"])
            a_s = dt_time.fromisoformat(self._trading_hours["afternoon_start"])
            ae = dt_time.fromisoformat(self._trading_hours["afternoon_end"])
        except (ValueError, TypeError):
            ms, me = dt_time(9, 30), dt_time(11, 30)
            a_s, ae = dt_time(13, 0), dt_time(15, 0)
        return (ms <= t <= me) or (a_s <= t <= ae)

    def is_trading_time(self) -> bool:
        return self._is_trading_time()

    # ── 价格轮询核心 ────────────────────────────────────

    def _poll_prices(self):
        with self._snap_lock:
            codes = list(self._snapshots.keys())
        if not codes:
            return

        quotes = self._get_realtime_quotes(codes)
        if not quotes:
            return

        self._check_count += 1
        self._last_check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._snap_lock:
            for code, snap in self._snapshots.items():
                quote = quotes.get(code)
                if not quote:
                    continue
                price = self._extract_price(quote)
                if price <= 0:
                    continue

                snap.current_price = price
                snap.profit_pct = (price - snap.entry_price) / snap.entry_price * 100 if snap.entry_price > 0 else 0

                # 移动止盈
                self._check_trailing_stop(snap)

                # 止损检测
                if self.alert_stop_loss and snap.is_stop_loss_hit and not snap.alerted_stop_loss:
                    eff_stop = max(snap.stop_loss, snap.trailing_stop)
                    self._fire_alert("stop_loss", snap, price,
                                     f"触发止损! 现价{price:.2f}≤止损{eff_stop:.2f} (浮亏{abs(snap.profit_pct):.2f}%)")
                    snap.alerted_stop_loss = True

                # 止盈检测
                if self.alert_take_profit and snap.is_take_profit_hit and not snap.alerted_take_profit:
                    self._fire_alert("take_profit", snap, price,
                                     f"触发止盈! 现价{price:.2f}≥止盈{snap.take_profit:.2f} (浮盈{snap.profit_pct:.2f}%)")
                    snap.alerted_take_profit = True

                # 破位检测
                if self.alert_breakout:
                    self._check_breakout(snap, price)

                # 放量检测
                if self.alert_volume_surge:
                    self._check_volume_surge(snap, price, quote)

        if self._check_count % 10 == 0:
            self._log_status()

    def _get_realtime_quotes(self, codes: List[str]) -> Dict[str, Any]:
        """获取实时报价 — 自动适配 DataSource API"""
        if self._ds is None:
            return {}
        try:
            if hasattr(self._ds, "get_quote"):
                return self._ds.get_quote(codes)
        except Exception as e:
            logger.error(f"[监控] get_quote 失败: {e}")

        # 备选: 逐个查询
        results = {}
        for code in codes:
            try:
                if hasattr(self._ds, "get_realtime_quote"):
                    results[code] = self._ds.get_realtime_quote(code)
            except Exception:
                pass
        return results

    @staticmethod
    def _extract_price(quote: Any) -> float:
        if isinstance(quote, dict):
            for key in ("price", "current", "last", "close", "trade"):
                val = quote.get(key)
                if val is not None:
                    try:
                        f = float(val)
                        if f > 0:
                            return f
                    except (ValueError, TypeError):
                        pass
        elif isinstance(quote, (int, float)):
            return float(quote)
        return 0.0

    # ── 移动止盈 ────────────────────────────────────────

    def _check_trailing_stop(self, snap: PositionSnapshot):
        if snap.entry_price <= 0 or snap.current_price <= 0:
            return
        profit_pct = (snap.current_price - snap.entry_price) / snap.entry_price * 100
        new_trailing = 0.0
        for threshold_pct, lock_type in self._trailing_rules:
            if profit_pct >= threshold_pct:
                if lock_type == "cost":
                    new_trailing = snap.entry_price
                elif lock_type == "5pct":
                    new_trailing = snap.entry_price * 1.05
                elif lock_type == "10pct":
                    new_trailing = snap.entry_price * 1.10
                break

        if new_trailing > snap.trailing_stop:
            old = snap.trailing_stop
            snap.trailing_stop = round(new_trailing, 2)
            logger.info(f"[移动止盈] {snap.stock_code}: 浮盈{profit_pct:.1f}% → 止损上移至{snap.trailing_stop:.2f}"
                        + (f" (原{old:.2f})" if old > 0 else ""))
            self._fire_alert("trailing", snap, snap.current_price,
                             f"移动止盈生效: 浮盈{profit_pct:.1f}% → 止损上移至{snap.trailing_stop:.2f}")

    # ── 破位检测 ────────────────────────────────────────

    def _check_breakout(self, snap: PositionSnapshot, price: float):
        if snap.entry_price > 0:
            decline_pct = (snap.entry_price - price) / snap.entry_price * 100
            if decline_pct >= 5.0:
                key = f"{snap.stock_code}:breakout_5pct"
                if key not in self._alerted_keys:
                    self._alerted_keys.add(key)
                    self._fire_alert("breakout", snap, price,
                                     f"破位告警: 现价{price:.2f}较入场{snap.entry_price:.2f}下跌{decline_pct:.1f}%")

    # ── 放量检测 ────────────────────────────────────────

    def _check_volume_surge(self, snap: PositionSnapshot, price: float, quote: dict):
        vol_ratio = float(quote.get("vol_ratio", quote.get("volume_ratio", 1.0)) or 1.0)
        turnover  = float(quote.get("turnover_pct", quote.get("turnover", 0)) or 0)

        surge = False
        reason_parts = []
        if vol_ratio >= 3.0:
            surge = True
            reason_parts.append(f"量比{vol_ratio:.1f}")
        if turnover >= 10.0:
            surge = True
            reason_parts.append(f"换手率{turnover:.1f}%")

        if surge:
            key = f"{snap.stock_code}:volume_surge"
            if key not in self._alerted_keys:
                self._alerted_keys.add(key)
                self._fire_alert("volume_surge", snap, price,
                                 f"放量异常: {' + '.join(reason_parts)} | 现价{price:.2f}")

    # ── 告警发送 ────────────────────────────────────────

    def _fire_alert(self, alert_type: str, snap: PositionSnapshot, price: float, message: str):
        event = AlertEvent(
            type=alert_type,
            stock_code=snap.stock_code,
            stock_name=snap.stock_name,
            message=message,
            price=price,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._alert_history.append(event)

        # 旧版兼容告警
        old_alert = Alert(
            stock=snap.stock_code,
            alert_type=alert_type,
            message=message,
            severity="critical" if alert_type == "stop_loss" else "warning",
        )
        self._alerts.append(old_alert)

        # 回调
        callbacks = {
            "stop_loss": self.on_stop_loss,
            "take_profit": self.on_take_profit,
            "breakout": self.on_breakout,
            "volume_surge": self.on_volume_surge,
            "trailing": self.on_trailing,
        }
        cb = callbacks.get(alert_type)
        if cb:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"[监控] 回调{alert_type}异常: {e}")

        if self.on_alert:
            try:
                self.on_alert(event)
            except Exception as e:
                logger.error(f"[监控] on_alert异常: {e}")

        logger.warning(f"[告警] {alert_type.upper()}: {message}")

    # ── 状态日志 ────────────────────────────────────────

    def _log_status(self):
        with self._snap_lock:
            lines = []
            for code, snap in self._snapshots.items():
                eff_stop = max(snap.stop_loss, snap.trailing_stop)
                flag = "🟢" if snap.profit_pct >= 5 else ("⚪" if snap.profit_pct >= 0 else ("🟡" if snap.profit_pct >= -3 else "🔴"))
                lines.append(
                    f"  {flag} {snap.stock_code} {snap.stock_name:6s} "
                    f"{snap.current_price:.2f} ({snap.profit_pct:+.1f}%) "
                    f"止{eff_stop:.2f} 盈{snap.take_profit:.2f}"
                )
        status_text = "\n".join(lines) if lines else "  (无持仓)"
        logger.info(f"[监控] 第{self._check_count}次轮询 {self._last_check_time}:\n{status_text}")

    # ── 旧版兼容: _check_position ───────────────────────

    def _check_position(self, position) -> List[Alert]:
        alerts = []
        try:
            code = position.stock if hasattr(position, "stock") else position.get("stock", "")
            if not self._ds or not code:
                return alerts

            quote = self._ds.get_quote([code])
            if not quote or code not in quote:
                return alerts

            current_price = quote[code].get("price", 0)
            if current_price <= 0:
                return alerts

            entry_price = getattr(position, "entry_price", position.get("entry_price", 0))
            stop_loss   = getattr(position, "stop_loss", position.get("stop_loss", 0))
            take_profit = getattr(position, "take_profit", position.get("take_profit", 0))

            if self.alert_stop_loss and stop_loss > 0 and current_price <= stop_loss:
                loss_pct = (current_price - entry_price) / entry_price * 100
                a = Alert(stock=code, alert_type="stop_loss",
                          message=f"触发止损: 现价{current_price:.2f} ≤ 止损{stop_loss:.2f} (亏损{loss_pct:+.2f}%)",
                          severity="critical")
                alerts.append(a)
                self._alerts.append(a)

            if self.alert_take_profit and take_profit > 0 and current_price >= take_profit:
                profit_pct = (current_price - entry_price) / entry_price * 100
                a = Alert(stock=code, alert_type="take_profit",
                          message=f"触发止盈: 现价{current_price:.2f} ≥ 止盈{take_profit:.2f} (盈利{profit_pct:+.2f}%)",
                          severity="warning")
                alerts.append(a)
                self._alerts.append(a)
        except Exception as e:
            logger.error(f"[Monitor] 检查异常: {e}")
        return alerts

    def __repr__(self) -> str:
        return f"Monitor(interval={self.interval}s, positions={len(self._snapshots)})"


# ═══════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════

def create_monitor(
    positions: List[Dict[str, Any]],
    ds: DataSource,
    config_path: Optional[str] = None,
) -> Monitor:
    """从 config.yaml 创建 Monitor"""
    import os
    import yaml

    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        config_path = os.path.normpath(config_path)

    cfg = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    return Monitor(positions=positions, data_source=ds, config=cfg)


# ═══════════════════════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("  实时监控模块 (Monitor) 自测")
    print("=" * 60)

    # ── 模拟 DataSource ──
    import random as _rnd
    _rnd.seed(42)
    _counter = [0]

    class MockDataSource:
        def __init__(self):
            self._prices = {"600519": 1680.0, "000858": 145.0}

        def get_quote(self, symbols):
            _counter[0] += 1
            result = {}
            for s in symbols:
                base = self._prices.get(s, 100.0)
                if _counter[0] < 8:
                    offset = -_counter[0] * 15
                elif _counter[0] < 20:
                    offset = -(8 * 15) + (_counter[0] - 8) * 40
                else:
                    offset = -(8 * 15) + (12 * 40) + (_counter[0] - 20) * 50
                price = round(base + offset, 2)
                result[s] = {
                    "name": "茅台" if "519" in s else "五粮液",
                    "price": price,
                    "vol_ratio": 1.0 + _rnd.random() * 0.5,
                    "turnover_pct": _rnd.random() * 5,
                }
            return result

    mock_ds = MockDataSource()

    # ── 模拟持仓 ──
    mock_positions = [
        {
            "stock_code": "600519", "stock_name": "贵州茅台",
            "entry_price": 1680.00, "position_size": 100,
            "stop_loss": 1620.00, "take_profit": 1800.00,
        },
        {
            "stock_code": "000858", "stock_name": "五粮液",
            "entry_price": 145.00, "position_size": 1000,
            "stop_loss": 138.00, "take_profit": 159.00,
        },
    ]

    # ── 创建监控器 ──
    mon = Monitor(mock_positions, mock_ds, config={
        "monitor": {"interval": 1, "alerts": {"stop_loss": True, "take_profit": True, "breakout": True, "volume_surge": True}},
    })

    print(f"\nMonitor created: {mon}")
    print(f"Status: {mon.get_status()['status']}")

    # ── 设置回调 ──
    def on_alert_cb(event):
        print(f"\n  🔔 [{event.type.upper()}] {event.stock_code}: {event.message}")

    mon.on_alert = on_alert_cb
    mon.on_stop_loss = lambda e: print(f"  ⛔ 止损触发: {e.stock_code} @ {e.price:.2f}")
    mon.on_take_profit = lambda e: print(f"  🎯 止盈触发: {e.stock_code} @ {e.price:.2f}")
    mon.on_trailing = lambda e: print(f"  📈 移动止盈: {e.message}")

    # ── 强制交易时间 ──
    mon._is_trading_time = lambda: True

    # ── 启动并测试 ──
    print("\n▶ 启动监控...")
    mon.start(background=True)

    import time as _time
    print("  运行中 (模拟价格下跌→止损, 回升→止盈)...")
    _time.sleep(6)

    # 暂停 & 恢复
    print("\n⏸ 暂停 1 秒...")
    mon.pause()
    _time.sleep(1)
    print("▶ 恢复...")
    mon.resume()
    _time.sleep(2)

    # 停止
    print("\n⏹ 停止监控...")
    mon.stop()

    # ── 状态报告 ──
    status = mon.get_status()
    print(f"\n📊 监控状态报告:")
    print(f"  状态: {status['status']}")
    print(f"  检查次数: {status['check_count']}")
    print(f"  告警总数: {status['alert_count']}")
    for p in status['positions_detail']:
        print(f"  {p['stock_code']}: 入{p['entry_price']:.2f} → 现{p['current_price']:.2f} ({p['profit_pct']:+.1f}%) "
              f"止{p['stop_loss']:.2f} 盈{p['take_profit']:.2f}")

    print(f"\n✅ 自测完成")
