# -*- coding: utf-8 -*-
"""Deterministic rule backtesting engine for AI-assisted strategies."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuleBacktestTrade:
    code: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    entry_signal: str
    exit_signal: str
    return_pct: float
    holding_days: int
    entry_rule_json: Dict[str, Any]
    exit_rule_json: Dict[str, Any]
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat(),
            "entry_price": round(self.entry_price, 6),
            "exit_price": round(self.exit_price, 6),
            "entry_signal": self.entry_signal,
            "exit_signal": self.exit_signal,
            "return_pct": round(self.return_pct, 4),
            "holding_days": self.holding_days,
            "entry_rule": self.entry_rule_json,
            "exit_rule": self.exit_rule_json,
            "notes": self.notes,
        }


@dataclass
class RuleBacktestPoint:
    date: date
    equity: float
    cumulative_return_pct: float
    drawdown_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "equity": round(self.equity, 6),
            "cumulative_return_pct": round(self.cumulative_return_pct, 6),
            "drawdown_pct": round(self.drawdown_pct, 6),
        }


@dataclass
class RuleBacktestResult:
    parsed_strategy: ParsedStrategy
    trades: List[RuleBacktestTrade]
    equity_curve: List[RuleBacktestPoint]
    metrics: Dict[str, Any]
    no_result_reason: Optional[str] = None
    no_result_message: Optional[str] = None
    warnings: List[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parsed_strategy": self.parsed_strategy.to_dict(),
            "trades": [trade.to_dict() for trade in self.trades],
            "equity_curve": [point.to_dict() for point in self.equity_curve],
            "metrics": self.metrics,
            "no_result_reason": self.no_result_reason,
            "no_result_message": self.no_result_message,
            "warnings": self.warnings or [],
        }


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
        )

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
        lookback_bars: int = 252,
    ) -> RuleBacktestResult:
        ordered_bars = list(bars)
        if not ordered_bars:
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars),
                no_result_reason="insufficient_history",
                no_result_message="没有可用于回测的历史行情数据。",
                warnings=[],
            )

        closes = [self._safe_price(getattr(bar, "close", None)) for bar in ordered_bars]
        if any(price is None for price in closes):
            return RuleBacktestResult(
                parsed_strategy=parsed_strategy,
                trades=[],
                equity_curve=[],
                metrics=self._empty_metrics(initial_capital, lookback_bars),
                no_result_reason="invalid_price_data",
                no_result_message="历史行情存在缺失收盘价，无法执行规则回测。",
                warnings=[],
            )

        start_index = max(0, len(ordered_bars) - max(1, int(lookback_bars)))
        warmup_cache = self._build_indicator_cache(ordered_bars[:], parsed_strategy)
        trades: List[RuleBacktestTrade] = []
        equity_curve: List[RuleBacktestPoint] = []

        position = False
        shares = 0.0
        cash = float(initial_capital)
        entry_index = -1
        entry_date = None
        entry_price = None
        entry_rule = ""
        entry_node = parsed_strategy.entry
        exit_node = parsed_strategy.exit
        fee_rate = max(0.0, float(fee_bps)) / 10000.0
        peak_equity = float(initial_capital)
        trade_entry_signals = 0

        for idx, bar in enumerate(ordered_bars):
            price = closes[idx]
            if price is None:
                continue
            if idx < start_index:
                continue

            exit_signal = position and self._evaluate_node(exit_node, idx, ordered_bars, warmup_cache)
            entry_signal = (not position) and self._evaluate_node(entry_node, idx, ordered_bars, warmup_cache)
            exited_today = False

            if position and exit_signal:
                exit_price = price * (1.0 - fee_rate)
                cash = shares * exit_price
                holding_days = max(1, idx - entry_index + 1)
                trade_return = ((exit_price - entry_price) / entry_price * 100.0) if entry_price else 0.0
                trades.append(
                    RuleBacktestTrade(
                        code=code,
                        entry_date=entry_date,
                        exit_date=getattr(bar, "date"),
                        entry_price=float(entry_price),
                        exit_price=float(exit_price),
                        entry_signal=entry_rule,
                        exit_signal=self._format_node(exit_node),
                        return_pct=round(trade_return, 4),
                        holding_days=holding_days,
                        entry_rule_json=entry_node,
                        exit_rule_json=exit_node,
                        notes="exit_signal",
                    )
                )
                position = False
                shares = 0.0
                entry_index = -1
                entry_date = None
                entry_price = None
                entry_rule = ""
                exited_today = True

            if not position and entry_signal and not exited_today:
                entry_price = price * (1.0 + fee_rate)
                shares = cash / entry_price if entry_price else 0.0
                position = True
                entry_index = idx
                entry_date = getattr(bar, "date")
                entry_rule = self._format_node(entry_node)
                trade_entry_signals += 1

            equity = cash if not position else shares * price
            peak_equity = max(peak_equity, equity)
            drawdown_pct = 0.0 if peak_equity <= 0 else ((equity / peak_equity) - 1.0) * 100.0
            equity_curve.append(
                RuleBacktestPoint(
                    date=getattr(bar, "date"),
                    equity=float(equity),
                    cumulative_return_pct=((equity / float(initial_capital)) - 1.0) * 100.0 if initial_capital else 0.0,
                    drawdown_pct=float(drawdown_pct),
                )
            )

        if position and entry_date is not None and entry_price is not None:
            last_bar = ordered_bars[-1]
            last_price = closes[-1] or entry_price
            exit_price = last_price * (1.0 - fee_rate)
            cash = shares * exit_price
            holding_days = max(1, len(ordered_bars) - entry_index)
            trade_return = ((exit_price - entry_price) / entry_price * 100.0) if entry_price else 0.0
            trades.append(
                RuleBacktestTrade(
                    code=code,
                    entry_date=entry_date,
                    exit_date=getattr(last_bar, "date"),
                    entry_price=float(entry_price),
                    exit_price=float(exit_price),
                    entry_signal=entry_rule,
                    exit_signal="eod_close",
                    return_pct=round(trade_return, 4),
                    holding_days=holding_days,
                    entry_rule_json=entry_node,
                    exit_rule_json=exit_node,
                    notes="forced_close",
                )
            )
            equity_curve[-1] = RuleBacktestPoint(
                date=getattr(last_bar, "date"),
                equity=float(cash),
                cumulative_return_pct=((cash / float(initial_capital)) - 1.0) * 100.0 if initial_capital else 0.0,
                drawdown_pct=equity_curve[-1].drawdown_pct if equity_curve else 0.0,
            )

        metrics = self._build_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=float(initial_capital),
            trade_entry_signals=trade_entry_signals,
        )
        no_result_reason, no_result_message = self._detect_no_result_reason(metrics, parsed_strategy)
        return RuleBacktestResult(
            parsed_strategy=parsed_strategy,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            no_result_reason=no_result_reason,
            no_result_message=no_result_message,
            warnings=parsed_strategy.ambiguities,
        )

    def _build_indicator_cache(self, bars: Sequence[Any], parsed_strategy: ParsedStrategy) -> Dict[Tuple[str, int], List[Optional[float]]]:
        closes = [self._safe_price(getattr(bar, "close", None)) for bar in bars]
        requirements = self._collect_requirements(parsed_strategy.entry) | self._collect_requirements(parsed_strategy.exit)
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

    def _empty_metrics(self, initial_capital: float, lookback_bars: int) -> Dict[str, Any]:
        return {
            "initial_capital": float(initial_capital),
            "final_equity": float(initial_capital),
            "total_return_pct": 0.0,
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate_pct": 0.0,
            "avg_trade_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_holding_days": 0.0,
            "bars_used": 0,
            "lookback_bars": int(lookback_bars),
        }

    def _build_metrics(
        self,
        *,
        trades: List[RuleBacktestTrade],
        equity_curve: List[RuleBacktestPoint],
        initial_capital: float,
        trade_entry_signals: int,
    ) -> Dict[str, Any]:
        final_equity = equity_curve[-1].equity if equity_curve else initial_capital
        returns = [trade.return_pct for trade in trades]
        win_count = sum(1 for trade in trades if trade.return_pct > 0)
        loss_count = sum(1 for trade in trades if trade.return_pct < 0)
        max_drawdown = min((point.drawdown_pct for point in equity_curve), default=0.0)
        holding_days = [trade.holding_days for trade in trades]
        metrics = {
            "initial_capital": float(initial_capital),
            "final_equity": round(float(final_equity), 6),
            "total_return_pct": round(((final_equity / initial_capital) - 1.0) * 100.0, 4) if initial_capital else 0.0,
            "trade_count": len(trades),
            "entry_signal_count": trade_entry_signals,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate_pct": round((win_count / len(trades)) * 100.0, 4) if trades else 0.0,
            "avg_trade_return_pct": round(mean(returns), 4) if returns else 0.0,
            "max_drawdown_pct": round(abs(max_drawdown), 4) if equity_curve else 0.0,
            "avg_holding_days": round(mean(holding_days), 4) if holding_days else 0.0,
            "bars_used": len(equity_curve),
        }
        return metrics

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
