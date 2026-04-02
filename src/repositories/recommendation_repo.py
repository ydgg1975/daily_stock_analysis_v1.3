# -*- coding: utf-8 -*-
"""
===================================
推荐选股数据访问层
===================================

职责：
1. 封装 RecommendationHistory 表的数据库操作
2. 提供 CRUD 接口
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from src.storage import DatabaseManager, RecommendationHistory

logger = logging.getLogger(__name__)


class RecommendationRepository:
    """推荐选股数据访问层"""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def create(self, task_id: str, markets: str,
               price_min: Optional[float] = None,
               price_max: Optional[float] = None,
               urls: Optional[str] = None,
               note: Optional[str] = None) -> int:
        """
        创建推荐记录（pending 状态）。

        Returns:
            记录 ID，失败返回 0
        """
        with self.db.session_scope() as session:
            try:
                record = RecommendationHistory(
                    task_id=task_id,
                    markets=markets,
                    price_min=price_min,
                    price_max=price_max,
                    urls=urls,
                    note=note,
                    status="pending",
                    created_at=datetime.now(),
                )
                session.add(record)
                session.flush()
                return record.id
            except Exception as e:
                logger.error("创建推荐记录失败: %s", e)
                return 0

    def update_completed(self, task_id: str, result: Dict[str, Any], model_used: str) -> bool:
        """标记为完成，保存结果"""
        from sqlalchemy import select
        with self.db.session_scope() as session:
            try:
                record = session.execute(
                    select(RecommendationHistory).where(RecommendationHistory.task_id == task_id)
                ).scalar_one_or_none()
                if not record:
                    return False
                record.status = "completed"
                record.result = json.dumps(result, ensure_ascii=False, default=str)
                record.model_used = model_used
                record.completed_at = datetime.now()
                return True
            except Exception as e:
                logger.error("更新推荐记录(completed)失败: %s", e)
                return False

    def update_failed(self, task_id: str, error: str) -> bool:
        """标记为失败"""
        from sqlalchemy import select
        with self.db.session_scope() as session:
            try:
                record = session.execute(
                    select(RecommendationHistory).where(RecommendationHistory.task_id == task_id)
                ).scalar_one_or_none()
                if not record:
                    return False
                record.status = "failed"
                record.error = error[:2000]
                record.completed_at = datetime.now()
                return True
            except Exception as e:
                logger.error("更新推荐记录(failed)失败: %s", e)
                return False

    def get_by_task_id(self, task_id: str) -> Optional[Dict[str, Any]]:
        """根据 task_id 查询记录"""
        from sqlalchemy import select
        with self.db.session_scope() as session:
            try:
                record = session.execute(
                    select(RecommendationHistory).where(RecommendationHistory.task_id == task_id)
                ).scalar_one_or_none()
                return record.to_dict() if record else None
            except Exception as e:
                logger.error("查询推荐记录失败: %s", e)
                return None

    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """根据主键 ID 查询记录"""
        from sqlalchemy import select
        with self.db.session_scope() as session:
            try:
                record = session.execute(
                    select(RecommendationHistory).where(RecommendationHistory.id == record_id)
                ).scalar_one_or_none()
                return record.to_dict() if record else None
            except Exception as e:
                logger.error("查询推荐记录失败: %s", e)
                return None

    def list_history(self, limit: int = 20, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """分页查询历史记录"""
        from sqlalchemy import select, func, desc
        with self.db.session_scope() as session:
            try:
                total = session.execute(
                    select(func.count(RecommendationHistory.id))
                ).scalar() or 0

                records = session.execute(
                    select(RecommendationHistory)
                    .order_by(desc(RecommendationHistory.created_at))
                    .offset(offset)
                    .limit(limit)
                ).scalars().all()

                items = [r.to_dict() for r in records]
                return items, total
            except Exception as e:
                logger.error("查询推荐历史失败: %s", e)
                return [], 0
