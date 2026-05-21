# -*- coding: utf-8 -*-
"""
===================================
비동기 분석 작업 서비스
===================================

역할:
1. 비동기 분석 작업을 관리합니다.
2. 종목 분석을 실행하고 결과를 저장합니다.
3. 작업 상태와 분석 이력을 조회합니다.

기존 web/services.py의 AnalysisService 역할을 서비스 계층으로 분리했습니다.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Dict, Any, List, Union

from src.enums import ReportType
from src.storage import get_db
from bot.models import BotMessage

logger = logging.getLogger(__name__)


class TaskService:
    """
    비동기 분석 작업 서비스

    담당 범위:
    1. 비동기 분석 작업 관리
    2. 단일 종목 분석 실행
    3. 알림 전송 트리거
    """

    _instance: Optional["TaskService"] = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 3):
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers = max_workers
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "TaskService":
        """싱글턴 인스턴스를 반환합니다."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def executor(self) -> ThreadPoolExecutor:
        """스레드 풀 실행기를 반환합니다."""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="analysis_",
            )
        return self._executor

    def submit_analysis(
        self,
        code: str,
        report_type: Union[ReportType, str] = ReportType.SIMPLE,
        source_message: Optional[BotMessage] = None,
        save_context_snapshot: Optional[bool] = None,
        query_source: str = "bot",
    ) -> Dict[str, Any]:
        """
        비동기 분석 작업을 제출합니다.

        Args:
            code: 종목 코드
            report_type: 보고서 유형
            source_message: 봇 응답에 사용할 원본 메시지
            save_context_snapshot: 분석 컨텍스트 스냅샷 저장 여부
            query_source: 작업 출처(bot/api/cli/system)

        Returns:
            작업 제출 결과
        """
        if isinstance(report_type, str):
            report_type = ReportType.from_str(report_type)

        task_id = f"{code}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        self.executor.submit(
            self._run_analysis,
            code,
            task_id,
            report_type,
            source_message,
            save_context_snapshot,
            query_source,
        )

        logger.info(
            "[TaskService] 종목 %s 분석 작업을 제출했습니다. task_id=%s, report_type=%s",
            code,
            task_id,
            report_type.value,
        )

        return {
            "success": True,
            "message": "분석 작업이 제출되었습니다. 백그라운드에서 실행 후 알림을 전송합니다.",
            "code": code,
            "task_id": task_id,
            "report_type": report_type.value,
        }

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태를 반환합니다."""
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """최근 작업 목록을 반환합니다."""
        with self._tasks_lock:
            tasks = list(self._tasks.values())
        tasks.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        return tasks[:limit]

    def get_analysis_history(
        self,
        code: Optional[str] = None,
        query_id: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """분석 이력을 반환합니다."""
        db = get_db()
        records = db.get_analysis_history(code=code, query_id=query_id, days=days, limit=limit)
        return [r.to_dict() for r in records]

    def _run_analysis(
        self,
        code: str,
        task_id: str,
        report_type: ReportType = ReportType.SIMPLE,
        source_message: Optional[BotMessage] = None,
        save_context_snapshot: Optional[bool] = None,
        query_source: str = "bot",
    ) -> Dict[str, Any]:
        """
        단일 종목 분석을 실행합니다.

        내부 메서드이며 스레드 풀에서 실행됩니다.
        """
        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "running",
                "start_time": datetime.now().isoformat(),
                "result": None,
                "error": None,
                "report_type": report_type.value,
            }

        try:
            from src.config import get_config
            from main import StockAnalysisPipeline

            logger.info("[TaskService] 종목 분석을 시작합니다: %s", code)

            config = get_config()
            pipeline = StockAnalysisPipeline(
                config=config,
                max_workers=1,
                source_message=source_message,
                query_id=task_id,
                query_source=query_source,
                save_context_snapshot=save_context_snapshot,
            )

            result = pipeline.process_single_stock(
                code=code,
                skip_analysis=False,
                single_stock_notify=True,
                report_type=report_type,
            )

            if result and result.success:
                result_data = {
                    "code": result.code,
                    "name": result.name,
                    "sentiment_score": result.sentiment_score,
                    "operation_advice": result.operation_advice,
                    "trend_prediction": result.trend_prediction,
                    "analysis_summary": result.analysis_summary,
                }

                with self._tasks_lock:
                    self._tasks[task_id].update(
                        {
                            "status": "completed",
                            "end_time": datetime.now().isoformat(),
                            "result": result_data,
                        }
                    )

                logger.info("[TaskService] 종목 %s 분석 완료: %s", code, result.operation_advice)
                return {"success": True, "task_id": task_id, "result": result_data}

            fail_message = "분석 결과가 비어 있습니다"
            if result is not None:
                fail_message = result.error_message or fail_message
            with self._tasks_lock:
                self._tasks[task_id].update(
                    {
                        "status": "failed",
                        "end_time": datetime.now().isoformat(),
                        "error": fail_message,
                    }
                )

            logger.warning("[TaskService] 종목 %s 분석 실패: %s", code, fail_message)
            return {"success": False, "task_id": task_id, "error": fail_message}

        except Exception as e:
            error_msg = str(e)
            logger.error("[TaskService] 종목 %s 분석 중 예외 발생: %s", code, error_msg)

            with self._tasks_lock:
                self._tasks[task_id].update(
                    {
                        "status": "failed",
                        "end_time": datetime.now().isoformat(),
                        "error": error_msg,
                    }
                )

            return {"success": False, "task_id": task_id, "error": error_msg}


def get_task_service() -> TaskService:
    """TaskService 싱글턴을 반환합니다."""
    return TaskService.get_instance()
