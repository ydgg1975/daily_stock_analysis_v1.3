# -*- coding: utf-8 -*-
"""
===================================
History Query Service Layer
===================================

Responsibilities:
1. Encapsulate history record query logic
2. Provide pagination and filtering functionality
3. Generate detailed reports in Markdown format
"""
from __future__ import annotations
import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, TYPE_CHECKING

from src.config import get_config, resolve_news_window_days
from src.repositories.analysis_repo import AnalysisRepository
from src.services import report_renderer
from src.report_language import (
    get_bias_status_emoji,
    get_localized_stock_name,
    get_report_labels,
    get_signal_level,
    localize_bias_status,
    localize_chip_health,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from data_provider.us_index_mapping import is_us_stock_code
from src.storage import DatabaseManager
from src.utils.data_processing import normalize_model_used, parse_json_field

if TYPE_CHECKING:
    from src.analyzer import AnalysisResult

logger = logging.getLogger(__name__)


class MarkdownReportGenerationError(Exception):
    """Exception raised when Markdown report generation fails due to internal errors."""

    def __init__(self, message: str, record_id: str = None):
        self.message = message
        self.record_id = record_id
        super().__init__(self.message)


class HistoryService:
    """
    History Query Service
    
    Encapsulates query logic for historical analysis records.
    """
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ):
        """
        Initialize the history query service.
        
        Args:
            db_manager: Database manager (optional, defaults to singleton instance)
        """
        self.db = db_manager or DatabaseManager.get_instance()
        self.repo = AnalysisRepository(
            self.db,
            owner_id=owner_id,
            include_all_owners=include_all_owners,
        )
        self.owner_id = owner_id
        self.include_all_owners = bool(include_all_owners)
    
    def get_history_list(
        self,
        stock_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get history analysis list.
        
        Args:
            stock_code: Stock code filter
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            page: Page number
            limit: Items per page
            
        Returns:
            Dictionary containing total count and items
        """
        try:
            # Parse date parameters
            start_dt = None
            end_dt = None
            
            if start_date:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
                except ValueError:
                    logger.warning(f"无效的 start_date 格式: {start_date}")
            
            if end_date:
                try:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
                except ValueError:
                    logger.warning(f"无效的 end_date 格式: {end_date}")
            
            # Calculate offset
            offset = (page - 1) * limit
            
            # Use new paginated query method
            records, total = self.repo.get_paginated(
                code=stock_code,
                start_date=start_dt,
                end_date=end_dt,
                offset=offset,
                limit=limit,
            )
            
            # Convert to response format
            items = []
            for record in records:
                items.append({
                    "id": record.id,
                    "query_id": record.query_id,
                    "stock_code": record.code,
                    "stock_name": record.name,
                    "report_type": record.report_type,
                    "sentiment_score": record.sentiment_score,
                    "operation_advice": record.operation_advice,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                })
            
            return {
                "total": total,
                "items": items,
            }
            
        except Exception as e:
            logger.error(f"查询历史列表失败: {e}", exc_info=True)
            return {"total": 0, "items": []}

    def _resolve_record(self, record_id: str):
        """
        Resolve a record_id parameter to an AnalysisHistory object.

        Tries integer primary key first; falls back to query_id string lookup
        when the value is not a valid integer.

        Args:
            record_id: integer PK (as string) or query_id string

        Returns:
            AnalysisHistory object or None
        """
        try:
            int_id = int(record_id)
            record = self.repo.get_by_id(int_id)
            if record:
                return record
        except (ValueError, TypeError):
            pass
        # Fall back to query_id lookup
        return self.repo.get_latest_record(query_id=record_id)

    def resolve_and_get_detail(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Resolve record_id (int PK or query_id string) and return history detail.

        Args:
            record_id: integer PK (as string) or query_id string

        Returns:
            Complete analysis report dict, or None
        """
        try:
            record = self._resolve_record(record_id)
            if not record:
                return None
            return self._record_to_detail_dict(record)
        except Exception as e:
            logger.error(f"resolve_and_get_detail failed for {record_id}: {e}", exc_info=True)
            return None

    def resolve_and_get_news(self, record_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Resolve record_id (int PK or query_id string) and return associated news.

        Args:
            record_id: integer PK (as string) or query_id string
            limit: max items to return

        Returns:
            List of news intel dicts
        """
        try:
            record = self._resolve_record(record_id)
            if not record:
                logger.warning(f"resolve_and_get_news: record not found for {record_id}")
                return []
            return self.get_news_intel(query_id=record.query_id, limit=limit)
        except Exception as e:
            logger.error(f"resolve_and_get_news failed for {record_id}: {e}", exc_info=True)
            return []

    def get_history_detail_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        Get history report detail.

        Uses database primary key for precise query, avoiding returning incorrect records 
        due to duplicate query_id in batch analysis.

        Args:
            record_id: Analysis history record primary key ID

        Returns:
            Complete analysis report dictionary, or None if not exists
        """
        try:
            record = self.repo.get_by_id(record_id)
            if not record:
                return None
            return self._record_to_detail_dict(record)
        except Exception as e:
            logger.error(f"根据 ID 查询历史详情失败: {e}", exc_info=True)
            return None

    @staticmethod
    def _normalize_display_sniper_value(value: Any) -> Optional[str]:
        """Normalize sniper point values for history display."""
        if value is None:
            return None
        text = str(value).strip()
        if not text or text in {"-", "—", "N/A"}:
            return None
        return text

    def _get_display_sniper_points(self, record, raw_result: Any) -> Dict[str, Optional[str]]:
        """Prefer raw dashboard sniper strings for history display, then fall back to numeric DB columns."""
        raw_points: Dict[str, Any] = {}
        if isinstance(raw_result, dict):
            for candidate in (raw_result.get("dashboard"), raw_result):
                if not isinstance(candidate, dict):
                    continue
                raw_points = DatabaseManager._find_sniper_in_dashboard(candidate) or raw_points
                if any(raw_points.get(k) is not None for k in ("ideal_buy", "secondary_buy", "stop_loss", "take_profit")):
                    break

        display_points: Dict[str, Optional[str]] = {}
        for field in ("ideal_buy", "secondary_buy", "stop_loss", "take_profit"):
            raw_value = self._normalize_display_sniper_value(raw_points.get(field))
            if raw_value is not None:
                display_points[field] = raw_value
                continue
            db_value = getattr(record, field, None)
            display_points[field] = str(db_value) if db_value is not None else None
        return display_points

    @staticmethod
    def _parse_context_snapshot(context_snapshot: Any) -> Any:
        return parse_json_field(context_snapshot)

    @staticmethod
    def _is_context_missing(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            text = value.strip()
            return text in {"", "N/A", "NA", "None", "null", "数据缺失", "-", "--"} or text.startswith("NA（")
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) == 0
        return False

    @classmethod
    def _is_placeholder_zero(cls, key: str, value: Any, zero_missing_keys: Optional[set[str]] = None) -> bool:
        if key not in (zero_missing_keys or set()):
            return False
        if value is None:
            return True
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return True
            try:
                return float(text.rstrip("%")) == 0.0
            except (TypeError, ValueError):
                return False
        if isinstance(value, (int, float)):
            return float(value) == 0.0
        return False

    @classmethod
    def _merge_missing_dict(
        cls,
        base: Any,
        supplement: Any,
        *,
        zero_missing_keys: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        result = dict(base) if isinstance(base, dict) else {}
        if not isinstance(supplement, dict):
            return result
        for key, value in supplement.items():
            current = result.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                result[key] = cls._merge_missing_dict(
                    current,
                    value,
                    zero_missing_keys=zero_missing_keys,
                )
                continue
            if (
                key not in result
                or cls._is_context_missing(current)
                or cls._is_placeholder_zero(key, current, zero_missing_keys)
            ):
                result[key] = value
        return result

    @classmethod
    def _first_present(cls, *values: Any) -> Any:
        for value in values:
            if not cls._is_context_missing(value):
                return value
        return None

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        text = str(value).strip()
        if not text or text.startswith("NA（"):
            return None
        try:
            return float(text.rstrip("%").replace(",", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _has_meaningful_change(value: Optional[float], *, tolerance: float = 0.005) -> bool:
        return value is not None and abs(value) > tolerance

    @classmethod
    def _derive_prev_close(
        cls,
        close: Any,
        *,
        change_amount: Any = None,
        change_pct: Any = None,
    ) -> Optional[float]:
        close_value = cls._to_float(close)
        if close_value is None:
            return None
        change_amount_value = cls._to_float(change_amount)
        change_pct_value = cls._to_float(change_pct)
        if change_amount_value is not None and (
            abs(change_amount_value) > 0.005 or not cls._has_meaningful_change(change_pct_value)
        ):
            derived = close_value - change_amount_value
            if derived > 0:
                return derived
        if change_pct_value is not None:
            denominator = 1 + (change_pct_value / 100.0)
            if abs(denominator) > 1e-9:
                derived = close_value / denominator
                if derived > 0:
                    return derived
        return None

    @classmethod
    def _repair_market_snapshot_price_basis(
        cls,
        payload: Dict[str, Any],
        *,
        preferred_prev_close: Any = None,
    ) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}

        repaired = dict(payload)
        close = cls._to_float(repaired.get("close"))
        prev_close = cls._to_float(repaired.get("prev_close"))
        change_amount = cls._to_float(repaired.get("change_amount"))
        change_pct = cls._to_float(repaired.get("pct_chg"))
        if change_pct is None:
            change_pct = cls._to_float(repaired.get("change_pct"))

        preferred_prev_close_value = cls._to_float(preferred_prev_close)
        derived_prev_close = preferred_prev_close_value or cls._derive_prev_close(
            close,
            change_amount=change_amount,
            change_pct=change_pct,
        )
        suspicious_flat = (
            close is not None
            and prev_close is not None
            and abs(close - prev_close) <= 0.01
            and (
                cls._has_meaningful_change(change_amount)
                or cls._has_meaningful_change(change_pct)
                or (
                    preferred_prev_close_value is not None
                    and abs(preferred_prev_close_value - prev_close) > 0.05
                )
            )
        )

        if derived_prev_close is not None and (prev_close is None or suspicious_flat):
            prev_close = derived_prev_close
            repaired["prev_close"] = round(derived_prev_close, 4)

        if close is not None and prev_close not in (None, 0):
            recalculated_change = close - prev_close
            recalculated_pct = (recalculated_change / prev_close) * 100
            if (
                repaired.get("change_amount") is None
                or suspicious_flat
                or abs((change_amount or 0.0) - recalculated_change) > 0.05
            ):
                repaired["change_amount"] = round(recalculated_change, 2)
            if (
                repaired.get("pct_chg") is None
                or suspicious_flat
                or change_pct is None
                or abs(change_pct - recalculated_pct) > 0.05
            ):
                repaired["pct_chg"] = round(recalculated_pct, 2)
            if "change_pct" in repaired or change_pct is not None:
                repaired["change_pct"] = round(recalculated_pct, 2)

        return repaired

    @classmethod
    def _extract_time_contract(cls, context_snapshot: Any) -> Dict[str, Any]:
        snapshot_obj = cls._parse_context_snapshot(context_snapshot)
        enhanced = snapshot_obj.get("enhanced_context") if isinstance(snapshot_obj, dict) else {}
        if not isinstance(enhanced, dict):
            return {}
        market_timestamp = enhanced.get("market_timestamp")
        market_session_date = enhanced.get("market_session_date")
        if market_timestamp:
            try:
                derived = datetime.fromisoformat(str(market_timestamp).replace("Z", "+00:00")).date().isoformat()
                market_session_date = derived
            except ValueError:
                pass
        return {
            "market_timestamp": market_timestamp,
            "market_session_date": market_session_date,
            "news_published_at": enhanced.get("news_published_at"),
            "report_generated_at": enhanced.get("report_generated_at"),
            "session_type": enhanced.get("session_type"),
        }

    @classmethod
    def _merge_market_snapshot_from_context(
        cls,
        market_snapshot: Any,
        context_snapshot: Any,
    ) -> Dict[str, Any]:
        base = dict(market_snapshot) if isinstance(market_snapshot, dict) else {}
        snapshot_obj = cls._parse_context_snapshot(context_snapshot)
        if not isinstance(snapshot_obj, dict):
            return base

        enhanced = snapshot_obj.get("enhanced_context")
        if not isinstance(enhanced, dict):
            return base

        today = enhanced.get("today") if isinstance(enhanced.get("today"), dict) else {}
        yesterday = enhanced.get("yesterday") if isinstance(enhanced.get("yesterday"), dict) else {}
        realtime = enhanced.get("realtime") if isinstance(enhanced.get("realtime"), dict) else {}
        realtime_raw = snapshot_obj.get("realtime_quote_raw") if isinstance(snapshot_obj.get("realtime_quote_raw"), dict) else {}

        prev_close = cls._first_present(
            yesterday.get("close"),
            realtime.get("pre_close"),
            realtime_raw.get("pre_close"),
            realtime_raw.get("previousClose"),
            realtime_raw.get("regularMarketPreviousClose"),
        )
        high = cls._first_present(today.get("high"), realtime.get("high"), realtime_raw.get("high"))
        low = cls._first_present(today.get("low"), realtime.get("low"), realtime_raw.get("low"))
        close = cls._first_present(
            today.get("close"),
            realtime_raw.get("regularMarketPrice"),
            realtime.get("price"),
            realtime_raw.get("price"),
        )
        change_amount = None
        amplitude = None
        try:
            if close is not None and prev_close not in (None, 0, "0", "0.0"):
                change_amount = float(close) - float(prev_close)
        except (TypeError, ValueError):
            change_amount = None
        try:
            if high is not None and low is not None and prev_close not in (None, 0, "0", "0.0"):
                amplitude = (float(high) - float(low)) / float(prev_close) * 100
        except (TypeError, ValueError, ZeroDivisionError):
            amplitude = None

        supplement = {
            "date": enhanced.get("date"),
            "close": close,
            "open": cls._first_present(today.get("open"), realtime.get("open_price"), realtime_raw.get("open")),
            "high": high,
            "low": low,
            "prev_close": prev_close,
            "pct_chg": cls._first_present(
                today.get("pct_chg"),
                realtime.get("change_pct"),
                realtime_raw.get("change_pct"),
                realtime_raw.get("pct_chg"),
            ),
            "change_amount": cls._first_present(
                realtime.get("change_amount"),
                realtime_raw.get("change_amount"),
                change_amount,
            ),
            "amplitude": cls._first_present(
                realtime.get("amplitude"),
                realtime_raw.get("amplitude"),
                amplitude,
            ),
            "volume": cls._first_present(today.get("volume"), realtime.get("volume"), realtime_raw.get("volume")),
            "amount": cls._first_present(today.get("amount"), realtime.get("amount"), realtime_raw.get("amount")),
            "price": cls._first_present(realtime.get("price"), realtime_raw.get("price")),
            "volume_ratio": cls._first_present(realtime.get("volume_ratio"), realtime_raw.get("volume_ratio")),
            "turnover_rate": cls._first_present(realtime.get("turnover_rate"), realtime_raw.get("turnover_rate")),
            "source": cls._first_present(
                today.get("data_source"),
                yesterday.get("data_source"),
                realtime.get("source"),
                realtime_raw.get("source"),
            ),
            "session_type": cls._first_present(enhanced.get("session_type"), realtime.get("snapshot_type")),
            "market_timestamp": cls._first_present(enhanced.get("market_timestamp"), realtime.get("market_timestamp")),
            "pre_market_price": cls._first_present(realtime_raw.get("pre_market_price"), realtime_raw.get("preMarketPrice")),
            "after_hours_price": cls._first_present(
                realtime_raw.get("after_hours_price"),
                realtime_raw.get("postMarketPrice"),
                realtime_raw.get("afterHoursPrice"),
            ),
            "extended_price": cls._first_present(
                realtime_raw.get("extended_price"),
                realtime_raw.get("postMarketPrice"),
                realtime_raw.get("preMarketPrice"),
            ),
            "extended_timestamp": cls._first_present(
                realtime_raw.get("extended_timestamp"),
                realtime_raw.get("postMarketTime"),
                realtime_raw.get("preMarketTime"),
            ),
            "pb_ratio": cls._first_present(realtime.get("pb_ratio"), realtime_raw.get("pb_ratio")),
            "total_mv": cls._first_present(realtime.get("total_mv"), realtime_raw.get("total_mv")),
            "circ_mv": cls._first_present(realtime.get("circ_mv"), realtime_raw.get("circ_mv")),
            "high_52w": cls._first_present(realtime.get("high_52w"), realtime_raw.get("high_52w")),
            "low_52w": cls._first_present(realtime.get("low_52w"), realtime_raw.get("low_52w")),
        }
        if supplement.get("session_type") == "last_completed_session" and supplement.get("close") is not None:
            supplement["price"] = supplement.get("close")
        supplement = cls._repair_market_snapshot_price_basis(supplement)
        merged = cls._merge_missing_dict(
            base,
            supplement,
            zero_missing_keys={
                "price",
                "close",
                "open",
                "high",
                "low",
                "prev_close",
                "volume",
                "amount",
                "volume_ratio",
                "turnover_rate",
                "pb_ratio",
                "total_mv",
                "circ_mv",
                "high_52w",
                "low_52w",
            },
        )
        return cls._repair_market_snapshot_price_basis(
            merged,
            preferred_prev_close=supplement.get("prev_close"),
        )

    @classmethod
    def _merge_dashboard_from_context(
        cls,
        dashboard: Any,
        context_snapshot: Any,
    ) -> Dict[str, Any]:
        base = dict(dashboard) if isinstance(dashboard, dict) else {}
        snapshot_obj = cls._parse_context_snapshot(context_snapshot)
        if not isinstance(snapshot_obj, dict):
            return base

        enhanced = snapshot_obj.get("enhanced_context")
        if not isinstance(enhanced, dict):
            return base

        structured = base.get("structured_analysis") if isinstance(base.get("structured_analysis"), dict) else {}
        structured = cls._merge_missing_dict(
            structured,
            {
                "time_context": {
                    "market_timestamp": enhanced.get("market_timestamp"),
                    "market_session_date": enhanced.get("market_session_date"),
                    "report_generated_at": enhanced.get("report_generated_at"),
                    "news_published_at": enhanced.get("news_published_at"),
                    "session_type": enhanced.get("session_type"),
                    "market_timezone": enhanced.get("market_timezone"),
                },
                "technicals": enhanced.get("technicals", {}),
                "trend_analysis": enhanced.get("trend_analysis", {}),
                "fundamentals": enhanced.get("fundamentals", {}),
                "earnings_analysis": enhanced.get("earnings_analysis", {}),
                "sentiment_analysis": enhanced.get("sentiment_analysis", {}),
                "data_quality": enhanced.get("data_quality", {}),
                "realtime_context": enhanced.get("realtime", {}),
                "market_context": {
                    "today": enhanced.get("today", {}),
                    "yesterday": enhanced.get("yesterday", {}),
                },
                "fundamental_context": enhanced.get("fundamental_context", {}),
            },
            zero_missing_keys={
                "price",
                "volume",
                "amount",
                "volume_ratio",
                "turnover_rate",
                "ma5",
                "ma10",
                "ma20",
                "ma60",
                "vwap",
                "trend_score",
                "trend_strength",
                "signal_score",
                "marketCap",
                "sharesOutstanding",
                "floatShares",
                "total_mv",
                "circ_mv",
                "pb_ratio",
            },
        )
        base["structured_analysis"] = structured

        data_persp = base.get("data_perspective") if isinstance(base.get("data_perspective"), dict) else {}
        technicals = enhanced.get("technicals") if isinstance(enhanced.get("technicals"), dict) else {}
        today = enhanced.get("today") if isinstance(enhanced.get("today"), dict) else {}
        realtime = enhanced.get("realtime") if isinstance(enhanced.get("realtime"), dict) else {}
        trend_analysis = enhanced.get("trend_analysis") if isinstance(enhanced.get("trend_analysis"), dict) else {}
        trend_status = data_persp.get("trend_status") if isinstance(data_persp.get("trend_status"), dict) else {}
        inferred_bullish = None
        trend_status_text = str(trend_analysis.get("trend_status") or "").strip().lower()
        if trend_status_text:
            if "bull" in trend_status_text:
                inferred_bullish = True
            elif "bear" in trend_status_text:
                inferred_bullish = False
        trend_status = cls._merge_missing_dict(
            trend_status,
            {
                "is_bullish": inferred_bullish,
                "trend_score": trend_analysis.get("trend_strength"),
                "signal_score": trend_analysis.get("signal_score"),
                "ma_alignment": trend_analysis.get("ma_alignment"),
            },
            zero_missing_keys={"trend_score", "signal_score"},
        )
        price_position = data_persp.get("price_position") if isinstance(data_persp.get("price_position"), dict) else {}
        price_position = cls._merge_missing_dict(
            price_position,
            {
                "current_price": realtime.get("price") or today.get("close"),
                "ma5": today.get("ma5") or ((technicals.get("ma5") or {}).get("value") if isinstance(technicals.get("ma5"), dict) else None),
                "ma10": today.get("ma10") or ((technicals.get("ma10") or {}).get("value") if isinstance(technicals.get("ma10"), dict) else None),
                "ma20": today.get("ma20") or ((technicals.get("ma20") or {}).get("value") if isinstance(technicals.get("ma20"), dict) else None),
                "ma60": ((technicals.get("ma60") or {}).get("value") if isinstance(technicals.get("ma60"), dict) else None),
                "bias_ma5": trend_analysis.get("bias_ma5"),
            },
            zero_missing_keys={"current_price", "ma5", "ma10", "ma20", "ma60", "vwap"},
        )
        volume_analysis = data_persp.get("volume_analysis") if isinstance(data_persp.get("volume_analysis"), dict) else {}
        volume_analysis = cls._merge_missing_dict(
            volume_analysis,
            {
                "volume_ratio": realtime.get("volume_ratio"),
                "turnover_rate": realtime.get("turnover_rate"),
                "volume_status": trend_analysis.get("volume_status"),
                "volume_meaning": realtime.get("volume_ratio_desc"),
            },
            zero_missing_keys={"volume_ratio", "turnover_rate"},
        )
        data_persp["trend_status"] = trend_status
        data_persp["price_position"] = price_position
        data_persp["volume_analysis"] = volume_analysis
        base["data_perspective"] = data_persp

        intel = base.get("intelligence") if isinstance(base.get("intelligence"), dict) else {}
        sentiment = enhanced.get("sentiment_analysis") if isinstance(enhanced.get("sentiment_analysis"), dict) else {}
        if isinstance(sentiment, dict):
            intel = cls._merge_missing_dict(
                intel,
                {
                    "sentiment_summary": sentiment.get("sentiment_summary"),
                    "company_sentiment": sentiment.get("company_sentiment"),
                    "industry_sentiment": sentiment.get("industry_sentiment"),
                    "regulatory_sentiment": sentiment.get("regulatory_sentiment"),
                    "overall_confidence": sentiment.get("overall_confidence"),
                },
            )
        base["intelligence"] = intel
        return base

    def _record_to_detail_dict(self, record) -> Dict[str, Any]:
        """
        Convert an AnalysisHistory ORM record to a detail response dict.
        """
        raw_result = parse_json_field(record.raw_result)
        context_snapshot = self._parse_context_snapshot(record.context_snapshot)
        standard_report = None
        if isinstance(raw_result, dict):
            rebuilt = self._rebuild_analysis_result(raw_result, record, context_snapshot=context_snapshot)
            if rebuilt is not None:
                report_language = normalize_report_language(
                    raw_result.get("report_language")
                    or getattr(rebuilt, "report_language", None)
                )
                standard_report = report_renderer.build_standard_report_payload(
                    rebuilt,
                    report_language=report_language,
                )

        model_used = (raw_result or {}).get("model_used") if isinstance(raw_result, dict) else None
        model_used = normalize_model_used(model_used)
        sniper_points = self._get_display_sniper_points(record, raw_result)
        time_contract = self._extract_time_contract(context_snapshot)

        return {
            "id": record.id,
            "query_id": record.query_id,
            "stock_code": record.code,
            "stock_name": record.name,
            "report_type": record.report_type,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "model_used": model_used,
            "analysis_summary": record.analysis_summary,
            "operation_advice": record.operation_advice,
            "trend_prediction": record.trend_prediction,
            "sentiment_score": record.sentiment_score,
            "sentiment_label": self._get_sentiment_label(record.sentiment_score or 50),
            "ideal_buy": sniper_points.get("ideal_buy"),
            "secondary_buy": sniper_points.get("secondary_buy"),
            "stop_loss": sniper_points.get("stop_loss"),
            "take_profit": sniper_points.get("take_profit"),
            "news_content": record.news_content,
            "raw_result": raw_result,
            "context_snapshot": context_snapshot,
            "standard_report": standard_report,
            "market_timestamp": time_contract.get("market_timestamp"),
            "market_session_date": time_contract.get("market_session_date"),
            "news_published_at": time_contract.get("news_published_at"),
            "report_generated_at": time_contract.get("report_generated_at"),
            "session_type": time_contract.get("session_type"),
        }

    def delete_history_records(self, record_ids: List[int]) -> int:
        """
        Delete specified analysis history records.

        Args:
            record_ids: List of history record primary key IDs

        Returns:
            Number of records actually deleted

        Raises:
            Exception: Re-raises any storage-layer exception so the API caller
                       receives a proper 500 error instead of a silent success.
        """
        return self.repo.delete_records(record_ids)

    def get_news_intel(self, query_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Get news intelligence associated with a specified query_id.

        Args:
            query_id: Unique analysis identifier
            limit: Result limit

        Returns:
            List of news intelligence (containing title, snippet, and url)
        """
        try:
            records = self.repo.get_news_intel_by_query_id(query_id=query_id, limit=limit)

            if not records:
                records = self._fallback_news_by_analysis_context(query_id=query_id, limit=limit)

            items: List[Dict[str, str]] = []
            for record in records:
                snippet = (record.snippet or "").strip()
                if len(snippet) > 200:
                    snippet = f"{snippet[:197]}..."
                items.append({
                    "title": record.title,
                    "snippet": snippet,
                    "url": record.url,
                })

            return items

        except Exception as e:
            logger.error(f"查询新闻情报失败: {e}", exc_info=True)
            return []

    def get_news_intel_by_record_id(self, record_id: int, limit: int = 20) -> List[Dict[str, str]]:
        """
        Get associated news intelligence based on analysis history record ID.

        Parses record_id to query_id, then calls get_news_intel.

        Args:
            record_id: Analysis history primary key ID
            limit: Result limit

        Returns:
            List of news intelligence (containing title, snippet, and url)
        """
        try:
            # Look up the corresponding AnalysisHistory record by record_id
            record = self.repo.get_by_id(record_id)
            if not record:
                logger.warning(f"No analysis record found for record_id={record_id}")
                return []

            # Get query_id from record, then call original method
            return self.get_news_intel(query_id=record.query_id, limit=limit)

        except Exception as e:
            logger.error(f"根据 record_id 查询新闻情报失败: {e}", exc_info=True)
            return []

    def _fallback_news_by_analysis_context(self, query_id: str, limit: int) -> List[Any]:
        """
        Fallback by analysis context when direct query_id lookup returns no news.

        Typical scenarios:
        - URL-level dedup keeps one canonical news row across repeated analyses.
        - Legacy records may have different historical query_id strategies.
        """
        analysis = self.repo.get_latest_record(query_id=query_id)
        if not analysis:
            return []
        if not analysis.code or not analysis.created_at:
            return []

        # Narrow down to same-stock recent news, then filter by analysis time window.
        days = max(1, (datetime.now() - analysis.created_at).days + 1)
        candidates = self.repo.get_recent_news(
            code=analysis.code,
            days=days,
            limit=max(limit * 5, 50),
        )

        start_time = analysis.created_at - timedelta(hours=6)
        end_time = analysis.created_at + timedelta(hours=6)
        matched = [
            item for item in candidates
            if item.fetched_at and start_time <= item.fetched_at <= end_time
        ]

        # 历史兜底链路也做发布时间硬过滤，避免旧库脏数据重新冒出。
        cfg = get_config()
        window_days = resolve_news_window_days(
            news_max_age_days=getattr(cfg, "news_max_age_days", 3),
            news_strategy_profile=getattr(cfg, "news_strategy_profile", "short"),
        )
        # Anchor to analysis date instead of "today" to preserve historical context.
        anchor_date = analysis.created_at.date()
        latest_allowed = anchor_date + timedelta(days=1)
        earliest_allowed = anchor_date - timedelta(days=max(0, window_days - 1))

        filtered = []
        for item in matched:
            if not item.published_date:
                continue
            if isinstance(item.published_date, datetime):
                published = item.published_date.date()
            elif isinstance(item.published_date, date):
                published = item.published_date
            else:
                continue
            if earliest_allowed <= published <= latest_allowed:
                filtered.append(item)

        return filtered[:limit]

    def get_latest_fundamental_snapshot(
        self,
        *,
        query_id: str,
        code: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the fallback fundamental payload for a history detail request."""
        return self.repo.get_latest_fundamental_snapshot(query_id=query_id, code=code)
    
    def _get_sentiment_label(self, score: int) -> str:
        """
        Get sentiment label based on score.

        Args:
            score: Sentiment score (0-100)

        Returns:
            Sentiment label
        """
        if score >= 80:
            return "极度乐观"
        elif score >= 60:
            return "乐观"
        elif score >= 40:
            return "中性"
        elif score >= 20:
            return "悲观"
        else:
            return "极度悲观"

    def get_markdown_report(self, record_id: str) -> Optional[str]:
        """
        Generate a Markdown report for a single analysis history record.

        This method reconstructs an AnalysisResult from the stored raw_result
        and generates a detailed Markdown report similar to the push notifications.

        Args:
            record_id: integer PK (as string) or query_id string

        Returns:
            Markdown formatted report string, or None if record not found

        Raises:
            MarkdownReportGenerationError: If report generation fails due to internal errors
        """
        record = self._resolve_record(record_id)
        if not record:
            logger.warning(f"get_markdown_report: record not found for {record_id}")
            return None

        # Rebuild AnalysisResult from raw_result
        raw_result = parse_json_field(record.raw_result)
        if not raw_result:
            logger.error(f"get_markdown_report: raw_result is empty for {record_id}")
            raise MarkdownReportGenerationError(
                f"raw_result is empty or invalid for record {record_id}",
                record_id=record_id
            )

        try:
            result = self._rebuild_analysis_result(
                raw_result,
                record,
                context_snapshot=self._parse_context_snapshot(record.context_snapshot),
            )
        except Exception as e:
            logger.error(f"get_markdown_report: failed to rebuild AnalysisResult for {record_id}: {e}", exc_info=True)
            raise MarkdownReportGenerationError(
                f"Failed to rebuild AnalysisResult: {str(e)}",
                record_id=record_id
            ) from e

        if not result:
            logger.error(f"get_markdown_report: _rebuild_analysis_result returned None for {record_id}")
            raise MarkdownReportGenerationError(
                f"Failed to rebuild AnalysisResult from raw_result",
                record_id=record_id
            )

        # Generate Markdown report via unified renderer to keep web/notification sections aligned.
        try:
            time_ctx = {}
            dashboard = getattr(result, "dashboard", {}) or {}
            structured = dashboard.get("structured_analysis", {}) if isinstance(dashboard, dict) else {}
            if isinstance(structured, dict):
                time_ctx = structured.get("time_context", {}) or {}
            rendered = report_renderer.render(
                "markdown",
                [result],
                report_date=record.created_at.strftime("%Y-%m-%d") if record.created_at else None,
                summary_only=False,
                extra_context={
                    "report_generated_at": time_ctx.get("report_generated_at") or (record.created_at.isoformat() if record.created_at else None),
                    "market_timestamp": time_ctx.get("market_timestamp"),
                    "market_session_date": time_ctx.get("market_session_date"),
                    "session_type": time_ctx.get("session_type"),
                    "news_published_at": time_ctx.get("news_published_at"),
                    "report_language": normalize_report_language(getattr(result, "report_language", None)),
                },
            )
            if rendered:
                return rendered
            return self._generate_single_stock_markdown(result, record)
        except Exception as e:
            logger.error(f"get_markdown_report: failed to generate markdown for {record_id}: {e}", exc_info=True)
            raise MarkdownReportGenerationError(
                f"Failed to generate markdown report: {str(e)}",
                record_id=record_id
            ) from e

    def _rebuild_analysis_result(
        self,
        raw_result: Dict[str, Any],
        record,
        context_snapshot: Any = None,
    ) -> Optional[AnalysisResult]:
        """
        Rebuild an AnalysisResult object from stored raw_result dict.

        Args:
            raw_result: The parsed raw_result JSON dict
            record: The AnalysisHistory ORM record

        Returns:
            AnalysisResult object or None
        """
        try:
            from src.analyzer import AnalysisResult
            dashboard = self._merge_dashboard_from_context(
                raw_result.get("dashboard", {}),
                context_snapshot,
            )
            market_snapshot = self._merge_market_snapshot_from_context(
                raw_result.get("market_snapshot"),
                context_snapshot,
            )

            # Build AnalysisResult with available data
            return AnalysisResult(
                code=raw_result.get("code", record.code),
                name=raw_result.get("name", record.name),
                sentiment_score=raw_result.get("sentiment_score", record.sentiment_score or 50),
                trend_prediction=raw_result.get("trend_prediction", record.trend_prediction or ""),
                operation_advice=raw_result.get("operation_advice", record.operation_advice or ""),
                decision_type=raw_result.get("decision_type", "hold"),
                confidence_level=raw_result.get("confidence_level", "中"),
                report_language=normalize_report_language(raw_result.get("report_language")),
                dashboard=dashboard,
                trend_analysis=raw_result.get("trend_analysis", ""),
                short_term_outlook=raw_result.get("short_term_outlook", ""),
                medium_term_outlook=raw_result.get("medium_term_outlook", ""),
                technical_analysis=raw_result.get("technical_analysis", ""),
                ma_analysis=raw_result.get("ma_analysis", ""),
                volume_analysis=raw_result.get("volume_analysis", ""),
                pattern_analysis=raw_result.get("pattern_analysis", ""),
                fundamental_analysis=raw_result.get("fundamental_analysis", ""),
                sector_position=raw_result.get("sector_position", ""),
                company_highlights=raw_result.get("company_highlights", ""),
                news_summary=raw_result.get("news_summary", record.news_content or ""),
                market_sentiment=raw_result.get("market_sentiment", ""),
                hot_topics=raw_result.get("hot_topics", ""),
                analysis_summary=raw_result.get("analysis_summary", record.analysis_summary or ""),
                key_points=raw_result.get("key_points", ""),
                risk_warning=raw_result.get("risk_warning", ""),
                buy_reason=raw_result.get("buy_reason", ""),
                market_snapshot=market_snapshot,
                search_performed=raw_result.get("search_performed", False),
                data_sources=raw_result.get("data_sources", ""),
                success=raw_result.get("success", True),
                error_message=raw_result.get("error_message"),
                current_price=raw_result.get("current_price"),
                change_pct=raw_result.get("change_pct"),
                model_used=raw_result.get("model_used"),
            )
        except Exception as e:
            logger.error(f"Failed to rebuild AnalysisResult: {e}", exc_info=True)
            return None

    def _generate_single_stock_markdown(
        self,
        result: AnalysisResult,
        record
    ) -> str:
        """
        Generate a Markdown report for a single stock analysis.

        This follows the same format as NotificationService.generate_dashboard_report()
        using dashboard structured data for detailed report.

        Args:
            result: The AnalysisResult object
            record: The AnalysisHistory ORM record

        Returns:
            Markdown formatted report string
        """
        report_date = record.created_at.strftime("%Y-%m-%d") if record.created_at else datetime.now().strftime("%Y-%m-%d")
        report_time = record.created_at.strftime("%H:%M:%S") if record.created_at else datetime.now().strftime("%H:%M:%S")
        report_language = normalize_report_language(getattr(result, "report_language", "zh"))
        labels = get_report_labels(report_language)
        analysis_date_label = "Analysis Date" if report_language == "en" else "分析日期"
        report_time_label = "Report Time" if report_language == "en" else "报告生成时间"
        reason_label = "Rationale" if report_language == "en" else "操作理由"
        risk_warning_label = "Risk Warning" if report_language == "en" else "风险提示"
        technical_heading = "Technicals" if report_language == "en" else "技术面"
        ma_label = "Moving Averages" if report_language == "en" else "均线"
        volume_analysis_label = "Volume" if report_language == "en" else "量能"
        news_heading = "News Flow" if report_language == "en" else "消息面"

        # Escape markdown special characters in stock name
        name_escaped = self._escape_md(
            get_localized_stock_name(result.name, result.code, report_language)
        ) or result.code

        # Get signal level
        signal_text, signal_emoji, signal_tag = self._get_signal_level(result)
        dashboard = result.dashboard if hasattr(result, 'dashboard') and result.dashboard else {}

        report_lines = [
            f"# 📊 {name_escaped} ({result.code}) {labels['report_title']}",
            "",
            f"> {analysis_date_label}: **{report_date}** | {report_time_label}: {report_time}",
            "",
            "---",
            "",
        ]

        # ========== 舆情与基本面概览（放在最前面）==========
        intel = dashboard.get('intelligence', {}) if dashboard else {}
        if intel:
            report_lines.extend([
                f"### 📰 {labels['info_heading']}",
                "",
            ])
            # 舆情情绪总结
            if intel.get('sentiment_summary'):
                report_lines.append(f"**💭 {labels['sentiment_summary_label']}**: {intel['sentiment_summary']}")
            # 业绩预期
            if intel.get('earnings_outlook'):
                report_lines.append(f"**📊 {labels['earnings_outlook_label']}**: {intel['earnings_outlook']}")
            # 风险警报（醒目显示）
            risk_alerts = intel.get('risk_alerts', [])
            if risk_alerts:
                report_lines.append("")
                report_lines.append(f"**🚨 {labels['risk_alerts_label']}**:")
                for alert in risk_alerts:
                    report_lines.append(f"- {alert}")
            # 利好催化
            catalysts = intel.get('positive_catalysts', [])
            if catalysts:
                report_lines.append("")
                report_lines.append(f"**✨ {labels['positive_catalysts_label']}**:")
                for cat in catalysts:
                    report_lines.append(f"- {cat}")
            # 最新消息
            if intel.get('latest_news'):
                report_lines.append("")
                report_lines.append(f"**📢 {labels['latest_news_label']}**: {intel['latest_news']}")
            report_lines.append("")

        # ========== 核心结论 ==========
        core = dashboard.get('core_conclusion', {}) if dashboard else {}
        one_sentence = core.get('one_sentence', result.analysis_summary)
        time_sense = core.get('time_sensitivity', labels['default_time_sensitivity'])
        pos_advice = core.get('position_advice', {})

        report_lines.extend([
            f"### 📌 {labels['core_conclusion_heading']}",
            "",
            f"**{signal_emoji} {signal_text}** | {localize_trend_prediction(result.trend_prediction, report_language)}",
            "",
            f"> **{labels['one_sentence_label']}**: {one_sentence}",
            "",
            f"⏰ **{labels['time_sensitivity_label']}**: {time_sense}",
            "",
        ])
        # 持仓分类建议
        if pos_advice:
            report_lines.extend([
                f"| {labels['position_status_label']} | {labels['action_advice_label']} |",
                "|---------|---------|",
                f"| 🆕 **{labels['no_position_label']}** | {pos_advice.get('no_position', localize_operation_advice(result.operation_advice, report_language))} |",
                f"| 💼 **{labels['has_position_label']}** | {pos_advice.get('has_position', labels['continue_holding'])} |",
                "",
            ])

        # ========== 行情快照 ==========
        self._append_market_snapshot_to_report(report_lines, result, labels)

        # ========== 数据透视 ==========
        data_persp = dashboard.get('data_perspective', {}) if dashboard else {}
        if data_persp:
            trend_data = data_persp.get('trend_status', {})
            price_data = data_persp.get('price_position', {})
            vol_data = data_persp.get('volume_analysis', {})
            chip_data = data_persp.get('chip_structure', {})

            report_lines.extend([
                f"### 📊 {labels['data_perspective_heading']}",
                "",
            ])
            # 趋势状态
            if trend_data:
                is_bullish = (
                    f"✅ {labels['yes_label']}"
                    if trend_data.get('is_bullish', False)
                    else f"❌ {labels['no_label']}"
                )
                report_lines.extend([
                    f"**{labels['ma_alignment_label']}**: {trend_data.get('ma_alignment', 'N/A')} | "
                    f"{labels['bullish_alignment_label']}: {is_bullish} | "
                    f"{labels['trend_strength_label']}: {trend_data.get('trend_score', 'N/A')}/100",
                    "",
                ])
            # 价格位置
            if price_data:
                raw_bias_status = price_data.get('bias_status', 'N/A')
                bias_status = localize_bias_status(raw_bias_status, report_language)
                bias_emoji = get_bias_status_emoji(raw_bias_status)
                bias_value = price_data.get('bias_ma5', 'N/A')
                try:
                    bias_num = float(str(bias_value).strip().rstrip('%'))
                    bias_display = "数据缺失" if bias_num == 0 else f"{bias_num:.2f}%"
                except (TypeError, ValueError):
                    bias_display = "数据缺失"
                report_lines.extend([
                    f"| {labels['price_metrics_label']} | {labels['current_price_label']} |",
                    "|---------|------|",
                    f"| {labels['current_price_label']} | {price_data.get('current_price', 'N/A')} |",
                    f"| {labels['ma5_label']} | {price_data.get('ma5', 'N/A')} |",
                    f"| {labels['ma10_label']} | {price_data.get('ma10', 'N/A')} |",
                    f"| {labels['ma20_label']} | {price_data.get('ma20', 'N/A')} |",
                    f"| {labels['bias_ma5_label']} | {bias_display} {bias_emoji}{bias_status} |",
                    f"| {labels['support_level_label']} | {price_data.get('support_level', 'N/A')} |",
                    f"| {labels['resistance_level_label']} | {price_data.get('resistance_level', 'N/A')} |",
                    "",
                ])
            # 量能分析
            if vol_data:
                volume_ratio_raw = vol_data.get('volume_ratio', 'N/A')
                volume_ratio_display = (
                    "数据缺失" if volume_ratio_raw in (None, "", "N/A", "None", 0, 0.0, "0", "0.0") else volume_ratio_raw
                )
                turnover_rate = vol_data.get('turnover_rate', 'N/A')
                turnover_display = (
                    "数据缺失"
                    if turnover_rate in (None, "", "N/A")
                    else (
                        str(turnover_rate)
                        if str(turnover_rate).endswith('%')
                        else f"{turnover_rate}%"
                    )
                )
                report_lines.extend([
                    f"**{labels['volume_label']}**: {labels['volume_ratio_label']} {volume_ratio_display} "
                    f"({vol_data.get('volume_status', '')}) | {labels['turnover_rate_label']} {turnover_display}",
                    f"💡 *{vol_data.get('volume_meaning', '')}*",
                    "",
                ])
            # 筹码结构
            if is_us_stock_code(result.code):
                report_lines.extend([
                    f"**{labels['chip_label']}**: 美股暂不支持该指标",
                    "",
                ])
            elif chip_data:
                raw_chip_health = chip_data.get('chip_health', 'N/A')
                chip_health = localize_chip_health(raw_chip_health, report_language)
                normalized_chip_health = str(raw_chip_health or "").strip().lower()
                if normalized_chip_health in {"健康", "healthy"}:
                    chip_emoji = "✅"
                elif normalized_chip_health in {"一般", "average"}:
                    chip_emoji = "⚠️"
                else:
                    chip_emoji = "🚨"
                report_lines.extend([
                    f"**{labels['chip_label']}**: {chip_data.get('profit_ratio', 'N/A')} | {chip_data.get('avg_cost', 'N/A')} | "
                    f"{chip_data.get('concentration', 'N/A')} {chip_emoji}{chip_health}",
                    "",
                ])

        # ========== 作战计划 ==========
        battle = dashboard.get('battle_plan', {}) if dashboard else {}
        if battle:
            report_lines.extend([
                f"### 🎯 {labels['battle_plan_heading']}",
                "",
            ])
            # 狙击点位
            sniper = battle.get('sniper_points', {})
            if sniper:
                report_lines.extend([
                    f"**📍 {labels['action_points_heading']}**",
                    "",
                    f"| {labels['action_points_heading']} | {labels['current_price_label']} |",
                    "|---------|------|",
                    f"| 🎯 {labels['ideal_buy_label']} | {self._clean_sniper_value(sniper.get('ideal_buy', 'N/A'))} |",
                    f"| 🔵 {labels['secondary_buy_label']} | {self._clean_sniper_value(sniper.get('secondary_buy', 'N/A'))} |",
                    f"| 🛑 {labels['stop_loss_label']} | {self._clean_sniper_value(sniper.get('stop_loss', 'N/A'))} |",
                    f"| 🎊 {labels['take_profit_label']} | {self._clean_sniper_value(sniper.get('take_profit', 'N/A'))} |",
                    "",
                ])
            # 仓位策略
            position = battle.get('position_strategy', {})
            if position:
                report_lines.extend([
                    f"**💰 {labels['suggested_position_label']}**: {position.get('suggested_position', 'N/A')}",
                    f"- {labels['entry_plan_label']}: {position.get('entry_plan', 'N/A')}",
                    f"- {labels['risk_control_label']}: {position.get('risk_control', 'N/A')}",
                    "",
                ])
            # 检查清单
            checklist = battle.get('action_checklist', []) if battle else []
            if checklist:
                report_lines.extend([
                    f"**✅ {labels['checklist_heading']}**",
                    "",
                ])
                for item in checklist:
                    report_lines.append(f"- {item}")
                report_lines.append("")

        # ========== 如果没有 dashboard，显示传统格式 ==========
        if not dashboard:
            # 操作理由
            if result.buy_reason:
                report_lines.extend([
                    f"**💡 {reason_label}**: {result.buy_reason}",
                    "",
                ])
            # 风险提示
            if result.risk_warning:
                report_lines.extend([
                    f"**⚠️ {risk_warning_label}**: {result.risk_warning}",
                    "",
                ])
            # 技术面分析
            if result.ma_analysis or result.volume_analysis:
                report_lines.extend([
                    f"### 📊 {technical_heading}",
                    "",
                ])
                if result.ma_analysis:
                    report_lines.append(f"**{ma_label}**: {result.ma_analysis}")
                if result.volume_analysis:
                    report_lines.append(f"**{volume_analysis_label}**: {result.volume_analysis}")
                report_lines.append("")
            # 消息面
            if result.news_summary:
                report_lines.extend([
                    f"### 📰 {news_heading}",
                    f"{result.news_summary}",
                    "",
                ])

        # ========== 底部 ==========
        report_lines.extend([
            "---",
            "",
            f"*{labels['generated_at_label']}: {report_time}*",
        ])

        return "\n".join(report_lines)

    @staticmethod
    def _escape_md(text: Optional[str]) -> str:
        """Escape markdown special characters."""
        if not text:
            return ""
        return text.replace('*', r'\*')

    @staticmethod
    def _clean_sniper_value(value: Any) -> str:
        """Clean sniper point value for display."""
        if value is None:
            return "N/A"
        text = str(value).strip()
        if not text or text in ("-", "—", "N/A", "None"):
            return "N/A"
        return text

    def _get_signal_level(self, result: AnalysisResult) -> Tuple[str, str, str]:
        """Get signal level based on sentiment score and decision type."""
        return get_signal_level(
            result.operation_advice,
            result.sentiment_score,
            getattr(result, "report_language", "zh"),
        )

    @staticmethod
    def _safe_format_number(value: Any, fmt: str = ".2f") -> str:
        """
        Safely format a numeric value that may be a string.

        Args:
            value: The value to format (may be int, float, or string like "12.34" or "N/A")
            fmt: Format string (default: ".2f")

        Returns:
            Formatted string or original string if not a valid number
        """
        if value is None:
            return "N/A"
        if isinstance(value, (int, float)):
            return f"{value:{fmt}}"
        if isinstance(value, str):
            value = value.strip()
            if not value or value in ("N/A", "-", "—", "None"):
                return "N/A"
            try:
                return f"{float(value):{fmt}}"
            except (ValueError, TypeError):
                return value
        return str(value)

    @staticmethod
    def _append_market_snapshot_to_report(
        lines: List[str],
        result: AnalysisResult,
        labels: Dict[str, str],
    ) -> None:
        """Append market snapshot data to report lines."""
        snapshot = getattr(result, 'market_snapshot', None)
        if not snapshot:
            return

        lines.extend([
            f"### 📈 {labels['market_snapshot_heading']}",
            "",
            f"| {labels['price_metrics_label']} | {labels['current_price_label']} |",
            "|------|------|",
        ])

        # Price info
        current_price = snapshot.get('price') or snapshot.get('current_price') or result.current_price
        change_pct = snapshot.get('change_pct') or snapshot.get('pct_chg') or result.change_pct
        if current_price is not None:
            current_str = HistoryService._safe_format_number(current_price, ".2f")
            if change_pct is not None:
                if isinstance(change_pct, str) and change_pct.strip().endswith("%"):
                    change_str = change_pct.strip()
                else:
                    change_str = f"{HistoryService._safe_format_number(change_pct, '+.2f')}%"
            else:
                change_str = "--"
            lines.append(f"| {labels['current_price_label']} | **{current_str}** ({change_str}) |")

        # Other metrics
        metrics = [
            (labels['open_label'], "open", ".2f"),
            (labels['high_label'], "high", ".2f"),
            (labels['low_label'], "low", ".2f"),
            (labels['volume_label'], "volume", ",.0f"),
            (labels['amount_label'], "amount", ",.0f"),
        ]
        for label, key, fmt in metrics:
            value = snapshot.get(key)
            if value is not None:
                formatted = HistoryService._safe_format_number(value, fmt)
                lines.append(f"| {label} | {formatted} |")

        lines.extend(["", "---", ""])
