"""Unified market data router built on top of existing data_provider fetchers."""

from __future__ import annotations

import logging
from typing import Any, Optional

from .source_health import SourceHealthRegistry
from .source_models import MarketDataBundle, SourceAttempt, SourceStatus, utc_now_iso

logger = logging.getLogger(__name__)


def _source_name_from_quote(quote: Any) -> Optional[str]:
    source = getattr(quote, "source", None)
    value = getattr(source, "value", source)
    return str(value) if value is not None else None


class MarketDataRouter:
    """Route quote/K-line/fundamental requests through a single fail-open facade."""

    def __init__(
        self,
        fetcher_manager: Any,
        *,
        health_registry: Optional[SourceHealthRegistry] = None,
    ) -> None:
        self.fetcher_manager = fetcher_manager
        self.health = health_registry or SourceHealthRegistry()

    def get_realtime_quote(self, stock_code: str, *, log_final_failure: bool = True) -> MarketDataBundle:
        started_at = utc_now_iso()
        try:
            quote = self.fetcher_manager.get_realtime_quote(
                stock_code,
                log_final_failure=log_final_failure,
            )
        except Exception as exc:
            ended_at = utc_now_iso()
            attempt = SourceAttempt(
                source_name="realtime_router",
                status=SourceStatus.FAILED,
                started_at=started_at,
                ended_at=ended_at,
                error_message=str(exc),
            )
            self.health.record_failure("realtime_router", str(exc))
            logger.warning("[market-router] realtime quote failed for %s: %s", stock_code, exc)
            return MarketDataBundle(
                stock_code=stock_code,
                source_name=None,
                data_timestamp=ended_at,
                realtime_quote=None,
                attempts=[attempt],
                status=SourceStatus.FAILED,
                insufficient_reason="数据不足，无法生成交易观察：实时行情链路异常",
            )

        ended_at = utc_now_iso()
        source_name = _source_name_from_quote(quote)
        if quote is not None and getattr(quote, "has_basic_data", lambda: True)():
            setattr(quote, "data_timestamp", getattr(quote, "provider_timestamp", None) or ended_at)
            attempt = SourceAttempt(
                source_name=source_name or "realtime_router",
                status=SourceStatus.OK,
                started_at=started_at,
                ended_at=ended_at,
                record_count=1,
            )
            self.health.record_success(source_name or "realtime_router")
            return MarketDataBundle(
                stock_code=stock_code,
                source_name=source_name,
                data_timestamp=getattr(quote, "provider_timestamp", None) or ended_at,
                realtime_quote=quote,
                attempts=[attempt],
                status=SourceStatus.OK,
            )

        attempt = SourceAttempt(
            source_name="realtime_router",
            status=SourceStatus.EMPTY,
            started_at=started_at,
            ended_at=ended_at,
            error_message="empty realtime quote",
            record_count=0,
        )
        self.health.record_empty("realtime_router", "empty realtime quote")
        return MarketDataBundle(
            stock_code=stock_code,
            source_name=None,
            data_timestamp=ended_at,
            realtime_quote=None,
            attempts=[attempt],
            status=SourceStatus.EMPTY,
            insufficient_reason="数据不足，无法生成交易观察：所有实时行情数据源均不可用",
        )

    def get_daily_data(
        self,
        stock_code: str,
        *,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30,
    ) -> MarketDataBundle:
        started_at = utc_now_iso()
        try:
            df, source_name = self.fetcher_manager.get_daily_data(
                stock_code,
                start_date=start_date,
                end_date=end_date,
                days=days,
            )
        except Exception as exc:
            ended_at = utc_now_iso()
            self.health.record_failure("daily_data_router", str(exc))
            return MarketDataBundle(
                stock_code=stock_code,
                source_name=None,
                data_timestamp=ended_at,
                kline_daily=None,
                attempts=[
                    SourceAttempt(
                        source_name="daily_data_router",
                        status=SourceStatus.FAILED,
                        started_at=started_at,
                        ended_at=ended_at,
                        error_message=str(exc),
                    )
                ],
                status=SourceStatus.FAILED,
                insufficient_reason="数据不足，无法生成交易观察：日线数据源全部失败",
            )

        ended_at = utc_now_iso()
        record_count = 0 if df is None else len(df)
        status = SourceStatus.OK if df is not None and not df.empty else SourceStatus.EMPTY
        if status == SourceStatus.OK:
            self.health.record_success(source_name)
        else:
            self.health.record_empty(source_name, "empty daily data")
        data_timestamp = ended_at
        if df is not None and not df.empty and "date" in df.columns:
            try:
                data_timestamp = str(df.iloc[-1]["date"])
            except Exception:
                data_timestamp = ended_at
        return MarketDataBundle(
            stock_code=stock_code,
            source_name=source_name,
            data_timestamp=data_timestamp,
            kline_daily=df,
            attempts=[
                SourceAttempt(
                    source_name=source_name,
                    status=status,
                    started_at=started_at,
                    ended_at=ended_at,
                    record_count=record_count,
                )
            ],
            status=status,
            insufficient_reason=None if status == SourceStatus.OK else "数据不足，无法生成交易观察：日线数据为空",
        )

    def get_fundamental_context(self, stock_code: str, *, budget_seconds: Optional[float] = None) -> MarketDataBundle:
        started_at = utc_now_iso()
        try:
            context = self.fetcher_manager.get_fundamental_context(
                stock_code,
                budget_seconds=budget_seconds,
            )
        except Exception as exc:
            ended_at = utc_now_iso()
            self.health.record_failure("fundamental_router", str(exc))
            context = self.fetcher_manager.build_failed_fundamental_context(stock_code, str(exc))
            return MarketDataBundle(
                stock_code=stock_code,
                source_name="fundamental_router",
                data_timestamp=ended_at,
                fundamental_context=context,
                attempts=[
                    SourceAttempt(
                        source_name="fundamental_router",
                        status=SourceStatus.FAILED,
                        started_at=started_at,
                        ended_at=ended_at,
                        error_message=str(exc),
                    )
                ],
                status=SourceStatus.FAILED,
                insufficient_reason="基本面/资金流数据源失败，禁止据此编造结论",
            )

        ended_at = utc_now_iso()
        source_chain = context.get("source_chain", []) if isinstance(context, dict) else []
        source_name = "fundamental_pipeline"
        if source_chain and isinstance(source_chain[0], dict):
            source_name = str(source_chain[0].get("provider") or source_name)
        coverage = context.get("coverage", {}) if isinstance(context, dict) else {}
        ok = any(value == "ok" for value in coverage.values()) if isinstance(coverage, dict) else bool(context)
        status = SourceStatus.OK if ok else SourceStatus.EMPTY
        if status == SourceStatus.OK:
            self.health.record_success(source_name)
        else:
            self.health.record_empty(source_name, "empty or unsupported fundamental context")
        context = dict(context) if isinstance(context, dict) else {}
        context.setdefault("source_name", source_name)
        context.setdefault("data_timestamp", ended_at)
        return MarketDataBundle(
            stock_code=stock_code,
            source_name=source_name,
            data_timestamp=ended_at,
            fundamental_context=context,
            attempts=[
                SourceAttempt(
                    source_name=source_name,
                    status=status,
                    started_at=started_at,
                    ended_at=ended_at,
                    record_count=1 if context else 0,
                )
            ],
            status=status,
            insufficient_reason=None if ok else "基本面/资金流数据不足，禁止据此编造结论",
        )
