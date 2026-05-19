# -*- coding: utf-8 -*-
"""
===================================
stockzhinenganalysisxitong - dapanfupanmokuai竊늷hichi A gu / ganggu / meigu竊?
===================================

zhize竊?
1. genju MARKET_REVIEW_REGION configxuanzemarketquyu竊늓n / hk / us / both竊?
2. zhixingdapanfupananalysisbingshengchengfupanbaogao
3. savehesendfupanbaogao
"""

import logging
from datetime import datetime
from typing import Optional
import uuid

from src.config import get_config
from src.notification import NotificationService
from src.market_analyzer import MarketAnalyzer
from src.report_language import normalize_report_language
from src.search_service import SearchService
from src.analyzer import AnalysisResult, GeminiAnalyzer


logger = logging.getLogger(__name__)

MARKET_REVIEW_HISTORY_CODE = "MARKET"
MARKET_REVIEW_REPORT_TYPE = "market_review"


def _get_market_review_text(language: str) -> dict[str, str]:
    normalized = normalize_report_language(language)
    if normalized == "en":
        return {
            "root_title": "# Market Review",
            "push_title": "Market Review",
            "cn_title": "# A-share Market Recap",
            "us_title": "# US Market Recap",
            "hk_title": "# HK Market Recap",
            "separator": "> Next market recap follows",
        }
    return {
        "root_title": "# 시장 리뷰",
        "push_title": "시장 리뷰",
        "cn_title": "# A주 시장 리뷰",
        "us_title": "# 미국 시장 리뷰",
        "hk_title": "# 홍콩 시장 리뷰",
        "separator": "> 다음 시장 리뷰입니다.",
    }


def run_market_review(
    notifier: NotificationService,
    analyzer: Optional[GeminiAnalyzer] = None,
    search_service: Optional[SearchService] = None,
    send_notification: bool = True,
    merge_notification: bool = False,
    override_region: Optional[str] = None,
    query_id: Optional[str] = None,
) -> Optional[str]:
    """
    zhixingdapanfupananalysis

    Args:
        notifier: notificationfuwu
        analyzer: AIanalysisqi竊늟exuan竊?
        search_service: sousuofuwu竊늟exuan竊?
        send_notification: shifousendnotification
        merge_notification: shifouhebingtuisong竊늯iaoguobencituisong竊똹ou main cenghebinggegu+dapanhoutongyisend竊똈ssue #190竊?
        override_region: fugai config de market_review_region竊뉹ssue #373 jiaoyiriguolvhouyouxiaoziji竊?
        query_id: lishirecordguanlian ID竊쌐PI houtairenwuhuichuanru task_id竊똂LI/Bot weikongshizidongshengcheng

    Returns:
        fupanbaogaowenben
    """
    logger.info("kaishizhixingdapanfupananalysis...")
    config = get_config()
    review_text = _get_market_review_text(getattr(config, "report_language", "zh"))
    region = (
        override_region
        if override_region is not None
        else (getattr(config, 'market_review_region', 'cn') or 'cn')
    )
    _ALL_MARKETS = [('cn', 'cn_title', 'A주'), ('hk', 'hk_title', '홍콩'), ('us', 'us_title', '미국')]
    _VALID_SINGLES = {'cn', 'us', 'hk'}

    # Determine which markets to run.
    # region can be: 'cn', 'hk', 'us', 'both', or a comma-joined subset like 'cn,us'.
    if ',' in region:
        run_markets = [m.strip() for m in region.split(',') if m.strip() in _VALID_SINGLES]
    elif region == 'both':
        run_markets = list(_VALID_SINGLES)
    elif region in _VALID_SINGLES:
        run_markets = [region]
    else:
        run_markets = ['cn']

    try:
        if len(run_markets) > 1:
            # duomarketshunxuzhixing竊똦ebingbaogao
            parts = []
            for mkt, title_key, label in _ALL_MARKETS:
                if mkt not in run_markets:
                    continue
                logger.info("shengcheng %s dapanfupanbaogao...", label)
                mkt_analyzer = MarketAnalyzer(
                    search_service=search_service, analyzer=analyzer, region=mkt
                )
                mkt_report = mkt_analyzer.run_daily_review()
                if mkt_report:
                    parts.append(f"{review_text[title_key]}\n\n{mkt_report}")
            if parts:
                review_report = f"\n\n---\n\n{review_text['separator']}\n\n".join(parts)
            else:
                review_report = None
        else:
            market_analyzer = MarketAnalyzer(
                search_service=search_service,
                analyzer=analyzer,
                region=region,
            )
            review_report = market_analyzer.run_daily_review()
        
        if review_report:
            # savebaogaodaowenjian
            date_str = datetime.now().strftime('%Y%m%d')
            report_filename = f"market_review_{date_str}.md"
            filepath = notifier.save_report_to_file(
                f"{review_text['root_title']}\n\n{review_report}",
                report_filename
            )
            logger.info(f"dapanfupanbaogaoyisave: {filepath}")

            _persist_market_review_history(
                review_report=review_report,
                markdown_report=f"{review_text['root_title']}\n\n{review_report}",
                region=region,
                config=config,
                query_id=query_id,
            )
            
            # tuisongnotification竊늜ebingmoshixiatiaoguo竊똹ou main cengtongyisend竊?
            if merge_notification and send_notification:
                logger.info("hebingtuisongmoshi竊쉞iaoguodapanfupandandutuisong竊똨iangzaigegu+dapanfupanhoutongyisend")
            elif send_notification and notifier.is_available():
                # addbiaoti
                report_content = f"{review_text['push_title']}\n\n{review_report}"

                success = notifier.send(report_content, email_send_to_all=True, route_type="report")
                if success:
                    logger.info("dapanfupantuisongchenggong")
                else:
                    logger.warning("dapanfupantuisongshibai")
            elif not send_notification:
                logger.info("yitiaoguotuisongnotification (--no-notify)")
            
            return review_report
        
    except Exception as e:
        logger.error(f"dapanfupananalysisshibai: {e}")
    
    return None


def _persist_market_review_history(
    *,
    review_report: str,
    markdown_report: str,
    region: str,
    config: object,
    query_id: Optional[str] = None,
) -> int:
    """Persist market review output into the existing analysis history table."""
    try:
        from src.storage import DatabaseManager

        report_language = normalize_report_language(getattr(config, "report_language", "zh"))
        summary = _summarize_market_review(review_report, report_language)
        if report_language == "en":
            stock_name = "Market Review"
            operation_advice = "View review"
            trend_prediction = "Market review"
        else:
            stock_name = "시장 리뷰"
            operation_advice = "리뷰 확인"
            trend_prediction = "시장 리뷰"

        result = AnalysisResult(
            code=MARKET_REVIEW_HISTORY_CODE,
            name=stock_name,
            sentiment_score=50,
            trend_prediction=trend_prediction,
            operation_advice=operation_advice,
            analysis_summary=summary,
            report_language=report_language,
            news_summary=review_report,
            raw_response=markdown_report,
            data_sources="market_review",
        )

        history_query_id = query_id or f"market_review_{uuid.uuid4().hex}"
        context_snapshot = {
            "report_kind": MARKET_REVIEW_REPORT_TYPE,
            "market_review_region": region,
            "report_language": report_language,
        }

        saved = DatabaseManager.get_instance().save_analysis_history(
            result=result,
            query_id=history_query_id,
            report_type=MARKET_REVIEW_REPORT_TYPE,
            news_content=review_report,
            context_snapshot=context_snapshot,
            save_snapshot=True,
        )
        if saved:
            logger.info("dapanfupanlishirecordyisave: query_id=%s", history_query_id)
        else:
            logger.warning("dapanfupanlishirecordsaveshibai: query_id=%s", history_query_id)
        return saved
    except Exception as exc:
        logger.warning("dapanfupanlishirecordsaveyichang竊똟aogaowenjianyutuisongliuchengjixu: %s", exc, exc_info=True)
        return 0


def _summarize_market_review(review_report: str, report_language: str) -> str:
    for line in (review_report or "").splitlines():
        text = line.strip().lstrip("#").strip()
        if text and not text.startswith("---") and not text.startswith(">"):
            return text[:200]
    return "Market review report generated." if report_language == "en" else "시장 리뷰 보고서가 생성되었습니다."

