# -*- coding: utf-8 -*-
"""
===================================
分析历史数据访问层
===================================

职责：
1. 封装分析历史数据的数据库操作
2. 提供 CRUD 接口
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select

from src.storage import DatabaseManager, AnalysisHistory

logger = logging.getLogger(__name__)


class AnalysisRepository:
    """
    分析历史数据访问层
    
    封装 AnalysisHistory 表的数据库操作
    """
    
    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        *,
        owner_id: Optional[str] = None,
        include_all_owners: bool = False,
    ):
        """
        初始化数据访问层
        
        Args:
            db_manager: 数据库管理器（可选，默认使用单例）
        """
        self.db = db_manager or DatabaseManager.get_instance()
        self.owner_id = owner_id
        self.include_all_owners = bool(include_all_owners)
    
    def get_by_query_id(self, query_id: str) -> Optional[AnalysisHistory]:
        """
        根据 query_id 获取分析记录
        
        Args:
            query_id: 查询 ID
            
        Returns:
            AnalysisHistory 对象，不存在返回 None
        """
        try:
            records = self.db.get_analysis_history(
                query_id=query_id,
                limit=1,
                owner_id=self.owner_id,
                include_all_owners=self.include_all_owners,
            )
            return records[0] if records else None
        except Exception as e:
            logger.error(f"查询分析记录失败: {e}")
            return None

    def get_by_id(self, record_id: int) -> Optional[AnalysisHistory]:
        """Return a single analysis record by primary key."""
        try:
            return self.db.get_analysis_history_by_id(
                record_id,
                owner_id=self.owner_id,
                include_all_owners=self.include_all_owners,
            )
        except Exception as e:
            logger.error(f"根据 ID 查询分析记录失败: {e}")
            return None

    def get_latest_record(
        self,
        *,
        query_id: Optional[str] = None,
        code: Optional[str] = None,
    ) -> Optional[AnalysisHistory]:
        """Return the latest matching analysis record for a narrow filter set."""
        try:
            history_kwargs: Dict[str, Any] = {
                "query_id": query_id,
                "code": code,
                "limit": 1,
            }
            if self.owner_id is not None:
                history_kwargs["owner_id"] = self.owner_id
            if self.include_all_owners:
                history_kwargs["include_all_owners"] = True
            records = self.db.get_analysis_history(**history_kwargs)
            return records[0] if records else None
        except Exception as e:
            logger.error(f"获取最新分析记录失败: {e}")
            return None
    
    def get_list(
        self,
        code: Optional[str] = None,
        days: int = 30,
        limit: int = 50
    ) -> List[AnalysisHistory]:
        """
        获取分析记录列表
        
        Args:
            code: 股票代码筛选
            days: 时间范围（天）
            limit: 返回数量限制
            
        Returns:
            AnalysisHistory 对象列表
        """
        try:
            return self.db.get_analysis_history(
                code=code,
                days=days,
                limit=limit,
                owner_id=self.owner_id,
                include_all_owners=self.include_all_owners,
            )
        except Exception as e:
            logger.error(f"获取分析列表失败: {e}")
            return []

    def get_paginated(
        self,
        *,
        code: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[AnalysisHistory], int]:
        """Return paginated analysis history rows and total count."""
        try:
            return self.db.get_analysis_history_paginated(
                code=code,
                start_date=start_date,
                end_date=end_date,
                offset=offset,
                limit=limit,
                owner_id=self.owner_id,
                include_all_owners=self.include_all_owners,
            )
        except Exception as e:
            logger.error(f"分页获取分析历史失败: {e}")
            return [], 0
    
    def save(
        self,
        result: Any,
        query_id: str,
        report_type: str,
        news_content: Optional[str] = None,
        context_snapshot: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        保存分析结果
        
        Args:
            result: 分析结果对象
            query_id: 查询 ID
            report_type: 报告类型
            news_content: 新闻内容
            context_snapshot: 上下文快照
            
        Returns:
            保存的记录数
        """
        try:
            return self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type=report_type,
                news_content=news_content,
                context_snapshot=context_snapshot,
                owner_id=self.owner_id,
            )
        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")
            return 0
    
    def count_by_code(self, code: str, days: int = 30) -> int:
        """
        统计指定股票的分析记录数
        
        Args:
            code: 股票代码
            days: 时间范围（天）
            
        Returns:
            记录数量
        """
        try:
            records = self.db.get_analysis_history(
                code=code,
                days=days,
                limit=1000,
                owner_id=self.owner_id,
                include_all_owners=self.include_all_owners,
            )
            return len(records)
        except Exception as e:
            logger.error(f"统计分析记录失败: {e}")
            return 0

    def delete_records(self, record_ids: List[int]) -> int:
        """Delete analysis history rows by primary key."""
        return self.db.delete_analysis_history_records(
            record_ids,
            owner_id=self.owner_id,
            include_all_owners=self.include_all_owners,
        )

    def get_news_intel_by_query_id(self, *, query_id: str, limit: int = 20) -> List[Any]:
        """Return news intel rows for a query."""
        try:
            return self.db.get_news_intel_by_query_id(query_id=query_id, limit=limit)
        except Exception as e:
            logger.error(f"根据 query_id 查询新闻情报失败: {e}")
            return []

    def get_recent_news(self, *, code: str, days: int, limit: int) -> List[Any]:
        """Return recent news rows for a stock code."""
        try:
            return self.db.get_recent_news(code=code, days=days, limit=limit)
        except Exception as e:
            logger.error(f"查询近期新闻失败: {e}")
            return []

    def get_latest_fundamental_snapshot(
        self,
        *,
        query_id: str,
        code: str,
    ) -> Optional[Dict[str, Any]]:
        """Return the latest fundamental snapshot payload for a query/code pair."""
        try:
            return self.db.get_latest_fundamental_snapshot(
                query_id=query_id,
                code=code,
            )
        except Exception as e:
            logger.error(f"查询最新基本面快照失败: {e}")
            return None

    def list_recent_named_codes(self) -> List[Dict[str, Optional[str]]]:
        """Return recent analysis codes with their latest seen names."""
        with self.db.get_session() as session:
            rows = session.execute(
                select(AnalysisHistory.code, AnalysisHistory.name)
                .order_by(AnalysisHistory.created_at.desc())
            ).all()
        return [
            {"code": str(code or "").strip(), "name": str(name or "").strip() or None}
            for code, name in rows
            if code
        ]
