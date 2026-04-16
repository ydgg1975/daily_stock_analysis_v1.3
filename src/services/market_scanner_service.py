# -*- coding: utf-8 -*-
"""Rule-based market scanner service."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import select

from data_provider.base import (
    DataFetcherManager,
    is_bse_code,
    is_kc_cy_stock,
    is_st_stock,
    normalize_stock_code,
)
from data_provider.us_index_mapping import is_us_stock_code
from src.config import get_config
from src.core.scanner_profile import ScannerMarketProfile, get_scanner_profile
from src.data.stock_mapping import STOCK_NAME_MAP
from src.core.trading_calendar import MARKET_TIMEZONE, is_market_open
from src.multi_user import OWNERSHIP_SCOPE_SYSTEM, OWNERSHIP_SCOPE_USER, normalize_scope
from src.repositories.scanner_repo import ScannerRepository
from src.repositories.stock_repo import StockRepository
from src.services.scanner_ai_service import ScannerAiInterpretationService
from src.services.us_history_helper import fetch_daily_history_with_local_us_fallback, get_us_stock_parquet_dir
from src.storage import (
    AnalysisHistory,
    DatabaseManager,
    MarketScannerCandidate,
    MarketScannerRun,
    StockDaily,
)

logger = logging.getLogger(__name__)

DEFAULT_SCANNER_REVIEW_WINDOW_DAYS = 3
DEFAULT_SCANNER_BENCHMARK_CODE = "000300"
DEFAULT_US_SCANNER_BENCHMARK_CODE = "SPY"
DEFAULT_HK_SCANNER_BENCHMARK_CODE = "HK02800"
MIN_US_SCANNER_SEED_TARGET = 24
MAX_US_SCANNER_SEED_TARGET = 36
CURATED_US_LIQUID_SEED_SYMBOLS: Tuple[str, ...] = (
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "AMD",
    "AVGO",
    "NFLX",
    "PLTR",
    "SOFI",
    "MU",
    "QCOM",
    "TSM",
    "ARM",
    "ORCL",
    "CRM",
    "PANW",
    "UBER",
    "SHOP",
    "SNOW",
    "COIN",
    "SMCI",
    "INTC",
    "JPM",
    "BAC",
    "XOM",
    "UNH",
    "ADBE",
    "QQQ",
    "IWM",
)
CURATED_HK_LIQUID_SEED_SYMBOLS: Tuple[str, ...] = (
    "HK00700",
    "HK09988",
    "HK03690",
    "HK01810",
    "HK00981",
    "HK00388",
    "HK01211",
    "HK09618",
    "HK09999",
    "HK01024",
    "HK02318",
    "HK00005",
    "HK01398",
    "HK00883",
    "HK02020",
    "HK02382",
    "HK06862",
    "HK03888",
    "HK01109",
    "HK06618",
    "HK02800",
)


class ScannerRuntimeError(ValueError):
    """Structured scanner runtime error with stable diagnostics."""

    def __init__(
        self,
        reason_code: str,
        message: str,
        *,
        diagnostics: Optional[Dict[str, Any]] = None,
        source_summary: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.diagnostics = dict(diagnostics or {})
        self.source_summary = source_summary


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value.strip():
            return default
        number = float(value)
        if np.isnan(number) or np.isinf(number):
            return default
        return number
    except Exception:
        return default


def _json_load(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _format_pct(value: Optional[float], digits: int = 1) -> str:
    if value is None:
        return "--"
    return f"{float(value):.{digits}f}%"


def _format_price(value: Optional[float], digits: int = 2) -> str:
    if value is None:
        return "--"
    return f"{float(value):.{digits}f}"


def _format_amount(value: Optional[float]) -> str:
    if value is None:
        return "--"
    number = float(value)
    if abs(number) >= 1.0e8:
        return f"{number / 1.0e8:.2f}亿"
    if abs(number) >= 1.0e4:
        return f"{number / 1.0e4:.2f}万"
    return f"{number:.0f}"


def _format_us_amount(value: Optional[float]) -> str:
    if value is None:
        return "--"
    number = float(value)
    if abs(number) >= 1.0e9:
        return f"${number / 1.0e9:.2f}B"
    if abs(number) >= 1.0e6:
        return f"${number / 1.0e6:.1f}M"
    if abs(number) >= 1.0e3:
        return f"${number / 1.0e3:.1f}K"
    return f"${number:.0f}"


def _format_hk_amount(value: Optional[float]) -> str:
    if value is None:
        return "--"
    number = float(value)
    if abs(number) >= 1.0e9:
        return f"HK${number / 1.0e9:.2f}B"
    if abs(number) >= 1.0e6:
        return f"HK${number / 1.0e6:.1f}M"
    if abs(number) >= 1.0e3:
        return f"HK${number / 1.0e3:.1f}K"
    return f"HK${number:.0f}"


def _format_volume(value: Optional[float]) -> str:
    if value is None:
        return "--"
    number = float(value)
    if abs(number) >= 1.0e8:
        return f"{number / 1.0e8:.2f}亿股"
    if abs(number) >= 1.0e4:
        return f"{number / 1.0e4:.2f}万股"
    return f"{number:.0f}股"


def _format_us_volume(value: Optional[float]) -> str:
    if value is None:
        return "--"
    number = float(value)
    if abs(number) >= 1.0e9:
        return f"{number / 1.0e9:.2f}B sh"
    if abs(number) >= 1.0e6:
        return f"{number / 1.0e6:.1f}M sh"
    if abs(number) >= 1.0e3:
        return f"{number / 1.0e3:.1f}K sh"
    return f"{number:.0f} sh"


def _format_hk_volume(value: Optional[float]) -> str:
    if value is None:
        return "--"
    number = float(value)
    if abs(number) >= 1.0e8:
        return f"{number / 1.0e8:.2f}亿股"
    if abs(number) >= 1.0e6:
        return f"{number / 1.0e6:.1f}M股"
    if abs(number) >= 1.0e3:
        return f"{number / 1.0e3:.1f}K股"
    return f"{number:.0f}股"


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _pct_change(base: Optional[float], value: Optional[float]) -> Optional[float]:
    base_value = _safe_float(base, default=np.nan)
    target_value = _safe_float(value, default=np.nan)
    if np.isnan(base_value) or np.isnan(target_value) or abs(base_value) < 1e-9:
        return None
    return ((target_value / base_value) - 1.0) * 100.0


def _round_optional(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _mean_or_none(values: Sequence[Optional[float]], digits: int = 2) -> Optional[float]:
    normalized = [float(value) for value in values if value is not None]
    if not normalized:
        return None
    return round(float(np.mean(normalized)), digits)


def _common_board_name(item: Any) -> Optional[str]:
    if isinstance(item, dict):
        for key in ("name", "board_name", "板块名称", "板块", "行业"):
            value = item.get(key)
            if value:
                return str(value).strip()
        return None
    if item is None:
        return None
    text = str(item).strip()
    return text or None


def _market_date_string(market: str, reference: Optional[datetime] = None) -> str:
    tz_name = MARKET_TIMEZONE.get((market or "").strip().lower(), "Asia/Shanghai")
    target_tz = ZoneInfo(tz_name)
    if reference is None:
        return datetime.now(target_tz).date().isoformat()

    base_dt = reference
    try:
        if base_dt.tzinfo:
            localized = base_dt.astimezone(target_tz)
        else:
            local_tz = datetime.now().astimezone().tzinfo or target_tz
            localized = base_dt.replace(tzinfo=local_tz).astimezone(target_tz)
    except Exception:
        localized = base_dt
    return localized.date().isoformat()


def _is_cn_common_stock_code(code: str) -> bool:
    normalized = normalize_stock_code(code)
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    if is_bse_code(normalized):
        return False
    return normalized.startswith(
        (
            "000",
            "001",
            "002",
            "003",
            "300",
            "301",
            "600",
            "601",
            "603",
            "605",
            "688",
            "689",
        )
    )


def _is_hk_scanner_symbol(code: str) -> bool:
    normalized = normalize_stock_code(code).upper()
    return normalized.startswith("HK") and normalized[2:].isdigit()


class MarketScannerService:
    """End-to-end market scanner orchestration."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        data_manager: Optional[DataFetcherManager] = None,
        local_universe_cache_path: Optional[str] = None,
        ai_interpretation_service: Optional[ScannerAiInterpretationService] = None,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self.data_manager = data_manager or DataFetcherManager()
        self.repo = ScannerRepository(self.db)
        self.stock_repo = StockRepository(self.db)
        self.ai_service = ai_interpretation_service or ScannerAiInterpretationService()
        self.owner_id = owner_id
        self.include_all_owners = bool(include_all_owners)
        configured_path = local_universe_cache_path or getattr(
            get_config(),
            "scanner_local_universe_path",
            "./data/scanner_cn_universe_cache.csv",
        )
        self.local_universe_cache_path = Path(str(configured_path)).expanduser()
        self._run_review_cache: Dict[int, Dict[str, Any]] = {}
        self._benchmark_review_cache: Dict[Tuple[str, str, int], Dict[str, Any]] = {}

    def _visibility_kwargs(
        self,
        *,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: Optional[bool] = None,
    ) -> Dict[str, Any]:
        return {
            "scope": normalize_scope(scope) if scope else None,
            "owner_id": self.owner_id if owner_id is None else owner_id,
            "include_all_owners": (
                self.include_all_owners if include_all_owners is None else bool(include_all_owners)
            ),
        }

    def _resolve_persisted_owner_id(
        self,
        *,
        scope: str,
        owner_id: Optional[str] = None,
    ) -> Optional[str]:
        if normalize_scope(scope) == OWNERSHIP_SCOPE_SYSTEM:
            return None
        return self.db.require_user_id(self.owner_id if owner_id is None else owner_id)

    def run_scan(
        self,
        *,
        market: str = "cn",
        profile: Optional[str] = None,
        shortlist_size: Optional[int] = None,
        universe_limit: Optional[int] = None,
        detail_limit: Optional[int] = None,
        scope: str = OWNERSHIP_SCOPE_USER,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run one market scan and persist the resulting shortlist."""

        run_started_at = datetime.now()
        profile_config = self._resolve_profile(market=market, profile=profile)
        normalized_scope = normalize_scope(scope)
        resolved_owner_id = self._resolve_persisted_owner_id(
            scope=normalized_scope,
            owner_id=owner_id,
        )
        resolved_shortlist_size = self._resolve_positive_int(shortlist_size, profile_config.shortlist_size, 1, 20)
        resolved_universe_limit = self._resolve_positive_int(universe_limit, profile_config.universe_limit, 50, 1000)
        resolved_detail_limit = self._resolve_positive_int(detail_limit, profile_config.detail_limit, 10, 200)
        if resolved_detail_limit < resolved_shortlist_size:
            raise ValueError("detail_limit 不能小于 shortlist_size")

        if profile_config.market == "us":
            return self._run_us_scan(
                profile_config=profile_config,
                run_started_at=run_started_at,
                resolved_shortlist_size=resolved_shortlist_size,
                resolved_universe_limit=resolved_universe_limit,
                resolved_detail_limit=resolved_detail_limit,
                scope=normalized_scope,
                owner_id=resolved_owner_id,
            )
        if profile_config.market == "hk":
            return self._run_hk_scan(
                profile_config=profile_config,
                run_started_at=run_started_at,
                resolved_shortlist_size=resolved_shortlist_size,
                resolved_universe_limit=resolved_universe_limit,
                resolved_detail_limit=resolved_detail_limit,
                scope=normalized_scope,
                owner_id=resolved_owner_id,
            )
        if profile_config.market != "cn":
            raise ValueError(f"当前阶段暂不支持市场: {profile_config.market}")

        universe_resolution = self._resolve_cn_stock_universe()
        snapshot_resolution = self._resolve_cn_snapshot(profile=profile_config, stock_list=universe_resolution.get("data"))

        stock_list = universe_resolution.get("data")
        stock_list_source = str(universe_resolution.get("source") or "unknown")
        snapshot = snapshot_resolution.get("data")
        snapshot_source = str(snapshot_resolution.get("source") or "unknown")

        if (stock_list is None or stock_list.empty) and snapshot is not None and not snapshot.empty:
            stock_list = snapshot[["code", "name"]].copy()
            stock_list_source = "snapshot_derived_universe"
            universe_resolution.update(
                {
                    "data": stock_list,
                    "source": stock_list_source,
                    "derived_from_snapshot": True,
                    "fallback_used": True,
                }
            )
            self._persist_local_universe_cache(stock_list, source=stock_list_source)

        if snapshot is None or snapshot.empty:
            failure_diagnostics = {
                "reason_code": str(snapshot_resolution.get("error_code") or "no_realtime_snapshot_available"),
                "universe_resolution": self._public_resolution_diagnostics(universe_resolution),
                "snapshot_resolution": self._public_resolution_diagnostics(snapshot_resolution),
            }
            raise ScannerRuntimeError(
                str(snapshot_resolution.get("error_code") or "no_realtime_snapshot_available"),
                str(snapshot_resolution.get("error_message") or "A 股全市场快照不可用，且未能进入本地历史降级模式。"),
                diagnostics=failure_diagnostics,
                source_summary=self._build_source_summary(
                    universe_source=stock_list_source,
                    snapshot_source=snapshot_source,
                    degraded_mode_used=bool(snapshot_resolution.get("degraded_mode_used")),
                    universe_resolution=universe_resolution,
                    snapshot_resolution=snapshot_resolution,
                ),
            )

        if stock_list is None or stock_list.empty:
            failure_diagnostics = {
                "reason_code": str(universe_resolution.get("error_code") or "universe_source_unavailable"),
                "universe_resolution": self._public_resolution_diagnostics(universe_resolution),
                "snapshot_resolution": self._public_resolution_diagnostics(snapshot_resolution),
            }
            raise ScannerRuntimeError(
                str(universe_resolution.get("error_code") or "universe_source_unavailable"),
                str(universe_resolution.get("error_message") or "A 股股票 universe 不可用。"),
                diagnostics=failure_diagnostics,
                source_summary=self._build_source_summary(
                    universe_source=stock_list_source,
                    snapshot_source=snapshot_source,
                    degraded_mode_used=bool(snapshot_resolution.get("degraded_mode_used")),
                    universe_resolution=universe_resolution,
                    snapshot_resolution=snapshot_resolution,
                ),
            )

        universe_df, universe_notes, universe_diag = self._build_cn_universe(
            stock_list=stock_list,
            snapshot=snapshot,
            profile=profile_config,
            universe_limit=resolved_universe_limit,
            degraded_mode=bool(snapshot_resolution.get("degraded_mode_used")),
        )
        if universe_df.empty:
            raise ValueError("扫描宇宙为空，无法生成候选名单")

        preselected_df = self._compute_pre_rank(universe_df).head(resolved_detail_limit).reset_index(drop=True)
        history_diag_rollup = {
            "local_hits": 0,
            "network_fetches": 0,
            "network_failures": 0,
            "partial_local_fallbacks": 0,
            "skipped_for_history": 0,
        }
        history_source_counts: Dict[str, int] = {}

        evaluated_candidates: List[Dict[str, Any]] = []
        for row in preselected_df.to_dict("records"):
            history_df, history_diag = self._load_history_local_first(
                code=str(row["code"]),
                profile=profile_config,
            )
            history_source = str(history_diag.get("source") or "")
            if history_source:
                history_source_counts[history_source] = history_source_counts.get(history_source, 0) + 1
            if history_source == "local_db":
                history_diag_rollup["local_hits"] += 1
            elif history_diag.get("network_used"):
                history_diag_rollup["network_fetches"] += 1
            if history_diag.get("network_failed"):
                history_diag_rollup["network_failures"] += 1
            if history_diag.get("partial_local_fallback"):
                history_diag_rollup["partial_local_fallbacks"] += 1

            candidate = self._build_candidate_from_history(
                snapshot_row=row,
                history_df=history_df,
                history_diag=history_diag,
                profile=profile_config,
                snapshot_source=snapshot_source,
            )
            if candidate is None:
                history_diag_rollup["skipped_for_history"] += 1
                continue
            evaluated_candidates.append(candidate)

        if not evaluated_candidates:
            raise ValueError("详细评估阶段未留下有效候选，请检查历史数据或放宽扫描条件")

        self._apply_relative_strength(evaluated_candidates)
        self._apply_base_scores(evaluated_candidates, profile=profile_config)

        sector_context = self._load_sector_context()
        board_target_count = max(profile_config.sector_context_limit, resolved_shortlist_size * 2)
        self._apply_board_context(
            candidates=sorted(
                evaluated_candidates,
                key=lambda item: float(item.get("_base_score", 0.0)),
                reverse=True,
            )[:board_target_count],
            sector_context=sector_context,
        )
        self._finalize_candidates(evaluated_candidates)

        ranked_candidates = sorted(
            evaluated_candidates,
            key=lambda item: (-float(item.get("score", 0.0)), str(item.get("symbol", ""))),
        )
        shortlist = ranked_candidates[:resolved_shortlist_size]
        for rank, candidate in enumerate(shortlist, start=1):
            candidate["rank"] = rank
        shortlist, ai_interpretation_diag = self.ai_service.interpret_shortlist(
            profile=profile_config,
            candidates=shortlist,
        )
        shortlisted_codes = [str(item["symbol"]) for item in shortlist]

        run_completed_at = datetime.now()
        headline = self._build_headline(shortlist)
        scoring_notes = self._build_scoring_notes()
        coverage_summary = self._build_coverage_summary(
            input_universe_size=int(len(stock_list)),
            eligible_after_universe_fetch=int(universe_diag.get("merged_size") or len(universe_df)),
            eligible_after_liquidity_filter=int(len(universe_df)),
            eligible_after_data_availability_filter=int(len(evaluated_candidates)),
            ranked_candidate_count=int(len(ranked_candidates)),
            shortlisted_count=int(len(shortlist)),
            excluded_reason_counts={
                "filtered_by_profile_constraints": int(
                    sum(int(value or 0) for value in (universe_diag.get("exclusion_stats") or {}).values())
                ),
                "missing_history": int(history_diag_rollup.get("skipped_for_history") or 0),
            },
        )
        provider_diagnostics = self._build_provider_diagnostics(
            configured_primary_provider=snapshot_source,
            quote_source_used=snapshot_source,
            snapshot_source_used=snapshot_source,
            history_source_used=self._history_source_summary(history_source_counts),
            attempt_groups=[
                universe_resolution.get("attempts") or [],
                snapshot_resolution.get("attempts") or [],
            ],
            history_source_counts=history_source_counts,
            missing_data_symbol_count=int(history_diag_rollup.get("skipped_for_history") or 0),
            additional_providers=[stock_list_source],
        )
        diagnostics = {
            "market": profile_config.market,
            "profile": profile_config.key,
            "profile_label": profile_config.label,
            "stock_list_source": stock_list_source,
            "snapshot_source": snapshot_source,
            "history_mode": "local_first",
            "history_stats": history_diag_rollup,
            "sector_context": sector_context,
            "universe_filter_stats": universe_diag,
            "coverage_summary": coverage_summary,
            "provider_diagnostics": provider_diagnostics,
            "scanner_data": {
                "universe_resolution": self._public_resolution_diagnostics(universe_resolution),
                "snapshot_resolution": self._public_resolution_diagnostics(snapshot_resolution),
                "degraded_mode_used": bool(snapshot_resolution.get("degraded_mode_used")),
            },
            "ai_interpretation": ai_interpretation_diag,
            "run_duration_seconds": round((run_completed_at - run_started_at).total_seconds(), 2),
        }
        source_summary = self._build_source_summary(
            universe_source=stock_list_source,
            snapshot_source=snapshot_source,
            degraded_mode_used=bool(snapshot_resolution.get("degraded_mode_used")),
            universe_resolution=universe_resolution,
            snapshot_resolution=snapshot_resolution,
        )

        run_model = MarketScannerRun(
            owner_id=resolved_owner_id,
            scope=normalized_scope,
            market=profile_config.market,
            profile=profile_config.key,
            universe_name=profile_config.universe_name,
            status="completed",
            shortlist_size=len(shortlist),
            universe_size=int(len(universe_df)),
            preselected_size=int(len(preselected_df)),
            evaluated_size=int(len(evaluated_candidates)),
            run_at=run_started_at,
            completed_at=run_completed_at,
            source_summary=source_summary,
            summary_json=json.dumps(
                {
                    "headline": headline,
                    "profile_label": profile_config.label,
                    "shortlisted_codes": shortlisted_codes,
                },
                ensure_ascii=False,
            ),
            diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
            universe_notes_json=json.dumps(universe_notes, ensure_ascii=False),
            scoring_notes_json=json.dumps(scoring_notes, ensure_ascii=False),
        )
        candidate_models = [
            self._candidate_dict_to_model(candidate, run_started_at=run_started_at)
            for candidate in shortlist
        ]
        saved_run = self.repo.save_run_with_candidates(run=run_model, candidates=candidate_models)

        response_shortlist = []
        for candidate in shortlist:
            candidate["scan_timestamp"] = run_started_at.isoformat()
            candidate["appeared_in_recent_runs"] = self.repo.count_recent_symbol_mentions(
                symbol=str(candidate["symbol"]),
                market=profile_config.market,
                profile=profile_config.key,
                exclude_run_id=saved_run.id,
                recent_run_limit=profile_config.recent_run_limit,
                scope=normalized_scope,
                owner_id=resolved_owner_id,
            )
            response_shortlist.append(self._public_candidate_dict(candidate))

        return {
            "id": saved_run.id,
            "market": profile_config.market,
            "profile": profile_config.key,
            "profile_label": profile_config.label,
            "status": "completed",
            "run_at": run_started_at.isoformat(),
            "completed_at": run_completed_at.isoformat(),
            "universe_name": profile_config.universe_name,
            "shortlist_size": len(response_shortlist),
            "universe_size": int(len(universe_df)),
            "preselected_size": int(len(preselected_df)),
            "evaluated_size": int(len(evaluated_candidates)),
            "source_summary": source_summary,
            "headline": headline,
            "universe_notes": universe_notes,
            "scoring_notes": scoring_notes,
            "diagnostics": diagnostics,
            "shortlist": response_shortlist,
        }

    def _run_us_scan(
        self,
        *,
        profile_config: ScannerMarketProfile,
        run_started_at: datetime,
        resolved_shortlist_size: int,
        resolved_universe_limit: int,
        resolved_detail_limit: int,
        scope: str,
        owner_id: Optional[str],
    ) -> Dict[str, Any]:
        universe_resolution = self._resolve_us_stock_universe(profile=profile_config)
        universe_symbols = universe_resolution.get("data") or []
        universe_source = str(universe_resolution.get("source") or "unknown")

        if not universe_symbols:
            failure_diagnostics = {
                "reason_code": str(universe_resolution.get("error_code") or "us_universe_unavailable"),
                "universe_resolution": self._public_resolution_diagnostics(universe_resolution),
                "snapshot_resolution": {
                    "source": "optional_us_realtime_quote",
                    "attempts": [],
                },
            }
            raise ScannerRuntimeError(
                str(universe_resolution.get("error_code") or "us_universe_unavailable"),
                str(universe_resolution.get("error_message") or "美股 scanner universe 不可用。"),
                diagnostics=failure_diagnostics,
                source_summary=self._build_source_summary(
                    universe_source=universe_source,
                    snapshot_source="optional_us_realtime_quote",
                    degraded_mode_used=False,
                    universe_resolution=universe_resolution,
                    snapshot_resolution={"source": "optional_us_realtime_quote", "attempts": []},
                ),
            )

        benchmark_context = self._load_us_benchmark_context(profile=profile_config)
        universe_df, universe_notes, universe_diag, history_cache = self._build_us_universe(
            symbols=universe_symbols,
            profile=profile_config,
            universe_limit=resolved_universe_limit,
            benchmark_context=benchmark_context,
        )
        coverage_strategy = str(universe_resolution.get("coverage_strategy") or "local_only")
        supplemented_seed_count = int(universe_resolution.get("supplemented_seed_count") or 0)
        local_symbol_count = int(universe_resolution.get("local_symbol_count") or 0)
        if supplemented_seed_count > 0:
            if coverage_strategy == "seed_only":
                universe_notes.append(
                    f"当前未发现足够的本地 US universe，已回退到受控的 liquid seed universe（{supplemented_seed_count} 只）补足首版覆盖。"
                )
            else:
                universe_notes.append(
                    f"本次在 {local_symbol_count} 只本地可用 US symbol 之外，额外补入 {supplemented_seed_count} 只受控 liquid seed 标的，避免候选池过窄。"
                )
        if universe_df.empty:
            raise ValueError("扫描宇宙为空，无法生成候选名单")

        preselected_df = self._compute_us_pre_rank(universe_df).head(resolved_detail_limit).reset_index(drop=True)
        quote_diag_rollup = {
            "attempted_candidates": 0,
            "available_candidates": 0,
            "unavailable_candidates": 0,
            "sources": [],
            "provider_attempts": {},
        }
        evaluated_candidates: List[Dict[str, Any]] = []
        for row in preselected_df.to_dict("records"):
            symbol = str(row["code"])
            history_df = history_cache["frames"].get(symbol, pd.DataFrame())
            history_diag = history_cache["diagnostics"].get(symbol, {})
            quote_context = self._load_us_realtime_quote_context(symbol=symbol, reference_close=row.get("close"))
            quote_diag_rollup["attempted_candidates"] += 1
            if quote_context.get("available"):
                quote_diag_rollup["available_candidates"] += 1
            else:
                quote_diag_rollup["unavailable_candidates"] += 1
            source_name = str(quote_context.get("source") or "").strip()
            if source_name and source_name not in quote_diag_rollup["sources"]:
                quote_diag_rollup["sources"].append(source_name)
            for trace_item in quote_context.get("trace") or []:
                if not isinstance(trace_item, dict):
                    continue
                provider_name = str(trace_item.get("provider") or "").strip()
                if not provider_name or provider_name in {"market_route", "market_realtime"}:
                    continue
                provider_stats = quote_diag_rollup["provider_attempts"].setdefault(
                    provider_name,
                    {
                        "attempts": 0,
                        "successes": 0,
                        "failures": 0,
                        "skipped": 0,
                    },
                )
                provider_stats["attempts"] += 1
                action_name = str(trace_item.get("action") or "").strip().lower()
                if action_name == "succeeded":
                    provider_stats["successes"] += 1
                elif action_name == "skipped":
                    provider_stats["skipped"] += 1
                elif action_name == "failed":
                    provider_stats["failures"] += 1

            candidate = self._build_us_candidate_from_history(
                universe_row=row,
                history_df=history_df,
                history_diag=history_diag,
                quote_context=quote_context,
                benchmark_context=benchmark_context,
                profile=profile_config,
            )
            if candidate is None:
                continue
            evaluated_candidates.append(candidate)

        if not evaluated_candidates:
            raise ValueError("详细评估阶段未留下有效候选，请检查历史数据、流动性过滤条件或本地 US universe。")

        self._apply_relative_strength(evaluated_candidates)
        self._apply_us_scores(evaluated_candidates, profile=profile_config)
        self._finalize_us_candidates(evaluated_candidates)

        ranked_candidates = sorted(
            evaluated_candidates,
            key=lambda item: (-float(item.get("score", 0.0)), str(item.get("symbol", ""))),
        )
        shortlist = ranked_candidates[:resolved_shortlist_size]
        for rank, candidate in enumerate(shortlist, start=1):
            candidate["rank"] = rank
        shortlist, ai_interpretation_diag = self.ai_service.interpret_shortlist(
            profile=profile_config,
            candidates=shortlist,
        )
        shortlisted_codes = [str(item["symbol"]) for item in shortlist]

        provider_attempts = quote_diag_rollup.get("provider_attempts") or {}
        quote_attempts = [
            {
                "fetcher": provider_name,
                "status": (
                    "success"
                    if stats.get("successes")
                    else "failed"
                    if stats.get("failures")
                    else "skipped"
                ),
                "rows": int(stats.get("successes") or 0),
                "reason_code": None if stats.get("successes") else "no_live_quote_context",
            }
            for provider_name, stats in provider_attempts.items()
        ] or [
            {
                "fetcher": "us_live_quote",
                "status": "failed",
                "rows": 0,
                "reason_code": "no_live_quote_context",
            }
        ]
        snapshot_resolution = {
            "source": (
                ",".join(quote_diag_rollup["sources"])
                if quote_diag_rollup["sources"]
                else "history_only_us_scan"
            ),
            "attempts": quote_attempts,
            "degraded_mode_used": False,
        }

        run_completed_at = datetime.now()
        headline = self._build_headline(shortlist, market=profile_config.market)
        scoring_notes = self._build_scoring_notes(profile=profile_config)
        history_source_counts = {}
        for item in (history_cache.get("diagnostics") or {}).values():
            if not isinstance(item, dict):
                continue
            source_name = str(item.get("source") or "").strip()
            if source_name:
                history_source_counts[source_name] = history_source_counts.get(source_name, 0) + 1
        coverage_summary = self._build_coverage_summary(
            input_universe_size=int(len(universe_symbols)),
            eligible_after_universe_fetch=int(universe_diag.get("raw_symbol_count") or len(universe_symbols)),
            eligible_after_liquidity_filter=int(len(universe_df)),
            eligible_after_data_availability_filter=int(len(evaluated_candidates)),
            ranked_candidate_count=int(len(ranked_candidates)),
            shortlisted_count=int(len(shortlist)),
            excluded_reason_counts={
                "filtered_by_profile_constraints": int(
                    sum(int(value or 0) for value in (universe_diag.get("exclusion_stats") or {}).values())
                ),
                "missing_quote_or_snapshot": int(quote_diag_rollup.get("unavailable_candidates") or 0),
                "missing_history": int((history_cache.get("history_rollup") or {}).get("skipped_for_history") or 0),
            },
        )
        provider_diagnostics = self._build_provider_diagnostics(
            configured_primary_provider=universe_source,
            quote_source_used=str(snapshot_resolution["source"]),
            snapshot_source_used=str(snapshot_resolution["source"]),
            history_source_used=self._history_source_summary(history_source_counts),
            attempt_groups=[
                universe_resolution.get("attempts") or [],
                snapshot_resolution.get("attempts") or [],
            ],
            history_source_counts=history_source_counts,
            missing_data_symbol_count=int(quote_diag_rollup.get("unavailable_candidates") or 0)
            + int((history_cache.get("history_rollup") or {}).get("skipped_for_history") or 0),
            additional_providers=quote_diag_rollup.get("sources") or [],
        )
        diagnostics = {
            "market": profile_config.market,
            "profile": profile_config.key,
            "profile_label": profile_config.label,
            "stock_list_source": universe_source,
            "snapshot_source": snapshot_resolution["source"],
            "history_mode": "local_us_first",
            "history_stats": history_cache["history_rollup"],
            "live_quote_stats": quote_diag_rollup,
            "benchmark_context": benchmark_context,
            "universe_filter_stats": {
                **universe_diag,
                "coverage_strategy": coverage_strategy,
                "local_symbol_count": local_symbol_count,
                "supplemented_seed_count": supplemented_seed_count,
                "resolved_symbol_count": int(universe_resolution.get("final_symbol_count") or len(universe_symbols)),
            },
            "coverage_summary": coverage_summary,
            "provider_diagnostics": provider_diagnostics,
            "scanner_data": {
                "universe_resolution": self._public_resolution_diagnostics(universe_resolution),
                "snapshot_resolution": snapshot_resolution,
                "degraded_mode_used": False,
            },
            "ai_interpretation": ai_interpretation_diag,
            "run_duration_seconds": round((run_completed_at - run_started_at).total_seconds(), 2),
        }
        source_summary = self._build_source_summary(
            universe_source=universe_source,
            snapshot_source=str(snapshot_resolution["source"]),
            degraded_mode_used=False,
            universe_resolution=universe_resolution,
            snapshot_resolution=snapshot_resolution,
        )

        run_model = MarketScannerRun(
            owner_id=owner_id,
            scope=scope,
            market=profile_config.market,
            profile=profile_config.key,
            universe_name=profile_config.universe_name,
            status="completed",
            shortlist_size=len(shortlist),
            universe_size=int(len(universe_df)),
            preselected_size=int(len(preselected_df)),
            evaluated_size=int(len(evaluated_candidates)),
            run_at=run_started_at,
            completed_at=run_completed_at,
            source_summary=source_summary,
            summary_json=json.dumps(
                {
                    "headline": headline,
                    "profile_label": profile_config.label,
                    "shortlisted_codes": shortlisted_codes,
                },
                ensure_ascii=False,
            ),
            diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
            universe_notes_json=json.dumps(universe_notes, ensure_ascii=False),
            scoring_notes_json=json.dumps(scoring_notes, ensure_ascii=False),
        )
        candidate_models = [
            self._candidate_dict_to_model(candidate, run_started_at=run_started_at)
            for candidate in shortlist
        ]
        saved_run = self.repo.save_run_with_candidates(run=run_model, candidates=candidate_models)

        response_shortlist = []
        for candidate in shortlist:
            candidate["scan_timestamp"] = run_started_at.isoformat()
            candidate["appeared_in_recent_runs"] = self.repo.count_recent_symbol_mentions(
                symbol=str(candidate["symbol"]),
                market=profile_config.market,
                profile=profile_config.key,
                exclude_run_id=saved_run.id,
                recent_run_limit=profile_config.recent_run_limit,
                scope=scope,
                owner_id=owner_id,
            )
            response_shortlist.append(self._public_candidate_dict(candidate))

        return {
            "id": saved_run.id,
            "market": profile_config.market,
            "profile": profile_config.key,
            "profile_label": profile_config.label,
            "status": "completed",
            "run_at": run_started_at.isoformat(),
            "completed_at": run_completed_at.isoformat(),
            "universe_name": profile_config.universe_name,
            "shortlist_size": len(response_shortlist),
            "universe_size": int(len(universe_df)),
            "preselected_size": int(len(preselected_df)),
            "evaluated_size": int(len(evaluated_candidates)),
            "source_summary": source_summary,
            "headline": headline,
            "universe_notes": universe_notes,
            "scoring_notes": scoring_notes,
            "diagnostics": diagnostics,
            "shortlist": response_shortlist,
        }

    def _run_hk_scan(
        self,
        *,
        profile_config: ScannerMarketProfile,
        run_started_at: datetime,
        resolved_shortlist_size: int,
        resolved_universe_limit: int,
        resolved_detail_limit: int,
        scope: str,
        owner_id: Optional[str],
    ) -> Dict[str, Any]:
        universe_resolution = self._resolve_hk_stock_universe(profile=profile_config)
        universe_symbols = universe_resolution.get("data") or []
        universe_source = str(universe_resolution.get("source") or "unknown")

        if not universe_symbols:
            failure_diagnostics = {
                "reason_code": str(universe_resolution.get("error_code") or "hk_universe_unavailable"),
                "universe_resolution": self._public_resolution_diagnostics(universe_resolution),
                "snapshot_resolution": {
                    "source": "optional_hk_realtime_quote",
                    "attempts": [],
                },
            }
            raise ScannerRuntimeError(
                str(universe_resolution.get("error_code") or "hk_universe_unavailable"),
                str(universe_resolution.get("error_message") or "港股 scanner universe 不可用。"),
                diagnostics=failure_diagnostics,
                source_summary=self._build_source_summary(
                    universe_source=universe_source,
                    snapshot_source="optional_hk_realtime_quote",
                    degraded_mode_used=False,
                    universe_resolution=universe_resolution,
                    snapshot_resolution={"source": "optional_hk_realtime_quote", "attempts": []},
                ),
            )

        benchmark_context = self._load_hk_benchmark_context(profile=profile_config)
        universe_df, universe_notes, universe_diag, history_cache = self._build_hk_universe(
            symbols=universe_symbols,
            profile=profile_config,
            universe_limit=resolved_universe_limit,
            benchmark_context=benchmark_context,
        )
        coverage_strategy = str(universe_resolution.get("coverage_strategy") or "local_only")
        supplemented_seed_count = int(universe_resolution.get("supplemented_seed_count") or 0)
        local_symbol_count = int(universe_resolution.get("local_symbol_count") or 0)
        if supplemented_seed_count > 0:
            if coverage_strategy == "seed_only":
                universe_notes.append(
                    f"当前未发现足够的本地港股 universe，已回退到受控的 HK liquid seed universe（{supplemented_seed_count} 只）补足首版覆盖。"
                )
            else:
                universe_notes.append(
                    f"本次在 {local_symbol_count} 只本地可用 HK symbol 之外，额外补入 {supplemented_seed_count} 只受控 liquid seed 标的，避免候选池过窄。"
                )
        if universe_df.empty:
            raise ValueError("港股扫描宇宙为空，无法生成候选名单")

        preselected_df = self._compute_hk_pre_rank(universe_df).head(resolved_detail_limit).reset_index(drop=True)
        quote_diag_rollup = {
            "attempted_candidates": 0,
            "available_candidates": 0,
            "unavailable_candidates": 0,
            "sources": [],
            "provider_attempts": {},
        }
        evaluated_candidates: List[Dict[str, Any]] = []
        for row in preselected_df.to_dict("records"):
            symbol = str(row["code"])
            history_df = history_cache["frames"].get(symbol, pd.DataFrame())
            history_diag = history_cache["diagnostics"].get(symbol, {})
            quote_context = self._load_hk_realtime_quote_context(symbol=symbol, reference_close=row.get("close"))
            quote_diag_rollup["attempted_candidates"] += 1
            if quote_context.get("available"):
                quote_diag_rollup["available_candidates"] += 1
            else:
                quote_diag_rollup["unavailable_candidates"] += 1
            source_name = str(quote_context.get("source") or "").strip()
            if source_name and source_name not in quote_diag_rollup["sources"]:
                quote_diag_rollup["sources"].append(source_name)
            for trace_item in quote_context.get("trace") or []:
                if not isinstance(trace_item, dict):
                    continue
                provider_name = str(trace_item.get("provider") or "").strip()
                if not provider_name or provider_name in {"market_route", "market_realtime"}:
                    continue
                provider_stats = quote_diag_rollup["provider_attempts"].setdefault(
                    provider_name,
                    {
                        "attempts": 0,
                        "successes": 0,
                        "failures": 0,
                        "skipped": 0,
                    },
                )
                provider_stats["attempts"] += 1
                action_name = str(trace_item.get("action") or "").strip().lower()
                if action_name == "succeeded":
                    provider_stats["successes"] += 1
                elif action_name == "skipped":
                    provider_stats["skipped"] += 1
                elif action_name == "failed":
                    provider_stats["failures"] += 1

            candidate = self._build_hk_candidate_from_history(
                universe_row=row,
                history_df=history_df,
                history_diag=history_diag,
                quote_context=quote_context,
                benchmark_context=benchmark_context,
                profile=profile_config,
            )
            if candidate is None:
                continue
            evaluated_candidates.append(candidate)

        if not evaluated_candidates:
            raise ValueError("港股详细评估阶段未留下有效候选，请检查历史数据、流动性过滤条件或 HK seed universe。")

        self._apply_relative_strength(evaluated_candidates)
        self._apply_hk_scores(evaluated_candidates, profile=profile_config)
        self._finalize_hk_candidates(evaluated_candidates)

        ranked_candidates = sorted(
            evaluated_candidates,
            key=lambda item: (-float(item.get("score", 0.0)), str(item.get("symbol", ""))),
        )
        shortlist = ranked_candidates[:resolved_shortlist_size]
        for rank, candidate in enumerate(shortlist, start=1):
            candidate["rank"] = rank
        shortlist, ai_interpretation_diag = self.ai_service.interpret_shortlist(
            profile=profile_config,
            candidates=shortlist,
        )
        shortlisted_codes = [str(item["symbol"]) for item in shortlist]

        provider_attempts = quote_diag_rollup.get("provider_attempts") or {}
        quote_attempts = [
            {
                "fetcher": provider_name,
                "status": (
                    "success"
                    if stats.get("successes")
                    else "failed"
                    if stats.get("failures")
                    else "skipped"
                ),
                "rows": int(stats.get("successes") or 0),
                "reason_code": None if stats.get("successes") else "no_live_quote_context",
            }
            for provider_name, stats in provider_attempts.items()
        ] or [
            {
                "fetcher": "hk_live_quote",
                "status": "failed",
                "rows": 0,
                "reason_code": "no_live_quote_context",
            }
        ]
        snapshot_resolution = {
            "source": (
                ",".join(quote_diag_rollup["sources"])
                if quote_diag_rollup["sources"]
                else "history_only_hk_scan"
            ),
            "attempts": quote_attempts,
            "degraded_mode_used": False,
        }

        run_completed_at = datetime.now()
        headline = self._build_headline(shortlist, market=profile_config.market)
        scoring_notes = self._build_scoring_notes(profile=profile_config)
        history_source_counts = {}
        for item in (history_cache.get("diagnostics") or {}).values():
            if not isinstance(item, dict):
                continue
            source_name = str(item.get("source") or "").strip()
            if source_name:
                history_source_counts[source_name] = history_source_counts.get(source_name, 0) + 1
        coverage_summary = self._build_coverage_summary(
            input_universe_size=int(len(universe_symbols)),
            eligible_after_universe_fetch=int(universe_diag.get("raw_symbol_count") or len(universe_symbols)),
            eligible_after_liquidity_filter=int(len(universe_df)),
            eligible_after_data_availability_filter=int(len(evaluated_candidates)),
            ranked_candidate_count=int(len(ranked_candidates)),
            shortlisted_count=int(len(shortlist)),
            excluded_reason_counts={
                "filtered_by_profile_constraints": int(
                    sum(int(value or 0) for value in (universe_diag.get("exclusion_stats") or {}).values())
                ),
                "missing_quote_or_snapshot": int(quote_diag_rollup.get("unavailable_candidates") or 0),
                "missing_history": int((history_cache.get("history_rollup") or {}).get("skipped_for_history") or 0),
            },
        )
        provider_diagnostics = self._build_provider_diagnostics(
            configured_primary_provider=universe_source,
            quote_source_used=str(snapshot_resolution["source"]),
            snapshot_source_used=str(snapshot_resolution["source"]),
            history_source_used=self._history_source_summary(history_source_counts),
            attempt_groups=[
                universe_resolution.get("attempts") or [],
                snapshot_resolution.get("attempts") or [],
            ],
            history_source_counts=history_source_counts,
            missing_data_symbol_count=int(quote_diag_rollup.get("unavailable_candidates") or 0)
            + int((history_cache.get("history_rollup") or {}).get("skipped_for_history") or 0),
            additional_providers=quote_diag_rollup.get("sources") or [],
        )
        diagnostics = {
            "market": profile_config.market,
            "profile": profile_config.key,
            "profile_label": profile_config.label,
            "stock_list_source": universe_source,
            "snapshot_source": snapshot_resolution["source"],
            "history_mode": "local_hk_first",
            "history_stats": history_cache["history_rollup"],
            "live_quote_stats": quote_diag_rollup,
            "benchmark_context": benchmark_context,
            "universe_filter_stats": {
                **universe_diag,
                "coverage_strategy": coverage_strategy,
                "local_symbol_count": local_symbol_count,
                "supplemented_seed_count": supplemented_seed_count,
                "resolved_symbol_count": int(universe_resolution.get("final_symbol_count") or len(universe_symbols)),
            },
            "coverage_summary": coverage_summary,
            "provider_diagnostics": provider_diagnostics,
            "scanner_data": {
                "universe_resolution": self._public_resolution_diagnostics(universe_resolution),
                "snapshot_resolution": snapshot_resolution,
                "degraded_mode_used": False,
            },
            "ai_interpretation": ai_interpretation_diag,
            "run_duration_seconds": round((run_completed_at - run_started_at).total_seconds(), 2),
        }
        source_summary = self._build_source_summary(
            universe_source=universe_source,
            snapshot_source=str(snapshot_resolution["source"]),
            degraded_mode_used=False,
            universe_resolution=universe_resolution,
            snapshot_resolution=snapshot_resolution,
        )

        run_model = MarketScannerRun(
            owner_id=owner_id,
            scope=scope,
            market=profile_config.market,
            profile=profile_config.key,
            universe_name=profile_config.universe_name,
            status="completed",
            shortlist_size=len(shortlist),
            universe_size=int(len(universe_df)),
            preselected_size=int(len(preselected_df)),
            evaluated_size=int(len(evaluated_candidates)),
            run_at=run_started_at,
            completed_at=run_completed_at,
            source_summary=source_summary,
            summary_json=json.dumps(
                {
                    "headline": headline,
                    "profile_label": profile_config.label,
                    "shortlisted_codes": shortlisted_codes,
                },
                ensure_ascii=False,
            ),
            diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
            universe_notes_json=json.dumps(universe_notes, ensure_ascii=False),
            scoring_notes_json=json.dumps(scoring_notes, ensure_ascii=False),
        )
        candidate_models = [
            self._candidate_dict_to_model(candidate, run_started_at=run_started_at)
            for candidate in shortlist
        ]
        saved_run = self.repo.save_run_with_candidates(run=run_model, candidates=candidate_models)

        response_shortlist = []
        for candidate in shortlist:
            candidate["scan_timestamp"] = run_started_at.isoformat()
            candidate["appeared_in_recent_runs"] = self.repo.count_recent_symbol_mentions(
                symbol=str(candidate["symbol"]),
                market=profile_config.market,
                profile=profile_config.key,
                exclude_run_id=saved_run.id,
                recent_run_limit=profile_config.recent_run_limit,
                scope=scope,
                owner_id=owner_id,
            )
            response_shortlist.append(self._public_candidate_dict(candidate))

        return {
            "id": saved_run.id,
            "market": profile_config.market,
            "profile": profile_config.key,
            "profile_label": profile_config.label,
            "status": "completed",
            "run_at": run_started_at.isoformat(),
            "completed_at": run_completed_at.isoformat(),
            "universe_name": profile_config.universe_name,
            "shortlist_size": len(response_shortlist),
            "universe_size": int(len(universe_df)),
            "preselected_size": int(len(preselected_df)),
            "evaluated_size": int(len(evaluated_candidates)),
            "source_summary": source_summary,
            "headline": headline,
            "universe_notes": universe_notes,
            "scoring_notes": scoring_notes,
            "diagnostics": diagnostics,
            "shortlist": response_shortlist,
        }

    def _resolve_hk_stock_universe(self, *, profile: ScannerMarketProfile) -> Dict[str, Any]:
        attempts: List[Dict[str, Any]] = []
        combined_symbols: List[str] = []
        seen_symbols = set()
        source_parts: List[str] = []

        def _merge_symbols(symbols: Sequence[str], *, source_name: str) -> int:
            added = 0
            for raw_symbol in symbols:
                symbol = normalize_stock_code(str(raw_symbol or "")).upper()
                if not symbol or symbol in seen_symbols or not _is_hk_scanner_symbol(symbol):
                    continue
                seen_symbols.add(symbol)
                combined_symbols.append(symbol)
                added += 1
            if added > 0 and source_name not in source_parts:
                source_parts.append(source_name)
            return added

        db_symbols = self._load_local_hk_universe_from_db()
        if db_symbols:
            added = _merge_symbols(db_symbols, source_name="local_db_hk_history")
            attempts.append(
                {
                    "fetcher": "local_db_hk_history",
                    "status": "success",
                    "rows": int(len(db_symbols)),
                    "added_rows": int(added),
                }
            )
        else:
            attempts.append(
                {
                    "fetcher": "local_db_hk_history",
                    "status": "failed",
                    "reason_code": "local_db_hk_universe_missing",
                }
            )

        local_symbol_count = int(len(combined_symbols))
        target_symbol_count = min(
            max(int(profile.detail_limit or 0), MIN_US_SCANNER_SEED_TARGET),
            MAX_US_SCANNER_SEED_TARGET,
        )
        supplement_pool = [symbol for symbol in CURATED_HK_LIQUID_SEED_SYMBOLS if symbol not in seen_symbols]
        required = max(0, target_symbol_count - len(combined_symbols))
        supplement_symbols = supplement_pool[:required]
        supplemented_seed_count = _merge_symbols(
            supplement_symbols,
            source_name="curated_hk_liquid_seed",
        )
        if supplemented_seed_count:
            attempts.append(
                {
                    "fetcher": "curated_hk_liquid_seed",
                    "status": "success",
                    "rows": int(supplemented_seed_count),
                    "reason_code": "coverage_supplement",
                }
            )

        if combined_symbols:
            coverage_strategy = (
                "seed_only"
                if local_symbol_count == 0 and supplemented_seed_count > 0
                else "seed_supplemented"
                if supplemented_seed_count > 0
                else "local_only"
            )
            return {
                "success": True,
                "source": "+".join(source_parts) if source_parts else "curated_hk_liquid_seed",
                "data": combined_symbols,
                "attempts": attempts,
                "local_symbol_count": local_symbol_count,
                "supplemented_seed_count": int(supplemented_seed_count),
                "final_symbol_count": int(len(combined_symbols)),
                "target_symbol_count": int(target_symbol_count),
                "coverage_strategy": coverage_strategy,
            }

        return {
            "success": False,
            "source": None,
            "data": [],
            "attempts": attempts,
            "error_code": "hk_universe_unavailable",
            "error_message": "未发现可扫描的港股 universe。请准备本地 HK 历史，或配置 Twelve Data 以支持 HK seed universe 历史补数。",
        }

    def _load_local_hk_universe_from_db(self) -> List[str]:
        with self.db.get_session() as session:
            rows = session.execute(select(StockDaily.code).distinct()).all()
        symbols = sorted(
            {
                normalize_stock_code(str(row[0] or "")).upper()
                for row in rows
                if row and row[0] and _is_hk_scanner_symbol(str(row[0]))
            }
        )
        return symbols

    def _load_hk_benchmark_context(self, *, profile: ScannerMarketProfile) -> Dict[str, Any]:
        benchmark_code = normalize_stock_code(str(profile.benchmark_code or DEFAULT_HK_SCANNER_BENCHMARK_CODE)).upper()
        history_df, history_diag = self._load_history_local_first(code=benchmark_code, profile=profile)
        features = self._extract_history_features(history_df)
        return {
            "benchmark_code": benchmark_code,
            "available": bool(features),
            "ret_20d": features.get("ret_20d"),
            "ret_60d": features.get("ret_60d"),
            "history_source": history_diag.get("source"),
            "latest_trade_date": features.get("last_trade_date"),
        }

    def _build_hk_universe(
        self,
        *,
        symbols: Sequence[str],
        profile: ScannerMarketProfile,
        universe_limit: int,
        benchmark_context: Dict[str, Any],
    ) -> Tuple[pd.DataFrame, List[str], Dict[str, Any], Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        history_frames: Dict[str, pd.DataFrame] = {}
        history_diags: Dict[str, Dict[str, Any]] = {}
        history_rollup = {
            "local_hits": 0,
            "network_fetches": 0,
            "network_failures": 0,
            "partial_local_fallbacks": 0,
            "skipped_for_history": 0,
        }
        exclusion_stats = {
            "insufficient_history": 0,
            "low_price": 0,
            "low_avg_amount_20": 0,
            "low_avg_volume_20": 0,
        }

        benchmark_ret_20d = _safe_float(benchmark_context.get("ret_20d"), default=np.nan)
        benchmark_code = str(benchmark_context.get("benchmark_code") or "").upper()

        for raw_symbol in symbols:
            symbol = normalize_stock_code(str(raw_symbol or "")).upper()
            if not _is_hk_scanner_symbol(symbol):
                continue
            if benchmark_code and symbol == benchmark_code:
                continue

            history_df, history_diag = self._load_history_local_first(code=symbol, profile=profile)
            history_frames[symbol] = history_df
            history_diags[symbol] = history_diag

            history_source = str(history_diag.get("source") or "")
            if history_source == "local_db":
                history_rollup["local_hits"] += 1
            elif history_diag.get("network_used"):
                history_rollup["network_fetches"] += 1
            if history_diag.get("network_failed"):
                history_rollup["network_failures"] += 1
            if history_diag.get("partial_local_fallback"):
                history_rollup["partial_local_fallbacks"] += 1

            features = self._extract_history_features(history_df)
            if not features:
                history_rollup["skipped_for_history"] += 1
                exclusion_stats["insufficient_history"] += 1
                continue

            avg_amount_20 = _safe_float(features.get("avg_amount_20"))
            avg_volume_20 = _safe_float(features.get("avg_volume_20"))
            close = _safe_float(features.get("close"))
            if close < profile.min_price:
                exclusion_stats["low_price"] += 1
                continue
            if avg_amount_20 < profile.min_avg_amount_20:
                exclusion_stats["low_avg_amount_20"] += 1
                continue
            if avg_volume_20 < profile.min_avg_volume_20:
                exclusion_stats["low_avg_volume_20"] += 1
                continue

            benchmark_relative_20d = None
            if not np.isnan(benchmark_ret_20d):
                benchmark_relative_20d = round(_safe_float(features.get("ret_20d")) - float(benchmark_ret_20d), 2)

            rows.append(
                {
                    "code": symbol,
                    "name": symbol,
                    "price": close,
                    "close": close,
                    "change_pct": _safe_float(features.get("latest_pct_chg")),
                    "amount": avg_amount_20,
                    "avg_amount_20": avg_amount_20,
                    "avg_volume_20": avg_volume_20,
                    "volume": _safe_float(features.get("latest_volume")),
                    "amplitude": _safe_float(features.get("atr20_pct")),
                    "change_20d": _safe_float(features.get("ret_20d")),
                    "change_60d": _safe_float(features.get("ret_60d")),
                    "ret_5d": _safe_float(features.get("ret_5d")),
                    "ret_20d": _safe_float(features.get("ret_20d")),
                    "ret_60d": _safe_float(features.get("ret_60d")),
                    "ma20": _safe_float(features.get("ma20")),
                    "ma60": _safe_float(features.get("ma60")),
                    "ma20_slope_pct": _safe_float(features.get("ma20_slope_pct")),
                    "distance_to_20d_high_pct": _safe_float(features.get("distance_to_20d_high_pct")),
                    "prior_20d_high": _safe_float(features.get("prior_20d_high")),
                    "prior_10d_low": _safe_float(features.get("prior_10d_low")),
                    "volume_expansion_20": _safe_float(features.get("volume_expansion_20")),
                    "atr20_pct": _safe_float(features.get("atr20_pct")),
                    "recent_up_days_10": int(features.get("recent_up_days_10") or 0),
                    "last_trade_date": features.get("last_trade_date"),
                    "history_source": history_source,
                    "benchmark_relative_20d": benchmark_relative_20d,
                }
            )

        universe_df = pd.DataFrame(rows)
        if universe_df.empty:
            diagnostics = {
                "raw_symbol_count": int(len(symbols)),
                "final_universe_size": 0,
                "exclusion_stats": exclusion_stats,
            }
            return universe_df, [
                "港股 profile 需要本地或 Twelve Data 可补的 HK history universe，且默认先按流动性、价格与历史样本完整度过滤。",
            ], diagnostics, {
                "frames": history_frames,
                "diagnostics": history_diags,
                "history_rollup": history_rollup,
            }

        universe_df = universe_df.sort_values(
            ["avg_amount_20", "ret_20d", "ret_60d"],
            ascending=[False, False, False],
        ).head(universe_limit).reset_index(drop=True)

        universe_notes = [
            "起始池采用 local-first 的 HK history universe：优先读取本地已落库的港股日线；当本地覆盖过窄时，会补入一小组受控 liquid seed symbols，并通过 Twelve Data 做历史补数。",
            "默认先过滤低价、20 日平均成交额不足、20 日平均成交量不足或历史样本过短的标的。",
            f"本版默认保留流动性与趋势条件更好的 {universe_limit} 只港股候选进入详细评估。",
            "若实时 quote 不可用，HK profile 仍会给出纯历史视角的 shortlist，并显式提示开盘上下文置信度较低。",
        ]
        diagnostics = {
            "raw_symbol_count": int(len(symbols)),
            "final_universe_size": int(len(universe_df)),
            "exclusion_stats": exclusion_stats,
        }
        return universe_df, universe_notes, diagnostics, {
            "frames": history_frames,
            "diagnostics": history_diags,
            "history_rollup": history_rollup,
        }

    def _compute_hk_pre_rank(self, universe_df: pd.DataFrame) -> pd.DataFrame:
        df = universe_df.copy()
        max_amount = max(float(df["avg_amount_20"].max()), 1.0)
        max_volume = max(float(df["avg_volume_20"].max()), 1.0)
        df["liquidity_score"] = np.log1p(df["avg_amount_20"].clip(lower=0.0)) / np.log1p(max_amount)
        df["volume_score"] = np.log1p(df["avg_volume_20"].clip(lower=0.0)) / np.log1p(max_volume)
        df["trend_context_score"] = df["ret_60d"].map(lambda value: _clamp((float(value) + 4.0) / 32.0, 0.0, 1.0))
        df["momentum_score"] = df["ret_20d"].map(lambda value: _clamp((float(value) + 3.0) / 18.0, 0.0, 1.0))
        df["range_quality_score"] = df["atr20_pct"].map(lambda value: 1.0 - _clamp(abs(float(value) - 4.2) / 4.8, 0.0, 1.0))
        df["benchmark_relative_score"] = df["benchmark_relative_20d"].fillna(0.0).map(
            lambda value: _clamp((float(value) + 3.0) / 14.0, 0.0, 1.0)
        )
        df["pre_rank_score"] = (
            df["liquidity_score"] * 26.0
            + df["volume_score"] * 14.0
            + df["trend_context_score"] * 18.0
            + df["momentum_score"] * 16.0
            + df["range_quality_score"] * 12.0
            + df["benchmark_relative_score"] * 14.0
        )
        return df.sort_values(
            ["pre_rank_score", "avg_amount_20", "ret_20d", "benchmark_relative_20d"],
            ascending=[False, False, False, False],
        )

    def _load_hk_realtime_quote_context(
        self,
        *,
        symbol: str,
        reference_close: Optional[float],
    ) -> Dict[str, Any]:
        return self._load_us_realtime_quote_context(symbol=symbol, reference_close=reference_close)

    def _build_hk_candidate_from_history(
        self,
        *,
        universe_row: Dict[str, Any],
        history_df: pd.DataFrame,
        history_diag: Dict[str, Any],
        quote_context: Dict[str, Any],
        benchmark_context: Dict[str, Any],
        profile: ScannerMarketProfile,
    ) -> Optional[Dict[str, Any]]:
        return self._build_us_candidate_from_history(
            universe_row=universe_row,
            history_df=history_df,
            history_diag=history_diag,
            quote_context=quote_context,
            benchmark_context=benchmark_context,
            profile=profile,
        )

    def _resolve_us_stock_universe(self, *, profile: ScannerMarketProfile) -> Dict[str, Any]:
        attempts: List[Dict[str, Any]] = []
        combined_symbols: List[str] = []
        seen_symbols = set()
        source_parts: List[str] = []

        def _merge_symbols(symbols: Sequence[str], *, source_name: str) -> int:
            added = 0
            for raw_symbol in symbols:
                symbol = str(raw_symbol or "").strip().upper()
                if not symbol or symbol in seen_symbols or not is_us_stock_code(symbol):
                    continue
                seen_symbols.add(symbol)
                combined_symbols.append(symbol)
                added += 1
            if added > 0 and source_name not in source_parts:
                source_parts.append(source_name)
            return added

        parquet_dir = get_us_stock_parquet_dir()
        parquet_symbols = self._load_local_us_universe_from_parquet(parquet_dir)
        if parquet_symbols:
            added = _merge_symbols(parquet_symbols, source_name="local_us_parquet_dir")
            attempts.append(
                {
                    "fetcher": "local_us_parquet_dir",
                    "status": "success",
                    "rows": int(len(parquet_symbols)),
                    "added_rows": int(added),
                }
            )
        else:
            attempts.append(
                {
                    "fetcher": "local_us_parquet_dir",
                    "status": "failed",
                    "reason_code": "local_us_universe_missing",
                }
            )

        db_symbols = self._load_local_us_universe_from_db()
        if db_symbols:
            added = _merge_symbols(db_symbols, source_name="local_db_us_history")
            attempts.append(
                {
                    "fetcher": "local_db_us_history",
                    "status": "success",
                    "rows": int(len(db_symbols)),
                    "added_rows": int(added),
                }
            )
        else:
            attempts.append(
                {
                    "fetcher": "local_db_us_history",
                    "status": "failed",
                    "reason_code": "local_db_us_universe_missing",
                }
            )

        local_symbol_count = int(len(combined_symbols))
        target_symbol_count = min(
            max(int(profile.detail_limit or 0), MIN_US_SCANNER_SEED_TARGET),
            MAX_US_SCANNER_SEED_TARGET,
        )
        supplemented_seed_count = 0
        if len(combined_symbols) < target_symbol_count:
            supplement_pool = [symbol for symbol in CURATED_US_LIQUID_SEED_SYMBOLS if symbol not in seen_symbols]
            required = max(0, target_symbol_count - len(combined_symbols))
            supplement_symbols = supplement_pool[:required]
            supplemented_seed_count = _merge_symbols(
                supplement_symbols,
                source_name="curated_us_liquid_seed",
            )
            if supplemented_seed_count:
                attempts.append(
                    {
                        "fetcher": "curated_us_liquid_seed",
                        "status": "success",
                        "rows": int(supplemented_seed_count),
                        "reason_code": "coverage_supplement",
                    }
                )

        if combined_symbols:
            coverage_strategy = (
                "seed_only"
                if local_symbol_count == 0 and supplemented_seed_count > 0
                else "seed_supplemented"
                if supplemented_seed_count > 0
                else "local_only"
            )
            return {
                "success": True,
                "source": "+".join(source_parts) if source_parts else "curated_us_liquid_seed",
                "data": combined_symbols,
                "attempts": attempts,
                "path": str(parquet_dir),
                "local_symbol_count": local_symbol_count,
                "supplemented_seed_count": int(supplemented_seed_count),
                "final_symbol_count": int(len(combined_symbols)),
                "target_symbol_count": int(target_symbol_count),
                "coverage_strategy": coverage_strategy,
            }

        return {
            "success": False,
            "source": None,
            "data": [],
            "attempts": attempts,
            "error_code": "us_universe_unavailable",
            "error_message": "未发现可扫描的美股 universe。请准备 LOCAL_US_PARQUET_DIR/US_STOCK_PARQUET_DIR，或先让本地 stock_daily 落入可用的美股日线数据。",
        }

    @staticmethod
    def _load_local_us_universe_from_parquet(parquet_dir: Path) -> List[str]:
        if not parquet_dir.exists() or not parquet_dir.is_dir():
            return []
        symbols = sorted(
            {
                path.stem.upper()
                for path in parquet_dir.glob("*.parquet")
                if is_us_stock_code(path.stem.upper())
            }
        )
        return symbols

    def _load_local_us_universe_from_db(self) -> List[str]:
        with self.db.get_session() as session:
            rows = session.execute(select(StockDaily.code).distinct()).all()
        symbols = sorted(
            {
                str(row[0]).upper()
                for row in rows
                if row and row[0] and is_us_stock_code(str(row[0]).upper())
            }
        )
        return symbols

    def _load_us_benchmark_context(self, *, profile: ScannerMarketProfile) -> Dict[str, Any]:
        benchmark_code = str(profile.benchmark_code or DEFAULT_US_SCANNER_BENCHMARK_CODE).upper()
        history_df, history_diag = self._load_history_local_first(code=benchmark_code, profile=profile)
        features = self._extract_history_features(history_df)
        return {
            "benchmark_code": benchmark_code,
            "available": bool(features),
            "ret_20d": features.get("ret_20d"),
            "ret_60d": features.get("ret_60d"),
            "history_source": history_diag.get("source"),
            "latest_trade_date": features.get("last_trade_date"),
        }

    def _build_us_universe(
        self,
        *,
        symbols: Sequence[str],
        profile: ScannerMarketProfile,
        universe_limit: int,
        benchmark_context: Dict[str, Any],
    ) -> Tuple[pd.DataFrame, List[str], Dict[str, Any], Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        history_frames: Dict[str, pd.DataFrame] = {}
        history_diags: Dict[str, Dict[str, Any]] = {}
        history_rollup = {
            "local_hits": 0,
            "network_fetches": 0,
            "network_failures": 0,
            "partial_local_fallbacks": 0,
            "skipped_for_history": 0,
        }
        exclusion_stats = {
            "insufficient_history": 0,
            "low_price": 0,
            "low_avg_amount_20": 0,
            "low_avg_volume_20": 0,
        }

        benchmark_ret_20d = _safe_float(benchmark_context.get("ret_20d"), default=np.nan)
        benchmark_code = str(benchmark_context.get("benchmark_code") or "").upper()

        for raw_symbol in symbols:
            symbol = str(raw_symbol or "").strip().upper()
            if not is_us_stock_code(symbol):
                continue
            if benchmark_code and symbol == benchmark_code:
                continue

            history_df, history_diag = self._load_history_local_first(code=symbol, profile=profile)
            history_frames[symbol] = history_df
            history_diags[symbol] = history_diag

            history_source = str(history_diag.get("source") or "")
            if history_source == "local_db":
                history_rollup["local_hits"] += 1
            elif history_diag.get("network_used"):
                history_rollup["network_fetches"] += 1
            if history_diag.get("network_failed"):
                history_rollup["network_failures"] += 1
            if history_diag.get("partial_local_fallback"):
                history_rollup["partial_local_fallbacks"] += 1

            features = self._extract_history_features(history_df)
            if not features:
                history_rollup["skipped_for_history"] += 1
                exclusion_stats["insufficient_history"] += 1
                continue

            avg_amount_20 = _safe_float(features.get("avg_amount_20"))
            avg_volume_20 = _safe_float(features.get("avg_volume_20"))
            close = _safe_float(features.get("close"))
            if close < profile.min_price:
                exclusion_stats["low_price"] += 1
                continue
            if avg_amount_20 < profile.min_avg_amount_20:
                exclusion_stats["low_avg_amount_20"] += 1
                continue
            if avg_volume_20 < profile.min_avg_volume_20:
                exclusion_stats["low_avg_volume_20"] += 1
                continue

            benchmark_relative_20d = None
            if not np.isnan(benchmark_ret_20d):
                benchmark_relative_20d = round(_safe_float(features.get("ret_20d")) - float(benchmark_ret_20d), 2)

            rows.append(
                {
                    "code": symbol,
                    "name": symbol,
                    "price": close,
                    "close": close,
                    "change_pct": _safe_float(features.get("latest_pct_chg")),
                    "amount": avg_amount_20,
                    "avg_amount_20": avg_amount_20,
                    "avg_volume_20": avg_volume_20,
                    "volume": _safe_float(features.get("latest_volume")),
                    "amplitude": _safe_float(features.get("atr20_pct")),
                    "change_20d": _safe_float(features.get("ret_20d")),
                    "change_60d": _safe_float(features.get("ret_60d")),
                    "ret_5d": _safe_float(features.get("ret_5d")),
                    "ret_20d": _safe_float(features.get("ret_20d")),
                    "ret_60d": _safe_float(features.get("ret_60d")),
                    "ma20": _safe_float(features.get("ma20")),
                    "ma60": _safe_float(features.get("ma60")),
                    "ma20_slope_pct": _safe_float(features.get("ma20_slope_pct")),
                    "distance_to_20d_high_pct": _safe_float(features.get("distance_to_20d_high_pct")),
                    "prior_20d_high": _safe_float(features.get("prior_20d_high")),
                    "prior_10d_low": _safe_float(features.get("prior_10d_low")),
                    "volume_expansion_20": _safe_float(features.get("volume_expansion_20")),
                    "atr20_pct": _safe_float(features.get("atr20_pct")),
                    "recent_up_days_10": int(features.get("recent_up_days_10") or 0),
                    "last_trade_date": features.get("last_trade_date"),
                    "history_source": history_source,
                    "benchmark_relative_20d": benchmark_relative_20d,
                }
            )

        universe_df = pd.DataFrame(rows)
        if universe_df.empty:
            diagnostics = {
                "raw_symbol_count": int(len(symbols)),
                "final_universe_size": 0,
                "exclusion_stats": exclusion_stats,
            }
            return universe_df, [
                "US profile 需要本地可用的美股日线 universe，且默认先按流动性、价格与历史样本完整度过滤。",
            ], diagnostics, {
                "frames": history_frames,
                "diagnostics": history_diags,
                "history_rollup": history_rollup,
            }

        universe_df = universe_df.sort_values(
            ["avg_amount_20", "ret_20d", "ret_60d"],
            ascending=[False, False, False],
        ).head(universe_limit).reset_index(drop=True)

        universe_notes = [
            "起始池采用 local-first 的 US history universe：优先读取 LOCAL_US_PARQUET_DIR/US_STOCK_PARQUET_DIR，再回退到本地 stock_daily；当本地覆盖过窄时，会补入一小组受控 liquid seed symbols。",
            "默认先过滤低价、20 日平均成交额不足、20 日平均成交量不足或历史样本过短的标的。",
            f"本版默认保留流动性与趋势条件更好的 {universe_limit} 只美股候选进入详细评估。",
            "若实时 quote 不可用，US profile 仍会给出纯历史视角的 shortlist，并显式提示盘前上下文置信度较低。",
        ]
        diagnostics = {
            "raw_symbol_count": int(len(symbols)),
            "final_universe_size": int(len(universe_df)),
            "exclusion_stats": exclusion_stats,
        }
        return universe_df, universe_notes, diagnostics, {
            "frames": history_frames,
            "diagnostics": history_diags,
            "history_rollup": history_rollup,
        }

    def _compute_us_pre_rank(self, universe_df: pd.DataFrame) -> pd.DataFrame:
        df = universe_df.copy()
        max_amount = max(float(df["avg_amount_20"].max()), 1.0)
        max_volume = max(float(df["avg_volume_20"].max()), 1.0)
        df["liquidity_score"] = np.log1p(df["avg_amount_20"].clip(lower=0.0)) / np.log1p(max_amount)
        df["volume_score"] = np.log1p(df["avg_volume_20"].clip(lower=0.0)) / np.log1p(max_volume)
        df["trend_context_score"] = df["ret_60d"].map(lambda value: _clamp((float(value) + 5.0) / 45.0, 0.0, 1.0))
        df["momentum_score"] = df["ret_20d"].map(lambda value: _clamp((float(value) + 4.0) / 24.0, 0.0, 1.0))
        df["range_quality_score"] = df["atr20_pct"].map(lambda value: 1.0 - _clamp(abs(float(value) - 3.8) / 4.5, 0.0, 1.0))
        df["benchmark_relative_score"] = df["benchmark_relative_20d"].fillna(0.0).map(
            lambda value: _clamp((float(value) + 4.0) / 18.0, 0.0, 1.0)
        )
        df["pre_rank_score"] = (
            df["liquidity_score"] * 24.0
            + df["volume_score"] * 16.0
            + df["trend_context_score"] * 18.0
            + df["momentum_score"] * 18.0
            + df["range_quality_score"] * 12.0
            + df["benchmark_relative_score"] * 12.0
        )
        return df.sort_values(
            ["pre_rank_score", "avg_amount_20", "ret_20d", "benchmark_relative_20d"],
            ascending=[False, False, False, False],
        )

    def _extract_history_features(self, history_df: pd.DataFrame) -> Dict[str, Any]:
        if history_df is None or history_df.empty or len(history_df) < 40:
            return {}

        df = history_df.copy().reset_index(drop=True)
        df["ma10"] = df["close"].rolling(10).mean()
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma60"] = df["close"].rolling(60).mean()
        df["avg_amount_20"] = df["amount"].rolling(20).mean()
        df["avg_volume_20"] = df["volume"].rolling(20).mean()
        df["range_pct"] = ((df["high"] - df["low"]) / df["close"].replace(0, np.nan)) * 100.0

        latest = df.iloc[-1]
        prev20 = df.iloc[-21:-1] if len(df) >= 21 else df.iloc[:-1]
        if prev20.empty:
            prev20 = df.iloc[-20:]
        prior_20d_high = _safe_float(prev20["high"].max(), default=_safe_float(latest.get("high")))
        prior_10d_low = _safe_float(df.iloc[-11:-1]["low"].min(), default=_safe_float(latest.get("low")))
        close = _safe_float(latest.get("close"))
        ma20 = _safe_float(latest.get("ma20"))
        ma60 = _safe_float(latest.get("ma60"))

        return {
            "close": close,
            "ma10": _safe_float(latest.get("ma10")),
            "ma20": ma20,
            "ma60": ma60,
            "avg_amount_20": _safe_float(latest.get("avg_amount_20")),
            "avg_volume_20": _safe_float(latest.get("avg_volume_20")),
            "ret_5d": self._period_return(df["close"], 5),
            "ret_20d": self._period_return(df["close"], 20),
            "ret_60d": self._period_return(df["close"], 60),
            "ma20_slope_pct": self._period_return(df["ma20"], 5),
            "distance_to_20d_high_pct": ((close / prior_20d_high) - 1.0) * 100.0 if prior_20d_high > 0 else 0.0,
            "prior_20d_high": prior_20d_high,
            "prior_10d_low": prior_10d_low,
            "volume_expansion_20": (_safe_float(latest.get("volume")) / _safe_float(latest.get("avg_volume_20"))) if _safe_float(latest.get("avg_volume_20")) > 0 else 0.0,
            "atr20_pct": _safe_float(df["range_pct"].tail(20).mean()),
            "recent_up_days_10": int((df["pct_chg"].tail(10).fillna(0.0) > 0).sum()),
            "last_trade_date": latest["date"].date().isoformat() if pd.notna(latest["date"]) else None,
            "latest_pct_chg": _safe_float(latest.get("pct_chg")),
            "latest_volume": _safe_float(latest.get("volume")),
            "latest_amount": _safe_float(latest.get("amount")),
        }

    def _load_us_realtime_quote_context(
        self,
        *,
        symbol: str,
        reference_close: Optional[float],
    ) -> Dict[str, Any]:
        try:
            quote = self.data_manager.get_realtime_quote(symbol)
        except Exception as exc:
            trace = self.data_manager.get_last_realtime_quote_trace() if hasattr(self.data_manager, "get_last_realtime_quote_trace") else []
            return {
                "available": False,
                "status": "failed",
                "source": None,
                "trace": trace,
                "message": str(exc),
            }

        trace = self.data_manager.get_last_realtime_quote_trace() if hasattr(self.data_manager, "get_last_realtime_quote_trace") else []
        if quote is None or getattr(quote, "price", None) is None:
            return {
                "available": False,
                "status": "unavailable",
                "source": None,
                "trace": trace,
                "message": "live quote unavailable",
            }

        price = _safe_float(getattr(quote, "price", None))
        pre_close = _safe_float(getattr(quote, "pre_close", None), default=_safe_float(reference_close))
        gap_pct = _pct_change(pre_close, price)
        source_name = getattr(getattr(quote, "source", None), "value", getattr(quote, "source", None))
        return {
            "available": True,
            "status": "available",
            "source": str(source_name or "yfinance"),
            "price": price,
            "change_pct": getattr(quote, "change_pct", None),
            "volume": getattr(quote, "volume", None),
            "amount": getattr(quote, "amount", None),
            "pre_close": pre_close,
            "gap_pct": _round_optional(gap_pct),
            "name": getattr(quote, "name", None),
            "trace": trace,
            "message": None,
        }

    def _build_us_candidate_from_history(
        self,
        *,
        universe_row: Dict[str, Any],
        history_df: pd.DataFrame,
        history_diag: Dict[str, Any],
        quote_context: Dict[str, Any],
        benchmark_context: Dict[str, Any],
        profile: ScannerMarketProfile,
    ) -> Optional[Dict[str, Any]]:
        features = self._extract_history_features(history_df)
        if not features:
            return None

        live_price = _safe_float(quote_context.get("price"), default=_safe_float(features.get("close")))
        live_change_pct = _safe_float(quote_context.get("change_pct"), default=_safe_float(features.get("latest_pct_chg")))
        avg_amount_20 = _safe_float(features.get("avg_amount_20"))
        avg_volume_20 = _safe_float(features.get("avg_volume_20"))
        amount = _safe_float(quote_context.get("amount"), default=avg_amount_20)
        volume = _safe_float(quote_context.get("volume"), default=_safe_float(features.get("latest_volume")))
        benchmark_relative_20d = universe_row.get("benchmark_relative_20d")

        return {
            "symbol": str(universe_row["code"]),
            "name": str(quote_context.get("name") or universe_row.get("name") or universe_row["code"]),
            "price": live_price,
            "change_pct": live_change_pct,
            "volume": volume,
            "amount": amount,
            "close": _safe_float(features.get("close")),
            "ma10": _safe_float(features.get("ma10")),
            "ma20": _safe_float(features.get("ma20")),
            "ma60": _safe_float(features.get("ma60")),
            "ret_5d": _safe_float(features.get("ret_5d")),
            "ret_20d": _safe_float(features.get("ret_20d")),
            "ret_60d": _safe_float(features.get("ret_60d")),
            "ma20_slope_pct": _safe_float(features.get("ma20_slope_pct")),
            "distance_to_20d_high_pct": _safe_float(features.get("distance_to_20d_high_pct")),
            "prior_20d_high": _safe_float(features.get("prior_20d_high")),
            "prior_10d_low": _safe_float(features.get("prior_10d_low")),
            "avg_amount_20": avg_amount_20,
            "avg_volume_20": avg_volume_20,
            "volume_expansion_20": _safe_float(features.get("volume_expansion_20")),
            "atr20_pct": _safe_float(features.get("atr20_pct")),
            "recent_up_days_10": int(features.get("recent_up_days_10") or 0),
            "benchmark_relative_20d": benchmark_relative_20d,
            "gap_pct": quote_context.get("gap_pct"),
            "quote_available": bool(quote_context.get("available")),
            "history_rows": int(len(history_df)),
            "last_trade_date": features.get("last_trade_date"),
            "history_source": history_diag.get("source"),
            "snapshot_source": quote_context.get("source") or "history_only_us_scan",
            "boards": [],
            "_matched_sectors": [],
            "_relative_strength_pct": 0.0,
            "_component_scores": {
                "pre_rank": 0.0,
                "trend": 0.0,
                "momentum": 0.0,
                "liquidity": 0.0,
                "activity": 0.0,
                "volatility_quality": 0.0,
                "relative_strength": 0.0,
                "benchmark_relative": 0.0,
                "gap_context": 0.0,
                "penalties": 0.0,
            },
            "_diagnostics": {
                "history": history_diag,
                "history_source": history_diag.get("source"),
                "snapshot_source": quote_context.get("source") or "history_only_us_scan",
                "quote_context": quote_context,
                "benchmark_code": benchmark_context.get("benchmark_code"),
                "profile": profile.key,
            },
        }

    def list_runs(
        self,
        *,
        market: Optional[str] = "cn",
        profile: Optional[str] = None,
        page: int = 1,
        limit: int = 10,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """List persisted scanner runs."""

        resolved_page = max(1, int(page))
        resolved_limit = self._resolve_positive_int(limit, 10, 1, 50)
        offset = (resolved_page - 1) * resolved_limit
        rows, total = self.repo.get_runs_paginated(
            market=(market or "").strip().lower() or None,
            profile=(profile or "").strip().lower() or None,
            offset=offset,
            limit=resolved_limit,
            **self._visibility_kwargs(
                scope=scope,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            ),
        )

        return {
            "total": int(total),
            "page": resolved_page,
            "limit": resolved_limit,
            "items": [self._run_row_to_history_item(row) for row in rows],
        }

    @staticmethod
    def _default_comparison_summary() -> Dict[str, Any]:
        return {
            "available": False,
            "previous_run_id": None,
            "previous_watchlist_date": None,
            "new_count": 0,
            "retained_count": 0,
            "dropped_count": 0,
            "new_symbols": [],
            "retained_symbols": [],
            "dropped_symbols": [],
        }

    @staticmethod
    def _default_review_summary() -> Dict[str, Any]:
        return {
            "available": False,
            "review_window_days": DEFAULT_SCANNER_REVIEW_WINDOW_DAYS,
            "review_status": "pending",
            "candidate_count": 0,
            "reviewed_count": 0,
            "pending_count": 0,
            "hit_rate_pct": None,
            "outperform_rate_pct": None,
            "avg_same_day_close_return_pct": None,
            "avg_review_window_return_pct": None,
            "avg_max_favorable_move_pct": None,
            "avg_max_adverse_move_pct": None,
            "strong_count": 0,
            "mixed_count": 0,
            "weak_count": 0,
            "best_symbol": None,
            "best_return_pct": None,
            "weakest_symbol": None,
            "weakest_return_pct": None,
        }

    @staticmethod
    def _default_quality_summary(benchmark_code: str = DEFAULT_SCANNER_BENCHMARK_CODE) -> Dict[str, Any]:
        return {
            "available": False,
            "review_window_days": DEFAULT_SCANNER_REVIEW_WINDOW_DAYS,
            "benchmark_code": benchmark_code,
            "run_count": 0,
            "reviewed_run_count": 0,
            "reviewed_candidate_count": 0,
            "review_coverage_pct": None,
            "avg_candidates_per_run": None,
            "avg_shortlist_return_pct": None,
            "positive_run_rate_pct": None,
            "hit_rate_pct": None,
            "outperform_rate_pct": None,
            "positive_candidate_avg_score": None,
            "negative_candidate_avg_score": None,
        }

    def _select_watchlist_runs(
        self,
        *,
        market: Optional[str],
        profile: Optional[str],
        limit_days: int,
    ) -> List[MarketScannerRun]:
        rows = self.repo.get_recent_runs(
            market=(market or "").strip().lower() or None,
            profile=(profile or "").strip().lower() or None,
            limit=max(20, limit_days * 6),
            scope=OWNERSHIP_SCOPE_SYSTEM,
        )

        by_watchlist_date: Dict[str, MarketScannerRun] = {}
        for row in rows:
            _, _, metadata = self._extract_run_metadata(row)
            watchlist_date = metadata.get("watchlist_date") or _market_date_string(row.market, row.run_at)
            existing = by_watchlist_date.get(watchlist_date)
            if existing is None:
                by_watchlist_date[watchlist_date] = row
                continue
            existing_item = {
                "status": existing.status,
                "run_at": existing.run_at.isoformat() if existing.run_at else None,
            }
            current_item = {
                "status": row.status,
                "run_at": row.run_at.isoformat() if row.run_at else None,
            }
            if self._prefer_watchlist_item(current_item, existing_item):
                by_watchlist_date[watchlist_date] = row

        sorted_runs = sorted(
            by_watchlist_date.values(),
            key=lambda row: (
                self._extract_run_metadata(row)[2].get("watchlist_date") or "",
                row.run_at.isoformat() if row.run_at else "",
            ),
            reverse=True,
        )
        return sorted_runs[:limit_days]

    def _get_previous_watchlist_run(self, run: MarketScannerRun) -> Optional[MarketScannerRun]:
        if run.run_at is None:
            return None

        current_watchlist_date = self._extract_run_metadata(run)[2].get("watchlist_date")
        rows = self.repo.get_runs_before(
            market=run.market,
            profile=run.profile,
            run_at=run.run_at,
            run_id=int(run.id),
            limit=36,
            scope=run.scope or OWNERSHIP_SCOPE_USER,
            owner_id=run.owner_id,
        )

        target_date: Optional[str] = None
        selected: Optional[MarketScannerRun] = None
        for row in rows:
            watchlist_date = self._extract_run_metadata(row)[2].get("watchlist_date")
            if watchlist_date == current_watchlist_date:
                continue
            if target_date is None:
                target_date = watchlist_date
                selected = row
                continue
            if watchlist_date != target_date:
                break
            if selected is None:
                selected = row
                continue
            current_item = {
                "status": row.status,
                "run_at": row.run_at.isoformat() if row.run_at else None,
            }
            selected_item = {
                "status": selected.status,
                "run_at": selected.run_at.isoformat() if selected.run_at else None,
            }
            if self._prefer_watchlist_item(current_item, selected_item):
                selected = row
        return selected

    @staticmethod
    def _classify_outcome_label(
        review_status: str,
        review_window_return_pct: Optional[float],
        max_favorable_move_pct: Optional[float],
    ) -> str:
        if review_status == "pending":
            return "pending"
        review_return = review_window_return_pct if review_window_return_pct is not None else 0.0
        favorable = max_favorable_move_pct if max_favorable_move_pct is not None else 0.0
        if review_return >= 3.0 or (review_return >= 1.5 and favorable >= 4.0):
            return "strong"
        if review_return >= 0.0 or favorable >= 2.0:
            return "mixed"
        return "weak"

    @staticmethod
    def _classify_thesis_match(outcome_label: str) -> str:
        if outcome_label == "strong":
            return "validated"
        if outcome_label == "mixed":
            return "mixed"
        if outcome_label == "weak":
            return "not_validated"
        return "pending"

    def _build_benchmark_review(
        self,
        *,
        anchor_date: date,
        window_end_date: date,
        review_window_days: int,
        benchmark_code: str = DEFAULT_SCANNER_BENCHMARK_CODE,
    ) -> Dict[str, Any]:
        cache_key = (anchor_date.isoformat(), window_end_date.isoformat(), int(review_window_days), str(benchmark_code))
        cached = self._benchmark_review_cache.get(cache_key)
        if cached is not None:
            return dict(cached)

        result = {
            "benchmark_code": benchmark_code,
            "benchmark_return_pct": None,
            "benchmark_window_end_date": None,
        }
        benchmark_anchor = self.stock_repo.get_start_daily(code=benchmark_code, analysis_date=anchor_date)
        if benchmark_anchor is None or benchmark_anchor.close is None:
            self._benchmark_review_cache[cache_key] = dict(result)
            return result

        benchmark_bars = self.stock_repo.get_forward_bars(
            code=benchmark_code,
            analysis_date=benchmark_anchor.date,
            eval_window_days=max(review_window_days + 5, 10),
        )
        eligible_bars = [bar for bar in benchmark_bars if bar.date <= window_end_date and bar.close is not None]
        if not eligible_bars:
            self._benchmark_review_cache[cache_key] = dict(result)
            return result

        result["benchmark_return_pct"] = _round_optional(
            _pct_change(benchmark_anchor.close, eligible_bars[-1].close),
        )
        result["benchmark_window_end_date"] = eligible_bars[-1].date.isoformat()
        self._benchmark_review_cache[cache_key] = dict(result)
        return result

    def _build_candidate_realized_outcome(
        self,
        *,
        symbol: str,
        score: float,
        watchlist_date: Optional[str],
        last_trade_date: Optional[str],
        review_window_days: int = DEFAULT_SCANNER_REVIEW_WINDOW_DAYS,
        benchmark_code: str = DEFAULT_SCANNER_BENCHMARK_CODE,
    ) -> Dict[str, Any]:
        outcome = {
            "review_status": "pending",
            "outcome_label": "pending",
            "thesis_match": "pending",
            "review_window_days": int(review_window_days),
            "anchor_date": None,
            "window_end_date": None,
            "same_day_close_return_pct": None,
            "next_day_return_pct": None,
            "review_window_return_pct": None,
            "max_favorable_move_pct": None,
            "max_adverse_move_pct": None,
            "benchmark_code": benchmark_code,
            "benchmark_return_pct": None,
            "outperformed_benchmark": None,
            "score": _round_optional(score),
        }

        watchlist_dt = _parse_iso_date(watchlist_date)
        anchor_target = _parse_iso_date(last_trade_date)
        if anchor_target is None and watchlist_dt is not None:
            anchor_target = watchlist_dt - timedelta(days=1)
        if anchor_target is None:
            return outcome

        anchor_bar = self.stock_repo.get_start_daily(code=symbol, analysis_date=anchor_target)
        if anchor_bar is None or anchor_bar.close is None:
            return outcome

        outcome["anchor_date"] = anchor_bar.date.isoformat()
        review_bars = self.stock_repo.get_forward_bars(
            code=symbol,
            analysis_date=anchor_bar.date,
            eval_window_days=review_window_days,
        )
        if not review_bars:
            return outcome

        review_status = "ready" if len(review_bars) >= review_window_days else "partial"
        same_day_bar = next((bar for bar in review_bars if watchlist_dt is not None and bar.date == watchlist_dt), None)
        next_day_bar = next((bar for bar in review_bars if same_day_bar is not None and bar.date > same_day_bar.date), None)
        window_end_bar = review_bars[min(len(review_bars), review_window_days) - 1]

        outcome["review_status"] = review_status
        outcome["window_end_date"] = window_end_bar.date.isoformat()
        outcome["same_day_close_return_pct"] = _round_optional(
            _pct_change(anchor_bar.close, same_day_bar.close if same_day_bar is not None else None),
        )
        outcome["next_day_return_pct"] = _round_optional(
            _pct_change(
                same_day_bar.close if same_day_bar is not None else None,
                next_day_bar.close if next_day_bar is not None else None,
            ),
        )
        outcome["review_window_return_pct"] = _round_optional(
            _pct_change(anchor_bar.close, window_end_bar.close),
        )

        high_values = [
            float(bar.high if bar.high is not None else bar.close)
            for bar in review_bars
            if (bar.high if bar.high is not None else bar.close) is not None
        ]
        low_values = [
            float(bar.low if bar.low is not None else bar.close)
            for bar in review_bars
            if (bar.low if bar.low is not None else bar.close) is not None
        ]
        if high_values:
            outcome["max_favorable_move_pct"] = _round_optional(_pct_change(anchor_bar.close, max(high_values)))
        if low_values:
            outcome["max_adverse_move_pct"] = _round_optional(_pct_change(anchor_bar.close, min(low_values)))

        benchmark_review = self._build_benchmark_review(
            anchor_date=anchor_bar.date,
            window_end_date=window_end_bar.date,
            review_window_days=review_window_days,
            benchmark_code=benchmark_code,
        )
        outcome["benchmark_code"] = benchmark_review.get("benchmark_code")
        outcome["benchmark_return_pct"] = benchmark_review.get("benchmark_return_pct")
        if outcome["review_window_return_pct"] is not None and benchmark_review.get("benchmark_return_pct") is not None:
            outcome["outperformed_benchmark"] = bool(
                float(outcome["review_window_return_pct"]) > float(benchmark_review["benchmark_return_pct"])
            )

        outcome_label = self._classify_outcome_label(
            review_status,
            outcome.get("review_window_return_pct"),
            outcome.get("max_favorable_move_pct"),
        )
        outcome["outcome_label"] = outcome_label
        outcome["thesis_match"] = self._classify_thesis_match(outcome_label)
        return outcome

    def _summarize_review_rows(self, review_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        summary = self._default_review_summary()
        summary["candidate_count"] = len(review_rows)
        if not review_rows:
            return summary

        reviewed_rows = [row for row in review_rows if row.get("review_window_return_pct") is not None]
        summary["reviewed_count"] = len(reviewed_rows)
        summary["pending_count"] = max(0, len(review_rows) - len(reviewed_rows))
        if summary["reviewed_count"] == 0:
            return summary

        status_set = {str(row.get("review_status") or "pending") for row in review_rows}
        if status_set == {"ready"}:
            summary["review_status"] = "ready"
        else:
            summary["review_status"] = "partial"

        benchmark_rows = [row for row in reviewed_rows if row.get("outperformed_benchmark") is not None]
        strong_count = sum(1 for row in reviewed_rows if row.get("outcome_label") == "strong")
        mixed_count = sum(1 for row in reviewed_rows if row.get("outcome_label") == "mixed")
        weak_count = sum(1 for row in reviewed_rows if row.get("outcome_label") == "weak")
        best_row = max(reviewed_rows, key=lambda row: float(row.get("review_window_return_pct") or -9999.0))
        weak_row = min(reviewed_rows, key=lambda row: float(row.get("review_window_return_pct") or 9999.0))

        summary.update(
            {
                "available": True,
                "hit_rate_pct": _round_optional(
                    sum(1 for row in reviewed_rows if float(row.get("review_window_return_pct") or 0.0) > 0.0)
                    / len(reviewed_rows)
                    * 100.0
                ),
                "outperform_rate_pct": _round_optional(
                    sum(1 for row in benchmark_rows if row.get("outperformed_benchmark") is True)
                    / len(benchmark_rows)
                    * 100.0
                ) if benchmark_rows else None,
                "avg_same_day_close_return_pct": _mean_or_none(
                    [row.get("same_day_close_return_pct") for row in reviewed_rows]
                ),
                "avg_review_window_return_pct": _mean_or_none(
                    [row.get("review_window_return_pct") for row in reviewed_rows]
                ),
                "avg_max_favorable_move_pct": _mean_or_none(
                    [row.get("max_favorable_move_pct") for row in reviewed_rows]
                ),
                "avg_max_adverse_move_pct": _mean_or_none(
                    [row.get("max_adverse_move_pct") for row in reviewed_rows]
                ),
                "strong_count": strong_count,
                "mixed_count": mixed_count,
                "weak_count": weak_count,
                "best_symbol": best_row.get("symbol"),
                "best_return_pct": _round_optional(best_row.get("review_window_return_pct")),
                "weakest_symbol": weak_row.get("symbol"),
                "weakest_return_pct": _round_optional(weak_row.get("review_window_return_pct")),
            }
        )
        return summary

    def _get_run_review_bundle(
        self,
        run: MarketScannerRun,
        candidates: Sequence[MarketScannerCandidate],
    ) -> Dict[str, Any]:
        cached = self._run_review_cache.get(int(run.id))
        if cached is not None:
            return cached

        watchlist_date = self._extract_run_metadata(run)[2].get("watchlist_date")
        profile_config = get_scanner_profile(market=run.market, profile=run.profile)
        review_rows: List[Dict[str, Any]] = []
        by_symbol: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            outcome = self._build_candidate_realized_outcome(
                symbol=candidate.symbol,
                score=float(candidate.score or 0.0),
                watchlist_date=watchlist_date,
                last_trade_date=self._candidate_row_to_dict(candidate).get("last_trade_date"),
                benchmark_code=str(profile_config.benchmark_code or DEFAULT_SCANNER_BENCHMARK_CODE),
            )
            enriched_row = {
                **outcome,
                "symbol": candidate.symbol,
                "name": candidate.name,
                "score": _round_optional(candidate.score),
            }
            review_rows.append(enriched_row)
            by_symbol[candidate.symbol] = {
                key: value
                for key, value in enriched_row.items()
                if key not in {"symbol", "name", "score"}
            }

        bundle = {
            "summary": self._summarize_review_rows(review_rows),
            "rows": review_rows,
            "by_symbol": by_symbol,
        }
        self._run_review_cache[int(run.id)] = bundle
        return bundle

    def _build_watchlist_comparison(
        self,
        run: MarketScannerRun,
        candidates: Sequence[MarketScannerCandidate],
        *,
        previous_run: Optional[MarketScannerRun] = None,
    ) -> Dict[str, Any]:
        comparison = self._default_comparison_summary()
        previous = previous_run or self._get_previous_watchlist_run(run)
        if previous is None:
            return comparison

        previous_watchlist_date = self._extract_run_metadata(previous)[2].get("watchlist_date")
        previous_candidates = self.repo.get_candidates_for_run(previous.id)
        current_by_symbol = {candidate.symbol: candidate for candidate in candidates}
        previous_by_symbol = {candidate.symbol: candidate for candidate in previous_candidates}

        new_symbols = [
            {
                "symbol": candidate.symbol,
                "name": candidate.name,
                "current_rank": int(candidate.rank),
                "previous_rank": None,
                "rank_delta": None,
            }
            for candidate in candidates
            if candidate.symbol not in previous_by_symbol
        ]
        retained_symbols = [
            {
                "symbol": candidate.symbol,
                "name": candidate.name,
                "current_rank": int(candidate.rank),
                "previous_rank": int(previous_by_symbol[candidate.symbol].rank),
                "rank_delta": int(previous_by_symbol[candidate.symbol].rank) - int(candidate.rank),
            }
            for candidate in candidates
            if candidate.symbol in previous_by_symbol
        ]
        dropped_symbols = [
            {
                "symbol": candidate.symbol,
                "name": candidate.name,
                "current_rank": None,
                "previous_rank": int(candidate.rank),
                "rank_delta": None,
            }
            for candidate in previous_candidates
            if candidate.symbol not in current_by_symbol
        ]

        comparison.update(
            {
                "available": True,
                "previous_run_id": previous.id,
                "previous_watchlist_date": previous_watchlist_date,
                "new_count": len(new_symbols),
                "retained_count": len(retained_symbols),
                "dropped_count": len(dropped_symbols),
                "new_symbols": new_symbols,
                "retained_symbols": retained_symbols,
                "dropped_symbols": dropped_symbols,
            }
        )
        return comparison

    def _build_recent_quality_summary(self, runs: Sequence[MarketScannerRun]) -> Dict[str, Any]:
        benchmark_code = DEFAULT_SCANNER_BENCHMARK_CODE
        if runs:
            try:
                profile_config = get_scanner_profile(market=runs[0].market, profile=runs[0].profile)
                benchmark_code = str(profile_config.benchmark_code or benchmark_code)
            except Exception:
                benchmark_code = DEFAULT_SCANNER_BENCHMARK_CODE
        summary = self._default_quality_summary(benchmark_code)
        if not runs:
            return summary

        run_summaries: List[Dict[str, Any]] = []
        review_rows: List[Dict[str, Any]] = []
        total_candidates = 0
        for run in runs:
            candidates = self.repo.get_candidates_for_run(run.id)
            total_candidates += len(candidates)
            bundle = self._get_run_review_bundle(run, candidates)
            run_summary = dict(bundle.get("summary") or {})
            run_summaries.append(run_summary)
            review_rows.extend(bundle.get("rows") or [])

        reviewed_run_summaries = [item for item in run_summaries if int(item.get("reviewed_count") or 0) > 0]
        reviewed_rows = [row for row in review_rows if row.get("review_window_return_pct") is not None]
        benchmark_rows = [row for row in reviewed_rows if row.get("outperformed_benchmark") is not None]
        positive_rows = [row for row in reviewed_rows if float(row.get("review_window_return_pct") or 0.0) > 0.0]
        negative_rows = [row for row in reviewed_rows if float(row.get("review_window_return_pct") or 0.0) <= 0.0]

        summary.update(
            {
                "run_count": len(runs),
                "reviewed_run_count": len(reviewed_run_summaries),
                "reviewed_candidate_count": len(reviewed_rows),
                "review_coverage_pct": _round_optional(
                    len(reviewed_rows) / total_candidates * 100.0
                ) if total_candidates else None,
                "avg_candidates_per_run": _round_optional(total_candidates / len(runs), 1) if runs else None,
            }
        )

        if not reviewed_rows:
            return summary

        summary.update(
            {
                "available": True,
                "avg_shortlist_return_pct": _mean_or_none(
                    [item.get("avg_review_window_return_pct") for item in reviewed_run_summaries]
                ),
                "positive_run_rate_pct": _round_optional(
                    sum(1 for item in reviewed_run_summaries if float(item.get("avg_review_window_return_pct") or 0.0) > 0.0)
                    / len(reviewed_run_summaries)
                    * 100.0
                ) if reviewed_run_summaries else None,
                "hit_rate_pct": _round_optional(
                    len(positive_rows) / len(reviewed_rows) * 100.0
                ),
                "outperform_rate_pct": _round_optional(
                    sum(1 for row in benchmark_rows if row.get("outperformed_benchmark") is True)
                    / len(benchmark_rows)
                    * 100.0
                ) if benchmark_rows else None,
                "positive_candidate_avg_score": _mean_or_none([row.get("score") for row in positive_rows]),
                "negative_candidate_avg_score": _mean_or_none([row.get("score") for row in negative_rows]),
            }
        )
        return summary

    def _build_run_detail_payload(
        self,
        run: MarketScannerRun,
        *,
        previous_watchlist_run: Optional[MarketScannerRun] = None,
    ) -> Dict[str, Any]:
        summary, diagnostics, metadata = self._extract_run_metadata(run)
        universe_notes = _json_load(run.universe_notes_json, [])
        scoring_notes = _json_load(run.scoring_notes_json, [])
        candidates = self.repo.get_candidates_for_run(run.id)
        profile_config = get_scanner_profile(market=run.market, profile=run.profile)
        review_bundle = self._get_run_review_bundle(run, candidates)
        shortlist = []
        for candidate in candidates:
            item = self._candidate_row_to_dict(candidate)
            item["appeared_in_recent_runs"] = self.repo.count_recent_symbol_mentions(
                symbol=candidate.symbol,
                market=run.market,
                profile=run.profile,
                exclude_run_id=run.id,
                scope=run.scope,
                owner_id=run.owner_id,
            )
            item["scan_timestamp"] = run.run_at.isoformat() if run.run_at else None
            item["realized_outcome"] = review_bundle.get("by_symbol", {}).get(
                candidate.symbol,
                self._build_candidate_realized_outcome(
                    symbol=candidate.symbol,
                    score=float(candidate.score or 0.0),
                    watchlist_date=metadata.get("watchlist_date"),
                    last_trade_date=item.get("last_trade_date"),
                ),
            )
            original_ai_payload = item.get("diagnostics", {}).get("ai_interpretation") if isinstance(item.get("diagnostics"), dict) else None
            updated_ai_payload = self.ai_service.enrich_review_commentary(
                profile=profile_config,
                candidate=item,
                realized_outcome=item["realized_outcome"],
            )
            if isinstance(updated_ai_payload, dict):
                item["diagnostics"]["ai_interpretation"] = updated_ai_payload
                item["ai_interpretation"] = self.ai_service.public_payload_from_diagnostics(updated_ai_payload)
                if updated_ai_payload != original_ai_payload:
                    self.repo.update_candidate_diagnostics(
                        candidate.id,
                        diagnostics_json=json.dumps(item["diagnostics"], ensure_ascii=False),
                    )
            shortlist.append(item)

        return {
            "id": run.id,
            "market": run.market,
            "profile": run.profile,
            "profile_label": summary.get("profile_label"),
            "status": run.status,
            "run_at": run.run_at.isoformat() if run.run_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "watchlist_date": metadata.get("watchlist_date"),
            "trigger_mode": metadata.get("trigger_mode"),
            "universe_name": run.universe_name,
            "shortlist_size": int(run.shortlist_size or 0),
            "universe_size": int(run.universe_size or 0),
            "preselected_size": int(run.preselected_size or 0),
            "evaluated_size": int(run.evaluated_size or 0),
            "source_summary": run.source_summary,
            "headline": summary.get("headline"),
            "universe_notes": universe_notes if isinstance(universe_notes, list) else [],
            "scoring_notes": scoring_notes if isinstance(scoring_notes, list) else [],
            "diagnostics": diagnostics if isinstance(diagnostics, dict) else {},
            "notification": self._normalize_notification_result(diagnostics.get("notification")),
            "failure_reason": self._extract_failure_reason(diagnostics),
            "comparison_to_previous": self._build_watchlist_comparison(
                run,
                candidates,
                previous_run=previous_watchlist_run,
            ),
            "review_summary": review_bundle.get("summary") or self._default_review_summary(),
            "shortlist": shortlist,
        }

    def get_run_detail(
        self,
        run_id: int,
        *,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get one persisted scanner run with shortlist details."""

        run = self.repo.get_run(
            run_id,
            **self._visibility_kwargs(
                scope=scope,
                owner_id=owner_id,
                include_all_owners=include_all_owners,
            ),
        )
        if run is None:
            return None
        return self._build_run_detail_payload(
            run,
            previous_watchlist_run=self._get_previous_watchlist_run(run),
        )

    def list_recent_watchlists(
        self,
        *,
        market: str = "cn",
        profile: Optional[str] = None,
        limit_days: int = 7,
    ) -> Dict[str, Any]:
        resolved_limit_days = self._resolve_positive_int(limit_days, 7, 1, 30)
        runs = self._select_watchlist_runs(
            market=market,
            profile=profile,
            limit_days=resolved_limit_days,
        )
        items = [self._run_row_to_history_item(row) for row in runs]
        for index, item in enumerate(items):
            candidates = self.repo.get_candidates_for_run(runs[index].id)
            item["review_summary"] = self._get_run_review_bundle(runs[index], candidates).get("summary") or self._default_review_summary()
            previous_run = runs[index + 1] if index + 1 < len(runs) else None
            item["change_summary"] = self._build_watchlist_comparison(
                runs[index],
                candidates,
                previous_run=previous_run,
            )

        return {
            "total": len(items),
            "page": 1,
            "limit": resolved_limit_days,
            "items": items,
        }

    def get_today_watchlist(
        self,
        *,
        market: str = "cn",
        profile: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        target_date = _market_date_string(market)
        runs = self._select_watchlist_runs(
            market=market,
            profile=profile,
            limit_days=7,
        )
        selected_run = next(
            (
                row
                for row in runs
                if (self._extract_run_metadata(row)[2].get("watchlist_date") or target_date) == target_date
            ),
            None,
        )
        if selected_run is None:
            return None
        return self.get_run_detail(selected_run.id, scope=OWNERSHIP_SCOPE_SYSTEM)

    def get_operational_status(
        self,
        *,
        market: str = "cn",
        profile: Optional[str] = None,
        schedule_enabled: bool = False,
        schedule_time: Optional[str] = None,
        schedule_run_immediately: bool = False,
        notification_enabled: bool = False,
    ) -> Dict[str, Any]:
        resolved_profile = self._resolve_profile(market=market, profile=profile)
        watchlist_date = _market_date_string(resolved_profile.market)
        try:
            today_trading_day = is_market_open(resolved_profile.market, datetime.now(ZoneInfo(MARKET_TIMEZONE.get(resolved_profile.market, "Asia/Shanghai"))).date())
        except Exception:
            today_trading_day = True

        daily_runs = self._select_watchlist_runs(
            market=resolved_profile.market,
            profile=resolved_profile.key,
            limit_days=10,
        )
        rows = self.repo.get_recent_runs(
            market=resolved_profile.market,
            profile=resolved_profile.key,
            limit=30,
            **self._visibility_kwargs(),
        )
        items = [self._run_row_to_history_item(row) for row in rows]
        daily_items = [self._run_row_to_history_item(row) for row in daily_runs]

        def first_where(predicate) -> Optional[Dict[str, Any]]:
            for item in items:
                if predicate(item):
                    return item
            return None

        today_items = [item for item in daily_items if item.get("watchlist_date") == watchlist_date]
        today_watchlist = None
        for item in today_items:
            if today_watchlist is None or self._prefer_watchlist_item(item, today_watchlist):
                today_watchlist = item

        return {
            "market": resolved_profile.market,
            "profile": resolved_profile.key,
            "profile_label": resolved_profile.label,
            "watchlist_date": watchlist_date,
            "today_trading_day": today_trading_day,
            "schedule_enabled": bool(schedule_enabled),
            "schedule_time": schedule_time,
            "schedule_run_immediately": bool(schedule_run_immediately),
            "notification_enabled": bool(notification_enabled),
            "today_watchlist": today_watchlist,
            "last_run": items[0] if items else None,
            "last_scheduled_run": first_where(lambda item: item.get("trigger_mode") == "scheduled"),
            "last_manual_run": first_where(lambda item: item.get("trigger_mode") == "manual"),
            "latest_failure": first_where(lambda item: item.get("status") == "failed"),
            "quality_summary": self._build_recent_quality_summary(daily_runs),
        }

    def update_run_operation_metadata(
        self,
        run_id: int,
        *,
        trigger_mode: str,
        watchlist_date: str,
        request_source: str,
        notification_result: Optional[Dict[str, Any]] = None,
        failure_reason: Optional[str] = None,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
        include_all_owners: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        visibility_kwargs = self._visibility_kwargs(
            scope=scope,
            owner_id=owner_id,
            include_all_owners=include_all_owners,
        )
        run = self.repo.get_run(run_id, **visibility_kwargs)
        if run is None:
            return None

        summary = _json_load(run.summary_json, {})
        diagnostics = _json_load(run.diagnostics_json, {})
        operation = diagnostics.get("operation") if isinstance(diagnostics.get("operation"), dict) else {}
        operation.update(
            {
                "trigger_mode": trigger_mode,
                "request_source": request_source,
                "watchlist_date": watchlist_date,
            }
        )
        diagnostics["operation"] = operation
        if notification_result is not None:
            diagnostics["notification"] = self._normalize_notification_result(notification_result)
        if failure_reason:
            diagnostics["failure"] = {
                "message": failure_reason,
                "updated_at": datetime.now().isoformat(),
            }

        summary["watchlist_date"] = watchlist_date
        summary["trigger_mode"] = trigger_mode
        summary["request_source"] = request_source

        self.repo.update_run(
            run_id,
            summary_json=json.dumps(summary, ensure_ascii=False),
            diagnostics_json=json.dumps(diagnostics, ensure_ascii=False),
            **visibility_kwargs,
        )
        return self.get_run_detail(run_id, **visibility_kwargs)

    def record_terminal_run(
        self,
        *,
        market: str,
        profile: str,
        profile_label: str,
        universe_name: str,
        status: str,
        headline: str,
        trigger_mode: str,
        request_source: str,
        watchlist_date: str,
        source_summary: str,
        diagnostics: Optional[Dict[str, Any]] = None,
        universe_notes: Optional[List[str]] = None,
        scoring_notes: Optional[List[str]] = None,
        shortlist: Optional[List[Dict[str, Any]]] = None,
        universe_size: int = 0,
        preselected_size: int = 0,
        evaluated_size: int = 0,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_started_at = datetime.now()
        run_completed_at = datetime.now()
        normalized_shortlist = list(shortlist or [])
        normalized_scope = normalize_scope(
            scope,
            default=(
                OWNERSHIP_SCOPE_SYSTEM
                if str(trigger_mode or "").strip().lower() == "scheduled"
                else OWNERSHIP_SCOPE_USER
            ),
        )
        resolved_owner_id = self._resolve_persisted_owner_id(
            scope=normalized_scope,
            owner_id=owner_id,
        )
        summary = {
            "headline": headline,
            "profile_label": profile_label,
            "shortlisted_codes": [str(item.get("symbol")) for item in normalized_shortlist if item.get("symbol")],
            "watchlist_date": watchlist_date,
            "trigger_mode": trigger_mode,
            "request_source": request_source,
        }
        run_model = MarketScannerRun(
            owner_id=resolved_owner_id,
            scope=normalized_scope,
            market=market,
            profile=profile,
            universe_name=universe_name,
            status=status,
            shortlist_size=len(normalized_shortlist),
            universe_size=int(universe_size),
            preselected_size=int(preselected_size),
            evaluated_size=int(evaluated_size),
            run_at=run_started_at,
            completed_at=run_completed_at,
            source_summary=source_summary,
            summary_json=json.dumps(summary, ensure_ascii=False),
            diagnostics_json=json.dumps(
                {
                    **dict(diagnostics or {}),
                    "operation": {
                        "trigger_mode": trigger_mode,
                        "request_source": request_source,
                        "watchlist_date": watchlist_date,
                    },
                },
                ensure_ascii=False,
            ),
            universe_notes_json=json.dumps(universe_notes or [], ensure_ascii=False),
            scoring_notes_json=json.dumps(scoring_notes or [], ensure_ascii=False),
        )
        candidate_models = [
            self._candidate_dict_to_model(candidate, run_started_at=run_started_at)
            for candidate in normalized_shortlist
        ]
        saved_run = self.repo.save_run_with_candidates(run=run_model, candidates=candidate_models)
        return self.get_run_detail(
            saved_run.id,
            scope=normalized_scope,
            owner_id=resolved_owner_id,
        ) or {
            "id": saved_run.id,
            "status": status,
            "headline": headline,
            "shortlist": [],
        }

    def record_failed_run(
        self,
        *,
        market: str,
        profile: str,
        profile_label: str,
        universe_name: str,
        trigger_mode: str,
        request_source: str,
        watchlist_date: str,
        error_message: str,
        diagnostics: Optional[Dict[str, Any]] = None,
        source_summary: Optional[str] = None,
        scope: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        merged_diagnostics = {
            **dict(diagnostics or {}),
            "failure": {
                "message": error_message,
                "updated_at": datetime.now().isoformat(),
            },
        }
        return self.record_terminal_run(
            market=market,
            profile=profile,
            profile_label=profile_label,
            universe_name=universe_name,
            status="failed",
            headline=f"{profile_label} 执行失败",
            trigger_mode=trigger_mode,
            request_source=request_source,
            watchlist_date=watchlist_date,
            source_summary=source_summary or "scanner=failed",
            diagnostics=merged_diagnostics,
            universe_notes=[],
            scoring_notes=[],
            shortlist=[],
            scope=scope,
            owner_id=owner_id,
        )

    def _extract_run_metadata(
        self,
        run: MarketScannerRun,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        summary = _json_load(run.summary_json, {})
        diagnostics = _json_load(run.diagnostics_json, {})
        operation = diagnostics.get("operation") if isinstance(diagnostics.get("operation"), dict) else {}
        metadata = {
            "watchlist_date": summary.get("watchlist_date") or operation.get("watchlist_date") or _market_date_string(run.market, run.run_at),
            "trigger_mode": summary.get("trigger_mode") or operation.get("trigger_mode") or "manual",
            "request_source": summary.get("request_source") or operation.get("request_source") or "unknown",
        }
        return (
            summary if isinstance(summary, dict) else {},
            diagnostics if isinstance(diagnostics, dict) else {},
            metadata,
        )

    def _normalize_notification_result(self, payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {
                "attempted": False,
                "status": "not_attempted",
                "success": None,
                "channels": [],
            }
        return {
            "attempted": bool(payload.get("attempted")),
            "status": str(payload.get("status") or "unknown"),
            "success": payload.get("success"),
            "channels": [str(item) for item in (payload.get("channels") or []) if str(item).strip()],
            "message": payload.get("message"),
            "report_path": payload.get("report_path"),
            "sent_at": payload.get("sent_at"),
        }

    @staticmethod
    def _extract_failure_reason(diagnostics: Dict[str, Any]) -> Optional[str]:
        failure = diagnostics.get("failure") if isinstance(diagnostics.get("failure"), dict) else {}
        message = failure.get("message")
        return str(message).strip() if message else None

    def _run_row_to_history_item(self, row: MarketScannerRun) -> Dict[str, Any]:
        summary, diagnostics, metadata = self._extract_run_metadata(row)
        candidates = self.repo.get_candidates_for_run(row.id)
        top_symbols = summary.get("shortlisted_codes")
        if not isinstance(top_symbols, list) or not top_symbols:
            top_symbols = [candidate.symbol for candidate in candidates[:3]]
        notification = self._normalize_notification_result(diagnostics.get("notification"))
        return {
            "id": row.id,
            "market": row.market,
            "profile": row.profile,
            "profile_label": summary.get("profile_label"),
            "status": row.status,
            "run_at": row.run_at.isoformat() if row.run_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "watchlist_date": metadata.get("watchlist_date"),
            "trigger_mode": metadata.get("trigger_mode"),
            "universe_name": row.universe_name,
            "shortlist_size": int(row.shortlist_size or 0),
            "universe_size": int(row.universe_size or 0),
            "preselected_size": int(row.preselected_size or 0),
            "evaluated_size": int(row.evaluated_size or 0),
            "source_summary": row.source_summary,
            "headline": summary.get("headline"),
            "top_symbols": [str(item) for item in top_symbols[:3]],
            "notification_status": notification.get("status"),
            "failure_reason": self._extract_failure_reason(diagnostics),
            "change_summary": self._default_comparison_summary(),
            "review_summary": self._default_review_summary(),
        }

    @staticmethod
    def _status_priority(status: Optional[str]) -> int:
        normalized = str(status or "").strip().lower()
        if normalized == "completed":
            return 3
        if normalized == "empty":
            return 2
        if normalized == "failed":
            return 1
        return 0

    def _prefer_watchlist_item(self, current: Dict[str, Any], existing: Dict[str, Any]) -> bool:
        current_priority = self._status_priority(current.get("status"))
        existing_priority = self._status_priority(existing.get("status"))
        if current_priority != existing_priority:
            return current_priority > existing_priority
        return str(current.get("run_at") or "") > str(existing.get("run_at") or "")

    @staticmethod
    def _resolve_positive_int(value: Optional[int], default: int, low: int, high: int) -> int:
        if value is None:
            return default
        try:
            normalized = int(value)
        except Exception as exc:
            raise ValueError(f"无效的整数参数: {value}") from exc
        if normalized < low or normalized > high:
            raise ValueError(f"参数必须位于 {low} 到 {high} 之间")
        return normalized

    def _resolve_profile(self, *, market: str, profile: Optional[str]) -> ScannerMarketProfile:
        profile_config = get_scanner_profile(market=market, profile=profile)
        if not profile_config.implemented:
            raise ValueError(f"扫描配置 {profile_config.key} 预留给未来阶段，当前尚未实现")
        return profile_config

    def _resolve_cn_stock_universe(self) -> Dict[str, Any]:
        local_cache = self._load_local_universe_cache()
        if local_cache.get("success"):
            return local_cache

        attempts = list(local_cache.get("attempts") or [])
        tushare_result = {
            "success": False,
            "source": None,
            "data": None,
            "attempts": [],
            "error_code": "universe_source_unavailable",
            "error_message": "Tushare A 股股票列表不可用。",
        }
        if hasattr(self.data_manager, "try_get_cn_stock_list"):
            tushare_result = self.data_manager.try_get_cn_stock_list(
                preferred_fetchers=["TushareFetcher"],
            )
        else:
            try:
                stock_list, source = self.data_manager.get_cn_stock_list()
                tushare_result = {
                    "success": True,
                    "source": source,
                    "data": stock_list,
                    "attempts": [{"fetcher": source, "status": "success", "rows": int(len(stock_list))}],
                    "error_code": None,
                    "error_message": None,
                }
            except Exception as exc:
                tushare_result = {
                    "success": False,
                    "source": None,
                    "data": None,
                    "attempts": [{"fetcher": "DataFetcherManager", "status": "failed", "summary": str(exc)}],
                    "error_code": "universe_source_unavailable",
                    "error_message": str(exc),
                }

        attempts.extend(tushare_result.get("attempts") or [])
        if tushare_result.get("success") and tushare_result.get("data") is not None:
            normalized = self._normalize_stock_list_frame(tushare_result["data"])
            self._persist_local_universe_cache(normalized, source=str(tushare_result.get("source") or "provider"))
            return {
                "success": True,
                "source": str(tushare_result.get("source") or "provider"),
                "data": normalized,
                "attempts": attempts,
                "fallback_used": bool(attempts),
                "cache_path": str(self.local_universe_cache_path),
            }

        db_fallback = self._load_local_stock_list_fallback()
        attempts.extend(db_fallback.get("attempts") or [])
        if db_fallback.get("success"):
            normalized = db_fallback["data"]
            self._persist_local_universe_cache(normalized, source=str(db_fallback.get("source") or "db_local_fallback"))
            return {
                "success": True,
                "source": str(db_fallback.get("source") or "db_local_fallback"),
                "data": normalized,
                "attempts": attempts,
                "fallback_used": True,
                "cache_path": str(self.local_universe_cache_path),
            }

        builtin_fallback = self._load_builtin_stock_list_fallback()
        attempts.extend(builtin_fallback.get("attempts") or [])
        if builtin_fallback.get("success"):
            normalized = builtin_fallback["data"]
            self._persist_local_universe_cache(normalized, source=str(builtin_fallback.get("source") or "builtin_stock_mapping"))
            return {
                "success": True,
                "source": str(builtin_fallback.get("source") or "builtin_stock_mapping"),
                "data": normalized,
                "attempts": attempts,
                "fallback_used": True,
                "cache_path": str(self.local_universe_cache_path),
            }

        akshare_result = {
            "success": False,
            "source": None,
            "data": None,
            "attempts": [],
            "error_code": "universe_source_unavailable",
            "error_message": "Akshare A 股股票列表不可用。",
        }
        if hasattr(self.data_manager, "try_get_cn_stock_list"):
            akshare_result = self.data_manager.try_get_cn_stock_list(
                preferred_fetchers=["AkshareFetcher"],
            )
        attempts.extend(akshare_result.get("attempts") or [])
        if akshare_result.get("success") and akshare_result.get("data") is not None:
            normalized = self._normalize_stock_list_frame(akshare_result["data"])
            self._persist_local_universe_cache(normalized, source=str(akshare_result.get("source") or "AkshareFetcher"))
            return {
                "success": True,
                "source": str(akshare_result.get("source") or "AkshareFetcher"),
                "data": normalized,
                "attempts": attempts,
                "fallback_used": True,
                "cache_path": str(self.local_universe_cache_path),
            }

        return {
            "success": False,
            "source": None,
            "data": None,
            "attempts": attempts,
            "fallback_used": True,
            "cache_path": str(self.local_universe_cache_path),
            "error_code": "universe_source_unavailable",
            "error_message": self._build_resolution_error_message(
                prefix="A 股股票 universe 不可用。",
                attempts=attempts,
                fallback_note="本地 cache、Tushare、数据库/内置 fallback 与 Akshare 股票列表均未能提供可用 universe。",
            ),
        }

    def _load_local_universe_cache(self) -> Dict[str, Any]:
        cache_path = self.local_universe_cache_path
        attempts: List[Dict[str, Any]] = []
        if not cache_path.exists():
            attempts.append(
                {
                    "fetcher": "local_universe_cache",
                    "status": "failed",
                    "reason_code": "local_universe_cache_missing",
                    "error_type": "FileNotFoundError",
                    "error_reason": str(cache_path),
                    "summary": f"[local_universe_cache] (FileNotFoundError) {cache_path}",
                }
            )
            return {
                "success": False,
                "source": None,
                "data": None,
                "attempts": attempts,
                "cache_path": str(cache_path),
            }

        try:
            df = pd.read_csv(cache_path)
            normalized = self._normalize_stock_list_frame(df)
            if normalized.empty:
                raise ValueError("local universe cache is empty")
            attempts.append(
                {
                    "fetcher": "local_universe_cache",
                    "status": "success",
                    "rows": int(len(normalized)),
                }
            )
            return {
                "success": True,
                "source": "local_universe_cache",
                "data": normalized,
                "attempts": attempts,
                "cache_path": str(cache_path),
            }
        except Exception as exc:
            attempts.append(
                {
                    "fetcher": "local_universe_cache",
                    "status": "failed",
                    "reason_code": "local_universe_cache_invalid",
                    "error_type": type(exc).__name__,
                    "error_reason": str(exc),
                    "summary": f"[local_universe_cache] ({type(exc).__name__}) {exc}",
                }
            )
            return {
                "success": False,
                "source": None,
                "data": None,
                "attempts": attempts,
                "cache_path": str(cache_path),
            }

    def _persist_local_universe_cache(self, stock_list: pd.DataFrame, *, source: str) -> None:
        try:
            normalized = self._normalize_stock_list_frame(stock_list)
            if normalized.empty:
                return
            cache_path = self.local_universe_cache_path
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            normalized[["code", "name"]].to_csv(cache_path, index=False)
            logger.info("Scanner local universe cache updated from %s: %s (%s rows)", source, cache_path, len(normalized))
        except Exception as exc:
            logger.warning("Failed to persist scanner local universe cache: %s", exc)

    @staticmethod
    def _normalize_stock_list_frame(stock_list: pd.DataFrame) -> pd.DataFrame:
        normalized = stock_list.copy()
        if "code" not in normalized.columns:
            raise ValueError("stock list missing code column")
        if "name" not in normalized.columns:
            normalized["name"] = normalized["code"]
        normalized["code"] = normalized["code"].astype(str).map(normalize_stock_code)
        normalized["name"] = normalized["name"].astype(str).str.strip()
        normalized = normalized[normalized["code"] != ""]
        normalized = normalized.drop_duplicates(subset=["code"], keep="first")
        return normalized.reset_index(drop=True)

    def _load_local_stock_list_fallback(self) -> Dict[str, Any]:
        names: Dict[str, str] = {}
        codes: List[str] = []
        with self.db.get_session() as session:
            history_rows = session.execute(
                select(AnalysisHistory.code, AnalysisHistory.name).order_by(AnalysisHistory.created_at.desc())
            ).all()
            for code, name in history_rows:
                normalized = normalize_stock_code(str(code or ""))
                if not normalized or normalized in names:
                    continue
                names[normalized] = str(name or normalized)

            daily_codes = session.execute(select(StockDaily.code).distinct()).scalars().all()
            for raw_code in daily_codes:
                normalized = normalize_stock_code(str(raw_code or ""))
                if normalized and normalized not in codes:
                    codes.append(normalized)

        if not codes:
            return {
                "success": False,
                "source": None,
                "data": None,
                "attempts": [
                    {
                        "fetcher": "local_db",
                        "status": "failed",
                        "reason_code": "local_db_universe_empty",
                        "error_type": "ValueError",
                        "error_reason": "本地数据库中没有可用股票列表",
                        "summary": "[local_db] (ValueError) 本地数据库中没有可用股票列表",
                    }
                ],
            }

        frame = pd.DataFrame(
            [{"code": code, "name": names.get(code, code)} for code in codes]
        )
        return {
            "success": True,
            "source": "db_local_fallback",
            "data": self._normalize_stock_list_frame(frame),
            "attempts": [{"fetcher": "local_db", "status": "success", "rows": int(len(frame))}],
        }

    def _load_builtin_stock_list_fallback(self) -> Dict[str, Any]:
        records = [
            {"code": code, "name": name}
            for code, name in STOCK_NAME_MAP.items()
            if _is_cn_common_stock_code(code)
        ]
        if not records:
            return {
                "success": False,
                "source": None,
                "data": None,
                "attempts": [
                    {
                        "fetcher": "builtin_stock_mapping",
                        "status": "failed",
                        "reason_code": "builtin_stock_mapping_empty",
                        "error_type": "ValueError",
                        "error_reason": "内置股票映射中没有可用 A 股列表",
                        "summary": "[builtin_stock_mapping] (ValueError) 内置股票映射中没有可用 A 股列表",
                    }
                ],
            }

        frame = pd.DataFrame(records)
        return {
            "success": True,
            "source": "builtin_stock_mapping",
            "data": self._normalize_stock_list_frame(frame),
            "attempts": [{"fetcher": "builtin_stock_mapping", "status": "success", "rows": int(len(frame))}],
        }

    def _resolve_cn_snapshot(
        self,
        *,
        profile: ScannerMarketProfile,
        stock_list: Optional[pd.DataFrame],
    ) -> Dict[str, Any]:
        realtime_result = {
            "success": False,
            "source": None,
            "data": None,
            "attempts": [],
            "error_code": "no_realtime_snapshot_available",
            "error_message": "A 股全市场快照不可用。",
        }
        if hasattr(self.data_manager, "try_get_cn_realtime_snapshot"):
            realtime_result = self.data_manager.try_get_cn_realtime_snapshot(
                preferred_fetchers=["AkshareFetcher", "EfinanceFetcher"],
            )
        else:
            try:
                snapshot, source = self.data_manager.get_cn_realtime_snapshot()
                realtime_result = {
                    "success": True,
                    "source": source,
                    "data": snapshot,
                    "attempts": [{"fetcher": source, "status": "success", "rows": int(len(snapshot))}],
                    "error_code": None,
                    "error_message": None,
                }
            except Exception as exc:
                realtime_result = {
                    "success": False,
                    "source": None,
                    "data": None,
                    "attempts": [{"fetcher": "DataFetcherManager", "status": "failed", "summary": str(exc)}],
                    "error_code": "no_realtime_snapshot_available",
                    "error_message": str(exc),
                }

        if realtime_result.get("success") and realtime_result.get("data") is not None:
            normalized = self._normalize_snapshot_frame(realtime_result["data"])
            return {
                "success": True,
                "source": str(realtime_result.get("source") or "realtime_snapshot"),
                "data": normalized,
                "attempts": realtime_result.get("attempts") or [],
                "degraded_mode_used": False,
            }

        degraded_result = self._build_degraded_snapshot_from_local_history(
            profile=profile,
            stock_list=stock_list,
            attempts=realtime_result.get("attempts") or [],
        )
        if degraded_result.get("success"):
            return degraded_result

        return {
            "success": False,
            "source": None,
            "data": None,
            "attempts": realtime_result.get("attempts") or [],
            "degraded_mode_used": False,
            "error_code": str(realtime_result.get("error_code") or "no_realtime_snapshot_available"),
            "error_message": self._build_resolution_error_message(
                prefix="A 股全市场快照不可用。",
                attempts=realtime_result.get("attempts") or [],
                fallback_note="Akshare / efinance 快照均失败，且本地历史数据不足以进入降级模式。",
            ),
        }

    @staticmethod
    def _normalize_snapshot_frame(snapshot: pd.DataFrame) -> pd.DataFrame:
        normalized = snapshot.copy()
        normalized["code"] = normalized["code"].astype(str).map(normalize_stock_code)
        normalized["name"] = normalized["name"].astype(str).str.strip()
        normalized = normalized.drop_duplicates(subset=["code"], keep="first")
        return normalized.reset_index(drop=True)

    def _build_degraded_snapshot_from_local_history(
        self,
        *,
        profile: ScannerMarketProfile,
        stock_list: Optional[pd.DataFrame],
        attempts: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        names: Dict[str, str] = {}
        candidate_codes: List[str] = []
        if stock_list is not None and not stock_list.empty:
            for row in stock_list.to_dict("records"):
                code = normalize_stock_code(str(row.get("code") or ""))
                if not code:
                    continue
                if code not in candidate_codes:
                    candidate_codes.append(code)
                name = str(row.get("name") or code).strip()
                if name:
                    names[code] = name

        with self.db.get_session() as session:
            if not candidate_codes:
                daily_codes = session.execute(select(StockDaily.code).distinct()).scalars().all()
                for raw_code in daily_codes:
                    code = normalize_stock_code(str(raw_code or ""))
                    if code and code not in candidate_codes:
                        candidate_codes.append(code)
            history_rows = session.execute(
                select(AnalysisHistory.code, AnalysisHistory.name).order_by(AnalysisHistory.created_at.desc())
            ).all()
            for code, name in history_rows:
                normalized = normalize_stock_code(str(code or ""))
                if normalized and normalized not in names and name:
                    names[normalized] = str(name).strip()

        records: List[Dict[str, Any]] = []
        max_codes = max(profile.universe_limit * 2, 400)
        for code in candidate_codes[:max_codes]:
            history_df = self._load_local_history(code, history_days=max(profile.history_days, 90))
            if history_df.empty or len(history_df) < max(40, profile.min_history_bars // 2):
                continue
            latest = history_df.iloc[-1]
            close = _safe_float(latest.get("close"))
            if close <= 0:
                continue
            recent_amount = _safe_float(latest.get("amount"))
            recent_volume = _safe_float(latest.get("volume"))
            if recent_amount <= 0 or recent_volume <= 0:
                continue
            avg_volume_5 = _safe_float(history_df["volume"].tail(5).mean(), default=recent_volume)
            recent_window = history_df.tail(min(len(history_df), 60))
            first_close_60 = _safe_float(recent_window["close"].iloc[0], default=close) if not recent_window.empty else close
            change_60d = ((close / first_close_60) - 1.0) * 100.0 if first_close_60 > 0 else 0.0
            amplitude = ((_safe_float(latest.get("high")) - _safe_float(latest.get("low"))) / close) * 100.0 if close > 0 else 0.0
            records.append(
                {
                    "code": code,
                    "name": names.get(code, code),
                    "price": close,
                    "change_pct": _safe_float(latest.get("pct_chg")),
                    "volume": recent_volume,
                    "amount": recent_amount,
                    "turnover_rate": np.nan,
                    "volume_ratio": recent_volume / avg_volume_5 if avg_volume_5 > 0 else 1.0,
                    "amplitude": amplitude,
                    "change_60d": change_60d,
                    "source": "local_history_degraded",
                }
            )

        if not records:
            return {
                "success": False,
                "source": None,
                "data": None,
                "attempts": list(attempts),
                "degraded_mode_used": False,
                "error_code": "no_realtime_snapshot_available",
                "error_message": "Akshare/efinance 快照不可用，且本地历史数据不足以进入降级模式。",
            }

        snapshot = pd.DataFrame(records).sort_values(["amount", "change_60d"], ascending=[False, False]).reset_index(drop=True)
        degraded_attempts = list(attempts) + [
            {
                "fetcher": "local_history_degraded",
                "status": "success",
                "rows": int(len(snapshot)),
            }
        ]
        return {
            "success": True,
            "source": "local_history_degraded",
            "data": snapshot,
            "attempts": degraded_attempts,
            "degraded_mode_used": True,
            "warning": "full_realtime_snapshot_unavailable",
        }

    @staticmethod
    def _public_resolution_diagnostics(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return {}
        return {
            key: value
            for key, value in payload.items()
            if key != "data"
        }

    def _build_source_summary(
        self,
        *,
        universe_source: str,
        snapshot_source: str,
        degraded_mode_used: bool,
        universe_resolution: Dict[str, Any],
        snapshot_resolution: Dict[str, Any],
    ) -> str:
        snapshot_attempts = self._compact_attempts(snapshot_resolution.get("attempts") or [])
        universe_attempts = self._compact_attempts(universe_resolution.get("attempts") or [])
        return (
            f"universe={universe_source}; "
            f"snapshot={snapshot_source}; "
            f"history=local_first; "
            f"degraded={'yes' if degraded_mode_used else 'no'}; "
            f"universe_attempts={universe_attempts}; "
            f"snapshot_attempts={snapshot_attempts}"
        )

    def _build_resolution_error_message(
        self,
        *,
        prefix: str,
        attempts: Sequence[Dict[str, Any]],
        fallback_note: str,
    ) -> str:
        compact = self._compact_attempts(attempts)
        if compact == "none":
            return f"{prefix} {fallback_note}"
        return f"{prefix} {fallback_note} 已尝试: {compact}."

    @staticmethod
    def _compact_attempts(attempts: Sequence[Dict[str, Any]]) -> str:
        items = []
        for attempt in attempts[:6]:
            fetcher = str(attempt.get("fetcher") or "unknown")
            status = str(attempt.get("status") or "unknown")
            reason = str(attempt.get("reason_code") or "").strip()
            items.append(f"{fetcher}:{status}{f'({reason})' if reason else ''}")
        return ",".join(items) if items else "none"

    @staticmethod
    def _history_source_summary(source_counts: Dict[str, int]) -> Optional[str]:
        normalized = {
            str(key): int(value)
            for key, value in (source_counts or {}).items()
            if str(key).strip() and int(value) > 0
        }
        if not normalized:
            return None
        return sorted(normalized.items(), key=lambda item: (-item[1], item[0]))[0][0]

    @staticmethod
    def _collect_provider_attempt_summary(attempts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        failures = 0
        fallback_count = 0
        warnings: List[str] = []
        providers: List[str] = []

        normalized_attempts = [item for item in attempts if isinstance(item, dict)]
        success_attempt = next(
            (
                item for item in normalized_attempts
                if str(item.get("status") or "").strip().lower() == "success"
            ),
            None,
        )
        if success_attempt is not None and len(normalized_attempts) > 1:
            first_fetcher = str(normalized_attempts[0].get("fetcher") or "").strip()
            final_fetcher = str(success_attempt.get("fetcher") or "").strip()
            if final_fetcher and final_fetcher != first_fetcher:
                fallback_count += 1

        for attempt in normalized_attempts:
            fetcher = str(attempt.get("fetcher") or "").strip()
            if fetcher and fetcher not in providers:
                providers.append(fetcher)
            status = str(attempt.get("status") or "").strip().lower()
            reason_code = str(attempt.get("reason_code") or "").strip()
            if status == "failed":
                failures += 1
                warnings.append(f"{fetcher or 'unknown'} failed{f' ({reason_code})' if reason_code else ''}")

        return {
            "providers": providers,
            "failures": failures,
            "fallback_count": fallback_count,
            "warnings": warnings,
        }

    def _build_coverage_summary(
        self,
        *,
        input_universe_size: int,
        eligible_after_universe_fetch: int,
        eligible_after_liquidity_filter: int,
        eligible_after_data_availability_filter: int,
        ranked_candidate_count: int,
        shortlisted_count: int,
        excluded_reason_counts: Dict[str, int],
    ) -> Dict[str, Any]:
        normalized_reasons = [
            {
                "reason": str(reason),
                "label": str(reason).replace("_", " "),
                "count": int(count),
            }
            for reason, count in excluded_reason_counts.items()
            if int(count) > 0
        ]
        normalized_reasons.sort(key=lambda item: (-item["count"], item["reason"]))

        drops = {
            "small_universe": max(0, int(input_universe_size) - int(eligible_after_universe_fetch)),
            "filtering": max(0, int(eligible_after_universe_fetch) - int(eligible_after_liquidity_filter)),
            "data_availability": max(
                0,
                int(eligible_after_liquidity_filter) - int(eligible_after_data_availability_filter),
            ),
            "shortlist_limit": max(0, int(ranked_candidate_count) - int(shortlisted_count)),
        }
        priority = ["filtering", "data_availability", "small_universe", "shortlist_limit"]
        likely_bottleneck = "balanced"
        highest_drop = 0
        for key in priority:
            if drops[key] > highest_drop:
                likely_bottleneck = key
                highest_drop = drops[key]

        labels = {
            "small_universe": "输入 universe 本身较小，覆盖先天受限",
            "filtering": "多数标的在 profile / liquidity 过滤阶段被淘汰",
            "data_availability": "数据可用性不足压缩了最终可评估候选",
            "shortlist_limit": "候选足够，但最终 shortlist 上限较小",
            "balanced": "扫描覆盖、过滤和 shortlist 限制相对均衡",
        }

        return {
            "input_universe_size": int(input_universe_size),
            "eligible_after_universe_fetch": int(eligible_after_universe_fetch),
            "eligible_after_liquidity_filter": int(eligible_after_liquidity_filter),
            "eligible_after_data_availability_filter": int(eligible_after_data_availability_filter),
            "ranked_candidate_count": int(ranked_candidate_count),
            "shortlisted_count": int(shortlisted_count),
            "excluded_total": int(sum(item["count"] for item in normalized_reasons)),
            "excluded_by_reason": normalized_reasons,
            "likely_bottleneck": likely_bottleneck,
            "likely_bottleneck_label": labels[likely_bottleneck],
        }

    def _build_provider_diagnostics(
        self,
        *,
        configured_primary_provider: Optional[str],
        quote_source_used: Optional[str],
        snapshot_source_used: Optional[str],
        history_source_used: Optional[str],
        attempt_groups: Sequence[Sequence[Dict[str, Any]]],
        history_source_counts: Optional[Dict[str, int]] = None,
        missing_data_symbol_count: int = 0,
        additional_providers: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        providers_used: List[str] = []
        warnings: List[str] = []
        provider_failure_count = 0
        fallback_count = 0

        def add_provider(name: Optional[str]) -> None:
            provider = str(name or "").strip()
            if provider and provider not in providers_used:
                providers_used.append(provider)

        for provider_name in (
            configured_primary_provider,
            quote_source_used,
            snapshot_source_used,
            history_source_used,
        ):
            add_provider(provider_name)
        for provider_name in additional_providers or []:
            add_provider(provider_name)
        for provider_name in (history_source_counts or {}).keys():
            add_provider(provider_name)

        for attempts in attempt_groups:
            summary = self._collect_provider_attempt_summary(attempts)
            provider_failure_count += int(summary["failures"])
            fallback_count += int(summary["fallback_count"])
            for provider_name in summary["providers"]:
                add_provider(provider_name)
            for warning in summary["warnings"]:
                if warning not in warnings:
                    warnings.append(warning)

        providers_used.sort()
        return {
            "configured_primary_provider": configured_primary_provider,
            "quote_source_used": quote_source_used,
            "snapshot_source_used": snapshot_source_used,
            "history_source_used": history_source_used,
            "providers_used": providers_used,
            "fallback_occurred": bool(fallback_count),
            "fallback_count": int(fallback_count),
            "provider_failure_count": int(provider_failure_count),
            "missing_data_symbol_count": int(missing_data_symbol_count),
            "provider_warnings": warnings,
        }

    def _build_cn_universe(
        self,
        *,
        stock_list: pd.DataFrame,
        snapshot: pd.DataFrame,
        profile: ScannerMarketProfile,
        universe_limit: int,
        degraded_mode: bool = False,
    ) -> Tuple[pd.DataFrame, List[str], Dict[str, Any]]:
        stock_meta = stock_list[["code", "name"]].copy()
        stock_meta = stock_meta.rename(columns={"name": "list_name"})
        merged = snapshot.merge(stock_meta, on="code", how="left")
        merged["name"] = merged["name"].where(
            merged["name"].astype(str).str.strip() != "",
            merged["list_name"],
        )
        merged["name"] = merged["name"].fillna(merged["list_name"]).fillna("")
        merged["code"] = merged["code"].astype(str).map(normalize_stock_code)
        merged["name"] = merged["name"].astype(str).str.strip()

        exclusion_stats: Dict[str, int] = {}

        def apply_filter(df: pd.DataFrame, key: str, mask: pd.Series) -> pd.DataFrame:
            exclusion_stats[key] = int((~mask).sum())
            return df[mask].copy()

        filtered = merged.copy()
        filtered = apply_filter(
            filtered,
            "non_a_share",
            filtered["code"].map(_is_cn_common_stock_code),
        )
        filtered = apply_filter(
            filtered,
            "missing_name",
            filtered["name"].astype(str).str.strip() != "",
        )
        filtered = apply_filter(
            filtered,
            "st_flag",
            ~filtered["name"].map(is_st_stock),
        )
        filtered["price"] = pd.to_numeric(filtered.get("price"), errors="coerce")
        filtered["amount"] = pd.to_numeric(filtered.get("amount"), errors="coerce").fillna(0.0)
        filtered["volume"] = pd.to_numeric(filtered.get("volume"), errors="coerce").fillna(0.0)
        filtered["turnover_rate"] = pd.to_numeric(filtered.get("turnover_rate"), errors="coerce").fillna(0.0)
        filtered["volume_ratio"] = pd.to_numeric(filtered.get("volume_ratio"), errors="coerce").fillna(0.0)
        filtered["amplitude"] = pd.to_numeric(filtered.get("amplitude"), errors="coerce").fillna(0.0)
        filtered["change_pct"] = pd.to_numeric(filtered.get("change_pct"), errors="coerce").fillna(0.0)
        filtered["change_60d"] = pd.to_numeric(filtered.get("change_60d"), errors="coerce").fillna(filtered["change_pct"])
        filtered = apply_filter(
            filtered,
            "low_price",
            filtered["price"].fillna(0.0) >= profile.min_price,
        )
        filtered = apply_filter(
            filtered,
            "zero_volume_or_suspended",
            (filtered["volume"] > 0) & (filtered["price"] > 0),
        )
        filtered = apply_filter(
            filtered,
            "low_amount",
            filtered["amount"] >= profile.min_amount,
        )
        if degraded_mode:
            exclusion_stats["low_turnover_skipped"] = 0
            filtered["turnover_rate"] = filtered["turnover_rate"].where(
                filtered["turnover_rate"] > 0,
                profile.min_turnover_rate,
            )
        else:
            filtered = apply_filter(
                filtered,
                "low_turnover",
                filtered["turnover_rate"] >= profile.min_turnover_rate,
            )
        filtered = apply_filter(
            filtered,
            "low_volume_ratio",
            filtered["volume_ratio"] >= profile.min_volume_ratio,
        )
        filtered = filtered.sort_values(["amount", "turnover_rate"], ascending=[False, False]).head(universe_limit)
        filtered = filtered.reset_index(drop=True)

        universe_notes = [
            "起始池为数据源可获取的 A 股股票列表与全市场快照交集。",
            "剔除范围包括北交所、ST、停牌或近似停牌、极低价与明显流动性不足标的。",
            f"本版默认保留最近成交额与活跃度更高的 {universe_limit} 只候选进入详细评估。",
            "本阶段仅面向 A 股盘前观察，不涉及自动交易执行。",
        ]
        if degraded_mode:
            universe_notes.append("当前运行使用本地历史降级快照，换手率过滤已放宽；结果更适合盘前参考而非高确信度筛选。")
        diagnostics = {
            "raw_snapshot_size": int(len(snapshot)),
            "merged_size": int(len(merged)),
            "final_universe_size": int(len(filtered)),
            "exclusion_stats": exclusion_stats,
            "degraded_mode_used": bool(degraded_mode),
        }
        return filtered, universe_notes, diagnostics

    def _compute_pre_rank(self, universe_df: pd.DataFrame) -> pd.DataFrame:
        df = universe_df.copy()
        df["liquidity_score"] = np.log1p(df["amount"].clip(lower=0.0)) / np.log1p(max(float(df["amount"].max()), 1.0))
        df["turnover_score"] = df["turnover_rate"].map(lambda value: _clamp((float(value) - 0.8) / 5.2, 0.0, 1.0))
        df["volume_ratio_score"] = df["volume_ratio"].map(lambda value: _clamp((float(value) - 0.8) / 2.2, 0.0, 1.0))
        df["trend_context_score"] = df["change_60d"].map(lambda value: _clamp((float(value) + 5.0) / 30.0, 0.0, 1.0))
        df["range_quality_score"] = df["amplitude"].map(lambda value: 1.0 - _clamp(abs(float(value) - 4.0) / 6.0, 0.0, 1.0))

        df["pre_rank_score"] = (
            df["liquidity_score"] * 24.0
            + df["turnover_score"] * 18.0
            + df["volume_ratio_score"] * 18.0
            + df["trend_context_score"] * 24.0
            + df["range_quality_score"] * 16.0
        )
        return df.sort_values(
            ["pre_rank_score", "amount", "change_60d", "turnover_rate"],
            ascending=[False, False, False, False],
        )

    def _load_history_local_first(
        self,
        *,
        code: str,
        profile: ScannerMarketProfile,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        normalized_code = normalize_stock_code(code)
        local_df = self._load_local_history(normalized_code, history_days=profile.history_days)
        if self._is_history_sufficient(local_df, profile=profile):
            latest_trade_date = (
                pd.to_datetime(local_df["date"]).max().date().isoformat()
                if not local_df.empty and "date" in local_df.columns
                else None
            )
            return local_df, {
                "source": "local_db",
                "rows": int(len(local_df)),
                "latest_trade_date": latest_trade_date,
                "network_used": False,
                "network_failed": False,
                "partial_local_fallback": False,
            }

        if profile.market == "us":
            try:
                remote_df, remote_source = fetch_daily_history_with_local_us_fallback(
                    normalized_code,
                    days=profile.history_days,
                    manager=self.data_manager,
                    log_context="[scanner us history]",
                )
                normalized_remote_df = self._normalize_history_frame(remote_df)
                if not normalized_remote_df.empty:
                    self.stock_repo.save_dataframe(normalized_remote_df, normalized_code, remote_source)
                    latest_trade_date = (
                        pd.to_datetime(normalized_remote_df["date"]).max().date().isoformat()
                        if "date" in normalized_remote_df.columns
                        else None
                    )
                    return normalized_remote_df, {
                        "source": remote_source,
                        "rows": int(len(normalized_remote_df)),
                        "latest_trade_date": latest_trade_date,
                        "network_used": remote_source != "local_us_parquet",
                        "network_failed": False,
                        "partial_local_fallback": False,
                    }
            except Exception as exc:
                logger.warning("US scanner history fetch failed for %s: %s", normalized_code, exc)
                if len(local_df) >= 40:
                    latest_trade_date = (
                        pd.to_datetime(local_df["date"]).max().date().isoformat()
                        if not local_df.empty and "date" in local_df.columns
                        else None
                    )
                    return local_df, {
                        "source": "local_partial_fallback",
                        "rows": int(len(local_df)),
                        "latest_trade_date": latest_trade_date,
                        "network_used": True,
                        "network_failed": True,
                        "partial_local_fallback": True,
                        "warning": str(exc),
                    }
                return pd.DataFrame(), {
                    "source": "unavailable",
                    "rows": int(len(local_df)),
                    "network_used": True,
                    "network_failed": True,
                    "partial_local_fallback": False,
                    "warning": str(exc),
                }

        try:
            remote_df, remote_source = self.data_manager.get_daily_data(
                normalized_code,
                days=profile.history_days,
            )
            normalized_remote_df = self._normalize_history_frame(remote_df)
            if not normalized_remote_df.empty:
                self.stock_repo.save_dataframe(normalized_remote_df, normalized_code, remote_source)
                latest_trade_date = (
                    pd.to_datetime(normalized_remote_df["date"]).max().date().isoformat()
                    if "date" in normalized_remote_df.columns
                    else None
                )
                return normalized_remote_df, {
                    "source": remote_source,
                    "rows": int(len(normalized_remote_df)),
                    "latest_trade_date": latest_trade_date,
                    "network_used": True,
                    "network_failed": False,
                    "partial_local_fallback": False,
                }
        except Exception as exc:
            logger.warning("Scanner history fetch failed for %s: %s", normalized_code, exc)
            if len(local_df) >= 40:
                latest_trade_date = (
                    pd.to_datetime(local_df["date"]).max().date().isoformat()
                    if not local_df.empty and "date" in local_df.columns
                    else None
                )
                return local_df, {
                    "source": "local_partial_fallback",
                    "rows": int(len(local_df)),
                    "latest_trade_date": latest_trade_date,
                    "network_used": True,
                    "network_failed": True,
                    "partial_local_fallback": True,
                    "warning": str(exc),
                }
            return pd.DataFrame(), {
                "source": "unavailable",
                "rows": int(len(local_df)),
                "network_used": True,
                "network_failed": True,
                "partial_local_fallback": False,
                "warning": str(exc),
            }

        return pd.DataFrame(), {
            "source": "unavailable",
            "rows": int(len(local_df)),
            "network_used": True,
            "network_failed": True,
            "partial_local_fallback": False,
            "warning": "empty_remote_history",
        }

    def _load_local_history(self, code: str, history_days: int) -> pd.DataFrame:
        with self.db.get_session() as session:
            rows = session.execute(
                select(StockDaily)
                .where(StockDaily.code == code)
                .order_by(StockDaily.date.desc())
                .limit(history_days)
            ).scalars().all()

        records = []
        for row in reversed(list(rows)):
            records.append(
                {
                    "date": row.date.isoformat() if row.date else None,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                    "amount": row.amount,
                    "pct_chg": row.pct_chg,
                }
            )
        return self._normalize_history_frame(pd.DataFrame(records))

    def _is_history_sufficient(self, history_df: pd.DataFrame, *, profile: ScannerMarketProfile) -> bool:
        if history_df.empty or len(history_df) < profile.min_history_bars:
            return False
        if "date" not in history_df.columns:
            return False
        latest_trade_date = pd.to_datetime(history_df["date"]).max()
        if pd.isna(latest_trade_date):
            return False
        return latest_trade_date.to_pydatetime() >= datetime.now() - timedelta(days=21)

    def _normalize_history_frame(self, history_df: pd.DataFrame) -> pd.DataFrame:
        if history_df is None or history_df.empty:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "amount", "pct_chg"])

        df = history_df.copy()
        rename_map = {}
        for source_name, target_name in (
            ("日期", "date"),
            ("开盘", "open"),
            ("最高", "high"),
            ("最低", "low"),
            ("收盘", "close"),
            ("成交量", "volume"),
            ("成交额", "amount"),
            ("涨跌幅", "pct_chg"),
        ):
            if source_name in df.columns and target_name not in df.columns:
                rename_map[source_name] = target_name
        df = df.rename(columns=rename_map)

        expected_columns = ["date", "open", "high", "low", "close", "volume", "amount", "pct_chg"]
        for column in expected_columns:
            if column not in df.columns:
                df[column] = np.nan

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for column in ("open", "high", "low", "close", "volume", "amount", "pct_chg"):
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df = df.dropna(subset=["date", "close"])
        if "amount" in df.columns:
            df["amount"] = df["amount"].fillna(df["close"] * df["volume"].fillna(0.0))
        df = df.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
        df["date"] = df["date"].dt.tz_localize(None)
        return df

    def _build_candidate_from_history(
        self,
        *,
        snapshot_row: Dict[str, Any],
        history_df: pd.DataFrame,
        history_diag: Dict[str, Any],
        profile: ScannerMarketProfile,
        snapshot_source: str,
    ) -> Optional[Dict[str, Any]]:
        if history_df.empty or len(history_df) < 40:
            return None

        df = history_df.copy().reset_index(drop=True)
        df["ma10"] = df["close"].rolling(10).mean()
        df["ma20"] = df["close"].rolling(20).mean()
        df["ma60"] = df["close"].rolling(60).mean()
        df["avg_amount_20"] = df["amount"].rolling(20).mean()
        df["avg_volume_20"] = df["volume"].rolling(20).mean()
        df["range_pct"] = ((df["high"] - df["low"]) / df["close"].replace(0, np.nan)) * 100.0

        latest = df.iloc[-1]
        prev20 = df.iloc[-21:-1] if len(df) >= 21 else df.iloc[:-1]
        if prev20.empty:
            prev20 = df.iloc[-20:]
        prior_20d_high = _safe_float(prev20["high"].max(), default=_safe_float(latest.get("high")))
        prior_10d_low = _safe_float(df.iloc[-11:-1]["low"].min(), default=_safe_float(latest.get("low")))

        close = _safe_float(latest.get("close"))
        ma10 = _safe_float(latest.get("ma10"))
        ma20 = _safe_float(latest.get("ma20"))
        ma60 = _safe_float(latest.get("ma60"))
        avg_amount_20 = _safe_float(latest.get("avg_amount_20"))
        avg_volume_20 = _safe_float(latest.get("avg_volume_20"))
        ret_5d = self._period_return(df["close"], 5)
        ret_20d = self._period_return(df["close"], 20)
        ma20_slope_pct = self._period_return(df["ma20"], 5)
        distance_to_high_pct = ((close / prior_20d_high) - 1.0) * 100.0 if prior_20d_high > 0 else 0.0
        amount_ratio_20 = (_safe_float(snapshot_row.get("amount")) / avg_amount_20) if avg_amount_20 > 0 else 0.0
        volume_expansion_20 = (_safe_float(latest.get("volume")) / avg_volume_20) if avg_volume_20 > 0 else 0.0
        atr20_pct = _safe_float(df["range_pct"].tail(20).mean())
        recent_up_days_10 = int((df["pct_chg"].tail(10).fillna(0.0) > 0).sum())

        candidate = {
            "symbol": str(snapshot_row["code"]),
            "name": str(snapshot_row.get("name") or snapshot_row["code"]),
            "price": _safe_float(snapshot_row.get("price"), default=close),
            "change_pct": _safe_float(snapshot_row.get("change_pct")),
            "turnover_rate": _safe_float(snapshot_row.get("turnover_rate")),
            "volume_ratio": _safe_float(snapshot_row.get("volume_ratio")),
            "amount": _safe_float(snapshot_row.get("amount")),
            "amplitude": _safe_float(snapshot_row.get("amplitude")),
            "pre_rank_score": _safe_float(snapshot_row.get("pre_rank_score")),
            "close": close,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "ret_5d": ret_5d,
            "ret_20d": ret_20d,
            "ma20_slope_pct": ma20_slope_pct,
            "distance_to_20d_high_pct": distance_to_high_pct,
            "prior_20d_high": prior_20d_high,
            "prior_10d_low": prior_10d_low,
            "avg_amount_20": avg_amount_20,
            "amount_ratio_20": amount_ratio_20,
            "volume_expansion_20": volume_expansion_20,
            "atr20_pct": atr20_pct,
            "recent_up_days_10": recent_up_days_10,
            "history_rows": int(len(df)),
            "last_trade_date": latest["date"].date().isoformat() if pd.notna(latest["date"]) else None,
            "history_source": history_diag.get("source"),
            "snapshot_source": snapshot_source,
            "boards": [],
            "_matched_sectors": [],
            "_relative_strength_pct": 0.0,
            "_component_scores": {
                "pre_rank": 0.0,
                "trend": 0.0,
                "momentum": 0.0,
                "breakout": 0.0,
                "liquidity": 0.0,
                "activity": 0.0,
                "volatility_quality": 0.0,
                "relative_strength": 0.0,
                "sector_bonus": 0.0,
                "penalties": 0.0,
            },
            "_diagnostics": {
                "history": history_diag,
                "history_source": history_diag.get("source"),
                "snapshot_source": snapshot_source,
                "profile": profile.key,
            },
        }
        return candidate

    @staticmethod
    def _period_return(series: pd.Series, lookback: int) -> float:
        if len(series) <= lookback:
            return 0.0
        latest = _safe_float(series.iloc[-1], default=0.0)
        previous = _safe_float(series.iloc[-(lookback + 1)], default=0.0)
        if previous <= 0:
            return 0.0
        return (latest / previous - 1.0) * 100.0

    def _apply_relative_strength(self, candidates: List[Dict[str, Any]]) -> None:
        if not candidates:
            return
        values = pd.Series([_safe_float(item.get("ret_20d")) for item in candidates], dtype="float64")
        ranks = values.rank(pct=True, method="average")
        for candidate, rank in zip(candidates, ranks.tolist()):
            candidate["_relative_strength_pct"] = float(rank)

    def _apply_base_scores(self, candidates: List[Dict[str, Any]], *, profile: ScannerMarketProfile) -> None:
        for candidate in candidates:
            pre_rank = _clamp(_safe_float(candidate.get("pre_rank_score")) / 100.0, 0.0, 1.0) * 25.0

            trend_signals = [
                1.0 if _safe_float(candidate.get("close")) > _safe_float(candidate.get("ma20")) > 0 else 0.0,
                1.0 if _safe_float(candidate.get("close")) > _safe_float(candidate.get("ma60")) > 0 else 0.0,
                1.0 if _safe_float(candidate.get("ma20")) > _safe_float(candidate.get("ma60")) > 0 else 0.0,
                _clamp((_safe_float(candidate.get("ma20_slope_pct")) + 1.0) / 4.0, 0.0, 1.0),
            ]
            trend_score = (sum(trend_signals) / len(trend_signals)) * 20.0

            momentum_signals = [
                _clamp((_safe_float(candidate.get("ret_5d")) + 2.0) / 10.0, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("ret_20d")) + 2.0) / 18.0, 0.0, 1.0),
                _clamp((float(candidate.get("recent_up_days_10") or 0) - 4.0) / 4.0, 0.0, 1.0),
            ]
            momentum_score = (sum(momentum_signals) / len(momentum_signals)) * 15.0

            breakout_signals = [
                1.0 - _clamp(abs(_safe_float(candidate.get("distance_to_20d_high_pct"))) / 8.0, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("amount_ratio_20")) - 0.8) / 1.0, 0.0, 1.0),
            ]
            breakout_score = (sum(breakout_signals) / len(breakout_signals)) * 12.0

            liquidity_signals = [
                _clamp((_safe_float(candidate.get("avg_amount_20")) - profile.min_avg_amount_20) / 4.0e8, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("amount")) - profile.min_amount) / 6.0e8, 0.0, 1.0),
            ]
            liquidity_score = (sum(liquidity_signals) / len(liquidity_signals)) * 10.0

            activity_signals = [
                _clamp((_safe_float(candidate.get("turnover_rate")) - profile.min_turnover_rate) / 5.0, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("volume_ratio")) - 0.8) / 1.4, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("volume_expansion_20")) - 0.8) / 1.4, 0.0, 1.0),
            ]
            activity_score = (sum(activity_signals) / len(activity_signals)) * 8.0

            volatility_quality = (1.0 - _clamp(abs(_safe_float(candidate.get("atr20_pct")) - 4.0) / 4.0, 0.0, 1.0)) * 5.0
            relative_strength_score = _clamp(_safe_float(candidate.get("_relative_strength_pct")), 0.0, 1.0) * 5.0

            penalty_score = 0.0
            if _safe_float(candidate.get("ret_5d")) >= 12.0:
                penalty_score += 2.0
            if _safe_float(candidate.get("turnover_rate")) >= 12.0:
                penalty_score += 1.5
            if _safe_float(candidate.get("atr20_pct")) >= 6.5:
                penalty_score += 1.5
            if str(candidate.get("history_source")) == "local_partial_fallback":
                penalty_score += 2.0

            candidate["_component_scores"].update(
                {
                    "pre_rank": round(pre_rank, 2),
                    "trend": round(trend_score, 2),
                    "momentum": round(momentum_score, 2),
                    "breakout": round(breakout_score, 2),
                    "liquidity": round(liquidity_score, 2),
                    "activity": round(activity_score, 2),
                    "volatility_quality": round(volatility_quality, 2),
                    "relative_strength": round(relative_strength_score, 2),
                    "penalties": round(penalty_score, 2),
                }
            )
            candidate["_base_score"] = round(
                pre_rank
                + trend_score
                + momentum_score
                + breakout_score
                + liquidity_score
                + activity_score
                + volatility_quality
                + relative_strength_score
                - penalty_score,
                2,
            )

    def _apply_us_scores(self, candidates: List[Dict[str, Any]], *, profile: ScannerMarketProfile) -> None:
        for candidate in candidates:
            pre_rank = _clamp(_safe_float(candidate.get("pre_rank_score")) / 100.0, 0.0, 1.0) * 12.0

            trend_signals = [
                1.0 if _safe_float(candidate.get("price")) > _safe_float(candidate.get("ma20")) > 0 else 0.0,
                1.0 if _safe_float(candidate.get("price")) > _safe_float(candidate.get("ma60")) > 0 else 0.0,
                1.0 if _safe_float(candidate.get("ma20")) > _safe_float(candidate.get("ma60")) > 0 else 0.0,
                _clamp((_safe_float(candidate.get("ma20_slope_pct")) + 1.0) / 4.0, 0.0, 1.0),
            ]
            trend_score = (sum(trend_signals) / len(trend_signals)) * 20.0

            momentum_signals = [
                _clamp((_safe_float(candidate.get("ret_5d")) + 2.0) / 10.0, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("ret_20d")) + 3.0) / 20.0, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("ret_60d")) + 5.0) / 35.0, 0.0, 1.0),
                _clamp((float(candidate.get("recent_up_days_10") or 0) - 4.0) / 4.0, 0.0, 1.0),
            ]
            momentum_score = (sum(momentum_signals) / len(momentum_signals)) * 16.0

            liquidity_signals = [
                _clamp((_safe_float(candidate.get("avg_amount_20")) - profile.min_avg_amount_20) / max(profile.min_avg_amount_20, 1.0), 0.0, 1.0),
                _clamp((_safe_float(candidate.get("avg_volume_20")) - profile.min_avg_volume_20) / max(profile.min_avg_volume_20 * 2.0, 1.0), 0.0, 1.0),
            ]
            liquidity_score = (sum(liquidity_signals) / len(liquidity_signals)) * 16.0

            activity_signals = [
                _clamp((_safe_float(candidate.get("volume_expansion_20")) - 0.8) / 1.0, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("avg_amount_20")) - profile.min_avg_amount_20) / (profile.min_avg_amount_20 * 1.5), 0.0, 1.0),
            ]
            activity_score = (sum(activity_signals) / len(activity_signals)) * 12.0

            volatility_quality = (1.0 - _clamp(abs(_safe_float(candidate.get("atr20_pct")) - 3.8) / 4.0, 0.0, 1.0)) * 8.0
            relative_strength_score = _clamp(_safe_float(candidate.get("_relative_strength_pct")), 0.0, 1.0) * 10.0
            benchmark_relative_score = _clamp((_safe_float(candidate.get("benchmark_relative_20d")) + 3.0) / 12.0, 0.0, 1.0) * 10.0

            gap_pct = candidate.get("gap_pct")
            if gap_pct is None:
                gap_context_score = 4.0
            else:
                gap_context_score = (
                    1.0 - _clamp(abs(_safe_float(gap_pct) - 2.0) / 6.0, 0.0, 1.0)
                ) * 8.0

            penalty_score = 0.0
            if _safe_float(candidate.get("ret_5d")) >= 15.0:
                penalty_score += 2.0
            if _safe_float(candidate.get("atr20_pct")) >= 7.0:
                penalty_score += 2.0
            if candidate.get("gap_pct") is not None and abs(_safe_float(candidate.get("gap_pct"))) >= 8.0:
                penalty_score += 2.0
            if not candidate.get("quote_available"):
                penalty_score += 1.0
            if str(candidate.get("history_source")) == "local_partial_fallback":
                penalty_score += 1.5

            candidate["_component_scores"].update(
                {
                    "pre_rank": round(pre_rank, 2),
                    "trend": round(trend_score, 2),
                    "momentum": round(momentum_score, 2),
                    "liquidity": round(liquidity_score, 2),
                    "activity": round(activity_score, 2),
                    "volatility_quality": round(volatility_quality, 2),
                    "relative_strength": round(relative_strength_score, 2),
                    "benchmark_relative": round(benchmark_relative_score, 2),
                    "gap_context": round(gap_context_score, 2),
                    "penalties": round(penalty_score, 2),
                }
            )

    def _apply_hk_scores(self, candidates: List[Dict[str, Any]], *, profile: ScannerMarketProfile) -> None:
        for candidate in candidates:
            pre_rank = _clamp(_safe_float(candidate.get("pre_rank_score")) / 100.0, 0.0, 1.0) * 14.0

            trend_signals = [
                1.0 if _safe_float(candidate.get("price")) > _safe_float(candidate.get("ma20")) > 0 else 0.0,
                1.0 if _safe_float(candidate.get("price")) > _safe_float(candidate.get("ma60")) > 0 else 0.0,
                1.0 if _safe_float(candidate.get("ma20")) > _safe_float(candidate.get("ma60")) > 0 else 0.0,
                _clamp((_safe_float(candidate.get("ma20_slope_pct")) + 1.0) / 4.0, 0.0, 1.0),
            ]
            trend_score = (sum(trend_signals) / len(trend_signals)) * 20.0

            momentum_signals = [
                _clamp((_safe_float(candidate.get("ret_5d")) + 2.0) / 9.0, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("ret_20d")) + 3.0) / 18.0, 0.0, 1.0),
                _clamp((_safe_float(candidate.get("ret_60d")) + 5.0) / 28.0, 0.0, 1.0),
                _clamp((float(candidate.get("recent_up_days_10") or 0) - 4.0) / 4.0, 0.0, 1.0),
            ]
            momentum_score = (sum(momentum_signals) / len(momentum_signals)) * 16.0

            liquidity_signals = [
                _clamp((_safe_float(candidate.get("avg_amount_20")) - profile.min_avg_amount_20) / max(profile.min_avg_amount_20, 1.0), 0.0, 1.0),
                _clamp((_safe_float(candidate.get("avg_volume_20")) - profile.min_avg_volume_20) / max(profile.min_avg_volume_20 * 2.0, 1.0), 0.0, 1.0),
            ]
            liquidity_score = (sum(liquidity_signals) / len(liquidity_signals)) * 18.0

            activity_signals = [
                _clamp((_safe_float(candidate.get("volume_expansion_20")) - 0.8) / 1.0, 0.0, 1.0),
                1.0 - _clamp(abs(_safe_float(candidate.get("distance_to_20d_high_pct"))) / 10.0, 0.0, 1.0),
            ]
            activity_score = (sum(activity_signals) / len(activity_signals)) * 10.0

            volatility_quality = (1.0 - _clamp(abs(_safe_float(candidate.get("atr20_pct")) - 4.2) / 4.5, 0.0, 1.0)) * 8.0
            relative_strength_score = _clamp(_safe_float(candidate.get("_relative_strength_pct")), 0.0, 1.0) * 8.0
            benchmark_relative_score = _clamp((_safe_float(candidate.get("benchmark_relative_20d")) + 2.5) / 10.0, 0.0, 1.0) * 10.0

            gap_pct = candidate.get("gap_pct")
            if gap_pct is None:
                gap_context_score = 3.0
            else:
                gap_context_score = (
                    1.0 - _clamp(abs(_safe_float(gap_pct) - 1.5) / 5.0, 0.0, 1.0)
                ) * 6.0

            penalty_score = 0.0
            if _safe_float(candidate.get("ret_5d")) >= 12.0:
                penalty_score += 1.5
            if _safe_float(candidate.get("atr20_pct")) >= 7.0:
                penalty_score += 2.0
            if candidate.get("gap_pct") is not None and abs(_safe_float(candidate.get("gap_pct"))) >= 7.0:
                penalty_score += 1.5
            if not candidate.get("quote_available"):
                penalty_score += 1.0
            if str(candidate.get("history_source")) == "local_partial_fallback":
                penalty_score += 1.5

            candidate["_component_scores"].update(
                {
                    "pre_rank": round(pre_rank, 2),
                    "trend": round(trend_score, 2),
                    "momentum": round(momentum_score, 2),
                    "liquidity": round(liquidity_score, 2),
                    "activity": round(activity_score, 2),
                    "volatility_quality": round(volatility_quality, 2),
                    "relative_strength": round(relative_strength_score, 2),
                    "benchmark_relative": round(benchmark_relative_score, 2),
                    "gap_context": round(gap_context_score, 2),
                    "penalties": round(penalty_score, 2),
                }
            )

    def _load_sector_context(self) -> Dict[str, Any]:
        try:
            top_sectors, bottom_sectors = self.data_manager.get_sector_rankings(5)
            top_names = [name for name in (_common_board_name(item) for item in (top_sectors or [])) if name]
            bottom_names = [name for name in (_common_board_name(item) for item in (bottom_sectors or [])) if name]
            return {
                "available": bool(top_names or bottom_names),
                "top_names": top_names,
                "bottom_names": bottom_names,
            }
        except Exception as exc:
            logger.warning("Scanner sector context unavailable: %s", exc)
            return {
                "available": False,
                "top_names": [],
                "bottom_names": [],
                "warning": str(exc),
            }

    def _apply_board_context(self, candidates: Sequence[Dict[str, Any]], sector_context: Dict[str, Any]) -> None:
        if not candidates:
            return

        top_names = set(str(name) for name in sector_context.get("top_names") or [])
        for candidate in candidates:
            try:
                raw_boards = self.data_manager.get_belong_boards(str(candidate["symbol"]))
            except Exception as exc:
                candidate["_diagnostics"]["board_warning"] = str(exc)
                continue

            board_names = []
            for item in raw_boards or []:
                name = _common_board_name(item)
                if name and name not in board_names:
                    board_names.append(name)

            matched = [name for name in board_names if name in top_names]
            sector_bonus = min(5.0, 2.5 * len(matched))
            candidate["boards"] = board_names[:4]
            candidate["_matched_sectors"] = matched[:3]
            candidate["_component_scores"]["sector_bonus"] = round(sector_bonus, 2)

    def _finalize_candidates(self, candidates: List[Dict[str, Any]]) -> None:
        for candidate in candidates:
            components = dict(candidate.get("_component_scores") or {})
            score = (
                _safe_float(components.get("pre_rank"))
                + _safe_float(components.get("trend"))
                + _safe_float(components.get("momentum"))
                + _safe_float(components.get("breakout"))
                + _safe_float(components.get("liquidity"))
                + _safe_float(components.get("activity"))
                + _safe_float(components.get("volatility_quality"))
                + _safe_float(components.get("relative_strength"))
                + _safe_float(components.get("sector_bonus"))
                - _safe_float(components.get("penalties"))
            )
            candidate["score"] = round(_clamp(score, 0.0, 100.0), 1)
            candidate["quality_hint"] = self._quality_hint(candidate["score"])

            reasons = self._build_reasons(candidate)
            risk_notes = self._build_risk_notes(candidate)
            watch_context = self._build_watch_context(candidate)
            key_metrics = self._build_key_metrics(candidate)
            feature_signals = self._build_feature_signals(candidate)

            candidate["reason_summary"] = "；".join(reasons[:2]) if len(reasons) >= 2 else (reasons[0] if reasons else "满足基础筛选条件，适合列入盘前观察。")
            candidate["reasons"] = reasons
            candidate["risk_notes"] = risk_notes
            candidate["watch_context"] = watch_context
            candidate["key_metrics"] = key_metrics
            candidate["feature_signals"] = feature_signals

    def _finalize_us_candidates(self, candidates: List[Dict[str, Any]]) -> None:
        for candidate in candidates:
            components = dict(candidate.get("_component_scores") or {})
            score = (
                _safe_float(components.get("pre_rank"))
                + _safe_float(components.get("trend"))
                + _safe_float(components.get("momentum"))
                + _safe_float(components.get("liquidity"))
                + _safe_float(components.get("activity"))
                + _safe_float(components.get("volatility_quality"))
                + _safe_float(components.get("relative_strength"))
                + _safe_float(components.get("benchmark_relative"))
                + _safe_float(components.get("gap_context"))
                - _safe_float(components.get("penalties"))
            )
            candidate["score"] = round(_clamp(score, 0.0, 100.0), 1)
            candidate["quality_hint"] = self._quality_hint(candidate["score"])

            reasons = self._build_us_reasons(candidate)
            risk_notes = self._build_us_risk_notes(candidate)
            watch_context = self._build_us_watch_context(candidate)
            key_metrics = self._build_us_key_metrics(candidate)
            feature_signals = self._build_us_feature_signals(candidate)

            candidate["reason_summary"] = "；".join(reasons[:2]) if len(reasons) >= 2 else (reasons[0] if reasons else "满足基础筛选条件，适合列入美股盘前观察。")
            candidate["reasons"] = reasons
            candidate["risk_notes"] = risk_notes
            candidate["watch_context"] = watch_context
            candidate["key_metrics"] = key_metrics
            candidate["feature_signals"] = feature_signals

    def _finalize_hk_candidates(self, candidates: List[Dict[str, Any]]) -> None:
        for candidate in candidates:
            components = dict(candidate.get("_component_scores") or {})
            score = (
                _safe_float(components.get("pre_rank"))
                + _safe_float(components.get("trend"))
                + _safe_float(components.get("momentum"))
                + _safe_float(components.get("liquidity"))
                + _safe_float(components.get("activity"))
                + _safe_float(components.get("volatility_quality"))
                + _safe_float(components.get("relative_strength"))
                + _safe_float(components.get("benchmark_relative"))
                + _safe_float(components.get("gap_context"))
                - _safe_float(components.get("penalties"))
            )
            candidate["score"] = round(_clamp(score, 0.0, 100.0), 1)
            candidate["quality_hint"] = self._quality_hint(candidate["score"])

            reasons = self._build_hk_reasons(candidate)
            risk_notes = self._build_hk_risk_notes(candidate)
            watch_context = self._build_hk_watch_context(candidate)
            key_metrics = self._build_hk_key_metrics(candidate)
            feature_signals = self._build_hk_feature_signals(candidate)

            candidate["reason_summary"] = "；".join(reasons[:2]) if len(reasons) >= 2 else (reasons[0] if reasons else "满足基础筛选条件，适合列入港股开盘观察。")
            candidate["reasons"] = reasons
            candidate["risk_notes"] = risk_notes
            candidate["watch_context"] = watch_context
            candidate["key_metrics"] = key_metrics
            candidate["feature_signals"] = feature_signals

    @staticmethod
    def _quality_hint(score: float) -> str:
        if score >= 78:
            return "高优先级"
        if score >= 68:
            return "优先观察"
        if score >= 58:
            return "条件确认"
        return "题材跟踪"

    def _build_reasons(self, candidate: Dict[str, Any]) -> List[str]:
        reasons: List[str] = []
        close = _safe_float(candidate.get("close"))
        ma20 = _safe_float(candidate.get("ma20"))
        ma60 = _safe_float(candidate.get("ma60"))
        if close > ma20 > 0 and close > ma60 > 0:
            reasons.append("趋势结构完整，价格站在 MA20/MA60 上方。")
        if _safe_float(candidate.get("ma20_slope_pct")) > 0:
            reasons.append(f"MA20 近 5 日继续上行，斜率约 {_format_pct(candidate.get('ma20_slope_pct'))}。")
        if _safe_float(candidate.get("ret_5d")) > 1.5 and _safe_float(candidate.get("ret_20d")) > 4.0:
            reasons.append("近 5 日与近 20 日动量均为正，延续性较好。")
        if _safe_float(candidate.get("distance_to_20d_high_pct")) > -3.0:
            reasons.append(
                f"距离近 20 日高点仅 {_format_pct(abs(_safe_float(candidate.get('distance_to_20d_high_pct'))))}，适合观察突破确认。"
            )
        if _safe_float(candidate.get("amount_ratio_20")) >= 1.2 or _safe_float(candidate.get("volume_ratio")) >= 1.2:
            reasons.append("量能活跃，成交额与量比显示资金参与度提升。")
        matched_sectors = candidate.get("_matched_sectors") or []
        if matched_sectors:
            reasons.append(f"所属板块与当前强势方向重叠：{'、'.join(matched_sectors[:2])}。")
        if not reasons:
            reasons.append("量价与趋势指标整体处于可观察区间。")
        return reasons[:4]

    def _build_risk_notes(self, candidate: Dict[str, Any]) -> List[str]:
        notes: List[str] = []
        symbol = str(candidate.get("symbol") or "")
        daily_limit_pct = 20.0 if is_kc_cy_stock(symbol) else 10.0
        change_pct = _safe_float(candidate.get("change_pct"))
        if change_pct >= daily_limit_pct * 0.8:
            notes.append(f"接近日内涨停约束（{daily_limit_pct:.0f}% 制），追价容错较低。")
        if _safe_float(candidate.get("ret_5d")) >= 12.0 or _safe_float(candidate.get("turnover_rate")) >= 12.0:
            notes.append("短线过热迹象偏强，需防范题材追高后的分歧。")
        if _safe_float(candidate.get("amount")) < 4.0e8 or _safe_float(candidate.get("avg_amount_20")) < 2.0e8:
            notes.append("流动性边际一般，若竞价承接不足需降级观察。")
        if _safe_float(candidate.get("atr20_pct")) >= 6.0:
            notes.append("近 20 日振幅偏大，事件驱动波动可能放大。")
        if str(candidate.get("history_source")) == "local_partial_fallback":
            notes.append("历史样本依赖本地部分回退，盘前建议二次核验。")
        if not notes:
            notes.append("默认仍需结合竞价强弱与市场风格确认，不宜机械追买。")
        return notes[:4]

    def _build_watch_context(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        prior_high = _safe_float(candidate.get("prior_20d_high"))
        ma10 = _safe_float(candidate.get("ma10"))
        prior_low = _safe_float(candidate.get("prior_10d_low"))
        context = [
            {
                "label": "观察触发",
                "value": f"关注是否上破近 20 日高点 {_format_price(prior_high)}。",
            },
            {
                "label": "量能确认",
                "value": "优先观察量比维持在 1.2 以上，且成交额不弱于近 20 日均值。",
            },
            {
                "label": "放弃条件",
                "value": f"若弱开后跌回 MA10 {_format_price(ma10)} 或失守近 10 日低点 {_format_price(prior_low)}，不宜追单。",
            },
        ]
        matched_sectors = candidate.get("_matched_sectors") or []
        if matched_sectors:
            context.append(
                {
                    "label": "板块联动",
                    "value": f"同步确认 {'、'.join(matched_sectors[:2])} 的板块强度是否延续。",
                }
            )
        return context

    def _build_key_metrics(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        return [
            {"label": "最新价", "value": _format_price(candidate.get("price"))},
            {"label": "日涨跌幅", "value": _format_pct(candidate.get("change_pct"))},
            {"label": "20日动量", "value": _format_pct(candidate.get("ret_20d"))},
            {"label": "换手率", "value": _format_pct(candidate.get("turnover_rate"))},
            {"label": "成交额", "value": _format_amount(candidate.get("amount"))},
            {"label": "量比", "value": f"{_safe_float(candidate.get('volume_ratio')):.2f}x"},
        ]

    def _build_feature_signals(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        components = dict(candidate.get("_component_scores") or {})
        return [
            {"label": "趋势结构", "value": f"{_safe_float(components.get('trend')):.1f} / 20"},
            {"label": "动量延续", "value": f"{_safe_float(components.get('momentum')):.1f} / 15"},
            {"label": "突破条件", "value": f"{_safe_float(components.get('breakout')):.1f} / 12"},
            {"label": "活跃度", "value": f"{_safe_float(components.get('activity')):.1f} / 8"},
            {"label": "相对强度", "value": f"{_safe_float(components.get('relative_strength')):.1f} / 5"},
            {"label": "板块加分", "value": f"{_safe_float(components.get('sector_bonus')):.1f} / 5"},
        ]

    def _build_us_reasons(self, candidate: Dict[str, Any]) -> List[str]:
        reasons: List[str] = []
        price = _safe_float(candidate.get("price"))
        ma20 = _safe_float(candidate.get("ma20"))
        ma60 = _safe_float(candidate.get("ma60"))
        if price > ma20 > 0 and price > ma60 > 0:
            reasons.append("价格仍站在 MA20/MA60 上方，趋势延续结构尚未破坏。")
        if _safe_float(candidate.get("ret_20d")) > 6.0 and _safe_float(candidate.get("ret_60d")) > 12.0:
            reasons.append("20 日与 60 日动量都保持正向，更像可跟踪的趋势延续候选。")
        if _safe_float(candidate.get("benchmark_relative_20d")) > 2.0:
            reasons.append(f"相对基准近 20 日超额约 {_format_pct(candidate.get('benchmark_relative_20d'))}，强于大盘。")
        if _safe_float(candidate.get("distance_to_20d_high_pct")) > -4.0:
            reasons.append(
                f"距离近 20 日高点仅 {_format_pct(abs(_safe_float(candidate.get('distance_to_20d_high_pct'))))}，适合观察 breakout follow-through。"
            )
        if candidate.get("quote_available") and candidate.get("gap_pct") is not None:
            reasons.append(f"盘前/实时价相对昨收变动约 {_format_pct(candidate.get('gap_pct'))}，具备 pre-open context。")
        if not reasons:
            reasons.append("流动性、趋势与波动结构整体仍在可交易区间。")
        return reasons[:4]

    def _build_us_risk_notes(self, candidate: Dict[str, Any]) -> List[str]:
        notes: List[str] = []
        if not candidate.get("quote_available"):
            notes.append("当前缺少可靠的实时/盘前 quote，上下文更偏历史视角，开盘前需二次确认。")
        gap_pct = candidate.get("gap_pct")
        if gap_pct is not None and abs(_safe_float(gap_pct)) >= 5.0:
            notes.append("Gap risk 偏高，若开盘后不能延续，容易出现快速回吐。")
        if _safe_float(candidate.get("avg_amount_20")) < 5.0e7 or _safe_float(candidate.get("avg_volume_20")) < 2.0e6:
            notes.append("流动性只处在中低区间，仓位与滑点容错需要更保守。")
        if _safe_float(candidate.get("atr20_pct")) >= 6.0:
            notes.append("近 20 日波动偏大，盘前强势不代表开盘后仍容易拿住。")
        if _safe_float(candidate.get("ret_5d")) >= 15.0:
            notes.append("短线拉升已较快，trend continuation 需要成交与相对强度继续配合。")
        if not notes:
            notes.append("默认仍需结合 index tone、开盘量能与相对强度确认，不宜机械追高。")
        return notes[:4]

    def _build_us_watch_context(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        prior_high = _safe_float(candidate.get("prior_20d_high"))
        ma10 = _safe_float(candidate.get("ma10"))
        prior_low = _safe_float(candidate.get("prior_10d_low"))
        context = [
            {
                "label": "Pre-open",
                "value": f"先看是否仍靠近/站上近 20 日高点 {_format_price(prior_high)}，避免强 gap 后立即走弱。",
            },
            {
                "label": "Open check",
                "value": "开盘后优先看成交是否延续到日内前 15 分钟，而不是只看第一笔价格跳动。",
            },
            {
                "label": "Risk off",
                "value": f"若开盘后跌回 MA10 {_format_price(ma10)} 附近，或快速失守近 10 日低点 {_format_price(prior_low)}，应降低跟踪优先级。",
            },
        ]
        if candidate.get("gap_pct") is not None:
            context.append(
                {
                    "label": "Gap context",
                    "value": f"当前 gap 约 {_format_pct(candidate.get('gap_pct'))}，需要确认不是 one-minute squeeze 后快速回落。",
                }
            )
        return context

    def _build_us_key_metrics(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        return [
            {"label": "Price", "value": _format_price(candidate.get("price"))},
            {"label": "Day change", "value": _format_pct(candidate.get("change_pct"))},
            {"label": "20D return", "value": _format_pct(candidate.get("ret_20d"))},
            {"label": "20D avg $vol", "value": _format_us_amount(candidate.get("avg_amount_20"))},
            {"label": "20D avg vol", "value": _format_us_volume(candidate.get("avg_volume_20"))},
            {"label": "Gap vs prev close", "value": _format_pct(candidate.get("gap_pct"))},
        ]

    def _build_us_feature_signals(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        components = dict(candidate.get("_component_scores") or {})
        return [
            {"label": "Trend", "value": f"{_safe_float(components.get('trend')):.1f} / 20"},
            {"label": "Momentum", "value": f"{_safe_float(components.get('momentum')):.1f} / 16"},
            {"label": "Liquidity", "value": f"{_safe_float(components.get('liquidity')):.1f} / 16"},
            {"label": "Tradability", "value": f"{_safe_float(components.get('activity')):.1f} / 12"},
            {"label": "Rel. benchmark", "value": f"{_safe_float(components.get('benchmark_relative')):.1f} / 10"},
            {"label": "Gap context", "value": f"{_safe_float(components.get('gap_context')):.1f} / 8"},
        ]

    def _build_hk_reasons(self, candidate: Dict[str, Any]) -> List[str]:
        reasons: List[str] = []
        price = _safe_float(candidate.get("price"))
        ma20 = _safe_float(candidate.get("ma20"))
        ma60 = _safe_float(candidate.get("ma60"))
        if price > ma20 > 0 and price > ma60 > 0:
            reasons.append("价格仍站在 MA20/MA60 上方，趋势延续结构尚未破坏。")
        if _safe_float(candidate.get("ret_20d")) > 5.0 and _safe_float(candidate.get("ret_60d")) > 10.0:
            reasons.append("20 日与 60 日动量同步转强，更像可持续跟踪的港股趋势候选。")
        if _safe_float(candidate.get("benchmark_relative_20d")) > 1.5:
            reasons.append(f"相对基准近 20 日超额约 {_format_pct(candidate.get('benchmark_relative_20d'))}，强于恒生宽基参考。")
        if _safe_float(candidate.get("distance_to_20d_high_pct")) > -4.5:
            reasons.append(
                f"距离近 20 日高点仅 {_format_pct(abs(_safe_float(candidate.get('distance_to_20d_high_pct'))))}，适合观察开盘延续确认。"
            )
        if candidate.get("quote_available") and candidate.get("gap_pct") is not None:
            reasons.append(f"开盘前/实时价相对昨收变动约 {_format_pct(candidate.get('gap_pct'))}，具备开盘上下文。")
        if not reasons:
            reasons.append("流动性、趋势与波动结构整体仍在可观察区间。")
        return reasons[:4]

    def _build_hk_risk_notes(self, candidate: Dict[str, Any]) -> List[str]:
        notes: List[str] = []
        if not candidate.get("quote_available"):
            notes.append("当前缺少可靠的实时 quote，上下文更偏历史视角，开盘前需二次确认。")
        gap_pct = candidate.get("gap_pct")
        if gap_pct is not None and abs(_safe_float(gap_pct)) >= 4.5:
            notes.append("开盘跳空幅度偏大，若承接不足，容易走成冲高回落。")
        if _safe_float(candidate.get("avg_amount_20")) < 1.2e8 or _safe_float(candidate.get("avg_volume_20")) < 1.8e6:
            notes.append("流动性只处在中低区间，仓位和滑点容错需要更保守。")
        if _safe_float(candidate.get("atr20_pct")) >= 6.5:
            notes.append("近 20 日波动偏大，强势并不等于开盘后容易持有。")
        if _safe_float(candidate.get("ret_5d")) >= 12.0:
            notes.append("短线拉升速度已较快，需要成交与相对强度继续配合。")
        if not notes:
            notes.append("默认仍需结合恒指/恒科气氛、开盘量能与相对强度确认，不宜机械追高。")
        return notes[:4]

    def _build_hk_watch_context(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        prior_high = _safe_float(candidate.get("prior_20d_high"))
        ma10 = _safe_float(candidate.get("ma10"))
        prior_low = _safe_float(candidate.get("prior_10d_low"))
        context = [
            {
                "label": "开盘前",
                "value": f"先看是否仍靠近/站上近 20 日高点 {_format_price(prior_high)}，避免高开后迅速走弱。",
            },
            {
                "label": "开盘确认",
                "value": "开盘后优先看前 15 分钟成交是否延续，而不是只看第一笔撮合价。",
            },
            {
                "label": "风险撤退",
                "value": f"若开盘后跌回 MA10 {_format_price(ma10)} 附近，或快速失守近 10 日低点 {_format_price(prior_low)}，应降低跟踪优先级。",
            },
        ]
        if candidate.get("gap_pct") is not None:
            context.append(
                {
                    "label": "跳空背景",
                    "value": f"当前跳空约 {_format_pct(candidate.get('gap_pct'))}，需要确认不是开盘一波脉冲后快速回落。",
                }
            )
        return context

    def _build_hk_key_metrics(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        return [
            {"label": "价格", "value": _format_price(candidate.get("price"))},
            {"label": "日涨跌幅", "value": _format_pct(candidate.get("change_pct"))},
            {"label": "20日动量", "value": _format_pct(candidate.get("ret_20d"))},
            {"label": "20日均成交额", "value": _format_hk_amount(candidate.get("avg_amount_20"))},
            {"label": "20日均成交量", "value": _format_hk_volume(candidate.get("avg_volume_20"))},
            {"label": "相对昨收跳空", "value": _format_pct(candidate.get("gap_pct"))},
        ]

    def _build_hk_feature_signals(self, candidate: Dict[str, Any]) -> List[Dict[str, str]]:
        components = dict(candidate.get("_component_scores") or {})
        return [
            {"label": "趋势", "value": f"{_safe_float(components.get('trend')):.1f} / 20"},
            {"label": "动量", "value": f"{_safe_float(components.get('momentum')):.1f} / 16"},
            {"label": "流动性", "value": f"{_safe_float(components.get('liquidity')):.1f} / 18"},
            {"label": "开盘条件", "value": f"{_safe_float(components.get('activity')):.1f} / 10"},
            {"label": "相对基准", "value": f"{_safe_float(components.get('benchmark_relative')):.1f} / 10"},
            {"label": "跳空背景", "value": f"{_safe_float(components.get('gap_context')):.1f} / 6"},
        ]

    @staticmethod
    def _build_headline(shortlist: Sequence[Dict[str, Any]], *, market: str = "cn") -> str:
        if not shortlist:
            return "本次扫描未生成可执行观察名单。"
        names = [f"{item['symbol']} {item['name']}" for item in shortlist[:5]]
        if (market or "").strip().lower() == "us":
            return "今日美股盘前优先观察：" + " / ".join(names)
        if (market or "").strip().lower() == "hk":
            return "今日港股开盘优先观察：" + " / ".join(names)
        return "今日 A 股盘前优先观察：" + " / ".join(names)

    @staticmethod
    def _build_scoring_notes(*, profile: Optional[ScannerMarketProfile] = None) -> List[str]:
        if profile and profile.market == "us":
            return [
                "US profile 先基于 local-first 的美股 history universe 做预筛；当本地覆盖过窄时，只补入受控的 liquid seed symbols，而不会做全市场盲扫。",
                "详细评估阶段会对高优先级候选补充 optional realtime / pre-open quote 上下文；若 live quote 不可用，仍保留纯历史规则型排序，但会明确提示置信度下降。",
                "第一版不追求覆盖全美股市场，而是优先在本地可用 universe 内筛出更可交易的 pre-open watchlist。",
                "结果仍是规则型观察名单，不是自动买卖指令。",
            ]
        if profile and profile.market == "hk":
            return [
                "HK profile 先基于 local-first 的港股 history universe 做预筛；当本地覆盖过窄时，只补入受控的 liquid seed symbols，而不会做全市场盲扫。",
                "详细评估阶段会补充 optional realtime quote / 开盘上下文；若 live quote 不可用，仍保留纯历史规则型排序，但会明确提示置信度下降。",
                "第一版不追求覆盖全部港股市场，而是优先在受控 universe 内筛出更可交易的开盘观察名单。",
                "结果仍是规则型观察名单，不是自动买卖指令。",
            ]
        return [
            "第一阶段以全市场快照做预筛：趋势背景、成交额、换手率、量比与振幅共同决定候选进入详细评估的优先级。",
            "第二阶段结合日线历史，重点看趋势结构、近 5/20 日动量、距近 20 日高点的位置、成交额放大与相对强度。",
            "板块上下文只作为小幅加分项，不覆盖基础趋势与流动性判断。",
            "结果为规则型观察名单，不是自动买卖指令。",
        ]

    def _candidate_dict_to_model(
        self,
        candidate: Dict[str, Any],
        *,
        run_started_at: datetime,
    ) -> MarketScannerCandidate:
        return MarketScannerCandidate(
            symbol=str(candidate["symbol"]),
            name=str(candidate.get("name") or candidate["symbol"]),
            rank=int(candidate.get("rank") or 0),
            score=float(candidate.get("score") or 0.0),
            quality_hint=str(candidate.get("quality_hint") or ""),
            reason_summary=str(candidate.get("reason_summary") or ""),
            reasons_json=json.dumps(candidate.get("reasons") or [], ensure_ascii=False),
            key_metrics_json=json.dumps(candidate.get("key_metrics") or [], ensure_ascii=False),
            feature_signals_json=json.dumps(candidate.get("feature_signals") or [], ensure_ascii=False),
            risk_notes_json=json.dumps(candidate.get("risk_notes") or [], ensure_ascii=False),
            watch_context_json=json.dumps(candidate.get("watch_context") or [], ensure_ascii=False),
            boards_json=json.dumps(candidate.get("boards") or [], ensure_ascii=False),
            diagnostics_json=json.dumps(
                {
                    **dict(candidate.get("_diagnostics") or {}),
                    "scan_timestamp": run_started_at.isoformat(),
                    "component_scores": candidate.get("_component_scores") or {},
                },
                ensure_ascii=False,
            ),
            created_at=run_started_at,
        )

    def _candidate_row_to_dict(self, candidate: MarketScannerCandidate) -> Dict[str, Any]:
        diagnostics = _json_load(candidate.diagnostics_json, {})
        return {
            "symbol": candidate.symbol,
            "name": candidate.name,
            "rank": int(candidate.rank),
            "score": float(candidate.score),
            "quality_hint": candidate.quality_hint,
            "reason_summary": candidate.reason_summary,
            "reasons": _json_load(candidate.reasons_json, []),
            "key_metrics": _json_load(candidate.key_metrics_json, []),
            "feature_signals": _json_load(candidate.feature_signals_json, []),
            "risk_notes": _json_load(candidate.risk_notes_json, []),
            "watch_context": _json_load(candidate.watch_context_json, []),
            "boards": _json_load(candidate.boards_json, []),
            "appeared_in_recent_runs": 0,
            "last_trade_date": diagnostics.get("history", {}).get("latest_trade_date") or diagnostics.get("last_trade_date"),
            "ai_interpretation": self.ai_service.public_payload_from_diagnostics(diagnostics.get("ai_interpretation")),
            "diagnostics": diagnostics if isinstance(diagnostics, dict) else {},
        }

    def _public_candidate_dict(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        diagnostics = {
            **dict(candidate.get("_diagnostics") or {}),
            "component_scores": dict(candidate.get("_component_scores") or {}),
            "last_trade_date": candidate.get("last_trade_date"),
        }
        return {
            "symbol": candidate["symbol"],
            "name": candidate["name"],
            "rank": int(candidate.get("rank") or 0),
            "score": float(candidate.get("score") or 0.0),
            "quality_hint": candidate.get("quality_hint"),
            "reason_summary": candidate.get("reason_summary"),
            "reasons": candidate.get("reasons") or [],
            "key_metrics": candidate.get("key_metrics") or [],
            "feature_signals": candidate.get("feature_signals") or [],
            "risk_notes": candidate.get("risk_notes") or [],
            "watch_context": candidate.get("watch_context") or [],
            "boards": candidate.get("boards") or [],
            "appeared_in_recent_runs": int(candidate.get("appeared_in_recent_runs") or 0),
            "last_trade_date": candidate.get("last_trade_date"),
            "scan_timestamp": candidate.get("scan_timestamp"),
            "ai_interpretation": self.ai_service.public_payload_from_diagnostics(diagnostics.get("ai_interpretation")),
            "diagnostics": diagnostics,
        }
