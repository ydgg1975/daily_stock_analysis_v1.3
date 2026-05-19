# -*- coding: utf-8 -*-
"""
===================================
Aguwatchlistguzhinenganalysisxitong - analysisfuwuceng
===================================

zhize竊?
1. fengzhuanghexinanalysisluoji竊똺hichiduodiaoyongfang竊뉱LI?갮ebUI?갃ot竊?
2. tigongqingxideAPIjiekou竊똟uyilaiyuminglingxingcanshu
3. zhichiyilaizhuru竊똟ianyutesthekuozhan
4. tongyiguanlianalysisliuchengheconfig
"""

import uuid
from typing import List, Optional

from src.analyzer import AnalysisResult
from src.core.market_review import run_market_review
from src.core.pipeline import StockAnalysisPipeline
from src.config import Config, get_config
from src.enums import ReportType
from src.notification import NotificationService


def analyze_stock(
    stock_code: str,
    config: Config = None,
    full_report: bool = False,
    notifier: Optional[NotificationService] = None,
) -> Optional[AnalysisResult]:
    """
    analysisdanzhistock

    Args:
        stock_code: stockdaima
        config: configduixiang竊늟exuan竊똫orenshiyongdanli竊?
        full_report: shifoushengchengwanzhengbaogao
        notifier: notificationfuwu竊늟exuan竊?

    Returns:
        analysisjieguoduixiang
    """
    if config is None:
        config = get_config()

    # chuangjiananalysisliushuixian
    pipeline = StockAnalysisPipeline(
        config=config,
        query_id=uuid.uuid4().hex,
        query_source="cli"
    )

    # shiyongnotificationfuwu竊늭uguotigong竊?
    if notifier:
        pipeline.notifier = notifier

    # genjufull_reportcanshushezhibaogaoleixing
    report_type = ReportType.FULL if full_report else ReportType.SIMPLE

    # yunxingdanzhistockanalysis
    result = pipeline.process_single_stock(
        code=stock_code,
        skip_analysis=False,
        single_stock_notify=notifier is not None,
        report_type=report_type,
    )

    return result


def analyze_stocks(
    stock_codes: List[str],
    config: Config = None,
    full_report: bool = False,
    notifier: Optional[NotificationService] = None,
) -> List[AnalysisResult]:
    """
    analysisduozhistock

    Args:
        stock_codes: stockdaimaliebiao
        config: configduixiang竊늟exuan竊똫orenshiyongdanli竊?
        full_report: shifoushengchengwanzhengbaogao
        notifier: notificationfuwu竊늟exuan竊?

    Returns:
        analysisjieguoliebiao
    """
    if config is None:
        config = get_config()

    results = []
    for stock_code in stock_codes:
        result = analyze_stock(stock_code, config, full_report, notifier)
        if result:
            results.append(result)

    return results


def perform_market_review(
    config: Config = None,
    notifier: Optional[NotificationService] = None,
) -> Optional[str]:
    """
    zhixingdapanfupan

    Args:
        config: configduixiang竊늟exuan竊똫orenshiyongdanli竊?
        notifier: notificationfuwu竊늟exuan竊?

    Returns:
        fupanbaogaoneirong
    """
    if config is None:
        config = get_config()

    # chuangjiananalysisliushuixianyihuoquanalyzerhesearch_service
    pipeline = StockAnalysisPipeline(
        config=config,
        query_id=uuid.uuid4().hex,
        query_source="cli",
    )

    # shiyongtigongdenotificationfuwuhuochuangjianxinde
    review_notifier = notifier or pipeline.notifier

    # diaoyongdapanfupanhanshu
    return run_market_review(
        notifier=review_notifier,
        analyzer=pipeline.analyzer,
        search_service=pipeline.search_service,
    )


