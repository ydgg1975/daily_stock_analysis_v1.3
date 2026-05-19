# -*- coding: utf-8 -*-
"""
dapanfupanmarketquyuconfig

dingyigemarketquyudezhishu?걒inwensousuoci?갥rompt tishidengyuanshuju竊?
gong MarketAnalyzer an region qiehuan A gu/meigufupanxingwei??
"""

from dataclasses import dataclass
from typing import List


@dataclass
class MarketProfile:
    """dapanfupanmarketquyuconfig"""

    region: str  # "cn" | "us"
    # yongyupanduanzhengtizoushidezhishudaima竊똠n yongshangzheng 000001竊똵s yongbiaopu SPX
    mood_index_code: str
    # xinwensousuoguanjianci
    news_queries: List[str]
    # zhishudianping Prompt tishiyu
    prompt_index_hint: str
    # marketgaikuangshifoubaohanzhangdiejiashu?걕hangtingdieting竊뉯 guyou竊똫eiguwu竊?
    has_market_stats: bool
    # marketgaikuangshifoubaohanbankuaizhangdie竊뉯 guyou竊똫eigunone竊?
    has_sector_rankings: bool


CN_PROFILE = MarketProfile(
    region="cn",
    mood_index_code="000001",
    news_queries=[
        "Agu dapan fupan",
        "gushi quote analysis",
        "Agu market redian bankuai",
    ],
    prompt_index_hint="analysisshangzheng?걌henzheng?갷huangyebandenggezhishuzoushitedian",
    has_market_stats=True,
    has_sector_rankings=True,
)

US_PROFILE = MarketProfile(
    region="us",
    mood_index_code="SPX",
    news_queries=[
        "meigu dapan",
        "US stock market",
        "S&P 500 NASDAQ",
    ],
    prompt_index_hint="analysisbiaopu500?걆asidake?갺aozhidenggezhishuzoushitedian",
    has_market_stats=False,
    has_sector_rankings=False,
)

HK_PROFILE = MarketProfile(
    region="hk",
    mood_index_code="HSI",
    news_queries=[
        "ganggu dapan fupan",
        "Hong Kong stock market",
        "hengshengzhishu quote",
    ],
    prompt_index_hint="analysishengshengzhishu?갿engshengkejizhishu?갾uoqizhishudenggezhishuzoushitedian",
    has_market_stats=False,
    has_sector_rankings=False,
)


def get_profile(region: str) -> MarketProfile:
    """genju region fanhuiduiyingde MarketProfile"""
    if region == "us":
        return US_PROFILE
    if region == "hk":
        return HK_PROFILE
    return CN_PROFILE

