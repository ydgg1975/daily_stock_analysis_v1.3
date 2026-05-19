# -*- coding: utf-8 -*-

"""

===================================

데이터 소스 기본 클래스 및 관리자

===================================



설계 패턴:전략 패턴 (Strategy Pattern)

- BaseFetcher: 추상 기본 클래스,통일된 인터페이스 정의

- DataFetcherManager: 전략 관리자,자동 전환 구현



차단 방지 전략:

1. 각 Fetcher의 내장 속도 제어 로직

2. 실패 시 다음 데이터 소스로 자동 전환

3. 지수 백오프 재시도 메쳮4니즘

"""





























import logging

import random

import time

from threading import BoundedSemaphore, RLock, Thread

from abc import ABC, abstractmethod

from datetime import datetime

from typing import Callable, Optional, List, Tuple, Dict, Any



import pandas as pd

import numpy as np

from src.data.stock_index_loader import get_index_stock_name

from src.data.stock_mapping import STOCK_NAME_MAP, is_meaningful_stock_name

from .fundamental_adapter import AkshareFundamentalAdapter



# peizhirizhi

logger = logging.getLogger(__name__)





# === biaozhunhualiemingdingyi ===

STANDARD_COLUMNS = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']





def unwrap_exception(exc: Exception) -> Exception:

    """

    Follow chained exceptions and return the deepest non-cyclic cause.

    """

    current = exc

    visited = set()



    while current is not None and id(current) not in visited:

        visited.add(id(current))

        next_exc = current.__cause__ or current.__context__

        if next_exc is None:

            break

        current = next_exc



    return current





def summarize_exception(exc: Exception) -> Tuple[str, str]:

    """

    Build a stable summary for logs while preserving the application-layer message.

    """

    root = unwrap_exception(exc)

    error_type = type(root).__name__

    message = str(exc).strip() or str(root).strip() or error_type

    return error_type, " ".join(message.split())





def normalize_stock_code(stock_code: str) -> str:

    """

    Normalize stock code by stripping exchange prefixes/suffixes.



    Accepted formats and their normalized results:

    - '600519'      -> '600519'   (already clean)

    - 'SH600519'    -> '600519'   (strip SH prefix)

    - 'SZ000001'    -> '000001'   (strip SZ prefix)

    - 'BJ920748'    -> '920748'   (strip BJ prefix, BSE)

    - 'sh600519'    -> '600519'   (case-insensitive)

    - '600519.SH'   -> '600519'   (strip .SH suffix)

    - '000001.SZ'   -> '000001'   (strip .SZ suffix)

    - '920748.BJ'   -> '920748'   (strip .BJ suffix, BSE)

    - 'HK00700'     -> 'HK00700'  (keep HK prefix for HK stocks)

    - '1810.HK'     -> 'HK01810'  (normalize HK suffix to canonical prefix form)

    - 'AAPL'        -> 'AAPL'     (keep US stock ticker as-is)



    This function is applied at the DataProviderManager layer so that

    all individual fetchers receive a clean 6-digit code (for A-shares/ETFs).

    """

    code = stock_code.strip()

    upper = code.upper()



    # Normalize HK prefix to a canonical 5-digit form (e.g. hk1810 -> HK01810)

    if upper.startswith('HK') and not upper.startswith('HK.'):

        candidate = upper[2:]

        if candidate.isdigit() and 1 <= len(candidate) <= 5:

            return f"HK{candidate.zfill(5)}"



    # Strip SH/SZ prefix (e.g. SH600519 -> 600519)

    if upper.startswith(('SH', 'SZ')) and not upper.startswith('SH.') and not upper.startswith('SZ.'):

        candidate = code[2:]

        # Only strip if the remainder looks like a valid numeric code

        if candidate.isdigit() and len(candidate) in (5, 6):

            return candidate



    # Strip BJ prefix (e.g. BJ920748 -> 920748)

    if upper.startswith('BJ') and not upper.startswith('BJ.'):

        candidate = code[2:]

        if candidate.isdigit() and len(candidate) == 6:

            return candidate



    # Strip .SH/.SZ/.BJ suffix (e.g. 600519.SH -> 600519, 920748.BJ -> 920748)

    if '.' in code:

        base, suffix = code.rsplit('.', 1)

        if suffix.upper() == 'HK' and base.isdigit() and 1 <= len(base) <= 5:

            return f"HK{base.zfill(5)}"

        if suffix.upper() in ('SH', 'SZ', 'SS', 'BJ') and base.isdigit():

            return base



    return code





ETF_PREFIXES = ("51", "52", "56", "58", "15", "16", "18")





def _is_us_market(code: str) -> bool:

    """미국 주식/지수 코드 여부 판단 (중국어 접미사 배제)。"""

    from .us_index_mapping import is_us_stock_code, is_us_index_code



    normalized = (code or "").strip().upper()

    return is_us_index_code(normalized) or is_us_stock_code(normalized)





def _is_hk_market(code: str) -> bool:

    """

    홍콩 주식 코드 여부 판단。



    `HK00700` 형태 지원 (A주 ETF/주식은 일반적으로 6자리)。

    """









    normalized = (code or "").strip().upper()

    if normalized.endswith(".HK"):

        base = normalized[:-3]

        return base.isdigit() and 1 <= len(base) <= 5

    if normalized.startswith("HK"):

        digits = normalized[2:]

        return digits.isdigit() and 1 <= len(digits) <= 5

    if normalized.isdigit() and len(normalized) == 5:

        return True

    return False





def _is_etf_code(code: str) -> bool:

    """A주 ETF 펀드 코드 판단 (보수적 규칙)。"""

    normalized = normalize_stock_code(code)

    return (

        normalized.isdigit()

        and len(normalized) == 6

        and normalized.startswith(ETF_PREFIXES)

    )





def _market_tag(code: str) -> str:

    """시장 태그 반환: cn/us/hk."""

    if _is_us_market(code):

        return "us"

    if _is_hk_market(code):

        return "hk"

    return "cn"





def is_bse_code(code: str) -> bool:

    """

    Check if the code is a Beijing Stock Exchange (BSE) A-share code.



    BSE rules (2026):

    - New format (2024+): 92xxxx main trading codes

    - Historical ranges: 43xxxx, 83xxxx, 87xxxx, 88xxxx

    - Special instruments: 81xxxx convertible bonds, 82xxxx preferred shares

    - Subscription codes: 889xxx

    Note: 900xxx are Shanghai B-shares and must return False.

    """

    c = (code or "").strip().split(".")[0]

    if len(c) != 6 or not c.isdigit():

        return False



    if c.startswith("900"):

        return False



    return c.startswith(("92", "43", "81", "82", "83", "87", "88"))



def is_st_stock(name: str) -> bool:

    """

    Check if the stock is an ST or *ST stock based on its name.



    ST stocks have special trading rules and typically a ±5% limit.

    """

    n = (name or "").upper()

    return 'ST' in n



def is_kc_cy_stock(code: str) -> bool:

    """

    Check if the stock is a STAR Market (kechuangban) or ChiNext (chuangyeban) stock based on its code.



    - STAR Market: Codes starting with 688

    - ChiNext: Codes starting with 300

    Both have a ±20% limit.

    """

    c = (code or "").strip().split(".")[0]

    return c.startswith("688") or c.startswith("30")





def canonical_stock_code(code: str) -> str:

    """

    Return the canonical (uppercase) form of a stock code.



    This is a display/storage layer concern, distinct from normalize_stock_code

    which strips exchange prefixes. Apply at system input boundaries to ensure

    consistent case across BOT, WEB UI, API, and CLI paths (Issue #355).



    Examples:

        'aapl'    -> 'AAPL'

        'AAPL'    -> 'AAPL'

        '600519'  -> '600519'  (digits are unchanged)

        'hk00700' -> 'HK00700'

    """

    return (code or "").strip().upper()





class DataFetchError(Exception):

    """데이터 조회 예외 기본 클래스"""

    pass





class RateLimitError(DataFetchError):

    """API 속도 제한 예외"""

    pass





class DataSourceUnavailableError(DataFetchError):

    """데이터 소스 사용 불가 예외"""

    pass





class BaseFetcher(ABC):

    """

    데이터 소스 추상 기본 클래스

    

    역할:

    1. 통일된 데이터 조회인터페이스

    2. 데이터 표준화 메서드 제공

    3. 일반적인 기술 지표 계산 구현

    

    자식 클래스 구현 항목:

    - _fetch_raw_data(): 구체적 데이터 소스에서 원시 데이터 조회

    - _normalize_data(): 원시 데이터를 표준 포맷으로 변환

    """























    

    name: str = "BaseFetcher"

    priority: int = 99  # youxianjishuziyuexiaoyueyouxian

    

    @abstractmethod

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:

        """

        데이터 소스에서 원시 데이터 조회 (자식 클래스 필수 구현)

        

        Args:

            stock_code: 주식 코드,ru '600519', '000001'

            start_date: 시작 날짜,포맷 'YYYY-MM-DD'

            end_date: 종료 날짜,포맷 'YYYY-MM-DD'

            

        Returns:

            원시 데이터 DataFrame (컬럼 이름은 데이터 소스에 따라 다름)

        """





















        pass

    

    @abstractmethod

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:

        """

        데이터 컬럼 이름 표준화 (자식 클래스 필수 구현)



        다른 데이터 소스의 컬럼 이름을 통일:

        ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']

        """











        pass



    def get_main_indices(self, region: str = "cn") -> Optional[List[Dict[str, Any]]]:

        """

        주요 지수 실시 현황 조회



        Args:

            region: 시장 영역,cn=Agu us=미국



        Returns:

            List[Dict]: 지수 목록,각 요소는 딕셔너리,baohan:

                - code: 지수 코드

                - name: 지수 이름

                - current: 현재 지수

                - change: 등락/하락 포인트

                - change_pct: 등락률(%)

                - volume: 거래량

                - amount: 거래대금

        """































        return None



    def get_market_stats(self) -> Optional[Dict[str, Any]]:

        """

        시장 등락/하락 통계 조회



        Returns:

            Dict: baohan:

                - up_count: 상승 종목 수

                - down_count: 하락 종목 수

                - flat_count: 보합 종목 수

                - limit_up_count: 상한가 종목 수

                - limit_down_count: 하한가 종목 수

                - total_amount: 전체 거래대금

        """























        return None



    def get_sector_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:

        """

        섹터 등락/하락 순위 조회



        Args:

            n: 앞에서 N개 반환



        Returns:

            Tuple: (상승률 상위 섹터 목록, 하락률 상위 섹터 목록)

        """

















        return None



    def get_concept_rankings(self, n: int = 5) -> Optional[Tuple[List[Dict], List[Dict]]]:

        """

        테맄/토픽 등락/하락 순위 조회。



        Returns:

            Tuple: (상승률 상위 테맄 목록, 하락률 상위 테맄 목록)

        """











        return None



    def get_hot_stocks(self, n: int = 10) -> Optional[List[Dict[str, Any]]]:

        """

        시장 인기 종목 순위 조회。



        Returns:

            List[Dict]: 인기 종목 목록

        """











        return None



    def get_limit_up_pool(

        self,

        date: Optional[str] = None,

        n: int = 20,

    ) -> Optional[List[Dict[str, Any]]]:

        """

        상한가 리스트/연속 상한가 대업。



        Args:

            date: YYYYMMDD,기본값은 구체적 데이터 소스가 결정

            n: 반환 건수

        """













        return None



    def get_daily_data(

        self,

        stock_code: str, 

        start_date: Optional[str] = None,

        end_date: Optional[str] = None,

        days: int = 30

    ) -> pd.DataFrame:

        """

        일분 데이터 조회 (통합 입력창)

        

        흐름:

        1. 날짜 범위 계산

        2. 자식 클래스의 원시 데이터 조회 호출

        3. biaozhunhualieming

        4. 기술 지표 계산

        

        Args:

            stock_code: 주식 코드

            start_date: 시작 날짜 (옵션)

            end_date: 종료 날짜 (옵션, 기본값 오늘)

            days: 조회 기간(~인 경우 start_date 알 수 없는dingshi사용)

            

        Returns:

            표준화된 DataFrame,baohanjishuzhibiao

        """



































        # jisuanriqifanwei

        if end_date is None:

            end_date = datetime.now().strftime('%Y-%m-%d')

        

        if start_date is None:

            # morenhuoquzuijin 30 gejiaoyiri(anrilirigusuan,duoquyixie)

            from datetime import timedelta

            start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=days * 2)

            start_date = start_dt.strftime('%Y-%m-%d')



        request_start = time.time()

        logger.info(f"[{self.name}] kaishihuoqu {stock_code} rixianshuju: fanwei={start_date} ~ {end_date}")

        

        try:

            # Step 1: huoquyuanshishuju

            raw_df = self._fetch_raw_data(stock_code, start_date, end_date)

            

            if raw_df is None or raw_df.empty:

                raise DataFetchError(f"[{self.name}] weihuoqudao {stock_code} deshuju")

            

            # Step 2: biaozhunhualieming

            df = self._normalize_data(raw_df, stock_code)

            

            # Step 3: shujuqingxi

            df = self._clean_data(df)

            

            # Step 4: jisuanjishuzhibiao

            df = self._calculate_indicators(df)



            elapsed = time.time() - request_start

            logger.info(

                f"[{self.name}] {stock_code} huoquchenggong: fanwei={start_date} ~ {end_date}, "

                f"rows={len(df)}, elapsed={elapsed:.2f}s"

            )

            return df

            

        except Exception as e:

            elapsed = time.time() - request_start

            error_type, error_reason = summarize_exception(e)

            logger.error(

                f"[{self.name}] {stock_code} huoqushibai: fanwei={start_date} ~ {end_date}, "

                f"error_type={error_type}, elapsed={elapsed:.2f}s, reason={error_reason}"

            )

            raise DataFetchError(f"[{self.name}] {stock_code}: {error_reason}") from e

    

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:

        """

        데이터 정제

        

        처리:

        1. 날짜 컬럼 포맷 확인

        2. 숫자 타입 변환

        3. 누락 행 제거

        4. 날짜순 정렬

        """

















        df = df.copy()

        

        # quebaoriqiliewei datetime leixing

        if 'date' in df.columns:

            df['date'] = pd.to_datetime(df['date'])

        

        # shuzhilieleixingzhuanhuan

        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']

        for col in numeric_cols:

            if col in df.columns:

                df[col] = pd.to_numeric(df[col], errors='coerce')

        

        # quchuguanjianlieweikongdexing

        df = df.dropna(subset=['close', 'volume'])

        

        # anriqishengxupaixu

        df = df.sort_values('date', ascending=True).reset_index(drop=True)

        

        return df

    

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:

        """

        기술 지표 계산

        

        jisuanzhibiao:

        - MA5, MA10, MA20: 이동평균선

        - Volume_Ratio: 거래량 비율 (오늘 거래량 / 5일 평균 거래량)

        """













        df = df.copy()

        

        # yidongpingjunxian

        df['ma5'] = df['close'].rolling(window=5, min_periods=1).mean()

        df['ma10'] = df['close'].rolling(window=10, min_periods=1).mean()

        df['ma20'] = df['close'].rolling(window=20, min_periods=1).mean()

        

        # liangbi:dangrichengjiaoliang / 5ripingjunchengjiaoliang

        # zhuyi:cichude volume_ratio shi“rixianchengjiaoliang / qian5rijunliang(shift 1)”dexiangduibeishu,

        # yubufenjiaoyiruanjiankoujingde“fenshiliangbi(tongyishikeduibi)”butong,hanyigengjiejin“fangliangbeishu”。

        # gaixingweimuqianbaoliu(anxuqiubugailuoji)。

        avg_volume_5 = df['volume'].rolling(window=5, min_periods=1).mean()

        df['volume_ratio'] = df['volume'] / avg_volume_5.shift(1)

        df['volume_ratio'] = df['volume_ratio'].fillna(1.0)

        

        # baoliu2weixiaoshu

        for col in ['ma5', 'ma10', 'ma20', 'volume_ratio']:

            if col in df.columns:

                df[col] = df[col].round(2)

        

        return df

    

    @staticmethod

    def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:

        """

        지능적 무작위 대기 (Jitter)

        

        차단 방지 전략:사람 행동 모의 무작위 지연

        요청 사이에 불규칙적 대기 시간 추가

        """











        sleep_time = random.uniform(min_seconds, max_seconds)

        logger.debug(f"suijixiumian {sleep_time:.2f} miao...")

        time.sleep(sleep_time)





class DataFetcherManager:

    """

    데이터 소스 전략 관리자

    

    역할:

    1. guanliduogeshujuyuan(anyouxianjipaixu)

    2. zidongguzhang전환(Failover)

    3. tigongtongyi의 데이터huoqujiekou

    

    전환celve:

    - 고우선순위 데이터 소스 선택적 사용

    - shibaihouzidong전환daoxiayige

    - 모든 데이터 소스 실패 시 예외 발생

    """



























    _DAILY_MARKET_FETCHER_SUPPORT = {

        "EfinanceFetcher": {"cn"},

        "AkshareFetcher": {"cn", "hk"},

        "TushareFetcher": {"cn", "hk"},

        "PytdxFetcher": {"cn"},

        "BaostockFetcher": {"cn"},

        "YfinanceFetcher": {"cn", "hk", "us"},

        "LongbridgeFetcher": {"hk", "us"},

        "FinnhubFetcher": {"us"},

        "AlphaVantageFetcher": {"us"},

    }

    

    def __init__(self, fetchers: Optional[List[BaseFetcher]] = None):

        """

        관리자 초기화

        

        Args:

            fetchers: 데이터 소스 목록 (옵션, 기본값은 우선순위로 자동 생성)

        """











        self._fetchers: List[BaseFetcher] = []

        self._fetchers_lock = RLock()

        self._fetchers_by_name: Dict[str, BaseFetcher] = {}

        self._fetcher_call_locks: Dict[int, RLock] = {}

        self._fetcher_call_locks_lock = RLock()

        self._stock_name_cache: Dict[str, str] = {}

        self._stock_name_cache_lock = RLock()

        

        if fetchers:

            # anyouxianjipaixu

            self._fetchers = sorted(fetchers, key=lambda f: f.priority)

            self._refresh_fetcher_indexes_locked()

        else:

            # morenshujuyuanjiangzaishoucishiyongshiyanchijiazai

            self._init_default_fetchers()

        self._fundamental_adapter = AkshareFundamentalAdapter()

        self._tickflow_fetcher = None

        self._tickflow_api_key: Optional[str] = None

        self._tickflow_lock = RLock()

        self._fundamental_cache: Dict[str, Dict[str, Any]] = {}

        self._fundamental_cache_lock = RLock()

        self._fundamental_timeout_worker_limit = 8

        self._fundamental_timeout_slots = BoundedSemaphore(self._fundamental_timeout_worker_limit)



    def _ensure_concurrency_guards(self) -> None:

        """Lazily initialize thread-safety primitives for test scaffolds using __new__."""

        if not hasattr(self, "_fetchers_lock") or self._fetchers_lock is None:

            self._fetchers_lock = RLock()

        if not hasattr(self, "_fetchers_by_name") or self._fetchers_by_name is None:

            self._fetchers_by_name = {}

        if not hasattr(self, "_fetcher_call_locks") or self._fetcher_call_locks is None:

            self._fetcher_call_locks = {}

        if not hasattr(self, "_fetcher_call_locks_lock") or self._fetcher_call_locks_lock is None:

            self._fetcher_call_locks_lock = RLock()

        if not hasattr(self, "_stock_name_cache") or self._stock_name_cache is None:

            self._stock_name_cache = {}

        if not hasattr(self, "_stock_name_cache_lock") or self._stock_name_cache_lock is None:

            self._stock_name_cache_lock = RLock()



    def _get_fetchers_snapshot(self) -> List[BaseFetcher]:

        self._ensure_concurrency_guards()

        with self._fetchers_lock:

            return list(getattr(self, "_fetchers", []))



    def _refresh_fetcher_indexes_locked(self) -> None:

        self._fetchers_by_name = {fetcher.name: fetcher for fetcher in self._fetchers}



    def _get_fetcher_by_name(self, fetcher_name: str, capability: str = "") -> Optional[BaseFetcher]:

        self._ensure_concurrency_guards()

        with self._fetchers_lock:

            fetcher = self._fetchers_by_name.get(fetcher_name)

            if fetcher is None and self._fetchers:

                self._refresh_fetcher_indexes_locked()

                fetcher = self._fetchers_by_name.get(fetcher_name)

        if fetcher is None:

            return None

        if not self._is_fetcher_available(fetcher, capability=capability):

            return None

        return fetcher



    @staticmethod

    def _call_availability_probe(fetcher: BaseFetcher, probe_name: str, capability: str) -> Optional[bool]:

        probe = getattr(fetcher, probe_name, None)

        if not callable(probe):

            return None

        try:

            if probe_name == "is_available_for_request":

                return bool(probe(capability))

            return bool(probe())

        except TypeError:

            return bool(probe())

        except Exception as exc:

            logger.debug(

                "[shujuyuankeyongxing] %s.%s jianchashibai(capability=%s): %s",

                fetcher.name,

                probe_name,

                capability or "default",

                exc,

            )

            return False



    @classmethod

    def _is_fetcher_available(cls, fetcher: BaseFetcher, capability: str = "") -> bool:

        for probe_name in ("is_available_for_request", "is_available", "_is_available"):

            result = cls._call_availability_probe(fetcher, probe_name, capability)

            if result is not None:

                return result

        return True



    def _get_fetcher_call_lock(self, fetcher: BaseFetcher) -> RLock:

        self._ensure_concurrency_guards()

        fetcher_id = id(fetcher)

        with self._fetcher_call_locks_lock:

            lock = self._fetcher_call_locks.get(fetcher_id)

            if lock is None:

                lock = RLock()

                self._fetcher_call_locks[fetcher_id] = lock

            return lock



    def _call_fetcher_method(self, fetcher: BaseFetcher, method_name: str, *args, **kwargs):

        """Serialize shared fetcher state access through manager-owned per-instance locks."""

        method = getattr(fetcher, method_name)

        with self._get_fetcher_call_lock(fetcher):

            return method(*args, **kwargs)



    @classmethod

    def _filter_daily_fetchers_for_market(

        cls,

        fetchers: List[BaseFetcher],

        market: str,

    ) -> List[BaseFetcher]:

        """Skip built-in daily fetchers that are known not to support a market."""

        if market not in {"cn", "hk", "us"}:

            return fetchers



        kept: List[BaseFetcher] = []

        skipped: List[str] = []

        for fetcher in fetchers:

            supported = cls._DAILY_MARKET_FETCHER_SUPPORT.get(fetcher.name)

            if supported is not None and market not in supported:

                skipped.append(fetcher.name)

            else:

                kept.append(fetcher)



        if skipped:

            logger.info(

                "[shujuyuanluyou] %s rixiantiaoguobuzhichideshujuyuan: %s",

                market,

                ", ".join(skipped),

            )

        return kept



    @classmethod

    def _filter_fetchers_by_capability(

        cls,

        fetchers: List[BaseFetcher],

        capability: str,

    ) -> List[BaseFetcher]:

        """Skip request-time unavailable fetchers before entering route-specific loops."""

        kept: List[BaseFetcher] = []

        skipped: List[str] = []



        for fetcher in fetchers:

            if cls._is_fetcher_available(fetcher, capability=capability):

                kept.append(fetcher)

            else:

                skipped.append(fetcher.name)



        if skipped:

            logger.info(

                "[shujuyuanluyou] %s tiaoguozanbukeyongdeshujuyuan: %s",

                capability or "request",

                ", ".join(skipped),

            )



        return kept



    def _get_cached_stock_name(self, stock_code: str) -> Optional[str]:

        self._ensure_concurrency_guards()

        with self._stock_name_cache_lock:

            return self._stock_name_cache.get(stock_code)



    def _cache_stock_name(self, stock_code: str, name: Optional[str]) -> Optional[str]:

        if name is None:

            return None

        self._ensure_concurrency_guards()

        with self._stock_name_cache_lock:

            self._stock_name_cache[stock_code] = name

        return name



    def _get_tickflow_fetcher(self):

        """Lazily create a TickFlow fetcher for market-review-only calls."""

        from src.config import get_config



        config = get_config()

        api_key = (getattr(config, "tickflow_api_key", None) or "").strip()



        if not hasattr(self, "_tickflow_lock") or self._tickflow_lock is None:

            self._tickflow_lock = RLock()



        with self._tickflow_lock:

            current_fetcher = getattr(self, "_tickflow_fetcher", None)

            current_key = getattr(self, "_tickflow_api_key", None)



            if not api_key:

                if current_fetcher is not None and hasattr(current_fetcher, "close"):

                    try:

                        current_fetcher.close()

                    except Exception as exc:

                        logger.debug("[TickFlowFetcher] guanbijiushilishibai: %s", exc)

                self._tickflow_fetcher = None

                self._tickflow_api_key = None

                return None



            if current_fetcher is not None and current_key == api_key:

                return current_fetcher



            if current_fetcher is not None and hasattr(current_fetcher, "close"):

                try:

                    current_fetcher.close()

                except Exception as exc:

                    logger.debug("[TickFlowFetcher] qiehuanshilishiguanbishibai: %s", exc)



            try:

                from .tickflow_fetcher import TickFlowFetcher



                fetcher = TickFlowFetcher(api_key=api_key)

                self._tickflow_fetcher = fetcher

                self._tickflow_api_key = api_key

                return fetcher

            except Exception as exc:

                logger.warning("[TickFlowFetcher] chushihuashibai: %s", exc)

                self._tickflow_fetcher = None

                self._tickflow_api_key = None

                return None



    def close(self) -> None:

        """Best-effort release of manager-owned resources."""

        if not hasattr(self, "_tickflow_lock") or self._tickflow_lock is None:

            self._tickflow_lock = RLock()



        with self._tickflow_lock:

            current_fetcher = getattr(self, "_tickflow_fetcher", None)

            self._tickflow_fetcher = None

            self._tickflow_api_key = None



        if current_fetcher is not None and hasattr(current_fetcher, "close"):

            try:

                current_fetcher.close()

            except Exception as exc:

                logger.debug("[TickFlowFetcher] guanbiguanliqiziyuanshibai: %s", exc)



    def __del__(self) -> None:

        try:

            self.close()

        except Exception:

            # Best-effort cleanup during interpreter shutdown.

            pass



    def _get_fundamental_cache_key(self, stock_code: str, budget_seconds: Optional[float] = None) -> str:

        """기본적 인자 캐시 키 생성 (예산 분 통일 및 저예산 결과 오염 방지)。"""

        normalized_code = normalize_stock_code(stock_code)

        if budget_seconds is None:

            return f"{normalized_code}|budget=default"

        try:

            budget = max(0.0, float(budget_seconds))

        except (TypeError, ValueError):

            budget = 0.0

        # 100ms bucket to balance cache reuse and scenario isolation.

        budget_bucket = int(round(budget * 10))

        return f"{normalized_code}|budget={budget_bucket}"



    def _prune_fundamental_cache(self, ttl_seconds: int, max_entries: int) -> None:

        """Prune expired and overflow fundamental cache items."""

        with self._fundamental_cache_lock:

            if not self._fundamental_cache:

                return



            now_ts = time.time()

            if ttl_seconds > 0:

                cache_items = list(self._fundamental_cache.items())

                expired_keys = [

                    key

                    for key, value in cache_items

                    if now_ts - float(value.get("ts", 0)) > ttl_seconds

                ]

                for key in expired_keys:

                    self._fundamental_cache.pop(key, None)



            if max_entries > 0 and len(self._fundamental_cache) > max_entries:

                overflow = len(self._fundamental_cache) - max_entries

                sorted_items = sorted(

                    list(self._fundamental_cache.items()),

                    key=lambda item: float(item[1].get("ts", 0)),

                )

                for key, _ in sorted_items[:overflow]:

                    self._fundamental_cache.pop(key, None)



    @staticmethod

    def _try_scalar_isna(value: Any, context: str) -> Optional[bool]:

        """Return scalar ``pd.isna`` result, or ``None`` when callers should use fallback logic."""

        if isinstance(value, (dict, list, tuple, set, pd.DataFrame, pd.Series, pd.Index)):

            return None



        if isinstance(value, np.ndarray):

            if value.ndim != 0:

                return None

            value = value.item()



        try:

            isna_result = pd.isna(value)

        except (TypeError, ValueError) as exc:

            if hasattr(value, "__array__"):

                logger.debug(

                    "[%s] pd.isna failed for array-like object; re-raise: value_type=%s error_type=%s",

                    context,

                    type(value).__name__,

                    type(exc).__name__,

                )

                raise

            logger.debug(

                "[%s] pd.isna fallback: value_type=%s error_type=%s",

                context,

                type(value).__name__,

                type(exc).__name__,

            )

            return None



        if isinstance(isna_result, (bool, np.bool_)):

            return bool(isna_result)



        if isinstance(isna_result, np.ndarray):

            if isna_result.ndim == 0:

                return bool(isna_result.item())

            logger.debug(

                "[%s] pd.isna returned non-scalar result: value_type=%s result_type=%s",

                context,

                type(value).__name__,

                type(isna_result).__name__,

            )

            return None



        logger.debug(

            "[%s] pd.isna returned unexpected result type: value_type=%s result_type=%s",

            context,

            type(value).__name__,

            type(isna_result).__name__,

        )

        return None



    @staticmethod

    def _is_missing_board_value(value: Any) -> bool:

        """Return True when a board field value should be treated as missing."""

        if value is None:

            return True

        is_missing = DataFetcherManager._try_scalar_isna(value, "board_value")

        if is_missing is True:

            return True

        text = str(value).strip()

        return text == "" or text.lower() in {"nan", "none", "null", "na", "n/a"}



    @staticmethod

    def _normalize_belong_boards(raw_data: Any) -> List[Dict[str, Any]]:

        """Normalize belong-board results from heterogeneous providers."""

        if DataFetcherManager._is_missing_board_value(raw_data):

            return []



        normalized: List[Dict[str, Any]] = []

        dedupe = set()



        if isinstance(raw_data, pd.DataFrame):

            if raw_data.empty:

                return []

            name_col = next(

                (

                    col

                    for col in raw_data.columns

                    if str(col) in {"bankuaimingcheng", "bankuai", "suoshubankuai", "bankuaiming", "name", "industry"}

                ),

                None,

            )

            code_col = next(

                (

                    col

                    for col in raw_data.columns

                    if str(col) in {"bankuaidaima", "daima", "code"}

                ),

                None,

            )

            type_col = next(

                (

                    col

                    for col in raw_data.columns

                    if str(col) in {"bankuaileixing", "leibie", "type"}

                ),

                None,

            )

            if name_col is None:

                return []

            for _, row in raw_data.iterrows():

                board_name_raw = row.get(name_col, "")

                if DataFetcherManager._is_missing_board_value(board_name_raw):

                    continue

                board_name = str(board_name_raw).strip()

                if board_name in dedupe:

                    continue

                dedupe.add(board_name)

                item = {"name": board_name}

                if code_col is not None:

                    board_code_raw = row.get(code_col, "")

                    if not DataFetcherManager._is_missing_board_value(board_code_raw):

                        item["code"] = str(board_code_raw).strip()

                if type_col is not None:

                    board_type_raw = row.get(type_col, "")

                    if not DataFetcherManager._is_missing_board_value(board_type_raw):

                        item["type"] = str(board_type_raw).strip()

                normalized.append(item)

            return normalized



        if isinstance(raw_data, dict):

            raw_data = [raw_data]



        if isinstance(raw_data, (list, tuple, set)):

            for item in raw_data:

                if isinstance(item, dict):

                    board_name_raw = (

                        item.get("name")

                        or item.get("board_name")

                        or item.get("bankuaimingcheng")

                        or item.get("bankuai")

                        or item.get("suoshubankuai")

                        or item.get("bankuaiming")

                        or item.get("industry")

                        or item.get("hangye")

                    )

                    if DataFetcherManager._is_missing_board_value(board_name_raw):

                        continue

                    board_name = str(board_name_raw).strip()

                    if board_name in dedupe:

                        continue

                    dedupe.add(board_name)

                    normalized_item: Dict[str, Any] = {"name": board_name}

                    code_raw = (

                        item.get("code")

                        or item.get("bankuaidaima")

                        or item.get("daima")

                    )

                    if not DataFetcherManager._is_missing_board_value(code_raw):

                        normalized_item["code"] = str(code_raw).strip()

                    type_raw = (

                        item.get("type")

                        or item.get("bankuaileixing")

                        or item.get("leibie")

                    )

                    if not DataFetcherManager._is_missing_board_value(type_raw):

                        normalized_item["type"] = str(type_raw).strip()

                    normalized.append(normalized_item)

                    continue

                if DataFetcherManager._is_missing_board_value(item):

                    continue

                board_name = str(item).strip()

                if board_name in dedupe:

                    continue

                dedupe.add(board_name)

                normalized.append({"name": board_name})

            return normalized



        if not DataFetcherManager._is_missing_board_value(raw_data):

            board_name = str(raw_data).strip()

            return [{"name": board_name}]

        return []

    

    def _init_default_fetchers(self) -> None:

        """

        기본 데이터 소스 목록 초기화



        youxianjidongtaitiaozhengluoji:

        - ruguopeizhile TUSHARE_TOKEN:shilihua TushareFetcher,binganqineibuluojitishengyouxianji

        - ruguopeizhile Longbridge pingju:shilihua LongbridgeFetcher zuoweimeigu/ganggudoudi

        - weipeizhidekexuanshujuyuanbushilihua,bimianzaipilianglaqushifanfutancewuxiaoyuan

        - morenyouxianji:

          0. EfinanceFetcher (Priority 0) - zuigaoyouxianji

          1. AkshareFetcher (Priority 1)

          2. PytdxFetcher (Priority 2) - tongdaxin

          3. BaostockFetcher (Priority 3)

          4. YfinanceFetcher (Priority 4)

        """



























        from src.config import get_config

        from .efinance_fetcher import EfinanceFetcher

        from .akshare_fetcher import AkshareFetcher

        from .tushare_fetcher import TushareFetcher

        from .pytdx_fetcher import PytdxFetcher

        from .baostock_fetcher import BaostockFetcher

        from .yfinance_fetcher import YfinanceFetcher

        from .longbridge_fetcher import LongbridgeFetcher

        config = get_config()

        # chuangjiansuoyoushujuyuanshili(youxianjizaige Fetcher de __init__ zhongqueding)

        efinance = EfinanceFetcher()

        akshare = AkshareFetcher()

        pytdx = PytdxFetcher()      # tongdaxinshujuyuan(kepei PYTDX_HOST/PYTDX_PORT)

        baostock = BaostockFetcher()

        yfinance = YfinanceFetcher()

        optional_fetchers: List[BaseFetcher] = []



        tushare_token = (getattr(config, "tushare_token", None) or "").strip()

        if tushare_token:

            optional_fetchers.append(TushareFetcher())  # huigenju Token peizhizidongtiaozhengyouxianji

        else:

            logger.debug("[shujuyuanchushihua] tiaoguoweipeizhide TushareFetcher")



        has_longbridge_creds = bool(

            (getattr(config, "longbridge_app_key", None) or "").strip()

            and (getattr(config, "longbridge_app_secret", None) or "").strip()

            and (getattr(config, "longbridge_access_token", None) or "").strip()

        )

        if has_longbridge_creds:

            optional_fetchers.append(LongbridgeFetcher())  # zhangqiao(meigu/ganggudoudi,lanjiazai)

        else:

            logger.debug("[shujuyuanchushihua] tiaoguoweipeizhide LongbridgeFetcher")



        finnhub_api_key = (getattr(config, "finnhub_api_key", None) or "").strip()

        if finnhub_api_key:

            from .finnhub_fetcher import FinnhubFetcher

            optional_fetchers.append(FinnhubFetcher())

        else:

            logger.debug("[shujuyuanchushihua] tiaoguoweipeizhide FinnhubFetcher")



        alphavantage_api_key = (getattr(config, "alphavantage_api_key", None) or "").strip()

        if alphavantage_api_key:

            from .alphavantage_fetcher import AlphaVantageFetcher

            optional_fetchers.append(AlphaVantageFetcher())

        else:

            logger.debug("[shujuyuanchushihua] tiaoguoweipeizhide AlphaVantageFetcher")



        # chushihuashujuyuanliebiao

        self._ensure_concurrency_guards()

        with self._fetchers_lock:

            self._fetchers = [

                efinance,

                akshare,

                pytdx,

                baostock,

                yfinance,

                *optional_fetchers,

            ]



            # anyouxianjipaixu(Tushare ruguopeizhile Token qiechushihuachenggong,youxianjiwei 0)

            self._fetchers.sort(key=lambda f: f.priority)

            self._refresh_fetcher_indexes_locked()



        # goujianyouxianjishuoming

        priority_info = ", ".join([f"{f.name}(P{f.priority})" for f in self._get_fetchers_snapshot()])

        logger.info(f"yichushihua {len(self._fetchers)} geshujuyuan(anyouxianji): {priority_info}")

    

    def add_fetcher(self, fetcher: BaseFetcher) -> None:

        """데이터 소스 추가 및 재정렬"""

        self._ensure_concurrency_guards()

        with self._fetchers_lock:

            self._fetchers.append(fetcher)

            self._fetchers.sort(key=lambda f: f.priority)

            self._refresh_fetcher_indexes_locked()

    

    def get_daily_data(

        self, 

        stock_code: str,

        start_date: Optional[str] = None,

        end_date: Optional[str] = None,

        days: int = 30

    ) -> Tuple[pd.DataFrame, str]:

        """

        조회일분 데이터(자동전환데이터 소스)

        

        guzhang전환celve:

        1. meiguzhishu/meigugupiaozhijieluyoudao YfinanceFetcher

        2. qitadaimacongzuigaoyouxianjishujuyuankaishichangshi

        3. buhuoyichanghouzidong전환daoxiayige

        4. jilumeigeshujuyuandeshibaiyuanyin

        5. suoyoushujuyuanshibaihoupaochuxiangxiyichang

        

        Args:

            stock_code: 주식 코드

            start_date: 시작 날짜

            end_date: 종료 날짜

            days: 조회 기간

            

        Returns:

            Tuple[DataFrame, str]: (데이터, 성공의 데이터yuanmingcheng)

            

        Raises:

            DataFetchError: suoyoushujuyuandoushibaishipaochu

        """











































        from .us_index_mapping import is_us_index_code, is_us_stock_code



        # Normalize code (strip SH/SZ prefix etc.)

        stock_code = normalize_stock_code(stock_code)



        fetchers = self._get_fetchers_snapshot()

        errors = []

        request_start = time.time()



        # kuaisulujing:meigushiyongzhuanyongshujuyuanluyou;gangguxianguolvbuzhichiganggurixiandeshujuyuan

        #   - peizhizhangqiaopingjuhou: Longbridge weishouxuan, YFinance/AkShare doudi

        #   - weipeizhizhangqiao:     YFinance weishouxuan(meigu), tongyong fetcher xunhuan(ganggu)

        #   - meiguzhishu:       shizhong YFinance weishouxuan(Longbridge butigongzhishuKxian)

        is_us_index = is_us_index_code(stock_code)

        is_us = is_us_index or is_us_stock_code(stock_code)

        is_hk = (not is_us) and _is_hk_market(stock_code)

        if is_hk:

            fetchers = self._filter_daily_fetchers_for_market(fetchers, "hk")

        fetchers = self._filter_fetchers_by_capability(fetchers, capability="daily_data")

        total_fetchers = len(fetchers)



        if total_fetchers == 0:

            market_label = "meiguzhishu" if is_us_index else "meigu" if is_us else "ganggu" if is_hk else "Agu"

            error_summary = f"{market_label} {stock_code} huoqushibai:\nzanwukeyongshujuyuan"

            logger.error(f"[shujuyuanzhongzhi] {stock_code} huoqushibai: {error_summary}")

            raise DataFetchError(error_summary)



        # meigu(hanmeiguzhishu)shiyongzhuanyongluyou;gangguzouxiafangtongyongshujuyuanxunhuan

        # Failover chain: Finnhub(P2) -> AlphaVantage(P3) -> Yfinance(P4) -> Longbridge(P5)

        # When Longbridge preferred: Longbridge -> Finnhub -> AlphaVantage -> Yfinance

        if is_us:

            prefer_lb = self._longbridge_preferred(capability="daily_data") and not is_us_index

            if is_us_index:

                # zhishushizhong YFinance shouxuan(Longbridge butigongzhishuKxian)

                source_order = ["YfinanceFetcher", "FinnhubFetcher"]

            elif prefer_lb:

                source_order = ["LongbridgeFetcher", "FinnhubFetcher", "AlphaVantageFetcher", "YfinanceFetcher"]

            else:

                source_order = ["FinnhubFetcher", "AlphaVantageFetcher", "YfinanceFetcher", "LongbridgeFetcher"]

            market_label = "meiguzhishu" if is_us_index else "meigu"



            for src_name in source_order:

                for attempt, fetcher in enumerate(fetchers, start=1):

                    if fetcher.name != src_name:

                        continue

                    try:

                        role = "shouxuan" if src_name == source_order[0] else "doudi"

                        logger.info(

                            f"[shujuyuanchangshi {attempt}/{total_fetchers}] [{fetcher.name}] "

                            f"{market_label} {stock_code} {role}luyou..."

                        )

                        df = self._call_fetcher_method(

                            fetcher,

                            "get_daily_data",

                            stock_code=stock_code,

                            start_date=start_date,

                            end_date=end_date,

                            days=days,

                        )

                        if df is not None and not df.empty:

                            elapsed = time.time() - request_start

                            logger.info(

                                f"[shujuyuanwancheng] {stock_code} shiyong [{fetcher.name}] huoquchenggong: "

                                f"rows={len(df)}, elapsed={elapsed:.2f}s"

                            )

                            return df, fetcher.name

                    except Exception as e:

                        error_type, error_reason = summarize_exception(e)

                        error_msg = f"[{fetcher.name}] ({error_type}) {error_reason}"

                        logger.warning(

                            f"[shujuyuanshibai {attempt}/{total_fetchers}] [{fetcher.name}] {stock_code}: "

                            f"error_type={error_type}, reason={error_reason}"

                        )

                        errors.append(error_msg)

                    break



            error_summary = f"{market_label} {stock_code} huoqushibai:\n" + "\n".join(errors)

            elapsed = time.time() - request_start

            logger.error(f"[shujuyuanzhongzhi] {stock_code} huoqushibai: elapsed={elapsed:.2f}s\n{error_summary}")

            raise DataFetchError(error_summary)



        for attempt, fetcher in enumerate(fetchers, start=1):

            try:

                logger.info(f"[shujuyuanchangshi {attempt}/{total_fetchers}] [{fetcher.name}] huoqu {stock_code}...")

                df = self._call_fetcher_method(

                    fetcher,

                    "get_daily_data",

                    stock_code=stock_code,

                    start_date=start_date,

                    end_date=end_date,

                    days=days

                )

                

                if df is not None and not df.empty:

                    elapsed = time.time() - request_start

                    logger.info(

                        f"[shujuyuanwancheng] {stock_code} shiyong [{fetcher.name}] huoquchenggong: "

                        f"rows={len(df)}, elapsed={elapsed:.2f}s"

                    )

                    return df, fetcher.name

                    

            except Exception as e:

                error_type, error_reason = summarize_exception(e)

                error_msg = f"[{fetcher.name}] ({error_type}) {error_reason}"

                logger.warning(

                    f"[shujuyuanshibai {attempt}/{total_fetchers}] [{fetcher.name}] {stock_code}: "

                    f"error_type={error_type}, reason={error_reason}"

                )

                errors.append(error_msg)

                if attempt < total_fetchers:

                    next_fetcher = fetchers[attempt]

                    logger.info(f"[shujuyuanqiehuan] {stock_code}: [{fetcher.name}] -> [{next_fetcher.name}]")

                # jixuchangshixiayigeshujuyuan

                continue

        

        # suoyoushujuyuandoushibai

        error_summary = f"suoyoushujuyuanhuoqu {stock_code} shibai:\n" + "\n".join(errors)

        elapsed = time.time() - request_start

        logger.error(f"[shujuyuanzhongzhi] {stock_code} huoqushibai: elapsed={elapsed:.2f}s\n{error_summary}")

        raise DataFetchError(error_summary)

    

    @property

    def available_fetchers(self) -> List[str]:

        """사용 가능한 데이터 소스 이름 목록 반환"""

        return [f.name for f in self._get_fetchers_snapshot()]

    

    def prefetch_realtime_quotes(self, stock_codes: List[str]) -> int:

        """

        piliangyuqushishixingqingshuju(zaifenxikaishiqiandiaoyong)

        

        celve:

        1. jianchayouxianjizhongshifoubaohanquanlianglaqushujuyuan(efinance/akshare_em)

        2. ruguobubaohan,tiaoguoyuqu(xinlang/tengxunshi~인 경우upiaochaxun,wuxuyuqu)

        3. ruguozixuangushuliang >= 5 qie사용quanliangshujuyuan,zeyuqutianchonghuancun

        

        zheyangzuodehaochu:

        - 사용xinlang/tengxunshi:meizhigupiaodulichaxun,wuquanlianglaquwenti

        - 사용 efinance/dongcaishi:yuquyici,houxuhuancunmingzhong

        

        Args:

            stock_codes: daifenxide주식 코드목록

            

        Returns:

            yuqudegupiaoshuliang(0 biaoshitiaoguoyuqu)

        """



































        # Normalize all codes

        stock_codes = [normalize_stock_code(c) for c in stock_codes]



        from src.config import get_config



        config = get_config()



        # Issue #455: PREFETCH_REALTIME_QUOTES=false kejinyongyuqu,bimianquanshichanglaqu

        if not getattr(config, "prefetch_realtime_quotes", True):

            logger.debug("[yuqu] PREFETCH_REALTIME_QUOTES=false,tiaoguopiliangyuqu")

            return 0



        # ruguoshishixingqingbeijinyong,tiaoguoyuqu

        if not config.enable_realtime_quote:

            logger.debug("[yuqu] shishixingqinggongnengyijinyong,tiaoguoyuqu")

            return 0

        

        # jianchayouxianjizhongshifoubaohanquanlianglaqushujuyuan

        # zhuyi:xinzengquanliangjiekou(ru tushare_realtime)shixutongbugengxinciliebiao

        # quanliangjiekoutezheng:yici API diaoyonglaququanshichang 5000+ gupiaoshuju

        priority = config.realtime_source_priority.lower()

        bulk_sources = ['efinance', 'akshare_em', 'tushare']  # quanliangjiekouliebiao

        

        # ruguoyouxianjizhongqianlianggedoubushiquanliangshujuyuan,tiaoguoyuqu

        # yinweixinlang/tengxunshidangupiaochaxun,buxuyaoyuqu

        priority_list = [s.strip() for s in priority.split(',')]

        first_bulk_source_index = None

        for i, source in enumerate(priority_list):

            if source in bulk_sources:

                first_bulk_source_index = i

                break

        

        # ruguomeiyouquanliangshujuyuan,huozhequanliangshujuyuanpaizaidi 3 weizhihou,tiaoguoyuqu

        if first_bulk_source_index is None or first_bulk_source_index >= 2:

            logger.info(f"[yuqu] dangqianyouxianjishiyongqingliangjishujuyuan(sina/tencent),wuxuyuqu")

            return 0

        

        # ruguogupiaoshuliangshaoyu 5 ge,bujinxingpiliangyuqu(zhugechaxungenggaoxiao)

        if len(stock_codes) < 5:

            logger.info(f"[yuqu] gupiaoshuliang {len(stock_codes)} < 5,tiaoguopiliangyuqu")

            return 0

        

        logger.info(f"[yuqu] kaishipiliangyuqushishixingqing,gong {len(stock_codes)} zhigupiao...")

        

        # changshitongguo efinance huo akshare yuqu

        # zhixuyaodiaoyongyici get_realtime_quote,huancunjizhihuizidonglaququanshichangshuju

        try:

            # yongdiyizhigupiaochufaquanlianglaqu

            first_code = stock_codes[0]

            quote = self.get_realtime_quote(first_code)

            

            if quote:

                logger.info(f"[yuqu] piliangyuquwancheng,huancunyitianchong")

                return len(stock_codes)

            else:

                logger.warning(f"[yuqu] piliangyuqushibai,jiangshiyongzhugechaxunmoshi")

                return 0

                

        except Exception as e:

            logger.error(f"[yuqu] piliangyuquyichang: {e}")

            return 0

    

    def get_realtime_quote(self, stock_code: str, *, log_final_failure: bool = True):

        """

        huoqushishixingqingshuju(zidongguzhang전환)

        

        guzhang전환celve(anpeizhideyouxianji):

        1. 미국:사용 YfinanceFetcher.get_realtime_quote()

        2. EfinanceFetcher.get_realtime_quote()

        3. AkshareFetcher.get_realtime_quote(source="em")  - dongcai

        4. AkshareFetcher.get_realtime_quote(source="sina") - xinlang

        5. AkshareFetcher.get_realtime_quote(source="tencent") - tengxun

        6. 반환 None(jiangjidoudi)

        

        Args:

            stock_code: 주식 코드

            log_final_failure: Whether to emit the final "all sources failed"

                summary log when no realtime quote is available.

            

        Returns:

            UnifiedRealtimeQuote duixiang,suoyoushujuyuandoushibaizefanhui None

        """





































        raw_stock_code = (stock_code or "").strip()

        # Normalize code (strip SH/SZ prefix etc.)

        stock_code = normalize_stock_code(stock_code)



        from .akshare_fetcher import _is_us_code

        from .us_index_mapping import is_us_index_code

        from src.config import get_config



        config = get_config()



        # ruguoshishixingqinggongnengbeijinyong,zhijiefanhui None

        if not config.enable_realtime_quote:

            logger.debug(f"[shishixingqing] gongnengyijinyong,tiaoguo {stock_code}")

            return None



        # ----------------------------------------------------------

        # meigu (zhishu + gegu) / ganggu — zhuanyongshuangyuanluyou

        #   peizhizhangqiaohou: Longbridge shouxuan, YFinance/AkShare buchong

        #   weipeizhizhangqiao: YFinance/AkShare shouxuan, Longbridge buchong

        #   meiguzhishu:   shizhong YFinance shouxuan(Longbridge butigongzhishuhangqing)

        # ----------------------------------------------------------

        is_us_index = is_us_index_code(stock_code)

        is_us = is_us_index or _is_us_code(stock_code)

        is_hk = (not is_us) and _is_hk_market(stock_code)



        if is_us or is_hk:

            prefer_lb = self._longbridge_preferred() and not is_us_index

            if is_us:

                primary_src = "LongbridgeFetcher" if prefer_lb else "YfinanceFetcher"

                secondary_src = "YfinanceFetcher" if prefer_lb else "LongbridgeFetcher"

                market_label = "meiguzhishu" if is_us_index else "meigu"

                primary_kw: dict = {}

                secondary_kw: dict = {}

            else:

                primary_src = "LongbridgeFetcher" if prefer_lb else "AkshareFetcher"

                secondary_src = "AkshareFetcher" if prefer_lb else "LongbridgeFetcher"

                market_label = "ganggu"

                primary_kw = {"source": "hk"} if primary_src == "AkshareFetcher" else {}

                secondary_kw = {"source": "hk"} if secondary_src == "AkshareFetcher" else {}



            primary_quote = self._try_fetcher_quote(stock_code, primary_src, **primary_kw)

            if primary_quote is not None:

                logger.info(f"[shishixingqing] {market_label} {stock_code} chenggonghuoqu (laiyuan: {primary_src})")

            primary_quote = self._supplement_quote(

                stock_code, primary_quote, secondary_src, **secondary_kw,

            )

            # meigugegu(feizhishu)changshicong Finnhub/AlphaVantage buchongqueshiziduan

            if is_us and not is_us_index and primary_quote is not None:

                for extra_src in ["FinnhubFetcher", "AlphaVantageFetcher"]:

                    primary_quote = self._supplement_quote(

                        stock_code, primary_quote, extra_src,

                    )

            if primary_quote is not None:

                return primary_quote

            if log_final_failure:

                logger.info(f"[shishixingqing] {market_label} {stock_code} wukeyongshujuyuan")

            return None

        

        # huoqupeizhideshujuyuanyouxianji

        source_priority = config.realtime_source_priority.split(',')

        

        errors = []

        # primary_quote holds the first successful result; we may supplement

        # missing fields (volume_ratio, turnover_rate, etc.) from later sources.

        primary_quote = None

        

        for source in source_priority:

            source = source.strip().lower()

            

            try:

                quote = None

                

                if source == "efinance":

                    fetcher = self._get_fetcher_by_name("EfinanceFetcher", capability="realtime_quote")

                    if fetcher is not None and hasattr(fetcher, 'get_realtime_quote'):

                        quote = self._call_fetcher_method(fetcher, 'get_realtime_quote', stock_code)

                

                elif source == "akshare_em":

                    fetcher = self._get_fetcher_by_name("AkshareFetcher", capability="realtime_quote")

                    if fetcher is not None and hasattr(fetcher, 'get_realtime_quote'):

                        quote = self._call_fetcher_method(fetcher, 'get_realtime_quote', stock_code, source="em")

                

                elif source == "akshare_sina":

                    fetcher = self._get_fetcher_by_name("AkshareFetcher", capability="realtime_quote")

                    if fetcher is not None and hasattr(fetcher, 'get_realtime_quote'):

                        quote = self._call_fetcher_method(fetcher, 'get_realtime_quote', stock_code, source="sina")

                

                elif source in ("tencent", "akshare_qq"):

                    fetcher = self._get_fetcher_by_name("AkshareFetcher", capability="realtime_quote")

                    if fetcher is not None and hasattr(fetcher, 'get_realtime_quote'):

                        quote = self._call_fetcher_method(fetcher, 'get_realtime_quote', stock_code, source="tencent")

                

                elif source == "tushare":

                    fetcher = self._get_fetcher_by_name("TushareFetcher", capability="realtime_quote")

                    if fetcher is not None and hasattr(fetcher, 'get_realtime_quote'):

                        quote = self._call_fetcher_method(fetcher, 'get_realtime_quote', raw_stock_code or stock_code)

                

                if quote is not None and quote.has_basic_data():

                    if primary_quote is None:

                        # First successful source becomes primary

                        primary_quote = quote

                        logger.info(f"[shishixingqing] {stock_code} chenggonghuoqu (laiyuan: {source})")

                        # If all key supplementary fields are present, return early

                        if not self._quote_needs_supplement(primary_quote):

                            return primary_quote

                        # Otherwise, continue to try later sources for missing fields

                        logger.debug(f"[shishixingqing] {stock_code} bufenziduanqueshi,changshiconghouxushujuyuanbuchong")

                        supplement_attempts = 0

                    else:

                        # Supplement missing fields from this source (limit attempts)

                        supplement_attempts += 1

                        if supplement_attempts > 1:

                            logger.debug(f"[shishixingqing] {stock_code} buchongchangshiyidashangxian,tingzhijixu")

                            break

                        merged = self._merge_quote_fields(primary_quote, quote)

                        if merged:

                            logger.info(f"[shishixingqing] {stock_code} cong {source} buchonglequeshiziduan: {merged}")

                        # Stop supplementing once all key fields are filled

                        if not self._quote_needs_supplement(primary_quote):

                            break

                    

            except Exception as e:

                error_msg = f"[{source}] shibai: {str(e)}"

                logger.info(f"[shishixingqing] {stock_code} {error_msg},jixuchangshixiayigeshujuyuan")

                errors.append(error_msg)

                continue

        

        # Return primary even if some fields are still missing

        if primary_quote is not None:

            return primary_quote



        # suoyoushujuyuandoushibai,fanhui None(jiangjidoudi)

        if log_final_failure:

            if errors:

                logger.info(f"[shishixingqing] {stock_code} suoyoushujuyuanjunshibai: {'; '.join(errors)}")

            else:

                logger.info(f"[shishixingqing] {stock_code} wukeyongshujuyuan")



        return None



    # Fields worth supplementing from secondary sources when the primary

    # source returns None for them. Ordered by importance.

    _SUPPLEMENT_FIELDS = [

        'volume_ratio', 'turnover_rate',

        'pe_ratio', 'pb_ratio', 'total_mv', 'circ_mv',

        'amplitude',

    ]



    @classmethod

    def _quote_needs_supplement(cls, quote) -> bool:

        """Check if any key supplementary field is still None."""

        for f in cls._SUPPLEMENT_FIELDS:

            if getattr(quote, f, None) is None:

                return True

        return False



    @classmethod

    def _merge_quote_fields(cls, primary, secondary) -> list:

        """

        Copy non-None fields from *secondary* into *primary* where

        *primary* has None. Returns list of field names that were filled.

        """

        filled = []

        for f in cls._SUPPLEMENT_FIELDS:

            if getattr(primary, f, None) is None:

                val = getattr(secondary, f, None)

                if val is not None:

                    setattr(primary, f, val)

                    filled.append(f)

        return filled



    def _longbridge_preferred(self, capability: str = "realtime_quote") -> bool:

        """Return True when Longbridge keys are configured and available.



        When True, non-A-share routing (US & HK) uses Longbridge as the

        primary data source with Yfinance/AkShare as fallback.

        """

        return self._get_fetcher_by_name(

            "LongbridgeFetcher",

            capability=capability,

        ) is not None



    def _try_fetcher_quote(self, stock_code: str, fetcher_name: str, **kw):

        """Try to get a realtime quote from a named fetcher; returns quote or None."""

        fetcher = self._get_fetcher_by_name(fetcher_name, capability="realtime_quote")

        if fetcher is None or not hasattr(fetcher, 'get_realtime_quote'):

            return None

        try:

            q = self._call_fetcher_method(fetcher, 'get_realtime_quote', stock_code, **kw)

            if q is not None and q.has_basic_data():

                return q

        except Exception as e:

            logger.debug(f"[shishixingqing] {stock_code} {fetcher_name} huoqushibai: {e}")

        return None



    def _supplement_quote(self, stock_code: str, primary_quote, fetcher_name: str, **kw):

        """Supplement *primary_quote* with data from *fetcher_name*.



        If *primary_quote* is None, try *fetcher_name* as the sole source.

        Returns the (potentially enriched) quote, or None.

        """

        if primary_quote is not None:

            if not self._quote_needs_supplement(primary_quote):

                return primary_quote

            try:

                secondary = self._try_fetcher_quote(stock_code, fetcher_name, **kw)

                if secondary is not None:

                    filled = self._merge_quote_fields(primary_quote, secondary)

                    if filled:

                        logger.info(f"[shishixingqing] {stock_code} cong {fetcher_name} buchongle: {filled}")

            except Exception as e:

                logger.debug(f"[shishixingqing] {stock_code} {fetcher_name} buchongshibai: {e}")

            return primary_quote



        q = self._try_fetcher_quote(stock_code, fetcher_name, **kw)

        if q is not None:

            logger.info(f"[shishixingqing] {stock_code} cong {fetcher_name} huoquchenggong (dulishujuyuan)")

        return q



    def _supplement_from_longbridge(self, stock_code: str, primary_quote):

        """Shortcut kept for backward-compat with A-share general loop."""

        return self._supplement_quote(stock_code, primary_quote, "LongbridgeFetcher")



    def get_chip_distribution(self, stock_code: str):

        """

        huoquchoumafenbushuju(dairongduanheduoshujuyuanjiangji)



        celve:

        1. jianchapeizhikaiguan

        2. jiancharongduanqizhuangtai

        3. yicichangshiduogeshujuyuan:shujuyuanyouxianjiyuhuoqudaily의 데이터youxianjiyizhi

        4. suoyoushujuyuanshibaizefanhui None(jiangjidoudi)



        Args:

            stock_code: 주식 코드



        Returns:

            ChipDistribution duixiang,shibaizefanhui None

        """





























        # Normalize code (strip SH/SZ prefix etc.)

        stock_code = normalize_stock_code(stock_code)



        from .realtime_types import get_chip_circuit_breaker

        from src.config import get_config



        config = get_config()



        # ruguochoumafenbugongnengbeijinyong,zhijiefanhui None

        if not config.enable_chip_distribution:

            logger.debug(f"[choumafenbu] gongnengyijinyong,tiaoguo {stock_code}")

            return None



        circuit_breaker = get_chip_circuit_breaker()



        # zhijiebianliguanliqiyijingan priority paihaoxudeshujuyuanliebiao

        for fetcher in self._get_fetchers_snapshot():

            # zhichulishixianlechoumafenbuluojideshujuyuan

            if not hasattr(fetcher, 'get_chip_distribution'):

                continue

            

            fetcher_name = fetcher.name

            # dongtaishengchengrongduanqide key,liru "TushareFetcher" -> "tushare_chip"

            source_key = f"{fetcher_name.replace('Fetcher', '').lower()}_chip"



            # jiancharongduanqizhuangtai

            if not circuit_breaker.is_available(source_key):

                logger.debug(f"[rongduan] {fetcher_name} choumajiekouchuyurongduanzhuangtai,changshixiayige")

                continue



            try:

                chip = self._call_fetcher_method(fetcher, 'get_chip_distribution', stock_code)

                if chip is not None:

                    circuit_breaker.record_success(source_key)

                    logger.info(f"[choumafenbu] {stock_code} chenggonghuoqu (laiyuan: {fetcher_name})")

                    return chip

                else:

                    # kongjieguo:shifang HALF_OPEN tanceminge,bimiankasi

                    circuit_breaker.record_inconclusive(source_key)

            except Exception as e:

                logger.warning(f"[choumafenbu] {fetcher_name} huoqu {stock_code} shibai: {e}")

                circuit_breaker.record_failure(source_key, str(e))

                continue



        logger.warning(f"[choumafenbu] {stock_code} suoyoushujuyuanjunshibai")

        return None



    def get_stock_name(self, stock_code: str, allow_realtime: bool = True) -> Optional[str]:

        """

        huoqugupiaozhongwenmingcheng(자동전환데이터 소스)

        

        changshicongduogeshujuyuanhuoqugupiaomingcheng:

        1. xiancongneicunhuancunzhonghuoqu(ruguoyou)

        2. zaichangshibendiweihuyingsheyu stocks.index.json suoyin

        3. ranhouanxuchaxunshishixingqing

        4. yicichangshigegeshujuyuande get_stock_name 메서드

        

        Args:

            stock_code: 주식 코드

            allow_realtime: Whether to query realtime quote first. Set False when

                caller only wants lightweight prefetch without triggering heavy

                realtime source calls.

            

        Returns:

            gupiaozhongwenmingcheng,suoyoushujuyuandoushibaizefanhui None

        """



































        raw_stock_code = (stock_code or "").strip()

        # Normalize code (strip SH/SZ prefix etc.)

        stock_code = normalize_stock_code(stock_code)

        static_name = STOCK_NAME_MAP.get(stock_code)



        # 1. xianjianchahuancun

        cached_name = self._get_cached_stock_name(stock_code)

        if cached_name is not None:

            return cached_name

        

        if is_meaningful_stock_name(static_name, stock_code):

            return self._cache_stock_name(stock_code, static_name) or static_name



        index_name = get_index_stock_name(stock_code)

        if is_meaningful_stock_name(index_name, stock_code):

            return self._cache_stock_name(stock_code, index_name) or index_name



        # 2. changshicongshishixingqingzhonghuoqu(zuikuai,keanxujinyong)

        if allow_realtime:

            quote = self.get_realtime_quote(raw_stock_code or stock_code, log_final_failure=False)

            if quote and hasattr(quote, 'name') and is_meaningful_stock_name(getattr(quote, 'name', ''), stock_code):

                name = quote.name

                self._cache_stock_name(stock_code, name)

                logger.info(f"[gupiaomingcheng] congshishixingqinghuoqu: {stock_code} -> {name}")

                return name



        # 3. yicichangshigegeshujuyuan

        from .akshare_fetcher import _is_us_code

        is_us = _is_us_code(stock_code)

        _US_CAPABLE_FETCHERS = {"YfinanceFetcher", "LongbridgeFetcher", "FinnhubFetcher", "AlphaVantageFetcher"}

        for fetcher in self._get_fetchers_snapshot():

            if not hasattr(fetcher, 'get_stock_name'):

                continue

            if is_us and fetcher.name not in _US_CAPABLE_FETCHERS:

                continue

            if not self._is_fetcher_available(fetcher, capability="stock_name"):

                continue

            try:

                name = self._call_fetcher_method(fetcher, 'get_stock_name', stock_code)

                if is_meaningful_stock_name(name, stock_code):

                    self._cache_stock_name(stock_code, name)

                    logger.info(f"[gupiaomingcheng] cong {fetcher.name} huoqu: {stock_code} -> {name}")

                    return name

            except Exception as e:

                logger.debug(f"[gupiaomingcheng] {fetcher.name} huoqushibai: {e}")

                continue



        # 4. suoyoushujuyuandoushibai

        logger.warning(f"[gupiaomingcheng] suoyoushujuyuandouwufahuoqu {stock_code} demingcheng")

        return ""



    def get_belong_boards(self, stock_code: str) -> List[Dict[str, Any]]:

        """

        Get stock membership boards through capability probing.



        Keep this at manager layer to avoid changing BaseFetcher abstraction.

        """

        stock_code = normalize_stock_code(stock_code)

        if _market_tag(stock_code) != "cn":

            return []

        for fetcher in self._fetchers:

            if not hasattr(fetcher, "get_belong_board"):

                continue

            try:

                raw_data = fetcher.get_belong_board(stock_code)

                boards = self._normalize_belong_boards(raw_data)

                if boards:

                    logger.info(f"[{fetcher.name}] huoqusuoshubankuaichenggong: {stock_code}, count={len(boards)}")

                    return boards

            except Exception as e:

                logger.debug(f"[{fetcher.name}] huoqusuoshubankuaishibai: {e}")

                continue

        return []



    def prefetch_stock_names(self, stock_codes: List[str], use_bulk: bool = False) -> None:

        """

        Pre-fetch stock names into cache before parallel analysis (Issue #455).



        When use_bulk=False, only calls get_stock_name per code (no get_stock_list),

        avoiding full-market fetch. Sequential execution to avoid rate limits.



        Args:

            stock_codes: Stock codes to prefetch.

            use_bulk: If True, may use get_stock_list (full fetch). Default False.

        """

        if not stock_codes:

            return

        stock_codes = [normalize_stock_code(c) for c in stock_codes]

        if use_bulk:

            self.batch_get_stock_names(stock_codes)

            return

        for code in stock_codes:

            # Skip realtime lookup to avoid triggering expensive full-market quote

            # requests during the prefetch phase.

            self.get_stock_name(code, allow_realtime=False)



    def batch_get_stock_names(self, stock_codes: List[str]) -> Dict[str, str]:

        """

        pilianghuoqugupiaozhongwenmingcheng

        

        xianchangshicongzhichipiliangchaxun의 데이터yuanhuoqugupiaoliebiao,

        ranhouzaizhugechaxunqueshidegupiaomingcheng。

        

        Args:

            stock_codes: 주식 코드목록

            

        Returns:

            {주식 코드: gupiaomingcheng} zidian

        """























        result = {}

        missing_codes = set(stock_codes)

        

        # 1. xianjianchahuancun

        self._ensure_concurrency_guards()

        with self._stock_name_cache_lock:

            for code in stock_codes:

                cached_name = self._stock_name_cache.get(code)

                if cached_name is not None:

                    result[code] = cached_name

                    missing_codes.discard(code)

        

        if not missing_codes:

            return result

        

        # 2. changshipilianghuoqugupiaoliebiao

        for fetcher in self._get_fetchers_snapshot():

            if not hasattr(fetcher, 'get_stock_list') or not missing_codes:

                continue

            if not self._is_fetcher_available(fetcher, capability="stock_list"):

                continue

            try:

                stock_list = self._call_fetcher_method(fetcher, 'get_stock_list')

                if stock_list is not None and not stock_list.empty:

                    cache_updates: Dict[str, str] = {}

                    for _, row in stock_list.iterrows():

                        code = row.get('code')

                        name = row.get('name')

                        if code and name:

                            cache_updates[code] = name

                            if code in missing_codes:

                                result[code] = name

                                missing_codes.discard(code)



                    if cache_updates:

                        with self._stock_name_cache_lock:

                            self._stock_name_cache.update(cache_updates)

                    

                    if not missing_codes:

                        break

                    

                    logger.info(f"[gupiaomingcheng] cong {fetcher.name} pilianghuoquwancheng,shengyu {len(missing_codes)} gedaicha")

            except Exception as e:

                logger.debug(f"[gupiaomingcheng] {fetcher.name} pilianghuoqushibai: {e}")

                continue

        

        # 3. zhugehuoqushengyude

        for code in list(missing_codes):

            name = self.get_stock_name(code)

            if name:

                result[code] = name

                missing_codes.discard(code)

        

        logger.info(f"[gupiaomingcheng] pilianghuoquwancheng,chenggong {len(result)}/{len(stock_codes)}")

        return result



    def get_main_indices(self, region: str = "cn") -> List[Dict[str, Any]]:

        """주요 지수 실시 현황 조회(자동전환데이터 소스)"""

        if region == "cn":

            tickflow_fetcher = self._get_tickflow_fetcher()

            if tickflow_fetcher is not None:

                try:

                    data = tickflow_fetcher.get_main_indices(region=region)

                    if data:

                        logger.info("[TickFlowFetcher] huoquzhishuhangqingchenggong")

                        return data

                except Exception as e:

                    logger.warning(f"[TickFlowFetcher] huoquzhishuhangqingshibai: {e}")



        for fetcher in self._fetchers:

            try:

                data = fetcher.get_main_indices(region=region)

                if data:

                    logger.info(f"[{fetcher.name}] huoquzhishuhangqingchenggong")

                    return data

            except Exception as e:

                logger.warning(f"[{fetcher.name}] huoquzhishuhangqingshibai: {e}")

                continue

        return []



    def get_market_stats(self) -> Dict[str, Any]:

        """시장 등락/하락 통계 조회(자동전환데이터 소스)"""

        tickflow_fetcher = self._get_tickflow_fetcher()

        if tickflow_fetcher is not None:

            try:

                data = tickflow_fetcher.get_market_stats()

                if data:

                    logger.info("[TickFlowFetcher] huoqushichangtongjichenggong")

                    return data

            except Exception as e:

                logger.warning(f"[TickFlowFetcher] huoqushichangtongjishibai: {e}")



        for fetcher in self._fetchers:

            try:

                data = fetcher.get_market_stats()

                if data:

                    logger.info(f"[{fetcher.name}] huoqushichangtongjichenggong")

                    return data

            except Exception as e:

                logger.warning(f"[{fetcher.name}] huoqushichangtongjishibai: {e}")

                continue

        return {}



    def _run_with_timeout(

        self,

        task: Callable[[], Any],

        timeout_seconds: float,

        task_name: str,

    ) -> Tuple[Optional[Any], Optional[str], int]:

        """

        Execute a task in a short-lived thread and enforce a timeout.



        Returns:

            (result, error, duration_ms)

        """

        start = time.time()

        timeout_value = max(0.0, timeout_seconds)

        if timeout_value <= 0:

            return None, f"{task_name} timeout", 0

        result_holder: Dict[str, Any] = {}

        error_holder: Dict[str, Exception] = {}



        if not self._fundamental_timeout_slots.acquire(blocking=False):

            return None, f"{task_name} timeout worker pool exhausted", int(timeout_value * 1000)



        def runner() -> None:

            try:

                result_holder["value"] = task()

            except Exception as exc:

                error_holder["value"] = exc

            finally:

                try:

                    self._fundamental_timeout_slots.release()

                except ValueError:

                    pass



        worker = Thread(target=runner, daemon=True, name=f"fundamental-{task_name}")

        try:

            worker.start()

        except Exception as exc:

            try:

                self._fundamental_timeout_slots.release()

            except ValueError:

                pass

            return None, str(exc), int((time.time() - start) * 1000)

        worker.join(timeout=timeout_value)

        if worker.is_alive():

            return None, f"{task_name} timeout", int(timeout_value * 1000)

        if "value" in error_holder:

            return None, str(error_holder["value"]), int((time.time() - start) * 1000)

        return result_holder.get("value"), None, int((time.time() - start) * 1000)



    def _run_with_retry(

        self,

        task: Callable[[], Any],

        timeout_seconds: float,

        task_name: str,

    ) -> Tuple[Optional[Any], Optional[str], int]:

        """

        Execute a task with bounded budget and best-effort retries.



        Returns:

            (result, error, total_duration_ms)

        """

        config = self._get_fundamental_config()

        attempts = max(1, int(config.fundamental_retry_max))

        remaining_seconds = max(0.0, float(timeout_seconds))

        total_cost_ms = 0

        last_error: Optional[str] = None



        for _ in range(attempts):

            if remaining_seconds <= 0:

                break

            result, err, cost_ms = self._run_with_timeout(task, remaining_seconds, task_name)

            total_cost_ms += cost_ms

            remaining_seconds = max(0.0, remaining_seconds - cost_ms / 1000)

            if err is None:

                return result, None, total_cost_ms

            last_error = err

            if remaining_seconds <= 0:

                break



        return None, last_error, total_cost_ms



    def _get_fundamental_config(self):

        from src.config import get_config

        return get_config()



    @staticmethod

    def _normalize_source_chain(

        entries: Any,

        provider: str,

        result: str,

        duration_ms: int,

    ) -> List[Dict[str, Any]]:

        """Normalize free-form source chain entries to structured dict list."""

        if entries is None:

            return [{"provider": provider, "result": result, "duration_ms": duration_ms}]



        normalized: List[Dict[str, Any]] = []

        if not isinstance(entries, (list, tuple)):

            entries = [entries]



        for item in entries:

            if isinstance(item, dict):

                normalized.append({

                    "provider": str(item.get("provider") or provider),

                    "result": str(item.get("result") or result),

                    "duration_ms": int(item.get("duration_ms", duration_ms)),

                })

                continue



            if item is None:

                continue



            provider_name = str(item)

            normalized.append({

                "provider": provider_name,

                "result": result,

                "duration_ms": duration_ms,

            })



        if not normalized:

            return [{"provider": provider, "result": result, "duration_ms": duration_ms}]



        return normalized



    @staticmethod

    def _block_status(payload: Dict[str, Any], available: bool = True) -> str:

        if not available:

            return "not_supported"

        if not payload:

            return "partial"

        return "ok"



    @staticmethod

    def _build_fundamental_block(

        status: str,

        payload: Optional[Dict[str, Any]] = None,

        source_chain: Optional[List[Dict[str, Any]]] = None,

        errors: Optional[List[str]] = None,

    ) -> Dict[str, Any]:

        return {

            "status": status,

            "coverage": {"status": status},

            "source_chain": source_chain or [],

            "errors": errors or [],

            "data": payload or {},

        }



    @staticmethod

    def _has_meaningful_payload(payload: Any) -> bool:

        if payload is None:

            return False

        if isinstance(payload, str):

            normalized = payload.strip().lower()

            return normalized not in ("", "-", "nan", "none", "null", "n/a", "na")

        if isinstance(payload, dict):

            return any(DataFetcherManager._has_meaningful_payload(v) for v in payload.values())

        if isinstance(payload, pd.DataFrame):

            if payload.empty:

                return False

            return any(

                DataFetcherManager._has_meaningful_payload(v)

                for v in payload.to_numpy().flat

            )

        if isinstance(payload, (pd.Series, pd.Index)):

            return any(DataFetcherManager._has_meaningful_payload(v) for v in payload.tolist())

        if isinstance(payload, np.ndarray):

            if payload.ndim == 0:

                payload = payload.item()

            else:

                return any(

                    DataFetcherManager._has_meaningful_payload(v)

                    for v in payload.flat

                )

        if isinstance(payload, (list, tuple, set)):

            return any(DataFetcherManager._has_meaningful_payload(v) for v in payload)

        if DataFetcherManager._try_scalar_isna(payload, "fundamental_payload") is True:

            return False

        return True



    @staticmethod

    def _infer_block_status(payload: Any, fallback_status: str) -> str:

        if DataFetcherManager._has_meaningful_payload(payload):

            return "ok"

        if fallback_status in ("failed", "partial", "not_supported"):

            return fallback_status

        return "partial"



    @staticmethod

    def _should_cache_fundamental_context(context: Any) -> bool:

        if not isinstance(context, dict):

            return False

        status = str(context.get("status", "")).strip().lower()

        if status == "ok":

            return True

        if status == "failed":

            return False

        for block in (

            "valuation",

            "growth",

            "earnings",

            "institution",

            "capital_flow",

            "dragon_tiger",

            "boards",

        ):

            payload = context.get(block, {})

            if isinstance(payload, dict) and DataFetcherManager._has_meaningful_payload(payload.get("data")):

                return True

        return False



    def _build_market_not_supported(self, market: str, reason: str) -> Dict[str, Any]:

        blocks = {

            "valuation": self._build_fundamental_block(

                "partial" if market == "etf" else "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                [reason],

            ),

            "growth": self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                [reason],

            ),

            "earnings": self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                [reason],

            ),

            "institution": self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                [reason],

            ),

            "capital_flow": self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                [reason],

            ),

            "dragon_tiger": self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                [reason],

            ),

            "boards": self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                [reason],

            ),

        }

        return {

            "market": market,

            "status": "partial" if market == "etf" else "not_supported",

            "coverage": {

                block: blocks[block]["status"] for block in blocks

            },

            "source_chain": [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

            "errors": [reason],

            **blocks,

        }



    def build_failed_fundamental_context(self, stock_code: str, reason: str) -> Dict[str, Any]:

        """Build a consistent failed-context payload for caller-side fallback."""

        market = _market_tag(stock_code)

        block_names = (

            "valuation",

            "growth",

            "earnings",

            "institution",

            "capital_flow",

            "dragon_tiger",

            "boards",

        )

        blocks = {

            block: self._build_fundamental_block(

                "failed",

                {},

                [{"provider": "fundamental_pipeline", "result": "failed", "duration_ms": 0}],

                [reason],

            )

            for block in block_names

        }

        return {

            "market": market,

            "status": "failed",

            "coverage": {block: "failed" for block in block_names},

            "source_chain": [{"provider": "fundamental_pipeline", "result": "failed", "duration_ms": 0}],

            "errors": [reason],

            **blocks,

        }



    def get_fundamental_context(

        self,

        stock_code: str,

        budget_seconds: Optional[float] = None

    ) -> Dict[str, Any]:

        """

        Aggregate fundamental blocks with fail-open semantics.

        """

        from src.config import get_config



        config = get_config()

        if not config.enable_fundamental_pipeline:

            return self._build_market_not_supported(

                market=_market_tag(stock_code),

                reason="fundamental pipeline disabled",

            )



        stock_code = normalize_stock_code(stock_code)

        market = _market_tag(stock_code)

        is_etf = _is_etf_code(stock_code)

        if market in {"us", "hk"}:

            return self._build_market_not_supported(

                market=market,

                reason="market not supported",

            )



        stage_timeout = float(

            budget_seconds if budget_seconds is not None else config.fundamental_stage_timeout_seconds

        )

        stage_timeout = max(0.0, stage_timeout)

        fetch_timeout = float(config.fundamental_fetch_timeout_seconds)

        fetch_timeout = max(0.0, fetch_timeout)



        cache_ttl = int(config.fundamental_cache_ttl_seconds)

        cache_max_entries = max(0, int(getattr(config, "fundamental_cache_max_entries", 256)))

        cache_key = self._get_fundamental_cache_key(stock_code, stage_timeout)

        if cache_ttl > 0:

            self._prune_fundamental_cache(cache_ttl, cache_max_entries)

            with self._fundamental_cache_lock:

                cache_item = self._fundamental_cache.get(cache_key)

                if cache_item:

                    age = time.time() - float(cache_item.get("ts", 0))

                    if age <= cache_ttl:

                        return cache_item.get("context", {})



        remaining_seconds = stage_timeout

        result_ctx: Dict[str, Any] = {

            "market": market,

            "valuation": {},

            "growth": {},

            "earnings": {},

            "institution": {},

            "capital_flow": {},

            "dragon_tiger": {},

            "boards": {},

            "coverage": {},

            "source_chain": [],

            "errors": [],

        }



        start_ts = time.time()



        def _consume_budget(consumed_ms: int) -> None:

            nonlocal remaining_seconds

            remaining_seconds = max(0.0, remaining_seconds - consumed_ms / 1000.0)



        valuation_timeout = min(fetch_timeout, remaining_seconds)

        if valuation_timeout > 0:

            quote_payload, valuation_err, valuation_ms = self._run_with_retry(

                lambda: self.get_realtime_quote(stock_code),

                valuation_timeout,

                "fundamental_valuation",

            )

            _consume_budget(valuation_ms)

        else:

            quote_payload, valuation_err, valuation_ms = None, "fundamental stage timeout", 0



        valuation_payload = {

            "pe_ratio": getattr(quote_payload, "pe_ratio", None) if quote_payload else None,

            "pb_ratio": getattr(quote_payload, "pb_ratio", None) if quote_payload else None,

            "total_mv": getattr(quote_payload, "total_mv", None) if quote_payload else None,

            "circ_mv": getattr(quote_payload, "circ_mv", None) if quote_payload else None,

        }

        valuation_status = self._infer_block_status(

            valuation_payload,

            "partial" if quote_payload is not None else "not_supported",

        )

        if valuation_status == "partial" and valuation_err and not self._has_meaningful_payload(valuation_payload):

            valuation_status = "failed"

        result_ctx["valuation"] = self._build_fundamental_block(

            valuation_status,

            valuation_payload,

            self._normalize_source_chain(

                [{"provider": "realtime_quote", "result": valuation_status, "duration_ms": valuation_ms}],

                "realtime_quote",

                valuation_status,

                valuation_ms,

            ),

            [valuation_err] if valuation_err else [],

        )



        # growth / earnings / institution (one AkShare call)

        if remaining_seconds <= 0:

            bundle_status = "failed"

            bundle_payload: Dict[str, Any] = {}

            bundle_errors = ["fundamental stage timeout"]

            bundle_ms = 0

        else:

            bundle_timeout = min(fetch_timeout, remaining_seconds)

            bundle_payload, bundle_err_msg, bundle_ms = self._run_with_retry(

                lambda: self._fundamental_adapter.get_fundamental_bundle(stock_code),

                bundle_timeout,

                "fundamental_bundle",

            )

            _consume_budget(bundle_ms)

            if not isinstance(bundle_payload, dict):

                bundle_status = "failed"

                bundle_payload = {}

                bundle_errors = ["fundamental_bundle failed"]

                if bundle_err_msg:

                    bundle_errors.append(bundle_err_msg)

            else:

                bundle_status = str(bundle_payload.get("status", "not_supported"))

                bundle_errors = [bundle_err_msg] if bundle_err_msg else []



        bundle_chain = self._normalize_source_chain(

            bundle_payload.get("source_chain", []),

            "fundamental_bundle",

            bundle_status,

            bundle_ms,

        ) if isinstance(bundle_payload, dict) else self._normalize_source_chain(

            None,

            "fundamental_bundle",

            bundle_status,

            bundle_ms,

        )

        growth_payload = bundle_payload.get("growth", {}) if isinstance(bundle_payload, dict) else {}

        earnings_payload = bundle_payload.get("earnings", {}) if isinstance(bundle_payload, dict) else {}

        institution_payload = bundle_payload.get("institution", {}) if isinstance(bundle_payload, dict) else {}

        if not isinstance(growth_payload, dict):

            growth_payload = {}

        else:

            growth_payload = dict(growth_payload)

        if not isinstance(earnings_payload, dict):

            earnings_payload = {}

        else:

            earnings_payload = dict(earnings_payload)

        if not isinstance(institution_payload, dict):

            institution_payload = {}

        else:

            institution_payload = dict(institution_payload)



        # Derive TTM dividend yield from already-fetched quote price; avoid extra quote calls.

        earnings_extra_errors: List[str] = []

        dividend_payload = earnings_payload.get("dividend")

        if isinstance(dividend_payload, dict):

            dividend_payload = dict(dividend_payload)

            ttm_cash_raw = dividend_payload.get("ttm_cash_dividend_per_share")

            ttm_cash = None

            if ttm_cash_raw is not None:

                try:

                    ttm_cash = float(ttm_cash_raw)

                except (TypeError, ValueError):

                    earnings_extra_errors.append("invalid_ttm_cash_dividend_per_share")

            if isinstance(quote_payload, dict):

                latest_price_raw = quote_payload.get("price")

            else:

                latest_price_raw = getattr(quote_payload, "price", None) if quote_payload else None

            latest_price = None

            if latest_price_raw is not None:

                try:

                    latest_price = float(latest_price_raw)

                except (TypeError, ValueError):

                    latest_price = None

            ttm_yield = None

            if ttm_cash is not None:

                if latest_price is not None and latest_price > 0:

                    ttm_yield = round(ttm_cash / latest_price * 100.0, 4)

                else:

                    earnings_extra_errors.append("invalid_price_for_ttm_dividend_yield")



            dividend_payload["ttm_dividend_yield_pct"] = ttm_yield

            if ttm_yield is not None:

                dividend_payload["yield_formula"] = "ttm_cash_dividend_per_share / latest_price * 100"

            earnings_payload["dividend"] = dividend_payload



        adapter_errors = list(bundle_payload.get("errors", [])) if isinstance(bundle_payload, dict) else []

        adapter_errors.extend(bundle_errors)

        growth_errors = list(adapter_errors)

        earnings_errors = list(adapter_errors)

        earnings_errors.extend(earnings_extra_errors)

        institution_errors = list(adapter_errors)



        growth_status = self._infer_block_status(growth_payload, bundle_status)

        earnings_status = self._infer_block_status(earnings_payload, bundle_status)

        institution_status = self._infer_block_status(institution_payload, bundle_status)



        result_ctx["growth"] = self._build_fundamental_block(

            growth_status,

            growth_payload,

            bundle_chain,

            growth_errors,

        )

        result_ctx["earnings"] = self._build_fundamental_block(

            earnings_status,

            earnings_payload,

            bundle_chain,

            earnings_errors,

        )

        result_ctx["institution"] = self._build_fundamental_block(

            institution_status,

            institution_payload,

            bundle_chain,

            institution_errors,

        )



        # capital flow

        if is_etf:

            result_ctx["capital_flow"] = self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                ["etf not fully supported"],

            )

            result_ctx["dragon_tiger"] = self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                ["etf not fully supported"],

            )

            result_ctx["boards"] = self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                ["etf not fully supported"],

            )

            result_ctx["status"] = "partial"

        else:

            capital_flow_budget = min(fetch_timeout, remaining_seconds)

            capital_flow_start = time.time()

            result_ctx["capital_flow"] = self.get_capital_flow_context(

                stock_code,

                budget_seconds=capital_flow_budget,

            )

            _consume_budget(int((time.time() - capital_flow_start) * 1000))



            dragon_tiger_budget = min(fetch_timeout, remaining_seconds)

            dragon_tiger_start = time.time()

            result_ctx["dragon_tiger"] = self.get_dragon_tiger_context(

                stock_code,

                budget_seconds=dragon_tiger_budget,

            )

            _consume_budget(int((time.time() - dragon_tiger_start) * 1000))



            result_ctx["boards"] = self.get_board_context(

                stock_code,

                budget_seconds=min(fetch_timeout, remaining_seconds),

            )



        block_statuses = {

            "valuation": result_ctx["valuation"].get("status", "not_supported"),

            "growth": result_ctx["growth"].get("status", "not_supported"),

            "earnings": result_ctx["earnings"].get("status", "not_supported"),

            "institution": result_ctx["institution"].get("status", "not_supported"),

            "capital_flow": result_ctx["capital_flow"].get("status", "not_supported"),

            "dragon_tiger": result_ctx["dragon_tiger"].get("status", "not_supported"),

            "boards": result_ctx["boards"].get("status", "not_supported"),

        }

        result_ctx["coverage"] = block_statuses

        for block in (

            "valuation",

            "growth",

            "earnings",

            "institution",

            "capital_flow",

            "dragon_tiger",

            "boards",

        ):

            result_ctx["errors"].extend(result_ctx[block].get("errors", []))

            result_ctx["source_chain"].extend(result_ctx[block].get("source_chain", []))



        if is_etf:

            # Keep ETF downgrade semantics for overall status even when valuation is available.

            result_ctx["status"] = (

                "not_supported" if all(value == "not_supported" for value in block_statuses.values()) else "partial"

            )

        elif all(value == "not_supported" for value in block_statuses.values()):

            result_ctx["status"] = "not_supported"

        elif "failed" in block_statuses.values() or "partial" in block_statuses.values():

            result_ctx["status"] = "partial"

        else:

            result_ctx["status"] = "ok"



        result_ctx["elapsed_ms"] = int((time.time() - start_ts) * 1000)

        if cache_ttl > 0 and self._should_cache_fundamental_context(result_ctx):

            with self._fundamental_cache_lock:

                self._fundamental_cache[cache_key] = {

                    "ts": time.time(),

                    "context": result_ctx,

                }

            self._prune_fundamental_cache(cache_ttl, cache_max_entries)

        return result_ctx



    def get_capital_flow_context(self, stock_code: str, budget_seconds: Optional[float] = None) -> Dict[str, Any]:

        """자금 흐름 랭킹 (fail-open)。"""

        from src.config import get_config



        config = get_config()

        stock_code = normalize_stock_code(stock_code)

        timeout = float(budget_seconds if budget_seconds is not None else config.fundamental_fetch_timeout_seconds)

        if _market_tag(stock_code) != "cn" or _is_etf_code(stock_code):

            return self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                ["not supported"],

            )



        if timeout <= 0:

            return self._build_fundamental_block(

                "failed",

                {},

                [{"provider": "fundamental_pipeline", "result": "failed", "duration_ms": 0}],

                ["fundamental stage timeout"],

            )

        payload, err, cost_ms = self._run_with_retry(

            lambda: self._fundamental_adapter.get_capital_flow(stock_code),

            timeout,

            "capital_flow",

        )

        if not isinstance(payload, dict):

            return self._build_fundamental_block(

                "failed",

                {},

                [{"provider": "fundamental_pipeline", "result": "failed", "duration_ms": cost_ms}],

                [err or "capital_flow failed"],

            )



        stock_flow = payload.get("stock_flow") or {}

        sector_rankings = payload.get("sector_rankings") or {}

        has_stock_flow = False

        if isinstance(stock_flow, dict):

            has_stock_flow = any(v is not None for v in stock_flow.values())

        has_sector_rankings = bool(sector_rankings.get("top")) or bool(sector_rankings.get("bottom"))

        adapter_status = str(payload.get("status", "not_supported"))

        if has_stock_flow or has_sector_rankings:

            capital_flow_status = "ok"

        elif adapter_status == "not_supported":

            capital_flow_status = "not_supported"

        else:

            capital_flow_status = "partial"



        return self._build_fundamental_block(

            capital_flow_status,

            {

                "stock_flow": payload.get("stock_flow", {}),

                "sector_rankings": payload.get("sector_rankings", {}),

            },

            self._normalize_source_chain(

                payload.get("source_chain", []),

                "capital_flow",

                capital_flow_status,

                cost_ms,

            ),

            list(payload.get("errors", [])) + ([err] if err else []),

        )



    def get_dragon_tiger_context(self, stock_code: str, budget_seconds: Optional[float] = None) -> Dict[str, Any]:

        """용호판 랭킹 (fail-open)。"""

        from src.config import get_config



        config = get_config()

        stock_code = normalize_stock_code(stock_code)

        timeout = float(budget_seconds if budget_seconds is not None else config.fundamental_fetch_timeout_seconds)

        if _market_tag(stock_code) != "cn" or _is_etf_code(stock_code):

            return self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                ["not supported"],

            )



        if timeout <= 0:

            return self._build_fundamental_block(

                "failed",

                {},

                [{"provider": "fundamental_pipeline", "result": "failed", "duration_ms": 0}],

                ["fundamental stage timeout"],

            )

        payload, err, cost_ms = self._run_with_retry(

            lambda: self._fundamental_adapter.get_dragon_tiger_flag(stock_code),

            timeout,

            "dragon_tiger",

        )

        if not isinstance(payload, dict):

            return self._build_fundamental_block(

                "failed",

                {},

                [{"provider": "fundamental_pipeline", "result": "failed", "duration_ms": cost_ms}],

                [err or "dragon_tiger failed"],

            )

        return self._build_fundamental_block(

            (payload.get("status") if isinstance(payload.get("status"), str) else "partial"),

            {

                "is_on_list": bool(payload.get("is_on_list", False)),

                "recent_count": int(payload.get("recent_count", 0)),

                "latest_date": payload.get("latest_date"),

            },

            self._normalize_source_chain(

                payload.get("source_chain", []),

                "dragon_tiger",

                str(payload.get("status", "ok")),

                cost_ms,

            ),

            list(payload.get("errors", [])) + ([err] if err else []),

        )



    def get_board_context(self, stock_code: str, budget_seconds: Optional[float] = None) -> Dict[str, Any]:

        """섹터 종목 랭킹 (fail-open)。"""

        from src.config import get_config



        config = get_config()

        stock_code = normalize_stock_code(stock_code)

        timeout = float(budget_seconds if budget_seconds is not None else config.fundamental_fetch_timeout_seconds)

        if _market_tag(stock_code) != "cn" or _is_etf_code(stock_code):

            return self._build_fundamental_block(

                "not_supported",

                {},

                [{"provider": "fundamental_pipeline", "result": "not_supported", "duration_ms": 0}],

                ["not supported"],

            )



        if timeout <= 0:

            return self._build_fundamental_block(

                "failed",

                {},

                [{"provider": "fundamental_pipeline", "result": "failed", "duration_ms": 0}],

                ["fundamental stage timeout"],

            )



        def task() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], str]:

            return self._get_sector_rankings_with_meta(5)



        rankings, err, cost_ms = self._run_with_retry(task, timeout, "boards")

        if isinstance(rankings, tuple) and len(rankings) == 4:

            top, bottom, chain, chain_error = rankings

            if chain_error and not err:

                err = chain_error

            if not top and not bottom:

                return self._build_fundamental_block(

                    "failed",

                    {},

                    chain if chain else [{"provider": "sector_rankings", "result": "failed", "duration_ms": cost_ms}],

                    [err or "boards empty from all sources"],

                )

            board_status = "ok" if top and bottom else "partial"

            return self._build_fundamental_block(

                board_status,

                {"top": top or [], "bottom": bottom or []},

                chain if chain else self._normalize_source_chain(

                    ["sector_rankings"],

                    "boards",

                    board_status,

                    cost_ms,

                ),

                [err] if err else [],

            )



        return self._build_fundamental_block(

            "failed",

            {},

            [{"provider": "sector_rankings", "result": "failed", "duration_ms": cost_ms}],

            [err or "boards failed"],

        )



    def _get_sector_rankings_with_meta(

            self,

            n: int = 5,

        ) -> Tuple[List[Dict], List[Dict], List[Dict[str, Any]], str]:

            """Get sector rankings with ordered fallback chain metadata."""

            source_chain: List[Dict[str, Any]] = []

            last_error = ""



            # zhijiebianliguanliqiyijingan priority paihaoxudeshujuyuanliebiao

            for fetcher in self._fetchers:

                if not hasattr(fetcher, 'get_sector_rankings'):

                    continue



                start = time.time()

                try:

                    data = fetcher.get_sector_rankings(n)

                    duration_ms = int((time.time() - start) * 1000)

                    if data and data[0] is not None and data[1] is not None:

                        source_chain.append(

                            {

                                "provider": fetcher.name,

                                "result": "ok",

                                "duration_ms": duration_ms,

                            }

                        )

                        logger.info(f"[{fetcher.name}] huoqubankuaipaihangchenggong")

                        return data[0], data[1], source_chain, ""



                    last_error = f"{fetcher.name}fanhuikongjieguo"

                    source_chain.append(

                        {

                            "provider": fetcher.name,

                            "result": "empty",

                            "duration_ms": duration_ms,

                            "error": last_error,

                        }

                    )

                except Exception as e:

                    error_type, error_reason = summarize_exception(e)

                    last_error = f"{fetcher.name} ({error_type}) {error_reason}"

                    duration_ms = int((time.time() - start) * 1000)

                    source_chain.append(

                        {

                            "provider": fetcher.name,

                            "result": "failed",

                            "duration_ms": duration_ms,

                            "error": error_reason,

                        }

                    )

                    logger.warning(f"[{fetcher.name}] huoqubankuaipaihangshibai: {error_reason}")



            return [], [], source_chain, last_error



    def get_sector_rankings(self, n: int = 5) -> Tuple[List[Dict], List[Dict]]:

        """섹터 등락/하락 순위 조회(자동전환데이터 소스)"""

        # anxuqiugudinghuituishunxu:Akshare(EM) -> Akshare(Sina) -> Tushare -> Efinance

        top, bottom, _, last_error = self._get_sector_rankings_with_meta(n)

        if top or bottom:

            return top, bottom

        logger.warning(f"[bankuaipaihang] suoyoushujuyuanjunshibai,zuizhongcuowu: {last_error}")

        return [], []



    def get_concept_rankings(self, n: int = 5) -> Tuple[List[Dict], List[Dict]]:

        """테맄/토픽 등락/하락 순위 조회(자동전환데이터 소스)。"""

        last_error = ""

        for fetcher in self._fetchers:

            try:

                data = fetcher.get_concept_rankings(n)

                if data and (data[0] or data[1]):

                    logger.info(f"[{fetcher.name}] huoqugainianpaihangchenggong")

                    return data[0] or [], data[1] or []

                last_error = f"{fetcher.name}fanhuikongjieguo"

            except Exception as e:

                error_type, error_reason = summarize_exception(e)

                last_error = f"{fetcher.name} ({error_type}) {error_reason}"

                logger.warning(f"[{fetcher.name}] huoqugainianpaihangshibai: {error_reason}")

        if last_error:

            logger.warning(f"[gainianpaihang] suoyoushujuyuanjunshibai,zuizhongcuowu: {last_error}")

        return [], []



    def get_hot_stocks(self, n: int = 10) -> List[Dict[str, Any]]:

        """시장 인기 종목 순위 조회(자동전환데이터 소스)。"""

        last_error = ""

        for fetcher in self._fetchers:

            try:

                data = fetcher.get_hot_stocks(n)

                if data:

                    logger.info(f"[{fetcher.name}] huoqurenqiguchenggong")

                    return data[:n]

                last_error = f"{fetcher.name}fanhuikongjieguo"

            except Exception as e:

                error_type, error_reason = summarize_exception(e)

                last_error = f"{fetcher.name} ({error_type}) {error_reason}"

                logger.warning(f"[{fetcher.name}] huoqurenqigushibai: {error_reason}")

        if last_error:

            logger.warning(f"[renqigu] suoyoushujuyuanjunshibai,zuizhongcuowu: {last_error}")

        return []



    def get_limit_up_pool(

        self,

        date: Optional[str] = None,

        n: int = 20,

    ) -> List[Dict[str, Any]]:

        """상한가 리스트yu연속 상한가 대업(자동전환데이터 소스)。"""

        last_error = ""

        for fetcher in self._fetchers:

            try:

                data = fetcher.get_limit_up_pool(date=date, n=n)

                if data:

                    logger.info(f"[{fetcher.name}] huoquzhangtingchichenggong")

                    return data[:n]

                last_error = f"{fetcher.name}fanhuikongjieguo"

            except Exception as e:

                error_type, error_reason = summarize_exception(e)

                last_error = f"{fetcher.name} ({error_type}) {error_reason}"

                logger.warning(f"[{fetcher.name}] huoquzhangtingchishibai: {error_reason}")

        if last_error:

            logger.warning(f"[zhangtingchi] suoyoushujuyuanjunshibai,zuizhongcuowu: {last_error}")

        return []

