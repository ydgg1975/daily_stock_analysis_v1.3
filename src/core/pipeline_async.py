# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - 异步 분석 파이프라인
===================================

职责：
1. asyncio 기반의 비동기 주식 분석 파이프라인 제공
2. 동기 데이터 수집 및 분석을 asyncio.to_thread 등을 활용하여 비동기 실행 및 병렬화
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Callable

from src.config import get_config, Config
from src.core.pipeline import StockAnalysisPipeline
from src.analyzer.core import AnalysisResult
from src.enums import ReportType

logger = logging.getLogger(__name__)


class AsyncStockAnalysisPipeline:
    """
    비동기 주식 분석 파이프라인
    
    기존 StockAnalysisPipeline의 분석 흐름을 비동기(async/await) 및 asyncio.gather를
    통해 고성능 병렬 처리가 가능하도록 래핑 및 최적화합니다.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        max_workers: Optional[int] = None,
        query_id: Optional[str] = None,
        query_source: Optional[str] = None,
        save_context_snapshot: Optional[bool] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ):
        self.config = config or get_config()
        self.max_workers = max_workers or self.config.max_workers
        self.query_id = query_id or uuid.uuid4().hex
        self.query_source = query_source or "async_cli"
        self.progress_callback = progress_callback

        # 기존 동기 파이프라인 인스턴스를 내부에 구성하여 핵심 로직 위임
        self._sync_pipeline = StockAnalysisPipeline(
            config=self.config,
            max_workers=self.max_workers,
            query_id=self.query_id,
            query_source=self.query_source,
            save_context_snapshot=save_context_snapshot,
            progress_callback=self._emit_progress_wrapper,
        )

    def _emit_progress_wrapper(self, progress: int, message: str) -> None:
        """동기 파이프라인에서 오는 진행 상태 콜백을 비동기 호환을 고려해 위임"""
        if self.progress_callback:
            try:
                self.progress_callback(progress, message)
            except Exception as exc:
                logger.warning("[async_pipeline] progress callback error: %s", exc)

    async def fetch_and_save_stock_data_async(
        self,
        code: str,
        force_refresh: bool = False,
        current_time: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        비동기적으로 단일 종목 데이터를 가져오고 로컬 데이터베이스에 저장합니다.
        기존의 동기 데이터 패치를 asyncio.to_thread를 사용해 비동기 I/O로 병렬 실행합니다.
        """
        logger.info("[async_pipeline] Fetching data for %s", code)
        return await asyncio.to_thread(
            self._sync_pipeline.fetch_and_save_stock_data,
            code=code,
            force_refresh=force_refresh,
            current_time=current_time,
        )

    async def analyze_stock_async(
        self,
        code: str,
        report_type: ReportType = ReportType.SIMPLE,
    ) -> Optional[AnalysisResult]:
        """
        비동기적으로 단일 종목을 분석합니다.
        기술적 지표, 뉴스 검색, LLM 분석 전체를 비동기 스레드 풀에서 안전하게 돌려 병목을 방지합니다.
        """
        logger.info("[async_pipeline] Analyzing stock %s", code)
        return await asyncio.to_thread(
            self._sync_pipeline.analyze_stock,
            code=code,
            report_type=report_type,
            query_id=self.query_id,
        )

    async def run_async(
        self,
        stock_codes: List[str],
        report_type: ReportType = ReportType.SIMPLE,
        force_refresh: bool = False,
    ) -> List[AnalysisResult]:
        """
        복수 종목에 대해 비동기 병렬 데이터 패치 및 AI 분석을 병렬로 수행합니다.
        """
        current_time = datetime.now()
        
        # 1. 병렬 데이터 패치 단계
        logger.info("[async_pipeline] Starting parallel data fetching for %d stocks", len(stock_codes))
        fetch_tasks = [
            self.fetch_and_save_stock_data_async(code, force_refresh, current_time)
            for code in stock_codes
        ]
        fetch_results = await asyncio.gather(*fetch_tasks)
        
        successful_fetches = [code for code, (success, _) in zip(stock_codes, fetch_results) if success]
        logger.info(
            "[async_pipeline] Data fetching completed. Success: %d/%d",
            len(successful_fetches),
            len(stock_codes),
        )

        # 2. 병렬 AI 분석 단계
        logger.info("[async_pipeline] Starting parallel AI analysis for %d stocks", len(successful_fetches))
        analysis_tasks = [
            self.analyze_stock_async(code, report_type)
            for code in successful_fetches
        ]
        analysis_results = await asyncio.gather(*analysis_tasks)
        
        valid_results = [r for r in analysis_results if r is not None]
        logger.info(
            "[async_pipeline] AI analysis completed. Active results count: %d",
            len(valid_results),
        )
        
        return valid_results
