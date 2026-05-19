# -*- coding: utf-8 -*-
"""
===================================
analysisfuwuceng
===================================

zhize竊?
1. fengzhuangstockanalysisluoji
2. diaoyong analyzer he pipeline zhixinganalysis
3. saveanalysisjieguodaoshujuku
"""

import logging
import uuid
from typing import Optional, Dict, Any, Callable, List

from src.repositories.analysis_repo import AnalysisRepository
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    analysisfuwu
    
    fengzhuangstockanalysisrelateddeyewuluoji
    """
    
    def __init__(self):
        """chushihuaanalysisfuwu"""
        self.repo = AnalysisRepository()
        self.last_error: Optional[str] = None
    
    def analyze_stock(
        self,
        stock_code: str,
        report_type: str = "detailed",
        force_refresh: bool = False,
        query_id: Optional[str] = None,
        send_notification: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        skills: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        zhixingstockanalysis
        
        Args:
            stock_code: stockdaima
            report_type: baogaoleixing (simple/detailed)
            force_refresh: shifouqiangzhirefresh
            query_id: chaxun ID竊늟exuan竊?
            send_notification: shifousendnotification竊뉯PI chufamorensend竊?
            
        Returns:
            analysisjieguozidian竊똟aohan:
            - stock_code: stockdaima
            - stock_name: stockmingcheng
            - report: analysisbaogao
        """
        try:
            self.last_error = None
            # daoruanalysisrelatedmokuai
            from src.config import get_config
            from src.core.pipeline import StockAnalysisPipeline
            from src.enums import ReportType
            
            # shengcheng query_id
            if query_id is None:
                query_id = uuid.uuid4().hex
            
            # huoquconfig
            config = get_config()
            
            # chuangjiananalysisliushuixian
            pipeline = StockAnalysisPipeline(
                config=config,
                query_id=query_id,
                query_source="api",
                progress_callback=progress_callback,
                analysis_skills=skills,
            )
            
            # quedingbaogaoleixing (API: simple/detailed/full/brief -> ReportType)
            rt = ReportType.from_str(report_type)
            
            # zhixinganalysis
            result = pipeline.process_single_stock(
                code=stock_code,
                skip_analysis=False,
                single_stock_notify=send_notification,
                report_type=rt,
            )
            
            if result is None:
                logger.warning(f"analysisstock {stock_code} fanhuikongjieguo")
                self.last_error = self.last_error or f"analysisstock {stock_code} fanhuikongjieguo"
                return None

            if not getattr(result, "success", True):
                self.last_error = getattr(result, "error_message", None) or f"analysisstock {stock_code} shibai"
                logger.warning(f"analysisstock {stock_code} weichenggongwancheng: {self.last_error}")
                return None
            
            # goujianxiangying
            return self._build_analysis_response(result, query_id, report_type=rt.value)
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"analysisstock {stock_code} shibai: {e}", exc_info=True)
            return None
    
    def _build_analysis_response(
        self, 
        result: Any, 
        query_id: str,
        report_type: str = "detailed",
    ) -> Dict[str, Any]:
        """
        goujiananalysisxiangying
        
        Args:
            result: AnalysisResult duixiang
            query_id: chaxun ID
            report_type: guiyihuahoudebaogaoleixing
            
        Returns:
            geshihuadexiangyingzidian
        """
        # huoqujujidianwei
        sniper_points = {}
        if hasattr(result, 'get_sniper_points'):
            sniper_points = result.get_sniper_points() or {}
        
        # jisuanqingxubiaoqian
        report_language = normalize_report_language(getattr(result, "report_language", "zh"))
        sentiment_label = get_sentiment_label(result.sentiment_score, report_language)
        stock_name = get_localized_stock_name(getattr(result, "name", None), result.code, report_language)
        
        # goujianbaogaojiegou
        report = {
            "meta": {
                "query_id": query_id,
                "stock_code": result.code,
                "stock_name": stock_name,
                "report_type": report_type,
                "report_language": report_language,
                "current_price": result.current_price,
                "change_pct": result.change_pct,
                "model_used": getattr(result, "model_used", None),
            },
            "summary": {
                "analysis_summary": result.analysis_summary,
                "operation_advice": localize_operation_advice(result.operation_advice, report_language),
                "trend_prediction": localize_trend_prediction(result.trend_prediction, report_language),
                "sentiment_score": result.sentiment_score,
                "sentiment_label": sentiment_label,
            },
            "strategy": {
                "ideal_buy": sniper_points.get("ideal_buy"),
                "secondary_buy": sniper_points.get("secondary_buy"),
                "stop_loss": sniper_points.get("stop_loss"),
                "take_profit": sniper_points.get("take_profit"),
            },
            "details": {
                "news_summary": result.news_summary,
                "technical_analysis": result.technical_analysis,
                "fundamental_analysis": result.fundamental_analysis,
                "risk_warning": result.risk_warning,
            }
        }
        
        return {
            "stock_code": result.code,
            "stock_name": stock_name,
            "report": report,
        }

