# -*- coding: utf-8 -*-
"""
===================================
yiburenwufuwuceng
===================================

zhize竊?
1. guanliyibuanalysisrenwu竊늵ianchengchi竊?
2. zhixingstockanalysisbingtuisongjieguo
3. chaxunrenwuzhuangtaihelishi

qianyizi web/services.py de AnalysisService lei
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
    yiburenwufuwu

    fuze竊?
    1. guanliyibuanalysisrenwu
    2. zhixingstockanalysis
    3. chufanotificationtuisong
    """

    _instance: Optional['TaskService'] = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 3):
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers = max_workers
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'TaskService':
        """huoqudanlishili"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @property
    def executor(self) -> ThreadPoolExecutor:
        """huoquhuochuangjianxianchengchi"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="analysis_"
            )
        return self._executor

    def submit_analysis(
        self,
        code: str,
        report_type: Union[ReportType, str] = ReportType.SIMPLE,
        source_message: Optional[BotMessage] = None,
        save_context_snapshot: Optional[bool] = None,
        query_source: str = "bot"
    ) -> Dict[str, Any]:
        """
        tijiaoyibuanalysisrenwu

        Args:
            code: stockdaima
            report_type: baogaoleixingmeiju
            source_message: laiyuanxiaoxi竊늶ongyuhuifu竊?
            save_context_snapshot: shifousaveshangxiawenkuaizhao
            query_source: renwulaiyuanbiaoshi竊늒ot/api/cli/system竊?

        Returns:
            renwuxinxizidian
        """
        # quebao report_type shimeijuleixing
        if isinstance(report_type, str):
            report_type = ReportType.from_str(report_type)

        task_id = f"{code}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        # tijiaodaoxianchengchi
        self.executor.submit(
            self._run_analysis,
            code,
            task_id,
            report_type,
            source_message,
            save_context_snapshot,
            query_source
        )

        logger.info(f"[TaskService] yitijiaostock {code} deanalysisrenwu, task_id={task_id}, report_type={report_type.value}")

        return {
            "success": True,
            "message": "analysisrenwuyitijiao竊똨iangyibuzhixingbingtuisongnotification",
            "code": code,
            "task_id": task_id,
            "report_type": report_type.value
        }

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """huoqurenwuzhuangtai"""
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """liechuzuijinderenwu"""
        with self._tasks_lock:
            tasks = list(self._tasks.values())
        # ankaishishijiandaoxu
        tasks.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return tasks[:limit]

    def get_analysis_history(
        self,
        code: Optional[str] = None,
        query_id: Optional[str] = None,
        days: int = 30,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """huoquanalysislishirecord"""
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
        query_source: str = "bot"
    ) -> Dict[str, Any]:
        """
        zhixingdanzhistockanalysis

        neibufangfa竊똺aixianchengchizhongyunxing
        """
        # chushihuarenwuzhuangtai
        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "running",
                "start_time": datetime.now().isoformat(),
                "result": None,
                "error": None,
                "report_type": report_type.value
            }

        try:
            # yanchidaorubimianxunhuanyilai
            from src.config import get_config
            from main import StockAnalysisPipeline

            logger.info(f"[TaskService] kaishianalysisstock: {code}")

            # chuangjiananalysisguandao
            config = get_config()
            pipeline = StockAnalysisPipeline(
                config=config,
                max_workers=1,
                source_message=source_message,
                query_id=task_id,
                query_source=query_source,
                save_context_snapshot=save_context_snapshot
            )

            # zhixingdanzhistockanalysis竊늫iyongdangutuisong竊?
            result = pipeline.process_single_stock(
                code=code,
                skip_analysis=False,
                single_stock_notify=True,
                report_type=report_type
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
                    self._tasks[task_id].update({
                        "status": "completed",
                        "end_time": datetime.now().isoformat(),
                        "result": result_data
                    })

                logger.info(f"[TaskService] stock {code} analysiswancheng: {result.operation_advice}")
                return {"success": True, "task_id": task_id, "result": result_data}
            else:
                fail_message = "analysisfanhuikongjieguo"
                if result is not None:
                    fail_message = result.error_message or fail_message
                with self._tasks_lock:
                    self._tasks[task_id].update({
                        "status": "failed",
                        "end_time": datetime.now().isoformat(),
                        "error": fail_message
                    })

                logger.warning(f"[TaskService] stock {code} analysisshibai: {fail_message}")
                return {"success": False, "task_id": task_id, "error": fail_message}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[TaskService] stock {code} analysisyichang: {error_msg}")

            with self._tasks_lock:
                self._tasks[task_id].update({
                    "status": "failed",
                    "end_time": datetime.now().isoformat(),
                    "error": error_msg
                })

            return {"success": False, "task_id": task_id, "error": error_msg}


# ============================================================
# bianjiehanshu
# ============================================================

def get_task_service() -> TaskService:
    """huoqurenwufuwudanli"""
    return TaskService.get_instance()

