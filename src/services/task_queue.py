# -*- coding: utf-8 -*-
"""
===================================
Aguwatchlistguzhinenganalysisxitong - yiburenwuduilie
===================================

zhize竊?
1. guanliyibuanalysisrenwudeshengmingzhouqi
2. fangzhixiangtongstockdaimachongfutijiao
3. tigong SSE shijianguangbojizhi
4. renwuwanchenghouchijiuhuadaoshujuku
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any, TYPE_CHECKING, Tuple, Literal, Callable

if TYPE_CHECKING:
    from asyncio import Queue as AsyncQueue

from data_provider.base import canonical_stock_code, normalize_stock_code
from src.utils.analysis_metadata import SELECTION_SOURCES

logger = logging.getLogger(__name__)


def _dedupe_stock_code_key(stock_code: str) -> str:
    """
    Build the internal duplicate-detection key for a stock code.

    The task queue should treat equivalent market code shapes as the same
    underlying stock, e.g. ``600519`` and ``600519.SH``.
    """
    return canonical_stock_code(normalize_stock_code(stock_code))


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"        # Waiting for execution
    PROCESSING = "processing"  # In progress
    COMPLETED = "completed"    # Completed
    FAILED = "failed"          # Failed


@dataclass
class TaskInfo:
    """
    Task information dataclass.

    Used for API responses and internal task management.
    """
    task_id: str
    stock_code: str
    stock_name: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    report_type: str = "detailed"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    original_query: Optional[str] = None
    selection_source: Optional[str] = None
    skills: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task info into an API-friendly dictionary."""
        return {
            "task_id": self.task_id,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "report_type": self.report_type,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "original_query": self.original_query,
            "selection_source": self.selection_source,
            "skills": self.skills,
        }
    
    def copy(self) -> 'TaskInfo':
        """Create a shallow copy of the task information."""
        return TaskInfo(
            task_id=self.task_id,
            stock_code=self.stock_code,
            stock_name=self.stock_name,
            status=self.status,
            progress=self.progress,
            message=self.message,
            result=self.result,
            error=self.error,
            report_type=self.report_type,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            original_query=self.original_query,
            selection_source=self.selection_source,
            skills=list(self.skills) if self.skills is not None else None,
        )


class DuplicateTaskError(Exception):
    """
    chongfutijiaoyichang
    
    dangstockyizaianalysisretrypaochuciyichang
    """
    def __init__(self, stock_code: str, existing_task_id: str):
        self.stock_code = stock_code
        self.existing_task_id = existing_task_id
        super().__init__(f"stock {stock_code} in_progressanalysiszhong (task_id: {existing_task_id})")


class AnalysisTaskQueue:
    """
    yibuanalysisrenwuduilie
    
    danlimoshi竊똰uanjuweiyishili
    
    texing竊?
    1. fangzhixiangtongstockdaimachongfutijiao
    2. xianchengchizhixinganalysisrenwu
    3. SSE shijianguangbojizhi
    4. renwuwanchenghouzidongchijiuhua
    """
    
    _instance: Optional['AnalysisTaskQueue'] = None
    _instance_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, max_workers: int = 3):
        # fangzhichongfuchushihua
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self._max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        
        # hexinshujujiegou
        self._tasks: Dict[str, TaskInfo] = {}           # task_id -> TaskInfo
        self._analyzing_stocks: Dict[str, str] = {}     # dedupe_key -> task_id
        self._futures: Dict[str, Future] = {}           # task_id -> Future
        
        # SSE dingyuezheliebiao竊늏syncio.Queue shili竊?
        self._subscribers: List['AsyncQueue'] = []
        self._subscribers_lock = threading.Lock()
        
        # zhushijianxunhuanyinyong竊늶ongyukuaxianchengguangbo竊?
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # xianchenganquansuo
        self._data_lock = threading.RLock()
        
        # renwulishibaoliushuliang竊늧eicunzhong竊?
        self._max_history = 100
        
        self._initialized = True
        logger.info(f"[TaskQueue] chushihuawancheng竊똺uidabingfa: {max_workers}")
    
    @property
    def executor(self) -> ThreadPoolExecutor:
        """lanjiazaixianchengchi"""
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="analysis_task_"
            )
        return self._executor

    @property
    def max_workers(self) -> int:
        """Return current executor max worker setting."""
        return self._max_workers

    def _has_inflight_tasks_locked(self) -> bool:
        """Check whether queue has any pending/processing tasks."""
        if self._analyzing_stocks:
            return True
        return any(
            task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)
            for task in self._tasks.values()
        )

    def sync_max_workers(
        self,
        max_workers: int,
        *,
        log: bool = True,
    ) -> Literal["applied", "unchanged", "deferred_busy"]:
        """
        Try to sync queue concurrency without replacing singleton instance.

        Returns:
            - "applied": new value applied immediately (idle queue only)
            - "unchanged": target equals current value or invalid target
            - "deferred_busy": queue is busy, apply is deferred
        """
        try:
            target = max(1, int(max_workers))
        except (TypeError, ValueError):
            if log:
                logger.warning("[TaskQueue] hulvefeifa MAX_WORKERS zhi: %r", max_workers)
            return "unchanged"

        executor_to_shutdown: Optional[ThreadPoolExecutor] = None
        previous: int
        with self._data_lock:
            previous = self._max_workers
            if target == previous:
                return "unchanged"

            if self._has_inflight_tasks_locked():
                if log:
                    logger.info(
                        "[TaskQueue] zuidabingfatiaozhengyanhou: dangqianfanmang (%s -> %s)",
                        previous,
                        target,
                    )
                return "deferred_busy"

            self._max_workers = target
            executor_to_shutdown = self._executor
            self._executor = None

        if executor_to_shutdown is not None:
            executor_to_shutdown.shutdown(wait=False)

        if log:
            logger.info("[TaskQueue] zuidabingfayigengxin: %s -> %s", previous, target)
        return "applied"
    
    # ========== renwutijiaoyuchaxun ==========
    
    def is_analyzing(self, stock_code: str) -> bool:
        """
        jianchastockshifouin_progressanalysiszhong
        
        Args:
            stock_code: stockdaima
            
        Returns:
            True biaoshiin_progressanalysiszhong
        """
        dedupe_key = _dedupe_stock_code_key(stock_code)
        with self._data_lock:
            return dedupe_key in self._analyzing_stocks
    
    def get_analyzing_task_id(self, stock_code: str) -> Optional[str]:
        """
        huoquin_progressanalysisgaistockderenwu ID
        
        Args:
            stock_code: stockdaima
            
        Returns:
            renwu ID竊똱uguomeiyouzefanhui None
        """
        dedupe_key = _dedupe_stock_code_key(stock_code)
        with self._data_lock:
            return self._analyzing_stocks.get(dedupe_key)

    def validate_selection_source(self, selection_source: Optional[str]) -> None:
        """
        Validate the selection source parameter.

        Args:
            selection_source: Selection source label.

        Raises:
            ValueError: Raised when the selection source is invalid.
        """
        if selection_source is not None and selection_source not in SELECTION_SOURCES:
            raise ValueError(
                f"Invalid selection_source: {selection_source}. "
                f"Must be one of {SELECTION_SOURCES}"
            )
    
    def submit_task(
        self,
        stock_code: str,
        stock_name: Optional[str] = None,
        original_query: Optional[str] = None,
        selection_source: Optional[str] = None,
        report_type: str = "detailed",
        force_refresh: bool = False,
        skills: Optional[List[str]] = None,
    ) -> TaskInfo:
        """
        Submit a single analysis task.

        Args:
            stock_code: Stock code
            stock_name: Optional stock name
            original_query: Optional raw user input
            selection_source: Optional source label
            report_type: Report type
            force_refresh: Whether to bypass cache

        Returns:
            TaskInfo: Accepted task information

        Raises:
            DuplicateTaskError: Raised when the stock is already being analyzed
        """
        stock_code = canonical_stock_code(stock_code)
        if not stock_code:
            raise ValueError("종목 코드는 비어 있거나 공백만 포함할 수 없습니다.")

        accepted, duplicates = self.submit_tasks_batch(
            [stock_code],
            stock_name=stock_name,
            original_query=original_query,
            selection_source=selection_source,
            report_type=report_type,
            force_refresh=force_refresh,
            skills=skills,
        )
        if duplicates:
            raise duplicates[0]
        return accepted[0]

    def submit_tasks_batch(
        self,
        stock_codes: List[str],
        stock_name: Optional[str] = None,
        original_query: Optional[str] = None,
        selection_source: Optional[str] = None,
        report_type: str = "detailed",
        force_refresh: bool = False,
        notify: bool = True,
        skills: Optional[List[str]] = None,
    ) -> Tuple[List[TaskInfo], List[DuplicateTaskError]]:
        """
        Submit analysis tasks in batch.

        - Duplicate stocks are skipped and recorded in duplicates.
        - If executor submission fails, the current batch is rolled back.
        """
        self.validate_selection_source(selection_source)

        accepted: List[TaskInfo] = []
        duplicates: List[DuplicateTaskError] = []
        created_task_ids: List[str] = []

        canonical_codes = [
            normalized for normalized in (canonical_stock_code(code) for code in stock_codes)
            if normalized
        ]

        with self._data_lock:
            for stock_code in canonical_codes:
                dedupe_key = _dedupe_stock_code_key(stock_code)
                if dedupe_key in self._analyzing_stocks:
                    existing_task_id = self._analyzing_stocks[dedupe_key]
                    duplicates.append(DuplicateTaskError(stock_code, existing_task_id))
                    continue

                task_id = uuid.uuid4().hex
                task_skills = list(skills) if skills is not None else None
                task_info = TaskInfo(
                    task_id=task_id,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    status=TaskStatus.PENDING,
                    message="renwuyijiaruduilie",
                    report_type=report_type,
                    original_query=original_query,
                    selection_source=selection_source,
                    skills=task_skills,
                )
                self._tasks[task_id] = task_info
                self._analyzing_stocks[dedupe_key] = task_id

                try:
                    future = self.executor.submit(
                        self._execute_task,
                        task_id,
                        stock_code,
                        report_type,
                        force_refresh,
                        notify,
                        task_skills,
                    )
                except Exception:
                    # Roll back the current batch to avoid partial submission.
                    self._rollback_submitted_tasks_locked(created_task_ids + [task_id])
                    raise

                self._futures[task_id] = future
                accepted.append(task_info)
                created_task_ids.append(task_id)
                logger.info(f"[TaskQueue] renwuyitijiao: {stock_code} -> {task_id}")

            # Keep task_created ordered before worker-emitted task_started/task_completed.
            # Broadcasting here also preserves batch rollback semantics because we only
            # reach this point after every submit in the batch has succeeded.
            for task_info in accepted:
                self._broadcast_event("task_created", task_info.to_dict())

        return accepted, duplicates

    def submit_background_task(
        self,
        run_task: Callable[[], Optional[Any]],
        *,
        stock_code: str,
        stock_name: Optional[str] = None,
        report_type: str = "detailed",
        message: Optional[str] = "renwuyijiaruduilie",
        task_id: Optional[str] = None,
    ) -> TaskInfo:
        """
        Submit a generic background callable with task lifecycle tracking.

        This is used by callers that need task status visibility but do not
        map to standard per-stock async analysis flow.
        """
        task_id = task_id or uuid.uuid4().hex
        task_info = TaskInfo(
            task_id=task_id,
            stock_code=stock_code,
            stock_name=stock_name,
            status=TaskStatus.PENDING,
            message=message,
            report_type=report_type,
        )

        with self._data_lock:
            if task_id in self._tasks:
                raise ValueError(f"renwu ID yicunzai: {task_id}")
            self._tasks[task_id] = task_info
            try:
                future = self.executor.submit(self._execute_background_task, task_id, run_task)
            except Exception:
                del self._tasks[task_id]
                raise

            self._futures[task_id] = future
            self._broadcast_event("task_created", task_info.to_dict())

        return task_info.copy()

    def _rollback_submitted_tasks_locked(self, task_ids: List[str]) -> None:
        """현재 배치에서 생성됐지만 호출자에게 반환되지 않은 작업을 롤백합니다."""
        for task_id in task_ids:
            future = self._futures.pop(task_id, None)
            if future is not None:
                future.cancel()

            task = self._tasks.pop(task_id, None)
            if task:
                dedupe_key = _dedupe_stock_code_key(task.stock_code)
                if self._analyzing_stocks.get(dedupe_key) == task_id:
                    del self._analyzing_stocks[dedupe_key]
    
    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """
        huoqurenwuxinxi
        
        Args:
            task_id: renwu ID
            
        Returns:
            TaskInfo huo None
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            return task.copy() if task else None
    
    def list_pending_tasks(self) -> List[TaskInfo]:
        """
        huoqusuoyoujinxingzhongderenwu竊늩ending + processing竊?
        
        Returns:
            renwuliebiao竊늗uben竊?
        """
        with self._data_lock:
            return [
                task.copy() for task in self._tasks.values()
                if task.status in (TaskStatus.PENDING, TaskStatus.PROCESSING)
            ]
    
    def list_all_tasks(self, limit: int = 50) -> List[TaskInfo]:
        """
        huoqusuoyourenwu竊늏nchuangjianshijiandaoxu竊?
        
        Args:
            limit: fanhuishuliangxianzhi
            
        Returns:
            renwuliebiao竊늗uben竊?
        """
        with self._data_lock:
            tasks = sorted(
                self._tasks.values(),
                key=lambda t: t.created_at,
                reverse=True
            )
            return [t.copy() for t in tasks[:limit]]
    
    def get_task_stats(self) -> Dict[str, int]:
        """
        huoqurenwutongjixinxi
        
        Returns:
            tongjixinxizidian
        """
        with self._data_lock:
            stats = {
                "total": len(self._tasks),
                "pending": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0,
            }
            for task in self._tasks.values():
                stats[task.status.value] = stats.get(task.status.value, 0) + 1
            return stats

    def update_task_progress(
        self,
        task_id: str,
        progress: int,
        message: Optional[str] = None,
        *,
        event_type: str = "task_progress",
    ) -> Optional[TaskInfo]:
        """
        Update in-flight task progress and broadcast an SSE event.

        Only pending/processing tasks are updated. Progress is clamped to
        [0, 99] so terminal states remain controlled by completion/failure.
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task or task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
                return None

            next_progress = max(task.progress, max(0, min(99, int(progress))))
            changed = False
            if next_progress != task.progress:
                task.progress = next_progress
                changed = True
            if message is not None and message != task.message:
                task.message = message
                changed = True

            if not changed:
                return task.copy()

            task_snapshot = task.copy()

        self._broadcast_event(event_type, task_snapshot.to_dict())
        return task_snapshot
    
    # ========== renwuzhixing ==========
    
    def _execute_task(
        self,
        task_id: str,
        stock_code: str,
        report_type: str,
        force_refresh: bool,
        notify: bool = True,
        skills: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        zhixinganalysisrenwu竊늷aixianchengchizhongyunxing竊?
        
        Args:
            task_id: renwu ID
            stock_code: stockdaima
            report_type: baogaoleixing
            force_refresh: shifouqiangzhirefresh
            
        Returns:
            analysisjieguozidian
        """
        # gengxinzhuangtaiweichulizhong
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            task.message = "in_progressanalysiszhong..."
            task.progress = 10
        
        self._broadcast_event("task_started", task.to_dict())
        
        try:
            # daoruanalysisfuwu竊늶anchidaorubimianxunhuanyilai竊?
            from src.services.analysis_service import AnalysisService
            
            # zhixinganalysis
            service = AnalysisService()

            def _on_progress(progress: int, message: str) -> None:
                self.update_task_progress(task_id, progress, message)

            result = service.analyze_stock(
                stock_code=stock_code,
                report_type=report_type,
                force_refresh=force_refresh,
                query_id=task_id,
                send_notification=notify,
                progress_callback=_on_progress,
                skills=skills,
            )
            
            if result:
                # gengxinrenwuzhuangtaiweiwancheng
                with self._data_lock:
                    task = self._tasks.get(task_id)
                    if task:
                        task.status = TaskStatus.COMPLETED
                        task.progress = 100
                        task.completed_at = datetime.now()
                        task.result = result
                        task.message = "analysiswancheng"
                        task.stock_name = result.get("stock_name", task.stock_name)
                        
                        # conganalysiszhongjiheyichu
                        dedupe_key = _dedupe_stock_code_key(task.stock_code)
                        if dedupe_key in self._analyzing_stocks:
                            del self._analyzing_stocks[dedupe_key]
                
                self._broadcast_event("task_completed", task.to_dict())
                logger.info(f"[TaskQueue] renwuwancheng: {task_id} ({stock_code})")
                
                # qingliguoqirenwu
                self._cleanup_old_tasks()
                
                return result
            else:
                # analysisfanhuikongjieguo
                raise Exception(service.last_error or "analysisfanhuikongjieguo")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[TaskQueue] renwushibai: {task_id} ({stock_code}), cuowu: {error_msg}")
            
            with self._data_lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    task.error = error_msg[:200]  # xianzhicuowuxinxichangdu
                    task.message = f"analysisshibai: {error_msg[:50]}"
                    
                    # conganalysiszhongjiheyichu
                    dedupe_key = _dedupe_stock_code_key(task.stock_code)
                    if dedupe_key in self._analyzing_stocks:
                        del self._analyzing_stocks[dedupe_key]
            
            self._broadcast_event("task_failed", task.to_dict())
            
            # qingliguoqirenwu
            self._cleanup_old_tasks()
            
            return None

    def _execute_background_task(
        self,
        task_id: str,
        run_task: Callable[[], Optional[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        """
        zhixingtongyonghoutairenwu竊늷hichizidingyiyunxingluoji竊?

        Args:
            task_id: renwu ID
            run_task: renwuzhixinghanshu

        Returns:
            renwuzhixingjieguozidian竊늟exuan竊?
        """
        with self._data_lock:
            task = self._tasks.get(task_id)
            if not task:
                return None

            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            task.message = "renwuzhixingzhong"
            task.progress = 10
            self._broadcast_event("task_started", task.to_dict())

        try:
            result = run_task()
            if result is None:
                raise RuntimeError("renwufanhuikongjieguo竊똷eishengchengkechijiuhuaneirong")

            with self._data_lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100
                    task.completed_at = datetime.now()
                    task.result = result
                    task.message = "renwuzhixingwancheng"

            self._broadcast_event("task_completed", task.to_dict())
            logger.info(f"[TaskQueue] zidingyirenwuwancheng: {task_id}")

            self._cleanup_old_tasks()
            return result

        except Exception as e:  # pragma: no cover - behavior verified in downstream tests
            error_msg = str(e)
            logger.error(
                f"[TaskQueue] zidingyirenwushibai: {task_id}, cuowu: {error_msg}"
            )

            with self._data_lock:
                task = self._tasks.get(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    task.error = error_msg[:200]
                    task.message = f"renwushibai: {error_msg[:80]}"

            if task:
                self._broadcast_event("task_failed", task.to_dict())

            self._cleanup_old_tasks()
            return None
    
    def _cleanup_old_tasks(self) -> int:
        """
        qingliguoqideyiwanchengrenwu
        
        baoliuzuijin _max_history gerenwu
        
        Returns:
            qingliderenwushuliang
        """
        with self._data_lock:
            if len(self._tasks) <= self._max_history:
                return 0
            
            # anshijianpaixu竊똲hanchujiudeyiwanchengrenwu
            completed_tasks = sorted(
                [t for t in self._tasks.values()
                 if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)],
                key=lambda t: t.created_at
            )
            
            to_remove = len(self._tasks) - self._max_history
            removed = 0
            
            for task in completed_tasks[:to_remove]:
                del self._tasks[task.task_id]
                if task.task_id in self._futures:
                    del self._futures[task.task_id]
                removed += 1
            
            if removed > 0:
                logger.debug(f"[TaskQueue] qinglile {removed} geguoqirenwu")
            
            return removed
    
    # ========== SSE shijianguangbo ==========
    
    def subscribe(self, queue: 'AsyncQueue') -> None:
        """
        dingyuerenwushijian
        
        Args:
            queue: asyncio.Queue shili竊똹ongyujieshoushijian
        """
        with self._subscribers_lock:
            self._subscribers.append(queue)
            # buhuodangqianshijianxunhuan竊늶ingzaizhuxianchengde async shangxiawenzhongdiaoyong竊?
            try:
                self._main_loop = asyncio.get_running_loop()
            except RuntimeError:
                # ruguobuzai async shangxiawenzhong竊똠hangshihuoqushijianxunhuan
                try:
                    self._main_loop = asyncio.get_event_loop()
                except RuntimeError:
                    pass
            logger.debug(f"[TaskQueue] xindingyuezhejiaru竊똡angqiandingyuezheshu: {len(self._subscribers)}")
    
    def unsubscribe(self, queue: 'AsyncQueue') -> None:
        """
        quxiaodingyuerenwushijian
        
        Args:
            queue: yaoquxiaodingyuede asyncio.Queue shili
        """
        with self._subscribers_lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
                logger.debug(f"[TaskQueue] dingyuezhelikai竊똡angqiandingyuezheshu: {len(self._subscribers)}")
    
    def _broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        guangboshijiandaosuoyoudingyuezhe
        
        shiyong call_soon_threadsafe quebaokuaxianchenganquan
        
        Args:
            event_type: shijianleixing
            data: shijianshuju
        """
        event = {"type": event_type, "data": data}
        
        with self._subscribers_lock:
            subscribers = self._subscribers.copy()
            loop = self._main_loop
        
        if not subscribers:
            return
        
        if loop is None:
            logger.warning("[TaskQueue] wufaguangboshijian竊쉦hushijianxunhuanweishezhi")
            return
        
        for queue in subscribers:
            try:
                # shiyong call_soon_threadsafe jiangshijianfangru asyncio duilie
                # zheshiconggongzuoxianchengxiangzhushijianxunhuansendxiaoxideanquanfangshi
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError as e:
                # shijianxunhuanyiclose
                logger.debug(f"[TaskQueue] guangboshijiantiaoguo竊늵unhuanyiclose竊? {e}")
            except Exception as e:
                logger.warning(f"[TaskQueue] guangboshijianshibai: {e}")
    
    # ========== qinglifangfa ==========
    
    def shutdown(self) -> None:
        """작업 큐를 종료합니다."""
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
            logger.info("[TaskQueue] xianchengchiyiclose")


# ========== bianjiehanshu ==========

def get_task_queue() -> AnalysisTaskQueue:
    """
    huoqurenwuduiliedanli
    
    Returns:
        AnalysisTaskQueue shili
    """
    queue = AnalysisTaskQueue()
    try:
        from src.config import get_config

        config = get_config()
        target_workers = max(1, int(getattr(config, "max_workers", queue.max_workers)))
        queue.sync_max_workers(target_workers, log=False)
    except Exception as exc:
        logger.debug("[TaskQueue] duqu MAX_WORKERS shibai竊똲hiyongdangqianbingfashezhi: %s", exc)

    return queue

