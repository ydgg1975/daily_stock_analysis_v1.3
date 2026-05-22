# -*- coding: utf-8 -*-
"""Candlestick chart image and metadata generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.services.alert_indicators import _calculate_rsi, normalize_ohlcv


@dataclass
class ChartRenderOptions:
    width: int = 960
    height: int = 640
    ma_windows: Tuple[int, ...] = (5, 20)
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9


class ChartAnalysisService:
    """Generate chart SVGs and machine-readable visual analysis metadata."""

    def analyze(
        self,
        stock_code: str,
        df: Any,
        *,
        options: Optional[ChartRenderOptions] = None,
    ) -> Dict[str, Any]:
        opts = options or ChartRenderOptions()
        normalized = self._normalize_chart_data(df)
        if normalized.empty:
            return {
                "status": "degraded",
                "stock_code": stock_code,
                "reason": "No OHLCV data available for chart rendering.",
                "image_format": "svg",
                "svg": "",
                "metadata": {},
            }

        indicators = self._build_indicators(normalized, opts)
        metadata = self._build_metadata(normalized, indicators)
        svg = self._render_svg(stock_code, normalized, indicators, metadata, opts)
        return {
            "status": "ok",
            "stock_code": stock_code,
            "image_format": "svg",
            "svg": svg,
            "metadata": metadata,
        }

    def _normalize_chart_data(self, df: Any) -> pd.DataFrame:
        normalized = normalize_ohlcv(df, required_columns=("high", "low", "close"))
        if normalized.empty:
            return normalized
        source = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        open_col = self._find_column(source, "open")
        volume_col = self._find_column(source, "volume")
        normalized["open"] = (
            pd.to_numeric(source[open_col], errors="coerce").reindex(normalized.index)
            if open_col else normalized["close"]
        )
        normalized["volume"] = (
            pd.to_numeric(source[volume_col], errors="coerce").reindex(normalized.index).fillna(0.0)
            if volume_col else 0.0
        )
        return normalized.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

    @staticmethod
    def _find_column(df: pd.DataFrame, canonical: str) -> Optional[str]:
        aliases = {
            "open": ("open", "open_price", "开盘", "開盤"),
            "volume": ("volume", "vol", "成交量"),
        }
        lower_map = {str(col).strip().lower(): col for col in getattr(df, "columns", [])}
        for alias in aliases.get(canonical, (canonical,)):
            key = alias.lower()
            if key in lower_map:
                return lower_map[key]
        return None

    def _build_indicators(self, df: pd.DataFrame, opts: ChartRenderOptions) -> Dict[str, Any]:
        close = df["close"]
        ma = {
            f"ma{window}": self._series_values(close.rolling(window=window).mean())
            for window in opts.ma_windows
        }
        rsi = _calculate_rsi(close, opts.rsi_period)
        ema_fast = close.ewm(span=opts.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=opts.macd_slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=opts.macd_signal, adjust=False).mean()
        hist = dif - dea
        return {
            "ma": ma,
            "rsi": self._series_values(rsi),
            "macd": {
                "dif": self._series_values(dif),
                "dea": self._series_values(dea),
                "histogram": self._series_values(hist),
            },
        }

    @staticmethod
    def _series_values(series: pd.Series) -> List[Optional[float]]:
        values: List[Optional[float]] = []
        for value in series:
            if pd.isna(value):
                values.append(None)
            else:
                values.append(round(float(value), 6))
        return values

    def _build_metadata(self, df: pd.DataFrame, indicators: Dict[str, Any]) -> Dict[str, Any]:
        latest_close = float(df["close"].iloc[-1])
        previous_close = float(df["close"].iloc[-2]) if len(df) >= 2 else latest_close
        support = float(df["low"].tail(min(len(df), 20)).min())
        resistance = float(df["high"].tail(min(len(df), 20)).max())
        pattern = self._detect_pattern(df)
        indicator_signal = self._indicator_signal(indicators)
        visual_signal = self._visual_signal(latest_close, previous_close, support, resistance, pattern)
        conflicts = []
        if indicator_signal != "neutral" and visual_signal != "neutral" and indicator_signal != visual_signal:
            conflicts.append(
                {
                    "type": "signal_conflict",
                    "visual_signal": visual_signal,
                    "indicator_signal": indicator_signal,
                    "message": "Chart structure and numeric indicators point in different directions.",
                }
            )
        return {
            "version": 1,
            "latest_close": round(latest_close, 6),
            "support": round(support, 6),
            "resistance": round(resistance, 6),
            "pattern": pattern,
            "visual_signal": visual_signal,
            "indicator_signal": indicator_signal,
            "conflicts": conflicts,
        }

    @staticmethod
    def _detect_pattern(df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < 5:
            return {"name": "insufficient_data", "confidence": 0.0}
        closes = [float(value) for value in df["close"].tail(5)]
        if closes[-1] > max(closes[:-1]):
            return {"name": "five_bar_breakout", "confidence": 0.72}
        if closes[-1] < min(closes[:-1]):
            return {"name": "five_bar_breakdown", "confidence": 0.72}
        if closes[-1] > closes[0] and closes[-2] > closes[1]:
            return {"name": "short_uptrend", "confidence": 0.58}
        if closes[-1] < closes[0] and closes[-2] < closes[1]:
            return {"name": "short_downtrend", "confidence": 0.58}
        return {"name": "range_bound", "confidence": 0.5}

    @staticmethod
    def _indicator_signal(indicators: Dict[str, Any]) -> str:
        rsi_values = [value for value in indicators.get("rsi", []) if value is not None]
        hist_values = [value for value in indicators.get("macd", {}).get("histogram", []) if value is not None]
        latest_rsi = float(rsi_values[-1]) if rsi_values else 50.0
        latest_hist = float(hist_values[-1]) if hist_values else 0.0
        if latest_rsi >= 70.0 and latest_hist > 0:
            return "bullish_overextended"
        if latest_rsi <= 30.0 and latest_hist < 0:
            return "bearish_oversold"
        if latest_hist > 0:
            return "bullish"
        if latest_hist < 0:
            return "bearish"
        return "neutral"

    @staticmethod
    def _visual_signal(
        latest_close: float,
        previous_close: float,
        support: float,
        resistance: float,
        pattern: Dict[str, Any],
    ) -> str:
        if pattern.get("name") == "five_bar_breakout" or latest_close >= resistance:
            return "bullish"
        if pattern.get("name") == "five_bar_breakdown" or latest_close <= support:
            return "bearish"
        if latest_close > previous_close:
            return "bullish"
        if latest_close < previous_close:
            return "bearish"
        return "neutral"

    def _render_svg(
        self,
        stock_code: str,
        df: pd.DataFrame,
        indicators: Dict[str, Any],
        metadata: Dict[str, Any],
        opts: ChartRenderOptions,
    ) -> str:
        width, height = opts.width, opts.height
        price_top, price_bottom = 48, int(height * 0.58)
        volume_top, volume_bottom = price_bottom + 24, int(height * 0.74)
        rsi_top, rsi_bottom = volume_bottom + 24, int(height * 0.86)
        macd_top, macd_bottom = rsi_bottom + 24, height - 36
        left, right = 56, width - 28
        plot_width = right - left
        count = len(df)
        candle_step = plot_width / max(count, 1)
        candle_width = max(3.0, min(12.0, candle_step * 0.55))

        price_min = float(df["low"].min())
        price_max = float(df["high"].max())
        volume_max = max(float(df["volume"].max()), 1.0)
        macd_values = [
            float(value)
            for key in ("dif", "dea", "histogram")
            for value in indicators["macd"].get(key, [])
            if value is not None
        ]
        macd_min = min(macd_values) if macd_values else -1.0
        macd_max = max(macd_values) if macd_values else 1.0
        if macd_min == macd_max:
            macd_min -= 1.0
            macd_max += 1.0

        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#fbfaf7"/>',
            f'<text x="{left}" y="28" fill="#1f2933" font-size="18" font-family="Arial">{self._escape(stock_code)} chart analysis</text>',
            self._panel(left, price_top, plot_width, price_bottom - price_top, "Price"),
            self._panel(left, volume_top, plot_width, volume_bottom - volume_top, "Volume"),
            self._panel(left, rsi_top, plot_width, rsi_bottom - rsi_top, "RSI"),
            self._panel(left, macd_top, plot_width, macd_bottom - macd_top, "MACD"),
        ]

        for idx, row in df.iterrows():
            x = left + candle_step * idx + candle_step / 2
            open_y = self._scale(float(row["open"]), price_min, price_max, price_bottom, price_top)
            close_y = self._scale(float(row["close"]), price_min, price_max, price_bottom, price_top)
            high_y = self._scale(float(row["high"]), price_min, price_max, price_bottom, price_top)
            low_y = self._scale(float(row["low"]), price_min, price_max, price_bottom, price_top)
            up = float(row["close"]) >= float(row["open"])
            color = "#247a50" if up else "#b42318"
            body_y = min(open_y, close_y)
            body_h = max(1.0, abs(close_y - open_y))
            parts.append(f'<line x1="{x:.2f}" y1="{high_y:.2f}" x2="{x:.2f}" y2="{low_y:.2f}" stroke="{color}" stroke-width="1.5"/>')
            parts.append(f'<rect x="{x - candle_width / 2:.2f}" y="{body_y:.2f}" width="{candle_width:.2f}" height="{body_h:.2f}" fill="{color}" opacity="0.88"/>')
            vol_y = self._scale(float(row["volume"]), 0.0, volume_max, volume_bottom, volume_top)
            parts.append(f'<rect x="{x - candle_width / 2:.2f}" y="{vol_y:.2f}" width="{candle_width:.2f}" height="{volume_bottom - vol_y:.2f}" fill="#6b7280" opacity="0.35"/>')

        colors = ["#2563eb", "#f59e0b", "#7c3aed"]
        for color, values in zip(colors, indicators["ma"].values()):
            parts.append(self._polyline(values, left, candle_step, price_min, price_max, price_bottom, price_top, color))
        parts.append(self._polyline(indicators["rsi"], left, candle_step, 0.0, 100.0, rsi_bottom, rsi_top, "#0f766e"))
        parts.append(self._polyline(indicators["macd"]["dif"], left, candle_step, macd_min, macd_max, macd_bottom, macd_top, "#2563eb"))
        parts.append(self._polyline(indicators["macd"]["dea"], left, candle_step, macd_min, macd_max, macd_bottom, macd_top, "#f97316"))

        support_y = self._scale(float(metadata["support"]), price_min, price_max, price_bottom, price_top)
        resistance_y = self._scale(float(metadata["resistance"]), price_min, price_max, price_bottom, price_top)
        parts.append(f'<line x1="{left}" y1="{support_y:.2f}" x2="{right}" y2="{support_y:.2f}" stroke="#16a34a" stroke-dasharray="5 4"/>')
        parts.append(f'<line x1="{left}" y1="{resistance_y:.2f}" x2="{right}" y2="{resistance_y:.2f}" stroke="#dc2626" stroke-dasharray="5 4"/>')
        parts.append(f'<text x="{left}" y="{height - 10}" fill="#4b5563" font-size="12" font-family="Arial">pattern={self._escape(metadata["pattern"]["name"])} visual={metadata["visual_signal"]} indicator={metadata["indicator_signal"]}</text>')
        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _panel(x: int, y: int, width: int, height: int, label: str) -> str:
        return (
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="#ffffff" stroke="#d0d7de"/>'
            f'<text x="{x + 6}" y="{y + 16}" fill="#667085" font-size="12" font-family="Arial">{label}</text>'
        )

    @staticmethod
    def _scale(value: float, source_min: float, source_max: float, target_min: float, target_max: float) -> float:
        if source_max == source_min:
            return (target_min + target_max) / 2.0
        ratio = (value - source_min) / (source_max - source_min)
        return target_min + (target_max - target_min) * ratio

    def _polyline(
        self,
        values: List[Any],
        left: int,
        step: float,
        source_min: float,
        source_max: float,
        target_min: float,
        target_max: float,
        color: str,
    ) -> str:
        points = []
        for idx, value in enumerate(values):
            if value is None:
                continue
            x = left + step * idx + step / 2
            y = self._scale(float(value), source_min, source_max, target_min, target_max)
            points.append(f"{x:.2f},{y:.2f}")
        if len(points) < 2:
            return ""
        return f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="1.6"/>'

    @staticmethod
    def _escape(value: Any) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
