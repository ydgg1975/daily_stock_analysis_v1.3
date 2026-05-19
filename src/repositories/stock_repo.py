# -*- coding: utf-8 -*-
"""
===================================
stockshujufangwenceng
===================================

zhize竊?
1. fengzhuangstockshujudeshujukucaozuo
2. tigongrixianshujuchaxunjiekou
"""

import logging
from datetime import date
from typing import Optional, List, Dict, Any

import pandas as pd
from sqlalchemy import and_, desc, select

from src.storage import DatabaseManager, StockDaily

logger = logging.getLogger(__name__)


class StockRepository:
    """
    stockshujufangwenceng
    
    fengzhuang StockDaily biaodeshujukucaozuo
    """
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        """
        chushihuashujufangwenceng
        
        Args:
            db_manager: shujukuguanliqi竊늟exuan竊똫orenshiyongdanli竊?
        """
        self.db = db_manager or DatabaseManager.get_instance()
    
    def get_latest(self, code: str, days: int = 2) -> List[StockDaily]:
        """
        huoquzuijin N tiandeshuju
        
        Args:
            code: stockdaima
            days: huoqutianshu
            
        Returns:
            StockDaily duixiangliebiao竊늏nriqijiangxu竊?
        """
        try:
            return self.db.get_latest_data(code, days)
        except Exception as e:
            logger.error(f"huoquzuixinshujushibai: {e}")
            return []
    
    def get_range(
        self,
        code: str,
        start_date: date,
        end_date: date
    ) -> List[StockDaily]:
        """
        huoquzhidingriqifanweideshuju
        
        Args:
            code: stockdaima
            start_date: kaishiriqi
            end_date: jieshuriqi
            
        Returns:
            StockDaily duixiangliebiao
        """
        try:
            return self.db.get_data_range(code, start_date, end_date)
        except Exception as e:
            logger.error(f"huoquriqifanweishujushibai: {e}")
            return []
    
    def save_dataframe(
        self,
        df: pd.DataFrame,
        code: str,
        data_source: str = "Unknown"
    ) -> int:
        """
        save DataFrame daoshujuku
        
        Args:
            df: baohanrixianshujude DataFrame
            code: stockdaima
            data_source: shujulaiyuan
            
        Returns:
            savederecordshu
        """
        try:
            return self.db.save_daily_data(df, code, data_source)
        except Exception as e:
            logger.error(f"saverixianshujushibai: {e}")
            return 0
    
    def has_today_data(self, code: str, target_date: Optional[date] = None) -> bool:
        """
        jianchashifouyouzhidingriqideshuju
        
        Args:
            code: stockdaima
            target_date: mubiaoriqi竊늤orenjintian竊?
            
        Returns:
            shifoucunzaishuju
        """
        try:
            return self.db.has_today_data(code, target_date)
        except Exception as e:
            logger.error(f"jianchashujucunzaishibai: {e}")
            return False
    
    def get_analysis_context(
        self, 
        code: str, 
        target_date: Optional[date] = None
    ) -> Optional[Dict[str, Any]]:
        """
        huoquanalysisshangxiawen
        
        Args:
            code: stockdaima
            target_date: mubiaoriqi
            
        Returns:
            analysisshangxiawenzidian
        """
        try:
            return self.db.get_analysis_context(code, target_date)
        except Exception as e:
            logger.error(f"huoquanalysisshangxiawenshibai: {e}")
            return None

    def get_start_daily(self, *, code: str, analysis_date: date) -> Optional[StockDaily]:
        """Return StockDaily for analysis_date (preferred) or nearest previous date."""
        with self.db.get_session() as session:
            row = session.execute(
                select(StockDaily)
                .where(and_(StockDaily.code == code, StockDaily.date <= analysis_date))
                .order_by(desc(StockDaily.date))
                .limit(1)
            ).scalar_one_or_none()
            return row

    def get_forward_bars(self, *, code: str, analysis_date: date, eval_window_days: int) -> List[StockDaily]:
        """Return forward daily bars after analysis_date, up to eval_window_days."""
        with self.db.get_session() as session:
            rows = session.execute(
                select(StockDaily)
                .where(and_(StockDaily.code == code, StockDaily.date > analysis_date))
                .order_by(StockDaily.date)
                .limit(eval_window_days)
            ).scalars().all()
            return list(rows)

