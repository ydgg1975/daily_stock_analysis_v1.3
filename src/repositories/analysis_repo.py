# -*- coding: utf-8 -*-
"""
===================================
analysislishishujufangwenceng
===================================

zhize竊?
1. fengzhuanganalysislishishujudeshujukucaozuo
2. tigong CRUD jiekou
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from src.storage import DatabaseManager, AnalysisHistory

logger = logging.getLogger(__name__)


class AnalysisRepository:
    """
    analysislishishujufangwenceng
    
    fengzhuang AnalysisHistory biaodeshujukucaozuo
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        chushihuashujufangwenceng
        
        Args:
            db_manager: shujukuguanliqi竊늟exuan竊똫orenshiyongdanli竊?
        """
        self.db = db_manager or DatabaseManager.get_instance()
    
    def get_by_query_id(self, query_id: str) -> Optional[AnalysisHistory]:
        """
        genju query_id huoquanalysisrecord
        
        Args:
            query_id: chaxun ID
            
        Returns:
            AnalysisHistory duixiang竊똟ucunzaifanhui None
        """
        try:
            records = self.db.get_analysis_history(query_id=query_id, limit=1)
            return records[0] if records else None
        except Exception as e:
            logger.error(f"chaxunanalysisrecordshibai: {e}")
            return None
    
    def get_list(
        self,
        code: Optional[str] = None,
        days: int = 30,
        limit: int = 50
    ) -> List[AnalysisHistory]:
        """
        huoquanalysisrecordliebiao
        
        Args:
            code: stockdaimashaixuan
            days: shijianfanwei竊늯ian竊?
            limit: fanhuishuliangxianzhi
            
        Returns:
            AnalysisHistory duixiangliebiao
        """
        try:
            return self.db.get_analysis_history(
                code=code,
                days=days,
                limit=limit
            )
        except Exception as e:
            logger.error(f"huoquanalysisliebiaoshibai: {e}")
            return []
    
    def save(
        self,
        result: Any,
        query_id: str,
        report_type: str,
        news_content: Optional[str] = None,
        context_snapshot: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        saveanalysisjieguo
        
        Args:
            result: analysisjieguoduixiang
            query_id: chaxun ID
            report_type: baogaoleixing
            news_content: xinwenneirong
            context_snapshot: shangxiawenkuaizhao
            
        Returns:
            savederecordshu
        """
        try:
            return self.db.save_analysis_history(
                result=result,
                query_id=query_id,
                report_type=report_type,
                news_content=news_content,
                context_snapshot=context_snapshot
            )
        except Exception as e:
            logger.error(f"saveanalysisjieguoshibai: {e}")
            return 0
    
    def count_by_code(self, code: str, days: int = 30) -> int:
        """
        tongjizhidingstockdeanalysisrecordshu
        
        Args:
            code: stockdaima
            days: shijianfanwei竊늯ian竊?
            
        Returns:
            recordshuliang
        """
        try:
            records = self.db.get_analysis_history(code=code, days=days, limit=1000)
            return len(records)
        except Exception as e:
            logger.error(f"tongjianalysisrecordshibai: {e}")
            return 0

