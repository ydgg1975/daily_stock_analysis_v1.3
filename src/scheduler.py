# -*- coding: utf-8 -*-
"""
===================================
dingshidiaodumokuai
===================================

zhize竊?
1. zhichimeiridingshizhixingstockanalysis
2. zhichidingshizhixingdapanfupan
3. youyachulixinhao竊똰uebaokekaotuichu

yilai竊?
- schedule: qingliangjidingshirenwuku
"""

import logging
import re
import signal
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class GracefulShutdown:
    """
    youyatuichuchuliqi

    buhuo SIGTERM/SIGINT xinhao竊똰uebaorenwuwanchenghouzaituichu
    """

    def __init__(self):
        self.shutdown_requested = False
        self._lock = threading.Lock()

        # zhucexinhaochuliqi
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """xinhaochulihanshu"""
        with self._lock:
            if not self.shutdown_requested:
                logger.info(f"shoudaotuichuxinhao ({signum})竊똡engdaidangqianrenwuwancheng...")
                self.shutdown_requested = True

    @property
    def should_shutdown(self) -> bool:
        """jianchashifouyinggaituichu"""
        with self._lock:
            return self.shutdown_requested


class Scheduler:
    """
    dingshirenwudiaoduqi

    jiyu schedule kushixian竊똺hichi竊?
    - meiridingshizhixing
    - qidongshilijizhixing
    - youyatuichu
    """

    def __init__(
        self,
        schedule_time: str = "18:00",
        schedule_time_provider: Optional[Callable[[], str]] = None,
    ):
        """
        chushihuadiaoduqi

        Args:
            schedule_time: meirizhixingshijian竊똤eshi "HH:MM"
        """
        try:
            import schedule
            self.schedule = schedule
        except ImportError:
            logger.error("schedule kuweianzhuang竊똰ingzhixing: pip install schedule")
            raise ImportError("qinganzhuang schedule ku: pip install schedule")

        self.schedule_time = schedule_time
        self._schedule_time_provider = schedule_time_provider
        self.shutdown_handler = GracefulShutdown()
        self._task_callback: Optional[Callable] = None
        self._daily_job: Optional[Any] = None
        self._background_tasks: List[Dict[str, Any]] = []
        self._running = False

    def set_daily_task(self, task: Callable, run_immediately: bool = True):
        """
        shezhimeiridingshirenwu

        Args:
            task: yaozhixingderenwuhanshu竊늳ucanshu竊?
            run_immediately: shifouzaishezhihoulijizhixingyici
        """
        self._task_callback = task
        if not self._configure_daily_task(self.schedule_time):
            raise ValueError(f"wuxiaodedingshizhixingshijian: {self.schedule_time!r}")

        if run_immediately:
            logger.info("lijizhixingyicirenwu...")
            self._safe_run_task()

    @staticmethod
    def _is_valid_schedule_time(schedule_time: str) -> bool:
        """Validate time string in HH:MM 24-hour format."""
        candidate = (schedule_time or "").strip()
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", candidate):
            return False
        return True

    def _cancel_daily_job(self) -> None:
        """Remove the currently registered daily job if one exists."""
        if self._daily_job is None:
            return

        if hasattr(self.schedule, "cancel_job"):
            self.schedule.cancel_job(self._daily_job)
        else:  # pragma: no cover - compatibility fallback
            jobs = getattr(self.schedule, "jobs", None)
            if isinstance(jobs, list) and self._daily_job in jobs:
                jobs.remove(self._daily_job)

        self._daily_job = None

    def _configure_daily_task(self, schedule_time: str) -> bool:
        """(Re)register the daily job at the requested time."""
        candidate = (schedule_time or "").strip()
        if not self._is_valid_schedule_time(candidate):
            logger.warning(
                "jiancedaowuxiaodedingshizhixingshijian %r竊똨ixuyanyongdangqianshijian %s",
                schedule_time,
                self.schedule_time,
            )
            return False

        previous_time = self.schedule_time
        self._cancel_daily_job()
        self._daily_job = self.schedule.every().day.at(candidate).do(self._safe_run_task)
        self.schedule_time = candidate

        if previous_time == candidate:
            logger.info("yishezhimeiridingshirenwu竊똺hixingshijian: %s", self.schedule_time)
        else:
            logger.info(
                "jiancedao SCHEDULE_TIME biangeng竊똹ijiangmeiridingshirenwucong %s gengxinwei %s",
                previous_time,
                self.schedule_time,
            )
        return True

    def _refresh_daily_schedule_if_needed(self) -> None:
        """Reload daily schedule time from the latest runtime config if needed."""
        if self._task_callback is None or self._schedule_time_provider is None:
            return

        try:
            latest_schedule_time = (self._schedule_time_provider() or "").strip()
        except Exception as exc:  # pragma: no cover - defensive branch
            logger.warning("duquzuixin SCHEDULE_TIME shibai竊똨ixuyanyong %s: %s", self.schedule_time, exc)
            return

        if not latest_schedule_time or latest_schedule_time == self.schedule_time:
            return

        if self._configure_daily_task(latest_schedule_time):
            logger.info("gengxinhoudexiacizhixingshijian: %s", self._get_next_run_time())

    def _safe_run_task(self):
        """예외를 잡으면서 예약 작업을 안전하게 실행합니다."""
        if self._task_callback is None:
            return

        try:
            logger.info("=" * 50)
            logger.info(f"dingshirenwukaishizhixing - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 50)

            self._task_callback()

            logger.info(f"dingshirenwuzhixingwancheng - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            logger.exception(f"dingshirenwuzhixingshibai: {e}")

    def add_background_task(
        self,
        task: Callable,
        interval_seconds: int,
        run_immediately: bool = False,
        name: Optional[str] = None,
    ) -> None:
        """Register a periodic background task executed inside the scheduler loop.

        Note: The scheduler loop polls every 30 seconds, so *interval_seconds*
        below 30 will be clamped to 30 to avoid promising unreachable precision.
        """
        clamped_interval = max(30, int(interval_seconds))
        if int(interval_seconds) < 30:
            logger.warning(
                "houtairenwu %s qingqiujiange %ds竊똡andiaoduxunhuanmei 30s lunxunyici竊똹izidongtiaozhengwei 30s",
                name or getattr(task, "__name__", "background_task"),
                interval_seconds,
            )
        entry = {
            "task": task,
            "interval_seconds": clamped_interval,
            "last_run": 0.0,
            "name": name or getattr(task, "__name__", "background_task"),
            "thread": None,
            "running": False,
        }
        if not run_immediately:
            entry["last_run"] = time.time()
        self._background_tasks.append(entry)
        logger.info(
            "백그라운드 작업 등록: %s (간격 %s초, 즉시 실행=%s)",
            entry["name"],
            entry["interval_seconds"],
            run_immediately,
        )
        if run_immediately:
            self._start_background_task(entry)

    def _start_background_task(self, entry: Dict[str, Any]) -> bool:
        """Start one background task in a dedicated daemon thread."""
        worker = entry.get("thread")
        if worker is not None and worker.is_alive():
            return False

        def _runner() -> None:
            try:
                logger.info("houtairenwukaishizhixing: %s", entry["name"])
                entry["task"]()
            except Exception as exc:
                logger.exception("houtairenwuzhixingshibai [%s]: %s", entry["name"], exc)
            finally:
                entry["running"] = False
                entry["thread"] = None

        entry["last_run"] = time.time()
        entry["running"] = True
        worker = threading.Thread(
            target=_runner,
            daemon=True,
            name=f"scheduler-bg-{entry['name']}",
        )
        entry["thread"] = worker
        worker.start()
        return True

    def _run_background_tasks(self) -> None:
        """Execute any background tasks whose interval has elapsed."""
        if not self._background_tasks:
            return

        now = time.time()
        for entry in self._background_tasks:
            worker = entry.get("thread")
            if worker is not None and worker.is_alive():
                continue
            if entry.get("running"):
                entry["running"] = False
                entry["thread"] = None
            if now - entry["last_run"] < entry["interval_seconds"]:
                continue
            self._start_background_task(entry)

    def run(self):
        """
        yunxingdiaoduqizhuxunhuan

        zuseyunxing竊똺hidaoshoudaotuichuxinhao
        """
        self._running = True
        logger.info("diaoduqikaishiyunxing...")
        logger.info(f"xiacizhixingshijian: {self._get_next_run_time()}")

        while self._running and not self.shutdown_handler.should_shutdown:
            self._refresh_daily_schedule_if_needed()
            self.schedule.run_pending()
            self._run_background_tasks()
            time.sleep(30)  # mei30miaojianchayici

            # meixiaoshidayinyicixintiao
            if datetime.now().minute == 0 and datetime.now().second < 30:
                logger.info(f"diaoduqiyunxingzhong... xiacizhixing: {self._get_next_run_time()}")

        logger.info("diaoduqiyitingzhi")

    def _get_next_run_time(self) -> str:
        """huoquxiacizhixingshijian"""
        jobs = self.schedule.get_jobs()
        if jobs:
            next_run = min(job.next_run for job in jobs)
            return next_run.strftime('%Y-%m-%d %H:%M:%S')
        return "weishezhi"

    def stop(self):
        """tingzhidiaoduqi"""
        self._running = False


def run_with_schedule(
    task: Callable,
    schedule_time: str = "18:00",
    run_immediately: bool = True,
    background_tasks: Optional[List[Dict[str, Any]]] = None,
    schedule_time_provider: Optional[Callable[[], str]] = None,
):
    """
    bianjiehanshu竊쉝hiyongdingshidiaoduyunxingrenwu

    Args:
        task: yaozhixingderenwuhanshu
        schedule_time: meirizhixingshijian
        run_immediately: shifoulijizhixingyici
        background_tasks: kexuandehoutairenwudingyiliebiao?굆eixiangweiyigezidian竊?
            xubaohan `task` yu `interval_seconds`竊똩exuanbaohan `name`
            he `run_immediately`??interval_seconds` danweiweimiao??
        schedule_time_provider: kexuandeshijiantigongqi竊쌶iaoduqimeilunjianchaqianhuiduqu竊?
            dangfanhuizhibianhuashizidongchongjian daily job??
    """
    scheduler = Scheduler(
        schedule_time=schedule_time,
        schedule_time_provider=schedule_time_provider,
    )
    for entry in background_tasks or []:
        scheduler.add_background_task(
            task=entry["task"],
            interval_seconds=entry["interval_seconds"],
            run_immediately=entry.get("run_immediately", False),
            name=entry.get("name"),
        )
    scheduler.set_daily_task(task, run_immediately=run_immediately)
    scheduler.run()


if __name__ == "__main__":
    # testdingshidiaodu
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    )

    def test_task():
        print(f"renwuzhixingzhong... {datetime.now()}")
        time.sleep(2)
        print("renwuwancheng!")

    print("테스트 스케줄러를 시작합니다. 종료하려면 Ctrl+C를 누르세요.")
    run_with_schedule(test_task, schedule_time="23:59", run_immediately=True)

