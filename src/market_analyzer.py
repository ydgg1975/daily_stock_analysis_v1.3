# -*- coding: utf-8 -*-

"""

===================================

dapanfupananalysismokuai

===================================



zhize竊?
1. huoqudapanzhishushuju竊늮hangzheng?걌henzheng?갷huangyeban竊?
2. sousuomarketxinwenxingchengfupanqingbao

3. shiyongdamodelshengchengmeiridapanfupanbaogao

"""



import logging

import time

from dataclasses import dataclass, field

from datetime import datetime

from typing import Optional, Dict, Any, List



import pandas as pd



from src.config import get_config

from src.report_language import normalize_report_language

from src.search_service import SearchService

from src.core.market_profile import get_profile, MarketProfile

from src.core.market_strategy import get_market_strategy_blueprint

from data_provider.base import DataFetcherManager



logger = logging.getLogger(__name__)





_ENGLISH_SECTION_PATTERNS = {

    "market_summary": r"###\s*(?:1\.\s*)?Market Summary",

    "index_commentary": r"###\s*(?:2\.\s*)?(?:Index Commentary|Major Indices)",

    "sector_highlights": r"###\s*(?:4\.\s*)?(?:Sector Highlights|Sector/Theme Highlights)",

}



_CHINESE_SECTION_PATTERNS = {

    "market_summary": r"###\s*yi???:panmianzonglan|marketzongjie)",

    "index_commentary": r"###\s*er???:zhishujiegou|zhishudianping|zhuyaozhishu)",

    "sector_highlights": r"###\s*san???:bankuaizhuxian|redianjiedu|bankuaibiaoxian)",

    "funds_sentiment": r"###\s*si???:zijinyuqingxu|zijindongxiang)",

    "news_catalysts": r"###\s*wu???:xiaoxicuihua|houshizhanwang)",

}





@dataclass

class MarketIndex:

    """dapanzhishushuju"""

    code: str                    # zhishudaima

    name: str                    # zhishumingcheng

    current: float = 0.0         # dangqiandianwei

    change: float = 0.0          # zhangdiedianshu

    change_pct: float = 0.0      # zhangdiefu(%)

    open: float = 0.0            # kaipandianwei

    high: float = 0.0            # zuigaodianwei

    low: float = 0.0             # zuididianwei

    prev_close: float = 0.0      # zuoshoudianwei

    volume: float = 0.0          # chengjiaoliang竊늮hou竊?
    amount: float = 0.0          # chengjiaoe竊늶uan竊?
    amplitude: float = 0.0       # zhenfu(%)

    

    def to_dict(self) -> Dict[str, Any]:

        return {

            'code': self.code,

            'name': self.name,

            'current': self.current,

            'change': self.change,

            'change_pct': self.change_pct,

            'open': self.open,

            'high': self.high,

            'low': self.low,

            'volume': self.volume,

            'amount': self.amount,

            'amplitude': self.amplitude,

        }





@dataclass

class MarketOverview:

    """marketgailanshuju"""

    date: str                           # riqi

    indices: List[MarketIndex] = field(default_factory=list)  # zhuyaozhishu

    up_count: int = 0                   # shangzhangjiashu

    down_count: int = 0                 # xiadiejiashu

    flat_count: int = 0                 # pingpanjiashu

    limit_up_count: int = 0             # zhangtingjiashu

    limit_down_count: int = 0           # dietingjiashu

    total_amount: float = 0.0           # liangshichengjiaoe竊늶iyuan竊?
    # north_flow: float = 0.0           # beixiangzijinjingliuru竊늶iyuan竊? yifeiqi竊똨iekoubukeyong

    

    # bankuaizhangfubang

    top_sectors: List[Dict] = field(default_factory=list)     # zhangfuqian5bankuai

    bottom_sectors: List[Dict] = field(default_factory=list)  # diefuqian5bankuai





class MarketAnalyzer:

    """

    dapanfupananalysisqi

    

    gongneng竊?
    1. huoqudapanzhishushishixingqing

    2. huoqumarketzhangdietongji

    3. huoqubankuaizhangdiebang

    4. sousuomarketxinwen

    5. shengchengdapanfupanbaogao

    """

    

    def __init__(

        self,

        search_service: Optional[SearchService] = None,

        analyzer=None,

        region: str = "cn",

    ):

        """

        chushihuadapananalysisqi



        Args:

            search_service: sousuofuwushili

            analyzer: AIanalysisqishili竊늶ongyudiaoyongLLM竊?
            region: marketquyu cn=Agu us=meigu

        """

        self.config = get_config()

        self.search_service = search_service

        self.analyzer = analyzer

        self.data_manager = DataFetcherManager()

        self.region = region if region in ("cn", "us", "hk") else "cn"

        self.profile: MarketProfile = get_profile(self.region)

        self.strategy = get_market_strategy_blueprint(self.region)



    def _get_review_language(self) -> str:

        configured = normalize_report_language(

            getattr(getattr(self, "config", None), "report_language", "zh")

        )

        if self.region == "us":

            return "en"

        return configured



    def _get_template_review_language(self) -> str:

        return normalize_report_language(

            getattr(getattr(self, "config", None), "report_language", "zh")

        )



    def _get_market_scope_name(self, review_language: str | None = None) -> str:

        review_language = review_language or self._get_review_language()

        if self.region == "us":

            return "US market"

        if self.region == "hk":

            return "Hong Kong market" if review_language == "en" else "홍콩 시장"

        if review_language == "en":

            return "A-share market"

        return "A주 시장"



    def _get_turnover_unit_label(self) -> str:

        """Return the turnover unit label for the current market/language."""

        if self.region == "us":

            return "USD bn" if self._get_review_language() == "en" else "십억 달러"

        if self.region == "hk":

            return "HKD bn" if self._get_review_language() == "en" else "십억 홍콩달러"

        return "CNY 100m" if self._get_review_language() == "en" else "억"



    def _format_turnover_value(self, amount_raw: float) -> str:

        """Format raw turnover according to market-specific units."""

        if amount_raw == 0.0:

            return "N/A"

        if self.region in ("us", "hk"):

            return f"{amount_raw / 1e9:.2f}"

        if amount_raw > 1e6:

            return f"{amount_raw / 1e8:.0f}"

        return f"{amount_raw:.0f}"



    def _get_index_change_arrow(self, change_pct: float) -> str:

        if change_pct == 0:

            return "→"
        color_scheme = getattr(getattr(self, "config", None), "market_review_color_scheme", "green_up")

        if color_scheme == "red_up":

            return "↑" if change_pct > 0 else "↓"
        return "↑" if change_pct > 0 else "↓"



    def _get_review_title(self, date: str) -> str:

        if self._get_review_language() == "en":

            market_names = {"us": "US Market Recap", "hk": "HK Market Recap"}

            market_name = market_names.get(self.region, "A-share Market Recap")

            return f"## {date} {market_name}"

        return f"## {date} 시장 리뷰"



    def _get_index_hint(self) -> str:

        if self._get_review_language() == "en":

            if self.region == "us":

                return "Analyze the key moves in the S&P 500, Nasdaq, Dow, and other major indices."

            if self.region == "hk":

                return "Analyze the key moves in the HSI, Hang Seng Tech, HSCEI, and other major indices."

            return "Analyze the price action in the SSE, SZSE, ChiNext, and other major indices."

        return self.profile.prompt_index_hint



    def _get_strategy_prompt_block(self) -> str:

        if self.region == "hk" and self._get_review_language() == "en":

            return """## Strategy Blueprint: Hong Kong Market Regime Strategy

Focus on HSI trend, southbound flow dynamics, and sector rotation to define next-session risk posture.



### Strategy Principles

- Read market regime from HSI, HSTECH, and HSCEI alignment first.

- Track southbound capital flow as a key sentiment driver.

- Translate recap into actionable risk-on/risk-off stance with clear invalidation points.



### Analysis Dimensions

- Trend Regime: Classify the market as momentum, range, or risk-off.

  - Are HSI/HSTECH/HSCEI directionally aligned

  - Did volume confirm the move

  - Are key index levels reclaimed or lost

- Capital Flows: Map southbound flow and macro narrative into equity risk appetite.

  - Southbound net flow direction and magnitude

  - USD/HKD and China policy implications

  - Breadth and leadership concentration

- Sector Themes: Identify persistent leaders and vulnerable laggards.

  - Tech/internet platform trend persistence

  - Financials/property sensitivity to policy shifts

  - Defensive vs growth factor rotation



### Action Framework

- Risk-on: broad index breakout with expanding southbound participation.

- Neutral: mixed index signals; focus on selective relative strength.

- Risk-off: failed breakouts and rising volatility; prioritize capital preservation."""

        if not (self.region == "cn" and self._get_review_language() == "en"):

            return self.strategy.to_prompt_block()

        return """## Strategy Blueprint: A-share Three-Phase Recap Strategy

Focus on index trend, liquidity, and sector rotation to shape the next-session trading plan.



### Strategy Principles

- Read index direction first, then confirm liquidity structure, and finally test sector persistence.

- Every conclusion must map to position sizing, trading pace, and risk-control actions.

- Base judgments on today's data and the latest 3-day news flow without inventing unverified information.



### Analysis Dimensions

- Trend Structure: Determine whether the market is in an uptrend, range, or defensive phase.

  - Are the SSE, SZSE, and ChiNext moving in the same direction

  - Is the market advancing on expanding volume or slipping on contracting volume

  - Have key support or resistance levels been reclaimed or broken

- Liquidity & Sentiment: Identify near-term risk appetite and market temperature.

  - Advance/decline breadth and limit-up/limit-down structure

  - Whether turnover is expanding or fading

  - Whether high-beta leaders are showing divergence

- Leading Themes: Distill tradable leadership and areas to avoid.

  - Whether leading sectors have clear event catalysts

  - Whether sector leaders are pulling the group higher

  - Whether weakness is broadening across lagging sectors



### Action Framework

- Offensive: indices rise in sync, turnover expands, and core themes strengthen.

- Balanced: index divergence or low-volume consolidation; keep sizing controlled and wait for confirmation.

- Defensive: indices weaken and laggards broaden; prioritize risk control and de-risking."""



    def _get_strategy_markdown_block(self, review_language: str | None = None) -> str:

        review_language = review_language or self._get_review_language()

        if self.region == "hk" and review_language == "en":

            return """### 6. Strategy Framework

- **Trend Regime**: Classify the market as momentum, range, or risk-off based on HSI/HSTECH/HSCEI alignment.

- **Capital Flows**: Track southbound flow direction and macro narrative for risk appetite signals.

- **Sector Themes**: Focus on tech/internet platform persistence and financials/property policy sensitivity.

"""

        if not (self.region == "cn" and review_language == "en"):

            return self.strategy.to_markdown_block()

        return """### 6. Strategy Framework

- **Trend Structure**: Determine whether the market is in an uptrend, range, or defensive phase.

- **Liquidity & Sentiment**: Track breadth, turnover expansion, and whether leaders are diverging.

- **Leading Themes**: Focus on sectors with catalysts and sustained leadership while avoiding broadening weakness.

"""



    def _get_market_mood_text(self, mood_key: str, review_language: str | None = None) -> str:

        review_language = review_language or self._get_review_language()

        if review_language == "en":

            mapping = {

                "strong_up": "strong gains",

                "mild_up": "moderate gains",

                "mild_down": "mild losses",

                "strong_down": "clear weakness",

                "range": "range-bound trading",

            }

        else:

            mapping = {

                "strong_up": "강한 상승",

                "mild_up": "소폭 상승",

                "mild_down": "소폭 하락",

                "strong_down": "뚜렷한 하락",

                "range": "박스권 등락",

            }

        return mapping[mood_key]



    def get_market_overview(self) -> MarketOverview:

        """

        huoqumarketgailanshuju

        

        Returns:

            MarketOverview: marketgailanshujuduixiang

        """

        today = datetime.now().strftime('%Y-%m-%d')

        overview = MarketOverview(date=today)

        

        # 1. huoquzhuyaozhishuquote竊늏n region qiehuan A gu/meigu竊?
        overview.indices = self._get_main_indices()



        # 2. huoquzhangdietongji竊뉯 guyou竊똫eiguwudengxiaoshuju竊?
        if self.profile.has_market_stats:

            self._get_market_statistics(overview)



        # 3. huoqubankuaizhangdiebang竊뉯 guyou竊똫eigunone竊?
        if self.profile.has_sector_rankings:

            self._get_sector_rankings(overview)

        

        # 4. huoqubeixiangzijin竊늟exuan竊?
        # self._get_north_flow(overview)

        

        return overview



    

    def _get_main_indices(self) -> List[MarketIndex]:

        """huoquzhuyaozhishushishixingqing"""

        indices = []



        try:

            logger.info("[dapan] huoquzhuyaozhishushishixingqing...")



            # shiyong DataFetcherManager huoquzhishuquote竊늏n region qiehuan竊?
            data_list = self.data_manager.get_main_indices(region=self.region)



            if data_list:

                for item in data_list:

                    index = MarketIndex(

                        code=item['code'],

                        name=item['name'],

                        current=item['current'],

                        change=item['change'],

                        change_pct=item['change_pct'],

                        open=item['open'],

                        high=item['high'],

                        low=item['low'],

                        prev_close=item['prev_close'],

                        volume=item['volume'],

                        amount=item['amount'],

                        amplitude=item['amplitude']

                    )

                    indices.append(index)



            if not indices:

                logger.warning("[dapan] suoyouquoteshujuyuanshibai竊똨iangyilaixinwensousuojinxinganalysis")

            else:

                logger.info(f"[dapan] huoqudao {len(indices)} gezhishuquote")



        except Exception as e:

            logger.error(f"[dapan] huoquzhishuquoteshibai: {e}")



        return indices



    def _get_market_statistics(self, overview: MarketOverview):

        """huoqumarketzhangdietongji"""

        try:

            logger.info("[dapan] huoqumarketzhangdietongji...")



            stats = self.data_manager.get_market_stats()



            if stats:

                overview.up_count = stats.get('up_count', 0)

                overview.down_count = stats.get('down_count', 0)

                overview.flat_count = stats.get('flat_count', 0)

                overview.limit_up_count = stats.get('limit_up_count', 0)

                overview.limit_down_count = stats.get('limit_down_count', 0)

                overview.total_amount = stats.get('total_amount', 0.0)



                logger.info(f"[dapan] zhang:{overview.up_count} die:{overview.down_count} ping:{overview.flat_count} "

                          f"zhangting:{overview.limit_up_count} dieting:{overview.limit_down_count} "

                          f"chengjiaoe:{overview.total_amount:.0f}yi")



        except Exception as e:

            logger.error(f"[dapan] huoquzhangdietongjishibai: {e}")



    def _get_sector_rankings(self, overview: MarketOverview):

        """huoqubankuaizhangdiebang"""

        try:

            logger.info("[dapan] huoqubankuaizhangdiebang...")



            top_sectors, bottom_sectors = self.data_manager.get_sector_rankings(5)



            if top_sectors or bottom_sectors:

                overview.top_sectors = top_sectors

                overview.bottom_sectors = bottom_sectors



                logger.info(f"[dapan] lingzhangbankuai: {[s['name'] for s in overview.top_sectors]}")

                logger.info(f"[dapan] lingdiebankuai: {[s['name'] for s in overview.bottom_sectors]}")



        except Exception as e:

            logger.error(f"[dapan] huoqubankuaizhangdiebangshibai: {e}")

    

    # def _get_north_flow(self, overview: MarketOverview):

    #     """huoqubeixiangzijinliuru"""

    #     try:

    #         logger.info("[dapan] huoqubeixiangzijin...")

    #         

    #         # huoqubeixiangzijinshuju

    #         df = ak.stock_hsgt_north_net_flow_in_em(symbol="beishang")

    #         

    #         if df is not None and not df.empty:

    #             # quzuixinyitiaoshuju

    #             latest = df.iloc[-1]

    #             if 'dangrijingliuru' in df.columns:

    #                 overview.north_flow = float(latest['dangrijingliuru']) / 1e8  # zhuanweiyiyuan

    #             elif 'jingliuru' in df.columns:

    #                 overview.north_flow = float(latest['jingliuru']) / 1e8

    #                 

    #             logger.info(f"[dapan] beixiangzijinjingliuru: {overview.north_flow:.2f}yi")

    #             

    #     except Exception as e:

    #         logger.warning(f"[dapan] huoqubeixiangzijinshibai: {e}")

    

    def search_market_news(self) -> List[Dict]:

        """

        sousuomarketxinwen

        

        Returns:

            xinwenliebiao

        """

        if not self.search_service:

            logger.warning("[dapan] sousuofuwuweiconfig竊똳iaoguoxinwensousuo")

            return []

        

        all_news = []



        # an region shiyongbutongdexinwensousuoci

        search_queries = self.profile.news_queries

        

        try:

            logger.info("[dapan] kaishisousuomarketxinwen...")

            

            # genju region shezhisousuoshangxiawenmingcheng竊똟imianmeigusousuobeijieduwei A guyujing

            market_names = {"cn": "dapan", "us": "US market", "hk": "HK market"}

            market_name = market_names.get(self.region, "dapan")

            for query in search_queries:

                response = self.search_service.search_stock_news(

                    stock_code="market",

                    stock_name=market_name,

                    max_results=3,

                    focus_keywords=query.split()

                )

                if response and response.results:

                    all_news.extend(response.results)

                    logger.info(f"[dapan] sousuo '{query}' huoqu {len(response.results)} tiaojieguo")

            

            logger.info(f"[dapan] gonghuoqu {len(all_news)} tiaomarketxinwen")

            

        except Exception as e:

            logger.error(f"[dapan] sousuomarketxinwenshibai: {e}")

        

        return all_news

    

    def generate_market_review(self, overview: MarketOverview, news: List) -> str:

        """

        shiyongdamodelshengchengdapanfupanbaogao

        

        Args:

            overview: marketgailanshuju

            news: marketxinwenliebiao (SearchResult duixiangliebiao)

            

        Returns:

            dapanfupanbaogaowenben

        """

        if not self.analyzer or not self.analyzer.is_available():

            logger.warning("[dapan] AIanalysisqiweiconfighuobukeyong竊똲hiyongmubanshengchengbaogao")

            return self._generate_template_review(overview, news)

        

        # goujian Prompt

        prompt = self._build_review_prompt(overview, news)

        

        logger.info("[dapan] diaoyongdamodelshengchengfupanbaogao...")

        # Use the public generate_text() entry point ??never access private analyzer attributes.

        review = self.analyzer.generate_text(prompt, max_tokens=8192, temperature=0.7)



        if review:

            logger.info("[dapan] fupanbaogaoshengchengchenggong竊똠hangdu: %d zifu", len(review))

            # Inject structured data tables into LLM prose sections

            return self._inject_data_into_review(review, overview, news)

        else:

            logger.warning("[dapan] damodelfanhuiweikong竊똲hiyongmubanbaogao")

            return self._generate_template_review(overview, news)

    

    def _inject_data_into_review(

        self,

        review: str,

        overview: MarketOverview,

        news: Optional[List] = None,

    ) -> str:

        """Inject structured data tables into the corresponding LLM prose sections."""

        # Build data blocks

        stats_block = self._build_stats_block(overview)

        indices_block = self._build_indices_block(overview)

        sector_block = self._build_sector_block(overview)

        news_block = self._build_news_block(news or [])

        patterns = (

            _ENGLISH_SECTION_PATTERNS

            if self._get_review_language() == "en"

            else _CHINESE_SECTION_PATTERNS

        )



        if stats_block:

            review = self._insert_after_section(

                review,

                patterns["market_summary"],

                stats_block,

            )



        if indices_block:

            review = self._insert_after_section(

                review,

                patterns["index_commentary"],

                indices_block,

            )



        if sector_block:

            review = self._insert_after_section(

                review,

                patterns["sector_highlights"],

                sector_block,

            )



        if news_block and "news_catalysts" in patterns:

            review = self._insert_after_section(

                review,

                patterns["news_catalysts"],

                news_block,

            )



        return review



    @staticmethod

    def _insert_after_section(text: str, heading_pattern: str, block: str) -> str:

        """Insert a data block at the end of a markdown section (before the next ### heading)."""

        import re

        # Find the heading

        match = re.search(heading_pattern, text)

        if not match:

            return text

        start = match.end()

        # Find the next ### heading after this one

        next_heading = re.search(r'\n###\s', text[start:])

        if next_heading:

            insert_pos = start + next_heading.start()

        else:

            # No next heading ??append at end

            insert_pos = len(text)

        # Insert the block before the next heading, with spacing

        return text[:insert_pos].rstrip() + '\n\n' + block + '\n\n' + text[insert_pos:].lstrip('\n')



    def _build_stats_block(self, overview: MarketOverview) -> str:

        """Build market statistics block."""

        has_stats = overview.up_count or overview.down_count or overview.total_amount

        if not has_stats:

            return ""

        if self._get_review_language() == "en":

            light = self.build_market_light_snapshot(overview)

            return "\n".join(

                [

                    f"> **Market Light**: {light['status']} ({light['label']}) | "

                    f"**{light['score']}/100** {self._build_temperature_bar(light['score'])}",

                    f"> **Reasons**: {'; '.join(light['reasons'])}",

                    f"> **Guidance**: {light['guidance']}",

                    "",

                    f"> ?뱢 Advancers **{overview.up_count}** / Decliners **{overview.down_count}** / "

                    f"Flat **{overview.flat_count}** | "

                    f"Limit-up **{overview.limit_up_count}** / Limit-down **{overview.limit_down_count}** | "

                    f"Turnover **{overview.total_amount:.0f}** ({self._get_turnover_unit_label()})",

                ]

            )

        light = self.build_market_light_snapshot(overview)

        score, label = light["score"], light["temperature_label"]

        participation = overview.up_count + overview.down_count

        up_ratio = overview.up_count / participation if participation else 0.0

        limit_spread = overview.limit_up_count - overview.limit_down_count

        lines = [

            f"> **대판 신호등**: {light['status']} {light['label']} | **{score}/100** {self._build_temperature_bar(score)}",
            f"> **핵심 이유**: {' / '.join(light['reasons'])}",
            f"> **운용 제안**: {light['guidance']}",
            "",

            f"> **시장 온도**: {label} **{score}/100** {self._build_temperature_bar(score)}",
            "",

            "| zhibiao | shuzhi | guancha |",

            "|------|------|------|",

            f"| shangzhang/xiadie/pingpan | {overview.up_count} / {overview.down_count} / {overview.flat_count} | shangzhangzhanbi(buhanpingpan) {up_ratio:.1%} |",

            f"| zhangting/dieting | {overview.limit_up_count} / {overview.limit_down_count} | zhangdietingcha {limit_spread:+d} |",

            f"| liangshichengjiaoe | {overview.total_amount:.0f} yi | {self._describe_turnover(overview.total_amount)} |",

        ]

        return "\n".join(lines)



    def build_market_light_snapshot(self, overview: MarketOverview) -> Dict[str, Any]:

        """Build a deterministic market-light snapshot from structured breadth data."""

        score, temperature_label = self._build_market_temperature(overview)

        if score >= 60:

            status = "green"

        elif score >= 40:

            status = "yellow"

        else:

            status = "red"



        if self._get_review_language() == "en":

            label_map = {

                "green": "constructive",

                "yellow": "watch",

                "red": "defensive",

            }

            guidance_map = {

                "green": "Risk appetite is acceptable; focus on leading themes and position discipline.",

                "yellow": "Signals are mixed; keep position sizing moderate and wait for confirmation.",

                "red": "Risk is elevated; prioritize drawdown control and avoid chasing weak rebounds.",

            }

            reasons = self._build_market_light_reasons_en(overview, score)

        else:

            label_map = {

                "green": "kejingong",

                "yellow": "xuguancha",

                "red": "pianfangshou",

            }

            guidance_map = {

                "green": "위험 선호가 양호합니다. 주도 흐름 지속과 포지션 규율을 확인하세요.",
                "yellow": "신호가 엇갈립니다. 포지션을 관리하고 거래량/가격 확인을 기다리세요.",
                "red": "리스크가 높습니다. 손실 통제를 우선하고 약한 반등 추격은 피하세요.",
            }

            reasons = self._build_market_light_reasons_zh(overview, score)



        return {

            "status": status,

            "label": label_map[status],

            "score": score,

            "temperature_label": temperature_label,

            "reasons": reasons,

            "guidance": guidance_map[status],

        }



    def _build_market_light_reasons_zh(self, overview: MarketOverview, score: int) -> List[str]:

        participation = overview.up_count + overview.down_count

        up_ratio = overview.up_count / participation if participation else None

        reasons: List[str] = [f"panmianwendu {score}/100"]

        if up_ratio is not None:

            if up_ratio >= 0.6:

                reasons.append(f"shangzhangjiashuzhanbi {up_ratio:.0%}竊똺huanqianxiaoyingkuosan")

            elif up_ratio <= 0.4:

                reasons.append(f"shangzhangjiashuzhanbi {up_ratio:.0%}竊똩uiqianxiaoyingjiaoqiang")

            else:

                reasons.append(f"shangzhangjiashuzhanbi {up_ratio:.0%}竊똲hichangfenhua")

        if overview.indices:

            avg_change = sum(idx.change_pct for idx in overview.indices) / len(overview.indices)

            reasons.append(f"zhuyaozhishupingjunzhangdiefu {avg_change:+.2f}%")

        if overview.limit_up_count or overview.limit_down_count:

            reasons.append(f"zhangdietingcha {overview.limit_up_count - overview.limit_down_count:+d}")

        return reasons[:4]



    def _build_market_light_reasons_en(self, overview: MarketOverview, score: int) -> List[str]:

        participation = overview.up_count + overview.down_count

        up_ratio = overview.up_count / participation if participation else None

        reasons: List[str] = [f"market temperature {score}/100"]

        if up_ratio is not None:

            if up_ratio >= 0.6:

                reasons.append(f"advancers ratio {up_ratio:.0%}, breadth is expanding")

            elif up_ratio <= 0.4:

                reasons.append(f"advancers ratio {up_ratio:.0%}, downside pressure dominates")

            else:

                reasons.append(f"advancers ratio {up_ratio:.0%}, breadth is mixed")

        if overview.indices:

            avg_change = sum(idx.change_pct for idx in overview.indices) / len(overview.indices)

            reasons.append(f"average major-index change {avg_change:+.2f}%")

        if overview.limit_up_count or overview.limit_down_count:

            reasons.append(f"limit-up/down spread {overview.limit_up_count - overview.limit_down_count:+d}")

        return reasons[:4]



    def _build_indices_block(self, overview: MarketOverview) -> str:

        """goujianzhishuquotebiaoge"""

        if not overview.indices:

            return ""

        if self._get_review_language() == "en":

            lines = [

                f"| Index | Last | Change % | Open | High | Low | Amplitude | Turnover ({self._get_turnover_unit_label()}) |",

                "|-------|------|----------|------|------|-----|-----------|-----------------|",

            ]

        else:

            lines = [

                "| 지수 | 현재가 | 등락률 | 시가 | 고가 | 저가 | 진폭 | 거래대금(억) |",

                "|------|------|--------|------|------|------|------|-----------|",

            ]

        for idx in overview.indices:

            arrow = self._get_index_change_arrow(idx.change_pct)

            amount_raw = idx.amount or 0.0

            amount_str = self._format_turnover_value(amount_raw)

            lines.append(

                f"| {idx.name} | {idx.current:.2f} | {arrow} {idx.change_pct:+.2f}% | "

                f"{self._format_optional_number(idx.open)} | {self._format_optional_number(idx.high)} | "

                f"{self._format_optional_number(idx.low)} | {self._format_optional_pct(idx.amplitude)} | {amount_str} |"

            )

        return "\n".join(lines)



    def _build_sector_block(self, overview: MarketOverview) -> str:

        """Build sector ranking block."""

        if not overview.top_sectors and not overview.bottom_sectors:

            return ""

        lines = []

        if overview.top_sectors:

            if self._get_review_language() == "en":

                lines.extend([

                    "#### Leading Sectors",

                    "| Rank | Sector | Change |",

                    "|------|--------|--------|",

                ])

            else:

                lines.extend([

                    "#### 상승 주도 섹터 Top 5",

                    "| 순위 | 섹터 | 등락률 |",

                    "|------|------|--------|",

                ])

            for rank, sector in enumerate(overview.top_sectors[:5], 1):

                lines.append(

                    f"| {rank} | {sector.get('name', '-')} | {self._format_signed_pct(sector.get('change_pct'))} |"

                )

        if overview.bottom_sectors:

            if lines:

                lines.append("")

            if self._get_review_language() == "en":

                lines.extend([

                    "#### Lagging Sectors",

                    "| Rank | Sector | Change |",

                    "|------|--------|--------|",

                ])

            else:

                lines.extend([

                    "#### 하락 섹터 Top 5",

                    "| 순위 | 섹터 | 등락률 |",

                    "|------|------|--------|",

                ])

            for rank, sector in enumerate(overview.bottom_sectors[:5], 1):

                lines.append(

                    f"| {rank} | {sector.get('name', '-')} | {self._format_signed_pct(sector.get('change_pct'))} |"

                )

        return "\n".join(lines)



    def _build_news_block(self, news: List) -> str:

        """Build a source-aware news catalyst table for the rendered report."""

        if not news:

            return ""

        if self._get_review_language() == "en":

            lines = [

                "#### News Catalysts",

                "| # | Headline | Snippet / Lead | Source |",

                "|---|----------|----------------|--------|",

            ]

        else:

            lines = [

                "#### 최근 3일 뉴스 촉매",

                "| 번호 | 시간/제목 | 요약/단서 | 출처 |",

                "|------|-----------|----------------|------|",

            ]



        for idx, item in enumerate(news[:5], 1):

            title = self._escape_table_cell(

                self._compact_news_text(self._get_news_field(item, "title"), limit=80) or "-"

            )

            snippet = self._escape_table_cell(

                self._compact_news_text(self._get_news_field(item, "snippet"), limit=180) or "-"

            )

            source = self._escape_table_cell(self._format_news_source_cell(item) or "-")

            lines.append(f"| {idx} | {title} | {snippet} | {source} |")

        return "\n".join(lines)



    @staticmethod

    def _get_news_field(item: Any, field: str) -> str:

        if hasattr(item, field):

            value = getattr(item, field, "") or ""

        elif isinstance(item, dict):

            value = item.get(field, "") or ""

        else:

            value = ""

        return str(value).strip()



    @classmethod

    def _format_news_source_cell(cls, item: Any) -> str:

        source = cls._compact_news_text(cls._get_news_field(item, "source"), limit=40)

        date_text = cls._compact_news_text(cls._get_news_field(item, "published_date"), limit=24)

        url = cls._compact_news_text(cls._get_news_field(item, "url"), limit=0)

        label_parts = [part for part in (source, date_text) if part]

        label = " / ".join(label_parts)

        if url:

            return f"[{label or 'URL'}]({url})"

        return label



    @staticmethod

    def _compact_news_text(value: str, *, limit: int) -> str:

        text = " ".join(str(value or "").split())

        if limit <= 0 or len(text) <= limit:

            return text

        return text[: max(0, limit - 3)].rstrip() + "..."



    @staticmethod

    def _format_optional_number(value: float) -> str:

        return "N/A" if value in (None, 0, 0.0) else f"{value:.2f}"



    @staticmethod

    def _format_optional_pct(value: float) -> str:

        return "N/A" if value in (None, 0, 0.0) else f"{value:.2f}%"



    @staticmethod

    def _format_signed_pct(value: Any) -> str:

        try:

            numeric_value = float(value)

        except (TypeError, ValueError):

            return "N/A"

        return f"{numeric_value:+.2f}%"



    @staticmethod

    def _escape_table_cell(value: str) -> str:

        return value.replace("|", "\\|")



    @staticmethod

    def _build_temperature_bar(score: int) -> str:

        filled = max(0, min(10, round(score / 10)))

        return "█" * filled + "░" * (10 - filled)


    @staticmethod

    def _describe_turnover(total_amount: float) -> str:

        if total_amount >= 15000:

            return "gaohuoyuedu"

        if total_amount >= 9000:

            return "zhongdenghuoyue"

        if total_amount > 0:

            return "suoliangguanwang"

        return "noneshuju"



    def _build_market_temperature(self, overview: MarketOverview) -> tuple[int, str]:

        participants = overview.up_count + overview.down_count

        breadth_score = 50

        if participants:

            breadth_score = int(overview.up_count / participants * 100)



        index_changes = [idx.change_pct for idx in overview.indices if idx.change_pct is not None]

        index_score = 50

        if index_changes:

            avg_change = sum(index_changes) / len(index_changes)

            index_score = int(max(0, min(100, 50 + avg_change * 12)))



        limit_total = overview.limit_up_count + overview.limit_down_count

        limit_score = 50

        if limit_total:

            limit_score = int(overview.limit_up_count / limit_total * 100)



        score = int(round(breadth_score * 0.45 + index_score * 0.35 + limit_score * 0.20))

        if self._get_review_language() == "en":

            if score >= 70:

                label = "risk-on"

            elif score >= 55:

                label = "constructive"

            elif score >= 40:

                label = "mixed"

            else:

                label = "defensive"

        else:

            if score >= 70:

                label = "qiangshi"

            elif score >= 55:

                label = "piannuan"

            elif score >= 40:

                label = "zhendang"

            else:

                label = "pianruo"

        return score, label



    def _build_review_prompt(self, overview: MarketOverview, news: List) -> str:

        """goujianfupanbaogao Prompt"""

        review_language = self._get_review_language()



        # zhishuquotexinxi竊늞ianjiegeshi竊똟uyongemoji竊?
        indices_text = ""

        for idx in overview.indices:

            direction = "+" if idx.change_pct > 0 else "-" if idx.change_pct < 0 else ""
            indices_text += f"- {idx.name}: {idx.current:.2f} ({direction}{abs(idx.change_pct):.2f}%)\n"

        

        # bankuaixinxi

        top_sectors_text = ", ".join([f"{s['name']}({s['change_pct']:+.2f}%)" for s in overview.top_sectors[:3]])

        bottom_sectors_text = ", ".join([f"{s['name']}({s['change_pct']:+.2f}%)" for s in overview.bottom_sectors[:3]])

        

        # xinwenxinxi - zhichi SearchResult duixianghuozidian

        news_text = ""

        for i, n in enumerate(news[:6], 1):

            # jianrong SearchResult duixianghezidian

            title = self._compact_news_text(self._get_news_field(n, "title"), limit=90)

            snippet = self._compact_news_text(self._get_news_field(n, "snippet"), limit=220)

            source = self._compact_news_text(self._get_news_field(n, "source"), limit=60)

            published_date = self._compact_news_text(self._get_news_field(n, "published_date"), limit=30)

            url = self._compact_news_text(self._get_news_field(n, "url"), limit=180)

            meta_parts = [part for part in (source, published_date) if part]

            meta = f" ({' / '.join(meta_parts)})" if meta_parts else ""

            url_line = f"\n   URL: {url}" if url else ""

            news_text += f"{i}. {title}{meta}\n   {snippet or '-'}{url_line}\n"

        

        # an region zuzhuangmarketgaikuangyubankuaiqukuai竊늤eiguwuzhangdiejiashu?갶ankuaishuju竊?
        stats_block = ""

        sector_block = ""

        if review_language == "en":

            if self.profile.has_market_stats:

                stats_block = f"""## Market Breadth

- Advancers: {overview.up_count} | Decliners: {overview.down_count} | Flat: {overview.flat_count}

- Limit-up: {overview.limit_up_count} | Limit-down: {overview.limit_down_count}

- Turnover: {overview.total_amount:.0f} ({self._get_turnover_unit_label()})"""

            else:

                stats_block = "## Market Breadth\n(No equivalent advance/decline statistics are available for this market.)"



            if self.profile.has_sector_rankings:

                sector_block = f"""## Sector Performance

Leading: {top_sectors_text if top_sectors_text else "N/A"}

Lagging: {bottom_sectors_text if bottom_sectors_text else "N/A"}"""

            else:

                sector_block = "## Sector Performance\n(Sector data not available for this market.)"

        else:

            if self.profile.has_market_stats:

                stats_block = f"""## marketgaikuang

- shangzhang: {overview.up_count} jia | xiadie: {overview.down_count} jia | pingpan: {overview.flat_count} jia

- zhangting: {overview.limit_up_count} jia | dieting: {overview.limit_down_count} jia

- liangshichengjiaoe: {overview.total_amount:.0f} yiyuan"""

            else:

                stats_block = "## 시장 개요\n해당 시장에는 상승/하락 종목 통계가 없습니다."


            if self.profile.has_sector_rankings:

                sector_block = f"""## bankuaibiaoxian

lingzhang: {top_sectors_text if top_sectors_text else "noneshuju"}

lingdie: {bottom_sectors_text if bottom_sectors_text else "noneshuju"}"""

            else:

                sector_block = "## 섹터 성과\n해당 시장에는 섹터 등락 데이터가 없습니다."


        data_no_indices_hint = (

            "주의: 시세 데이터 확보에 실패한 경우 시장 뉴스 중심으로 정성 분석을 수행하고 구체적인 지수 포인트는 만들지 마세요."
            if not indices_text

            else ""

        )

        if review_language == "en":

            data_no_indices_hint = (

                "Note: Market data fetch failed. Rely mainly on [Market News] for qualitative analysis. Do not invent index levels."

                if not indices_text

                else ""

            )

            indices_placeholder = indices_text if indices_text else "No index data (API error)"

            news_placeholder = news_text if news_text else "No relevant news"

        else:

            indices_placeholder = indices_text if indices_text else "지수 데이터 없음(API 오류)"
            news_placeholder = news_text if news_text else "관련 뉴스 없음"


        if review_language == "en":

            report_title = self._get_review_title(overview.date).removeprefix("## ").strip()

            return f"""You are a professional US/A/H market analyst. Please produce a concise market recap report based on the data below.



[Requirements]

- Output pure Markdown only

- No JSON

- No code blocks

- Use emoji sparingly in headings (at most one per heading)

- The entire fixed shell, headings, guidance, and conclusion must be in English



---



# Today's Market Data



## Date

{overview.date}



## Major Indices

{indices_placeholder}



{stats_block}



{sector_block}



## Market News

{news_placeholder}



{data_no_indices_hint}



{self._get_strategy_prompt_block()}



---



# Output Template (follow this structure)



## {report_title}



### 1. Market Summary

(2-3 sentences summarizing overall market tone, index moves, and liquidity.)



### 2. Index Commentary

({self._get_index_hint()})



### 3. Fund Flows

(Interpret what turnover, participation, and flow signals imply.)



### 4. Sector Highlights

(Analyze the drivers behind the leading and lagging sectors or themes.)



### 5. Outlook

(Provide the near-term outlook based on price action and news.)



### 6. Risk Alerts

(List the main risks to monitor.)



### 7. Strategy Plan

(Provide an offensive/balanced/defensive stance, a position-sizing guideline, one invalidation trigger, and end with ?쏤or reference only, not investment advice.??



---



Output the report content directly, no extra commentary.

"""



        # A guchangjingshiyongzhongwentishiyu

        return f"""당신은 전문 시장 분석가입니다. 아래 데이터를 바탕으로 {self._get_market_scope_name('zh')} 시장 리뷰 보고서를 한국어로 작성하세요.

# 입력 데이터

## 날짜
{overview.date}

## 지수 데이터
{indices_placeholder}

{stats_block}

{sector_block}

## 뉴스
{news_placeholder}

{self._get_strategy_prompt_block()}

# 출력 형식
## {overview.date} 시장 리뷰

### 1. 시장 총평
2-3문장으로 시장 상태, 핵심 모순, 다음 거래일 관찰 포인트를 요약하세요.

### 2. 지수 구조
주요 지수의 방향, 강한 지수와 약한 지수, 핵심 지지/저항을 설명하세요.

### 3. 섹터 주도권
상승/하락 섹터의 논리와 지속 가능성을 분석하세요.

### 4. 자금과 심리
거래대금, 시장 폭, 위험 선호를 해석하세요.

### 5. 뉴스 촉매
최근 뉴스가 시장에 미친 영향을 정리하세요.

### 6. 다음 거래일 전략
공격/균형/방어 중 하나의 관점으로 포지션과 리스크 관리 계획을 제시하세요.

검증되지 않은 수치나 사실은 만들지 마세요.
"""

    

    def _generate_template_review(self, overview: MarketOverview, news: List) -> str:

        """모델을 사용할 수 없을 때 템플릿 기반 시장 리뷰를 생성합니다."""

        template_language = self._get_template_review_language()

        mood_code = self.profile.mood_index_code

        # genju mood_index_code chazhaoduiyingzhishu

        # cn: mood_code="000001"竊똧dx.code kenengwei "sh000001"竊늶i mood_code jiewei竊?
        # us: mood_code="SPX"竊똧dx.code zhijiewei "SPX"

        mood_index = next(

            (

                idx

                for idx in overview.indices

                if idx.code == mood_code or idx.code.endswith(mood_code)

            ),

            None,

        )

        if mood_index:

            if mood_index.change_pct > 1:

                market_mood = self._get_market_mood_text("strong_up", template_language)

            elif mood_index.change_pct > 0:

                market_mood = self._get_market_mood_text("mild_up", template_language)

            elif mood_index.change_pct > -1:

                market_mood = self._get_market_mood_text("mild_down", template_language)

            else:

                market_mood = self._get_market_mood_text("strong_down", template_language)

        else:

            market_mood = self._get_market_mood_text("range", template_language)

        

        # zhishuquote竊늞ianjiegeshi竊?
        indices_text = ""

        for idx in overview.indices[:4]:

            direction = "+" if idx.change_pct > 0 else "-" if idx.change_pct < 0 else ""

            indices_text += f"- **{idx.name}**: {idx.current:.2f} ({direction}{abs(idx.change_pct):.2f}%)\n"

        

        # bankuaixinxi

        separator = ", " if template_language == "en" else "、"

        top_text = separator.join([s['name'] for s in overview.top_sectors[:3]])

        bottom_text = separator.join([s['name'] for s in overview.bottom_sectors[:3]])



        if template_language == "en":

            stats_section = ""

            if self.profile.has_market_stats:

                stats_section = f"""

### 3. Breadth & Liquidity

| Metric | Value |

|--------|-------|

| Advancers | {overview.up_count} |

| Decliners | {overview.down_count} |

| Limit-up | {overview.limit_up_count} |

| Limit-down | {overview.limit_down_count} |

| Turnover ({self._get_turnover_unit_label()}) | {overview.total_amount:.0f} |

"""

            sector_section = ""

            if self.profile.has_sector_rankings and (top_text or bottom_text):

                sector_section = f"""

### 4. Sector Highlights

- **Leaders**: {top_text or "N/A"}

- **Laggards**: {bottom_text or "N/A"}

"""

            market_names = {"us": "US Market Recap", "hk": "HK Market Recap"}

            market_name = market_names.get(self.region, "A-share Market Recap")

            report = f"""## {overview.date} {market_name}



### 1. Market Summary

Today's {self._get_market_scope_name(template_language)} showed **{market_mood}**.



### 2. Major Indices

{indices_text or "- No index data available"}

{stats_section}

{sector_section}

### 5. Risk Alerts

Market conditions can change quickly. The data above is for reference only and does not constitute investment advice.



{self._get_strategy_markdown_block(template_language)}



---

*Review Time: {datetime.now().strftime('%H:%M')}*

"""

            return report



        market_labels = {"cn": "A주", "us": "미국", "hk": "홍콩"}

        market_label = market_labels.get(self.region, "시장")

        dashboard_block = self._build_stats_block(overview)

        indices_block = self._build_indices_block(overview)

        sector_block = self._build_sector_block(overview)

        return f"""## {overview.date} 시장 리뷰

> 오늘 {market_label} 시장은 **{market_mood}** 흐름입니다. 지수 위치, 거래대금 변화, 섹터 지속성을 우선 확인하세요.

### 1. 시장 총평
{dashboard_block or "시장 폭 데이터가 없습니다."}

### 2. 지수 구조
{indices_block or indices_text or "지수 데이터가 없습니다."}

### 3. 섹터 주도권
{sector_block or "- 섹터 등락 데이터가 없습니다."}

### 4. 자금과 심리
- 거래대금과 상승/하락 종목 수를 함께 보며 추격 매수보다 확인을 우선하세요.

### 5. 뉴스 촉매
- 사용 가능한 뉴스가 없으면 테마 지속성 판단의 확신도를 낮추세요.

### 6. 다음 거래일 계획
- **결론**: 균형 관찰
- **포지션**: 중립 구간에서 관리하고 지수와 주도 섹터의 공진을 기다리세요.
- **관심 방향**: {top_text or "지수보다 강한 주도 섹터"}
- **회피 방향**: {bottom_text or "연속 약세와 회복 신호가 부족한 방향"}

### 7. 리스크 안내
- 본 리뷰는 참고용이며 투자 조언이 아닙니다.

---
*리뷰 시각: {datetime.now().strftime('%H:%M')}*
"""

    

    def run_daily_review(self) -> str:

        """

        zhixingmeiridapanfupanliucheng

        

        Returns:

            fupanbaogaowenben

        """

        logger.info("========== kaishidapanfupananalysis ==========")

        

        # 1. huoqumarketgailan

        overview = self.get_market_overview()

        

        # 2. sousuomarketxinwen

        news = self.search_market_news()

        

        # 3. shengchengfupanbaogao

        report = self.generate_market_review(overview, news)

        

        logger.info("========== dapanfupananalysiswancheng ==========")

        

        return report





# testrukou

if __name__ == "__main__":

    import sys

    sys.path.insert(0, '.')

    

    logging.basicConfig(

        level=logging.INFO,

        format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',

    )

    

    analyzer = MarketAnalyzer()

    

    # testhuoqumarketgailan

    overview = analyzer.get_market_overview()

    print(f"\n=== marketgailan ===")

    print(f"riqi: {overview.date}")

    print(f"zhishushuliang: {len(overview.indices)}")

    for idx in overview.indices:

        print(f"  {idx.name}: {idx.current:.2f} ({idx.change_pct:+.2f}%)")

    print(f"shangzhang: {overview.up_count} | xiadie: {overview.down_count}")

    print(f"chengjiaoe: {overview.total_amount:.0f}yi")

    

    # testshengchengmubanbaogao

    report = analyzer._generate_template_review(overview, [])

    print(f"\n=== fupanbaogao ===")

    print(report)


