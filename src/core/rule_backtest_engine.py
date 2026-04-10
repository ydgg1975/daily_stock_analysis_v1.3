# -*- coding: utf-8 -*-
"""Deterministic rule backtesting engine for AI-assisted strategies."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict, field
from datetime import date
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _round_pct(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 4)


@dataclass
class ParsedStrategy:
    version: str
    timeframe: str
    source_text: str
    normalized_text: str
    entry: Dict[str, Any]
    exit: Dict[str, Any]
    confidence: float
    needs_confirmation: bool
    ambiguities: List[Dict[str, Any]]
    summary: Dict[str, str]
    max_lookback: int
    strategy_kind: str = "rule_conditions"
    setup: Dict[str, Any] = field(default_factory=dict)
    strategy_spec: Dict[str, Any] = field(default_factory=dict)
    executable: bool = False
    normalization_state: str = "pending"
    assumptions: List[Dict[str, Any]] = field(default_factory=list)
    assumption_groups: List[Dict[str, Any]] = field(default_factory=list)
    unsupported_reason: Optional[str] = None
    unsupported_details: List[Dict[str, Any]] = field(default_factory=list)
    unsupported_extensions: List[Dict[str, Any]] = field(default_factory=list)
    detected_strategy_family: Optional[str] = None
    core_intent_summary: Optional[str] = None
    interpretation_confidence: float = 0.0
    supported_portion_summary: Optional[str] = None
    rewrite_suggestions: List[Dict[str, Any]] = field(default_factory=list)
    parse_warnings: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionAssumptions:
    """Explicit execution assumptions for deterministic rule backtests."""

    timeframe: str
    indicator_price_basis: str
    signal_evaluation_timing: str
    entry_fill_timing: str
    exit_fill_timing: str
    default_fill_price_basis: str
    position_sizing: str
    fee_model: str
    fee_bps_per_side: float
    slippage_model: str
    slippage_bps_per_side: float
    benchmark_method: str
    benchmark_price_basis: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuleBacktestTrade:
    code: str
    entry_signal_date: date
    exit_signal_date: date
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    entry_signal: str
    exit_signal: str
    entry_trigger: str
    exit_trigger: str
    return_pct: float
    holding_days: int
    holding_bars: int
    holding_calendar_days: int
    entry_rule_json: Dict[str, Any]
    exit_rule_json: Dict[str, Any]
    entry_indicators: Dict[str, Any]
    exit_indicators: Dict[str, Any]
    entry_fill_basis: str
    exit_fill_basis: str
    signal_price_basis: str
    price_basis: str
    fee_bps: float
    slippage_bps: float
    entry_fee_amount: float = 0.0
    exit_fee_amount: float = 0.0
    entry_slippage_amount: float = 0.0
    exit_slippage_amount: float = 0.0
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "entry_signal_date": self.entry_signal_date.isoformat(),
            "exit_signal_date": self.exit_signal_date.isoformat(),
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat(),
            "entry_price": round(self.entry_price, 6),
            "exit_price": round(self.exit_price, 6),
            "entry_signal": self.entry_signal,
            "exit_signal": self.exit_signal,
            "entry_trigger": self.entry_trigger,
            "exit_trigger": self.exit_trigger,
            "return_pct": round(self.return_pct, 4),
            "holding_days": self.holding_days,
            "holding_bars": self.holding_bars,
            "holding_calendar_days": self.holding_calendar_days,
            "entry_rule": self.entry_rule_json,
            "exit_rule": self.exit_rule_json,
            "entry_indicators": self.entry_indicators,
            "exit_indicators": self.exit_indicators,
            "entry_fill_basis": self.entry_fill_basis,
            "exit_fill_basis": self.exit_fill_basis,
            "signal_price_basis": self.signal_price_basis,
            "price_basis": self.price_basis,
            "fee_bps": round(self.fee_bps, 4),
            "slippage_bps": round(self.slippage_bps, 4),
            "entry_fee_amount": round(self.entry_fee_amount, 6),
            "exit_fee_amount": round(self.exit_fee_amount, 6),
            "entry_slippage_amount": round(self.entry_slippage_amount, 6),
            "exit_slippage_amount": round(self.exit_slippage_amount, 6),
            "notes": self.notes,
        }


@dataclass
class RuleBacktestPoint:
    date: date
    equity: float
    cumulative_return_pct: float
    drawdown_pct: float
    close: Optional[float] = None
    signal_summary: Optional[str] = None
    target_position: Optional[float] = None
    executed_action: Optional[str] = None
    fill_price: Optional[float] = None
    shares_held: Optional[float] = None
    cash: Optional[float] = None
    holdings_value: Optional[float] = None
    total_portfolio_value: Optional[float] = None
    position_state: Optional[str] = None
    exposure_pct: Optional[float] = None
    fee_amount: Optional[float] = None
    slippage_amount: Optional[float] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "equity": round(self.equity, 6),
            "cumulative_return_pct": round(self.cumulative_return_pct, 6),
            "drawdown_pct": round(self.drawdown_pct, 6),
            "close": round(self.close, 6) if self.close is not None else None,
            "signal_summary": self.signal_summary,
            "target_position": round(self.target_position, 6) if self.target_position is not None else None,
            "executed_action": self.executed_action,
            "fill_price": round(self.fill_price, 6) if self.fill_price is not None else None,
            "shares_held": round(self.shares_held, 6) if self.shares_held is not None else None,
            "cash": round(self.cash, 6) if self.cash is not None else None,
            "holdings_value": round(self.holdings_value, 6) if self.holdings_value is not None else None,
            "total_portfolio_value": round(self.total_portfolio_value, 6) if self.total_portfolio_value is not None else None,
            "position_state": self.position_state,
            "exposure_pct": round(self.exposure_pct, 6) if self.exposure_pct is not None else None,
            "fee_amount": round(self.fee_amount, 6) if self.fee_amount is not None else None,
            "slippage_amount": round(self.slippage_amount, 6) if self.slippage_amount is not None else None,
            "notes": self.notes,
        }


@dataclass
class RuleBacktestResult:
    parsed_strategy: ParsedStrategy
    execution_assumptions: ExecutionAssumptions
    trades: List[RuleBacktestTrade]
    equity_curve: List[RuleBacktestPoint]
    metrics: Dict[str, Any]
    benchmark_curve: List[Dict[str, Any]] = field(default_factory=list)
    benchmark_summary: Dict[str, Any] = field(default_factory=dict)
    buy_and_hold_curve: List[Dict[str, Any]] = field(default_factory=list)
    buy_and_hold_summary: Dict[str, Any] = field(default_factory=dict)
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None
    warnings: List[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parsed_strategy": self.parsed_strategy.to_dict(),
            "execution_assumptions": self.execution_assumptions.to_dict(),
            "trades": [trade.to_dict() for trade in self.trades],
            "equity_curve": [point.to_dict() for point in self.equity_curve],
            "metrics": self.metrics,
            "benchmark_curve": self.benchmark_curve,
            "benchmark_summary": self.benchmark_summary,
            "buy_and_hold_curve": self.buy_and_hold_curve,
            "buy_and_hold_summary": self.buy_and_hold_summary,
            "no_result_reason": self.no_result_reason,
            "no_result_message": self.no_result_message,
            "warnings": self.warnings or [],
        }


@dataclass
class PendingOrder:
    signal_date: date
    trigger: str
    rule_json: Dict[str, Any]
    indicators: Dict[str, Any]


class RuleBacktestParser:
    """Parse human-readable strategy text into a deterministic rule tree."""

    _TYPO_SUGGESTIONS = {
        "RIS": "RSI",
        "SMA": "MA",
    }

    _LOGICAL_OR_PATTERNS = (
        r"\bor\b",
        r"\|\|",
        r"\b或\b",
    )
    _LOGICAL_AND_PATTERNS = (
        r"\band\b",
        r"&&",
        r"\b且\b",
        r"\b并且\b",
    )

    def parse(self, strategy_text: str, llm_adapter: Any = None) -> ParsedStrategy:
        raw_text = (strategy_text or "").strip()
        if not raw_text:
            raise ValueError("strategy_text is required")

        periodic_strategy = self._parse_periodic_accumulation(raw_text)
        if periodic_strategy is not None:
            return periodic_strategy
        macd_strategy = self._parse_macd_crossover(raw_text)
        if macd_strategy is not None:
            return macd_strategy
        moving_average_strategy = self._parse_moving_average_crossover(raw_text)
        if moving_average_strategy is not None:
            return moving_average_strategy
        rsi_strategy = self._parse_rsi_threshold(raw_text)
        if rsi_strategy is not None:
            return rsi_strategy

        normalized = self._normalize_text(raw_text)
        entry_text, exit_text, issues, inferred_sections = self._split_sections(normalized)
        entry_node, entry_meta = self._parse_expression(entry_text)
        exit_node, exit_meta = self._parse_expression(exit_text)

        ambiguities: List[Dict[str, Any]] = []
        ambiguities.extend(issues)
        ambiguities.extend(entry_meta["issues"])
        ambiguities.extend(exit_meta["issues"])

        confidence = 1.0
        confidence -= 0.12 * inferred_sections
        confidence -= 0.08 * len(issues)
        confidence -= 0.05 * (entry_meta["issue_count"] + exit_meta["issue_count"])
        confidence = max(0.0, min(1.0, confidence))

        if (confidence < 0.75 or not entry_node or not exit_node) and llm_adapter is not None:
            llm_result = self._llm_parse(raw_text, llm_adapter)
            if llm_result is not None:
                parsed_dict, llm_issues = llm_result
                entry_node = parsed_dict.get("entry") or entry_node
                exit_node = parsed_dict.get("exit") or exit_node
                if parsed_dict.get("summary"):
                    summary = parsed_dict["summary"]
                else:
                    summary = self._build_summary(entry_node, exit_node)
                confidence = max(confidence, float(parsed_dict.get("confidence") or 0.75))
                if parsed_dict.get("ambiguities"):
                    ambiguities.extend(parsed_dict["ambiguities"])
                ambiguities.extend(llm_issues)
                max_lookback = self._collect_max_lookback(entry_node, exit_node)
                needs_confirmation = bool(parsed_dict.get("needs_confirmation", True)) or confidence < 0.85 or bool(ambiguities)
                return ParsedStrategy(
                    version="v1",
                    timeframe="daily",
                    source_text=raw_text,
                    normalized_text=normalized,
                    entry=entry_node or parsed_dict.get("entry") or self._empty_group("and"),
                    exit=exit_node or parsed_dict.get("exit") or self._empty_group("or"),
                    confidence=round(confidence, 3),
                    needs_confirmation=needs_confirmation,
                    ambiguities=self._dedupe_issues(ambiguities),
                    summary=summary,
                    max_lookback=max_lookback,
                    strategy_spec={},
                    executable=False,
                    normalization_state="pending",
                )

        max_lookback = self._collect_max_lookback(entry_node, exit_node)
        summary = self._build_summary(entry_node, exit_node)
        needs_confirmation = confidence < 0.85 or bool(ambiguities) or entry_node is None or exit_node is None
        return ParsedStrategy(
            version="v1",
            timeframe="daily",
            source_text=raw_text,
            normalized_text=normalized,
            entry=entry_node or self._empty_group("and"),
            exit=exit_node or self._empty_group("or"),
            confidence=round(confidence, 3),
            needs_confirmation=needs_confirmation,
            ambiguities=self._dedupe_issues(ambiguities),
            summary=summary,
            max_lookback=max_lookback,
            strategy_spec={},
            executable=False,
            normalization_state="pending",
        )

    def _parse_periodic_accumulation(self, raw_text: str) -> Optional[ParsedStrategy]:
        text = (raw_text or "").strip()
        if not text:
            return None

        normalized_text = re.sub(r"\s+", " ", text)
        start_end_match = re.search(r"从\s*(\d{4}-\d{2}-\d{2})\s*到\s*(\d{4}-\d{2}-\d{2})", normalized_text)
        daily_frequency = bool(re.search(r"(每天|每日|每个交易日)", normalized_text))
        if not start_end_match or not daily_frequency:
            return None

        quantity_match = re.search(
            r"(?:每天|每日|每个交易日)\s*买(?:入)?\s*([0-9]+(?:\.[0-9]+)?)\s*股\s*([A-Za-z][A-Za-z0-9.\-]{0,9})?",
            normalized_text,
            flags=re.IGNORECASE,
        )
        amount_match = re.search(
            r"(?:每天|每日|每个交易日)\s*买(?:入)?\s*([0-9]+(?:\.[0-9]+)?)\s*(元|块|块钱)\s*([A-Za-z][A-Za-z0-9.\-]{0,9})?",
            normalized_text,
            flags=re.IGNORECASE,
        )
        if quantity_match is None and amount_match is None:
            return None

        capital_match = re.search(r"资金\s*([0-9]+(?:\.[0-9]+)?)", normalized_text)
        symbol = None
        order_mode = "fixed_shares"
        quantity_per_trade: Optional[float] = None
        amount_per_trade: Optional[float] = None
        if quantity_match is not None:
            quantity_per_trade = float(quantity_match.group(1))
            symbol = quantity_match.group(2)
        else:
            amount_per_trade = float(amount_match.group(1))
            symbol = amount_match.group(3)

        ambiguities: List[Dict[str, Any]] = []
        if capital_match is None:
            ambiguities.append({
                "code": "default_initial_capital",
                "message": "未显式写出初始资金，已默认使用 100000。",
                "suggestion": "如需其他资金规模，请写成“资金 50000”。",
            })
        if not symbol:
            ambiguities.append({
                "code": "missing_symbol",
                "message": "未在自然语言中识别到股票代码。",
                "suggestion": "请在文本中写出类似 ORCL / AAPL 的单一股票代码。",
            })

        cash_stop = "stop_when_insufficient_cash" if re.search(r"(资金耗尽|现金不足|资金不足)", normalized_text) else "skip_when_insufficient_cash"
        confidence = 0.98 if symbol else 0.82
        setup = {
            "symbol": str(symbol or "").upper() or None,
            "start_date": start_end_match.group(1),
            "end_date": start_end_match.group(2),
            "initial_capital": float(capital_match.group(1)) if capital_match is not None else 100000.0,
            "execution_frequency": "daily",
            "action": "buy",
            "order_mode": order_mode,
            "quantity_per_trade": quantity_per_trade,
            "amount_per_trade": amount_per_trade,
            "cash_policy": cash_stop,
            "execution_price_basis": "open",
            "fee_bps": 0.0,
            "slippage_bps": 0.0,
            "exit_policy": "close_at_end",
        }
        size_text = (
            f"每个交易日买入 {int(quantity_per_trade) if quantity_per_trade is not None and quantity_per_trade.is_integer() else quantity_per_trade:g} 股"
            if quantity_per_trade is not None
            else f"每个交易日买入 {amount_per_trade:g} 元"
        )
        stop_text = "现金不足即停止买入" if cash_stop == "stop_when_insufficient_cash" else "现金不足时跳过当日"
        summary = {
            "entry": f"{size_text} {setup['symbol'] or '--'}",
            "exit": "区间结束统一按收盘价平仓",
            "strategy": "中文定投策略草稿",
        }
        normalized = (
            f"资金 {setup['initial_capital']:.0f}，{setup['start_date']} 至 {setup['end_date']}，"
            f"{size_text} {setup['symbol'] or '--'}，{stop_text}。"
        )
        return ParsedStrategy(
            version="v1",
            timeframe="daily",
            source_text=raw_text,
            normalized_text=normalized,
            entry=self._empty_group("and"),
            exit=self._empty_group("or"),
            confidence=confidence,
            needs_confirmation=True,
            ambiguities=ambiguities,
            summary=summary,
            max_lookback=1,
            strategy_kind="periodic_accumulation",
            setup=setup,
            strategy_spec={},
            executable=False,
            normalization_state="pending",
        )

    def _parse_macd_crossover(self, raw_text: str) -> Optional[ParsedStrategy]:
        text = (raw_text or "").strip()
        if not text:
            return None
        normalized_text = re.sub(r"\s+", " ", text)
        if "MACD" not in normalized_text.upper():
            return None
        upper = normalized_text.upper()
        has_bullish = bool(re.search(r"(金叉|GOLDEN\s+CROSS|CROSS(?:ES)?\s+ABOVE)", upper, re.IGNORECASE))
        has_bearish = bool(re.search(r"(死叉|DEAD\s+CROSS|CROSS(?:ES)?\s+BELOW)", upper, re.IGNORECASE))
        if not (has_bullish and has_bearish):
            return None

        params_match = re.search(
            r"MACD\s*(?:\(|（)?\s*(\d{1,3})\s*[,/]\s*(\d{1,3})\s*[,/]\s*(\d{1,3})\s*(?:\)|）)?",
            upper,
            re.IGNORECASE,
        )
        ambiguities: List[Dict[str, Any]] = []
        if params_match is not None:
            fast_period = int(params_match.group(1))
            slow_period = int(params_match.group(2))
            signal_period = int(params_match.group(3))
        else:
            fast_period, slow_period, signal_period = 12, 26, 9
            ambiguities.append({
                "code": "default_macd_periods",
                "message": "未显式写出 MACD 参数，当前默认使用 (12, 26, 9)。",
                "suggestion": "如需其他 MACD 参数，可写成 MACD(8,21,5)。",
            })

        summary = {
            "entry": f"买入条件：MACD({fast_period},{slow_period},{signal_period}) 金叉",
            "exit": f"卖出条件：MACD({fast_period},{slow_period},{signal_period}) 死叉",
            "strategy": "MACD 交叉策略",
        }
        normalized = (
            f"MACD({fast_period},{slow_period},{signal_period}) 金叉买入，"
            f"MACD({fast_period},{slow_period},{signal_period}) 死叉卖出。"
        )
        setup = {
            "indicator_family": "macd",
            "fast_period": fast_period,
            "slow_period": slow_period,
            "signal_period": signal_period,
        }
        return ParsedStrategy(
            version="v1",
            timeframe="daily",
            source_text=raw_text,
            normalized_text=normalized,
            entry=self._empty_group("and"),
            exit=self._empty_group("or"),
            confidence=0.96,
            needs_confirmation=bool(ambiguities),
            ambiguities=ambiguities,
            summary=summary,
            max_lookback=max(fast_period, slow_period) + signal_period,
            strategy_kind="macd_crossover",
            setup=setup,
            strategy_spec={},
            executable=False,
            normalization_state="pending",
        )

    def _parse_moving_average_crossover(self, raw_text: str) -> Optional[ParsedStrategy]:
        text = (raw_text or "").strip()
        if not text:
            return None
        normalized_text = re.sub(r"\s+", " ", text)
        upper = normalized_text.upper()
        if "MACD" in upper:
            return None

        explicit_pair_match = re.search(
            r"(?:(EMA|SMA|MA)\s*)?(\d{1,3})\s*(?:日|天|DAY)?\s*(?:均线|EMA|SMA|MA)?\s*(?:上穿|金叉|CROSS(?:ES)?\s+ABOVE)\s*(?:(EMA|SMA|MA)\s*)?(\d{1,3})\s*(?:日|天|DAY)?\s*(?:均线|EMA|SMA|MA)?",
            upper,
            re.IGNORECASE,
        )
        shorthand_match = re.search(
            r"(?:MA|EMA|SMA)\s*(\d{1,3})\s*(?:上穿|金叉|CROSS(?:ES)?\s+ABOVE)\s*(?:MA|EMA|SMA)\s*(\d{1,3})",
            upper,
            re.IGNORECASE,
        )
        if explicit_pair_match is None and shorthand_match is None:
            return None

        if explicit_pair_match is not None:
            fast_type = str(explicit_pair_match.group(1) or "").strip().upper()
            fast_period = int(explicit_pair_match.group(2))
            slow_type = str(explicit_pair_match.group(3) or "").strip().upper()
            slow_period = int(explicit_pair_match.group(4))
        else:
            fast_type = "MA"
            slow_type = "MA"
            fast_period = int(shorthand_match.group(1))
            slow_period = int(shorthand_match.group(2))
        if fast_period == slow_period:
            return None

        ambiguities: List[Dict[str, Any]] = []
        if not fast_type:
            fast_type = "MA"
            ambiguities.append({
                "code": "default_fast_ma_type",
                "message": "未显式写出快线类型，当前默认使用 SMA。",
                "suggestion": "如需指数均线，可写成 EMA5。",
            })
        if not slow_type:
            slow_type = "MA"
            ambiguities.append({
                "code": "default_slow_ma_type",
                "message": "未显式写出慢线类型，当前默认使用 SMA。",
                "suggestion": "如需指数均线，可写成 EMA20。",
            })

        has_exit = bool(re.search(r"(下穿|死叉|CROSS(?:ES)?\s+BELOW)", upper, re.IGNORECASE))
        if not has_exit:
            ambiguities.append({
                "code": "default_reverse_exit",
                "message": "未显式写出离场条件，当前默认使用反向下穿离场。",
                "suggestion": "如需其他离场方式，请显式写出。",
            })

        summary = {
            "entry": f"买入条件：{fast_type}{fast_period} 上穿 {slow_type}{slow_period}",
            "exit": f"卖出条件：{fast_type}{fast_period} 下穿 {slow_type}{slow_period}",
            "strategy": "均线交叉策略",
        }
        normalized = (
            f"{fast_type}{fast_period} 上穿 {slow_type}{slow_period} 买入，"
            f"{fast_type}{fast_period} 下穿 {slow_type}{slow_period} 卖出。"
        )
        setup = {
            "indicator_family": "moving_average",
            "fast_period": fast_period,
            "slow_period": slow_period,
            "fast_type": "ema" if fast_type == "EMA" else "simple",
            "slow_type": "ema" if slow_type == "EMA" else "simple",
        }
        return ParsedStrategy(
            version="v1",
            timeframe="daily",
            source_text=raw_text,
            normalized_text=normalized,
            entry=self._empty_group("and"),
            exit=self._empty_group("or"),
            confidence=0.95,
            needs_confirmation=bool(ambiguities),
            ambiguities=ambiguities,
            summary=summary,
            max_lookback=max(fast_period, slow_period),
            strategy_kind="moving_average_crossover",
            setup=setup,
            strategy_spec={},
            executable=False,
            normalization_state="pending",
        )

    def _parse_rsi_threshold(self, raw_text: str) -> Optional[ParsedStrategy]:
        text = (raw_text or "").strip()
        if not text:
            return None
        normalized = self._normalize_text(text)
        upper = normalized.upper()
        if "RSI" not in upper:
            return None
        if re.search(r"\b(?:MA|EMA|SMA)\d+\b", upper):
            return None

        buy_pattern = re.search(
            r"(?:BUY|买入).{0,24}?RSI\s*(\d{1,3})?\s*(?:<|<=)\s*([0-9]+(?:\.[0-9]+)?)|RSI\s*(\d{1,3})?\s*(?:<|<=)\s*([0-9]+(?:\.[0-9]+)?).{0,24}?(?:BUY|买入)",
            upper,
            re.IGNORECASE,
        )
        sell_pattern = re.search(
            r"(?:SELL|卖出|平仓).{0,24}?RSI\s*(\d{1,3})?\s*(?:>|>=)\s*([0-9]+(?:\.[0-9]+)?)|RSI\s*(\d{1,3})?\s*(?:>|>=)\s*([0-9]+(?:\.[0-9]+)?).{0,24}?(?:SELL|卖出|平仓)",
            upper,
            re.IGNORECASE,
        )
        if buy_pattern is None:
            buy_pattern = re.search(
                r"(?:<|<=)\s*([0-9]+(?:\.[0-9]+)?).{0,12}?(?:BUY|买入)",
                upper,
                re.IGNORECASE,
            )
        if sell_pattern is None:
            sell_pattern = re.search(
                r"(?:>|>=)\s*([0-9]+(?:\.[0-9]+)?).{0,12}?(?:SELL|卖出|平仓)",
                upper,
                re.IGNORECASE,
            )
        if buy_pattern is None or sell_pattern is None:
            return None

        buy_groups = buy_pattern.groups()
        sell_groups = sell_pattern.groups()
        entry_period, lower_threshold = self._extract_rsi_match_parts(buy_groups, default_period=14)
        exit_period, upper_threshold = self._extract_rsi_match_parts(sell_groups, default_period=entry_period)
        period = entry_period if entry_period == exit_period else max(entry_period, exit_period)

        ambiguities: List[Dict[str, Any]] = []
        if not re.search(r"RSI\s*\d{1,3}", upper, re.IGNORECASE):
            ambiguities.append({
                "code": "default_rsi_period",
                "message": "未显式写出 RSI 周期，当前默认使用 14。",
                "suggestion": "如需其他周期，可写成 RSI6 或 RSI21。",
            })
        if entry_period != exit_period:
            ambiguities.append({
                "code": "mixed_rsi_period",
                "message": f"买卖条件出现不同 RSI 周期，当前统一采用 RSI{period}。",
                "suggestion": "建议显式使用同一个 RSI 周期。",
            })

        summary = {
            "entry": f"买入条件：RSI{period} < {lower_threshold:g}",
            "exit": f"卖出条件：RSI{period} > {upper_threshold:g}",
            "strategy": "RSI 阈值策略",
        }
        normalized_text = f"RSI{period} 低于 {lower_threshold:g} 买入，RSI{period} 高于 {upper_threshold:g} 卖出。"
        setup = {
            "indicator_family": "rsi",
            "period": period,
            "lower_threshold": lower_threshold,
            "upper_threshold": upper_threshold,
        }
        return ParsedStrategy(
            version="v1",
            timeframe="daily",
            source_text=raw_text,
            normalized_text=normalized_text,
            entry=self._empty_group("and"),
            exit=self._empty_group("or"),
            confidence=0.95,
            needs_confirmation=bool(ambiguities),
            ambiguities=ambiguities,
            summary=summary,
            max_lookback=period + 1,
            strategy_kind="rsi_threshold",
            setup=setup,
            strategy_spec={},
            executable=False,
            normalization_state="pending",
        )

    @staticmethod
    def _extract_rsi_match_parts(groups: Tuple[Any, ...], *, default_period: int) -> Tuple[int, float]:
        if len(groups) == 1:
            return int(default_period), float(groups[0])
        period_candidates = []
        threshold_candidates = []
        if len(groups) > 0:
            period_candidates.append(groups[0])
        if len(groups) > 1:
            threshold_candidates.append(groups[1])
        if len(groups) > 2:
            period_candidates.append(groups[2])
        if len(groups) > 3:
            threshold_candidates.append(groups[3])
        period_value = next((value for value in period_candidates if value not in (None, "")), None)
        threshold_value = next((value for value in threshold_candidates if value not in (None, "")), None)
        return int(period_value or default_period), float(threshold_value if threshold_value is not None else 0.0)

    def _llm_parse(self, raw_text: str, llm_adapter: Any) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        prompt = (
            "You convert trading strategy text into a strict JSON rule schema for a deterministic daily long-only backtest.\n"
            "Only use these indicator kinds: ma, ema, rsi, close, return_pct.\n"
            "Supported comparisons: >, <, >=, <=.\n"
            "Supported logical ops: and, or.\n"
            "Return JSON only with keys: version, timeframe, entry, exit, confidence, needs_confirmation, ambiguities, summary.\n"
            "Each rule node must be either:\n"
            "1) {\"type\":\"group\",\"op\":\"and|or\",\"rules\":[...]} or\n"
            "2) {\"type\":\"comparison\",\"left\":{...},\"compare\":\">|<|>=|<=\",\"right\":{...},\"text\":\"...\"}\n"
            "Operand schema:\n"
            " - {\"kind\":\"indicator\",\"indicator\":\"ma|ema|rsi|close|return_pct\",\"period\":number?}\n"
            " - {\"kind\":\"value\",\"value\":number}\n"
            "If a typo is obvious, keep the intended indicator in the rule and add an ambiguity item with suggestion.\n"
            "Do not invent indicators or thresholds not present in the text.\n"
            f"Strategy text:\n{raw_text}"
        )
        try:
            response = llm_adapter.call_text(
                [
                    {"role": "system", "content": "You are a JSON-only strategy parser."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=900,
            )
            content = (response.content or "").strip()
            if not content:
                return None
            import json
            from json_repair import repair_json

            parsed = json.loads(repair_json(content))
            if not isinstance(parsed, dict):
                return None
            issues = parsed.get("ambiguities") or []
            if not isinstance(issues, list):
                issues = []
            entry = parsed.get("entry")
            exit_rule = parsed.get("exit")
            if not entry or not exit_rule:
                return None
            return parsed, [item for item in issues if isinstance(item, dict)]
        except Exception:
            return None

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = (text or "").strip()
        replacements = {
            "；": ";",
            "：": ":",
            "，": ",",
            "。": ".",
            "（": "(",
            "）": ")",
            "＞": ">",
            "＜": "<",
            "＝": "=",
            "＆": "&",
            "｜": "|",
            "买入条件": "entry",
            "建仓条件": "entry",
            "入场条件": "entry",
            "卖出条件": "exit",
            "平仓条件": "exit",
            "出场条件": "exit",
            "entry：": "entry:",
            "exit：": "exit:",
            "greater than or equal to": ">=",
            "less than or equal to": "<=",
            "no less than": ">=",
            "no more than": "<=",
            "at least": ">=",
            "at most": "<=",
            "greater than": ">",
            "less than": "<",
            "above": ">",
            "below": "<",
            "大于等于": ">=",
            "小于等于": "<=",
            "不低于": ">=",
            "不高于": "<=",
            "大于": ">",
            "小于": "<",
        }
        for src, dst in replacements.items():
            normalized = normalized.replace(src, dst)
            normalized = normalized.replace(src.upper(), dst)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _split_sections(self, text: str) -> Tuple[str, str, List[Dict[str, Any]], int]:
        issues: List[Dict[str, Any]] = []
        lowered = text.lower()
        entry_text = ""
        exit_text = ""

        entry_match = re.search(r"\bentry\b\s*:?\s*", lowered)
        exit_match = re.search(r"\bexit\b\s*:?\s*", lowered)
        if entry_match and exit_match and entry_match.start() < exit_match.start():
            entry_text = text[entry_match.end():exit_match.start()].strip(" .;")
            exit_text = text[exit_match.end():].strip(" .;")
        else:
            buy_match = re.search(r"\b(buy|entry|buy when|买入|建仓)\b", lowered)
            sell_match = re.search(r"\b(sell|exit|sell when|卖出|平仓)\b", lowered)
            if buy_match and sell_match and buy_match.start() < sell_match.start():
                entry_text = text[buy_match.end():sell_match.start()].strip(" .;")
                exit_text = text[sell_match.end():].strip(" .;")
            else:
                parts = [p.strip(" .;") for p in re.split(r"[;\n]+", text) if p.strip(" .;")]
                if len(parts) >= 2:
                    entry_text, exit_text = parts[0], parts[1]
                elif parts:
                    entry_text = parts[0]
                    exit_text = ""
                    issues.append({
                        "code": "missing_exit",
                        "message": "未找到明显的退出规则。",
                        "suggestion": "请补充 Exit: ...",
                    })
                else:
                    entry_text = text
                    exit_text = ""

        if not entry_text:
            entry_text = text

        return entry_text.strip(), exit_text.strip(), issues, 0

    def _parse_expression(self, text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        cleaned = (text or "").strip()
        if not cleaned:
            return self._empty_group("and"), {"issues": [{"code": "empty_rule", "message": "规则为空。", "suggestion": "请填写有效规则。"}], "issue_count": 1}

        or_parts = self._split_by_logical(cleaned, self._LOGICAL_OR_PATTERNS)
        if len(or_parts) > 1:
            child_nodes = []
            issues: List[Dict[str, Any]] = []
            for part in or_parts:
                node, meta = self._parse_and_expression(part)
                child_nodes.append(node)
                issues.extend(meta["issues"])
            return {"type": "group", "op": "or", "rules": child_nodes}, {"issues": issues, "issue_count": len(issues)}
        return self._parse_and_expression(cleaned)

    def _parse_and_expression(self, text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        and_parts = self._split_by_logical(text, self._LOGICAL_AND_PATTERNS)
        if len(and_parts) > 1:
            child_nodes = []
            issues: List[Dict[str, Any]] = []
            for part in and_parts:
                node, meta = self._parse_atom_or_group(part)
                child_nodes.append(node)
                issues.extend(meta["issues"])
            return {"type": "group", "op": "and", "rules": child_nodes}, {"issues": issues, "issue_count": len(issues)}
        return self._parse_atom_or_group(text)

    def _parse_atom_or_group(self, text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        cleaned = text.strip().strip("() ")
        cleaned = re.sub(r"^(?:when|if|then|buy|sell|entry|exit|买入|卖出|建仓|平仓)\s*", "", cleaned, flags=re.IGNORECASE)
        if not cleaned:
            return self._empty_group("and"), {"issues": [{"code": "empty_rule", "message": "空规则块。"}], "issue_count": 1}

        condition, issues = self._parse_condition(cleaned)
        if condition is not None:
            return condition, {"issues": issues, "issue_count": len(issues)}

        # Nested OR/AND fallback if the atom still contains logical separators.
        if self._split_by_logical(cleaned, self._LOGICAL_OR_PATTERNS) != [cleaned]:
            return self._parse_expression(cleaned)

        return self._empty_group("and"), {
            "issues": [{
                "code": "unparsed_atom",
                "message": f"无法解析条件: {cleaned}",
                "suggestion": "请使用类似 MA5 > MA20 或 RSI6 < 40 的格式。",
            }],
            "issue_count": 1,
        }

    def _parse_condition(self, text: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        issues: List[Dict[str, Any]] = []
        m = re.match(r"^(?P<left>.+?)\s*(?P<op>>=|<=|>|<)\s*(?P<right>.+?)$", text)
        if not m:
            return None, issues

        left_raw = m.group("left").strip()
        right_raw = m.group("right").strip()
        compare = m.group("op")

        left_operand, left_issues = self._parse_operand(left_raw)
        right_operand, right_issues = self._parse_operand(right_raw)
        issues.extend(left_issues)
        issues.extend(right_issues)
        if left_operand is None or right_operand is None:
            return None, issues

        return {
            "type": "comparison",
            "left": left_operand,
            "compare": compare,
            "right": right_operand,
            "text": text.strip(),
        }, issues

    def _parse_operand(self, token: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        issues: List[Dict[str, Any]] = []
        cleaned = token.strip().replace(" ", "").replace("_", "")
        numeric = _safe_float(cleaned)
        if numeric is not None:
            return {"kind": "value", "value": numeric}, issues

        indicator_match = re.match(r"^(MA|SMA|EMA|RSI|RETURN|RET|CLOSE|PRICE)(\d+)?$", cleaned, re.IGNORECASE)
        if indicator_match:
            name = indicator_match.group(1).upper()
            period_raw = indicator_match.group(2)
            period = int(period_raw) if period_raw else None
            indicator = self._normalize_indicator_name(name)
            if indicator == "close":
                return {"kind": "indicator", "indicator": "close"}, issues
            if period is None and indicator in {"ma", "ema", "rsi", "return_pct"}:
                issues.append({
                    "code": "missing_period",
                    "message": f"{token} 缺少周期。",
                    "suggestion": f"请明确写成 {name}5 / {name}20 这类带周期的规则。",
                })
                return None, issues
            if indicator in {"return_pct"} and period is not None and period <= 0:
                issues.append({
                    "code": "invalid_period",
                    "message": f"{token} 的周期必须大于 0。",
                    "suggestion": "请使用正整数周期。",
                })
                return None, issues
            return {"kind": "indicator", "indicator": indicator, "period": period}, issues

        typo_match = re.match(r"^(RIS)(\d+)$", cleaned, re.IGNORECASE)
        if typo_match:
            period = int(typo_match.group(2))
            issues.append({
                "code": "indicator_typo",
                "message": f"{token} 可能是 RSI{period}。",
                "suggestion": f"建议改为 RSI{period}。",
            })
            return {"kind": "indicator", "indicator": "rsi", "period": period}, issues

        if cleaned.lower() in {"price", "close", "收盘价", "收盘"}:
            return {"kind": "indicator", "indicator": "close"}, issues

        return None, [{
            "code": "unknown_operand",
            "message": f"无法识别的字段: {token}",
            "suggestion": "请使用 MA5、EMA20、RSI6、CLOSE 或数值。",
        }]

    @staticmethod
    def _normalize_indicator_name(name: str) -> str:
        upper = name.upper()
        if upper in {"MA", "SMA"}:
            return "ma"
        if upper == "EMA":
            return "ema"
        if upper == "RSI":
            return "rsi"
        if upper in {"RETURN", "RET"}:
            return "return_pct"
        return "close"

    def _build_summary(self, entry: Dict[str, Any], exit_rule: Dict[str, Any]) -> Dict[str, str]:
        return {
            "entry": f"买入条件：{self._format_node(entry, wrap=False)}",
            "exit": f"卖出条件：{self._format_node(exit_rule, wrap=False)}",
        }

    def _format_node(self, node: Dict[str, Any], wrap: bool = True) -> str:
        if not node:
            return "--"
        if node.get("type") == "group":
            joiner = " 且 " if node.get("op") == "and" else " 或 "
            parts = [self._format_node(child, wrap=True) for child in node.get("rules", [])]
            if not parts:
                return "--"
            joined = joiner.join(parts) if len(parts) > 1 else parts[0]
            return f"({joined})" if wrap and len(parts) > 1 else joined
        if node.get("type") == "comparison":
            return f"{self._format_operand(node.get('left'))} {node.get('compare')} {self._format_operand(node.get('right'))}"
        return "--"

    @staticmethod
    def _format_operand(operand: Optional[Dict[str, Any]]) -> str:
        if not operand:
            return "--"
        if operand.get("kind") == "value":
            value = operand.get("value")
            if value is None:
                return "--"
            return f"{float(value):g}"
        indicator = operand.get("indicator")
        period = operand.get("period")
        if indicator == "close":
            return "Close"
        if indicator == "return_pct":
            return f"Return{period}" if period else "Return"
        if indicator in {"ma", "ema", "rsi"} and period is not None:
            return f"{indicator.upper()}{period}"
        return indicator.upper() if isinstance(indicator, str) else "--"

    def _collect_max_lookback(self, *nodes: Optional[Dict[str, Any]]) -> int:
        return max([self._node_lookback(node) for node in nodes if node], default=1)

    def _node_lookback(self, node: Dict[str, Any]) -> int:
        if not node:
            return 1
        if node.get("type") == "group":
            return max([self._node_lookback(child) for child in node.get("rules", [])], default=1)
        if node.get("type") == "comparison":
            return max(self._operand_lookback(node.get("left")), self._operand_lookback(node.get("right")))
        return 1

    @staticmethod
    def _operand_lookback(operand: Optional[Dict[str, Any]]) -> int:
        if not operand or operand.get("kind") != "indicator":
            return 1
        indicator = operand.get("indicator")
        period = int(operand.get("period") or 1)
        if indicator in {"rsi", "return_pct"}:
            return period + 1
        if indicator in {"ma", "ema"}:
            return max(1, period)
        return 1

    @staticmethod
    def _empty_group(op: str) -> Dict[str, Any]:
        return {"type": "group", "op": op, "rules": []}

    @staticmethod
    def _split_by_logical(text: str, patterns: Sequence[str]) -> List[str]:
        pattern = "|".join(patterns)
        parts = [part.strip() for part in re.split(pattern, text, flags=re.IGNORECASE) if part.strip()]
        return parts or [text.strip()]

    @staticmethod
    def _dedupe_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for item in issues:
            key = (
                item.get("code"),
                item.get("message"),
                item.get("suggestion"),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped


class RuleBacktestEngine:
    """Deterministic long-only daily rule backtest engine."""

    def run(
        self,
        *,
        code: str,
        parsed_strategy: ParsedStrategy,
        bars: Sequence[Any],
        initial_capital: float = 100000.0,
        fee_bps: float = 0.0,
        slippage_bps: float = 0.0,
        lookback_bars: int = 252,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> RuleBacktestResult:
        assumptions = self._build_execution_assumptions(
            timeframe=parsed_strategy.timeframe,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
        )
        strategy_spec = parsed_strategy.strategy_spec or {}
        strategy_type = str(strategy_spec.get("strategy_type") or parsed_strategy.strategy_kind)
        if strategy_type == "periodic_accumulation":
            assumptions.position_sizing = "scheduled_fixed_accumulation"
            assumptions.signal_evaluation_timing = "execute scheduled accumulation on each trading day"
            assumptions.entry_fill_timing = "same_bar_open"
            assumptions.exit_fill_timing = "forced_close_at_window_end_close"
            return self._run_periodic_accumulation(
                code=code,
                parsed_strategy=parsed_strategy,
                bars=bars,
                assumptions=assumptions,
                initial_capital=initial_capital,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                lookback_bars=lookback_bars,
                start_date=start_date,
                end_date=end_date,
            )
        if strategy_type in {"moving_average_crossover", "macd_crossover", "rsi_threshold"}:
            return self._run_indicator_family_strategy(
                code=code,
                parsed_strategy=parsed_strategy,
                bars=bars,
                assumptions=assumptions,
                initial_capital=initial_capital,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                lookback_bars=lookback_bars,
                start_date=start_date,
                end_date=end_date,
            )
        ordered_bars = list(bars)
        if not ordered_bars:
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                execution_assumptions=assumptions,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars, start_date=start_date, end_date=end_date),
                no_result_reason="insufficient_history",
                no_result_message="没有可用于回测的历史行情数据。",
                warnings=[],
            )

        closes = [self._safe_price(getattr(bar, "close", None)) for bar in ordered_bars]
        if any(price is None for price in closes):
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                execution_assumptions=assumptions,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars, start_date=start_date, end_date=end_date),
                no_result_reason="invalid_price_data",
                no_result_message="历史行情存在缺失收盘价，无法执行规则回测。",
                warnings=[],
            )

        execution_start_index, execution_end_index = self._resolve_execution_window(
            ordered_bars,
            lookback_bars=lookback_bars,
            start_date=start_date,
            end_date=end_date,
        )
        if execution_start_index is None or execution_end_index is None or execution_start_index > execution_end_index:
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                execution_assumptions=assumptions,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars, start_date=start_date, end_date=end_date),
                no_result_reason="no_bars_in_range",
                no_result_message="指定日期区间内没有可用于执行规则回测的历史数据。",
                warnings=[],
            )
        warmup_cache = self._build_indicator_cache(ordered_bars[:], parsed_strategy)
        trades: List[RuleBacktestTrade] = []
        equity_curve: List[RuleBacktestPoint] = []

        position = False
        cash = float(initial_capital)
        entry_node = parsed_strategy.entry
        exit_node = parsed_strategy.exit
        fee_rate = max(0.0, float(fee_bps)) / 10000.0
        slippage_rate = max(0.0, float(slippage_bps)) / 10000.0
        peak_equity = float(initial_capital)
        trade_entry_signals = 0
        shares = 0.0
        active_position: Dict[str, Any] = {}
        pending_entry: Optional[PendingOrder] = None
        pending_exit: Optional[PendingOrder] = None

        for idx, bar in enumerate(ordered_bars):
            price = closes[idx]
            if price is None:
                continue
            if idx < execution_start_index or idx > execution_end_index:
                continue

            executed_action: Optional[str] = None
            executed_fill_price: Optional[float] = None
            executed_fee_amount: Optional[float] = None
            executed_slippage_amount: Optional[float] = None
            action_notes: Optional[str] = None

            if pending_exit is not None and position:
                fill_price, fill_basis = self._resolve_fill_price(bar, close_price=price, preferred="open")
                exit_execution = self._apply_exit_execution(
                    shares=shares,
                    base_fill_price=fill_price,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                )
                cash = float(active_position.get("cash_buffer", 0.0)) + exit_execution["net_proceeds"]
                exit_date = getattr(bar, "date")
                entry_date = active_position["entry_date"]
                holding_bars = max(1, idx - int(active_position["entry_fill_index"]))
                holding_calendar_days = max(1, (exit_date - entry_date).days)
                entry_total_cost = float(active_position["entry_total_cost"])
                trade_return = ((exit_execution["net_proceeds"] / entry_total_cost) - 1.0) * 100.0 if entry_total_cost else 0.0
                trades.append(
                    RuleBacktestTrade(
                        code=code,
                        entry_signal_date=active_position["entry_signal_date"],
                        exit_signal_date=pending_exit.signal_date,
                        entry_date=entry_date,
                        exit_date=exit_date,
                        entry_price=float(active_position["entry_price"]),
                        exit_price=float(exit_execution["effective_price"]),
                        entry_signal=active_position["entry_signal_text"],
                        exit_signal=pending_exit.trigger,
                        entry_trigger=active_position["entry_trigger"],
                        exit_trigger=pending_exit.trigger,
                        return_pct=round(trade_return, 4),
                        holding_days=holding_bars,
                        holding_bars=holding_bars,
                        holding_calendar_days=holding_calendar_days,
                        entry_rule_json=active_position["entry_rule_json"],
                        exit_rule_json=pending_exit.rule_json,
                        entry_indicators=active_position["entry_indicators"],
                        exit_indicators=pending_exit.indicators,
                        entry_fill_basis=active_position["entry_fill_basis"],
                        exit_fill_basis=fill_basis,
                        signal_price_basis="close",
                        price_basis="close",
                        fee_bps=float(fee_bps),
                        slippage_bps=float(slippage_bps),
                        entry_fee_amount=float(active_position["entry_fee_amount"]),
                        exit_fee_amount=float(exit_execution["fee_amount"]),
                        entry_slippage_amount=float(active_position["entry_slippage_amount"]),
                        exit_slippage_amount=float(exit_execution["slippage_amount"]),
                        notes="exit_signal_next_bar_open",
                    )
                )
                pending_exit = None
                active_position = {}
                shares = 0.0
                position = False
                executed_action = "sell"
                executed_fill_price = float(exit_execution["effective_price"])
                executed_fee_amount = float(exit_execution["fee_amount"])
                executed_slippage_amount = float(exit_execution["slippage_amount"])
                action_notes = "exit_signal_next_bar_open"

            if pending_entry is not None and not position:
                fill_price, fill_basis = self._resolve_fill_price(bar, close_price=price, preferred="open")
                entry_execution = self._apply_entry_execution(
                    cash=cash,
                    base_fill_price=fill_price,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                )
                if entry_execution["shares"] > 0:
                    shares = entry_execution["shares"]
                    cash = entry_execution["cash_remaining"]
                    position = True
                    active_position = {
                        "entry_signal_date": pending_entry.signal_date,
                        "entry_date": getattr(bar, "date"),
                        "entry_fill_index": idx,
                        "entry_price": float(entry_execution["effective_price"]),
                        "entry_total_cost": float(entry_execution["total_cost"]),
                        "entry_fee_amount": float(entry_execution["fee_amount"]),
                        "entry_slippage_amount": float(entry_execution["slippage_amount"]),
                        "entry_signal_text": pending_entry.trigger,
                        "entry_trigger": pending_entry.trigger,
                        "entry_rule_json": pending_entry.rule_json,
                        "entry_indicators": pending_entry.indicators,
                        "entry_fill_basis": fill_basis,
                        "cash_buffer": float(entry_execution["cash_remaining"]),
                    }
                    executed_action = "buy"
                    executed_fill_price = float(entry_execution["effective_price"])
                    executed_fee_amount = float(entry_execution["fee_amount"])
                    executed_slippage_amount = float(entry_execution["slippage_amount"])
                    action_notes = "entry_signal_next_bar_open"
                pending_entry = None

            equity = cash if not position else cash + shares * price
            peak_equity = max(peak_equity, equity)
            equity_curve.append(
                self._build_equity_point(
                    point_date=getattr(bar, "date"),
                    close_price=float(price),
                    cash=float(cash),
                    shares=float(shares),
                    initial_capital=float(initial_capital),
                    peak_equity=float(peak_equity),
                    target_position=1.0 if position else 0.0,
                    executed_action=executed_action,
                    fill_price=executed_fill_price,
                    fee_amount=executed_fee_amount,
                    slippage_amount=executed_slippage_amount,
                    notes=action_notes,
                )
            )

            if idx >= execution_end_index:
                continue

            if position and self._evaluate_node(exit_node, idx, ordered_bars, warmup_cache):
                pending_exit = PendingOrder(
                    signal_date=getattr(bar, "date"),
                    trigger=self._format_node(exit_node),
                    rule_json=exit_node,
                    indicators=self._collect_indicator_snapshot(exit_node, idx, ordered_bars, warmup_cache),
                )
                self._update_point_signal(
                    equity_curve[-1],
                    signal_summary=self._format_node(exit_node),
                    target_position=0.0,
                )
                continue

            if not position and self._evaluate_node(entry_node, idx, ordered_bars, warmup_cache):
                trade_entry_signals += 1
                pending_entry = PendingOrder(
                    signal_date=getattr(bar, "date"),
                    trigger=self._format_node(entry_node),
                    rule_json=entry_node,
                    indicators=self._collect_indicator_snapshot(entry_node, idx, ordered_bars, warmup_cache),
                )
                self._update_point_signal(
                    equity_curve[-1],
                    signal_summary=self._format_node(entry_node),
                    target_position=1.0,
                )

        if position and active_position:
            last_bar = ordered_bars[execution_end_index]
            last_price = closes[execution_end_index] or float(active_position["entry_price"])
            fill_price, fill_basis = self._resolve_fill_price(last_bar, close_price=last_price, preferred="close")
            exit_execution = self._apply_exit_execution(
                shares=shares,
                base_fill_price=fill_price,
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
            )
            cash = float(active_position.get("cash_buffer", 0.0)) + exit_execution["net_proceeds"]
            exit_signal_date = pending_exit.signal_date if pending_exit is not None else getattr(last_bar, "date")
            exit_trigger = pending_exit.trigger if pending_exit is not None else "END_OF_WINDOW"
            holding_bars = max(1, execution_end_index - int(active_position["entry_fill_index"]) + 1)
            holding_calendar_days = max(1, (getattr(last_bar, "date") - active_position["entry_date"]).days)
            entry_total_cost = float(active_position["entry_total_cost"])
            trade_return = ((exit_execution["net_proceeds"] / entry_total_cost) - 1.0) * 100.0 if entry_total_cost else 0.0
            trades.append(
                RuleBacktestTrade(
                    code=code,
                    entry_signal_date=active_position["entry_signal_date"],
                    exit_signal_date=exit_signal_date,
                    entry_date=active_position["entry_date"],
                    exit_date=getattr(last_bar, "date"),
                    entry_price=float(active_position["entry_price"]),
                    exit_price=float(exit_execution["effective_price"]),
                    entry_signal=active_position["entry_signal_text"],
                    exit_signal=exit_trigger,
                    entry_trigger=active_position["entry_trigger"],
                    exit_trigger=exit_trigger,
                    return_pct=round(trade_return, 4),
                    holding_days=holding_bars,
                    holding_bars=holding_bars,
                    holding_calendar_days=holding_calendar_days,
                    entry_rule_json=active_position["entry_rule_json"],
                    exit_rule_json=pending_exit.rule_json if pending_exit is not None else exit_node,
                    entry_indicators=active_position["entry_indicators"],
                    exit_indicators=(
                        pending_exit.indicators
                        if pending_exit is not None
                        else self._collect_indicator_snapshot(exit_node, execution_end_index, ordered_bars, warmup_cache)
                    ),
                    entry_fill_basis=active_position["entry_fill_basis"],
                    exit_fill_basis=fill_basis,
                    signal_price_basis="close",
                    price_basis="close",
                    fee_bps=float(fee_bps),
                    slippage_bps=float(slippage_bps),
                    entry_fee_amount=float(active_position["entry_fee_amount"]),
                    exit_fee_amount=float(exit_execution["fee_amount"]),
                    entry_slippage_amount=float(active_position["entry_slippage_amount"]),
                    exit_slippage_amount=float(exit_execution["slippage_amount"]),
                    notes="forced_close_at_window_end",
                )
            )
            previous_signal_summary = equity_curve[-1].signal_summary if equity_curve else None
            equity_curve[-1] = self._build_equity_point(
                point_date=getattr(last_bar, "date"),
                close_price=float(last_price),
                cash=float(cash),
                shares=0.0,
                initial_capital=float(initial_capital),
                peak_equity=float(peak_equity),
                target_position=0.0,
                signal_summary=previous_signal_summary,
                executed_action="forced_close",
                fill_price=float(exit_execution["effective_price"]),
                fee_amount=float(exit_execution["fee_amount"]),
                slippage_amount=float(exit_execution["slippage_amount"]),
                notes="forced_close_at_window_end",
            )

        execution_bars = ordered_bars[execution_start_index:execution_end_index + 1]
        benchmark_metrics = self._build_benchmark_metrics(execution_bars)
        buy_and_hold_curve = self._build_benchmark_curve(execution_bars)
        buy_and_hold_summary = self._build_benchmark_summary(benchmark_metrics)
        metrics = self._build_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=float(initial_capital),
            trade_entry_signals=trade_entry_signals,
            benchmark_metrics=benchmark_metrics,
            lookback_bars=int(lookback_bars),
            start_date=start_date,
            end_date=end_date,
        )
        no_result_reason, no_result_message = self._detect_no_result_reason(metrics, parsed_strategy)
        return RuleBacktestResult(
            parsed_strategy=parsed_strategy,
            execution_assumptions=assumptions,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            benchmark_curve=buy_and_hold_curve,
            benchmark_summary=buy_and_hold_summary,
            buy_and_hold_curve=buy_and_hold_curve,
            buy_and_hold_summary=buy_and_hold_summary,
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            warnings=parsed_strategy.ambiguities,
        )

    def _run_indicator_family_strategy(
        self,
        *,
        code: str,
        parsed_strategy: ParsedStrategy,
        bars: Sequence[Any],
        assumptions: ExecutionAssumptions,
        initial_capital: float,
        fee_bps: float,
        slippage_bps: float,
        lookback_bars: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> RuleBacktestResult:
        ordered_bars = list(bars)
        if not ordered_bars:
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                execution_assumptions=assumptions,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars, start_date=start_date, end_date=end_date),
                no_result_reason="insufficient_history",
                no_result_message="没有可用于回测的历史行情数据。",
                warnings=[],
            )

        closes = [self._safe_price(getattr(bar, "close", None)) for bar in ordered_bars]
        if any(price is None for price in closes):
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                execution_assumptions=assumptions,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars, start_date=start_date, end_date=end_date),
                no_result_reason="invalid_price_data",
                no_result_message="历史行情存在缺失收盘价，无法执行规则回测。",
                warnings=[],
            )

        execution_start_index, execution_end_index = self._resolve_execution_window(
            ordered_bars,
            lookback_bars=lookback_bars,
            start_date=start_date,
            end_date=end_date,
        )
        if execution_start_index is None or execution_end_index is None or execution_start_index > execution_end_index:
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                execution_assumptions=assumptions,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars, start_date=start_date, end_date=end_date),
                no_result_reason="no_bars_in_range",
                no_result_message="指定日期区间内没有可用于执行规则回测的历史数据。",
                warnings=[],
            )

        strategy_spec = parsed_strategy.strategy_spec or {}
        signal_spec = dict(strategy_spec.get("signal") or {})
        series_payload = self._build_strategy_signal_series(closes, strategy_spec)
        fee_rate = max(0.0, float(fee_bps)) / 10000.0
        slippage_rate = max(0.0, float(slippage_bps)) / 10000.0
        trades: List[RuleBacktestTrade] = []
        equity_curve: List[RuleBacktestPoint] = []
        peak_equity = float(initial_capital)
        cash = float(initial_capital)
        shares = 0.0
        position = False
        active_position: Dict[str, Any] = {}
        pending_entry: Optional[PendingOrder] = None
        pending_exit: Optional[PendingOrder] = None
        trade_entry_signals = 0

        for idx, bar in enumerate(ordered_bars):
            price = closes[idx]
            if price is None or idx < execution_start_index or idx > execution_end_index:
                continue

            executed_action: Optional[str] = None
            executed_fill_price: Optional[float] = None
            executed_fee_amount: Optional[float] = None
            executed_slippage_amount: Optional[float] = None
            action_notes: Optional[str] = None

            if pending_exit is not None and position:
                fill_price, fill_basis = self._resolve_fill_price(bar, close_price=price, preferred="open")
                exit_execution = self._apply_exit_execution(
                    shares=shares,
                    base_fill_price=fill_price,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                )
                cash = float(active_position.get("cash_buffer", 0.0)) + exit_execution["net_proceeds"]
                exit_date = getattr(bar, "date")
                entry_date = active_position["entry_date"]
                holding_bars = max(1, idx - int(active_position["entry_fill_index"]))
                holding_calendar_days = max(1, (exit_date - entry_date).days)
                entry_total_cost = float(active_position["entry_total_cost"])
                trade_return = ((exit_execution["net_proceeds"] / entry_total_cost) - 1.0) * 100.0 if entry_total_cost else 0.0
                trades.append(
                    RuleBacktestTrade(
                        code=code,
                        entry_signal_date=active_position["entry_signal_date"],
                        exit_signal_date=pending_exit.signal_date,
                        entry_date=entry_date,
                        exit_date=exit_date,
                        entry_price=float(active_position["entry_price"]),
                        exit_price=float(exit_execution["effective_price"]),
                        entry_signal=active_position["entry_signal_text"],
                        exit_signal=pending_exit.trigger,
                        entry_trigger=active_position["entry_trigger"],
                        exit_trigger=pending_exit.trigger,
                        return_pct=round(trade_return, 4),
                        holding_days=holding_bars,
                        holding_bars=holding_bars,
                        holding_calendar_days=holding_calendar_days,
                        entry_rule_json=active_position["entry_rule_json"],
                        exit_rule_json=pending_exit.rule_json,
                        entry_indicators=active_position["entry_indicators"],
                        exit_indicators=pending_exit.indicators,
                        entry_fill_basis=active_position["entry_fill_basis"],
                        exit_fill_basis=fill_basis,
                        signal_price_basis="close",
                        price_basis="close",
                        fee_bps=float(fee_bps),
                        slippage_bps=float(slippage_bps),
                        entry_fee_amount=float(active_position["entry_fee_amount"]),
                        exit_fee_amount=float(exit_execution["fee_amount"]),
                        entry_slippage_amount=float(active_position["entry_slippage_amount"]),
                        exit_slippage_amount=float(exit_execution["slippage_amount"]),
                        notes=f"{strategy_spec.get('strategy_type')}_exit_next_bar_open",
                    )
                )
                pending_exit = None
                active_position = {}
                shares = 0.0
                position = False
                executed_action = "sell"
                executed_fill_price = float(exit_execution["effective_price"])
                executed_fee_amount = float(exit_execution["fee_amount"])
                executed_slippage_amount = float(exit_execution["slippage_amount"])
                action_notes = f"{strategy_spec.get('strategy_type')}_exit_next_bar_open"

            if pending_entry is not None and not position:
                fill_price, fill_basis = self._resolve_fill_price(bar, close_price=price, preferred="open")
                entry_execution = self._apply_entry_execution(
                    cash=cash,
                    base_fill_price=fill_price,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                )
                if entry_execution["shares"] > 0:
                    shares = entry_execution["shares"]
                    cash = entry_execution["cash_remaining"]
                    position = True
                    active_position = {
                        "entry_signal_date": pending_entry.signal_date,
                        "entry_date": getattr(bar, "date"),
                        "entry_fill_index": idx,
                        "entry_price": float(entry_execution["effective_price"]),
                        "entry_total_cost": float(entry_execution["total_cost"]),
                        "entry_fee_amount": float(entry_execution["fee_amount"]),
                        "entry_slippage_amount": float(entry_execution["slippage_amount"]),
                        "entry_signal_text": pending_entry.trigger,
                        "entry_trigger": pending_entry.trigger,
                        "entry_rule_json": pending_entry.rule_json,
                        "entry_indicators": pending_entry.indicators,
                        "entry_fill_basis": fill_basis,
                        "cash_buffer": float(entry_execution["cash_remaining"]),
                    }
                    executed_action = "buy"
                    executed_fill_price = float(entry_execution["effective_price"])
                    executed_fee_amount = float(entry_execution["fee_amount"])
                    executed_slippage_amount = float(entry_execution["slippage_amount"])
                    action_notes = f"{strategy_spec.get('strategy_type')}_entry_next_bar_open"
                pending_entry = None

            equity = cash if not position else cash + shares * price
            peak_equity = max(peak_equity, equity)
            equity_curve.append(
                self._build_equity_point(
                    point_date=getattr(bar, "date"),
                    close_price=float(price),
                    cash=float(cash),
                    shares=float(shares),
                    initial_capital=float(initial_capital),
                    peak_equity=float(peak_equity),
                    target_position=1.0 if position else 0.0,
                    executed_action=executed_action,
                    fill_price=executed_fill_price,
                    fee_amount=executed_fee_amount,
                    slippage_amount=executed_slippage_amount,
                    notes=action_notes,
                )
            )

            if idx >= execution_end_index:
                continue

            if position and self._signal_family_triggered("exit", idx, series_payload, signal_spec):
                pending_exit = PendingOrder(
                    signal_date=getattr(bar, "date"),
                    trigger=str(parsed_strategy.summary.get("exit") or "Exit signal"),
                    rule_json={"strategy_spec": signal_spec, "condition": signal_spec.get("exit_condition")},
                    indicators=self._collect_signal_strategy_snapshot(strategy_spec, idx, series_payload, ordered_bars),
                )
                self._update_point_signal(
                    equity_curve[-1],
                    signal_summary=str(parsed_strategy.summary.get("exit") or "Exit signal"),
                    target_position=0.0,
                )
                continue

            if (not position) and self._signal_family_triggered("entry", idx, series_payload, signal_spec):
                trade_entry_signals += 1
                pending_entry = PendingOrder(
                    signal_date=getattr(bar, "date"),
                    trigger=str(parsed_strategy.summary.get("entry") or "Entry signal"),
                    rule_json={"strategy_spec": signal_spec, "condition": signal_spec.get("entry_condition")},
                    indicators=self._collect_signal_strategy_snapshot(strategy_spec, idx, series_payload, ordered_bars),
                )
                self._update_point_signal(
                    equity_curve[-1],
                    signal_summary=str(parsed_strategy.summary.get("entry") or "Entry signal"),
                    target_position=1.0,
                )

        end_behavior = dict(strategy_spec.get("end_behavior") or {})
        if position and active_position and str(end_behavior.get("policy") or "liquidate_at_end") == "liquidate_at_end":
            last_bar = ordered_bars[execution_end_index]
            last_price = closes[execution_end_index] or float(active_position["entry_price"])
            fill_price, fill_basis = self._resolve_fill_price(
                last_bar,
                close_price=last_price,
                preferred=str(end_behavior.get("price_basis") or "close"),
            )
            exit_execution = self._apply_exit_execution(
                shares=shares,
                base_fill_price=fill_price,
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
            )
            cash = float(active_position.get("cash_buffer", 0.0)) + exit_execution["net_proceeds"]
            holding_bars = max(1, execution_end_index - int(active_position["entry_fill_index"]) + 1)
            holding_calendar_days = max(1, (getattr(last_bar, "date") - active_position["entry_date"]).days)
            entry_total_cost = float(active_position["entry_total_cost"])
            trade_return = ((exit_execution["net_proceeds"] / entry_total_cost) - 1.0) * 100.0 if entry_total_cost else 0.0
            trades.append(
                RuleBacktestTrade(
                    code=code,
                    entry_signal_date=active_position["entry_signal_date"],
                    exit_signal_date=getattr(last_bar, "date"),
                    entry_date=active_position["entry_date"],
                    exit_date=getattr(last_bar, "date"),
                    entry_price=float(active_position["entry_price"]),
                    exit_price=float(exit_execution["effective_price"]),
                    entry_signal=active_position["entry_signal_text"],
                    exit_signal="END_OF_WINDOW",
                    entry_trigger=active_position["entry_trigger"],
                    exit_trigger="END_OF_WINDOW",
                    return_pct=round(trade_return, 4),
                    holding_days=holding_bars,
                    holding_bars=holding_bars,
                    holding_calendar_days=holding_calendar_days,
                    entry_rule_json=active_position["entry_rule_json"],
                    exit_rule_json={"strategy_spec": signal_spec, "condition": "end_of_test_liquidation"},
                    entry_indicators=active_position["entry_indicators"],
                    exit_indicators=self._collect_signal_strategy_snapshot(strategy_spec, execution_end_index, series_payload, ordered_bars),
                    entry_fill_basis=active_position["entry_fill_basis"],
                    exit_fill_basis=fill_basis,
                    signal_price_basis="close",
                    price_basis="close",
                    fee_bps=float(fee_bps),
                    slippage_bps=float(slippage_bps),
                    entry_fee_amount=float(active_position["entry_fee_amount"]),
                    exit_fee_amount=float(exit_execution["fee_amount"]),
                    entry_slippage_amount=float(active_position["entry_slippage_amount"]),
                    exit_slippage_amount=float(exit_execution["slippage_amount"]),
                    notes="forced_close_at_window_end",
                )
            )
            previous_signal_summary = equity_curve[-1].signal_summary if equity_curve else None
            equity_curve[-1] = self._build_equity_point(
                point_date=getattr(last_bar, "date"),
                close_price=float(last_price),
                cash=float(cash),
                shares=0.0,
                initial_capital=float(initial_capital),
                peak_equity=float(peak_equity),
                target_position=0.0,
                signal_summary=previous_signal_summary,
                executed_action="forced_close",
                fill_price=float(exit_execution["effective_price"]),
                fee_amount=float(exit_execution["fee_amount"]),
                slippage_amount=float(exit_execution["slippage_amount"]),
                notes="forced_close_at_window_end",
            )

        execution_bars = ordered_bars[execution_start_index:execution_end_index + 1]
        benchmark_metrics = self._build_benchmark_metrics(execution_bars)
        buy_and_hold_curve = self._build_benchmark_curve(execution_bars)
        buy_and_hold_summary = self._build_benchmark_summary(benchmark_metrics)
        metrics = self._build_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=float(initial_capital),
            trade_entry_signals=trade_entry_signals,
            benchmark_metrics=benchmark_metrics,
            lookback_bars=int(lookback_bars),
            start_date=start_date,
            end_date=end_date,
        )
        no_result_reason, no_result_message = self._detect_no_result_reason(metrics, parsed_strategy)
        return RuleBacktestResult(
            parsed_strategy=parsed_strategy,
            execution_assumptions=assumptions,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            benchmark_curve=buy_and_hold_curve,
            benchmark_summary=buy_and_hold_summary,
            buy_and_hold_curve=buy_and_hold_curve,
            buy_and_hold_summary=buy_and_hold_summary,
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            warnings=parsed_strategy.ambiguities,
        )

    def _run_periodic_accumulation(
        self,
        *,
        code: str,
        parsed_strategy: ParsedStrategy,
        bars: Sequence[Any],
        assumptions: ExecutionAssumptions,
        initial_capital: float,
        fee_bps: float,
        slippage_bps: float,
        lookback_bars: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> RuleBacktestResult:
        ordered_bars = list(bars)
        if not ordered_bars:
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                execution_assumptions=assumptions,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars, start_date=start_date, end_date=end_date),
                no_result_reason="insufficient_history",
                no_result_message="没有可用于回测的历史行情数据。",
                warnings=[],
            )

        execution_start_index, execution_end_index = self._resolve_execution_window(
            ordered_bars,
            lookback_bars=lookback_bars,
            start_date=start_date,
            end_date=end_date,
        )
        if execution_start_index is None or execution_end_index is None or execution_start_index > execution_end_index:
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                execution_assumptions=assumptions,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars, start_date=start_date, end_date=end_date),
                no_result_reason="no_bars_in_range",
                no_result_message="指定日期区间内没有可用于执行规则回测的历史数据。",
                warnings=[],
            )

        strategy_spec = parsed_strategy.strategy_spec or {}
        order_mode = str(strategy_spec.get("entry", {}).get("order", {}).get("mode") or "fixed_shares")
        quantity_per_trade = _safe_float(strategy_spec.get("entry", {}).get("order", {}).get("quantity"))
        amount_per_trade = _safe_float(strategy_spec.get("entry", {}).get("order", {}).get("amount"))
        cash_policy = str(strategy_spec.get("position_behavior", {}).get("cash_policy") or "stop_when_insufficient_cash")
        fee_rate = max(0.0, float(fee_bps)) / 10000.0
        slippage_rate = max(0.0, float(slippage_bps)) / 10000.0

        cash = float(initial_capital)
        total_shares = 0.0
        peak_equity = float(initial_capital)
        equity_curve: List[RuleBacktestPoint] = []
        trades: List[RuleBacktestTrade] = []
        open_lots: List[Dict[str, Any]] = []
        stop_buying = False
        buy_attempts = 0

        for idx in range(execution_start_index, execution_end_index + 1):
            bar = ordered_bars[idx]
            close_price = self._safe_price(getattr(bar, "close", None))
            if close_price is None:
                continue

            executed_action: Optional[str] = None
            executed_fill_price: Optional[float] = None
            executed_fee_amount: Optional[float] = None
            executed_slippage_amount: Optional[float] = None
            action_notes: Optional[str] = None
            signal_summary: Optional[str] = None

            if not stop_buying:
                buy_attempts += 1
                base_fill_price, fill_basis = self._resolve_fill_price(bar, close_price=close_price, preferred="open")
                order_plan = self._build_periodic_order_plan(
                    order_mode=order_mode,
                    quantity_per_trade=quantity_per_trade,
                    amount_per_trade=amount_per_trade,
                    base_fill_price=base_fill_price,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                    available_cash=cash,
                )
                if order_plan is None:
                    if cash_policy == "stop_when_insufficient_cash":
                        stop_buying = True
                        signal_summary = "现金不足，后续停止继续买入"
                        action_notes = "stop_buying_when_insufficient_cash"
                    else:
                        signal_summary = "现金不足，跳过本次计划买入"
                        action_notes = "skip_buy_when_insufficient_cash"
                else:
                    cash -= order_plan["total_cost"]
                    total_shares += order_plan["shares"]
                    open_lots.append(
                        {
                            "entry_signal_date": getattr(bar, "date"),
                            "entry_date": getattr(bar, "date"),
                            "entry_index": idx,
                            "entry_price": order_plan["effective_price"],
                            "entry_fee_amount": order_plan["fee_amount"],
                            "entry_slippage_amount": order_plan["slippage_amount"],
                            "shares": order_plan["shares"],
                            "entry_fill_basis": fill_basis,
                            "cash_after_buy": cash,
                        }
                    )
                    executed_action = "accumulate"
                    executed_fill_price = float(order_plan["effective_price"])
                    executed_fee_amount = float(order_plan["fee_amount"])
                    executed_slippage_amount = float(order_plan["slippage_amount"])
                    signal_summary = f"按计划买入 {self._format_accumulation_size(order_mode, quantity_per_trade, amount_per_trade)}"
                    action_notes = "periodic_accumulation_fill"

            equity = cash + total_shares * close_price
            peak_equity = max(peak_equity, equity)
            equity_curve.append(
                self._build_equity_point(
                    point_date=getattr(bar, "date"),
                    close_price=float(close_price),
                    cash=float(cash),
                    shares=float(total_shares),
                    initial_capital=float(initial_capital),
                    peak_equity=float(peak_equity),
                    target_position=(float(total_shares * close_price) / float(equity)) if equity > 0 else 0.0,
                    signal_summary=signal_summary,
                    executed_action=executed_action,
                    fill_price=executed_fill_price,
                    fee_amount=executed_fee_amount,
                    slippage_amount=executed_slippage_amount,
                    notes=action_notes,
                )
            )

        if open_lots and equity_curve:
            last_bar = ordered_bars[execution_end_index]
            last_close = self._safe_price(getattr(last_bar, "close", None)) or 0.0
            total_exit_fee = 0.0
            total_exit_slippage = 0.0
            final_fill_price = last_close * (1.0 - slippage_rate)
            for lot in open_lots:
                exit_execution = self._apply_exit_execution(
                    shares=lot["shares"],
                    base_fill_price=last_close,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                )
                cash += exit_execution["net_proceeds"]
                total_shares -= lot["shares"]
                total_exit_fee += float(exit_execution["fee_amount"])
                total_exit_slippage += float(exit_execution["slippage_amount"])
                final_fill_price = float(exit_execution["effective_price"])
                holding_calendar_days = max(1, (getattr(last_bar, "date") - lot["entry_date"]).days)
                holding_bars = max(1, execution_end_index - int(lot["entry_index"]) + 1)
                entry_total_cost = float(lot["shares"]) * float(lot["entry_price"]) + float(lot["entry_fee_amount"])
                trade_return = ((exit_execution["net_proceeds"] / entry_total_cost) - 1.0) * 100.0 if entry_total_cost else 0.0
                trades.append(
                    RuleBacktestTrade(
                        code=code,
                        entry_signal_date=lot["entry_signal_date"],
                        exit_signal_date=getattr(last_bar, "date"),
                        entry_date=lot["entry_date"],
                        exit_date=getattr(last_bar, "date"),
                        entry_price=float(lot["entry_price"]),
                        exit_price=float(exit_execution["effective_price"]),
                        entry_signal=f"定投买入 {self._format_accumulation_size(order_mode, quantity_per_trade, amount_per_trade)}",
                        exit_signal="区间结束统一平仓",
                        entry_trigger="PERIODIC_BUY",
                        exit_trigger="END_OF_WINDOW",
                        return_pct=round(trade_return, 4),
                        holding_days=holding_bars,
                        holding_bars=holding_bars,
                        holding_calendar_days=holding_calendar_days,
                        entry_rule_json={"strategy_spec": strategy_spec.get("entry", {}), "strategy_type": "periodic_accumulation"},
                        exit_rule_json={"strategy_spec": strategy_spec.get("exit", {})},
                        entry_indicators={
                            "shares": round(float(lot["shares"]), 6),
                            "cash_after_buy": round(float(max(lot["cash_after_buy"], 0.0)), 6),
                        },
                        exit_indicators={"close": round(float(last_close), 6)},
                        entry_fill_basis=lot["entry_fill_basis"],
                        exit_fill_basis="close",
                        signal_price_basis="scheduled",
                        price_basis="close",
                        fee_bps=float(fee_bps),
                        slippage_bps=float(slippage_bps),
                        entry_fee_amount=float(lot["entry_fee_amount"]),
                        exit_fee_amount=float(exit_execution["fee_amount"]),
                        entry_slippage_amount=float(lot["entry_slippage_amount"]),
                        exit_slippage_amount=float(exit_execution["slippage_amount"]),
                        notes="periodic_accumulation_lot",
                    )
                )
            equity_curve[-1] = self._build_equity_point(
                point_date=getattr(last_bar, "date"),
                close_price=float(last_close),
                cash=float(cash),
                shares=0.0,
                initial_capital=float(initial_capital),
                peak_equity=float(peak_equity),
                target_position=0.0,
                signal_summary="区间结束统一平仓",
                executed_action="forced_close",
                fill_price=float(final_fill_price),
                fee_amount=float(total_exit_fee),
                slippage_amount=float(total_exit_slippage),
                notes="periodic_accumulation_window_close",
            )

        execution_bars = ordered_bars[execution_start_index:execution_end_index + 1]
        benchmark_metrics = self._build_benchmark_metrics(execution_bars)
        buy_and_hold_curve = self._build_benchmark_curve(execution_bars)
        buy_and_hold_summary = self._build_benchmark_summary(benchmark_metrics)
        metrics = self._build_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=float(initial_capital),
            trade_entry_signals=buy_attempts,
            benchmark_metrics=benchmark_metrics,
            lookback_bars=int(lookback_bars),
            start_date=start_date,
            end_date=end_date,
        )
        no_result_reason = None
        no_result_message = None
        if metrics.get("trade_count", 0) <= 0:
            no_result_reason = "no_trades"
            no_result_message = "指定区间内未能完成任何定投买入。"
        return RuleBacktestResult(
            parsed_strategy=parsed_strategy,
            execution_assumptions=assumptions,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            benchmark_curve=buy_and_hold_curve,
            benchmark_summary=buy_and_hold_summary,
            buy_and_hold_curve=buy_and_hold_curve,
            buy_and_hold_summary=buy_and_hold_summary,
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            warnings=parsed_strategy.ambiguities,
        )

    def _build_strategy_signal_series(
        self,
        closes: Sequence[Optional[float]],
        strategy_spec: Dict[str, Any],
    ) -> Dict[str, List[Optional[float]]]:
        signal_spec = dict(strategy_spec.get("signal") or {})
        strategy_type = str(strategy_spec.get("strategy_type") or "")
        if strategy_type == "moving_average_crossover":
            fast_period = int(signal_spec.get("fast_period") or 5)
            slow_period = int(signal_spec.get("slow_period") or 20)
            fast_builder = self._build_ema if str(signal_spec.get("fast_type") or "simple") == "ema" else self._build_sma
            slow_builder = self._build_ema if str(signal_spec.get("slow_type") or "simple") == "ema" else self._build_sma
            return {
                "fast": fast_builder(closes, fast_period),
                "slow": slow_builder(closes, slow_period),
            }
        if strategy_type == "macd_crossover":
            fast_period = int(signal_spec.get("fast_period") or 12)
            slow_period = int(signal_spec.get("slow_period") or 26)
            signal_period = int(signal_spec.get("signal_period") or 9)
            fast_ema = self._build_ema(closes, fast_period)
            slow_ema = self._build_ema(closes, slow_period)
            macd_line = [
                ((float(fast_ema[idx]) - float(slow_ema[idx])) if fast_ema[idx] is not None and slow_ema[idx] is not None else None)
                for idx in range(len(closes))
            ]
            signal_line = self._build_ema(macd_line, signal_period)
            histogram = [
                ((float(macd_line[idx]) - float(signal_line[idx])) if macd_line[idx] is not None and signal_line[idx] is not None else None)
                for idx in range(len(closes))
            ]
            return {
                "macd": macd_line,
                "signal": signal_line,
                "histogram": histogram,
            }
        if strategy_type == "rsi_threshold":
            period = int(signal_spec.get("period") or 14)
            return {
                "rsi": self._build_rsi(closes, period),
            }
        return {}

    def _signal_family_triggered(
        self,
        side: str,
        index: int,
        series_payload: Dict[str, List[Optional[float]]],
        signal_spec: Dict[str, Any],
    ) -> bool:
        indicator_family = str(signal_spec.get("indicator_family") or "").lower()
        if index <= 0:
            return False
        if indicator_family == "moving_average":
            fast_series = series_payload.get("fast") or []
            slow_series = series_payload.get("slow") or []
            return self._cross_signal(fast_series, slow_series, index, direction=("above" if side == "entry" else "below"))
        if indicator_family == "macd":
            macd_line = series_payload.get("macd") or []
            signal_line = series_payload.get("signal") or []
            return self._cross_signal(macd_line, signal_line, index, direction=("above" if side == "entry" else "below"))
        if indicator_family == "rsi":
            rsi_series = series_payload.get("rsi") or []
            threshold_value = signal_spec.get("lower_threshold") if side == "entry" else signal_spec.get("upper_threshold")
            threshold = float(threshold_value or 0.0)
            previous = rsi_series[index - 1] if index - 1 < len(rsi_series) else None
            current = rsi_series[index] if index < len(rsi_series) else None
            if previous is None or current is None:
                return False
            if side == "entry":
                return float(previous) >= threshold and float(current) < threshold
            return float(previous) <= threshold and float(current) > threshold
        return False

    @staticmethod
    def _cross_signal(
        left_series: Sequence[Optional[float]],
        right_series: Sequence[Optional[float]],
        index: int,
        *,
        direction: str,
    ) -> bool:
        if index <= 0 or index >= len(left_series) or index >= len(right_series):
            return False
        prev_left = left_series[index - 1]
        prev_right = right_series[index - 1]
        current_left = left_series[index]
        current_right = right_series[index]
        if prev_left is None or prev_right is None or current_left is None or current_right is None:
            return False
        if direction == "above":
            return float(prev_left) <= float(prev_right) and float(current_left) > float(current_right)
        return float(prev_left) >= float(prev_right) and float(current_left) < float(current_right)

    def _collect_signal_strategy_snapshot(
        self,
        strategy_spec: Dict[str, Any],
        index: int,
        series_payload: Dict[str, List[Optional[float]]],
        bars: Sequence[Any],
    ) -> Dict[str, Any]:
        signal_spec = dict(strategy_spec.get("signal") or {})
        indicator_family = str(signal_spec.get("indicator_family") or "").lower()
        close_value = self._safe_price(getattr(bars[index], "close", None))
        snapshot: Dict[str, Any] = {
            "Close": round(float(close_value), 6) if close_value is not None else None,
        }
        if indicator_family == "moving_average":
            fast_period = int(signal_spec.get("fast_period") or 5)
            slow_period = int(signal_spec.get("slow_period") or 20)
            fast_label = f"{'EMA' if str(signal_spec.get('fast_type') or 'simple') == 'ema' else 'SMA'}{fast_period}"
            slow_label = f"{'EMA' if str(signal_spec.get('slow_type') or 'simple') == 'ema' else 'SMA'}{slow_period}"
            snapshot[fast_label] = self._series_value(series_payload.get("fast"), index)
            snapshot[slow_label] = self._series_value(series_payload.get("slow"), index)
            return snapshot
        if indicator_family == "macd":
            snapshot["MACD"] = self._series_value(series_payload.get("macd"), index)
            snapshot["Signal"] = self._series_value(series_payload.get("signal"), index)
            snapshot["Histogram"] = self._series_value(series_payload.get("histogram"), index)
            return snapshot
        if indicator_family == "rsi":
            period = int(signal_spec.get("period") or 14)
            snapshot[f"RSI{period}"] = self._series_value(series_payload.get("rsi"), index)
            return snapshot
        return snapshot

    @staticmethod
    def _series_value(series: Optional[Sequence[Optional[float]]], index: int) -> Optional[float]:
        if not series or index >= len(series):
            return None
        value = series[index]
        return round(float(value), 6) if value is not None else None

    @staticmethod
    def _build_periodic_order_plan(
        *,
        order_mode: str,
        quantity_per_trade: Optional[float],
        amount_per_trade: Optional[float],
        base_fill_price: float,
        fee_rate: float,
        slippage_rate: float,
        available_cash: float,
    ) -> Optional[Dict[str, float]]:
        effective_price = float(base_fill_price) * (1.0 + slippage_rate)
        per_share_cost = effective_price * (1.0 + fee_rate)
        if per_share_cost <= 0:
            return None
        if order_mode == "fixed_amount":
            target_amount = float(amount_per_trade or 0.0)
            if target_amount <= 0:
                return None
            gross_budget = min(target_amount, float(available_cash))
            shares = gross_budget / per_share_cost
        else:
            shares = float(quantity_per_trade or 0.0)
        if shares <= 0:
            return None
        gross_notional = shares * effective_price
        fee_amount = gross_notional * fee_rate
        total_cost = gross_notional + fee_amount
        if total_cost > float(available_cash) + 1e-9:
            return None
        slippage_amount = shares * max(0.0, effective_price - float(base_fill_price))
        return {
            "shares": float(shares),
            "effective_price": float(effective_price),
            "fee_amount": float(fee_amount),
            "slippage_amount": float(slippage_amount),
            "total_cost": float(total_cost),
        }

    @staticmethod
    def _format_accumulation_size(
        order_mode: str,
        quantity_per_trade: Optional[float],
        amount_per_trade: Optional[float],
    ) -> str:
        if order_mode == "fixed_amount":
            return f"{float(amount_per_trade or 0.0):g} 元"
        return f"{float(quantity_per_trade or 0.0):g} 股"

    @staticmethod
    def _resolve_execution_window(
        bars: Sequence[Any],
        *,
        lookback_bars: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> Tuple[Optional[int], Optional[int]]:
        if not bars:
            return None, None
        if start_date is None and end_date is None:
            return max(0, len(bars) - max(1, int(lookback_bars))), len(bars) - 1

        start_index: Optional[int] = None
        end_index: Optional[int] = None
        for idx, bar in enumerate(bars):
            bar_date = getattr(bar, "date", None)
            if not isinstance(bar_date, date):
                continue
            if start_date is not None and bar_date < start_date:
                continue
            if end_date is not None and bar_date > end_date:
                if end_index is not None:
                    break
                continue
            if start_index is None:
                start_index = idx
            end_index = idx
        return start_index, end_index

    def _build_indicator_cache(self, bars: Sequence[Any], parsed_strategy: ParsedStrategy) -> Dict[Tuple[str, int], List[Optional[float]]]:
        closes = [self._safe_price(getattr(bar, "close", None)) for bar in bars]
        requirements = self._collect_requirements(parsed_strategy.entry)
        exit_requirements = self._collect_requirements(parsed_strategy.exit)
        for indicator, periods in exit_requirements.items():
            requirements.setdefault(indicator, set()).update(periods)
        cache: Dict[Tuple[str, int], List[Optional[float]]] = {}
        for indicator, periods in requirements.items():
            for period in sorted(periods):
                if indicator == "ma":
                    cache[(indicator, period)] = self._build_sma(closes, period)
                elif indicator == "ema":
                    cache[(indicator, period)] = self._build_ema(closes, period)
                elif indicator == "rsi":
                    cache[(indicator, period)] = self._build_rsi(closes, period)
                elif indicator == "return_pct":
                    cache[(indicator, period)] = self._build_return_pct(closes, period)
        return cache

    def _evaluate_node(
        self,
        node: Dict[str, Any],
        index: int,
        bars: Sequence[Any],
        cache: Dict[Tuple[str, int], List[Optional[float]]],
    ) -> bool:
        if not node:
            return False
        node_type = node.get("type")
        if node_type == "group":
            rules = node.get("rules", []) or []
            if not rules:
                return False
            results = [self._evaluate_node(rule, index, bars, cache) for rule in rules]
            return all(results) if node.get("op") == "and" else any(results)
        if node_type == "comparison":
            left = self._resolve_operand(node.get("left"), index, bars, cache)
            right = self._resolve_operand(node.get("right"), index, bars, cache)
            if left is None or right is None:
                return False
            compare = node.get("compare")
            if compare == ">":
                return left > right
            if compare == "<":
                return left < right
            if compare == ">=":
                return left >= right
            if compare == "<=":
                return left <= right
            return False
        return False

    def _resolve_operand(
        self,
        operand: Optional[Dict[str, Any]],
        index: int,
        bars: Sequence[Any],
        cache: Dict[Tuple[str, int], List[Optional[float]]],
    ) -> Optional[float]:
        if not operand:
            return None
        if operand.get("kind") == "value":
            return _safe_float(operand.get("value"))
        if operand.get("kind") != "indicator":
            return None
        indicator = operand.get("indicator")
        period = int(operand.get("period") or 0)
        if indicator == "close":
            return self._safe_price(getattr(bars[index], "close", None))
        series = cache.get((indicator, period))
        if not series or index >= len(series):
            return None
        return series[index]

    @staticmethod
    def _build_execution_assumptions(*, timeframe: str, fee_bps: float, slippage_bps: float) -> ExecutionAssumptions:
        return ExecutionAssumptions(
            timeframe=str(timeframe or "daily"),
            indicator_price_basis="close",
            signal_evaluation_timing="evaluate rules on each bar close",
            entry_fill_timing="next_bar_open",
            exit_fill_timing="next_bar_open; last openless bar falls back to same-bar close",
            default_fill_price_basis="open",
            position_sizing="single_position_full_notional",
            fee_model="bps_per_side",
            fee_bps_per_side=float(fee_bps),
            slippage_model="bps_per_side",
            slippage_bps_per_side=float(slippage_bps),
            benchmark_method="buy_and_hold_same_window",
            benchmark_price_basis="close",
        )

    def _resolve_fill_price(self, bar: Any, *, close_price: float, preferred: str) -> Tuple[float, str]:
        if preferred == "open":
            open_price = self._safe_price(getattr(bar, "open", None))
            if open_price is not None:
                return float(open_price), "open"
            return float(close_price), "close_fallback"
        return float(close_price), "close"

    @staticmethod
    def _apply_entry_execution(
        *,
        cash: float,
        base_fill_price: float,
        fee_rate: float,
        slippage_rate: float,
    ) -> Dict[str, float]:
        effective_price = float(base_fill_price) * (1.0 + slippage_rate)
        per_share_cost = effective_price * (1.0 + fee_rate)
        shares = float(cash) / per_share_cost if per_share_cost > 0 else 0.0
        gross_notional = shares * effective_price
        fee_amount = gross_notional * fee_rate
        total_cost = gross_notional + fee_amount
        slippage_amount = shares * max(0.0, effective_price - float(base_fill_price))
        cash_remaining = max(0.0, float(cash) - total_cost)
        return {
            "shares": float(shares),
            "effective_price": float(effective_price),
            "fee_amount": float(fee_amount),
            "slippage_amount": float(slippage_amount),
            "total_cost": float(total_cost),
            "cash_remaining": float(cash_remaining),
        }

    @staticmethod
    def _apply_exit_execution(
        *,
        shares: float,
        base_fill_price: float,
        fee_rate: float,
        slippage_rate: float,
    ) -> Dict[str, float]:
        effective_price = float(base_fill_price) * (1.0 - slippage_rate)
        gross_proceeds = float(shares) * effective_price
        fee_amount = gross_proceeds * fee_rate
        net_proceeds = gross_proceeds - fee_amount
        slippage_amount = float(shares) * max(0.0, float(base_fill_price) - effective_price)
        return {
            "effective_price": float(effective_price),
            "fee_amount": float(fee_amount),
            "slippage_amount": float(slippage_amount),
            "net_proceeds": float(net_proceeds),
        }

    @staticmethod
    def _build_equity_point(
        *,
        point_date: date,
        close_price: float,
        cash: float,
        shares: float,
        initial_capital: float,
        peak_equity: float,
        target_position: Optional[float] = None,
        signal_summary: Optional[str] = None,
        executed_action: Optional[str] = None,
        fill_price: Optional[float] = None,
        fee_amount: Optional[float] = None,
        slippage_amount: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> RuleBacktestPoint:
        holdings_value = max(0.0, float(shares)) * float(close_price)
        total_portfolio_value = float(cash) + holdings_value
        exposure_pct = (holdings_value / total_portfolio_value) if total_portfolio_value > 0 else 0.0
        cumulative_return_pct = ((total_portfolio_value / float(initial_capital)) - 1.0) * 100.0 if initial_capital else 0.0
        drawdown_pct = 0.0 if peak_equity <= 0 else ((total_portfolio_value / float(peak_equity)) - 1.0) * 100.0
        return RuleBacktestPoint(
            date=point_date,
            equity=float(total_portfolio_value),
            cumulative_return_pct=float(cumulative_return_pct),
            drawdown_pct=float(drawdown_pct),
            close=float(close_price),
            signal_summary=signal_summary,
            target_position=float(target_position) if target_position is not None else None,
            executed_action=executed_action,
            fill_price=float(fill_price) if fill_price is not None else None,
            shares_held=float(shares),
            cash=float(cash),
            holdings_value=float(holdings_value),
            total_portfolio_value=float(total_portfolio_value),
            position_state="long" if float(shares) > 0 else "flat",
            exposure_pct=float(exposure_pct),
            fee_amount=float(fee_amount) if fee_amount is not None else None,
            slippage_amount=float(slippage_amount) if slippage_amount is not None else None,
            notes=notes,
        )

    @staticmethod
    def _update_point_signal(
        point: RuleBacktestPoint,
        *,
        signal_summary: Optional[str] = None,
        target_position: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> None:
        if signal_summary:
            point.signal_summary = signal_summary
        if target_position is not None:
            point.target_position = float(target_position)
        if notes:
            point.notes = notes

    def _collect_indicator_snapshot(
        self,
        node: Dict[str, Any],
        index: int,
        bars: Sequence[Any],
        cache: Dict[Tuple[str, int], List[Optional[float]]],
    ) -> Dict[str, Any]:
        labels = self._collect_indicator_labels(node)
        snapshot: Dict[str, Any] = {}
        for label, operand in labels.items():
            value = self._resolve_operand(operand, index, bars, cache)
            snapshot[label] = _round_pct(value) if operand.get("indicator") == "return_pct" else (round(float(value), 6) if value is not None else None)
        close_value = self._safe_price(getattr(bars[index], "close", None))
        snapshot.setdefault("Close", round(float(close_value), 6) if close_value is not None else None)
        return snapshot

    def _collect_indicator_labels(self, node: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        labels: Dict[str, Dict[str, Any]] = {}
        if not node:
            return labels
        if node.get("type") == "group":
            for child in node.get("rules", []) or []:
                labels.update(self._collect_indicator_labels(child))
            return labels
        if node.get("type") == "comparison":
            for side in ("left", "right"):
                operand = node.get(side) or {}
                if operand.get("kind") != "indicator":
                    continue
                labels[self._format_operand(operand)] = operand
        return labels

    def _collect_requirements(self, node: Dict[str, Any]) -> Dict[str, set]:
        requirements: Dict[str, set] = {"ma": set(), "ema": set(), "rsi": set(), "return_pct": set()}
        if not node:
            return requirements
        if node.get("type") == "group":
            for child in node.get("rules", []) or []:
                child_req = self._collect_requirements(child)
                for indicator, periods in child_req.items():
                    requirements.setdefault(indicator, set()).update(periods)
            return requirements
        if node.get("type") == "comparison":
            for side in ("left", "right"):
                op = node.get(side) or {}
                if op.get("kind") != "indicator":
                    continue
                indicator = op.get("indicator")
                period = int(op.get("period") or 1)
                if indicator in requirements:
                    requirements[indicator].add(period)
        return requirements

    @staticmethod
    def _build_sma(closes: Sequence[Optional[float]], period: int) -> List[Optional[float]]:
        series: List[Optional[float]] = []
        window: List[float] = []
        for price in closes:
            if price is None:
                series.append(None)
                continue
            window.append(float(price))
            if len(window) > period:
                window.pop(0)
            if len(window) < period:
                series.append(None)
                continue
            series.append(sum(window) / len(window))
        return series

    @staticmethod
    def _build_ema(closes: Sequence[Optional[float]], period: int) -> List[Optional[float]]:
        series: List[Optional[float]] = []
        alpha = 2.0 / (period + 1.0)
        prev: Optional[float] = None
        for price in closes:
            if price is None:
                series.append(None)
                continue
            current = float(price) if prev is None else (float(price) * alpha + prev * (1.0 - alpha))
            prev = current
            series.append(current)
        return series

    @staticmethod
    def _build_rsi(closes: Sequence[Optional[float]], period: int) -> List[Optional[float]]:
        series: List[Optional[float]] = []
        gains: List[float] = []
        losses: List[float] = []
        avg_gain: Optional[float] = None
        avg_loss: Optional[float] = None
        prev_price: Optional[float] = None
        for price in closes:
            if price is None or prev_price is None:
                series.append(None)
                prev_price = price if price is not None else prev_price
                continue
            change = float(price) - float(prev_price)
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))
            if len(gains) < period:
                series.append(None)
            elif len(gains) == period:
                avg_gain = sum(gains[-period:]) / period
                avg_loss = sum(losses[-period:]) / period
                series.append(RuleBacktestEngine._rsi_from_avgs(avg_gain, avg_loss))
            else:
                avg_gain = ((avg_gain or 0.0) * (period - 1) + gains[-1]) / period
                avg_loss = ((avg_loss or 0.0) * (period - 1) + losses[-1]) / period
                series.append(RuleBacktestEngine._rsi_from_avgs(avg_gain, avg_loss))
            prev_price = float(price)
        return series

    @staticmethod
    def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> Optional[float]:
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _build_return_pct(closes: Sequence[Optional[float]], period: int) -> List[Optional[float]]:
        series: List[Optional[float]] = []
        for idx, price in enumerate(closes):
            if price is None or idx < period:
                series.append(None)
                continue
            prev = closes[idx - period]
            if prev is None or prev == 0:
                series.append(None)
                continue
            series.append((float(price) / float(prev) - 1.0) * 100.0)
        return series

    @staticmethod
    def _safe_price(value: Any) -> Optional[float]:
        price = _safe_float(value)
        if price is None or price <= 0:
            return None
        return price

    @staticmethod
    def _format_node(node: Dict[str, Any]) -> str:
        if not node:
            return "--"
        if node.get("type") == "group":
            joiner = " AND " if node.get("op") == "and" else " OR "
            parts = [RuleBacktestEngine._format_node(child) for child in node.get("rules", []) or []]
            if not parts:
                return "--"
            return "(" + joiner.join(parts) + ")" if len(parts) > 1 else parts[0]
        if node.get("type") == "comparison":
            return f"{RuleBacktestEngine._format_operand(node.get('left'))} {node.get('compare')} {RuleBacktestEngine._format_operand(node.get('right'))}"
        return "--"

    @staticmethod
    def _format_operand(operand: Optional[Dict[str, Any]]) -> str:
        if not operand:
            return "--"
        if operand.get("kind") == "value":
            value = _safe_float(operand.get("value"))
            return f"{value:g}" if value is not None else "--"
        indicator = operand.get("indicator")
        period = operand.get("period")
        if indicator == "close":
            return "Close"
        if indicator == "return_pct":
            return f"Return{period}" if period else "Return"
        if indicator and period is not None:
            return f"{str(indicator).upper()}{period}"
        return str(indicator or "--").upper()

    def _empty_metrics(
        self,
        initial_capital: float,
        lookback_bars: int,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        return {
            "initial_capital": float(initial_capital),
            "final_equity": float(initial_capital),
            "total_return_pct": 0.0,
            "annualized_return_pct": None,
            "benchmark_return_pct": None,
            "excess_return_vs_benchmark_pct": None,
            "buy_and_hold_return_pct": 0.0,
            "excess_return_vs_buy_and_hold_pct": 0.0,
            "trade_count": 0,
            "entry_signal_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate_pct": 0.0,
            "avg_trade_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_holding_days": 0.0,
            "avg_holding_bars": 0.0,
            "avg_holding_calendar_days": 0.0,
            "bars_used": 0,
            "lookback_bars": int(lookback_bars),
            "period_start": start_date.isoformat() if start_date is not None else None,
            "period_end": end_date.isoformat() if end_date is not None else None,
        }

    def _build_metrics(
        self,
        *,
        trades: List[RuleBacktestTrade],
        equity_curve: List[RuleBacktestPoint],
        initial_capital: float,
        trade_entry_signals: int,
        benchmark_metrics: Dict[str, Any],
        lookback_bars: int,
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> Dict[str, Any]:
        final_equity = equity_curve[-1].equity if equity_curve else initial_capital
        returns = [trade.return_pct for trade in trades]
        win_count = sum(1 for trade in trades if trade.return_pct > 0)
        loss_count = sum(1 for trade in trades if trade.return_pct < 0)
        max_drawdown = min((point.drawdown_pct for point in equity_curve), default=0.0)
        holding_bars = [trade.holding_bars for trade in trades]
        holding_calendar_days = [trade.holding_calendar_days for trade in trades]
        total_return_pct = round(((final_equity / initial_capital) - 1.0) * 100.0, 4) if initial_capital else 0.0
        buy_and_hold_return_pct = float(benchmark_metrics.get("buy_and_hold_return_pct") or 0.0)
        annualized_return_pct = self._calculate_annualized_return_pct(
            total_return_pct=total_return_pct,
            period_start=benchmark_metrics.get("period_start") or (start_date.isoformat() if start_date is not None else None),
            period_end=benchmark_metrics.get("period_end") or (end_date.isoformat() if end_date is not None else None),
        )
        metrics = {
            "initial_capital": float(initial_capital),
            "final_equity": round(float(final_equity), 6),
            "total_return_pct": total_return_pct,
            "annualized_return_pct": annualized_return_pct,
            "benchmark_return_pct": buy_and_hold_return_pct,
            "excess_return_vs_benchmark_pct": round(total_return_pct - buy_and_hold_return_pct, 4),
            "buy_and_hold_return_pct": buy_and_hold_return_pct,
            "excess_return_vs_buy_and_hold_pct": round(total_return_pct - buy_and_hold_return_pct, 4),
            "trade_count": len(trades),
            "entry_signal_count": trade_entry_signals,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate_pct": round((win_count / len(trades)) * 100.0, 4) if trades else 0.0,
            "avg_trade_return_pct": round(mean(returns), 4) if returns else 0.0,
            "max_drawdown_pct": round(abs(max_drawdown), 4) if equity_curve else 0.0,
            "avg_holding_days": round(mean(holding_bars), 4) if holding_bars else 0.0,
            "avg_holding_bars": round(mean(holding_bars), 4) if holding_bars else 0.0,
            "avg_holding_calendar_days": round(mean(holding_calendar_days), 4) if holding_calendar_days else 0.0,
            "bars_used": len(equity_curve),
            "lookback_bars": int(lookback_bars),
            "period_start": benchmark_metrics.get("period_start") or (start_date.isoformat() if start_date is not None else None),
            "period_end": benchmark_metrics.get("period_end") or (end_date.isoformat() if end_date is not None else None),
        }
        return metrics

    @staticmethod
    def _calculate_annualized_return_pct(
        *,
        total_return_pct: float,
        period_start: Optional[str],
        period_end: Optional[str],
    ) -> Optional[float]:
        if not period_start or not period_end:
            return None
        try:
            start_dt = date.fromisoformat(period_start)
            end_dt = date.fromisoformat(period_end)
        except ValueError:
            return None
        days = (end_dt - start_dt).days
        if days <= 30:
            return None
        total_return = 1.0 + (float(total_return_pct) / 100.0)
        if total_return <= 0:
            return None
        return round((math.pow(total_return, 365.0 / float(days)) - 1.0) * 100.0, 4)

    def _build_benchmark_metrics(self, bars: Sequence[Any]) -> Dict[str, Any]:
        if not bars:
            return {
                "buy_and_hold_return_pct": 0.0,
                "period_start": None,
                "period_end": None,
                "start_close": None,
                "end_close": None,
            }
        first_close = self._safe_price(getattr(bars[0], "close", None))
        last_close = self._safe_price(getattr(bars[-1], "close", None))
        if first_close is None or last_close is None or first_close <= 0:
            buy_and_hold_return = 0.0
        else:
            buy_and_hold_return = round(((last_close / first_close) - 1.0) * 100.0, 4)
        return {
            "buy_and_hold_return_pct": buy_and_hold_return,
            "period_start": getattr(bars[0], "date").isoformat() if getattr(bars[0], "date", None) else None,
            "period_end": getattr(bars[-1], "date").isoformat() if getattr(bars[-1], "date", None) else None,
            "start_close": round(float(first_close), 6) if first_close is not None else None,
            "end_close": round(float(last_close), 6) if last_close is not None else None,
        }

    def _build_benchmark_curve(self, bars: Sequence[Any]) -> List[Dict[str, Any]]:
        if not bars:
            return []
        first_close = self._safe_price(getattr(bars[0], "close", None))
        if first_close is None or first_close <= 0:
            return []
        curve: List[Dict[str, Any]] = []
        for bar in bars:
            close_price = self._safe_price(getattr(bar, "close", None))
            bar_date = getattr(bar, "date", None)
            if close_price is None or bar_date is None:
                continue
            normalized_value = close_price / first_close
            curve.append(
                {
                    "date": bar_date.isoformat(),
                    "close": round(float(close_price), 6),
                    "normalized_value": round(float(normalized_value), 6),
                    "cumulative_return_pct": round((float(normalized_value) - 1.0) * 100.0, 6),
                }
            )
        return curve

    def _build_benchmark_summary(self, benchmark_metrics: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "label": "当前标的买入并持有",
            "code": None,
            "method": "same_symbol_buy_and_hold",
            "requested_mode": "same_symbol_buy_and_hold",
            "resolved_mode": "same_symbol_buy_and_hold",
            "normalized_base": 1.0,
            "price_basis": "close",
            "start_date": benchmark_metrics.get("period_start"),
            "end_date": benchmark_metrics.get("period_end"),
            "start_price": benchmark_metrics.get("start_close"),
            "end_price": benchmark_metrics.get("end_close"),
            "return_pct": benchmark_metrics.get("buy_and_hold_return_pct"),
            "auto_resolved": False,
            "fallback_used": False,
            "unavailable_reason": None,
        }

    def _detect_no_result_reason(
        self,
        metrics: Dict[str, Any],
        parsed_strategy: ParsedStrategy,
    ) -> Tuple[Optional[str], Optional[str]]:
        if metrics.get("bars_used", 0) <= 0:
            return "insufficient_history", "没有可用于执行规则回测的历史数据。"
        if metrics.get("entry_signal_count", 0) <= 0:
            return "no_entry_signals", "回测窗口内没有触发任何入场信号。"
        if metrics.get("trade_count", 0) <= 0:
            return "no_trades", "规则被解析成功，但没有生成实际交易。"
        if parsed_strategy.needs_confirmation and parsed_strategy.confidence < 0.75:
            return "low_confidence_parse", "策略解析置信度偏低，建议先修正规则后再回测。"
        return None, None
